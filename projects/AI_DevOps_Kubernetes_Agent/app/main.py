import asyncio
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .collector import Collector, CollectionError
from .diagnosis import diagnose
from .fixtures import SCENARIOS, sample
from .llm import assess
from .security import authenticate, redact

ROOT=Path(__file__).resolve().parent.parent

@dataclass
class Settings:
    token: str=field(default_factory=lambda:os.getenv("APP_AUTH_TOKEN",""))
    kubeconfig: str=field(default_factory=lambda:os.getenv("KUBECONFIG_PATH",""))
    kubectl: str=field(default_factory=lambda:os.getenv("KUBECTL_BIN","kubectl"))
    namespaces: tuple=field(default_factory=lambda:tuple(x.strip() for x in os.getenv("KUBE_NAMESPACES","default").split(",") if x.strip()))
    api_key: str=field(default_factory=lambda:os.getenv("OPENROUTER_API_KEY",""))
    model: str=field(default_factory=lambda:os.getenv("OPENROUTER_MODEL",""))
    live_ai: bool=field(default_factory=lambda:os.getenv("ALLOW_LIVE_LLM","false").lower()=="true")
    db: str=field(default_factory=lambda:os.getenv("HISTORY_DB","/tmp/kubescope-history.sqlite3"))

class Investigation(BaseModel):
    mode: Literal["demo","live"]="demo"
    scenario: str=Field(default="crashloop",max_length=40)
    context: str=Field(default="",max_length=256)
    namespace: str=Field(default="default",pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    use_ai: bool=False

def create_app(cfg=None):
    cfg=cfg or Settings()
    app=FastAPI(title="KubeScope — AI DevOps Kubernetes Agent",version="1.0.0")
    capacity=asyncio.Semaphore(3)

    @app.middleware("http")
    async def headers(request: Request,call_next):
        if request.method=="POST":
            raw=await request.body()
            if len(raw)>8192:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail":"Request too large."},status_code=413)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path in {"/docs","/redoc"}:
            response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"): response.headers["Cache-Control"]="no-store"
        return response

    @app.get("/health")
    def health():
        return {"status":"healthy","service":"ai-kubernetes-agent","version":"1.0.0"}

    @app.get("/api/config")
    def config():
        return {"demo":True,"live_configured":bool(cfg.kubeconfig and len(cfg.token)>=32),"ai_configured":bool(cfg.api_key and cfg.model and len(cfg.token)>=32),"live_ai_enabled":cfg.live_ai,"history":"Demo reports stay in this browser. Live server history requires owner access and a persistent disk to survive redeploys."}

    @app.get("/api/scenarios")
    def scenarios(): return SCENARIOS

    @app.get("/api/contexts")
    async def contexts(authorization: str | None=Header(default=None)):
        authenticate(authorization,cfg.token)
        if not cfg.kubeconfig: raise HTTPException(503,"No cluster is configured. Mount a trusted kubeconfig on the server.")
        try:
            names=await asyncio.to_thread(Collector(cfg.kubeconfig,binary=cfg.kubectl).contexts)
        except CollectionError as exc:
            raise HTTPException(503,str(exc)) from exc
        return {"contexts":names,"namespaces":cfg.namespaces}

    def connection():
        Path(cfg.db).parent.mkdir(parents=True,exist_ok=True)
        con=sqlite3.connect(cfg.db,timeout=5)
        con.execute("CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, created TEXT NOT NULL, data TEXT NOT NULL)")
        return con

    @app.get("/api/history")
    def history(authorization: str | None=Header(default=None)):
        authenticate(authorization,cfg.token)
        with connection() as con:
            return [json.loads(x[0]) for x in con.execute("SELECT data FROM reports ORDER BY created DESC LIMIT 20")]

    async def prepare(body,authorization):
        collector=None
        if body.mode=="demo":
            if body.scenario not in {s["id"] for s in SCENARIOS}: raise HTTPException(422,"Choose a valid sample incident.")
        else:
            authenticate(authorization,cfg.token)
            if not cfg.kubeconfig: raise HTTPException(503,"A live Kubernetes cluster is not configured.")
            if body.namespace not in cfg.namespaces: raise HTTPException(403,"This namespace is outside the configured allowlist.")
            collector=Collector(cfg.kubeconfig,namespace=body.namespace,binary=cfg.kubectl)
            try: names=await asyncio.to_thread(collector.contexts)
            except CollectionError as exc: raise HTTPException(503,str(exc)) from exc
            if body.context not in names: raise HTTPException(422,"Choose a context from the server's kubeconfig.")
            collector.context=body.context
        if body.use_ai:
            authenticate(authorization,cfg.token)
            if not cfg.api_key or not cfg.model: raise HTTPException(503,"OpenRouter is not configured. Rule-based analysis remains available.")
            if body.mode=="live" and not cfg.live_ai: raise HTTPException(403,"Sending live evidence to OpenRouter is disabled by the owner.")
        try: await asyncio.wait_for(capacity.acquire(),timeout=0.5)
        except TimeoutError: raise HTTPException(429,"Investigations are busy. Try again in a moment.")
        return collector

    async def run(body,collector):
        started=time.monotonic()
        evidence={"namespace":"demo" if body.mode=="demo" else body.namespace,"warnings":[]}
        demo=sample(body.scenario) if body.mode=="demo" else None
        labels={"pods":"Inspecting pod health","logs":"Collecting container logs","events":"Reading Kubernetes events","deployments":"Checking rollout health","network":"Comparing services and endpoints"}
        try:
            for key,label in labels.items():
                yield {"type":"progress","stage":key,"label":label,"status":"running"}
                if demo is not None:
                    evidence[key]=demo[key]
                else:
                    try:
                        method=getattr(collector,key)
                        evidence[key]=await asyncio.to_thread(method,*([evidence["pods"]] if key=="logs" else []))
                    except CollectionError:
                        if key=="pods": raise
                        evidence["warnings"].append(f"{label} was incomplete. Verify resource permissions and cluster reachability.")
                        evidence[key]={"services":[]} if key=="network" else []
                yield {"type":"progress","stage":key,"label":label,"status":"complete"}
            if collector: evidence["warnings"]+=collector.warnings
            evidence=redact(evidence)
            yield {"type":"progress","stage":"analysis","label":"Correlating evidence","status":"running"}
            findings=diagnose(evidence)
            ai={"status":"disabled","summary":"Deterministic rule analysis. No language model was called."}
            if body.use_ai:
                yield {"type":"progress","stage":"analysis","label":"Requesting AI assessment","status":"running"}
                ai=await assess(evidence,findings,cfg.api_key,cfg.model)
            yield {"type":"progress","stage":"analysis","label":"Analysis complete","status":"complete"}
            result={"id":str(uuid.uuid4()),"created_at":datetime.now(timezone.utc).isoformat(),"mode":body.mode,"scenario":body.scenario if demo else None,"context":"sample-cluster" if demo else body.context,"namespace":evidence["namespace"],"status":"issues_found" if findings else "incomplete" if evidence["warnings"] else "no_issues_detected","engine":"rules + AI assessment" if ai["status"]=="completed" else "evidence-based rules","duration_ms":round((time.monotonic()-started)*1000),"findings":findings,"evidence":evidence,"ai":ai,"stats":{"pods":len(evidence["pods"]),"ready":sum(p["ready"] for p in evidence["pods"]),"restarts":sum(p["restarts"] for p in evidence["pods"]),"findings":len(findings)},"confidence_note":"Confidence labels describe rule evidence strength, not a calibrated probability. No fixes are executed."}
            if body.mode=="live":
                try:
                    with connection() as con:
                        con.execute("INSERT INTO reports VALUES (?,?,?)",(result["id"],result["created_at"],json.dumps(result)))
                        con.execute("DELETE FROM reports WHERE id NOT IN (SELECT id FROM reports ORDER BY created DESC LIMIT 100)")
                except sqlite3.Error:
                    result["evidence"]["warnings"].append("Server history could not be saved. Download this report to keep a copy.")
            yield {"type":"result","report":result}
        except CollectionError as exc:
            yield {"type":"error","message":str(exc)}
        finally:
            capacity.release()

    @app.post("/api/investigate")
    async def investigate(body: Investigation,authorization: str | None=Header(default=None)):
        collector=await prepare(body,authorization)
        async for event in run(body,collector):
            if event["type"]=="result": return event["report"]
            if event["type"]=="error": raise HTTPException(503,event["message"])

    @app.post("/api/investigate/stream")
    async def stream(body: Investigation,authorization: str | None=Header(default=None)):
        collector=await prepare(body,authorization)
        async def lines():
            async for event in run(body,collector): yield json.dumps(event)+"\n"
        return StreamingResponse(lines(),media_type="application/x-ndjson",headers={"X-Accel-Buffering":"no"})

    @app.get("/")
    def index(): return FileResponse(ROOT/"static"/"index.html")

    app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")
    return app

app=create_app()
