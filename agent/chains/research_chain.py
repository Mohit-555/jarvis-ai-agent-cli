from core.exceptions import LLMError


class ResearchChain:
    def __init__(self, llm_router=None, web_search_fn=None):
        self.llm = llm_router
        self.search = web_search_fn

    async def research(self, topic: str, depth: int = 2) -> str:
        if not self.search:
            if self.llm:
                return await self.llm.generate([
                    {"role": "user", "content": f"Provide a comprehensive summary of: {topic}"}
                ])
            return f"No search capability available for researching: {topic}"

        all_findings = []
        queries = self._generate_queries(topic, depth)

        for i, query in enumerate(queries):
            try:
                results = self.search(query)
                if isinstance(results, list):
                    snippets = [r.get("snippet", r.get("content", str(r)))[:500] for r in results[:3]]
                    all_findings.extend(snippets)
                elif isinstance(results, str):
                    all_findings.append(results[:1000])
            except Exception:
                pass

        if not all_findings:
            return f"No research results found for: {topic}"

        combined = "\n".join(f"- {f}" for f in all_findings[:15])

        if not self.llm:
            return f"Research findings on '{topic}':\n{combined}"

        synthesis_prompt = (
            f"Synthesize the following research findings on '{topic}' into a coherent summary:\n\n"
            f"{combined}\n\nProvide key insights, main points, and a conclusion."
        )
        try:
            synthesis = await self.llm.generate([{"role": "user", "content": synthesis_prompt}])
            return synthesis
        except LLMError:
            raise
        except Exception as e:
            return f"Research findings on '{topic}':\n{combined}\n\n(Synthesis failed: {e})"

    def _generate_queries(self, topic: str, depth: int) -> list[str]:
        queries = [topic]
        if depth > 1:
            queries.append(f"{topic} overview 2026")
        if depth > 2:
            queries.append(f"{topic} latest developments")
            queries.append(f"{topic} tutorial guide")
        return queries
