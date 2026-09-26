"""The coach: studies losing games and proposes several different changes to the harness.

It never plays. It sees the current harness, losing games turn by turn with the player's own
reasons (so it can spot wrong beliefs), simple move statistics, lessons from earlier rounds
(Atlas vector search), and what was already tried and failed.
"""
import copy
import json
import time

from .harness import EDITABLE
from .tools import compile_tool

COACH_SYSTEM = """You improve the harness of an AI agent that plays Pokemon Showdown, Gen 1 OU, with a fixed team.
The harness is what the player reads every turn: a system prompt, learned rules, tools it wrote, and context settings.
The player model never changes; only the harness does. Your changes are tested on fresh battles and kept only if they win more.

Important: Gen 1 mechanics differ from modern Pokemon. Do not trust general Pokemon knowledge blindly. Base changes on what
the games show. Statistics are correlations: a move used mostly when already losing will look bad without being the cause.

Allowed change kinds:
  add_rule      value: one short, general rule for the player
  remove_rule   value: the exact text of an existing rule
  edit_prompt   value: a new system prompt (short)
  write_tool    value: {"name": "snake_case", "description": "what it tells the player",
                         "code": "def tool(state):\\n    ...\\n    return 'short hint'"}
  remove_tool   value: the name of a tool you wrote before
  set_context   value: {"history_turns": 0-6}   (how many of its own recent choices the player sees)

write_tool: the function runs every turn; its returned text is shown to the player. `state` is a dict:
{"turn", "me": {"species","types","hp","fainted","status"}, "opponent": {same}, "my_team": [same...],
"opponent_seen": [same...], "moves": [{"id","type","power","accuracy","category"}], "switches": [same as me]}.
Status values look like "par", "slp", "frz", "brn", "psn", or null. Plain Python only: no imports, no double underscores.
Keep a tool under ~60 lines. At most 3 written tools in a harness.

Propose 3 or 4 DIFFERENT candidate changes (different kinds or different ideas), each most likely to raise the win rate.
Respond with JSON only:
{"candidates": [{"kind": ..., "value": ..., "rationale": "one sentence citing what you saw", "lesson": "one sentence"}]}"""


def game_summary(doc: dict, last: int = 12) -> str:
    turns = doc["log"][-last:]
    lines = [f"  t{t['turn']} {t['me']}({t['me_hp']}%) vs {t['opp']}({t['opp_hp']}%"
             f"{', ' + t['opp_status'] if t.get('opp_status') else ''}) -> {t['action']}  | reason: {t['reason']}"
             for t in turns]
    return f"LOST in {doc['turns']} turns. Last {len(turns)} turns:\n" + "\n".join(lines)


def move_stats(docs: list[dict], top: int = 10) -> str:
    n = len(docs)
    if n < 6:
        return ""
    used: dict[str, set] = {}
    for i, d in enumerate(docs):
        for t in d["log"]:
            used.setdefault(t["action"], set()).add(i)
    rows = []
    for act, idx in used.items():
        k = len(idx)
        if 3 <= k <= n - 3:
            w = sum(docs[i]["won"] for i in idx) / k
            wo = sum(docs[i]["won"] for i in range(n) if i not in idx) / (n - k)
            rows.append((abs(w - wo), f"  {act}: in {k}/{n} battles, win rate {w:.0%} when used vs {wo:.0%} when not"))
    rows.sort(reverse=True)
    return "\n".join(r for _, r in rows[:top])


def build_prompt(cfg: dict, docs: list[dict], tried: list[dict], lessons: list[dict], n_games: int = 6) -> str:
    losses = [d for d in docs if not d["won"]][:n_games]
    view = {k: cfg[k] for k in EDITABLE}
    tried_txt = "\n".join(f"- {t.get('kind')}: {json.dumps(t.get('value'))[:160]}" for t in tried) or "- nothing yet"
    lesson_txt = "\n".join(f"- {h['text']}" for h in lessons) or "- none yet"
    wr = sum(d["won"] for d in docs) / max(1, len(docs))
    return (f"Current harness:\n{json.dumps(view, indent=2)}\n\n"
            f"It won {wr:.0%} of its last {len(docs)} battles.\n\n"
            f"Already tested and did NOT help (do not propose these again):\n{tried_txt}\n\n"
            f"Lessons from earlier rounds (found by vector search):\n{lesson_txt}\n\n"
            f"Move statistics from these battles (correlations, not causes):\n{move_stats(docs) or '  (too few battles)'}\n\n"
            "Losing games, with the player's own reasons:\n" + "\n\n".join(game_summary(d) for d in losses))


def parse_candidates(text: str) -> list[dict]:
    try:
        data = json.loads(text[text.find("{"): text.rfind("}") + 1], strict=False)
        cands = data.get("candidates", []) if isinstance(data, dict) else []
        return [c for c in cands if isinstance(c, dict) and c.get("kind")][:4]
    except ValueError:
        return []


async def propose(llm, cfg, docs, tried, lessons) -> tuple[list[dict], str]:
    prompt = build_prompt(cfg, docs, tried, lessons)
    text = await llm.complete(COACH_SYSTEM, prompt, llm.coach_model, max_tokens=6000)
    return parse_candidates(text), prompt


def apply_change(cfg: dict, change: dict, new_id: str) -> tuple[dict | None, str | None]:
    """A copy of the harness with one change applied, or (None, why it was rejected). Guardrails never change."""
    c = copy.deepcopy(cfg)
    c.update({"_id": new_id, "parent": cfg["_id"], "created": time.time(), "change": change, "status": "candidate"})
    c.pop("score", None)
    k, v = change.get("kind"), change.get("value")
    tools = c.setdefault("custom_tools", [])
    if k == "add_rule" and isinstance(v, str) and v.strip() and v not in c["rules"]:
        c["rules"].append(v.strip())
    elif k == "remove_rule" and v in c["rules"]:
        c["rules"].remove(v)
    elif k == "edit_prompt" and isinstance(v, str) and v.strip():
        c["system_prompt"] = v.strip()
    elif k == "write_tool" and isinstance(v, dict):
        name, code = str(v.get("name", "")).strip(), str(v.get("code", ""))
        if not name or any(t["name"] == name for t in tools):
            return None, "missing or duplicate tool name"
        if len(tools) >= 3:
            return None, "already 3 written tools"
        _, err = compile_tool(code)
        if err:
            return None, err
        tools.append({"name": name, "description": str(v.get("description", "")), "code": code})
    elif k == "remove_tool" and any(t["name"] == v for t in tools):
        c["custom_tools"] = [t for t in tools if t["name"] != v]
    elif k == "set_context" and isinstance(v, dict):
        c["context"] = {"history_turns": max(0, min(6, int(v.get("history_turns", 0))))}
    else:
        return None, f"not a valid {k} change"
    return c, None
