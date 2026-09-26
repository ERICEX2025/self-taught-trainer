"""Play N battles with one harness version against a fixed local opponent."""
import random
import time
from pathlib import Path

from poke_env import AccountConfiguration, LocalhostServerConfiguration
from poke_env.player import MaxBasePowerPlayer, RandomPlayer, SimpleHeuristicsPlayer

from .harness import HarnessPlayer

FORMAT = "gen1ou"
TEAM = Path(__file__).resolve().parent.parent.joinpath("teams", "gen1ou.txt").read_text()
OPPONENTS = {"random": RandomPlayer, "maxpower": MaxBasePowerPlayer, "heuristic": SimpleHeuristicsPlayer}


def _name(prefix: str) -> str:
    return f"{prefix}{random.randint(10000, 99999)}"[:18]


async def evaluate(cfg: dict, llm, n: int, opponent: str = "heuristic", tools=None, on_finish=None,
                   concurrency: int = 8) -> tuple[float, list[dict], HarnessPlayer]:
    me = HarnessPlayer(cfg, llm, on_finish=on_finish, tools=tools, battle_format=FORMAT, team=TEAM,
                       account_configuration=AccountConfiguration(_name(f"stt{cfg['_id']}"), None),
                       max_concurrent_battles=concurrency, save_replays="replays")
    opp = OPPONENTS[opponent](battle_format=FORMAT, team=TEAM, max_concurrent_battles=concurrency,
                              account_configuration=AccountConfiguration(_name("opp"), None),
                              server_configuration=LocalhostServerConfiguration)
    await me.battle_against(opp, n_battles=n)
    docs = []
    for tag, b in me.battles.items():
        docs.append({"version": cfg["_id"], "battle": tag, "won": bool(b.won), "turns": b.turn,
                     "opponent": opponent, "at": time.time(),
                     "replay": f"replays/{me.username} - {tag}.html",
                     "log": [{k: v for k, v in t.items() if k != "context"} for t in me.turn_log.get(tag, [])]})
    return sum(d["won"] for d in docs) / max(1, len(docs)), docs, me
