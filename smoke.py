"""Milestone 1 check: v1 plays N Gen 1 OU battles against the local rule-based bot."""
import asyncio
import sys

from stt.env import load_env

load_env()
from stt.evaluate import evaluate  # noqa: E402
from stt.harness import v1  # noqa: E402
from stt.llm import LLM  # noqa: E402


async def main(n: int):
    llm = LLM()
    wr, docs, me = await evaluate(v1(), llm, n)
    turns = sum(len(d["log"]) for d in docs)
    print(f"v1: won {sum(d['won'] for d in docs)}/{len(docs)} ({wr:.0%}) | invalid {me.invalid}/{turns} | "
          f"{llm.avg_seconds:.2f}s per model call | errors {llm.errors} {llm.last_error}")
    t = docs[0]["log"][3] if docs and len(docs[0]["log"]) > 3 else None
    if t:
        print(f"example turn {t['turn']}: reason: {t['reason']} -> {t['action']}")


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 10))
