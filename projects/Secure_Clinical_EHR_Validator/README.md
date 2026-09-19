# Secure Clinical EHR Insight Validator

**FastAPI · Streamlit · scoped RAG · safety guardrails · PHI redaction · grounding validation · optional LLM**

A portfolio-grade clinical information retrieval demo by **Rishabh Shukla**.

**Live demo:** https://secure-clinical-ehr-validator.onrender.com

**Verified:** 9/9 deterministic retrieval-and-safety evaluation cases pass in the project test suite. It demonstrates how an AI application can retrieve evidence from a selected synthetic patient record while enforcing patient scope, blocking diagnosis/treatment requests, redacting identifiers before optional external LLM calls, and validating generated answers against retrieved evidence.

> **Safety boundary:** This repository uses synthetic records only. It is not a medical device, not HIPAA-certified, and must not be used for diagnosis, treatment, or real patient care.

## Recruiter quick scan

- **Secure RAG workflow:** patient-scoped retrieval → deterministic safety gate → context redaction → optional LLM → grounding validator.
- **Fail-safe behavior:** medical-advice, prompt-injection and cross-patient exfiltration requests are blocked before generation.
- **Evidence-first answers:** responses expose encounter citations, retrieval scores, grounding scores and validator flags.
- **Deployment-friendly:** no paid API is required; an OpenAI-compatible provider can be enabled with environment variables.
- **Engineering proof:** FastAPI API, Streamlit UI, automated tests, evaluation cases, CI, Docker and Render blueprint.

## Architecture

~~~text
User question
    │
    ▼
Patient-scope validation
    │
    ▼
Deterministic safety gate ─── blocked ──► safe refusal
    │
    ▼
Scoped TF-IDF retrieval over synthetic EHR encounters
    │
    ▼
Identifier redaction
    │
    ├── no LLM key ─► evidence-first extractive answer
    │
    └── LLM configured ─► OpenAI-compatible generation
                              │
                              ▼
                       grounding validator
                              │
                              ▼
                     answer + citations + evidence
~~~

## What is implemented

- Synthetic patient dataset with encounter, medication, lab and diagnosis fields.
- Explicit patient scoping: retrieval never searches outside the selected demo patient.
- Deterministic guards for medical advice, prompt injection and cross-patient enumeration.
- Identifier redaction before any optional external LLM call.
- Lightweight TF-IDF retrieval implemented without a large local model, keeping deployment memory low.
- Optional OpenAI-compatible LLM support through `LLM_API_BASE`, `LLM_API_KEY` and `LLM_MODEL`.
- Grounding validation that checks generated claims against retrieved evidence and falls back to extractive output if support is weak.
- FastAPI `/health`, `/api/v1/patients` and `/api/v1/query` endpoints.
- Streamlit interface with evidence, safety decision, mode and grounding metrics.
- Unit tests, evaluation script, GitHub Actions, Dockerfile and Render deployment blueprint.

## Local run

~~~bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python serve.py
~~~

Open the Streamlit URL shown in the terminal. FastAPI stays on `127.0.0.1:8000`.

## Optional LLM mode

The app is fully functional without an API key. To enable an OpenAI-compatible provider:

~~~env
LLM_API_KEY=your-key
LLM_API_BASE=https://provider.example.com/openai/v1
LLM_MODEL=your-model-name
~~~

No real patient identifier is intentionally sent to the optional LLM provider.

## Verification

~~~bash
python -m unittest discover -s tests -v
python -m evals.run_eval
python -m compileall -q app evals serve.py
~~~

## Deployment

`render.yaml` defines one lightweight Python web service. `serve.py` supervises FastAPI privately on loopback and Streamlit publicly on Render's `PORT`. `APP_PASSWORD` can protect the demo without exposing an API key to visitors.

## Provenance

This implementation was independently written after reviewing a public architecture reference. See [ATTRIBUTION.md](ATTRIBUTION.md). The reference repository had no visible license file when reviewed, so its source, bundled dataset, instructor credentials, and binary files were not copied here.
