import uuid
from datetime import datetime

try:
    import chromadb
    from chromadb.utils import embedding_functions
    _HAS_CHROMA = True
except ImportError:
    _HAS_CHROMA = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class _FallbackEmbedder:
    def __call__(self, texts):
        if _HAS_NUMPY:
            return np.random.rand(len(texts), 384).tolist()
        return [[0.0] * 384 for _ in texts]


class SemanticMemory:
    def __init__(self, collection_name: str = "semantic", persist_dir: str = None):
        self._collection_name = collection_name
        self._client = None
        self._collection = None
        self._local_store: dict[str, dict] = {}
        self._enabled = _HAS_CHROMA

        if _HAS_CHROMA:
            try:
                self._client = chromadb.PersistentClient(
                    path=persist_dir or "/tmp/jarvis_semantic"
                )
                self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
                self._collection = self._client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=self._embed_fn,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:
                self._enabled = False

    def add(self, text: str, metadata: dict = None):
        doc_id = str(uuid.uuid4())
        ts = datetime.now().isoformat()
        meta = {"timestamp": ts, **(metadata or {})}

        if self._enabled and self._collection:
            try:
                self._collection.add(
                    documents=[text],
                    metadatas=[meta],
                    ids=[doc_id],
                )
                return doc_id
            except Exception:
                pass

        self._local_store[doc_id] = {"text": text, "metadata": meta, "id": doc_id}
        return doc_id

    def search(self, query: str, k: int = 5) -> list[dict]:
        if self._enabled and self._collection:
            try:
                results = self._collection.query(
                    query_texts=[query], n_results=k
                )
                items = []
                if results["documents"] and results["documents"][0]:
                    for i in range(len(results["documents"][0])):
                        items.append({
                            "content": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "score": 1 - (results["distances"][0][i] if results["distances"] else 0),
                        })
                return items
            except Exception:
                pass

        query_lower = query.lower()
        scored = []
        for doc_id, entry in self._local_store.items():
            text = entry["text"].lower()
            score = sum(1 for word in query_lower.split() if word in text) / max(len(query.split()), 1)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"content": e["text"], "metadata": e["metadata"], "score": s}
            for s, e in scored[:k]
        ]

    def delete(self, ids: list[str]):
        if self._enabled and self._collection:
            try:
                self._collection.delete(ids=ids)
            except Exception:
                pass
        for doc_id in ids:
            self._local_store.pop(doc_id, None)

    def clear(self):
        if self._enabled and self._client:
            try:
                self._client.delete_collection(self._collection_name)
                self._collection = self._client.create_collection(
                    name=self._collection_name,
                    embedding_function=self._embed_fn,
                )
            except Exception:
                pass
        self._local_store.clear()
