# Private OpenJarvis deployment wrapper

This folder is intentionally kept off the public portfolio UI. It exists only on the `openjarvis-personal` branch as deployment glue for a personal OpenJarvis instance.

Upstream project: https://github.com/open-jarvis/OpenJarvis  
License: Apache-2.0 (upstream license and authorship remain with the OpenJarvis project).

## Security model

1. Public traffic reaches a small login gateway first.
2. Successful login creates a signed, HttpOnly, Secure, SameSite=Strict session cookie.
3. Failed logins are rate-limited in memory.
4. OpenJarvis itself binds only to `127.0.0.1:8001`.
5. The internal OpenJarvis API keeps its separate `OPENJARVIS_API_KEY`; the gateway injects it server-side.
6. OpenJarvis starts with the `simple` agent and no tools/MCP, with security scanning and default-deny capabilities enabled.
7. External anonymous analytics and local telemetry/traces are disabled in the supplied personal config.

## Render secrets

Never commit these:

- `MISTRAL_API_KEY`
- `OPENJARVIS_API_KEY`
- `APP_PASSWORD`
- `SESSION_SECRET`

Optional:

- `APP_USER` (defaults to `rishabh`)
- `OPENJARVIS_MODEL` (defaults to `mistral/mistral-small-latest`)

## Render commands

Build:

```bash
pip install -r personal/OpenJarvis_Private/requirements.txt && python personal/OpenJarvis_Private/verify_install.py
```

Start:

```bash
python personal/OpenJarvis_Private/launcher.py
```

Health check:

```
/__gateway_health
```

## Storage note

On a free Render web service the filesystem is ephemeral. OpenJarvis memory, settings and connector credentials stored under `OPENJARVIS_HOME` will not survive every restart/spin-down/redeploy. Use a paid persistent disk or external storage before relying on durable personal memory.
