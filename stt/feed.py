"""Live feed of every write to the database, via a MongoDB change stream.

  python -m stt.feed        (runs beside the loop; the lab reads feed.json)

Atlas pushes each insert/update as it happens; we keep the last 80 as one readable line each.
"""
import json
import os
import time
from pathlib import Path

from pymongo import MongoClient

from .env import load_env

load_env()


def summarize(coll: str, doc: dict) -> str:
    if coll == "battles":
        return f"{doc.get('version') or doc.get('agent')} {'won' if doc.get('won') else 'lost'} in {doc.get('turns')} turns" + (
            f" vs {doc['opponent']}" if doc.get("opponent") and doc["opponent"] != "heuristic" else "")
    if coll == "harness_versions":
        s = doc.get("score")
        return f"{doc.get('_id')} · {doc.get('status')}" + (f" · {round(s * 100)}%" if isinstance(s, (int, float)) else "")
    if coll == "reflections":
        res = doc.get("result") or {}
        return (f"{doc.get('run')} generation {doc.get('generation')}: {len(doc.get('candidates', []))} candidates"
                + (f" · {'KEPT ' + res['top'] if res.get('kept') else 'nothing kept'}" if res else " · testing"))
    if coll == "lessons":
        return f"\"{(doc.get('text') or '')[:100]}\""
    return ""


def main():
    db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "trainer")]
    out, events = Path("feed.json"), []
    out.write_text("[]")
    print(f"watching {db.name} for changes", flush=True)
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}]
    with db.watch(pipeline, full_document="updateLookup") as stream:
        for ev in stream:
            coll = ev["ns"]["coll"]
            events.append({"t": time.strftime("%H:%M:%S"), "op": ev["operationType"], "coll": coll,
                           "what": summarize(coll, ev.get("fullDocument") or {})})
            events = events[-80:]
            tmp = Path("feed.json.tmp")
            tmp.write_text(json.dumps(events))
            tmp.replace(out)


if __name__ == "__main__":
    main()
