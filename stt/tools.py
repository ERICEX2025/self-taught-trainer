"""Tools the coach writes itself, as small Python functions run in a restricted sandbox.

The coach writes:   def tool(state): ... return "one short hint"
`state` is a plain dict of battle facts (no game objects). The code gets a tiny set of
builtins, banned words are rejected up front, and every tool is test-run on a sample battle
before it is accepted. At play time, any error just means the tool adds nothing that turn.
"""
SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n) for n in (
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len", "list", "max", "min",
    "range", "round", "set", "sorted", "str", "sum", "tuple", "zip", "isinstance")}
BANNED = ("import", "__", "open(", "exec", "eval", "globals", "locals", "getattr", "setattr", "compile", "input(")


def battle_state(battle) -> dict:
    """The same facts the player already sees as text, as a dict."""
    def mon(p):
        if not p:
            return None
        return {"species": p.species, "types": [t.name.lower() for t in p.types if t],
                "hp": round((p.current_hp_fraction or 0) * 100), "fainted": p.fainted,
                "status": p.status.name.lower() if p.status else None}
    return {
        "turn": battle.turn,
        "me": mon(battle.active_pokemon), "opponent": mon(battle.opponent_active_pokemon),
        "my_team": [mon(p) for p in battle.team.values()],
        "opponent_seen": [mon(p) for p in battle.opponent_team.values()],
        "moves": [{"id": m.id, "type": m.type.name.lower(), "power": m.base_power,
                   "accuracy": 1.0 if m.accuracy is True else float(m.accuracy),
                   "category": m.category.name.lower()} for m in battle.available_moves],
        "switches": [mon(p) for p in battle.available_switches],
    }


SAMPLE = {
    "turn": 5,
    "me": {"species": "chansey", "types": ["normal"], "hp": 70, "fainted": False, "status": None},
    "opponent": {"species": "alakazam", "types": ["psychic"], "hp": 90, "fainted": False, "status": None},
    "my_team": [{"species": "chansey", "types": ["normal"], "hp": 70, "fainted": False, "status": None},
                {"species": "tauros", "types": ["normal"], "hp": 100, "fainted": False, "status": "par"}],
    "opponent_seen": [{"species": "alakazam", "types": ["psychic"], "hp": 90, "fainted": False, "status": None},
                      {"species": "snorlax", "types": ["normal"], "hp": 40, "fainted": False, "status": "slp"}],
    "moves": [{"id": "thunderwave", "type": "electric", "power": 0, "accuracy": 1.0, "category": "status"},
              {"id": "icebeam", "type": "ice", "power": 95, "accuracy": 1.0, "category": "special"},
              {"id": "softboiled", "type": "normal", "power": 0, "accuracy": 1.0, "category": "status"}],
    "switches": [{"species": "tauros", "types": ["normal"], "hp": 100, "fainted": False, "status": "par"}],
}


def compile_tool(code: str):
    """(function, None) if the code is safe and works on the sample battle, else (None, reason)."""
    low = code.lower()
    for bad in BANNED:
        if bad in low:
            return None, f"not allowed: {bad!r}"
    ns: dict = {"__builtins__": SAFE_BUILTINS}
    try:
        exec(code, ns)  # noqa: S102  restricted builtins, banned words checked above
    except Exception as e:
        return None, f"does not compile: {type(e).__name__}: {e}"
    fn = ns.get("tool")
    if not callable(fn):
        return None, "must define a function named tool(state)"
    try:
        out = fn(dict(SAMPLE))
    except Exception as e:
        return None, f"crashed on the sample battle: {type(e).__name__}: {e}"
    if not isinstance(out, str):
        return None, "must return a string (an empty string is fine when there is nothing to say)"
    return fn, None


def load_tools(cfg: dict) -> list:
    """Compile a version's written tools into [(name, battle -> text)] for the player."""
    out = []
    for t in cfg.get("custom_tools", []):
        fn, _ = compile_tool(t["code"])
        if fn:
            def run(battle, fn=fn):
                try:
                    r = fn(battle_state(battle))
                    return r.strip()[:600] if isinstance(r, str) else ""
                except Exception:
                    return ""
            out.append((t["name"], run))
    return out
