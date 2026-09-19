from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    public_port = os.getenv("PORT", "10000")
    env = os.environ.copy()
    env.setdefault("API_URL", "http://127.0.0.1:8000")

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env,
    )
    ui = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app/ui.py",
            "--server.address", "0.0.0.0",
            "--server.port", public_port,
            "--server.headless", "true",
        ],
        env=env,
    )

    children = [api, ui]

    def stop(*_):
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    stop()
                    return code
            time.sleep(1)
    finally:
        stop()


if __name__ == "__main__":
    raise SystemExit(main())
