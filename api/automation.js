const crypto = require("crypto");

const WORKFLOWS = {
  "support-triage": {
    name: "Support Incident Triage",
    description: "Classify, route, gate risky actions, and produce an auditable incident record."
  },
  "lead-ops": {
    name: "Lead Qualification Pipeline",
    description: "Normalize a lead, score intent, route by quality, and prepare a CRM-ready handoff."
  },
  "content-ops": {
    name: "Content Operations",
    description: "Validate a brief, apply policy checks, request approval when needed, and prepare a publish package."
  }
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeInput(value) {
  return String(value || "").trim().replace(/\s+/g, " ").slice(0, 1600);
}

function classifySupport(input) {
  const t = input.toLowerCase();
  const urgent = /(down|outage|breach|security|payment failed|cannot login|critical|urgent|production)/.test(t);
  const billing = /(invoice|billing|refund|payment|charge)/.test(t);
  const category = billing ? "billing" : urgent ? "incident" : "general";
  const severity = /(breach|security|outage|production down|critical)/.test(t) ? "P1" : urgent ? "P2" : "P3";
  return { category, severity, confidence: urgent || billing ? 0.92 : 0.78 };
}

function scoreLead(input) {
  const t = input.toLowerCase();
  let score = 38;
  if (/(demo|pricing|quote|budget|proposal)/.test(t)) score += 24;
  if (/(enterprise|team|company|organization)/.test(t)) score += 18;
  if (/(this week|today|urgent|asap)/.test(t)) score += 10;
  if (/(student|just exploring|learning)/.test(t)) score -= 12;
  score = Math.max(5, Math.min(98, score));
  return { score, segment: score >= 75 ? "hot" : score >= 55 ? "warm" : "nurture" };
}

function inspectContent(input) {
  const t = input.toLowerCase();
  const risky = /(guaranteed returns|medical diagnosis|password|secret key|private data)/.test(t);
  const missing = input.length < 45;
  return {
    policyRisk: risky ? "high" : "low",
    briefQuality: missing ? "needs-context" : "ready",
    requiresApproval: risky || missing
  };
}

function step(id, label, status, detail, ms) {
  return { id, label, status, detail, duration_ms: ms };
}

async function executeWorkflow(workflow, input) {
  const runId = "run_" + crypto.randomBytes(6).toString("hex");
  const started = Date.now();
  const logs = [];

  logs.push(step("trigger", "Trigger received", "success", "Request normalized and assigned " + runId, 8));
  await sleep(20);

  if (workflow === "support-triage") {
    const triage = classifySupport(input);
    logs.push(step("classify", "Intent & severity classifier", "success", `Detected ${triage.category} / ${triage.severity} with ${Math.round(triage.confidence*100)}% confidence`, 34));
    logs.push(step("route", "Dynamic router", "success", `Routed to ${triage.category === "billing" ? "Billing Ops" : triage.severity === "P1" ? "Incident Commander" : "Support Queue"}`, 12));
    const approval = triage.severity === "P1";
    logs.push(step("guardrail", "Risk policy gate", approval ? "waiting" : "success", approval ? "P1 incidents require human approval before external action." : "No elevated approval required.", 7));
    logs.push(step("action", "Action executor", approval ? "paused" : "success", approval ? "Prepared escalation package; external dispatch intentionally paused." : "Created queue item and response draft.", 18));
    logs.push(step("audit", "Audit event", "success", "Immutable-style execution record generated for the demo run.", 5));
    return {
      runId,
      workflow,
      workflowName: WORKFLOWS[workflow].name,
      status: approval ? "approval_required" : "completed",
      summary: approval
        ? `Detected a ${triage.severity} ${triage.category} issue. The workflow stopped at the approval gate before taking an external action.`
        : `Detected a ${triage.severity} ${triage.category} request and routed it automatically.`,
      output: { triage, destination: triage.category === "billing" ? "Billing Ops" : triage.severity === "P1" ? "Incident Commander" : "Support Queue" },
      logs,
      duration_ms: Date.now() - started
    };
  }

  if (workflow === "lead-ops") {
    const lead = scoreLead(input);
    logs.push(step("normalize", "Lead normalizer", "success", "Contact intent and buying signals extracted from free text.", 21));
    logs.push(step("score", "Qualification scorer", "success", `Lead score ${lead.score}/100 → ${lead.segment.toUpperCase()}`, 26));
    logs.push(step("route", "Revenue router", "success", `Assigned to ${lead.segment === "hot" ? "Sales Fast Lane" : lead.segment === "warm" ? "SDR Follow-up" : "Nurture Sequence"}`, 9));
    logs.push(step("action", "CRM handoff builder", "success", "Prepared normalized CRM payload and next-action recommendation.", 16));
    logs.push(step("audit", "Audit event", "success", "Scoring factors and route stored in the run result.", 6));
    return {
      runId,
      workflow,
      workflowName: WORKFLOWS[workflow].name,
      status: "completed",
      summary: `Lead scored ${lead.score}/100 and was routed to the ${lead.segment} path.`,
      output: { lead, nextAction: lead.segment === "hot" ? "Book demo within 1 business day" : lead.segment === "warm" ? "Personalized follow-up" : "Automated nurture" },
      logs,
      duration_ms: Date.now() - started
    };
  }

  const content = inspectContent(input);
  logs.push(step("brief", "Brief parser", "success", "Objective, constraints, and action intent extracted.", 20));
  logs.push(step("policy", "Policy & quality gate", content.requiresApproval ? "waiting" : "success", content.requiresApproval ? "Human review required before publish preparation." : "Brief passed policy and completeness checks.", 14));
  logs.push(step("compose", "Publish package builder", content.requiresApproval ? "paused" : "success", content.requiresApproval ? "Package held until approval." : "Generated channel checklist, metadata, and publication payload.", 24));
  logs.push(step("audit", "Audit event", "success", "Policy decision and execution trace recorded.", 5));
  return {
    runId,
    workflow,
    workflowName: WORKFLOWS[workflow].name,
    status: content.requiresApproval ? "approval_required" : "completed",
    summary: content.requiresApproval ? "The workflow found a policy or completeness issue and paused for human approval." : "The content brief passed checks and a publish-ready package was prepared.",
    output: content,
    logs,
    duration_ms: Date.now() - started
  };
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(204).end();

  if (req.method === "GET") {
    return res.status(200).json({
      service: "Agentic Automation OS",
      status: "ok",
      runtime: "Vercel Serverless",
      workflows: WORKFLOWS
    });
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const workflow = String(req.body?.workflow || "");
    const input = normalizeInput(req.body?.input);
    if (!WORKFLOWS[workflow]) return res.status(400).json({ error: "Unknown workflow" });
    if (input.length < 8) return res.status(400).json({ error: "Please provide a little more context for the workflow." });

    const result = await executeWorkflow(workflow, input);
    return res.status(200).json(result);
  } catch (error) {
    return res.status(500).json({ error: "Automation execution failed", detail: error.message });
  }
};