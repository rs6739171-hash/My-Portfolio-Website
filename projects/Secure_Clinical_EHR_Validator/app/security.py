from __future__ import annotations

import re

from .models import SafetyDecision


MEDICAL_ADVICE_PATTERNS = [
    r"\bshould\s+(?:i|we)\s+(?:start|stop|increase|decrease|prescribe|give|switch)",
    r"\bwhat\s+(?:drug|medication|antibiotic|dose|treatment)\s+should\b",
    r"\bdiagnose\b",
    r"\bdo\s+i\s+have\b",
    r"\brecommend\s+(?:a\s+)?(?:drug|medication|dose|treatment)",
    r"\bchange\s+(?:the\s+)?dose\b",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous",
    r"system\s+prompt",
    r"developer\s+message",
    r"jailbreak",
    r"reveal\s+(?:your\s+)?instructions",
    r"bypass\s+(?:the\s+)?guardrail",
]

EXFILTRATION_PATTERNS = [
    r"all\s+patients",
    r"every\s+patient",
    r"dump\s+(?:the\s+)?database",
    r"list\s+(?:all\s+)?patient\s+ids",
]


def classify_request(text: str) -> SafetyDecision:
    normalized = " ".join(text.lower().split())
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, normalized):
            return SafetyDecision(allowed=False, category="prompt_injection", reason="The request attempts to override application instructions or security controls.")
    for pattern in EXFILTRATION_PATTERNS:
        if re.search(pattern, normalized):
            return SafetyDecision(allowed=False, category="data_exfiltration", reason="The request attempts to access records outside the selected patient scope.")
    for pattern in MEDICAL_ADVICE_PATTERNS:
        if re.search(pattern, normalized):
            return SafetyDecision(allowed=False, category="medical_advice", reason="The demo retrieves historical information but does not diagnose, prescribe, or recommend treatment changes.")
    return SafetyDecision(allowed=True, category="allowed", reason="Historical-record retrieval request passed deterministic safety checks.")


PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<SSN>"),
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    (re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"), "<PHONE>"),
]


def redact_external_context(text: str) -> str:
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    redacted = re.sub(r"\bDEMO-\d+\b", "<PATIENT_ID>", redacted)
    return redacted
