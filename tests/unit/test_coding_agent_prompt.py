import unittest
from agent.executor import AgentExecutor


class TestCodingAgentPrompt(unittest.TestCase):
    def test_coding_agent_prompt_guidelines(self):
        executor = AgentExecutor()
        prompt = executor._get_system_prompt()

        # Check workspace separation
        self.assertIn("NEVER treat this directory or Jarvis agent source files as the user's application project", prompt)
        self.assertIn("AI Coding Agent Behavior & Protocol", prompt)

        # Check purpose explanation requirement
        self.assertIn("Purpose Explanation", prompt)
        self.assertIn("ALWAYS explain the exact purpose before taking action", prompt)

        # Check response requirement when in Jarvis directory
        self.assertIn("I've located your Jarvis directory. However, I haven't identified your actual application source code yet", prompt)
        self.assertIn("I'll inspect its Python files, understand the existing architecture", prompt)
        self.assertIn("I won't modify any files without your confirmation", prompt)

        # Check sensitive file avoidance
        self.assertIn("Strictly avoid mentioning or scanning .bashrc, shell configs, browser profiles, API keys, session data, or credentials", prompt)

        # Check scan_project in tools
        self.assertIn("scan_project", prompt)


if __name__ == "__main__":
    unittest.main()
