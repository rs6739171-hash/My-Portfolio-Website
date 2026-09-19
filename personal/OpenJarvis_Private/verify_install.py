from pathlib import Path

import openjarvis
import litellm

root = Path(openjarvis.__file__).resolve().parent
static_index = root / "server" / "static" / "index.html"
if not static_index.exists():
    raise SystemExit(
        f"OpenJarvis browser assets are missing from the installed package: {static_index}"
    )

print(f"OpenJarvis installed at: {root}")
print(f"Browser assets: {static_index}")
print(f"LiteLLM: {getattr(litellm, '__version__', 'installed')}")
