"""Held-out check: play harness versions against an opponent the loop never trained against.

  python heldout.py maxpower 60 r1.v1 r1.v10
Results are saved to Atlas under run "heldout:<opponent>".
"""
import asyncio
import sys

from stt.env import load_env

load_env()
from stt.evaluate import evaluate  # noqa: E402
from stt.harness import v1  # noqa: E402
from stt.llm import LLM  # noqa: E402
from stt.store import Store  # noqa: E402
from stt.tools import load_tools  # noqa: E402


async def main(opponent: str, n: int, vids: list[str]):
    store, llm = Store(), LLM(concurrency=24)
    cfgs = []
    for vid in vids:
        cfg = store.versions.find_one({"_id": vid}) or (dict(v1(), _id=vid) if vid.endswith(".v1") else None)
        if not cfg:
            raise SystemExit(f"no version {vid}")
        cfgs.append(cfg)
    results = await asyncio.gather(*[evaluate(c, llm, n, opponent, tools=load_tools(c)) for c in cfgs])
    for c, (wr, docs, _) in zip(cfgs, results):
        store.save_battles(docs, f"heldout:{opponent}")
        print(f"{c['_id']} vs {opponent}: {sum(d['won'] for d in docs)}/{len(docs)} ({wr:.0%})", flush=True)


asyncio.run(main(sys.argv[1], int(sys.argv[2]), sys.argv[3:]))
