from pathlib import Path
import asyncio
import traceback

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend import run_travel_agent, resume_travel_agent, system_capabilities

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="TripMate AI",
    description=(
        "Multi-agent travel planner with LangGraph, MCP, supervisor routing, "
        "guardrails, direct API fallbacks, and human-in-the-loop review."
    ),
    version="3.2.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class TravelRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    thread_id: str | None = None


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=200)
    approved: bool
    feedback: str = Field(default="", max_length=2000)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"capabilities": system_capabilities()},
    )


@app.get("/api/capabilities")
async def capabilities():
    return {"success": True, **system_capabilities()}


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    try:
        result = await asyncio.to_thread(
            run_travel_agent,
            request_data.message.strip(),
            request_data.thread_id,
        )
        return JSONResponse(content={"success": True, **result})
    except Exception as exc:
        print("TRAVEL ERROR:", exc, flush=True)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "The travel workflow could not complete. Please try again.",
                "detail": str(exc)[:500],
            },
        )


@app.post("/api/travel/approve")
async def approve_travel_plan(request_data: ApprovalRequest):
    if not request_data.approved and not request_data.feedback.strip():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Add revision feedback before requesting changes.",
            },
        )

    try:
        result = await asyncio.to_thread(
            resume_travel_agent,
            request_data.thread_id,
            request_data.approved,
            request_data.feedback,
        )
        return JSONResponse(content={"success": True, **result})
    except Exception as exc:
        print("APPROVAL ERROR:", exc, flush=True)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "The review step could not be resumed. Start a new plan if the session expired.",
                "detail": str(exc)[:500],
            },
        )


@app.get("/health")
async def health_check():
    caps = system_capabilities()
    return {
        "status": "ok",
        "message": "TripMate AI API is running",
        "version": caps["version"],
        "demo_mode": caps["demo_mode"],
        "persistence": caps["persistence"],
    }


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
