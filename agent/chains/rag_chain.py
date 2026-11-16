from core.exceptions import LLMError


class RAGChain:
    def __init__(self, llm_router=None):
        self.llm = llm_router

    async def run(self, query: str, memory_manager=None) -> str:
        context = ""
        if memory_manager:
            try:
                results = memory_manager.recall(query, limit=5)
                if results:
                    context = "\n".join(
                        r.get("content", r.get("data", str(r)))[:1000] for r in results
                    )
                    context = f"Relevant context:\n{context}\n\n"
            except Exception:
                pass

        prompt = (
            f"{context}Answer the following question based on the context above "
            f"and your knowledge. If the context is not relevant, use your own knowledge.\n\n"
            f"Question: {query}"
        )

        if not self.llm:
            return f"Based on available information:\n{context[:1000] if context else 'No context available.'}"

        try:
            return await self.llm.generate([{"role": "user", "content": prompt}])
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"RAG chain failed: {e}") from e
