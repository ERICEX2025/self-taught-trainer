"""Play N battles with one harness version against a fixed local opponent."""
import random
import time
from pathlib import Path

from poke_env import AccountConfiguration, LocalhostServerConfiguration
from poke_env.player import MaxBasePowerPlayer, RandomPlayer, SimpleHeuristicsPlayer
from poke_env.teambuilder import Teambuilder

from .harness import HarnessPlayer

FORMAT = "gen1ou"
TEAM = Path(__file__).resolve().parent.parent.joinpath("teams", "gen1ou.txt").read_text()
OPP_TEAMS = [p.read_text() for p in sorted(Path(__file__).resolve().parent.parent.joinpath("teams", "opponents").glob("*.txt"))]
VARIED = {"on": False}  # set by the loop: opponents rotate through OPP_TEAMS instead of mirroring our team


class RotatingTeams(Teambuilder):
    """A different real Gen 1 OU team for each battle, cycling in order so every version sees the same mix."""
    def __init__(self, teams):
        self.teams = [self.join_team(self.parse_showdown_team(t)) for t in teams]
        self.i = 0

    def yield_team(self):
        t = self.teams[self.i % len(self.teams)]
        self.i += 1
        return t


OPPONENTS = {"random": RandomPlayer, "maxpower": MaxBasePowerPlayer, "heuristic": SimpleHeuristicsPlayer}


def _name(prefix: str) -> str:
    return f"{prefix}{random.randint(10000, 99999)}"[:18]


async def evaluate(cfg: dict, llm, n: int, opponent: str = "heuristic", tools=None, on_finish=None,
                   concurrency: int = 8, opponent_cfg: dict | None = None, opponent_tools=None
                   ) -> tuple[float, list[dict], HarnessPlayer]:
    me = HarnessPlayer(cfg, llm, on_finish=on_finish, tools=tools, battle_format=FORMAT, team=TEAM,
                       account_configuration=AccountConfiguration(_name(f"stt{cfg['_id']}"), None),
                       max_concurrent_battles=concurrency, save_replays="replays")
    if opponent == "self":  # self-play: the opponent is another harness version, played by the same model
        opp = HarnessPlayer(opponent_cfg, llm, tools=opponent_tools, battle_format=FORMAT, team=TEAM,
                            account_configuration=AccountConfiguration(_name("self"), None),
                            max_concurrent_battles=concurrency)
    else:
        opp_team = RotatingTeams(OPP_TEAMS) if VARIED["on"] and OPP_TEAMS else TEAM
        opp = OPPONENTS[opponent](battle_format=FORMAT, team=opp_team, max_concurrent_battles=concurrency,
                                  account_configuration=AccountConfiguration(_name("opp"), None),
                                  server_configuration=LocalhostServerConfiguration)
    await me.battle_against(opp, n_battles=n)
    docs = []
    for tag, b in me.battles.items():
        docs.append({"version": cfg["_id"], "battle": tag, "won": bool(b.won), "turns": b.turn,
                     "opponent": f"self:{opponent_cfg['_id']}" if opponent == "self" else opponent, "at": time.time(),
                     "replay": f"replays/{me.username} - {tag}.html",
                     "log": [{k: v for k, v in t.items() if k != "context"} for t in me.turn_log.get(tag, [])]})
    return sum(d["won"] for d in docs) / max(1, len(docs)), docs, me


async def evaluate_external(cfg: dict, llm, n: int, opponent_user: str, tools=None, on_finish=None,
                            concurrency: int = 4) -> tuple[float, list[dict], HarnessPlayer]:
    """Play n battles against an opponent running in another process (e.g. a Metamon RL agent) that
    accepts challenges on the local server under the username opponent_user."""
    me = HarnessPlayer(cfg, llm, on_finish=on_finish, tools=tools, battle_format=FORMAT, team=TEAM,
                       account_configuration=AccountConfiguration(_name(f"stt{cfg['_id']}"), None),
                       max_concurrent_battles=concurrency, save_replays="replays")
    await me.send_challenges(opponent_user, n)
    docs = []
    for tag, b in me.battles.items():
        docs.append({"version": cfg["_id"], "battle": tag, "won": bool(b.won), "turns": b.turn,
                     "opponent": f"ext:{opponent_user}", "at": time.time(),
                     "replay": f"replays/{me.username} - {tag}.html",
                     "log": [{k: v for k, v in t.items() if k != "context"} for t in me.turn_log.get(tag, [])]})
    return sum(d["won"] for d in docs) / max(1, len(docs)), docs, me
