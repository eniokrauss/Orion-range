const apiBaseInput = document.getElementById('api-base');
const apiKeyInput = document.getElementById('api-key');
const saveButton = document.getElementById('save-config');
const refreshMitreButton = document.getElementById('refresh-mitre');
const refreshRunsButton = document.getElementById('refresh-runs');
const refreshJobsButton = document.getElementById('refresh-jobs');
const statusText = document.getElementById('mitre-status');
const mitreList = document.getElementById('mitre-list');
const activeScenarios = document.getElementById('active-scenarios');

const metricPps = document.getElementById('metric-pps');
const metricThroughput = document.getElementById('metric-throughput');
const metricConnections = document.getElementById('metric-connections');
const metricAlerts = document.getElementById('metric-alerts');
const metricAnomalies = document.getElementById('metric-anomalies');

const scenarioNameInput = document.getElementById('scenario-name');
const scenarioTechniqueSelect = document.getElementById('scenario-technique');
const startScenarioButton = document.getElementById('start-scenario');
const scenarioRunsList = document.getElementById('scenario-runs');

const createBlueprintButton = document.getElementById('create-blueprint');
const jobBlueprintSelect = document.getElementById('job-blueprint');
const jobActionSelect = document.getElementById('job-action');
const submitJobButton = document.getElementById('submit-job');
const jobsList = document.getElementById('jobs-list');
const eventsList = document.getElementById('events-list');

const nodeIds = ['node-fw', 'node-core', 'node-sw-core', 'node-sw-dmz', 'node-siem', 'node-ids', 'node-web', 'node-db', 'node-attacker'];
const linkThreat = document.getElementById('link-threat');
const linkDmz = document.getElementById('link-dmz');

let localEvents = [];
let backendEvents = [];
let localEvents = [];
let backendEvents = [];
let lastScenarioRuns = [];
let lastJobs = [];

const getConfig = () => ({
  baseUrl: localStorage.getItem('orion.apiBase') || 'http://localhost:8000',
  apiKey: localStorage.getItem('orion.apiKey') || '',
});

const requestHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const config = getConfig();
  if (config.apiKey) headers['x-api-key'] = config.apiKey;
  return headers;
};

const setStatus = (message, type = 'info') => {
  statusText.textContent = message;
  statusText.dataset.type = type;
};

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

const setTopologyState = () => {
  nodeIds.forEach((id) => {
    const node = document.getElementById(id);
    node.classList.remove('node-active', 'node-alert');
  });
  linkThreat.classList.remove('link-hot');
  linkDmz.classList.remove('link-hot');

  const runningScenarios = lastScenarioRuns.filter((r) => r.status === 'running' || r.status === 'pending').length;
  const runningJobs = lastJobs.filter((j) => j.status === 'running' || j.status === 'pending').length;
  const failedJobs = lastJobs.filter((j) => j.status === 'failed').length;

  if (runningScenarios > 0) {
    document.getElementById('node-attacker').classList.add('node-active');
    document.getElementById('node-fw').classList.add('node-active');
    linkThreat.classList.add('link-hot');
  }

  if (runningJobs > 0) {
    document.getElementById('node-core').classList.add('node-active');
    document.getElementById('node-sw-dmz').classList.add('node-active');
    linkDmz.classList.add('link-hot');
  }

  if (failedJobs > 0) {
    document.getElementById('node-ids').classList.add('node-alert');
    document.getElementById('node-siem').classList.add('node-alert');
  }
};

const applyOverview = (overview) => {
  const summary = overview.summary || {};
  const telemetry = overview.telemetry || {};

  metricPps.textContent = `${telemetry.packets_per_sec ?? 0} pps`;
  metricThroughput.textContent = `${telemetry.throughput_gbps ?? 0} Gbps`;
  metricConnections.textContent = `${telemetry.connections ?? 0}`;
  metricAlerts.textContent = `${summary.alerts_per_min ?? 0} /min`;
  metricAnomalies.textContent = `${summary.anomalies ?? 0}`;
  activeScenarios.textContent = `${summary.active_scenarios ?? 0} ativos`;

  backendEvents = (overview.recent_events || []).map((event) => ({
    timestamp: (event.timestamp || '').replace('T', ' ').slice(11, 19) || new Date().toLocaleTimeString(),
    level: event.level || 'info',
    message: `${event.source || 'ops'}: ${event.message || ''}`,
  }));

  renderEvents();
};

