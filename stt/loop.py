"""The self-improvement loop.

  python -m stt.loop --run r1 --generations 4 --battles 60

Each generation:
  1. the current best version plays fresh battles (its score is always recent)
  2. the coach studies its losses and proposes 3-4 different changes
  3. every candidate plays the same number of battles, at the same time as the best
  4. the top candidate gets a head-to-head re-test against the best (the best of 4 is usually a bit lucky)
  5. it is kept only if its combined score beats the best by the margin; otherwise it goes on the "tried" list
Everything is saved to Atlas, and live.json feeds the lab page.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

from .env import load_env

load_env()
from . import coach  # noqa: E402
from .evaluate import evaluate  # noqa: E402
from .harness import EDITABLE, v1  # noqa: E402
from .llm import LLM  # noqa: E402
from .store import Store  # noqa: E402
from .tools import load_tools  # noqa: E402

LIVE: dict = {"phase": "starting", "progress": {}, "versions": [], "reflections": [], "last_battle": None}


def write_live(**kw):
    LIVE.update(kw)
    ladders = {}
    for f in Path(".").glob("ladder-*.json"):
        try:
            ladders[f.stem.replace("ladder-", "")] = json.loads(f.read_text())
        except ValueError:
            pass
    LIVE["ladders"] = ladders
    tmp = Path("live.json.tmp")
    tmp.write_text(json.dumps(LIVE, default=str))
    tmp.replace("live.json")


def on_finish(player, battle):
    vid = player.cfg["_id"]
    p = LIVE["progress"].setdefault(vid, {"done": 0, "won": 0})
    p["done"] += 1
    p["won"] += int(bool(battle.won))
    LIVE["last_battle"] = {"version": vid, "tag": battle.battle_tag, "won": bool(battle.won),
                           "replay": f"replays/{player.username} - {battle.battle_tag}.html",
                           "turns": player.turn_log.get(battle.battle_tag, [])}
    write_live()


def evidence_for(docs: list[dict]) -> str:
    """Hook for the partner's evidence module (stt/evidence.py with build(docs) -> str). Empty if absent."""
    try:
        from . import evidence
        return evidence.build(docs) or ""
    except ImportError:
        return ""
    except Exception as e:  # never let evidence code crash the loop
        print(f"  evidence module error: {type(e).__name__}: {e}", flush=True)
        return ""


