# Rishabh Shukla — AI & GenAI Portfolio

Personal portfolio, hosted at https://my-portfolio-website-topaz-beta.vercel.app/.

A dependency-free static site using HTML, CSS, and JavaScript. No build step is required.

## Featured AI systems

- **Enterprise Agentic RAG** — retrieval, reranking, guardrails, hosted evaluation, FastAPI and Qdrant.
- **Multi-Agent Market Analyst** — LangGraph specialist agents with human approval.
- **Multi-Agent Travel Planner** — tool-using agents, MCP integrations and persistent workflow state.
- **Secure Clinical EHR Insight Validator** — synthetic patient-scoped retrieval with safety guardrails, identifier redaction, citations and grounding validation. Live at https://secure-clinical-ehr-validator.onrender.com.

The clinical project source lives at `projects/Secure_Clinical_EHR_Validator/` and includes its own README, tests, evaluation suite, attribution, Dockerfile and Render configuration.

## Local preview

Run `python -m http.server 4173` in this directory and open `http://localhost:4173`.

## Content and interaction

- Four project cards open accessible native dialogs with project details, source links, hosted demos, and illustrative workflow walkthroughs.
- Resume buttons open a preview or download `Rishabh_Shukla_Resume.pdf`. The legacy filename, `Rishabh Shukla Resume.pdf`, contains the same PDF so previously shared links keep working.
- The resume preview image is a rendering of the PDF, not a separately authored document.
- The contact dialog provides email, phone, and resume shortcuts. Copy actions report success only after the clipboard operation succeeds.
- Ctrl/Cmd+K opens searchable quick navigation. Arrow keys, Enter, Escape, and ordinary Tab navigation work.
- A dismissible recruiter shortcut appears after the visitor explores the page; dismissal is remembered for the tab session.
- Animations honor `prefers-reduced-motion`. Content remains visible if JavaScript or IntersectionObserver is unavailable.
- The hero uses one existing portrait frame. The original frame archive is retained in the repository but is no longer preloaded by the website.

## Updating

Edit page content in `index.html`, interaction data in `script.js`, and presentation in `style.css`. Replace both resume PDFs with identical bytes when updating, re-render `assets/resume-preview.jpg`, and update the version query on resume links.

GitHub's `main` branch is connected to the existing Vercel production project. Feature branches create preview deployments through that connection.

The walkthroughs are clearly labeled examples; they do not run live agents or present measured evaluation scores. Hosted apps are separate services and may take time to start.
