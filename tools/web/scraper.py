import requests
from bs4 import BeautifulSoup


class ScraperTool:
    def fetch(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [l for l in text.split("\n") if len(l.strip()) > 30]
            return "\n".join(lines[:100])
        except Exception as e:
            return f"Error fetching page: {e}"

    def extract_links(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if href.startswith("http"):
                    links.append({"url": href, "text": text})
            return links[:50]
        except Exception as e:
            return [{"error": str(e)}]
