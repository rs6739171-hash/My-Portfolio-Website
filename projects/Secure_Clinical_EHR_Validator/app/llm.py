from __future__ import annotations

import httpx

from .config import settings


SYSTEM_PROMPT = """You are a clinical record retrieval assistant for a synthetic portfolio demo.
Use only the supplied evidence. Never diagnose, prescribe, recommend medication changes, or infer facts not present in the evidence.
Answer the historical question concisely. Cite encounter IDs in square brackets, e.g. [E1001-2]. If evidence is insufficient, say so.
The context has already been redacted for external processing."""


async def generate_answer(question: str, evidence_text: str) -> str | None:
    if not settings.llm_enabled:
        return None
    url = settings.llm_api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nQuestion: {question}"},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"].strip()
