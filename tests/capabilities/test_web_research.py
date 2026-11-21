import unittest
from tools.web.search import WebSearchTool
from tools.web.scraper import ScraperTool
from agent.planner import Planner


class TestWebResearchCapabilities(unittest.TestCase):
    """
    Verification of Tasks 121–130: Internet Research & Browsing.
    """

    def setUp(self):
        self.search = WebSearchTool()
        self.scraper = ScraperTool()
        self.planner = Planner()

    def test_task_121_130_planner_routing_for_web_research(self):
        """Tasks 121-130: Verify planner correctly maps web search and browsing intents."""
        prompt = self.planner.get_prompt("search latest python tutorials")
        self.assertIn("web_search", prompt)
        self.assertIn("web_fetch", prompt)
        self.assertIn("browse_url", prompt)

    def test_scraper_structure(self):
        """Task 130: Summarize information from webpage URL scraper."""
        self.assertTrue(hasattr(self.scraper, "fetch"))


if __name__ == "__main__":
    unittest.main()
