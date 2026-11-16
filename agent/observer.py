from dataclasses import dataclass, field
from typing import Any, Optional

from agent.actor import ToolResult


@dataclass
class Observation:
    success: bool
    summary: str
    extracted_info: dict = field(default_factory=dict)
    goal_satisfied: bool = False
    raw_result: Any = None


class Observer:
    def __init__(self, llm_router=None):
        self.llm = llm_router

    def observe(self, result: ToolResult, goal: str) -> Observation:
        if not result.success:
            return Observation(
                success=False,
                summary=f"Tool {result.tool_name} failed: {result.error}",
                goal_satisfied=False,
                raw_result=result,
            )
        summary = result.data[:200] if result.data else "Completed"
        goal_satisfied = self._check_goal_satisfied(summary, goal)
        return Observation(
            success=True,
            summary=summary,
            goal_satisfied=goal_satisfied,
            extracted_info={"data": result.data, "tool": result.tool_name},
            raw_result=result,
        )

    def _check_goal_satisfied(self, result_summary: str, goal: str) -> bool:
        if not goal:
            return True
        goal_lower = goal.lower()
        result_lower = result_summary.lower()
        goal_words = set(goal_lower.split())
        result_words = set(result_lower.split())
        overlap = goal_words & result_words
        return len(overlap) >= max(2, len(goal_words) // 3)

    async def analyze_result(self, result: ToolResult, goal: str) -> Observation:
        if not self.llm:
            return self.observe(result, goal)
        prompt = (
            f"Goal: {goal}\n"
            f"Tool result (success={result.success}): {result.data}\n\n"
            "Evaluate carefully:\n"
            "1. If the goal asks to 'write an essay' or 'write about' a topic, check that the content is actually a substantive essay — not the user's question repeated back or a placeholder.\n"
            "2. If a specific directory was requested (e.g., 'Downloads', 'desktop'), check the path matches.\n"
            "3. If the content looks like an instruction rather than actual written content, the goal is NOT satisfied.\n"
            "Was the goal actually satisfied? Reply with YES or NO, then brief explanation."
        )
        try:
            resp = await self.llm.generate([
                {"role": "system", "content": "You are a quality assurance checker. Your job is to verify if a task was actually completed correctly."},
                {"role": "user", "content": prompt},
            ])
            satisfied = resp.strip().upper().startswith("YES")
            return Observation(
                success=result.success,
                summary=resp[:300],
                goal_satisfied=satisfied,
                extracted_info={"data": result.data, "tool": result.tool_name, "analysis": resp},
                raw_result=result,
            )
        except Exception:
            return self.observe(result, goal)
