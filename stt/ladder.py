"""Put a harness version on the PokeAgent benchmark ladder (Gen 1 OU, standard timer).

  python -m stt.ladder stt-base v1 30        # agent name, harness version id, number of games

The harness version is loaded from Atlas (v1 is built in), so the ladder agent plays exactly
what the loop tested. Every ladder battle is saved to Atlas under run "ladder:<agent>".
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from poke_env import AccountConfiguration, ServerConfiguration

from .env import load_env

load_env()
from .evaluate import FORMAT, TEAM  # noqa: E402
from .harness import HarnessPlayer, v1  # noqa: E402
from .llm import LLM  # noqa: E402
from .store import Store  # noqa: E402

POKEAGENT = ServerConfiguration(
    "wss://battling.pokeagentchallenge.com/showdown/websocket",
    "https://battling.pokeagentchallenge.com/action.php?",
)


def load_version(store: Store, vid: str) -> dict:
    if vid == "v1":
        return v1()
    cfg = store.versions.find_one({"_id": vid})
    if not cfg:
        raise SystemExit(f"no harness version {vid!r} in Atlas")
    return cfg


async def main(agent: str, vid: str, n: int):
    store, llm = Store(), LLM()
    cfg = load_version(store, vid)
    status = Path(f"ladder-{agent}.json")
    results: list[dict] = []

    def on_finish(player, battle):
        doc = {"agent": agent, "version": vid, "battle": battle.battle_tag, "won": bool(battle.won),
               "turns": battle.turn, "opponent": battle.opponent_username, "at": time.time(),
               "rating": getattr(battle, "rating", None),
               "log": [{k: v for k, v in t.items() if k != "context"} for t in player.turn_log.get(battle.battle_tag, [])]}
        results.append(doc)
        store.save_battles([doc], run=f"ladder:{agent}")
        status.write_text(json.dumps({"agent": agent, "version": vid, "played": len(results),
                                      "won": sum(r["won"] for r in results),
                                      "recent": [{k: r[k] for k in ("battle", "won", "turns", "opponent")} for r in results[-10:]]}))
        print(f"{agent} ({vid}) {'WON ' if battle.won else 'lost'} in {battle.turn} turns vs {battle.opponent_username}"
              f" | {sum(r['won'] for r in results)}/{len(results)}", flush=True)

    player = HarnessPlayer(cfg, llm, on_finish=on_finish, battle_format=FORMAT, team=TEAM,
                           account_configuration=AccountConfiguration(agent, os.environ["POKEAGENT_PASSWORD"]),
                           server_configuration=POKEAGENT, max_concurrent_battles=1,
                           start_timer_on_battle_start=True)
    await player.ladder(n)
    print(f"done: {agent} won {sum(r['won'] for r in results)}/{len(results)} | "
          f"{llm.avg_seconds:.2f}s per move | invalid {player.invalid}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1))
