from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import QueryRequest, QueryResponse
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


@app.get("/health")
def health():
    return {"status": "ok", "llm_mode_available": settings.llm_enabled, "data": "synthetic-only"}


@app.get("/api/v1/patients")
def patients():
    return {"patients": list_patients(), "data_classification": "synthetic demo records"}


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    if payload.patient_id not in list_patients():
        raise HTTPException(status_code=404, detail="Unknown demo patient")
    return await answer_query(payload.patient_id, payload.question)
