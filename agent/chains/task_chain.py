from core.event_bus import event_bus, EVENTS
from core.exceptions import AgentError

from agent.planner import Planner
from agent.actor import Actor
from agent.observer import Observer
from agent.reflector import Reflector


class TaskChain:
    def __init__(self, llm_router=None, tool_registry=None):
        self.llm = llm_router
        self.tools = tool_registry or {}
        self.planner = Planner(llm_router)
        self.actor = Actor(tool_registry)
        self.observer = Observer(llm_router)
        self.reflector = Reflector()
        self.max_iterations = 10

    async def execute(self, goal: str) -> str:
        event_bus.emit(EVENTS["AGENT_START"], task=goal)

        try:
            steps = await self.planner.plan(goal)
            if not steps:
                return await self._fallback_llm(goal)
        except Exception as e:
            event_bus.emit(EVENTS["AGENT_ERROR"], error=str(e))
            return f"Planning failed: {e}"

        completed = []

        for iteration in range(self.max_iterations):
            pending = [s for s in steps if s.status == "pending"]
            if not pending:
                break

            step = pending[0]
            step.status = "in_progress"
            event_bus.emit(EVENTS["AGENT_STEP"], step=step.id, description=step.description)

            try:
                result = self.actor.execute_step(step, self.tools)
            except Exception as e:
                step.status = "failed"
                event_bus.emit(EVENTS["AGENT_ERROR"], error=str(e))
                diagnosis = self.reflector.reflect(str(e))
                fix = self.reflector.suggest_fix(str(e))
                new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                if new_steps:
                    steps.extend(new_steps)
                continue

            observation = await self.observer.analyze_result(result, goal)
            step.status = "success" if observation.success else "failed"
            completed.append(result)

            if observation.goal_satisfied:
                event_bus.emit(EVENTS["AGENT_COMPLETE"], task=goal)
                return self._summarize(completed)

            if not observation.success:
                diagnosis = self.reflector.reflect(result.error or "")
                fix = self.reflector.suggest_fix(result.error or "")
                new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                if new_steps:
                    steps.extend(new_steps)

        event_bus.emit(EVENTS["AGENT_COMPLETE"], task=goal)
        return self._summarize(completed)

    async def _fallback_llm(self, goal: str) -> str:
        if self.llm:
            try:
                return await self.llm.generate([{"role": "user", "content": goal}])
            except Exception:
                pass
        return f"Unable to process: {goal}"

    def _summarize(self, results) -> str:
        parts = []
        for i, r in enumerate(results):
            icon = "✓" if r.success else "✗"
            parts.append(f"{icon} Step {i+1}: {str(r.data or r.error)[:200]}")
        return "\n".join(parts)
