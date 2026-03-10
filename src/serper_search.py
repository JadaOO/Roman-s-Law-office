import requests
from config import SERPER_API_KEY


def search_az_family_law(query):
    url = "https://google.serper.dev/search"

    payload = {
        "q": f"site:azleg.gov ars 25 {query}"
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    results = response.json()

    links = []
    for r in results.get("organic", []):
        links.append(r["link"])

    return links[:3]
