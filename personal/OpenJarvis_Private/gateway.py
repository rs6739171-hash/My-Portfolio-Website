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



def _chat_page() -> HTMLResponse:
    page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Private OpenJarvis</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#080b10;color:#e9eef7;font-family:Inter,system-ui,-apple-system,sans-serif}
.shell{min-height:100vh;display:grid;grid-template-rows:auto 1fr auto;max-width:980px;margin:auto}
header{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;border-bottom:1px solid #202938;background:#0c1119cc;backdrop-filter:blur(12px);position:sticky;top:0;z-index:2}
.brand{display:flex;align-items:center;gap:11px}.dot{width:10px;height:10px;border-radius:50%;background:#7d8cff;box-shadow:0 0 24px #7d8cff}
h1{font-size:16px;margin:0}.sub{font-size:11px;color:#718096;margin-top:3px}
.actions{display:flex;gap:8px}.actions button,.actions a{border:1px solid #2a3548;background:#121925;color:#c7d2e5;border-radius:9px;padding:8px 11px;text-decoration:none;font-size:12px;cursor:pointer}
#messages{padding:28px 20px 150px;display:flex;flex-direction:column;gap:16px}
.msg{max-width:82%;padding:13px 15px;border-radius:14px;line-height:1.55;white-space:pre-wrap;word-wrap:break-word}
.user{align-self:flex-end;background:#29385a;color:#fff;border-bottom-right-radius:4px}
.assistant{align-self:flex-start;background:#111925;border:1px solid #263247;color:#dce5f5;border-bottom-left-radius:4px}
.status{font-size:12px;color:#75859d;text-align:center;padding:8px}
.composer{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:min(980px,100%);padding:14px 20px 20px;background:linear-gradient(transparent,#080b10 28%)}
.box{display:flex;gap:10px;align-items:flex-end;border:1px solid #2a3548;background:#101720;border-radius:16px;padding:10px}
textarea{flex:1;min-height:46px;max-height:180px;resize:none;border:0;outline:0;background:transparent;color:#f5f7fb;font:inherit;padding:10px}
.send{border:0;border-radius:11px;padding:11px 16px;background:#e7ebf5;color:#111827;font-weight:700;cursor:pointer}.send:disabled{opacity:.45;cursor:wait}
.note{font-size:10px;color:#5f6e83;text-align:center;margin-top:8px}
@media(max-width:640px){.msg{max-width:92%}header{padding:14px}.composer{padding:10px 12px 14px}#messages{padding-left:12px;padding-right:12px}}
</style>
</head>
<body><div class="shell">
<header><div class="brand"><span class="dot"></span><div><h1>OpenJarvis · Private</h1><div class="sub">Mistral Small · simple agent · tools disabled</div></div></div>
<div class="actions"><button id="clear">Clear</button><a href="/logout">Lock</a></div></header>
<main id="messages"><div class="status">Private session active. Messages are sent through your secured OpenJarvis backend.</div></main>
<div class="composer"><div class="box"><textarea id="prompt" placeholder="Message Jarvis…" rows="1"></textarea><button class="send" id="send">Send</button></div><div class="note">Initial hardened mode: no shell, file access, MCP, channels, or autonomous tasks.</div></div>
</div>
<script>
const messages=[];
const list=document.getElementById('messages');
const prompt=document.getElementById('prompt');
const send=document.getElementById('send');
function add(role,text){
  const el=document.createElement('div');
  el.className='msg '+(role==='user'?'user':'assistant');
  el.textContent=text;
  list.appendChild(el);
  window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});
}
async function submit(){
  const text=prompt.value.trim(); if(!text||send.disabled)return;
  prompt.value=''; add('user',text); messages.push({role:'user',content:text}); send.disabled=true;
  const waiting=document.createElement('div'); waiting.className='msg assistant'; waiting.textContent='Thinking…'; list.appendChild(waiting);
  try{
    const res=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      model:'mistral/mistral-small-latest',messages,temperature:0.3,max_tokens:1024,stream:false
    })});
    if(res.status===401){location.href='/login';return}
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||data.error?.message||('HTTP '+res.status));
    const answer=data.choices?.[0]?.message?.content||'No response content returned.';
    waiting.remove(); add('assistant',answer); messages.push({role:'assistant',content:answer});
  }catch(err){waiting.textContent='Error: '+err.message}
  finally{send.disabled=false;prompt.focus()}
}
send.addEventListener('click',submit);
prompt.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit()}});
document.getElementById('clear').addEventListener('click',()=>{messages.length=0;[...list.querySelectorAll('.msg')].forEach(x=>x.remove())});
prompt.focus();
</script></body></html>"""
    response = HTMLResponse(page)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
async def private_chat(request: Request):
    if _requires_login(request):
        return RedirectResponse("/login", status_code=303)
    return _chat_page()

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
