from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic_ehr.json"
TOKEN_RE = re.compile(r"[A-Za-z0-9.]+")
STOP = {"the","a","an","and","or","of","to","in","on","for","was","were","is","are","this","that","patient","about","what","when","show","me","their"}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text) if t.lower() not in STOP and len(t) > 1]


def encounter_text(encounter: dict) -> str:
    return " | ".join([
        f"Encounter {encounter['id']}",
        f"Date {encounter['date']}",
        f"Type {encounter['type']}",
        encounter["summary"],
        "Medications: " + ", ".join(encounter.get("medications", [])),
        "Labs: " + ", ".join(encounter.get("labs", [])),
        "Diagnoses: " + ", ".join(encounter.get("diagnoses", [])),
    ])


@lru_cache(maxsize=1)
def load_dataset() -> dict[str, list[dict]]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {row["patient_id"]: row["encounters"] for row in payload}


def list_patients() -> list[str]:
    return sorted(load_dataset().keys())


def _idf(doc_tokens: list[list[str]]) -> dict[str, float]:
    n = len(doc_tokens)
    df = Counter()
    for tokens in doc_tokens:
        df.update(set(tokens))
    return {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}


def _vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    if not counts:
        return {}
    total = sum(counts.values())
    return {term: (count / total) * idf.get(term, 1.0) for term, count in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(patient_id: str, question: str, top_k: int = 3) -> list[dict]:
    encounters = load_dataset().get(patient_id)
    if not encounters:
        return []
    normalized_question = " ".join(question.lower().split())
    if any(phrase in normalized_question for phrase in ("last encounter", "latest encounter", "most recent encounter", "last visit", "latest visit")):
        latest = sorted(encounters, key=lambda e: e["date"], reverse=True)[0]
        return [{"encounter": latest, "text": encounter_text(latest), "score": 1.0}]
    docs = [encounter_text(e) for e in encounters]
    doc_tokens = [tokenize(d) for d in docs]
    query_tokens = tokenize(question)
    idf = _idf(doc_tokens + [query_tokens])
    qv = _vector(query_tokens, idf)
    scored = []
    for encounter, text, tokens in zip(encounters, docs, doc_tokens):
        score = _cosine(qv, _vector(tokens, idf))
        scored.append({"encounter": encounter, "text": text, "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [row for row in scored[:top_k] if row["score"] > 0]
