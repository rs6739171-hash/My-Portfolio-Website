"""Synthetic evidence for the public demonstration. Never represents a live cluster."""
from copy import deepcopy

SCENARIOS = [
    {"id":"crashloop", "title":"The payment service is restarting", "category":"CrashLoopBackOff", "description":"Correlate startup logs with repeated container failures.", "severity":"critical"},
    {"id":"imagepull", "title":"A release cannot pull its image", "category":"ImagePullBackOff", "description":"Trace a failed rollout to an unavailable image tag.", "severity":"critical"},
    {"id":"oom", "title":"The worker keeps running out of memory", "category":"OOMKilled", "description":"Inspect termination reasons and resource limits.", "severity":"warning"},
    {"id":"pending", "title":"New pods are stuck in Pending", "category":"FailedScheduling", "description":"Read scheduler evidence before changing capacity.", "severity":"warning"},
    {"id":"network", "title":"A service has no matching backends", "category":"Selector mismatch", "description":"Compare service selectors with actual pod labels.", "severity":"critical"},
    {"id":"probe", "title":"The readiness check is failing", "category":"Readiness probe", "description":"Connect probe events with unavailable replicas.", "severity":"warning"},
    {"id":"healthy", "title":"Check a healthy workload", "category":"Healthy baseline", "description":"Verify that successful checks do not invent an incident.", "severity":"healthy"},
]

def sample(scenario: str) -> dict:
    if scenario not in {x["id"] for x in SCENARIOS}:
        raise ValueError("Unknown sample incident")
    pod = {"name":"payment-api-7b6f4b8b9d-k2mlp", "namespace":"demo", "status":"Running", "ready":True, "restarts":0, "labels":{"app":"payment-api"}, "containers":[{"name":"api", "image":"example/payment-api:v1", "memory_limit":"256Mi", "reason":"", "last_reason":""}]}
    data = {"pods":[pod], "logs":[], "events":[], "deployments":[{"name":"payment-api", "namespace":"demo", "desired":1, "available":1, "conditions":[]}], "network":{"services":[{"name":"payment-api", "selector":{"app":"payment-api"}, "type":"ClusterIP", "endpoint_count":1}]}, "warnings":[]}
    if scenario != "healthy":
        pod["ready"]=False
        data["deployments"][0]["available"]=0
        data["network"]["services"][0]["endpoint_count"]=0
    if scenario == "crashloop":
        pod.update(status="CrashLoopBackOff", restarts=8)
        pod["containers"][0]["reason"]="CrashLoopBackOff"
        data["logs"]=[{"pod":pod["name"],"container":"api","previous":True,"text":"ERROR startup validation failed: DATABASE_URL environment variable is missing\nProcess exited with code 1"}]
        data["events"]=[{"reason":"BackOff","message":"Back-off restarting failed container api", "resource":pod["name"]}]
    elif scenario == "imagepull":
        pod.update(status="ImagePullBackOff")
        pod["containers"][0].update(image="example/payment-api:v404",reason="ImagePullBackOff")
        data["events"]=[{"reason":"Failed","message":"Failed to pull image example/payment-api:v404: manifest unknown", "resource":pod["name"]}]
    elif scenario == "oom":
        pod.update(status="CrashLoopBackOff",restarts=5)
        pod["containers"][0].update(reason="CrashLoopBackOff",last_reason="OOMKilled",memory_limit="64Mi")
        data["events"]=[{"reason":"BackOff","message":"Container restarted after OOMKilled (exit 137)","resource":pod["name"]}]
    elif scenario == "pending":
        pod.update(status="Pending")
        data["events"]=[{"reason":"FailedScheduling","message":"0/2 nodes are available: 2 Insufficient cpu", "resource":pod["name"]}]
    elif scenario == "network":
        pod["ready"]=True
        data["deployments"][0]["available"]=1
        data["network"]["services"][0]["selector"]={"app":"payments-api"}
    elif scenario == "probe":
        data["events"]=[{"reason":"Unhealthy","message":"Readiness probe failed: HTTP probe failed with statuscode: 503", "resource":pod["name"]}]
        data["logs"]=[{"pod":pod["name"],"container":"api","previous":False,"text":"GET /ready -> 503: database dependency is not ready"}]
    return deepcopy(data)
