import os, json, httpx

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY")
INDEX = os.getenv("AZURE_SEARCH_INDEX")

async def search_docs(query: str, top: int = 5):
    if not (SEARCH_ENDPOINT and SEARCH_KEY and INDEX):
        return [{"id": "env-missing", "content": "환경변수 설정을 확인하세요.", "source": ""}]
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX}/docs/search?api-version=2024-12-01-preview"
    headers = {"Content-Type": "application/json", "api-key": SEARCH_KEY}
    body = {"search": query, "queryType": "semantic", "top": top}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        hits = []
        for item in data.get("value", []):
            hits.append({
                "id": item.get("@search.documentId") or item.get("id", ""),
                "content": item.get("content") or item.get("text") or "",
                "source": item.get("source") or item.get("url") or "",
            })
        return hits
