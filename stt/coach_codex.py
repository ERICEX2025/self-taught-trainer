"""The coach as a Codex agent (runs on the user's ChatGPT plan via `codex exec`).

Instead of reading a text summary, the coach gets a scratch folder with every battle as data and
investigates it by writing and running its own Python scripts, then proposes changes.
Sandbox: it may only write inside that folder, with no network. Falls back to the API coach on failure.
"""
import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path

from .coach import COACH_SYSTEM, move_stats, parse_candidates
from .harness import EDITABLE

TASK = """You are the coach. Read README.md first; it explains the job and the allowed changes.

Investigate before deciding: battles.jsonl has every battle the current harness played (won or lost, and every
turn with the move and the player's own reason). Write and run small Python scripts in this folder to find
patterns that separate wins from losses. Be careful about correlation vs cause (a move used mostly when already
losing will look bad). Name each script after what it checks, e.g. check_hyperbeam_after_ko.py.

When done, write your answer to candidates.json in exactly this format, and also print it as your final message:
{"candidates": [{"kind": ..., "value": ..., "rationale": "one sentence citing what your analysis found", "lesson": "one sentence"}]}
Propose 3 or 4 DIFFERENT changes."""


def _workspace(cfg: dict, docs: list[dict], tried: list[dict], lessons: list[dict], evidence: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="stt-coach-"))
    (d / "README.md").write_text(COACH_SYSTEM + "\n\nFiles: harness.json (current harness), battles.jsonl (one battle per line), "
                                 "tried.json (changes already tested that did NOT help; don't repeat), lessons.json "
                                 "(lessons from earlier rounds), move_stats.txt (simple correlations), evidence.txt (extra evidence, may be empty).\n")
    (d / "harness.json").write_text(json.dumps({k: cfg[k] for k in EDITABLE}, indent=2))
    with (d / "battles.jsonl").open("w") as f:
        for b in docs:
            f.write(json.dumps({"won": b["won"], "turns": b["turns"], "opponent": b.get("opponent"), "log": b["log"]}) + "\n")
    (d / "tried.json").write_text(json.dumps(tried, indent=2, default=str))
    (d / "lessons.json").write_text(json.dumps([{"text": h["text"]} for h in lessons], indent=2))
    (d / "move_stats.txt").write_text(move_stats(docs) or "")
    (d / "evidence.txt").write_text(evidence or "")
    return d


async def propose(cfg, docs, tried, lessons, evidence: str = "", timeout: int = 600) -> tuple[list[dict], str, str, list[dict]]:
    """Returns (candidates, summary of what it was given, raw final message, scripts it wrote)."""
    d = _workspace(cfg, docs, tried, lessons, evidence)
    started = time.time()
    proc = await asyncio.create_subprocess_exec(
        "codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "workspace-write", "-C", str(d),
        "-o", str(d / "last_message.txt"), TASK,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
    raw = ""
    for name in ("candidates.json", "last_message.txt"):
        p = d / name
        if p.exists():
            raw = p.read_text()
            cands = parse_candidates(raw)
            if cands:
                break
    else:
        cands = []
    scripts = [{"name": p.name, "code": p.read_text()[:4000]} for p in sorted(d.glob("*.py"))][:8]
    summary = (f"Codex coach workspace: {len(docs)} battles as data, {len(tried)} tried changes, {len(lessons)} lessons. "
               f"Ran {round(time.time() - started)} s and wrote {len(scripts)} analysis scripts.")
    shutil.rmtree(d, ignore_errors=True)
    return cands, summary, raw[-4000:], scripts
