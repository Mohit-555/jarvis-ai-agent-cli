import json
import uuid
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions
from core.config import DB_DIR


class Memory:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(DB_DIR))
        self.embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="conversations",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, role, content, metadata=None):
        doc_id = str(uuid.uuid4())
        ts = datetime.now().isoformat()
        self.collection.add(
            documents=[content],
            metadatas=[{"role": role, "timestamp": ts, **(metadata or {})}],
            ids=[doc_id],
        )

    def search(self, query, n_results=5):
        results = self.collection.query(query_texts=[query], n_results=n_results)
        items = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                items.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        return items

    def recent(self, n=10):
        total = self.collection.count()
        if total == 0:
            return []
        offset = max(0, total - n)
        limit = min(n, total)
        all_items = self.collection.get(limit=limit, offset=offset)
        if not all_items["ids"]:
            return []
        items = []
        for i in range(len(all_items["ids"])):
            items.append({
                "content": all_items["documents"][i],
                "metadata": all_items["metadatas"][i] if all_items["metadatas"] else {},
            })
        items.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)
        return items

    def clear(self):
        self.client.delete_collection("conversations")
        self.collection = self.client.create_collection(
            name="conversations",
            embedding_function=self.embed_fn,
        )
