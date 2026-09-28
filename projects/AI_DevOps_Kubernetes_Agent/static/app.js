'use strict';
const $ = (id) => document.getElementById(id);
const node = (tag, text, className) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (className) n.className = className; return n; };
let mode = 'demo', selected = 'crashloop', current = null, busy = false, cfg = {}, scenarios = [], liveHistory = [];
let demoHistory = [];
try { const saved = JSON.parse(localStorage.getItem('kubescope-reports-v1') || '[]'); if (Array.isArray(saved)) demoHistory = saved.filter(r => r && r.mode === 'demo' && r.stats && Array.isArray(r.findings) && r.evidence).slice(0, 20); } catch (_) { /* Storage can be unavailable in private browsing. */ }
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function ownerHeaders() { const token = $('owner-token').value.trim(); return token ? { Authorization: 'Bearer ' + token } : {}; }
async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) { let detail = 'The request could not be completed.'; try { const data = await response.json(); if (typeof data.detail === 'string') detail = data.detail; } catch (_) {} throw new Error(detail); }
  return response.json();
}
function updateControls() {
  $('run').disabled = busy || !scenarios.length || (mode === 'live' && (!cfg.live_configured || !$('context').value));
  $('demo-mode').disabled = busy; $('live-mode').disabled = busy;
  document.querySelectorAll('.scenario').forEach(b => { b.disabled = busy; });
  $('connect').disabled = busy; $('use-ai').disabled = busy;
  $('run').firstElementChild.textContent = busy ? 'Investigating…' : mode === 'demo' ? 'Investigate incident' : 'Investigate cluster';
}
function setMode(value) {
  mode = value; error('');
  $('demo-mode').classList.toggle('selected', mode === 'demo'); $('demo-mode').setAttribute('aria-pressed', mode === 'demo');
  $('live-mode').classList.toggle('selected', mode === 'live'); $('live-mode').setAttribute('aria-pressed', mode === 'live');
  $('live-panel').hidden = mode !== 'live'; $('scenarios').hidden = mode !== 'demo'; $('scenario-count').hidden = mode !== 'demo'; $('live-selection').hidden = mode !== 'live';
  $('mode-note').textContent = mode === 'demo' ? 'Synthetic evidence · no cluster required' : 'Authenticated access · read-only namespace scope';
  $('incident-heading').textContent = mode === 'demo' ? 'What needs attention?' : 'Investigate current state';
  $('owner-form').hidden = !(mode === 'live' && (cfg.live_configured || cfg.ai_configured));
  $('ai-option').hidden = !(mode === 'live' && cfg.ai_configured && cfg.live_ai); $('use-ai').checked = false; $('ai-notice').hidden = true;
  $('engine-note').textContent = mode === 'demo' ? 'Evidence-based rules · no LLM calls in the public demo' : 'Only configured read operations are permitted';
  if (mode === 'live' && !cfg.live_configured) $('live-note').textContent = 'This public deployment has no live cluster attached. Demo incidents are ready to use. To investigate your own cluster, follow the setup guide and mount a trusted kubeconfig on the server.';
  renderHistory(); updateControls();
}
function renderScenarios() {
  $('scenarios').replaceChildren();
  for (const s of scenarios) {
    const button = node('button', null, 'scenario' + (selected === s.id ? ' selected' : '')); button.type = 'button'; button.setAttribute('aria-pressed', selected === s.id); button.setAttribute('aria-label', s.category + ': ' + s.title);
    const label = node('div'); label.append(node('strong', s.title), node('small', s.category));
    const icon = node('span', s.severity === 'healthy' ? '✓' : '!', 'scenario-icon ' + s.severity); icon.setAttribute('aria-hidden', 'true');
    button.append(icon, label, node('span', '', 'scenario-radio'));
    button.addEventListener('click', () => { selected = s.id; renderScenarios(); }); $('scenarios').append(button);
  }
}
function resetTrace() {
  document.querySelectorAll('#trace li').forEach((li, i) => { li.className = ''; li.querySelector('.trace-mark').textContent = i + 1; li.querySelector('.trace-state').textContent = 'Waiting'; });
}
function progress(event) {
  const li = document.querySelector('#trace li[data-stage="' + event.stage + '"]'); if (!li) return;
  li.className = event.status === 'complete' ? 'done' : 'busy'; li.querySelector('.trace-state').textContent = event.status === 'complete' ? 'Complete' : 'Running';
  if (event.status === 'complete') li.querySelector('.trace-mark').textContent = '✓';
  $('trace-note').textContent = event.label;
}
async function investigate() {
  if (busy) return; busy = true; updateControls(); error(''); resetTrace();
  $('run-status').textContent = 'Investigating'; $('run-status').className = 'badge running';
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 180000);
  try {
    const payload = { mode, scenario: selected, context: mode === 'live' ? $('context').value : '', namespace: mode === 'live' ? $('namespace').value : 'default', use_ai: mode === 'live' && $('use-ai').checked };
    const response = await fetch('/api/investigate/stream', { method: 'POST', headers: { 'Content-Type': 'application/json', ...(mode === 'live' ? ownerHeaders() : {}) }, body: JSON.stringify(payload), signal: controller.signal });
    if (!response.ok) { const data = await response.json(); throw new Error(typeof data.detail === 'string' ? data.detail : 'Investigation request was rejected.'); }
    if (!response.body) throw new Error('This browser does not support streaming responses.');
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '', received = false;
    function consume(line) {
      if (!line.trim()) return; const event = JSON.parse(line);
      if (event.type === 'progress') progress(event);
      else if (event.type === 'error') throw new Error(event.message);
      else if (event.type === 'result') { current = event.report; received = true; }
    }
    while (true) { const chunk = await reader.read(); if (chunk.done) break; buffer += decoder.decode(chunk.value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop(); lines.forEach(consume); }
    buffer += decoder.decode(); consume(buffer);
    if (!received) throw new Error('The connection ended before a report arrived. Please try again.');
    if (current.mode === 'demo') {
      demoHistory = [current, ...demoHistory].slice(0, 20);
      try { localStorage.setItem('kubescope-reports-v1', JSON.stringify(demoHistory)); } catch (_) { $('history-note').textContent = 'Browser storage is unavailable. Export your report to keep a copy.'; }
    } else liveHistory = [current, ...liveHistory.filter(x => x.id !== current.id)].slice(0, 20);
    renderReport(current); renderHistory();
    $('run-status').textContent = 'Complete'; $('run-status').className = 'badge complete';
    $('trace-note').textContent = (current.mode === 'demo' ? 'Sample evidence' : 'Live evidence') + ' · completed in ' + (current.duration_ms / 1000).toFixed(2) + 's';
  } catch (err) {
    error(err.name === 'AbortError' ? 'The investigation timed out. Check cluster connectivity and try again.' : err.message);
    $('run-status').textContent = 'Failed'; $('run-status').className = 'badge critical'; $('trace-note').textContent = 'Investigation did not complete. The last report, if present, is unchanged.';
  } finally { clearTimeout(timeout); busy = false; updateControls(); }
}
function renderReport(report) {
  current = report; $('report-empty').hidden = true; $('report').replaceChildren();
  for (const key of ['pods', 'ready', 'restarts', 'findings']) $('stat-' + key).textContent = report.stats[key];
  $('report-meta').hidden = false; $('report-meta').textContent = (report.mode === 'demo' ? 'SAMPLE REPORT' : 'LIVE REPORT') + ' / ' + report.context + ' / ' + report.namespace + ' · ' + report.engine + ' · ' + new Date(report.created_at).toLocaleString();
  if (!report.findings.length) {
    const box = node('article', null, 'finding'); box.append(node('h3', report.status === 'incomplete' ? 'Some evidence could not be collected' : 'No supported issues detected'), node('p', report.status === 'incomplete' ? 'Review the collection warnings before drawing a conclusion.' : 'These checks found no matching failure signals in the collected evidence. This is not a guarantee of overall cluster health.')); $('report').append(box);
  }
  for (const finding of report.findings) {
    const article = node('article', null, 'finding'), header = node('div', null, 'finding-header');
    header.append(node('h3', finding.title), node('span', finding.severity.toUpperCase(), 'badge ' + finding.severity));
    article.append(header, node('p', finding.explanation), node('p', 'Evidence: ' + finding.evidence_refs.join(' · '), 'evidence-ref'), node('h4', 'RECOMMENDED NEXT STEP'), node('p', finding.fix));
    const commandBox = node('div', null, 'command-box'), copy = node('button', 'Copy checks', 'copy-button');
    const commands = finding.commands.join('\n'); commandBox.append(node('pre', commands), copy);
    copy.addEventListener('click', async () => { try { await navigator.clipboard.writeText(commands); copy.textContent = 'Copied'; } catch (_) { copy.textContent = 'Select text to copy'; } });
    article.append(commandBox, node('h4', 'PREVENTION'), node('p', finding.prevention), node('p', 'Evidence strength: ' + finding.confidence + '. Heuristic, not a calibrated probability. Commands shown above are read-only checks; nothing is executed.', 'fine')); $('report').append(article);
  }
  const warnings = report.evidence.warnings || []; $('warnings').hidden = !warnings.length; $('warnings').textContent = warnings.join(' ');
  $('ai-result').hidden = report.ai.status === 'disabled'; $('ai-result').replaceChildren();
  if (report.ai.status !== 'disabled') {
    $('ai-result').append(node('h3', report.ai.status === 'completed' ? 'AI assessment · operator review required' : 'AI assessment unavailable'), node('p', report.ai.summary));
    for (const key of ['hypotheses', 'next_checks']) if (report.ai[key]) { const list = node('ul'); report.ai[key].forEach(x => list.append(node('li', x))); $('ai-result').append(node('h4', key === 'hypotheses' ? 'Hypotheses' : 'Next checks'), list); }
    if (report.ai.limitations) $('ai-result').append(node('p', report.ai.limitations));
  }
  $('evidence-panel').hidden = false; $('evidence').textContent = JSON.stringify(report.evidence, null, 2); $('download').disabled = false;
}
function renderHistory() {
  const history = mode === 'demo' ? demoHistory : liveHistory; $('history-count').textContent = history.length; $('history-list').replaceChildren();
  if (!history.length) $('history-list').append(node('p', 'No reports yet. Your first investigation will appear here.', 'empty-note'));
  for (const report of history) {
    const button = node('button', null, 'history-row'), details = node('div');
    const title = report.findings[0]?.title || (report.status === 'incomplete' ? 'Incomplete evidence' : 'No supported issues detected');
    details.append(node('strong', title), node('small', new Date(report.created_at).toLocaleString() + ' · ' + report.namespace + ' · ' + report.mode));
    button.append(details, node('span', report.stats.findings + ' findings ↗', 'badge neutral'));
    button.addEventListener('click', () => { renderReport(report); $('results').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); }); $('history-list').append(button);
  }
}
$('run').addEventListener('click', investigate); $('demo-mode').addEventListener('click', () => setMode('demo')); $('live-mode').addEventListener('click', () => setMode('live'));
$('use-ai').addEventListener('change', () => { $('ai-notice').hidden = !$('use-ai').checked; });
$('connect').addEventListener('click', async () => {
  error(''); $('connect').disabled = true;
  try { const result = await request('/api/contexts', { headers: ownerHeaders() }); $('context').replaceChildren(); $('namespace').replaceChildren(); result.contexts.forEach(x => { const option = node('option', x); option.value = x; $('context').append(option); }); result.namespaces.forEach(x => { const option = node('option', x); option.value = x; $('namespace').append(option); }); liveHistory = await request('/api/history', { headers: ownerHeaders() }); renderHistory(); if (!result.contexts.length) error('No cluster contexts were found in the configured kubeconfig.'); }
  catch (err) { error(err.message); } finally { $('connect').disabled = false; updateControls(); }
});
$('clear-history').addEventListener('click', () => { demoHistory = []; try { localStorage.removeItem('kubescope-reports-v1'); } catch (_) {} renderHistory(); });
$('download').addEventListener('click', () => { if (!current) return; const url = URL.createObjectURL(new Blob([JSON.stringify(current, null, 2)], { type: 'application/json' })); const link = node('a'); link.href = url; link.download = 'kubescope-' + current.id + '.json'; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
async function start() {
  try { [cfg, scenarios] = await Promise.all([request('/api/config'), request('/api/scenarios')]); $('api-status').textContent = '● API connected'; renderScenarios(); renderHistory(); setMode('demo'); }
  catch (_) { $('api-status').textContent = 'API unavailable'; error('The service is starting or could not be reached. Refresh this page in a moment.'); }
}
start();
