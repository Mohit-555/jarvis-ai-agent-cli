from core.config import CONFIG_DIR

from memory.working_memory import WorkingMemory
from memory.semantic_memory import SemanticMemory
from memory.episodic_memory import EpisodicMemory
from memory.user_profile import UserProfile


class MemoryManager:
    def __init__(self, config: dict = None):
        self.config = config or {}
        mem_dir = str(CONFIG_DIR / "memory")

        self.working = WorkingMemory(
            redis_url=self.config.get("redis_url"),
            default_ttl=self.config.get("working_ttl", 3600),
        )
        self.semantic = SemanticMemory(
            collection_name="jarvis_semantic",
            persist_dir=self.config.get("semantic_dir", mem_dir),
        )
        self.episodic = EpisodicMemory(
            db_path=self.config.get("episodic_db", str(CONFIG_DIR / "episodic.db")),
        )
        self.profile = UserProfile(
            profile_path=self.config.get("profile_path", str(CONFIG_DIR / "profile.json")),
        )

    async def remember(self, context: str, session_id: str = None):
        self.working.set(f"ctx:{session_id or 'default'}", context, ttl=3600)

        if session_id:
            self.episodic.store_episode(
                session_id=session_id,
                role="system",
                content=context[:2000],
            )

        if len(context) > 100:
            try:
                self.semantic.add(context, {"session_id": session_id or "default", "type": "context"})
            except Exception:
                pass

    async def recall(self, query: str, limit: int = 5) -> list[dict]:
        results = []
        seen = set()

        semantic_results = self.semantic.search(query, k=limit)
        for r in semantic_results:
            key = r.get("content", "")[:200]
            if key not in seen:
                seen.add(key)
                results.append(r)

        episodic_results = self.episodic.search_facts(query)
        for r in episodic_results:
            key = r.get("value", "")[:200]
            if key not in seen:
                seen.add(key)
                results.append({
                    "content": r.get("value", ""),
                    "metadata": {"category": r.get("category"), "key": r.get("key")},
                    "source": "episodic",
                })

        working_val = self.working.get(f"ctx:{query}")
        if working_val:
            results.append({
                "content": working_val,
                "metadata": {"source": "working"},
            })

        return results[:limit]

    def store_fact(self, key: str, value: str, category: str = "general"):
        self.episodic.store_fact(key, value, category)
        self.working.set(f"fact:{key}", value, ttl=86400)

    def get_fact(self, key: str) -> str:
        return self.episodic.get_fact(key)

    def search_facts(self, query: str) -> list[dict]:
        return self.episodic.search_facts(query)

    def get_working(self, key: str) -> str:
        return self.working.get(key)

    def set_working(self, key: str, value: str, ttl: int = None):
        self.working.set(key, value, ttl)

    async def on_session_end(self, session_id: str):
        episodes = self.episodic.get_session_episodes(session_id)
        combined = "\n".join(f"{e['role']}: {e['content'][:500]}" for e in episodes[-20:])
        if combined:
            try:
                self.semantic.add(
                    combined,
                    {"session_id": session_id, "type": "session_summary"},
                )
            except Exception:
                pass
        self.working.delete(f"ctx:{session_id}")

    def get_user_preference(self, key: str, default=None):
        return self.profile.get(key, default)

    def set_user_preference(self, key: str, value):
        self.profile.set(key, value)

    def get_all_preferences(self) -> dict:
        return self.profile.get_all()
