"""The harness as a document, and the player that reads it every turn.

A version of the harness is a small dict: instructions, rules, tools the coach wrote, and
context settings, plus guardrails nobody can edit. Changing the dict changes how the player
plays; the code and the model stay the same.
"""
import random
import re
import time

from poke_env import AccountConfiguration, LocalhostServerConfiguration
from poke_env.player import Player

from . import tracing
from .adapter import describe, legal_actions

GUARDRAILS = [
    "End your reply with one line: action: <one action id copied exactly from the legal actions list>.",
    "Never forfeit or stall on purpose.",
]
EDITABLE = ("system_prompt", "rules", "custom_tools", "context")
ACTION_RE = re.compile(r"action:\s*([^\n]+)", re.I)
REASON_RE = re.compile(r"reason:\s*(.+)", re.I)


def v1() -> dict:
    """The starting harness: generic, no rules, no tools, nothing about Pokémon strategy."""
    return {
        "_id": "v1", "parent": None, "created": time.time(), "status": "baseline",
        "system_prompt": "You are playing a turn-based game. Each turn you see the state and your legal actions. Your goal is to win.",
        "rules": [], "custom_tools": [], "context": {"history_turns": 0},
        "guardrails": GUARDRAILS, "change": None,
    }


def resolve_action(raw: str, legal: dict) -> str | None:
    """Match the model's answer to a legal id. Models often drop the 'move:' prefix or add spaces."""
    key = re.sub(r"[^a-z0-9:]", "", raw.lower())
    if key in legal:
        return key
    bare = key.split(":", 1)[-1]
    for prefix in ("move:", "switch:"):
        if prefix + bare in legal:
            return prefix + bare
    return None


class HarnessPlayer(Player):
    def __init__(self, cfg: dict, llm, on_finish=None, tools=None, **kw):
        kw.setdefault("server_configuration", LocalhostServerConfiguration)
        super().__init__(**kw)
        self.cfg, self.llm, self.on_finish = cfg, llm, on_finish
        self.tools = tools or []          # [(name, compiled function)] for this version
        self.turn_log: dict[str, list] = {}
        self.invalid = 0

    def _battle_finished_callback(self, battle):
        vid = self.cfg["_id"]
        tracing.event("battle result", trace_id=tracing.battle_trace_id(battle.battle_tag, vid),
                      session=self.cfg.get("run", "adhoc"), tags=[vid, "battle"],
                      output={"won": bool(battle.won), "turns": battle.turn},
                      metadata={"version": vid, "battle": battle.battle_tag, "opponent": battle.opponent_username,
                                "invalid_answers": sum(t["invalid"] for t in self.turn_log.get(battle.battle_tag, []))})
        if self.on_finish:
            self.on_finish(self, battle)

    def system_text(self) -> str:
        parts = [self.cfg["system_prompt"]]
        if self.cfg["rules"]:
            parts.append("Rules you have learned:\n" + "\n".join(f"- {r}" for r in self.cfg["rules"]))
        parts.append("Answer format: first a line 'reason: <one short sentence>', then a line 'action: <id>'.")
        parts.append("Hard constraints:\n" + "\n".join(f"- {g}" for g in self.cfg["guardrails"]))
        return "\n\n".join(parts)

    def context_text(self, battle) -> str:
        blocks = [describe(battle)]
        for name, fn in self.tools:
            out = fn(battle)
            if out:
                blocks.append(f"Tool {name} (written by you):\n{out}")
        n = self.cfg["context"].get("history_turns", 0)
        hist = self.turn_log.get(battle.battle_tag, [])[-n:] if n else []
        if hist:
            blocks.append("Your recent choices:\n" + "\n".join(
                f"  turn {h['turn']}: {h['action']} ({h['reason']})" for h in hist))
        return "\n\n".join(blocks)

    async def choose_move(self, battle):
        acts = dict(legal_actions(battle))
        if not acts:
            return self.choose_random_move(battle)
        context = self.context_text(battle)
        vid = self.cfg["_id"]
        usage: dict = {}
        meta = {"version": vid, "battle": battle.battle_tag, "turn": battle.turn}
        obs = tracing.start_generation(f"turn {battle.turn} · {vid}", trace_id=tracing.battle_trace_id(battle.battle_tag, vid),
                                       session=self.cfg.get("run", "adhoc"), tags=[vid, "player"], model=self.llm.play_model,
                                       input={"system": self.system_text(), "battle": context}, metadata=meta)
        text = await self.llm.complete(self.system_text(), context, self.llm.play_model, usage=usage)
        m, r = ACTION_RE.search(text or ""), REASON_RE.search(text or "")
        choice = resolve_action(m.group(1), acts) if m else None
        invalid = choice is None
        tracing.end_generation(obs, output=text, usage={k: v for k, v in usage.items() if k in ("input", "output", "total")},
                               metadata={**meta, "action": choice, "invalid": invalid, "latency_s": usage.get("latency_s")})
        if invalid:  # guardrail: never send an illegal move
            self.invalid += 1
            choice = random.choice(list(acts))
        me, opp = battle.active_pokemon, battle.opponent_active_pokemon
        self.turn_log.setdefault(battle.battle_tag, []).append({
            "turn": battle.turn, "action": choice, "reason": (r.group(1).strip()[:200] if r else ""),
            "invalid": invalid, "context": context,
            "me": me.species if me else None, "opp": opp.species if opp else None,
            "me_hp": round((me.current_hp_fraction or 0) * 100) if me else 0,
            "opp_hp": round((opp.current_hp_fraction or 0) * 100) if opp else 0,
            "opp_status": opp.status.name.lower() if opp and opp.status else None,
        })
        return self.create_order(acts[choice])
