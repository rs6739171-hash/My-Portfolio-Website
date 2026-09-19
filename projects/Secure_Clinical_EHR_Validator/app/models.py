from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    patient_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    question: str = Field(min_length=2, max_length=1200)


class Evidence(BaseModel):
    encounter_id: str
    date: str
    score: float
    text: str


class SafetyDecision(BaseModel):
    allowed: bool
    category: Literal["allowed", "medical_advice", "prompt_injection", "data_exfiltration"]
    reason: str


class QueryResponse(BaseModel):
    status: Literal["success", "blocked", "no_evidence"]
    answer: str
    mode: Literal["extractive", "llm", "blocked"]
    safety: SafetyDecision
    support_score: float
    unsupported_claims: list[str]
    evidence: list[Evidence]
    disclaimer: str
