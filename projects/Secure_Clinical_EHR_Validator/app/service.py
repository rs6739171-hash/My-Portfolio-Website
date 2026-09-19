from __future__ import annotations

import re

from .llm import generate_answer
from .models import Evidence, QueryResponse
from .retrieval import retrieve
from .security import classify_request, redact_external_context

DISCLAIMER = "Synthetic educational demo only. Not a medical device and not for diagnosis, treatment, or real patient care."
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[A-Za-z0-9.]+")


def _extractive_answer(rows: list[dict]) -> str:
    if not rows:
        return "I could not find relevant historical evidence for that question."
    parts = []
    for row in rows[:2]:
        e = row["encounter"]
        facts = []
        if e.get("summary"):
            facts.append(e["summary"])
        if e.get("medications"):
            facts.append("Medications recorded: " + ", ".join(e["medications"]) + ".")
        if e.get("labs"):
            facts.append("Labs recorded: " + ", ".join(e["labs"]) + ".")
        if e.get("diagnoses"):
            facts.append("Diagnoses recorded: " + ", ".join(e["diagnoses"]) + ".")
        parts.append(f"[{e['id']}] " + " ".join(facts))
    return "\n\n".join(parts)


def _token_set(text: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(text) if len(w) > 2}


def validate_grounding(answer: str, evidence: list[Evidence]) -> tuple[float, list[str]]:
    evidence_tokens = _token_set(" ".join(e.text for e in evidence))
    sentences = [s.strip() for s in SENTENCE_RE.split(answer) if s.strip() and not s.startswith("Synthetic educational demo")]
    if not sentences:
        return 1.0, []
    supported = 0
    unsupported = []
    for sentence in sentences:
        tokens = _token_set(sentence)
        content_tokens = {t for t in tokens if not t.startswith("e100")}
        overlap = len(content_tokens & evidence_tokens) / max(1, len(content_tokens))
        has_citation = bool(re.search(r"\[E\d+-\d+\]", sentence))
        if overlap >= 0.32 or has_citation:
            supported += 1
        else:
            unsupported.append(sentence)
    return round(supported / len(sentences), 3), unsupported


async def answer_query(patient_id: str, question: str) -> QueryResponse:
    safety = classify_request(question)
    if not safety.allowed:
        return QueryResponse(
            status="blocked",
            answer=safety.reason,
            mode="blocked",
            safety=safety,
            support_score=1.0,
            unsupported_claims=[],
            evidence=[],
            disclaimer=DISCLAIMER,
        )

    rows = retrieve(patient_id, question, top_k=3)
    evidence = [Evidence(encounter_id=r["encounter"]["id"], date=r["encounter"]["date"], score=r["score"], text=r["text"]) for r in rows]
    if not evidence:
        return QueryResponse(
            status="no_evidence",
            answer="I could not find relevant historical evidence for that question.",
            mode="extractive",
            safety=safety,
            support_score=1.0,
            unsupported_claims=[],
            evidence=[],
            disclaimer=DISCLAIMER,
        )

    external_context = redact_external_context("\n".join(e.text for e in evidence))
    try:
        llm_answer = await generate_answer(question, external_context)
    except Exception:
        llm_answer = None

    if llm_answer:
        answer = llm_answer
        mode = "llm"
    else:
        answer = _extractive_answer(rows)
        mode = "extractive"

    score, unsupported = validate_grounding(answer, evidence)
    if mode == "llm" and score < 0.5:
        answer = _extractive_answer(rows)
        mode = "extractive"
        score, unsupported = validate_grounding(answer, evidence)

    return QueryResponse(
        status="success",
        answer=answer,
        mode=mode,
        safety=safety,
        support_score=score,
        unsupported_claims=unsupported,
        evidence=evidence,
        disclaimer=DISCLAIMER,
    )