async def play(cfg, llm, n, opponent):
    """opponent can be one bot, or several joined with '+': battles are split evenly and the
    score is the overall win rate, so a change must help against all of them to be kept."""
    opps = opponent.split("+")
    per = max(1, n // len(opps))
    parts = await asyncio.gather(*[evaluate(cfg, llm, per, o, tools=load_tools(cfg), on_finish=on_finish) for o in opps])
    docs = [d for _, ds, _ in parts for d in ds]
    return sum(d["won"] for d in docs) / max(1, len(docs)), docs, parts[0][2]


async def main(a):
    store, llm = Store(), LLM(concurrency=a.concurrency)
    run = a.run
    print(f"run {run} | player {llm.play_model} | coach {llm.coach_model} | Atlas db {store.db.name}", flush=True)

    def versions():
        return [v for v in store.all_versions() if v.get("run") == run]

    best = v1()
    best.update({"_id": f"{run}.v1", "run": run})
    counter = 1
    tried: list[dict] = []
    reflections: list[dict] = []
    write_live(run=run, phase="play", generation=0, battles=a.battles, progress={}, reflections=[],
               models={"play": llm.play_model, "coach": llm.coach_model})

    wr, docs, _ = await play(best, llm, a.battles, a.opponent)
    best["score"] = wr
    store.save_version(best)
    store.save_battles(docs, run)
    print(f"{best['_id']}: {wr:.0%} (baseline)", flush=True)
    write_live(versions=versions())

    for g in range(1, a.generations + 1):
        # 1-2. the coach studies the best version's losses
        write_live(phase="coach", generation=g, progress={})
        loss_text = " ".join(coach.game_summary(d, 6) for d in docs if not d["won"])[:3000]
        lessons = store.search_lessons(loss_text, k=3) if store.lessons.count_documents({"archived": False}) else []
        write_live(last_search=store.last_search)
        cands, prompt, raw = await coach.propose(llm, best, docs, tried, lessons, evidence=evidence_for(docs))
        ref = {"run": run, "generation": g, "parent": best["_id"], "at": time.time(),
               "saw": {"harness": {k: best[k] for k in EDITABLE}, "n_battles": len(docs),
                       "n_losses": sum(not d["won"] for d in docs), "tried": list(tried),
                       "lessons": [{"text": h["text"], "score": h.get("score")} for h in lessons],
                       "prompt": prompt},
               "raw_reply": raw[-4000:] if not cands else None,
               "candidates": [], "result": None}
        versions_to_test = []
        for c in cands:
            counter += 1
            cand, err = coach.apply_change(best, c, f"{run}.v{counter}")
            entry = {"id": f"{run}.v{counter}", "change": c, "error": err}
            ref["candidates"].append(entry)
            if cand:
                cand["run"] = run
                versions_to_test.append(cand)
            else:
                tried.append(c)
        reflections.append(ref)
        store.save_reflection(ref)
        print(f"gen {g}: coach proposed {len(cands)}, {len(versions_to_test)} valid", flush=True)
        if not versions_to_test:
            write_live(reflections=reflections)
            continue

        # 3. candidates and the best play at the same time
        write_live(phase="test", reflections=reflections, testing=[v["_id"] for v in versions_to_test])
        results = await asyncio.gather(play(best, llm, a.battles, a.opponent),
                                       *[play(v, llm, a.battles, a.opponent) for v in versions_to_test])
        best_wr, best_docs, _ = results[0]
        for v, (w, d, _) in zip(versions_to_test, results[1:]):
            v["score"] = w
            store.save_battles(d, run)
            for e in ref["candidates"]:
                if e["id"] == v["_id"]:
                    e["score"] = w
        store.save_battles(best_docs, run)
        top_i = max(range(len(versions_to_test)), key=lambda i: versions_to_test[i]["score"])
        top, (top_wr, top_docs, _) = versions_to_test[top_i], results[1 + top_i]
        print(f"  best {best['_id']} {best_wr:.0%} | " + " | ".join(
            f"{v['_id']} {v['score']:.0%} ({v['change']['kind']})" for v in versions_to_test), flush=True)

        # 4. head-to-head re-test of the top candidate
        keep = False
        retest = None
        if top_wr > best_wr:
            write_live(phase="retest", testing=[top["_id"]], progress={})
            (b2, bd2, _), (t2, td2, _) = await asyncio.gather(play(best, llm, a.battles, a.opponent),
                                                              play(top, llm, a.battles, a.opponent))
            store.save_battles(bd2 + td2, run)
            best_avg, top_avg = (best_wr + b2) / 2, (top_wr + t2) / 2
            retest = {"best": b2, "top": t2, "best_avg": best_avg, "top_avg": top_avg}
            keep = top_avg >= best_avg + a.margin
            print(f"  re-test: best {b2:.0%} vs {top['_id']} {t2:.0%} | averages {best_avg:.0%} vs {top_avg:.0%} "
                  f"-> {'KEPT' if keep else 'rejected'}", flush=True)
            top_docs = top_docs + td2
            best_docs = best_docs + bd2
            top["score"] = top_avg
            best_wr = best_avg

        # 5. keep or roll back, and remember what didn't work
        for v in versions_to_test:
            v["status"] = "promoted" if (keep and v is top) else "rolled_back"
            store.save_version(v)
            if not (keep and v is top):
                tried.append(v["change"])
        best["score"] = best_wr
        store.save_version(best)
        ref["result"] = {"top": top["_id"], "top_first": top_wr, "best_first": results[0][0],
                         "retest": retest, "kept": keep}
        store.save_reflection(ref)
        if keep:
            ref["result"]["examples"] = await coach.explain_keep(llm, prompt, top["change"])
            store.save_reflection(ref)
            if top["change"].get("lesson"):
                store.add_lesson(top["change"]["lesson"], top["_id"], run)
            best, docs = top, top_docs
        else:
            docs = best_docs
        write_live(phase="decide", versions=versions(), reflections=reflections, best=best["_id"])

    write_live(phase="finished", versions=versions(), reflections=reflections, best=best["_id"])
    print(f"done. best {best['_id']} at {best['score']:.0%} | rules {best['rules']} | "
          f"tools {[t['name'] for t in best.get('custom_tools', [])]} | "
          f"{llm.calls} model calls, {llm.errors} errors", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="r1")
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--battles", type=int, default=60)
    ap.add_argument("--opponent", default="heuristic")
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--concurrency", type=int, default=24)
    asyncio.run(main(ap.parse_args()))
