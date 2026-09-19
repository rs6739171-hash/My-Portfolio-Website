from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import QueryRequest, QueryResponse
from .llm import verify_provider_access
from .retrieval import list_patients
from .service import answer_query

app = FastAPI(
    title="Secure Clinical EHR Insight Validator",
    version="1.0.0",
    description="Synthetic portfolio demo for scoped clinical retrieval, safety guardrails, and grounding validation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

@app.on_event("startup")
async def startup_provider_check():
    ready, message = await verify_provider_access()
    app.state.llm_provider_ready = ready
    app.state.llm_provider_message = message
    print(f"LLM provider check: {message}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_mode_available": settings.llm_enabled,
        "llm_provider_ready": getattr(app.state, "llm_provider_ready", False),
        "llm_model": settings.llm_model if settings.llm_enabled else None,
        "data": "synthetic-only",
    }


@app.get("/api/v1/patients")
def patients():
    return {"patients": list_patients(), "data_classification": "synthetic demo records"}


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    if payload.patient_id not in list_patients():
        raise HTTPException(status_code=404, detail="Unknown demo patient")
    return await answer_query(payload.patient_id, payload.question)