const fetchOpsOverview = async () => {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/ops/overview`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const overview = await response.json();
    applyOverview(overview);
  } catch {
    // fallback silently; specific fetches still keep screen updated
  }
};

const saveConfig = () => {
  localStorage.setItem('orion.apiBase', apiBaseInput.value.trim() || 'http://localhost:8000');
  localStorage.setItem('orion.apiKey', apiKeyInput.value.trim());
  setStatus('Configuração salva.', 'ok');
  addEvent('Configuração da API atualizada.', 'info');
};

const renderMitreList = (items) => {
  mitreList.innerHTML = '';
  scenarioTechniqueSelect.innerHTML = '';

  items.forEach((item) => {
    const li = document.createElement('li');
    li.innerHTML = `<strong>${item.technique_id}</strong> — ${item.name}<small>${item.tactics.join(', ') || 'no tactics'} · action: ${item.action}</small>`;
    mitreList.appendChild(li);

    const option = document.createElement('option');
    option.value = item.technique_id;
    option.textContent = `${item.technique_id} — ${item.name}`;
    scenarioTechniqueSelect.appendChild(option);
  });
};

const fetchMitreTechniques = async () => {
  const config = getConfig();
  setStatus('Carregando técnicas MITRE...');

  try {
    const response = await fetch(`${config.baseUrl}/mitre/techniques`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const payload = await response.json();
    const items = payload.items || [];
    renderMitreList(items);
    setStatus(`${items.length} técnicas carregadas.`, 'ok');
    addEvent(`MITRE sync: ${items.length} técnicas.`, 'ok');
  } catch (error) {
    mitreList.innerHTML = '<li><strong>Falha ao carregar.</strong><small>Verifique URL/API key e backend.</small></li>';
    scenarioTechniqueSelect.innerHTML = '<option value="">Sem técnicas</option>';
    setStatus(`Erro ao carregar MITRE: ${error.message}`, 'error');
    addEvent('Falha ao sincronizar MITRE.', 'error');
  }
};

const renderScenarioRuns = (runs) => {
  scenarioRunsList.innerHTML = '';
  lastScenarioRuns = runs;

  runs.slice(0, 8).forEach((run) => {
    const li = document.createElement('li');
    li.innerHTML = `<div><strong>${run.scenario_name}</strong><small>${run.id.slice(0, 8)} · ${run.status}</small></div><button class="btn ghost stop-btn" data-run-id="${run.id}">stop</button>`;
    scenarioRunsList.appendChild(li);
  });

  scenarioRunsList.querySelectorAll('.stop-btn').forEach((button) => {
    button.addEventListener('click', async () => {
      const runId = button.dataset.runId;
      await stopScenarioRun(runId);
      await fetchScenarioRuns();
    });
  });

  setTopologyState();
};

const fetchScenarioRuns = async () => {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/scenarios/runs`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const runs = await response.json();
    renderScenarioRuns(Array.isArray(runs) ? runs : []);
  } catch {
    scenarioRunsList.innerHTML = '<li><div><strong>Falha ao listar cenários</strong><small>Confira backend/auth</small></div></li>';
  }
};

