from tools.web.search import WebSearchTool
from tools.web.scraper import ScraperTool


class WebTool:
    def search(self, query, num_results=5):
        return WebSearchTool().search(query, num_results)

    def fetch_page(self, url):
        return ScraperTool().fetch(url)
