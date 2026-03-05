// ── DOM references ────────────────────────────────────────────────────────────
const apiBaseInput       = document.getElementById('api-base');
const apiKeyInput        = document.getElementById('api-key');
const apiTokenInput      = document.getElementById('api-token');
const saveButton         = document.getElementById('save-config');
const refreshMitreButton = document.getElementById('refresh-mitre');
const refreshRunsButton  = document.getElementById('refresh-runs');
const refreshJobsButton  = document.getElementById('refresh-jobs');
const refreshSessionsButton = document.getElementById('refresh-sessions');
const logoutTokenButton  = document.getElementById('logout-token');
const logoutAllButton    = document.getElementById('logout-all');
const runGcButton        = document.getElementById('run-gc');
const statusText         = document.getElementById('mitre-status');
const mitreList          = document.getElementById('mitre-list');
const activeScenarios    = document.getElementById('active-scenarios');

// Stats bar — now sourced from real /ops/overview
const metricActiveJobs   = document.getElementById('metric-active-jobs');
const metricJobsTotal    = document.getElementById('metric-jobs-total');
const metricAlerts       = document.getElementById('metric-alerts');
const metricActiveSteps  = document.getElementById('metric-active-steps');
const metricFailedJobs   = document.getElementById('metric-failed-jobs');

const scenarioNameInput      = document.getElementById('scenario-name');
const scenarioTechniqueSelect = document.getElementById('scenario-technique');
const startScenarioButton    = document.getElementById('start-scenario');
const scenarioRunsList       = document.getElementById('scenario-runs');

const createBlueprintButton = document.getElementById('create-blueprint');
const jobBlueprintSelect    = document.getElementById('job-blueprint');
const jobActionSelect       = document.getElementById('job-action');
const submitJobButton       = document.getElementById('submit-job');
const jobsList              = document.getElementById('jobs-list');
const eventsList            = document.getElementById('events-list');

// Steps panel
const stepsPanel   = document.getElementById('steps-panel');
const stepsJobId   = document.getElementById('steps-job-id');
const stepsList    = document.getElementById('steps-list');
const closeSteps   = document.getElementById('close-steps');

// GC panel
const gcPanel      = document.getElementById('gc-panel');
const gcDryLabel   = document.getElementById('gc-dry-label');
const gcOrphans    = document.getElementById('gc-orphans');
const closeGc      = document.getElementById('close-gc');

// Sessions panel
const sessionsScopeSelect    = document.getElementById('sessions-scope');
const sessionsUserIdInput    = document.getElementById('sessions-user-id');
const sessionsTokenType      = document.getElementById('sessions-token-type');
const sessionsReason         = document.getElementById('sessions-reason');
const sessionsLimit          = document.getElementById('sessions-limit');
const sessionsPrev           = document.getElementById('sessions-prev');
const sessionsNext           = document.getElementById('sessions-next');
const sessionsMeta           = document.getElementById('sessions-meta');
const sessionsList           = document.getElementById('sessions-list');

const nodeIds   = ['node-fw','node-core','node-sw-core','node-sw-dmz','node-siem','node-ids','node-web','node-db','node-attacker'];
const linkThreat = document.getElementById('link-threat');
const linkDmz    = document.getElementById('link-dmz');

let localEvents      = [];
let backendEvents    = [];
let lastScenarioRuns = [];
let lastJobs         = [];
let sessionsOffset   = 0;
let openStepsJobId   = null;

// ── Config ────────────────────────────────────────────────────────────────────
/**
 * @returns {{baseUrl: string, apiKey: string, apiToken: string}}
 */
const getConfig = () => ({
  baseUrl: localStorage.getItem('orion.apiBase') || 'http://localhost:8000',
  apiKey:  localStorage.getItem('orion.apiKey')  || '',
  apiToken: localStorage.getItem('orion.apiToken') || '',
});

/**
 * Build request headers for backend calls.
 * Prefer Bearer token when available and keep x-api-key for legacy/admin flows.
 * @returns {Record<string, string>}
 */
const requestHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const { apiKey, apiToken } = getConfig();
  if (apiKey) headers['x-api-key'] = apiKey;
  if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;
  return headers;
};

const setStatus = (message, type = 'info') => {
  statusText.textContent  = message;
  statusText.dataset.type = type;
};

// ── Events ────────────────────────────────────────────────────────────────────
const renderEvents = () => {
  const merged = [...localEvents, ...backendEvents]
    .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)))
    .slice(0, 12);

  eventsList.innerHTML = '';
  merged.forEach((event) => {
    const li = document.createElement('li');
    li.className = `event-${event.level || 'info'}`;
    li.innerHTML = `<strong>${event.timestamp}</strong><span>${event.message}</span>`;
    eventsList.appendChild(li);
  });
};

const addEvent = (message, level = 'info') => {
  localEvents.unshift({ message, level, timestamp: new Date().toLocaleTimeString() });
  localEvents = localEvents.slice(0, 12);
  renderEvents();
};

// ── Topology ──────────────────────────────────────────────────────────────────
const setTopologyState = () => {
  nodeIds.forEach((id) => {
    const node = document.getElementById(id);
    if (node) node.classList.remove('node-active', 'node-alert');
  });
  linkThreat.classList.remove('link-hot');
  linkDmz.classList.remove('link-hot');

  const runningScenarios = lastScenarioRuns.filter(r => r.status === 'running' || r.status === 'pending').length;
  const runningJobs      = lastJobs.filter(j => j.status === 'running' || j.status === 'pending').length;
  const failedJobs       = lastJobs.filter(j => j.status === 'failed').length;

  if (runningScenarios > 0) {
    document.getElementById('node-attacker')?.classList.add('node-active');
    document.getElementById('node-fw')?.classList.add('node-active');
    linkThreat.classList.add('link-hot');
  }
  if (runningJobs > 0) {
    document.getElementById('node-core')?.classList.add('node-active');
    document.getElementById('node-sw-dmz')?.classList.add('node-active');
    linkDmz.classList.add('link-hot');
  }
  if (failedJobs > 0) {
    document.getElementById('node-ids')?.classList.add('node-alert');
    document.getElementById('node-siem')?.classList.add('node-alert');
  }
};

// ── Ops overview — real metrics from backend ──────────────────────────────────
const applyOverview = (overview) => {
  const summary = overview.summary || {};

  metricActiveJobs.textContent  = summary.active_jobs    ?? 0;
  metricJobsTotal.textContent   = summary.jobs_total     ?? 0;
  metricAlerts.textContent      = summary.alerts_active  ?? 0;
  metricActiveSteps.textContent = summary.active_steps   ?? 0;
  metricFailedJobs.textContent  = `${summary.failed_jobs ?? 0} falhas`;
  activeScenarios.textContent   = `${summary.active_scenarios ?? 0} ativos`;

  backendEvents = (overview.recent_events || []).map((event) => ({
    timestamp: (event.timestamp || '').replace('T', ' ').slice(11, 19) || new Date().toLocaleTimeString(),
    level:     event.level   || 'info',
    message:   `${event.source || 'ops'}: ${event.message || ''}`,
  }));

  renderEvents();
};

const fetchOpsOverview = async () => {
  const { baseUrl } = getConfig();
  try {
    const r = await fetch(`${baseUrl}/ops/overview`, { headers: requestHeaders() });
    if (!r.ok) return;
    applyOverview(await r.json());
  } catch { /* silent — specific fetches keep screen updated */ }
};

// ── Config save ───────────────────────────────────────────────────────────────
const saveConfig = () => {
  localStorage.setItem('orion.apiBase', apiBaseInput.value.trim() || 'http://localhost:8000');
  localStorage.setItem('orion.apiKey',  apiKeyInput.value.trim());
  localStorage.setItem('orion.apiToken', apiTokenInput.value.trim());
  setStatus('Configuração salva.', 'ok');
  addEvent('Configuração da API atualizada.', 'info');
};

