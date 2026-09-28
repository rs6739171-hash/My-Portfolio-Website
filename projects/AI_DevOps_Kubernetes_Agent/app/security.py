import re
import secrets
from fastapi import HTTPException

NAME = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")

def resource_name(value: str) -> str:
    if not NAME.fullmatch(value):
        raise ValueError("Invalid Kubernetes resource name")
    return value

def authenticate(header: str | None, token: str) -> None:
    if len(token) < 32:
        raise HTTPException(503, "Owner access is not configured on this deployment.")
    provided = (header or "").removeprefix("Bearer ")
    if not header or not header.startswith("Bearer ") or not secrets.compare_digest(provided.encode(), token.encode()):
        raise HTTPException(401, "A valid owner access token is required.")

def redact(value):
    """Best-effort scrubbing, not a substitute for controlling collected logs."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if re.search(r"password|token|api.?key|authorization|private.?key", k, re.I) else redact(v)) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:password|token|api[_-]?key|secret|database_url)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", value)
    value = re.sub(r"(\w+://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@", value)
    return value
