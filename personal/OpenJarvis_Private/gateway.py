from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import os
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket

from security_keys import derive_runtime_keys
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse


INTERNAL_HTTP = os.getenv("OPENJARVIS_INTERNAL_URL", "http://127.0.0.1:8001").rstrip("/")
INTERNAL_WS = INTERNAL_HTTP.replace("http://", "ws://").replace("https://", "wss://")
APP_USER = os.getenv("APP_USER", "rishabh")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
INTERNAL_API_KEY, SESSION_SECRET = derive_runtime_keys(APP_PASSWORD) if APP_PASSWORD else ("", "")
COOKIE = "oj_private_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_attempts: dict[str, deque[float]] = defaultdict(deque)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign(payload: str) -> str:
    return _b64(hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())


def _new_session(username: str) -> str:
    expires = int(time.time()) + SESSION_SECONDS
    payload = f"{username}|{expires}"
    return f"{_b64(payload.encode())}.{_sign(payload)}"


def _valid_session(token: str | None) -> bool:
    if not token or not SESSION_SECRET:
        return False
    try:
        payload_b64, signature = token.split(".", 1)
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(padded).decode()
        username, expires_raw = payload.rsplit("|", 1)
        expected = _sign(payload)
        return (
            hmac.compare_digest(signature, expected)
            and hmac.compare_digest(username, APP_USER)
            and int(expires_raw) >= int(time.time())
        )
    except Exception:
        return False


def _client_ip(request_or_ws) -> str:
    forwarded = request_or_ws.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    client = getattr(request_or_ws, "client", None)
    return getattr(client, "host", "unknown") if client else "unknown"


def _rate_limited(ip: str) -> bool:
    now = time.time()
    bucket = _attempts[ip]
    while bucket and now - bucket[0] > LOGIN_WINDOW_SECONDS:
        bucket.popleft()
    return len(bucket) >= MAX_LOGIN_ATTEMPTS


def _record_failure(ip: str) -> None:
    _attempts[ip].append(time.time())


def _login_page(error: str = "") -> HTMLResponse:
    message = (
        f'<div class="error">{html.escape(error)}</div>' if error else ""
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private OpenJarvis</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#070a0f;color:#f5f7fb;font-family:Inter,system-ui,-apple-system,sans-serif}}
.card{{width:min(92vw,420px);padding:32px;border:1px solid #263044;border-radius:18px;background:#0f1520;box-shadow:0 24px 70px #0008}}
.badge{{display:inline-block;padding:6px 10px;border:1px solid #34425a;border-radius:999px;color:#9fb0c8;font-size:12px;letter-spacing:.08em;text-transform:uppercase}}
h1{{font-size:28px;margin:18px 0 8px}}p{{color:#9ba9bd;line-height:1.55;margin:0 0 24px}}label{{display:block;font-size:13px;color:#bac5d6;margin:14px 0 7px}}
input{{width:100%;padding:13px 14px;border:1px solid #34425a;border-radius:10px;background:#0a0f17;color:#fff;outline:none}}input:focus{{border-color:#7289ff}}
button{{width:100%;margin-top:20px;padding:13px 16px;border:0;border-radius:10px;background:#e8edf8;color:#111827;font-weight:700;cursor:pointer}}
.error{{margin:0 0 16px;padding:10px 12px;border-radius:9px;background:#421b24;color:#ffbac7;font-size:13px}}
small{{display:block;margin-top:18px;color:#65738a;text-align:center}}
</style>
</head>
<body><main class="card">
<span class="badge">Private access</span>
<h1>OpenJarvis</h1>
<p>This deployment is protected by a private gateway before the OpenJarvis API layer.</p>
{message}
<form method="post" action="/login" autocomplete="on">
<label for="username">Username</label>
<input id="username" name="username" autocomplete="username" required>
<label for="password">Password</label>
<input id="password" type="password" name="password" autocomplete="current-password" required>
<button type="submit">Unlock Jarvis</button>
</form>
<small>Session expires automatically after 12 hours.</small>
</main></body></html>"""
    response = HTMLResponse(page)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/__gateway_health")
async def gateway_health():
    return {"status": "ok", "gateway": "private"}


@app.get("/login")
async def login_get(request: Request):
    if _valid_session(request.cookies.get(COOKIE)):
        return RedirectResponse("/", status_code=303)
    return _login_page()


@app.post("/login")
async def login_post(request: Request):
    ip = _client_ip(request)
    if _rate_limited(ip):
        return _login_page("Too many failed attempts. Try again in a few minutes.")

    body = (await request.body()).decode("utf-8", errors="ignore")
    form = parse_qs(body)
    username = (form.get("username") or [""])[0]
    password = (form.get("password") or [""])[0]

    valid = (
        APP_PASSWORD
        and hmac.compare_digest(username, APP_USER)
        and hmac.compare_digest(password, APP_PASSWORD)
    )
    if not valid:
        _record_failure(ip)
        await asyncio.sleep(0.35)
        return _login_page("Invalid username or password.")

    _attempts.pop(ip, None)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE,
        _new_session(APP_USER),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response


def _requires_login(request: Request) -> bool:
    return not _valid_session(request.cookies.get(COOKIE))


_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_http(path: str, request: Request):
    if _requires_login(request):
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "Private session required"}, status_code=401)

    url = f"{INTERNAL_HTTP}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() not in {"host", "authorization", "cookie"}
    }
    headers["Authorization"] = f"Bearer {INTERNAL_API_KEY}"
    headers["X-Forwarded-For"] = _client_ip(request)
    body = await request.body()

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    upstream_request = client.build_request(
        request.method,
        url,
        headers=headers,
        content=body,
    )
    try:
        upstream = await client.send(upstream_request, stream=True)
    except Exception:
        await client.aclose()
        return JSONResponse({"detail": "OpenJarvis backend unavailable"}, status_code=502)

    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    response_headers["X-Frame-Options"] = "DENY"
    response_headers["X-Content-Type-Options"] = "nosniff"
    response_headers["Referrer-Policy"] = "same-origin"

    async def body_stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        body_stream(),
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )


@app.websocket("/{path:path}")
async def proxy_websocket(websocket: WebSocket, path: str):
    if not _valid_session(websocket.cookies.get(COOKIE)):
        await websocket.close(code=4401)
        return

    query = websocket.url.query
    target = f"{INTERNAL_WS}/{path}" + (f"?{query}" if query else "")
    try:
        upstream = await websockets.connect(
            target,
            additional_headers={"Authorization": f"Bearer {INTERNAL_API_KEY}"},
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
        )
    except Exception:
        await websocket.close(code=1011)
        return

    await websocket.accept()

    async def browser_to_jarvis():
        try:
            while True:
                message = await websocket.receive()
                kind = message.get("type")
                if kind == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    await upstream.send(message["bytes"])
        finally:
            await upstream.close()

    async def jarvis_to_browser():
        try:
            async for message in upstream:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    await asyncio.gather(browser_to_jarvis(), jarvis_to_browser(), return_exceptions=True)
