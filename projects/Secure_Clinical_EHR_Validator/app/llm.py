from __future__ import annotations

import time
from collections import deque

import httpx

from .config import settings


SYSTEM_PROMPT = """You are a clinical record retrieval assistant for a synthetic portfolio demo.
Use only the supplied evidence. Never diagnose, prescribe, recommend medication changes, or infer facts not present in the evidence.
Answer the historical question concisely. Cite encounter IDs in square brackets, e.g. [E1001-2]. If evidence is insufficient, say so.
The context has already been redacted for external processing."""

_LLM_CALL_TIMES: deque[float] = deque()


def _within_usage_budget() -> bool:
    now = time.monotonic()
    cutoff = now - 3600
    while _LLM_CALL_TIMES and _LLM_CALL_TIMES[0] < cutoff:
        _LLM_CALL_TIMES.popleft()
    if len(_LLM_CALL_TIMES) >= settings.max_llm_calls_per_hour:
        return False
    _LLM_CALL_TIMES.append(now)
    return True


def _message_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip()
    return str(content).strip()


async def generate_answer(question: str, evidence_text: str) -> str | None:
    if not settings.llm_enabled or not _within_usage_budget():
        return None

    url = settings.llm_api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.1,
        "max_tokens": settings.llm_max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nQuestion: {question}"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return _message_text(data["choices"][0]["message"]["content"])


async def verify_provider_access() -> tuple[bool, str]:
    if not settings.llm_enabled:
        return False, "LLM environment variables are not fully configured."
    url = settings.llm_api_base.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        model_ids = {
            item.get("id")
            for item in payload.get("data", [])
            if isinstance(item, dict) and item.get("id")
        }
        if settings.llm_model in model_ids:
            return True, f"Provider authenticated; {settings.llm_model} is available."
        return True, f"Provider authenticated; model listing returned successfully."
    except Exception as exc:
        return False, f"Provider validation failed: {type(exc).__name__}"
