"""Ladder and run statistics computed inside Atlas with aggregation pipelines.

  python -m stt.stats          (loops every 60 s; the lab reads stats.json)
"""
import json
import time
from pathlib import Path

from .env import load_env

load_env()
from .store import Store  # noqa: E402

LADDER_BY_FAMILY = [
    {"$match": {"run": {"$regex": "^ladder:"}}},
    {"$addFields": {"family": {"$arrayElemAt": [{"$split": ["$opponent", "-"]}, 0]}}},
    {"$group": {"_id": {"agent": "$agent", "family": "$family"},
                "games": {"$sum": 1}, "wins": {"$sum": {"$cond": ["$won", 1, 0]}}}},
    {"$sort": {"_id.agent": 1, "_id.family": 1}},
]
RUN_BY_VERSION = [
    {"$match": {"run": {"$not": {"$regex": "^ladder:"}}}},
    {"$group": {"_id": {"run": "$run", "version": "$version"}, "battles": {"$sum": 1},
                "win_rate": {"$avg": {"$cond": ["$won", 1, 0]}}}},
    {"$sort": {"_id.run": 1, "_id.version": 1}},
]


def snapshot(st: Store) -> dict:
    ladder: dict = {}
    for r in st.battles.aggregate(LADDER_BY_FAMILY):
        a = ladder.setdefault(r["_id"]["agent"], {"games": 0, "wins": 0, "families": {}})
        a["games"] += r["games"]; a["wins"] += r["wins"]
        a["families"][r["_id"]["family"]] = {"games": r["games"], "wins": r["wins"]}
    runs = [{"run": r["_id"]["run"], "version": r["_id"]["version"], "battles": r["battles"],
             "win_rate": r["win_rate"]} for r in st.battles.aggregate(RUN_BY_VERSION)]
    disc = []
    for r in st.reflections.find({"result.kept": True}).sort([("run", 1), ("generation", 1)]):
        top = r["result"]["top"]
        c = next((c for c in r["candidates"] if c["id"] == top), None)
        if not c:
            continue
        rt = r["result"].get("retest") or {}
        disc.append({"run": r["run"], "generation": r["generation"], "version": top, "parent": r["parent"],
                     "change": c["change"], "examples": r["result"].get("examples") or {},
                     "first": {"best": r["result"].get("best_first"), "top": r["result"].get("top_first")},
                     "retest": rt, "n_losses": r["saw"].get("n_losses"), "n_battles": r["saw"].get("n_battles")})
    return {"at": time.time(), "ladder": ladder, "runs": runs, "atlas": st.stats(), "discoveries": disc,
            "pipelines": {"ladder_by_family": LADDER_BY_FAMILY, "run_by_version": RUN_BY_VERSION}}


def main():
    st = Store()
    while True:
        tmp = Path("stats.json.tmp")
        tmp.write_text(json.dumps(snapshot(st), default=str))
        tmp.replace("stats.json")
        time.sleep(60)


if __name__ == "__main__":
    main()
