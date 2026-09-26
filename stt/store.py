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
INDEX = "lessons_vec"


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
        hits = list(self.lessons.aggregate([
            {"$vectorSearch": {"index": INDEX, "path": "embedding", "queryVector": embed([query])[0],
                               "numCandidates": 50, "limit": k, "filter": {"archived": False}}},
            {"$project": {"_id": 0, "text": 1, "from_version": 1, "wealth": 1,
                          "score": {"$meta": "vectorSearchScore"}}},
        ]))
        self.last_search = {"query": query[:300], "k": k, "hits": hits, "at": time.time()}
        return hits

    def stats(self) -> dict:
        return {"db": self.db.name, "index": INDEX, "index_status": self.index_status(),
                "index_def": self.index_def, "last_search": self.last_search,
                "counts": {c: self.db[c].count_documents({}) for c in
                           ("harness_versions", "battles", "reflections", "lessons")}}
