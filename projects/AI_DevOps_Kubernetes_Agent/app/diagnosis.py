"""Explainable rules over collected evidence; no fabricated confidence percentages."""
import json
from .security import resource_name

def diagnose(evidence: dict) -> list[dict]:
    findings=[]
    def add(code,title,severity,explanation,refs,fix,commands,prevention,confidence="high"):
        findings.append(dict(code=code,title=title,severity=severity,explanation=explanation,evidence_refs=refs,fix=fix,commands=commands,prevention=prevention,confidence=confidence))
    for i,pod in enumerate(evidence["pods"]):
        name=resource_name(pod["name"]); namespace=resource_name(pod["namespace"])
        refs=[f"pods[{i}]"]
        logs=[(j,l) for j,l in enumerate(evidence["logs"]) if l["pod"]==name]
        text="\n".join(l["text"] for _,l in logs).lower()
        reasons={c.get("reason","") for c in pod["containers"]}|{c.get("last_reason","") for c in pod["containers"]}
        commands=[f"kubectl get pod {name} -n {namespace} -o wide",f"kubectl describe pod {name} -n {namespace}"]
        if "OOMKilled" in reasons:
            add("oom", "Container terminated by an out-of-memory kill", "critical", "A container reports OOMKilled in its current or previous state. This is evidence of an OOM termination; investigate container limits and node pressure before deciding on new limits.",refs,"Profile memory use and inspect the current requests and limits. Adjust them only after checking node capacity.",commands,"Track memory working set, set realistic requests, and test peak workload memory.")
        elif pod["status"] in {"ImagePullBackOff","ErrImagePull"} or reasons & {"ImagePullBackOff","ErrImagePull"}:
            event_refs=[f"events[{j}]" for j,e in enumerate(evidence["events"]) if e["resource"]==name]
            add("imagepull","Container image cannot be pulled","critical","Kubernetes reports an image pull failure. Pod events distinguish a missing image/tag from registry authentication, rate limits, or connectivity.",refs+event_refs,"Verify the image repository and tag. Inspect registry access and the configured imagePullSecret reference. Update the workload manifest after verifying the cause.",commands,"Validate image tags in CI and use immutable image digests.")
        elif pod["status"]=="CrashLoopBackOff" or "CrashLoopBackOff" in reasons:
            missing="database_url" in text and ("missing" in text or "not set" in text)
            title="Application startup is missing DATABASE_URL" if missing else "Container is repeatedly failing during startup"
            explanation="The startup log explicitly reports a missing DATABASE_URL and the container is in CrashLoopBackOff." if missing else "The container is in CrashLoopBackOff. Its underlying application failure needs confirmation from logs and recent configuration changes."
            add("crashloop",title,"critical",explanation,refs+[f"logs[{j}]" for j,_ in logs],"Add the required environment variable using a Secret reference in your deployment manifest; never paste secret values into a report." if missing else "Inspect current and previous container logs, validate startup configuration, and review the most recent rollout.",commands+[f"kubectl logs {name} -n {namespace} --all-containers=true --previous --tail=80"],"Validate required configuration at startup and exercise it in CI.","high" if missing else "moderate")
        elif pod["status"]=="Pending":
            related=[(j,e) for j,e in enumerate(evidence["events"]) if e["resource"]==name and e["reason"]=="FailedScheduling"]
            add("pending","Pod is waiting to be scheduled" if related else "Pod remains Pending","warning","Scheduler events report: "+"; ".join(e["message"] for _,e in related) if related else "A Pending phase alone does not establish a cause. Check scheduling, storage, and image initialization events.",refs+[f"events[{j}]" for j,_ in related],"Review resource requests, node capacity, taints, affinity rules, and storage claims. Change only the constraint supported by events.",commands,"Capacity-plan resource requests and alert on prolonged Pending states.","high" if related else "moderate")
        elif not pod["ready"] and pod["status"] not in {"Succeeded"}:
            probe_events=[(j,e) for j,e in enumerate(evidence["events"]) if e["resource"]==name and "probe" in e["message"].lower()]
            add("probe" if probe_events else "unready","Health probe is failing" if probe_events else "Pod is not ready","warning","Probe events report: "+"; ".join(e["message"] for _,e in probe_events) if probe_events else "The pod is not Ready. More evidence is required to distinguish initialization, dependency, and application failures.",refs+[f"events[{j}]" for j,_ in probe_events],"Check the probe path, port, timeouts, startup timing, and application dependencies. Do not disable probes to hide a failure.",commands,"Use separate startup, readiness, and liveness checks with realistic thresholds.","high" if probe_events else "moderate")
    for i,service in enumerate(evidence["network"]["services"]):
        selector=service.get("selector",{})
        if not selector or service.get("type")=="ExternalName":
            continue
        matches=[p for p in evidence["pods"] if all(p["labels"].get(k)==v for k,v in selector.items())]
        name=resource_name(service["name"])
        namespace=evidence["pods"][0]["namespace"] if evidence["pods"] else evidence.get("namespace","default")
        resource_name(namespace)
        if not matches and not evidence.get("pods_truncated"):
            add("selector","Service selector matches no collected pods","critical",f"Service {name} selects {json.dumps(selector)}, which matches none of the pods collected in this namespace.",[f"network.services[{i}]","pods"],"Compare workload labels with the Service selector and correct the mismatched key or value in the manifest.",[f"kubectl get svc {name} -n {namespace} -o yaml",f"kubectl get pods -n {namespace} --show-labels"],"Test Service selectors against pod-template labels in CI.")
        elif service.get("endpoint_count")==0 and not findings:
            add("endpoints","Service has no ready endpoints","warning","The service has no ready endpoint addresses. This can result from unready pods or endpoint publication issues.",[f"network.services[{i}]"],"Inspect readiness and EndpointSlices before changing service networking.",[f"kubectl get endpointslices -n {namespace}"],"Monitor endpoint availability and readiness transitions.","moderate")
    for i,deployment in enumerate(evidence["deployments"]):
        if deployment["available"] < deployment["desired"] and not findings:
            add("rollout","Deployment has unavailable replicas","warning","Available replicas are below the desired count. Inspect rollout conditions and pod events.",[f"deployments[{i}]"],"Inspect the rollout and validate its image, scheduling, and health checks.",[f"kubectl describe deployment {resource_name(deployment['name'])} -n {resource_name(deployment['namespace'])}"],"Gate releases on rollout health and watch deployment conditions.","moderate")
    return findings
