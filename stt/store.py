"""MongoDB Atlas: everything the system knows lives here.

Collections (database set by MONGODB_DB, "trainer" today):
  harness_versions  one document per harness version: the settings, its score, and its parent
  battles           one document per battle: won/lost, every turn with the player's reason
  reflections       one document per coach decision: what it saw, what it changed, what happened
  lessons           one sentence the coach learned + an embedding for vector search (+ ledger fields)
"""
import os
import time

from openai import OpenAI
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

EMBED_MODEL, EMBED_DIM = "text-embedding-3-small", 1536
INDEX = "lessons_vec"          # fallback: embeddings we compute ourselves
AUTO_INDEX = "lessons_auto"    # Atlas Automated Embeddings: Atlas embeds `text` itself with Voyage
VOYAGE_MODEL, RERANK_MODEL = "voyage-4", "rerank-2.5"


def rerank(query: str, docs: list[str], k: int) -> list[tuple[int, float]]:
    """Voyage reranker through MongoDB's model endpoint: (index into docs, relevance), best first."""
    import json
    import urllib.request
    req = urllib.request.Request(
        "https://ai.mongodb.com/v1/rerank", method="POST",
        headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}", "Content-Type": "application/json"},
        data=json.dumps({"query": query, "documents": docs, "model": RERANK_MODEL, "top_k": k}).encode())
    data = json.load(urllib.request.urlopen(req, timeout=20))["data"]
    return [(d["index"], d["relevance_score"]) for d in data]


def embed(texts: list[str]) -> list[list[float]]:
    r = OpenAI().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in r.data]


class Store:
    def __init__(self):
        self.client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=15000)
        self.db = self.client[os.environ.get("MONGODB_DB", "trainer")]
        self.versions = self.db["harness_versions"]
        self.battles = self.db["battles"]
        self.reflections = self.db["reflections"]
        self.lessons = self.db["lessons"]
        self.last_search = None
        self.index_def = {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": EMBED_DIM, "similarity": "cosine"},
            {"type": "filter", "path": "archived"},
        ]}
        self._ensure_index()

    def _ensure_index(self):
        """Create the vector index from code if it's missing. Atlas builds it in the background (~1 min)."""
        if "lessons" not in self.db.list_collection_names():
            self.db.create_collection("lessons")
        if INDEX not in [i["name"] for i in self.lessons.list_search_indexes()]:
            self.lessons.create_search_index(
                SearchIndexModel(definition=self.index_def, name=INDEX, type="vectorSearch"))

    def index_status(self) -> str:
        for i in self.lessons.list_search_indexes():
            if i["name"] == INDEX:
                return i.get("status", "unknown")
        return "missing"

    # --- versions ----------------------------------------------------------
    def save_version(self, cfg: dict) -> None:
        self.versions.replace_one({"_id": cfg["_id"]}, cfg, upsert=True)

    def all_versions(self) -> list[dict]:
        return list(self.versions.find({}, {"guardrails": 0}).sort("created", 1))

    # --- battles -----------------------------------------------------------
    def save_battles(self, docs: list[dict], run: str) -> None:
        if docs:
            self.battles.insert_many([{**d, "run": run} for d in docs])

    # --- reflections -------------------------------------------------------
    def save_reflection(self, ref: dict) -> None:
        self.reflections.replace_one({"run": ref["run"], "generation": ref["generation"]}, ref, upsert=True)

    # --- lessons (vector memory) ---------------------------------------------
    def add_lesson(self, text: str, version: str, run: str) -> None:
        self.lessons.insert_one({"text": text, "embedding": embed([text])[0], "from_version": version,
                                 "run": run, "archived": False, "wealth": 0.0, "created": time.time()})

    def search_lessons(self, query: str, k: int = 3) -> list[dict]:
        """Atlas auto-embedded vector search (Voyage) for 8 candidates, then the Voyage reranker picks k.
        Falls back to our own embeddings if the automated path isn't available."""
        if os.environ.get("VOYAGE_API_KEY"):
            try:
                cands = list(self.lessons.aggregate([
                    {"$vectorSearch": {"index": AUTO_INDEX, "path": "text", "query": query[:4000], "model": VOYAGE_MODEL,
                                       "numCandidates": 50, "limit": 8, "filter": {"archived": False}}},
                    {"$project": {"_id": 0, "text": 1, "from_version": 1, "wealth": 1,
                                  "score": {"$meta": "vectorSearchScore"}}}]))
                if cands:
                    order = rerank(query[:4000], [c["text"] for c in cands], min(k, len(cands)))
                    hits = [{**cands[i], "rerank": round(r, 3)} for i, r in order]
                else:
                    hits = []
                self.last_search = {"query": query[:300], "k": k, "hits": hits, "at": time.time(),
                                    "how": f"Atlas autoEmbed ({VOYAGE_MODEL}) + Voyage {RERANK_MODEL}"}
                return hits
            except Exception as e:  # never let memory break the loop
                print(f"  automated-embedding search failed, using fallback: {type(e).__name__}", flush=True)
        hits = list(self.lessons.aggregate([
            {"$vectorSearch": {"index": INDEX, "path": "embedding", "queryVector": embed([query])[0],
                               "numCandidates": 50, "limit": k, "filter": {"archived": False}}},
            {"$project": {"_id": 0, "text": 1, "from_version": 1, "wealth": 1,
                          "score": {"$meta": "vectorSearchScore"}}},
        ]))
        self.last_search = {"query": query[:300], "k": k, "hits": hits, "at": time.time(), "how": "own embeddings"}
        return hits

    def stats(self) -> dict:
        auto = next((i.get("status") for i in self.lessons.list_search_indexes() if i["name"] == AUTO_INDEX), "missing")
        return {"db": self.db.name, "index": f"{AUTO_INDEX} (autoEmbed {VOYAGE_MODEL})", "index_status": auto,
                "index_def": {"fields": [{"type": "autoEmbed", "modality": "text", "path": "text", "model": VOYAGE_MODEL},
                                         {"type": "filter", "path": "archived"}]},
                "last_search": self.last_search,
                "counts": {c: self.db[c].count_documents({}) for c in
                           ("harness_versions", "battles", "reflections", "lessons")}}
