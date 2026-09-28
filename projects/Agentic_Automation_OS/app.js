const workflowMeta = {
  "support-triage": { title: "Support Incident Triage", description: "Classify incoming support requests, route by severity, and stop risky actions at a human approval gate.", sample: "Production login is down for enterprise customers and this is urgent. Please escalate it now." },
  "lead-ops": { title: "Lead Qualification Pipeline", description: "Normalize lead intent, score buying signals, route by quality, and prepare a CRM-ready handoff.", sample: "We are an enterprise operations team of 80 people and want a demo plus pricing this week." },
  "content-ops": { title: "Content Operations", description: "Validate a content brief, apply policy checks, require approval when needed, and prepare a publish package.", sample: "Create a technical LinkedIn post explaining a production RAG evaluation workflow with a professional tone and evidence-focused claims." }
};

let currentWorkflow = "support-triage";
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const input = $("#workflowInput");
const runButton = $("#runButton");
const emptyState = $("#emptyState");
const resultState = $("#resultState");
const traceList = $("#traceList");
const historyList = $("#historyList");

function selectWorkflow(id) {
  currentWorkflow = id;
  $$(".workflow-card").forEach((card) => card.classList.toggle("active", card.dataset.workflow === id));
  $("#selectedTitle").textContent = workflowMeta[id].title;
  $("#selectedDescription").textContent = workflowMeta[id].description;
  input.value = workflowMeta[id].sample;
}

$$(".workflow-card").forEach((card) => card.addEventListener("click", () => selectWorkflow(card.dataset.workflow)));
$$(".sample").forEach((button) => button.addEventListener("click", () => { input.value = button.dataset.sample; input.focus(); }));

function getHistory() {
  try { return JSON.parse(localStorage.getItem("automation-os-runs") || "[]"); } catch { return []; }
}

function saveRun(run) {
  const history = getHistory();
  history.unshift({ runId: run.runId, workflowName: run.workflowName, status: run.status, summary: run.summary, at: new Date().toISOString(), duration_ms: run.duration_ms });
  localStorage.setItem("automation-os-runs", JSON.stringify(history.slice(0, 12)));
  renderHistory();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

function renderHistory() {
  const history = getHistory();
  if (!history.length) {
    historyList.innerHTML = '<div class="history-empty">No local run history yet. Your recent demo runs will appear here.</div>';
    return;
  }
  historyList.innerHTML = history.map((item) =>
    '<div class="history-item">' +
      '<strong>' + escapeHtml(item.workflowName) + '</strong>' +
      '<span>' + escapeHtml(item.summary) + '</span>' +
      '<small>' + new Date(item.at).toLocaleString() + '</small>' +
      '<b>' + (item.status === "approval_required" ? "APPROVAL" : "DONE") + '</b>' +
    '</div>'
  ).join("");
}

function renderRun(run) {
  emptyState.classList.add("hidden");
  resultState.classList.remove("hidden");
  $("#runName").textContent = run.workflowName;
  $("#runId").textContent = run.runId + " · " + run.duration_ms + "ms";
  $("#runSummaryText").textContent = run.summary;
  const status = $("#runStatus");
  status.textContent = run.status === "approval_required" ? "APPROVAL REQUIRED" : "COMPLETED";
  status.classList.toggle("approval", run.status === "approval_required");
  traceList.innerHTML = run.logs.map((log, index) =>
    '<div class="trace-step ' + log.status + '">' +
      '<span class="marker">' + String(index + 1).padStart(2, "0") + '</span>' +
      '<div><strong>' + escapeHtml(log.label) + '</strong><small>' + escapeHtml(log.detail) + '</small></div>' +
      '<time>' + log.duration_ms + 'ms</time>' +
    '</div>'
  ).join("");
  $("#payloadOutput").textContent = JSON.stringify(run.output, null, 2);
}

async function runWorkflow() {
  const text = input.value.trim();
  if (text.length < 8) { input.focus(); return; }
  runButton.disabled = true;
  runButton.querySelector("span").textContent = "EXECUTING…";
  try {
    const response = await fetch("/api/automation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow: currentWorkflow, input: text })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Run failed");
    renderRun(data);
    saveRun(data);
  } catch (error) {
    emptyState.classList.add("hidden");
    resultState.classList.remove("hidden");
    $("#runName").textContent = "Execution error";
    $("#runId").textContent = "SERVERLESS ENDPOINT";
    $("#runSummaryText").textContent = error.message + ". If this deployment is still propagating, retry from the production URL.";
    $("#runStatus").textContent = "ERROR";
    $("#runStatus").classList.add("approval");
    traceList.innerHTML = "";
    $("#payloadOutput").textContent = "{}";
  } finally {
    runButton.disabled = false;
    runButton.querySelector("span").textContent = "RUN WORKFLOW";
  }
}

runButton.addEventListener("click", runWorkflow);
document.addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runWorkflow(); });
$("#clearHistory").addEventListener("click", () => { localStorage.removeItem("automation-os-runs"); renderHistory(); });
renderHistory();