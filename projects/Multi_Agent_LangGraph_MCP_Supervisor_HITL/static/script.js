let currentThreadId = localStorage.getItem("tripmate_thread_id") || null;
let latestAnswerMarkdown = "";
let waitingForApproval = false;
let latestData = null;

const AGENTS = [
  { key: "guardrail", label: "Guardrail", type: "control" },
  { key: "supervisor", label: "Supervisor", type: "control" },
  { key: "flight_agent", label: "Flight", type: "specialist" },
  { key: "hotel_agent", label: "Hotel", type: "specialist" },
  { key: "weather_agent", label: "Weather", type: "specialist" },
  { key: "budget_agent", label: "Budget", type: "specialist" },
  { key: "itinerary_agent", label: "Itinerary", type: "specialist" },
  { key: "human_approval", label: "Human review", type: "control" },
  { key: "final_agent", label: "Finalizer", type: "control" }
];

const $ = (id) => document.getElementById(id);

function setHidden(id, hidden) {
  $(id).classList.toggle("hidden", hidden);
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderMarkdown(target, markdown) {
  const text = markdown || "";
  if (typeof marked === "undefined") {
    target.textContent = text;
    return;
  }
  const html = marked.parse(text);
  target.innerHTML = typeof DOMPurify !== "undefined"
    ? DOMPurify.sanitize(html)
    : html;
}

async function loadCapabilities() {
  try {
    const response = await fetch("/api/capabilities", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error("capabilities unavailable");

    $("modeBadge").textContent = data.demo_mode ? "Demo engine" : (data.llm || "Live model");
    $("modeBadge").className = data.demo_mode ? "status-off" : "status-on";
    $("persistenceBadge").textContent = data.persistence === "postgres" ? "PostgreSQL" : "In-memory";
    $("persistenceBadge").className = data.persistence === "postgres" ? "status-on" : "status-off";

    const status = (id, enabled) => {
      $(id).textContent = enabled ? "Configured" : "Fallback ready";
      $(id).className = enabled ? "status-on" : "status-off";
    };
    status("tavilyStatus", data.integrations?.tavily);
    status("aviationStatus", data.integrations?.aviationstack);
    status("weatherStatus", data.integrations?.openweather);
  } catch (_) {
    ["modeBadge", "persistenceBadge", "tavilyStatus", "aviationStatus", "weatherStatus"]
      .forEach((id) => { $(id).textContent = "Available"; });
  }
}

function setBusy(busy) {
  $("sendBtn").disabled = busy || waitingForApproval;
  $("approveBtn").disabled = busy;
  $("reviseBtn").disabled = busy;
  $("btnText").classList.toggle("hidden", busy);
  $("btnLoader").classList.toggle("hidden", !busy);
}

function showError(message) {
  $("errorBox").textContent = message;
  setHidden("errorBox", false);
  $("errorBox").scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideError() {
  setHidden("errorBox", true);
  $("errorBox").textContent = "";
}

function setPrompt(text) {
  $("userInput").value = text;
  $("userInput").focus();
}

function renderAgentRail(data = null, loading = false) {
  const selected = new Set(data?.selected_agents || []);
  const requiresApproval = Boolean(data?.requires_approval);
  const isFinal = data && !requiresApproval && data.guardrail_allowed !== false;
  const blocked = data?.guardrail_allowed === false;

  $("agentRail").innerHTML = AGENTS.map((agent) => {
    let state = "pending";
    let selectedNode = false;

    if (loading) {
      selectedNode = true;
    } else if (data) {
      if (agent.key === "guardrail" || agent.key === "supervisor") {
        state = "done";
        selectedNode = true;
      } else if (agent.type === "specialist") {
        selectedNode = selected.has(agent.key);
        state = selectedNode ? "done" : "pending";
      } else if (agent.key === "human_approval") {
        selectedNode = !blocked;
        state = requiresApproval ? "done" : (isFinal ? "done" : "pending");
      } else if (agent.key === "final_agent") {
        selectedNode = isFinal;
        state = isFinal ? "done" : "pending";
      }
    }

    const classes = ["agent-node", state];
    if (selectedNode) classes.push("selected");

    return `<div class="${classes.join(" ")}">
      <span>${escapeHtml(agent.type)}</span>
      <strong>${escapeHtml(agent.label)}</strong>
    </div>`;
  }).join("");
}

function renderWorkflow(data) {
  latestData = data;
  setHidden("workflowSection", false);

  const guardrail = $("guardrailBadge");
  if (data.guardrail_allowed === false) {
    guardrail.textContent = "Guardrail blocked";
    guardrail.classList.add("blocked");
  } else {
    guardrail.textContent = "Guardrail passed";
    guardrail.classList.remove("blocked");
  }

  $("supervisorReasoning").textContent =
    data.supervisor_reasoning || "Supervisor routing completed.";

  renderAgentRail(data);

  const trace = data.integration_trace || [];
  $("integrationTrace").innerHTML = trace.length
    ? trace.map((item) => `<span class="trace-item"><b>${escapeHtml(item.agent.replace("_agent", ""))}</b> · ${escapeHtml(item.source)}</span>`).join("")
    : '<span class="trace-item">No external tool call was required.</span>';
}

function renderEvidence(data) {
  if (data.guardrail_allowed === false) {
    setHidden("evidenceSection", true);
    return;
  }

  const values = {
    flightEvidence: data.flight_results || "No flight specialist output.",
    hotelEvidence: data.hotel_results || "No hotel specialist output.",
    weatherEvidence: data.weather_results || "No weather specialist output.",
    budgetEvidence: data.budget_results || "No budget specialist output."
  };

  Object.entries(values).forEach(([id, value]) => {
    $(id).textContent = String(value);
  });
  setHidden("evidenceSection", false);
}

function showResult(data, isDraft) {
  latestAnswerMarkdown = data.answer || data.itinerary || "";
  $("resultTitle").textContent = isDraft ? "Draft itinerary for your review" : "Your final TripMate plan";
  $("resultKicker").textContent = isDraft ? "DRAFT · HUMAN REVIEW REQUIRED" : "FINAL · REVIEW COMPLETE";
  $("threadInfo").textContent = `Session ${data.thread_id.slice(0, 18)}… · ${data.llm_calls || 0} model calls`;
  renderMarkdown($("resultBox"), latestAnswerMarkdown);
  setHidden("resultSection", false);
}

function showApproval(data) {
  waitingForApproval = true;
  $("approvalRequest").textContent = data.approval_request ||
    "Review the draft, then approve it or request a revision.";
  setHidden("approvalSection", false);
  $("sendBtn").disabled = true;
}

function hideApproval() {
  waitingForApproval = false;
  setHidden("approvalSection", true);
  $("approvalFeedback").value = "";
  $("sendBtn").disabled = false;
}

async function sendMessage() {
  hideError();

  if (waitingForApproval) {
    showError("Review the current draft before starting another plan.");
    return;
  }

  const message = $("userInput").value.trim();
  if (!message) {
    showError("Describe the trip you want TripMate to plan.");
    return;
  }

  setHidden("workflowSection", false);
  $("guardrailBadge").textContent = "Guardrail checking";
  $("guardrailBadge").classList.remove("blocked");
  $("supervisorReasoning").textContent = "The supervisor is assembling the specialist workflow…";
  $("integrationTrace").innerHTML = '<span class="trace-item">Waiting for tool results…</span>';
  renderAgentRail(null, true);
  setBusy(true);

  try {
    const response = await fetch("/api/travel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, thread_id: currentThreadId })
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || data.detail || "TripMate could not create the plan.");
    }

    currentThreadId = data.thread_id;
    localStorage.setItem("tripmate_thread_id", currentThreadId);

    renderWorkflow(data);
    renderEvidence(data);

    if (data.requires_approval) {
      showResult(data, true);
      showApproval(data);
    } else {
      hideApproval();
      showResult(data, false);
    }

    $("workflowSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    renderAgentRail();
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function submitApproval(approved) {
  hideError();
  if (!currentThreadId || !waitingForApproval) {
    showError("No draft is waiting for review.");
    return;
  }

  const feedback = $("approvalFeedback").value.trim();
  if (!approved && !feedback) {
    showError("Add revision feedback before requesting changes.");
    $("approvalFeedback").focus();
    return;
  }

  setBusy(true);
  try {
    const response = await fetch("/api/travel/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: currentThreadId,
        approved,
        feedback
      })
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || data.detail || "TripMate could not resume the workflow.");
    }

    hideApproval();
    renderWorkflow(data);
    renderEvidence(data);
    showResult(data, false);
    $("resultSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

function newPlan() {
  currentThreadId = null;
  latestAnswerMarkdown = "";
  latestData = null;
  waitingForApproval = false;
  localStorage.removeItem("tripmate_thread_id");
  $("userInput").value = "";
  $("approvalFeedback").value = "";
  ["workflowSection", "evidenceSection", "approvalSection", "resultSection", "errorBox"]
    .forEach((id) => setHidden(id, true));
  $("sendBtn").disabled = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
  setTimeout(() => $("userInput").focus(), 350);
}

async function copyResult() {
  const text = $("resultBox").innerText.trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const button = document.querySelector(".copy-btn");
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = original; }, 1400);
  } catch (_) {
    showError("Copy is unavailable in this browser.");
  }
}

function downloadPDF() {
  if (!latestAnswerMarkdown || typeof html2pdf === "undefined") {
    showError("There is no travel plan ready to export.");
    return;
  }

  const button = document.querySelector(".download-btn");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Preparing…";

  html2pdf()
    .set({
      margin: 0.45,
      filename: "tripmate-ai-travel-plan.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
      jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
      pagebreak: { mode: ["css", "legacy"] }
    })
    .from($("pdfContent"))
    .save()
    .catch(() => showError("PDF export failed. Try the browser print option instead."))
    .finally(() => {
      button.disabled = false;
      button.textContent = original;
    });
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => setPrompt(button.dataset.prompt));
});

document.querySelectorAll("[data-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = $(button.dataset.toggle);
    const opening = target.classList.contains("hidden");
    target.classList.toggle("hidden");
    button.textContent = opening ? "Hide" : "View";
  });
});

$("sendBtn").addEventListener("click", sendMessage);
$("approveBtn").addEventListener("click", () => submitApproval(true));
$("reviseBtn").addEventListener("click", () => submitApproval(false));
$("newPlanBtn").addEventListener("click", newPlan);
document.querySelector(".copy-btn").addEventListener("click", copyResult);
document.querySelector(".download-btn").addEventListener("click", downloadPDF);

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    sendMessage();
  }
});

renderAgentRail();
loadCapabilities();
