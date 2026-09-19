'use strict';
(() => {
  // Existing hosted-demo destinations are retained from the previous portfolio.
  const demoLinks = {"rag": "https://enterprise-rag-rishabh.onrender.com/?password=HeZ7xzyq-lznN5r4vpZpj-HfwhrYqh-UzIcMzI_6lbg#HeZ7xzyq-lznN5r4vpZpj-HfwhrYqh-UzIcMzI_6lbg", "market": "https://market-analyst-rishabh.onrender.com/?password=mSRmkjXOEDKriIO16inihuOCiBjHycKCzT_zBt9300w#mSRmkjXOEDKriIO16inihuOCiBjHycKCzT_zBt9300w", "travel": "https://travel-planner-rishabh.onrender.com/?password=gpKaoEIKA_plNs9L5zj4-n8zqdY-IlIkDLs4u3ZcHEU#gpKaoEIKA_plNs9L5zj4-n8zqdY-IlIkDLs4u3ZcHEU", "clinical": "https://secure-clinical-ehr-validator.onrender.com", "credit": "https://explainable-credit-risk-shap.onrender.com"};
  const projects = {
    rag: {
      title: 'Enterprise Agentic RAG', kicker: '01 / KNOWLEDGE SYSTEMS',
      description: 'A deployed document question-answering system combining LangGraph routing, semantic retrieval, reranking, guardrails, and a dedicated evaluation application.',
      tags: ['LangGraph', 'Qdrant', 'Gemini Embeddings', 'FlashRank', 'Portkey', 'RAGAS'],
      repository: 'Enterprise_Agentic_RAG',
      features: ['Planner, Retriever, and Responder agents with conditional routing and conversation memory.', 'Gemini Embeddings and Qdrant Cloud for semantic retrieval, with FlashRank cross-encoder reranking.', 'NeMo Guardrails for input checks and Portkey for LLM gateway routing.', 'A hosted evaluation app measures four quality rubrics, routing, latency, and six safety cases; optional local RAGAS scoring is also supported.'],
      workflow: ['Question & conversation', 'Safety checks', 'Plan & retrieve context', 'Rerank evidence', 'Generate & evaluate'],
      steps: ['A question arrives with the conversation history. The planner determines which information is needed.', 'The safety gate checks the request before the retrieval and response stages.', 'The retriever searches the document collection in Qdrant using semantic embeddings.', 'FlashRank reorders candidate passages so the response receives the most relevant context.', 'The responder generates an answer from the selected context. The evaluation pipeline can assess answer and retrieval quality.']
    },
    market: {
      title: 'Multi-Agent Market Analyst', kicker: '02 / MULTI-AGENT RESEARCH',
      description: 'An equity research application where specialist agents examine financial data and price indicators, then produce a structured memo after human review.',
      tags: ['LangGraph', 'Python', 'FastAPI', 'Streamlit', 'yfinance', 'Human-in-the-loop'],
      repository: 'Market_Analyst_Agent',
      features: ['Fundamental Analyst, Technical Analyst, and Portfolio Manager agents coordinate through LangGraph.', 'A yfinance and Pandas pipeline processes valuation, profitability, price, volume, SMA-20, SMA-50, and RSI data.', 'The workflow pauses for explicit human approval before the final investment memo.', 'A FastAPI backend and Streamlit frontend use checkpoint-based session state, input validation, and regression checks.'],
      workflow: ['Select a ticker', 'Analyze fundamentals', 'Analyze technicals', 'Human approval', 'Synthesize memo'],
      steps: ['The user provides a stock ticker. Input validation runs before the data pipeline.', 'The Fundamental Analyst works with valuation and profitability information collected through yfinance.', 'The Technical Analyst examines price, volume, moving averages, and RSI indicators.', 'The graph pauses for a person to review the research. The next step illustrates approval; it does not execute any trade.', 'After approval, the Portfolio Manager synthesizes the analyses into a research memo. This example does not provide current market data or an investment recommendation.'],
      approval: 3
    },
    travel: {
      title: 'Multi-Agent Travel Planner', kicker: '03 / TOOL-USING AGENTS',
      description: 'A travel planning workflow that routes one request to specialist agents, combines their findings, and lets the user revise or approve the itinerary.',
      tags: ['LangGraph', 'MCP', 'PostgreSQL', 'Streamlit', 'Tavily', 'OpenWeather'],
      repository: 'Travel_Planner_System',
      features: ['A Supervisor routes work to Flight, Hotel, Weather, Budget, and Itinerary agents.', 'Tavily MCP, OpenWeather, and AviationStack enrich hotel research, weather, and flight-status information.', 'Input validation runs before external tools; human review allows approval or itinerary revisions.', 'PostgreSQL-backed checkpoints preserve resumable sessions, with an in-memory option for local development.'],
      workflow: ['Trip request & validation', 'Route specialist tasks', 'Combine research & budget', 'Review or revise', 'Finalize itinerary'],
      steps: ['A destination, duration, and budget form the trip request. Guardrails validate it before tool calls.', 'The supervisor routes relevant work to the flight, hotel, weather, and budget specialists.', 'The itinerary agent combines the research and budget constraints into a proposed plan.', 'The user reviews the itinerary and can request changes. Choose approval below to continue this illustrative walkthrough.', 'The approved itinerary is finalized. Checkpointing lets a session resume later; the planner does not book flights or hotels.'],
      approval: 3
    },
    clinical: {
      title: 'Secure Clinical EHR Insight Validator', kicker: '04 / AI SAFETY & HEALTHCARE',
      description: 'A deployed synthetic clinical-record retrieval application with explicit patient scoping, deterministic safety guardrails, identifier redaction, evidence citations, and grounding validation.',
      tags: ['Mistral Small', 'FastAPI', 'Streamlit', 'Scoped RAG', 'Safety Guardrails', 'Grounding Validation'],
      sourceUrl: 'https://github.com/rs6739171-hash/My-Portfolio-Website/tree/main/projects/Secure_Clinical_EHR_Validator',
      features: ['Patient-scoped retrieval ensures a query only searches the selected synthetic record.', 'Deterministic safety checks block treatment advice, prompt injection, and cross-patient data-exfiltration requests before generation.', 'Identifiers are redacted before Mistral Small generation; provider credentials stay in Render secrets and extractive fallback keeps the app functional if generation is unavailable.', 'Every successful answer exposes retrieved evidence, encounter citations, retrieval scores, and a grounding score. Automated tests and a nine-case evaluation suite are included.'],
      workflow: ['Select synthetic patient', 'Classify request safety', 'Retrieve scoped evidence', 'Redact external context', 'Generate & validate grounding'],
      steps: ['The visitor selects one synthetic demo patient; the retrieval boundary is fixed to that patient.', 'A deterministic gate classifies medical-advice, prompt-injection, and cross-patient exfiltration requests before retrieval or generation.', 'A lightweight retrieval layer ranks encounters only inside the selected patient record and returns evidence with encounter IDs.', 'Common identifiers are redacted before context can be sent to an optional external LLM. Without an API key, evidence-first extractive mode remains fully functional.', 'The grounding validator checks the response against retrieved evidence. Low-support LLM output falls back to an extractive answer with citations.']
    },
    credit: {
      title: 'Explainable Credit Risk with SHAP', kicker: '05 / EXPLAINABLE MACHINE LEARNING',
      description: 'A deployed explainable-ML application that trains on generated synthetic credit data, estimates default probability, exposes field-level SHAP reason codes, reports holdout metrics, and supports what-if scenario analysis.',
      tags: ['SHAP', 'scikit-learn', 'Logistic Regression', 'FastAPI', 'Streamlit', 'Model Evaluation'],
      sourceUrl: 'https://github.com/rs6739171-hash/My-Portfolio-Website/tree/main/projects/Explainable_Credit_Risk_SHAP',
      features: ['A deterministic synthetic-data generator creates training data during the build; no borrower dataset or binary model is copied into the repository.', 'A scikit-learn preprocessing pipeline handles numeric scaling and categorical one-hot encoding before a balanced logistic-risk model.', 'SHAP LinearExplainer produces per-feature contributions that are aggregated back to business-facing input fields and labeled by direction.', 'The application exposes ROC-AUC, PR-AUC, precision, recall, F1, Brier score, selected threshold, and a what-if scenario endpoint.'],
      workflow: ['Generate & split synthetic data', 'Preprocess features', 'Train & select threshold', 'Score application', 'Explain with SHAP & compare scenarios'],
      steps: ['A seeded generator creates synthetic credit applications and labels for a reproducible portfolio experiment.', 'Numeric features are standardized while categorical features are one-hot encoded using a fitted ColumnTransformer.', 'A balanced logistic regression model is trained and the review threshold is selected on the holdout split using F1.', 'FastAPI returns the estimated probability, risk tier, threshold comparison, and model metadata for a validated application.', 'SHAP contributions are aggregated to the original business fields. The UI can then compare a modified scenario against the baseline without claiming causality.']
    }
  };
  const skills = {
    agents: {title: 'Agents that collaborate.', description: 'I use explicit graph state and specialist roles to make multi-agent workflows easier to follow and control.', examples: ['LangGraph coordinates the Fundamental Analyst, Technical Analyst, and Portfolio Manager in the Market Analyst.', 'The Travel Planner supervisor routes tasks to specialist agents and exposes a human review step.', 'MCP connects external research tools to the travel workflow.'], project: 'market'},
    retrieval: {title: 'Answers with context.', description: 'The retrieval pipeline connects a user question to relevant document passages before generating an answer.', examples: ['Gemini Embeddings represent queries and documents for semantic search.', 'Qdrant stores and retrieves vectors; FlashRank reranks the candidate passages.', 'Planner, Retriever, and Responder agents coordinate the RAG workflow.'], project: 'rag'},
    reliability: {title: 'Trust, then verify.', description: 'Quality checks belong inside an AI application, alongside the features a user sees.', examples: ['NeMo Guardrails checks RAG inputs for off-topic or unsafe requests.', 'The clinical validator blocks treatment advice, prompt injection, and cross-patient exfiltration before generation.', 'RAGAS, grounding checks, model metrics, SHAP explanations, LangSmith and Logfire make quality and failure modes visible.'], project: 'credit'},
    delivery: {title: 'From code to product.', description: 'I work across the application: Python logic, API endpoints, interfaces, persistent state, and deployment configuration.', examples: ['FastAPI and Streamlit provide backend and interface layers for the projects.', 'PostgreSQL-backed checkpoints support resumable travel planning sessions.', 'Git, GitHub Actions, validation tests, and Render deployment configuration support delivery.'], project: 'travel'}
  };
  const $ = (selector) => document.querySelector(selector);
  const dialogs = {project: $('#projectDialog'), resume: $('#resumeDialog'), contact: $('#contactDialog'), command: $('#commandDialog'), skill: $('#skillDialog')};
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const nudge = $('#recruiterNudge');
  let lastTrigger = null;
  let currentProject = null;
  let walkthroughStep = -1;
  let toastTimer;
  let nudgeSeen = false;
  let nudgeDismissed = false;
  try { nudgeDismissed = sessionStorage.getItem('rs-nudge-dismissed') === 'true'; } catch (_) { /* Private browsing can disable session storage. */ }

  function dismissNudge() {
    nudge.hidden = true;
    nudgeDismissed = true;
    try { sessionStorage.setItem('rs-nudge-dismissed', 'true'); } catch (_) { /* No persistence is needed for the main experience. */ }
  }
  function openDialog(name, trigger = document.activeElement) {
    const next = dialogs[name];
    if (!next) return;
    if (trigger instanceof HTMLElement && !trigger.closest('dialog')) lastTrigger = trigger;
    document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
    dismissNudge();
    next.showModal();
    document.body.classList.add('modal-open');
    if (name === 'command') { $('#commandSearch').value = ''; renderCommands(); $('#commandSearch').focus(); }
  }
  function closeDialog(dialog) { if (dialog.open) dialog.close(); }
  Object.values(dialogs).forEach(dialog => {
    dialog.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => closeDialog(dialog)));
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeDialog(dialog);
    });
    dialog.addEventListener('close', () => {
      if (!document.querySelector('dialog[open]')) {
        document.body.classList.remove('modal-open');
        document.body.append($('#toast'));
        if (lastTrigger?.isConnected) lastTrigger.focus({preventScroll:true});
      }
    });
  });
  document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => openDialog(button.dataset.open, button)));
  $('.nudge-close').addEventListener('click', dismissNudge);

  function showToast(message) {
    const toast = $('#toast');
    const parent = document.querySelector('dialog[open]') || document.body;
    parent.append(toast);
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 3200);
  }
  async function copyText(value, label) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else {
        const input = document.createElement('textarea');
        input.value = value;
        input.setAttribute('aria-label', 'Text to copy');
        Object.assign(input.style, {position:'fixed',top:'0',left:'0',opacity:'0'});
        const focused = document.activeElement;
        (document.querySelector('dialog[open]') || document.body).append(input);
        input.select();
        const copied = document.execCommand('copy');
        input.remove();
        focused?.focus({preventScroll:true});
        if (!copied) throw new Error('Copy unavailable');
      }
      showToast(`${label} copied to clipboard.`);
    } catch (_) {
      showToast(`Copy unavailable. ${label === 'Email' ? 'Select the email address or use the email link.' : 'Use the hosted app link for automatic demo access.'}`);
    }
  }
  $('#copyEmail').addEventListener('click', () => copyText('rishabhshukla9512@gmail.com', 'Email'));
  $('#copyDemoPasscode').addEventListener('click', () => {
    if (!currentProject) return;
    const url = new URL(demoLinks[currentProject]);
    const passcode = url.searchParams.get('password') || url.hash.slice(1);
    if (passcode) copyText(passcode, 'Demo passcode');
  });
  function fillList(element, items) {
    element.replaceChildren(...items.map(text => {const li = document.createElement('li'); li.textContent = text; return li;}));
  }
  function openProject(key, trigger = document.activeElement) {
    const project = projects[key];
    if (!project) return;
    currentProject = key;
    walkthroughStep = -1;
    $('#projectDialogTitle').textContent = project.title;
    $('#projectDialogKicker').textContent = project.kicker;
    $('#projectDialogDescription').textContent = project.description;
    fillList($('#projectDialogTags'), project.tags);
    fillList($('#projectDialogFeatures'), project.features);
    fillList($('#projectDialogWorkflow'), project.workflow);
    $('#projectDemoLink').href = demoLinks[key];
    $('#projectSourceLink').href = project.sourceUrl || `https://github.com/rs6739171-hash/${project.repository}`;
    const demoUrl = new URL(demoLinks[key]);
    const hasPasscode = Boolean(demoUrl.searchParams.get('password') || demoUrl.hash.slice(1));
    $('#copyDemoPasscode').hidden = !hasPasscode;
    $('#walkthroughNext').textContent = 'Start walkthrough →';
    $('#walkthroughOutput').textContent = 'Explore how the agents work together, one step at a time.';
    openDialog('project', trigger);
    dialogs.project.scrollTop = 0;
  }
  document.querySelectorAll('[data-project]').forEach(button => button.addEventListener('click', () => openProject(button.dataset.project, button)));
  $('#walkthroughNext').addEventListener('click', () => {
    const project = projects[currentProject];
    if (!project) return;
    walkthroughStep = (walkthroughStep + 1) % project.steps.length;
    $('#walkthroughOutput').textContent = `${walkthroughStep + 1} / ${project.steps.length} · ${project.steps[walkthroughStep]}`;
    $('#walkthroughNext').textContent = walkthroughStep === project.steps.length - 1 ? 'Restart walkthrough ↻' : (walkthroughStep === project.approval ? 'Approve example →' : 'Next step →');
    Array.from($('#projectDialogWorkflow').children).forEach((item, index) => {
      if (index === walkthroughStep) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
  });
  let relatedProject = 'rag';
  document.querySelectorAll('[data-skill]').forEach(button => button.addEventListener('click', () => {
    const skill = skills[button.dataset.skill];
    $('#skillTitle').textContent = skill.title;
    $('#skillDescription').textContent = skill.description;
    fillList($('#skillExamples'), skill.examples);
    relatedProject = skill.project;
    openDialog('skill', button);
  }));
  $('#skillProjectButton').addEventListener('click', () => openProject(relatedProject));

  // Searchable keyboard navigation also works using ordinary Tab / Shift+Tab.
  const commands = [
    {label:'Selected projects', hint:'Section', keywords:'work portfolio projects', section:'projects'},
    {label:'Enterprise Agentic RAG', hint:'Project', keywords:'retrieval knowledge ragas qdrant', project:'rag'},
    {label:'Market Analyst', hint:'Project', keywords:'stocks langgraph research', project:'market'},
    {label:'Travel Planner', hint:'Project', keywords:'trip mcp itinerary', project:'travel'},
    {label:'Secure Clinical EHR Validator', hint:'Project', keywords:'clinical healthcare safety guardrails retrieval grounding ehr', project:'clinical'},
    {label:'Explainable Credit Risk with SHAP', hint:'Project', keywords:'machine learning analytics shap explainability credit risk model', project:'credit'},
    {label:'View resume', hint:'PDF preview', keywords:'cv download education', dialog:'resume'},
    {label:'Contact Rishabh', hint:'Email & phone', keywords:'hire recruiter connect linkedin', dialog:'contact'},
    {label:'About & experience', hint:'Section', keywords:'education iit analyst', section:'about'},
    {label:'Technical stack', hint:'Section', keywords:'skills tools python', section:'skills'},
    {label:'Back to introduction', hint:'Section', keywords:'home top', section:'hero'}
  ];
  let matchingCommands = [];
  let activeCommand = 0;
  function selectCommand(index, moveFocus = false) {
    if (!matchingCommands.length) return;
    activeCommand = (index + matchingCommands.length) % matchingCommands.length;
    const buttons = Array.from($('#commandResults').children);
    buttons.forEach((button,i) => button.classList.toggle('is-selected',i === activeCommand));
    if (moveFocus) buttons[activeCommand]?.focus();
  }
  function executeCommand(command) {
    if (!command) return;
    if (command.project) openProject(command.project);
    else if (command.dialog) openDialog(command.dialog);
    else {
      closeDialog(dialogs.command);
      const destination = document.getElementById(command.section);
      destination?.scrollIntoView({behavior:reducedMotion.matches?'instant':'smooth',block:'start'});
      history.replaceState(null,'',`#${command.section}`);
    }
  }
  function renderCommands() {
    const query = $('#commandSearch').value.trim().toLowerCase();
    matchingCommands = commands.filter(command => `${command.label} ${command.keywords}`.toLowerCase().includes(query));
    const buttons = matchingCommands.map((command,index) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'command-result';
      const title = document.createElement('strong'); title.textContent = command.label; title.style.fontWeight = '500';
      const hint = document.createElement('span'); hint.textContent = command.hint;
      button.append(title,hint); button.addEventListener('click', () => executeCommand(command));
      button.addEventListener('focus', () => selectCommand(index));
      return button;
    });
    $('#commandResults').replaceChildren(...buttons);
    $('#commandEmpty').hidden = matchingCommands.length !== 0;
    selectCommand(0);
  }
  $('#commandSearch').addEventListener('input', renderCommands);
  dialogs.command.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const start = document.activeElement === $('#commandSearch') ? (event.key === 'ArrowDown' ? 0 : matchingCommands.length - 1) : activeCommand + (event.key === 'ArrowDown' ? 1 : -1);
      selectCommand(start, true);
    } else if (event.key === 'Enter' && document.activeElement === $('#commandSearch')) {
      event.preventDefault();executeCommand(matchingCommands[activeCommand]);
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (dialogs.command.open) closeDialog(dialogs.command); else openDialog('command');
    }
  });

  // Mobile navigation is an ordinary, keyboard-accessible disclosure.
  const menu = $('.menu-toggle');
  const navLinks = $('#navLinks');
  function setMenu(open) {
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    navLinks.classList.toggle('is-open',open);
  }
  menu.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
  navLinks.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', event => {if(event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true'){setMenu(false);menu.focus();}});
  document.addEventListener('click', event => {if(!event.target.closest('.nav') && menu.getAttribute('aria-expanded') === 'true') setMenu(false);});

  // No frame preloader: the page is usable immediately. Animate only when needed.
  if ('IntersectionObserver' in window) {
    if (!reducedMotion.matches) document.body.classList.add('motion-enabled');
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {if(entry.isIntersecting){entry.target.classList.add('is-visible');revealObserver.unobserve(entry.target);}});
    },{threshold:.06,rootMargin:'0px 0px -24px 0px'});
    document.querySelectorAll('.reveal').forEach(element => revealObserver.observe(element));
  }
  reducedMotion.addEventListener('change', () => {
    if (reducedMotion.matches) document.body.classList.remove('motion-enabled');
  });
  let framePending = false;
  const trackedSections = Array.from(document.querySelectorAll('main section[id]')).filter(section => ['projects','about','skills','contact'].includes(section.id));
  const pageLinks = Array.from(navLinks.querySelectorAll('a'));
  function updateScroll() {
    framePending = false;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const progress = Math.min(1, Math.max(0, window.scrollY / max));
    $('.scroll-progress').style.transform = `scaleX(${progress})`;
    let active = '';
    for (const section of trackedSections) {if(section.getBoundingClientRect().top < window.innerHeight * .4) active = section.id;}
    pageLinks.forEach(link => {if(link.hash === `#${active}`) link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});
    const contactVisible = $('#contact').getBoundingClientRect().top < window.innerHeight;
    if (contactVisible) nudge.hidden = true;
    else if (!nudgeDismissed && !nudgeSeen && progress > .47 && !document.querySelector('dialog[open]')) {
      nudge.hidden = false;nudgeSeen = true;
    }
  }
  window.addEventListener('scroll', () => {if(!framePending){framePending=true;requestAnimationFrame(updateScroll);}}, {passive:true});
  window.addEventListener('resize', () => {if(window.innerWidth > 620) setMenu(false);updateScroll();}, {passive:true});
  updateScroll();
})();
