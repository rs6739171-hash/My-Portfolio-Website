import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

def tavily_search(query: str, max_results: int = 5) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured.")

    response = TavilyClient(api_key=api_key).search(
        query=query,
        max_results=max_results,
        search_depth="basic",
    )

    items = []
    for index, item in enumerate(response.get("results", []), 1):
        title = item.get("title") or "Result"
        url = item.get("url") or ""
        snippet = (item.get("content") or "").strip()
        if len(snippet) > 420:
            snippet = snippet[:420].rsplit(" ", 1)[0] + "..."
        items.append(f"{index}. **{title}**\n   {url}\n   {snippet}")

    return "\n\n".join(items) or "No hotel-search results were returned."
