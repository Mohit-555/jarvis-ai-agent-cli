import requests
from bs4 import BeautifulSoup
import urllib.parse


class WebSearchTool:
    """
    Search using DuckDuckGo Instant Answer API (primary) with HTML scrape fallback.
    No API key required.
    """

    DDG_API = "https://api.duckduckgo.com/"
    DDG_HTML = "https://html.duckduckgo.com/html/"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    def search(self, query: str, num_results: int = 5) -> list[dict]:
        """Return up to `num_results` search results for `query`."""
        results = self._ddg_api(query, num_results)
        if not results:
            results = self._ddg_html(query, num_results)
        if not results:
            return [{"title": "No results", "snippet": f"Could not fetch results for: {query}", "link": ""}]
        return results

    # ── Primary: DDG Instant Answer API ─────────────────────────────────────
    def _ddg_api(self, query: str, limit: int) -> list[dict]:
        try:
            resp = requests.get(
                self.DDG_API,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers=self.HEADERS,
                timeout=10,
            )
            data = resp.json()
            results = []

            # Instant abstract (e.g. Wikipedia summary)
            abstract = data.get("Abstract", "").strip()
            abstract_url = data.get("AbstractURL", "").strip()
            abstract_source = data.get("AbstractSource", "")
            if abstract:
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": abstract,
                    "link": abstract_url,
                    "source": abstract_source,
                })

            # Direct answer (e.g. "The capital of France is Paris")
            answer = data.get("Answer", "").strip()
            if answer and answer not in [r.get("snippet") for r in results]:
                results.append({
                    "title": "Direct Answer",
                    "snippet": answer,
                    "link": "",
                    "source": "DuckDuckGo",
                })

            # Related topics
            for topic in data.get("RelatedTopics", [])[:limit]:
                if isinstance(topic, dict) and topic.get("Text"):
                    text = topic["Text"].strip()
                    if text and text not in [r.get("snippet") for r in results]:
                        results.append({
                            "title": text[:80],
                            "snippet": text,
                            "link": topic.get("FirstURL", ""),
                            "source": "DuckDuckGo",
                        })

            return results[:limit]
        except Exception:
            return []

    # ── Fallback: HTML scraping ──────────────────────────────────────────────
    def _ddg_html(self, query: str, limit: int) -> list[dict]:
        try:
            resp = requests.get(
                self.DDG_HTML,
                params={"q": query},
                headers=self.HEADERS,
                timeout=10,
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            for item in soup.select(".web-result, .result")[:limit]:
                title_el = item.select_one(".result__title, .result__a")
                snippet_el = item.select_one(".result__snippet, .result__extras__url")
                link_el = item.select_one("a.result__a, a")

                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                link = link_el.get("href", "") if link_el else ""

                if title or snippet:
                    results.append({"title": title, "snippet": snippet, "link": link})

            return results[:limit]
        except Exception:
            return []
