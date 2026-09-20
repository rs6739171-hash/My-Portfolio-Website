# TripMate AI — Multi-Agent Travel Planner

TripMate AI is a deployment-ready travel-planning application that combines **LangGraph orchestration, MCP tools, supervisor routing, input guardrails, direct API fallbacks, FastAPI, checkpointing, and human-in-the-loop review** in one web experience.

## Final merged architecture

This project consolidates ideas and implementation from three upstream learning repositories:

1. `entbappy/TripMate-AI-A-Multi-Agent-Travel-Planner-with-LangGraph`
   - original LangGraph specialist workflow
   - direct AviationStack flight lookup
   - direct Tavily search
   - FastAPI/Jinja frontend structure
2. `entbappy/TripMate-AI-Using-MCP`
   - MCP-backed Tavily search
   - AviationStack MCP adapter
   - custom OpenWeather MCP server
3. `entbappy/Multi-Agent-System-using-LangGraph-MCP-Supervisor-Guardrails-HITL`
   - supervisor routing
   - input guardrail
   - dynamic specialist selection
   - human-in-the-loop approval/revision

The portfolio version merges these into one coherent application instead of maintaining three parallel implementations.

## Runtime flow

```text
User request
   ↓
Input Guardrail
   ↓
Supervisor
   ↓
Selected specialists
   ├── Flight Agent   → MCP AviationStack → direct AviationStack fallback
   ├── Hotel Agent    → MCP Tavily        → direct Tavily fallback
   ├── Weather Agent  → Weather MCP       → direct OpenWeather fallback
   └── Budget Agent   → LLM analysis
   ↓
Itinerary Agent
   ↓
LangGraph interrupt
   ↓
Human approve / revise
   ↓
Final Response Agent
```

## FastAPI API

- `GET /` — interactive frontend
- `GET /health` — deployment health
- `GET /api/capabilities` — safe, non-secret integration status
- `POST /api/travel` — start a travel-planning workflow
- `POST /api/travel/approve` — resume the LangGraph thread after human review

The FastAPI layer runs synchronous LangGraph work in worker threads so MCP and direct tool calls do not block the server event loop.

## Frontend

The final UI includes:

- live deployment/integration status
- supervisor and guardrail visibility
- agent execution rail
- MCP/direct/fallback integration trace
- expandable specialist evidence
- draft itinerary review
- human approval/revision controls
- final Markdown rendering
- copy and PDF export
- responsive mobile layout

## Environment variables

All provider credentials stay outside the repository.

```env
MISTRAL_API_KEY=\n# Optional fallback:\nGROQ_API_KEY=\nTAVILY_API_KEY=
AVIATION_STACK_API_KEY=
OPENWEATHER_API_KEY=
DATABASE_URL=
DEFAULT_ORIGIN_IATA=AMD
```

`AVIATIONSTACK_API_KEY` is also accepted for compatibility with the upstream repositories.

### Graceful deployment mode

The app can start without provider secrets. In that state:

- Mistral is the primary live LLM when `MISTRAL_API_KEY` is configured.\n- Groq remains an optional secondary provider; without either LLM key the app uses a deterministic demo engine.
- MCP integrations fall back to direct integrations when corresponding keys are configured.
- If no provider is configured, specialists return explicit non-live guidance rather than crashing.
- PostgreSQL is used when `DATABASE_URL` exists; otherwise LangGraph uses in-memory checkpoints.

## Local run

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
pip install uv

uvicorn app:app --host 0.0.0.0 --port 8000
```

## Deployment

The portfolio deployment uses Render with:

```bash
pip install -r projects/Multi_Agent_LangGraph_MCP_Supervisor_HITL/requirements.txt && pip install uv
```

Start command:

```bash
cd projects/Multi_Agent_LangGraph_MCP_Supervisor_HITL && uvicorn app:app --host 0.0.0.0 --port $PORT
```

## Attribution and licenses

This directory preserves the Apache-2.0 license from the supervisor/guardrails upstream project. Code incorporated from the two TripMate repositories is MIT-licensed by Bappy Ahmed; the required MIT notice is preserved in `LICENSE-MIT-TRIPMATE` and the source projects are listed in `THIRD_PARTY_NOTICES.md`.

Portfolio integration, deployment hardening, UI redesign, fallback orchestration, and FastAPI request-layer changes are maintained in this repository.
