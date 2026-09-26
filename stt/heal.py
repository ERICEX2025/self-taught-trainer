"""The healer: a coding agent that reads the app's own observability and edits the app's own code.

    python -m stt.heal --run r6 [--push]

1. Makes a git worktree on a new branch heal/<run>-<time>, so the running app and main are never touched.
2. Runs Codex (`codex exec`) in that worktree with MCP servers attached:
     langfuse  every turn the player took (battle in, reason + move out, tokens, latency, invalid answers)
     sentry    crashes and error logs (works with self-hosted Sentry or GlitchTip)
   plus an offline copy of the run's battles from Atlas, so it still works if an MCP server is down.
3. Codex diagnoses one real problem, edits the code, and runs the selftest itself.
4. The gate, outside Codex's control: only allowed files changed, the grader and guardrails are untouched,
   and `python -m stt.selftest` passes in the worktree. Pass -> commit on the branch (push with --push).
   Fail -> the branch is thrown away. Main is only changed by a human merging the branch.

Env: LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL for Langfuse MCP; SENTRY_ACCESS_TOKEN (+ SENTRY_HOST for a
self-hosted Sentry/GlitchTip, e.g. glitchtip.example.com; optional MCP_SKILLS, default "inspect" when self-hosted)
for Sentry MCP. Either can be missing. Langfuse MCP is limited to read-only tools.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .env import load_env

load_env()
from . import tracing  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PY = str(REPO / ".venv" / "bin" / "python")
ALLOWED = ("stt/adapter.py", "stt/harness.py", "stt/tools.py", "stt/coach.py", "stt/coach_codex.py",
           "stt/tracing.py", "stt/llm.py", "tests/", "HEAL_REPORT.md")
# The healer reads telemetry; it may not rewrite it (no scores, prompts, datasets or evaluators).
LANGFUSE_READ_TOOLS = ["listObservations", "getObservation", "getObservationFieldSchema", "getObservationFilterSchema",
                       "getObservationFilterValues", "queryMetrics", "getMetricsSchema", "listScores", "getScore",
                       "listPrompts", "getPrompt", "getHealth"]
# The agent may not grade itself: the scorer, the keep rule, the teams and the selftest stay fixed.
PROTECTED = ("stt/evaluate.py", "stt/loop.py", "stt/selftest.py", "stt/heal.py", "heldout.py", "teams/", ".env")

TASK = """You are the healer for this codebase: an LLM that plays Pokemon Showdown Gen 1 OU, plus a coach that
rewrites the player's prompt, rules and tools between rounds. Read README.md and HEAL.md first.

Your job: use the app's own observability to find ONE real defect in the code (not in strategy) and fix it.
Look at run "{run}".
- Langfuse MCP (if connected): observations in session "{run}". Each turn is a generation; metadata has action,
  invalid, latency_s. Look for invalid answers, parse failures, slow or huge prompts, missing battle info the
  player keeps asking for or guessing wrong, tool outputs that are wrong.
- Sentry MCP (if connected): recent issues and stack traces from this app.
- Offline copy: observability/battles.jsonl and observability/summary.json (same run, from MongoDB).

Rules:
- Only edit: {allowed}. Never edit: {protected}. Do not change GUARDRAILS in stt/harness.py.
- Smallest fix that addresses what the data shows. No refactors, no new dependencies.
- Run `{py} -m stt.selftest` and make sure it passes.
- Write HEAL_REPORT.md: what the traces showed (cite trace/observation ids or battle ids and numbers),
  the diagnosis, the fix, and how to tell if it worked.
- If you find no code defect worth fixing, change nothing except HEAL_REPORT.md explaining why.
Final message: one paragraph summary."""


def git(*args, cwd=REPO, check=True) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check).stdout.strip()


def export_run(run: str, out: Path) -> dict:
    """Offline copy of the run's battles from Atlas, and a small summary."""
    out.mkdir(parents=True, exist_ok=True)
    try:
        from .store import Store
        docs = list(Store().db.battles.find({"run": run}, {"_id": 0, "at": 0}).sort("at", -1).limit(120))
    except Exception as e:
        docs = []
        (out / "error.txt").write_text(f"could not read MongoDB: {e}")
    turns = [t for d in docs for t in d.get("log", [])]
    with (out / "battles.jsonl").open("w") as f:
        for d in docs:
            f.write(json.dumps(d, default=str) + "\n")
    summary = {"run": run, "battles": len(docs), "won": sum(bool(d.get("won")) for d in docs), "turns": len(turns),
               "invalid_turns": sum(bool(t.get("invalid")) for t in turns),
               "versions": sorted({d.get("version", "?") for d in docs})}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def mcp_config() -> tuple[list[str], dict, list[str]]:
    """Codex -c overrides for the MCP servers we have keys for. Secrets travel in env vars, never argv."""
    args, env, attached = [], {}, []
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if pk and sk:
        base = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"
        env["STT_LANGFUSE_MCP_AUTH"] = "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()
        args += ["-c", f'mcp_servers.langfuse.url="{base.rstrip("/")}/api/public/mcp"',
                 "-c", 'mcp_servers.langfuse.env_http_headers={"Authorization"="STT_LANGFUSE_MCP_AUTH"}',
                 "-c", "mcp_servers.langfuse.enabled_tools=" + json.dumps(LANGFUSE_READ_TOOLS)]
        attached.append("langfuse")
    if os.environ.get("SENTRY_ACCESS_TOKEN"):
        env_vars = ["SENTRY_ACCESS_TOKEN"] + [k for k in ("SENTRY_HOST", "MCP_SKILLS") if os.environ.get(k)]
        args += ["-c", 'mcp_servers.sentry.command="npx"',
                 "-c", 'mcp_servers.sentry.args=["-y","@sentry/mcp-server@latest"]',
                 "-c", "mcp_servers.sentry.env_vars=" + json.dumps(env_vars)]
        attached.append("sentry")
    return args, env, attached


