import asyncio
import json
import subprocess
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import Settings, create_app
from app.collector import Collector, CollectionError
from app.diagnosis import diagnose
from app.fixtures import sample
from app.security import redact
from app.llm import assess

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(token="",kubeconfig="",api_key="",model="",db=str(tmp_path/"history.db"))))

@pytest.mark.parametrize("scenario,code",[("crashloop","crashloop"),("imagepull","imagepull"),("oom","oom"),("pending","pending"),("network","selector"),("probe","probe")])
def test_incident_root_cause_and_evidence(client,scenario,code):
    response=client.post("/api/investigate",json={"scenario":scenario})
    assert response.status_code==200
    report=response.json()
    assert report["mode"]=="demo" and report["ai"]["status"]=="disabled"
    assert report["findings"][0]["code"]==code
    assert report["findings"][0]["evidence_refs"]
    assert report["stats"]["findings"]==len(report["findings"])
    for finding in report["findings"]:
        for command in finding["commands"]:
            assert command.split()[1] in {"get","describe","logs"}

def test_healthy_does_not_invent_failure(client):
    report=client.post("/api/investigate",json={"scenario":"healthy"}).json()
    assert report["status"]=="no_issues_detected"
    assert report["findings"]==[] and report["stats"]["ready"]==1

def test_stream_contains_completed_stages_before_result(client):
    response=client.post("/api/investigate/stream",json={"scenario":"network"})
    events=[json.loads(x) for x in response.text.splitlines()]
    assert len([e for e in events if e.get("status")=="complete"])==6
    assert events[-1]["type"]=="result"
    assert events[-1]["report"]["findings"][0]["code"]=="selector"

def test_public_cannot_enable_live_or_ai_or_read_history(client):
    with patch("app.collector.subprocess.run") as process,patch("app.llm.httpx.AsyncClient") as provider:
        assert client.post("/api/investigate",json={"mode":"live"}).status_code==503
        assert client.post("/api/investigate",json={"use_ai":True}).status_code==503
        assert client.get("/api/contexts").status_code==503
        assert client.get("/api/history").status_code==503
        process.assert_not_called(); provider.assert_not_called()

def test_invalid_inputs_rejected(client):
    assert client.post("/api/investigate",json={"scenario":"invalid"}).status_code==422
    assert client.post("/api/investigate",json={"namespace":"default; touch /tmp/pwn"}).status_code==422
    assert client.post("/api/investigate",json={"mode":"anything"}).status_code==422
    assert client.post("/api/investigate",content='a'*9000).status_code==413

def test_authentication_and_namespace_scope(tmp_path):
    token="test-owner-token-with-at-least-32-characters"
    client=TestClient(create_app(Settings(token=token,kubeconfig="/trusted/config",api_key="",model="",db=str(tmp_path/"history.db"))))
    with patch.object(Collector,"contexts",return_value=["trusted"]):
        assert client.get("/api/contexts").status_code==401
        assert client.get("/api/history",headers={"Authorization":"Bearer wrong"}).status_code==401
        auth={"Authorization":"Bearer "+token}
        assert client.get("/api/contexts",headers=auth).json()["contexts"]==["trusted"]
        assert client.post("/api/investigate",headers=auth,json={"mode":"live","namespace":"kube-system","context":"trusted"}).status_code==403
        assert client.post("/api/investigate",headers=auth,json={"mode":"live","context":"--evil"}).status_code==422

def test_live_incomplete_collection_never_returns_healthy(tmp_path):
    token="test-owner-token-with-at-least-32-characters"
    client=TestClient(create_app(Settings(token=token,kubeconfig="/trusted/config",db=str(tmp_path/"history.db"))))
    evidence=sample("healthy")
    with patch.object(Collector,"contexts",return_value=["trusted"]),patch.object(Collector,"pods",return_value=evidence["pods"]),patch.object(Collector,"logs",return_value=[]),patch.object(Collector,"events",side_effect=CollectionError("fail")),patch.object(Collector,"deployments",return_value=evidence["deployments"]),patch.object(Collector,"network",return_value=evidence["network"]):
        auth={"Authorization":"Bearer "+token}
        result=client.post("/api/investigate",headers=auth,json={"mode":"live","context":"trusted"}).json()
        assert result["status"]=="incomplete"
        assert result["evidence"]["warnings"]
        history=client.get("/api/history",headers=auth).json()
        assert history[0]["id"]==result["id"]
        assert client.get("/api/history").status_code==401

def test_live_pod_collection_failure_is_actionable(tmp_path):
    token="test-owner-token-with-at-least-32-characters"
    client=TestClient(create_app(Settings(token=token,kubeconfig="/trusted/config",db=str(tmp_path/"h.db"))))
    with patch.object(Collector,"contexts",return_value=["trusted"]),patch.object(Collector,"pods",side_effect=CollectionError("Cluster unreachable.")):
        response=client.post("/api/investigate",headers={"Authorization":"Bearer "+token},json={"mode":"live","context":"trusted"})
        assert response.status_code==503 and response.json()["detail"]=="Cluster unreachable."

def test_collector_command_boundary():
    collector=Collector("/trusted/config",context="example; echo nope")
    with patch("app.collector.subprocess.run",return_value=subprocess.CompletedProcess([],0,'{"items":[]}',"")) as process:
        assert collector.get("pods")==[]
        assert process.call_args.kwargs["shell"] is False
        assert "--context=example; echo nope" in process.call_args.args[0]
        with pytest.raises(CollectionError): collector.run(["delete","pods","--all"])
        with pytest.raises(CollectionError): collector.get("secrets")

def test_collector_reduces_pod_environment_and_detects_init_failure():
    raw={"metadata":{"name":"test-pod","labels":{"app":"test"}},"spec":{"containers":[{"name":"api","env":[{"name":"PASSWORD","value":"not-for-reports"}]}]},"status":{"phase":"Pending","initContainerStatuses":[{"name":"init","state":{"waiting":{"reason":"CrashLoopBackOff"}},"restartCount":3}]}}
    collector=Collector("/trusted/config")
    with patch.object(collector,"get",return_value=[raw]):
        data=collector.pods()
    assert data[0]["status"]=="CrashLoopBackOff"
    assert "not-for-reports" not in json.dumps(data)

def test_log_redaction():
    data=redact({"logs":"Authorization: Bearer abc.def.ghi password=abc123 postgres://alice:pass@host token=xyz", "api_key":"private"})
    assert all(secret not in json.dumps(data) for secret in ["abc.def.ghi","abc123","alice:pass","xyz","private"])
    assert "DATABASE_URL environment variable is missing" in redact("DATABASE_URL environment variable is missing")

def test_ai_provider_failure_falls_back_without_exposing_key():
    class BrokenClient:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            import httpx
            raise httpx.ConnectError("secret-must-not-leak")
    with patch("app.llm.httpx.AsyncClient",return_value=BrokenClient()):
        result=asyncio.run(assess(sample("oom"),[],"secret-must-not-leak","test-model"))
    assert result["status"]=="unavailable"
    assert "secret-must-not-leak" not in json.dumps(result)

def test_static_page_health_and_headers(client):
    assert client.get("/health").json()["status"]=="healthy"
    page=client.get("/")
    assert "KubeScope" in page.text
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert client.get("/static/app.js").status_code==200
    assert client.get("/.env").status_code==404