/**
 * @param {string} token
 */
const setApiToken = (token) => {
  const value = String(token || '').trim();
  localStorage.setItem('orion.apiToken', value);
  apiTokenInput.value = value;
};

const logoutCurrentToken = async () => {
  const { baseUrl, apiToken } = getConfig();
  if (!apiToken) {
    setStatus('Informe Access Token para logout.', 'error');
    return;
  }

  try {
    const r = await fetch(`${baseUrl}/auth/logout`, {
      method: 'POST',
      headers: requestHeaders(),
      body: JSON.stringify({ access_token: apiToken }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    setStatus(`Logout concluído (revogados: ${body.revoked ?? 0}).`, 'ok');
    addEvent('Logout token executado.', 'info');
    setApiToken('');
    sessionsOffset = 0;
    await fetchSessions();
  } catch (error) {
    setStatus(`Erro logout: ${error.message}`, 'error');
    addEvent('Falha em logout token.', 'error');
  }
};

const logoutAllSessions = async () => {
  const { baseUrl, apiToken } = getConfig();
  if (!apiToken) {
    setStatus('Informe Access Token para logout-all.', 'error');
    return;
  }

  try {
    const r = await fetch(`${baseUrl}/auth/logout-all`, {
      method: 'POST',
      headers: requestHeaders(),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    setStatus(`Logout-all concluído (tv=${body.token_version ?? '?'}).`, 'ok');
    addEvent('Logout all executado.', 'warn');
    setApiToken('');
    sessionsOffset = 0;
    await fetchSessions();
  } catch (error) {
    setStatus(`Erro logout-all: ${error.message}`, 'error');
    addEvent('Falha em logout all.', 'error');
  }
};

// ── Sessions ─────────────────────────────────────────────────────────────────
/**
 * @param {{
 *  user_id?: string,
 *  token_version?: number,
 *  total_revoked_tokens?: number,
 *  limit?: number,
 *  offset?: number,
 *  revoked_tokens?: Array<{jti?: string, token_type?: string, reason?: string, revoked_at?: string, expires_at?: string}>
 * }} payload
 */
const renderSessions = (payload) => {
  const items = Array.isArray(payload.revoked_tokens) ? payload.revoked_tokens : [];
  const limit = Number(payload.limit ?? (Number(sessionsLimit.value) || 10));
  const offset = Number(payload.offset ?? sessionsOffset);
  const total = Number(payload.total_revoked_tokens ?? items.length);

  sessionsOffset = offset;

  const scope = sessionsScopeSelect.value;
  const label = scope === 'user' ? (payload.user_id || sessionsUserIdInput.value || '-') : 'self';
  sessionsMeta.textContent = `scope=${label} • tv=${payload.token_version ?? 0} • total=${total} • showing ${items.length} (offset=${offset})`;

  sessionsList.innerHTML = '';
  if (!items.length) {
    sessionsList.innerHTML = '<li><small>Nenhum token revogado para os filtros atuais.</small></li>';
    return;
  }

  items.forEach((item) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <strong>${item.token_type || '-'} · ${item.reason || 'n/a'}</strong>
      <small>jti=${(item.jti || '').slice(0, 12)}…</small>
      <small>revoked=${item.revoked_at || '-'}</small>
      <small>expires=${item.expires_at || '-'}</small>
    `;
    sessionsList.appendChild(li);
  });

  sessionsPrev.disabled = sessionsOffset <= 0;
  sessionsNext.disabled = sessionsOffset + limit >= total;
};

const _sessionsEndpoint = () => {
  if (sessionsScopeSelect.value === 'user') {
    const userId = sessionsUserIdInput.value.trim();
    if (!userId) throw new Error('Informe user_id para modo Usuário (admin).');
    return `/auth/users/${encodeURIComponent(userId)}/sessions`;
  }
  return '/auth/sessions';
};

const fetchSessions = async () => {
  const { baseUrl } = getConfig();
  const limit = Number(sessionsLimit.value || 10);
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(sessionsOffset),
  });
  if (sessionsTokenType.value) params.set('token_type', sessionsTokenType.value);
  if (sessionsReason.value) params.set('reason', sessionsReason.value);

  try {
    const endpoint = _sessionsEndpoint();
    const r = await fetch(`${baseUrl}${endpoint}?${params.toString()}`, { headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    renderSessions(body);
  } catch (error) {
    sessionsMeta.textContent = `Falha ao carregar sessões: ${error.message}`;
    sessionsList.innerHTML = '<li><small>Sem dados de sessão.</small></li>';
  }
};

// ── MITRE ─────────────────────────────────────────────────────────────────────
const renderMitreList = (items) => {
  mitreList.innerHTML            = '';
  scenarioTechniqueSelect.innerHTML = '';

  items.forEach((item) => {
    const li     = document.createElement('li');
    li.innerHTML = `<strong>${item.technique_id}</strong> — ${item.name}<small>${item.tactics.join(', ') || 'no tactics'} · action: ${item.action}</small>`;
    mitreList.appendChild(li);

    const option      = document.createElement('option');
    option.value      = item.technique_id;
    option.textContent = `${item.technique_id} — ${item.name}`;
    scenarioTechniqueSelect.appendChild(option);
  });
};

const fetchMitreTechniques = async () => {
  const { baseUrl } = getConfig();
  setStatus('Carregando técnicas MITRE...');
  try {
    const r = await fetch(`${baseUrl}/mitre/techniques`, { headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { items = [] } = await r.json();
    renderMitreList(items);
    setStatus(`${items.length} técnicas carregadas.`, 'ok');
    addEvent(`MITRE sync: ${items.length} técnicas.`, 'ok');
  } catch (error) {
    mitreList.innerHTML = '<li><strong>Falha ao carregar.</strong><small>Verifique URL/API key e backend.</small></li>';
    scenarioTechniqueSelect.innerHTML = '<option value="">Sem técnicas</option>';
    setStatus(`Erro: ${error.message}`, 'error');
    addEvent('Falha ao sincronizar MITRE.', 'error');
  }
};

// ── Scenarios ─────────────────────────────────────────────────────────────────
const renderScenarioRuns = (runs) => {
  scenarioRunsList.innerHTML = '';
  lastScenarioRuns = runs;

  runs.slice(0, 8).forEach((run) => {
    const li     = document.createElement('li');
    li.innerHTML = `<div><strong>${run.scenario_name}</strong><small>${run.id.slice(0,8)} · ${run.status}</small></div><button class="btn ghost stop-btn" data-run-id="${run.id}">stop</button>`;
    scenarioRunsList.appendChild(li);
  });

  scenarioRunsList.querySelectorAll('.stop-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await stopScenarioRun(btn.dataset.runId);
      await fetchScenarioRuns();
    });
  });

  setTopologyState();
};

const fetchScenarioRuns = async () => {
  const { baseUrl } = getConfig();
  try {
    const r = await fetch(`${baseUrl}/scenarios/runs`, { headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const runs = await r.json();
    renderScenarioRuns(Array.isArray(runs) ? runs : []);
  } catch {
    scenarioRunsList.innerHTML = '<li><div><strong>Falha ao listar cenários</strong></div></li>';
  }
};

const startScenarioRun = async () => {
  const { baseUrl } = getConfig();
  const tech = scenarioTechniqueSelect.value;
  if (!tech) return setStatus('Selecione uma técnica MITRE.', 'error');

  const payload = {
    scenario_name: scenarioNameInput.value.trim() || 'mitre-live-sim',
    steps: [
      { name: 'technique-step', action: `mitre:${tech}`, delay_ms: 20 },
      { name: 'observe-step',   action: 'observe',       delay_ms: 20 },
    ],
  };

  try {
    const r   = await fetch(`${baseUrl}/scenarios/runs`, { method: 'POST', headers: requestHeaders(), body: JSON.stringify(payload) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const run = await r.json();
    setStatus(`Cenário iniciado: ${run.id.slice(0,8)}`, 'ok');
    addEvent(`Scenario start: ${run.scenario_name}.`, 'ok');
    await fetchScenarioRuns();
    await fetchOpsOverview();
  } catch (error) {
    setStatus(`Erro: ${error.message}`, 'error');
    addEvent('Falha ao iniciar cenário.', 'error');
  }
};

const stopScenarioRun = async (runId) => {
  const { baseUrl } = getConfig();
  try {
    const r = await fetch(`${baseUrl}/scenarios/runs/${runId}/stop`, { method: 'POST', headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    setStatus(`Parada solicitada: ${runId.slice(0,8)}`, 'ok');
    addEvent(`Scenario stop: ${runId.slice(0,8)}.`, 'info');
  } catch (error) {
    setStatus(`Erro: ${error.message}`, 'error');
  }
};

// ── Blueprints ────────────────────────────────────────────────────────────────
const renderBlueprints = (items) => {
  jobBlueprintSelect.innerHTML = '';
  if (!items.length) { jobBlueprintSelect.innerHTML = '<option value="">Nenhum blueprint</option>'; return; }
  items.forEach((bp) => {
    const o = document.createElement('option');
    o.value       = bp.id;
    o.textContent = `${bp.name} (${bp.id.slice(0,8)})`;
    jobBlueprintSelect.appendChild(o);
  });
};

const fetchBlueprints = async () => {
  const { baseUrl } = getConfig();
  try {
    const r     = await fetch(`${baseUrl}/blueprints`, { headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const items = await r.json();
    renderBlueprints(Array.isArray(items) ? items : []);
  } catch { renderBlueprints([]); }
};

const createDemoBlueprint = async () => {
  const { baseUrl } = getConfig();
  const suffix  = Date.now().toString().slice(-6);
  const payload = {
    name: `frontend-demo-${suffix}`, schema_version: '1.0', version: '0.1.0',
    networks: [{ name: 'corp-net', cidr: '10.10.10.0/24' }],
    nodes:    [{ name: 'node-1', role: 'server', networks: ['corp-net'] }],
  };
  try {
    const r = await fetch(`${baseUrl}/blueprints`, { method: 'POST', headers: requestHeaders(), body: JSON.stringify(payload) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    setStatus('Blueprint demo criado.', 'ok');
    addEvent('Blueprint demo criado.', 'ok');
    await fetchBlueprints();
    await fetchOpsOverview();
  } catch (error) { setStatus(`Erro: ${error.message}`, 'error'); }
};

// ── Jobs ──────────────────────────────────────────────────────────────────────
const _stepStatusEmoji = (s) => ({ done: '✅', running: '⏳', failed: '❌', pending: '○' }[s] || '?');
const _formatStepTime = (iso) => (iso ? String(iso).replace('T', ' ').slice(0, 19) : '-');
const _truncateText = (value, max = 220) => {
  const text = String(value || '').trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const showJobSteps = async (jobId, { silent = false } = {}) => {
  const { baseUrl } = getConfig();
  openStepsJobId = jobId;
  stepsPanel.style.display = 'block';
  gcPanel.style.display = 'none';
  stepsJobId.textContent = jobId.slice(0, 8);
  if (!silent) {
    stepsList.innerHTML = '<li>Carregando...</li>';
  }

  try {
    const r     = await fetch(`${baseUrl}/jobs/${jobId}/steps`, { headers: requestHeaders() });
    if (!r.ok)  throw new Error(`HTTP ${r.status}`);
    const steps = await r.json();

    stepsList.innerHTML = '';
    if (!steps.length) {
      stepsList.innerHTML = '<li><small>Nenhum step registrado ainda.</small></li>';
      return;
    }
    steps.forEach((step) => {
      const li = document.createElement('li');
      const title = document.createElement('strong');
      const meta = document.createElement('small');
      const emoji = _stepStatusEmoji(step.status);
      const durSeconds = (step.started_at && step.finished_at)
        ? ((new Date(step.finished_at) - new Date(step.started_at)) / 1000).toFixed(1)
        : null;

      title.textContent = `${emoji} ${step.step_key}`;
      const metaParts = [
        `status=${step.status || 'pending'}`,
        `started=${_formatStepTime(step.started_at)}`,
        `finished=${_formatStepTime(step.finished_at)}`,
      ];
      if (durSeconds !== null) metaParts.push(`dur=${durSeconds}s`);
      meta.textContent = metaParts.join(' | ');
      li.appendChild(title);
      li.appendChild(meta);

      if (step.error) {
        const err = document.createElement('pre');
        err.className = 'step-error';
        err.textContent = _truncateText(step.error, 600);
        li.appendChild(err);
      }

      stepsList.appendChild(li);
    });
  } catch (error) {
    if (!silent) {
      stepsList.innerHTML = `<li><small>Erro: ${error.message}</small></li>`;
    }
  }
};

const renderJobs = (jobs) => {
  jobsList.innerHTML = '';
  lastJobs = jobs;

  jobs.slice(0, 10).forEach((job) => {
    const li = document.createElement('li');
    const statusClass = { succeeded: 'ok', failed: 'error', running: 'info', pending: 'info' }[job.status] || 'info';
    li.innerHTML = `
      <div>
        <strong>${job.action}</strong>
        <small>${job.id.slice(0,8)} · <span class="event-${statusClass}">${job.status}</span>
          · tentativa ${job.attempts}/${job.max_attempts}
        </small>
        ${job.last_error ? `<small class="job-last-error">erro: ${_truncateText(job.last_error)}</small>` : ''}
      </div>
      <button class="btn ghost steps-btn" data-job-id="${job.id}" title="Ver checkpoints">steps</button>
    `;
    jobsList.appendChild(li);
  });

  jobsList.querySelectorAll('.steps-btn').forEach((btn) => {
    btn.addEventListener('click', () => showJobSteps(btn.dataset.jobId));
  });

  setTopologyState();
};

const refreshOpenJobSteps = async () => {
  if (!openStepsJobId || stepsPanel.style.display === 'none') return;
  await showJobSteps(openStepsJobId, { silent: true });
};

const fetchJobs = async () => {
  const { baseUrl } = getConfig();
  try {
    const r    = await fetch(`${baseUrl}/jobs`, { headers: requestHeaders() });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const jobs = await r.json();
    renderJobs(Array.isArray(jobs) ? jobs : []);
  } catch {
    jobsList.innerHTML = '<li><div><strong>Falha ao listar jobs</strong></div></li>';
  }
};

const submitJob = async () => {
  const { baseUrl }   = getConfig();
  const blueprintId   = jobBlueprintSelect.value;
  const action        = jobActionSelect.value;

  // teardown doesn't need a blueprint in open-mode but we still pass it for tracking
  if (!blueprintId && action !== 'teardown') {
    return setStatus('Selecione um blueprint.', 'error');
  }

  const payload = {
    action,
    target_blueprint_id: blueprintId || null,
    max_attempts: 2,
  };

  try {
    const r   = await fetch(`${baseUrl}/jobs`, { method: 'POST', headers: requestHeaders(), body: JSON.stringify(payload) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const job = await r.json();
    setStatus(`Job enviado: ${job.id.slice(0,8)} [${action}]`, 'ok');
    addEvent(`Job submitted: ${action}.`, 'info');
    await fetchJobs();
    await fetchOpsOverview();
  } catch (error) {
    setStatus(`Erro: ${error.message}`, 'error');
    addEvent('Falha ao enviar job.', 'error');
  }
};

// ── GC dry-run ────────────────────────────────────────────────────────────────
const runGcDryRun = async () => {
  const { baseUrl } = getConfig();
  gcPanel.style.display    = 'block';
  stepsPanel.style.display = 'none';
  gcDryLabel.textContent   = '(dry-run)';
  gcOrphans.innerHTML      = '<li>Executando scan…</li>';

  try {
    const r      = await fetch(`${baseUrl}/ops/gc`, { headers: requestHeaders() });
    if (!r.ok)   throw new Error(`HTTP ${r.status}`);
    const report = await r.json();

    gcOrphans.innerHTML = '';

    if (report.skipped_reason) {
      gcOrphans.innerHTML = `<li><small>Pulado: ${report.skipped_reason}</small></li>`;
      return;
    }

    if (!report.orphaned_vms.length) {
      gcOrphans.innerHTML = '<li><small>✅ Nenhuma VM órfã encontrada.</small></li>';
      return;
    }

    report.orphaned_vms.forEach((vm) => {
      const li     = document.createElement('li');
      li.innerHTML = `<strong>⚠️ ${vm}</strong><small>órfã — blueprint não existe</small>`;
      gcOrphans.appendChild(li);
    });

    if (report.errors.length) {
      const errLi     = document.createElement('li');
      errLi.innerHTML = `<small style="color:var(--danger)">Erros: ${report.errors.join(', ')}</small>`;
      gcOrphans.appendChild(errLi);
    }

    addEvent(`GC: ${report.orphaned_vms.length} VMs órfãs detectadas.`, 'warn');
  } catch (error) {
    gcOrphans.innerHTML = `<li><small>Erro: ${error.message}</small></li>`;
    addEvent('Falha no GC dry-run.', 'error');
  }
};

// ── Bootstrap ─────────────────────────────────────────────────────────────────
const bootstrap = async () => {
  const config      = getConfig();
  apiBaseInput.value = config.baseUrl;
  apiKeyInput.value  = config.apiKey;
  apiTokenInput.value = config.apiToken;

  addEvent('Console iniciado.', 'info');
  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
  await fetchOpsOverview();
  await fetchSessions();
};

// ── Event listeners ───────────────────────────────────────────────────────────
saveButton.addEventListener('click', async () => {
  saveConfig();
  sessionsOffset = 0;
  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
  await fetchOpsOverview();
  await fetchSessions();
});

refreshMitreButton.addEventListener('click',  fetchMitreTechniques);
refreshRunsButton.addEventListener('click',   fetchScenarioRuns);
refreshJobsButton.addEventListener('click',   fetchJobs);
  refreshSessionsButton.addEventListener('click', async () => {
  sessionsOffset = 0;
  await fetchSessions();
});
logoutTokenButton.addEventListener('click',   logoutCurrentToken);
logoutAllButton.addEventListener('click',     logoutAllSessions);
runGcButton.addEventListener('click',         runGcDryRun);
startScenarioButton.addEventListener('click', startScenarioRun);
createBlueprintButton.addEventListener('click', createDemoBlueprint);
submitJobButton.addEventListener('click',     submitJob);
closeSteps.addEventListener('click', () => {
  stepsPanel.style.display = 'none';
  openStepsJobId = null;
});
closeGc.addEventListener('click',    () => { gcPanel.style.display    = 'none'; });
sessionsPrev.addEventListener('click', async () => {
  const step = Number(sessionsLimit.value || 10);
  sessionsOffset = Math.max(0, sessionsOffset - step);
  await fetchSessions();
});
sessionsNext.addEventListener('click', async () => {
  const step = Number(sessionsLimit.value || 10);
  sessionsOffset += step;
  await fetchSessions();
});
[sessionsScopeSelect, sessionsUserIdInput, sessionsTokenType, sessionsReason, sessionsLimit].forEach((el) => {
  el.addEventListener('change', async () => {
    sessionsOffset = 0;
    await fetchSessions();
  });
});

// Auto-refresh
setInterval(fetchScenarioRuns, 4000);
setInterval(fetchJobs,          5000);
setInterval(fetchOpsOverview,   4500);
setInterval(refreshOpenJobSteps, 4000);

bootstrap();
