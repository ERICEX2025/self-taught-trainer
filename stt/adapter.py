"""The only game-specific code: describe a battle as text and list the legal actions.

Raw facts only. Anything that helps decide (matchups, damage, statistics) belongs to tools,
which the harness has to choose to turn on.
"""


def _hp(p) -> str:
    return f"{round((p.current_hp_fraction or 0) * 100)}%"


def _types(p) -> str:
    return "/".join(t.name.title() for t in p.types if t) if p else "unknown"


def _status(p) -> str:
    return f", {p.status.name.lower()}" if p and p.status else ""


def legal_actions(battle) -> list[tuple[str, object]]:
    """(action id, poke-env object). The ids are what the player answers with."""
    acts = [(f"move:{m.id}", m) for m in battle.available_moves]
    acts += [(f"switch:{p.species}", p) for p in battle.available_switches]
    return acts


def describe(battle) -> str:
    me, opp = battle.active_pokemon, battle.opponent_active_pokemon
    lines = [f"Turn {battle.turn}."]
    if me:
        lines.append(f"Your active: {me.species} ({_types(me)}), HP {_hp(me)}{_status(me)}")
    if opp:
        lines.append(f"Opponent active: {opp.species} ({_types(opp)}), HP {_hp(opp)}{_status(opp)}")
    bench = [p for p in battle.team.values() if not p.active]
    if bench:
        lines.append("Your bench: " + ", ".join(
            f"{p.species} {'fainted' if p.fainted else _hp(p)}{_status(p)}" for p in bench))
    seen = [p for p in battle.opponent_team.values() if not p.active]
    if seen:
        lines.append("Opponent Pokémon seen: " + ", ".join(
            f"{p.species} {'fainted' if p.fainted else _hp(p)}{_status(p)}" for p in seen))
    lines.append("Legal actions:")
    for aid, obj in legal_actions(battle):
        # poke-env gives these commands placeholder stats, not actual move data.
        if aid == "move:fight":
            lines.append(f"  {aid}  continue the turn without selecting an attack "
                         "(asleep, frozen, or partially trapped)")
        elif aid == "move:recharge":
            lines.append(f"  {aid}  recharge this turn")
        elif aid.startswith("move:"):
            acc = 1.0 if obj.accuracy is True else obj.accuracy
            lines.append(f"  {aid}  type {obj.type.name.title()}, power {obj.base_power}, "
                         f"{obj.category.name.lower()}, accuracy {acc}")
        else:
            lines.append(f"  {aid}  ({_types(obj)}, HP {_hp(obj)}{_status(obj)})")
    return "\n".join(lines)