const startScenarioRun = async () => {
  const config = getConfig();
  const selectedTechnique = scenarioTechniqueSelect.value;
  if (!selectedTechnique) return setStatus('Selecione uma técnica MITRE para iniciar.', 'error');

  const payload = {
    scenario_name: scenarioNameInput.value.trim() || 'mitre-live-sim',
    steps: [
      { name: 'technique-step', action: `mitre:${selectedTechnique}`, delay_ms: 20 },
      { name: 'observe-step', action: 'observe', delay_ms: 20 },
    ],
  };

  try {
    const response = await fetch(`${config.baseUrl}/scenarios/runs`, {
      method: 'POST',
      headers: requestHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const run = await response.json();
    setStatus(`Cenário iniciado: ${run.id.slice(0, 8)}`, 'ok');
    addEvent(`Scenario start: ${run.scenario_name}.`, 'ok');
    await fetchScenarioRuns();
    await fetchOpsOverview();
    await fetchOpsOverview();
  } catch (error) {
    setStatus(`Erro ao iniciar cenário: ${error.message}`, 'error');
    addEvent('Falha ao iniciar cenário.', 'error');
  }
};

const stopScenarioRun = async (runId) => {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/scenarios/runs/${runId}/stop`, {
      method: 'POST',
      headers: requestHeaders(),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    setStatus(`Parada solicitada: ${runId.slice(0, 8)}`, 'ok');
    addEvent(`Scenario stop requested: ${runId.slice(0, 8)}.`, 'info');
  } catch (error) {
    setStatus(`Erro ao parar cenário: ${error.message}`, 'error');
  }
};

const renderBlueprints = (items) => {
  jobBlueprintSelect.innerHTML = '';
  if (!items.length) return (jobBlueprintSelect.innerHTML = '<option value="">Nenhum blueprint</option>');

  items.forEach((bp) => {
    const option = document.createElement('option');
    option.value = bp.id;
    option.textContent = `${bp.name} (${bp.id.slice(0, 8)})`;
    jobBlueprintSelect.appendChild(option);
  });
};

const fetchBlueprints = async () => {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/blueprints`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const items = await response.json();
    renderBlueprints(Array.isArray(items) ? items : []);
  } catch {
    renderBlueprints([]);
  }
};

const createDemoBlueprint = async () => {
  const config = getConfig();
  const suffix = Date.now().toString().slice(-6);
  const payload = {
    name: `frontend-demo-${suffix}`,
    schema_version: '1.0',
    version: '0.1.0',
    networks: [{ name: 'corp-net', cidr: '10.10.10.0/24' }],
    nodes: [{ name: 'node-1', role: 'server', networks: ['corp-net'] }],
  };

  try {
    const response = await fetch(`${config.baseUrl}/blueprints`, {
      method: 'POST',
      headers: requestHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    setStatus('Blueprint demo criado.', 'ok');
    addEvent('Blueprint demo criado.', 'ok');
    await fetchBlueprints();
    await fetchOpsOverview();
    await fetchOpsOverview();
  } catch (error) {
    setStatus(`Erro ao criar blueprint: ${error.message}`, 'error');
  }
};

const renderJobs = (jobs) => {
  jobsList.innerHTML = '';
  lastJobs = jobs;
  jobs.slice(0, 8).forEach((job) => {
    const li = document.createElement('li');
    li.innerHTML = `<div><strong>${job.action}</strong><small>${job.id.slice(0, 8)} · ${job.status}</small></div>`;
    jobsList.appendChild(li);
  });
  setTopologyState();
};

const fetchJobs = async () => {
  const config = getConfig();
  try {
    const response = await fetch(`${config.baseUrl}/jobs`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const jobs = await response.json();
    renderJobs(Array.isArray(jobs) ? jobs : []);
  } catch {
    jobsList.innerHTML = '<li><div><strong>Falha ao listar jobs</strong><small>Confira backend/auth</small></div></li>';
  }
};

const submitJob = async () => {
  const config = getConfig();
  const blueprintId = jobBlueprintSelect.value;
  if (!blueprintId) return setStatus('Selecione um blueprint para enviar job.', 'error');

  const payload = { action: jobActionSelect.value, target_blueprint_id: blueprintId, max_attempts: 2 };

  try {
    const response = await fetch(`${config.baseUrl}/jobs`, {
      method: 'POST',
      headers: requestHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const job = await response.json();
    setStatus(`Job enviado: ${job.id.slice(0, 8)}`, 'ok');
    addEvent(`Job submitted: ${job.action}.`, 'info');
    await fetchJobs();
    await fetchOpsOverview();
    await fetchOpsOverview();
  } catch (error) {
    setStatus(`Erro ao enviar job: ${error.message}`, 'error');
  }
};

const bootstrap = async () => {
  const config = getConfig();
  apiBaseInput.value = config.baseUrl;
  apiKeyInput.value = config.apiKey;

  addEvent('Console iniciado.', 'info');
  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
  await fetchOpsOverview();
  await fetchOpsOverview();
};

saveButton.addEventListener('click', async () => {
  saveConfig();
  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
  await fetchOpsOverview();
  await fetchOpsOverview();
});

refreshMitreButton.addEventListener('click', fetchMitreTechniques);
refreshRunsButton.addEventListener('click', fetchScenarioRuns);
refreshJobsButton.addEventListener('click', fetchJobs);
startScenarioButton.addEventListener('click', startScenarioRun);
createBlueprintButton.addEventListener('click', createDemoBlueprint);
submitJobButton.addEventListener('click', submitJob);

setInterval(fetchScenarioRuns, 4000);
setInterval(fetchJobs, 5000);
setInterval(fetchOpsOverview, 4500);
setInterval(fetchOpsOverview, 4500);

bootstrap();