def gate(wt: Path) -> tuple[bool, list[str], str]:
    """Checks Codex cannot skip. Returns (ok, changed files, reason)."""
    git("add", "-A", cwd=wt)
    changed = [f for f in git("diff", "--cached", "--name-only", cwd=wt).splitlines() if f]
    bad = [f for f in changed if f.startswith(PROTECTED) or not f.startswith(ALLOWED)]
    if bad:
        return False, changed, f"touched files it may not edit: {', '.join(bad)}"
    probe = "from stt.harness import GUARDRAILS; print(GUARDRAILS)"
    if subprocess.run([PY, "-c", probe], cwd=wt, capture_output=True, text=True).stdout != \
            subprocess.run([PY, "-c", probe], cwd=REPO, capture_output=True, text=True).stdout:
        return False, changed, "changed the locked guardrails"
    t = subprocess.run([PY, "-m", "stt.selftest"], cwd=wt, capture_output=True, text=True, timeout=120)
    if t.returncode != 0:
        return False, changed, "selftest failed: " + (t.stdout + t.stderr)[-600:]
    return True, changed, "selftest passed"


def heal(run: str, push: bool = False, timeout: int = 900) -> dict:
    stamp = time.strftime("%H%M%S")
    safe = "".join(c if c.isalnum() or c in "._-" else "-" for c in run)
    branch = f"heal/{safe}-{stamp}"
    wt = REPO.parent / "stt-heal" / f"{safe}-{stamp}"
    wt.parent.mkdir(exist_ok=True)
    git("worktree", "add", "-b", branch, str(wt), "HEAD")
    for name in (".env",):
        if (REPO / name).exists():
            os.symlink(REPO / name, wt / name)        # so the selftest's imports can read settings; gate blocks edits
    (wt / ".venv").symlink_to(REPO / ".venv")
    exclude = Path(git("rev-parse", "--git-path", "info/exclude", cwd=wt))
    exclude = exclude if exclude.is_absolute() else wt / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    have = exclude.read_text().splitlines() if exclude.exists() else []
    exclude.write_text("\n".join(have + [x for x in (".env", ".venv", "observability/", "HEAL.md") if x not in have]) + "\n")

    summary = export_run(run, wt / "observability")
    mcp_args, mcp_env, attached = mcp_config()
    (wt / "HEAL.md").write_text(f"MCP servers attached: {', '.join(attached) or 'none (use observability/ only)'}\n"
                                f"Run summary: {json.dumps(summary)}\n")
    task = TASK.format(run=run, allowed=", ".join(ALLOWED), protected=", ".join(PROTECTED), py=PY)

    started = time.time()
    out = wt / "observability" / "last_message.txt"
    proc = subprocess.run(["codex", "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(wt),
                           *mcp_args, "-o", str(out), task],
                          env={**os.environ, **mcp_env}, capture_output=True, text=True, timeout=timeout)
    final = out.read_text() if out.exists() else (proc.stdout + proc.stderr)[-2000:]

    ok, changed, reason = gate(wt)
    code_changed = [f for f in changed if f != "HEAL_REPORT.md"]
    result = {"run": run, "branch": branch, "mcp": attached, "seconds": round(time.time() - started),
              "changed": changed, "passed_gate": ok, "gate": reason, "summary": final[-1500:], "at": time.time()}
    if ok and changed:
        git("commit", "-m", f"heal({run}): {final.strip().splitlines()[0][:60] if final.strip() else 'self-heal'}\n\n"
            f"Healer read: {', '.join(attached) or 'offline battles'}. Gate: {reason}.", cwd=wt)
        result["commit"] = git("rev-parse", "--short", "HEAD", cwd=wt)
        if push and code_changed:
            git("push", "-u", "origin", branch, cwd=wt)
            result["pushed"] = True
    report = wt / "HEAL_REPORT.md"
    result["report"] = report.read_text()[:6000] if report.exists() else ""
    if not ok:
        git("worktree", "remove", "--force", str(wt), check=False)
        git("branch", "-D", branch, check=False)

    try:
        from .store import Store
        Store().db.heals.insert_one(dict(result))
    except Exception:
        pass
    tracing.event("heal", trace_id=None, session=run, tags=["healer"], output=result["summary"],
                  metadata={k: result[k] for k in ("branch", "mcp", "changed", "passed_gate", "gate", "seconds")})
    tracing.flush()
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--push", action="store_true", help="push the heal branch (never main) if it passed the gate")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    r = heal(a.run, a.push, a.timeout)
    print(json.dumps({k: v for k, v in r.items() if k not in ("report",)}, indent=2, default=str))
    sys.exit(0 if r["passed_gate"] else 1)
