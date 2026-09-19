from __future__ import annotations

import base64
import hashlib
import hmac


def derive_runtime_keys(app_password: str) -> tuple[str, str]:
    """Derive internal-only keys from the user-supplied gateway password.

    The login password itself is never written to source. The derived keys are
    domain-separated so the OpenJarvis bearer token and cookie-signing key are
    different values even though they originate from one deployment secret.
    """
    master = hashlib.sha256(app_password.encode("utf-8")).digest()
    api_bytes = hmac.new(master, b"openjarvis-internal-api-v1", hashlib.sha256).digest()
    session_bytes = hmac.new(master, b"openjarvis-session-signing-v1", hashlib.sha256).digest()
    api_key = "oj_sk_" + base64.urlsafe_b64encode(api_bytes).decode("ascii").rstrip("=")
    session_secret = base64.urlsafe_b64encode(session_bytes).decode("ascii").rstrip("=")
    return api_key, session_secret
