import requests
from bs4 import BeautifulSoup


def scrape_statute(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    text = soup.get_text(separator="\n")
    return text[:8000]


def fetch_law_context(urls):
    context = ""
    for url in urls:
        try:
            text = scrape_statute(url)
            context += text + "\n\n"
        except Exception:
            pass
    return context
