# Multi-Agent Travel Planner — LangGraph + MCP + Supervisor + Guardrails + HITL

Portfolio deployment adapted from the Apache-2.0 licensed upstream project:
https://github.com/entbappy/Multi-Agent-System-using-LangGraph-MCP-Supervisor-Guardrails-HITL

## What this demonstrates
- LangGraph multi-agent orchestration
- Supervisor-based specialist routing
- Input guardrails
- Human-in-the-loop approval and revision
- FastAPI UI/API
- MCP integrations for search, aviation, and weather
- PostgreSQL checkpointer support with an in-memory deployment fallback

## Deployment-safe demo mode
The application starts without provider secrets. When `GROQ_API_KEY` is absent,
a deterministic demo model keeps the supervisor, specialist flow, guardrail path,
interrupt, approval, and finalization experience usable.

Optional live integrations:
- `GROQ_API_KEY`
- `TAVILY_API_KEY`
- `AVIATION_STACK_API_KEY`
- `OPENWEATHER_API_KEY`
- `DATABASE_URL` for persistent LangGraph checkpoints

## Run
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Attribution
The original LICENSE is preserved in this directory. This portfolio copy includes
deployment-oriented fallback and integration changes by Rishabh Shukla.
