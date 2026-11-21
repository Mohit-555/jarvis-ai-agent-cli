import unittest
import asyncio
from unittest.mock import MagicMock

from core.event_bus import event_bus, EVENTS
from agent.planner import Step
from agent.actor import Actor
from agent.executor import AgentExecutor

class TestInteractiveAsk(unittest.TestCase):
    def test_ask_user_emits_event_and_token(self):
        async def _run():
            executor = AgentExecutor()
            asked_events = []

            def on_ask(**kwargs):
                asked_events.append(kwargs)

            event_bus.on(EVENTS["AGENT_ASK"], on_ask)
            try:
                # Prepare a step with ask_user
                step = Step(id="1", description="Ask user what type of website", tool="ask_user", args={"question": "What website?"})
                
                # Mock planner to return this step
                executor.planner.plan = MagicMock(return_value=asyncio.Future())
                executor.planner.plan.return_value.set_result([step])

                gen = executor.execute_stream("create website")
                
                # First chunk should be the [ASK:...] signal
                chunk = await gen.__anext__()
                self.assertIn("[ASK:What website?]", chunk)
                self.assertEqual(len(asked_events), 1)
                self.assertEqual(asked_events[0]["question"], "What website?")

                # Submit answer to unblock
                executor.submit_answer("portfolio website")

                # Consume remaining
                remaining = []
                async for c in gen:
                    remaining.append(c)
                
            finally:
                event_bus.off(EVENTS["AGENT_ASK"], on_ask)

        asyncio.run(_run())

if __name__ == "__main__":
    unittest.main()
