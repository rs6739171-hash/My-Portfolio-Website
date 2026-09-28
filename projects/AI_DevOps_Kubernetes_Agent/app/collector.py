"""Read-only, namespace-scoped kubectl collection. No shell or write commands."""
import json
import os
import subprocess
from .security import resource_name, redact

class CollectionError(Exception):
    pass

class Collector:
    def __init__(self, kubeconfig: str, context: str = "", namespace: str = "default", binary: str = "kubectl"):
        self.kubeconfig=kubeconfig
        self.context=context
        self.namespace=resource_name(namespace)
        self.binary=binary
        self.warnings=[]

    def run(self, args: list[str]) -> str:
        if args[:2] != ["config","get-contexts"] and args[0] not in {"get","logs"}:
            raise CollectionError("Only read-only commands are allowed.")
        command=[self.binary,"--request-timeout=8s",f"--kubeconfig={self.kubeconfig}"]
        if self.context:
            command.append(f"--context={self.context}")
        command+=args
        try:
            completed=subprocess.run(command,capture_output=True,text=True,timeout=12,check=False,shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CollectionError("kubectl is unavailable or the cluster request timed out.") from exc
        if completed.returncode:
            raise CollectionError("The Kubernetes request failed. Verify reachability, context, and read-only RBAC permissions.")
        if len(completed.stdout)>4_000_000:
            raise CollectionError("Kubernetes response is too large. Select a smaller namespace.")
        return completed.stdout

    def contexts(self) -> list[str]:
        return [x for x in self.run(["config","get-contexts","-o","name"]).splitlines() if x.strip()]

    def get(self, resource: str) -> list[dict]:
        if resource not in {"pods","events","deployments","services","endpointslices"}:
            raise CollectionError("Resource collection is not permitted.")
        try:
            return json.loads(self.run(["get",resource,"-n",self.namespace,"-o","json"]))["items"]
        except (json.JSONDecodeError,KeyError) as exc:
            raise CollectionError("Cluster returned an invalid resource response.") from exc

    def pods(self) -> list[dict]:
        result=[]
        all_pods=self.get("pods")
        if len(all_pods)>100:
            raise CollectionError("Namespace contains more than 100 pods. Use a smaller investigation namespace.")
        for p in all_pods:
            states=p.get("status",{}).get("initContainerStatuses",[])+p.get("status",{}).get("containerStatuses",[])
            specs=p.get("spec",{}).get("initContainers",[])+p.get("spec",{}).get("containers",[])
            containers=[]
            status=p.get("status",{}).get("phase","Unknown")
            for c in states:
                state=c.get("state",{})
                reason=state.get("waiting",{}).get("reason") or state.get("terminated",{}).get("reason","")
                if reason and reason not in {"Completed"}: status=reason
                spec=next((s for s in specs if s["name"]==c["name"]),{})
                containers.append({"name":c["name"],"image":c.get("image",""),"reason":reason,"last_reason":c.get("lastState",{}).get("terminated",{}).get("reason",""),"memory_limit":spec.get("resources",{}).get("limits",{}).get("memory","unset")})
            result.append({"name":p["metadata"]["name"],"namespace":self.namespace,"labels":p["metadata"].get("labels",{}),"status":status,"ready":any(c.get("type")=="Ready" and c.get("status")=="True" for c in p.get("status",{}).get("conditions",[])),"restarts":sum(c.get("restartCount",0) for c in states),"containers":containers})
        return redact(result)

    def logs(self,pods) -> list[dict]:
        result=[]
        targets=[p for p in pods if not p["ready"] and p["status"]!="Succeeded"]
        if len(targets)>3: self.warnings.append("Logs sampled from three unhealthy pods; additional pods were not read.")
        for p in targets[:3]:
            for c in p["containers"][:2]:
                if c["reason"] in {"ImagePullBackOff","ErrImagePull","ContainerCreating"}: continue
                previous=bool(c["last_reason"] or p["restarts"])
                args=["logs",resource_name(p["name"]),"-n",self.namespace,"-c",resource_name(c["name"]),"--tail=60","--limit-bytes=6000"]
                if previous: args.append("--previous=true")
                try:
                    output=self.run(args)
                except CollectionError:
                    self.warnings.append(f"Logs unavailable for {p['name']}/{c['name']}.")
                    continue
                result.append({"pod":p["name"],"container":c["name"],"previous":previous,"text":redact(output)})
        return result

    def events(self):
        events=self.get("events")
        events.sort(key=lambda e:e.get("lastTimestamp") or e.get("eventTime") or e.get("metadata",{}).get("creationTimestamp") or "",reverse=True)
        if len(events)>100: self.warnings.append("Only the 100 most recent namespace events were included.")
        return redact([{"reason":e.get("reason",""),"message":e.get("message","")[:2000],"resource":e.get("involvedObject",{}).get("name","")} for e in events[:100]])

    def deployments(self):
        return [{"name":d["metadata"]["name"],"namespace":self.namespace,"desired":d.get("spec",{}).get("replicas",1),"available":d.get("status",{}).get("availableReplicas",0),"conditions":[{"type":c["type"],"status":c["status"],"reason":c.get("reason","")} for c in d.get("status",{}).get("conditions",[])]} for d in self.get("deployments")]

    def network(self):
        services=self.get("services")
        try:
            slices=self.get("endpointslices")
        except CollectionError:
            slices=None
            self.warnings.append("EndpointSlices could not be read; endpoint availability is unknown.")
        result=[]
        for s in services:
            endpoints=None if slices is None else sum(1 for sl in slices if sl.get("metadata",{}).get("labels",{}).get("kubernetes.io/service-name")==s["metadata"]["name"] for e in sl.get("endpoints",[]) if e.get("conditions",{}).get("ready") is not False for _ in e.get("addresses",[]))
            result.append({"name":s["metadata"]["name"],"selector":s.get("spec",{}).get("selector",{}),"type":s.get("spec",{}).get("type","ClusterIP"),"endpoint_count":endpoints})
        return {"services":result}
