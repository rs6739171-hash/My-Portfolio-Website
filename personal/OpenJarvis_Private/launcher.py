from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import uvicorn

from security_keys import derive_runtime_keys


BASE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("OPENJARVIS_HOME", "/tmp/openjarvis-home"))
INTERNAL_PORT = "8001"
MODEL = os.environ.get("OPENJARVIS_MODEL", "mistral/mistral-small-latest")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Required environment variable is missing: {name}")
    return value


def _prepare_config() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE / "safe_config.toml", HOME / "config.toml")


def _verify_mistral_provider() -> None:
    api_key = _require("MISTRAL_API_KEY")
    response = httpx.get(
        "https://api.mistral.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload.get("data"), list):
        raise SystemExit("Mistral provider validation returned an unexpected response.")
    print("Mistral provider check: authenticated successfully (zero-token verification).")


def _wait_for_backend(process: subprocess.Popen, timeout: float = 75.0) -> None:
    deadline = time.time() + timeout
    health = f"http://127.0.0.1:{INTERNAL_PORT}/health"
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"OpenJarvis exited during startup with code {process.returncode}")
        try:
            response = httpx.get(health, timeout=2.0)
            if response.status_code in (200, 503):
                return
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("OpenJarvis backend did not become reachable before timeout")


def main() -> int:
    _require("MISTRAL_API_KEY")
    _verify_mistral_provider()
    app_password = _require("APP_PASSWORD")
    internal_api_key, session_secret = derive_runtime_keys(app_password)
    os.environ["OPENJARVIS_API_KEY"] = internal_api_key
    os.environ["SESSION_SECRET"] = session_secret
    _prepare_config()

    from gateway import app

    env = os.environ.copy()
    env["OPENJARVIS_HOME"] = str(HOME)
    env["OPENJARVIS_API_KEY"] = internal_api_key

    jarvis = subprocess.Popen(
        [
            "jarvis",
            "serve",
            "--host", "127.0.0.1",
            "--port", INTERNAL_PORT,
            "--engine", "litellm",
            "--model", MODEL,
            "--agent", "simple",
        ],
        env=env,
    )

    def stop(*_):
        if jarvis.poll() is None:
            jarvis.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        _wait_for_backend(jarvis)
        port = int(os.environ.get("PORT", "10000"))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", proxy_headers=True)
    finally:
        stop()
        try:
            jarvis.wait(timeout=8)
        except subprocess.TimeoutExpired:
            jarvis.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
