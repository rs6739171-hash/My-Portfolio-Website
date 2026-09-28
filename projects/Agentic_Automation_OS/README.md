# Agentic Automation OS

A portfolio-grade workflow automation control plane built for a **$0 required infrastructure cost** demo.

It combines patterns seen in modern automation/orchestration systems — event-driven execution, graph-style routing, policy gates, human-in-the-loop approval, run observability, and connector-ready actions — without requiring a paid queue, database, automation SaaS subscription, or LLM API key.

## Why this project

The architecture was informed by strong open-source automation patterns found across:

- **triggerdotdev/trigger.dev** — durable background-job and event-driven workflow patterns.
- **bytechefhq/bytechef** — workflow orchestration, integrations, and visual automation concepts.
- **lucaswalter/n8n-ai-automations** and the wider n8n template ecosystem — practical business automation use cases.
- **LangGraph-style agent graphs** — stateful routing, approval gates, and explicit workflow transitions.

This repository contains an **original implementation** built specifically for this portfolio; it does not copy those projects' source code.

## Live architecture

~~~text
UI / Event
   |
   v
Vercel Serverless API
   |
   +-- Normalize trigger
   +-- Classify / score / inspect
   +-- Dynamic router
   +-- Policy + risk gate
   +-- Human approval boundary
   +-- Action payload builder
   +-- Audit trace
           |
           v
Browser run history (localStorage)
~~~

## Included workflows

1. **Support Incident Triage** — request → severity classification → routing → risk gate → human approval for P1 → action package → audit.
2. **Lead Qualification Pipeline** — lead → normalization → intent scoring → revenue route → CRM-ready handoff → audit.
3. **Content Operations** — brief → completeness check → policy gate → approval when needed → publish package → audit.

## Free-tier decisions

| Production component | Free demo alternative |
|---|---|
| Worker / workflow runtime | Vercel Functions |
| Redis / queue | Per-request synchronous orchestration |
| Postgres run store | Browser localStorage |
| Paid LLM | Deterministic planner/router fallback |
| SaaS automation UI | Custom control center |
| Observability vendor | Structured execution trace |

These choices keep the project deployable and interactive with no mandatory billing setup.

## API

**Health:** GET /api/automation-health

**Execute:** POST /api/automation

~~~json
{
  "workflow": "support-triage",
  "input": "Production login is down for enterprise users."
}
~~~

Every run returns a run ID, workflow status, approval state, output payload, step-by-step trace, per-step timing, and total execution time.

## Reliability and safety

- Explicit workflow states instead of opaque one-shot prompting.
- High-risk branches pause before external action.
- Dependency-free serverless runtime.
- No secrets embedded in the client.
- No paid external services required by default.
- User input length is bounded before execution.
- The demo prepares connector payloads but intentionally does not dispatch arbitrary user-provided URLs.

## Production upgrade path

1. Add a durable queue such as Upstash/QStash or Trigger.dev.
2. Persist run state in Neon/Supabase/Postgres.
3. Replace deterministic planner steps with an LLM only where reasoning adds value.
4. Add real connectors for Gmail, Slack, GitHub, Notion, CRM, or internal APIs.
5. Add webhook signatures, idempotency keys, retries, dead-letter handling, RBAC, and encrypted secrets.
6. Add OpenTelemetry traces and workflow-level SLOs.

## Author

Rishabh Shukla — AI & GenAI Engineer
