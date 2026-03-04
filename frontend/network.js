const apiBaseInput = document.getElementById('api-base');
const apiKeyInput = document.getElementById('api-key');
const saveButton = document.getElementById('save-config');
const refreshMitreButton = document.getElementById('refresh-mitre');
const refreshRunsButton = document.getElementById('refresh-runs');
const refreshJobsButton = document.getElementById('refresh-jobs');
const refreshMitreButton = document.getElementById('refresh-mitre');
const refreshRunsButton = document.getElementById('refresh-runs');
const statusText = document.getElementById('mitre-status');
const mitreList = document.getElementById('mitre-list');
const activeScenarios = document.getElementById('active-scenarios');
const scenarioNameInput = document.getElementById('scenario-name');
const scenarioTechniqueSelect = document.getElementById('scenario-technique');
const startScenarioButton = document.getElementById('start-scenario');
const scenarioRunsList = document.getElementById('scenario-runs');
const createBlueprintButton = document.getElementById('create-blueprint');
const jobBlueprintSelect = document.getElementById('job-blueprint');
const jobActionSelect = document.getElementById('job-action');
const submitJobButton = document.getElementById('submit-job');
const jobsList = document.getElementById('jobs-list');
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

const saveConfig = () => {
  localStorage.setItem('orion.apiBase', apiBaseInput.value.trim() || 'http://localhost:8000');
  localStorage.setItem('orion.apiKey', apiKeyInput.value.trim());
  setStatus('Configuração salva.', 'ok');
};

const renderMitreList = (items) => {
  mitreList.innerHTML = '';
  scenarioTechniqueSelect.innerHTML = '';

  scenarioTechniqueSelect.innerHTML = '';

  items.forEach((item) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <strong>${item.technique_id}</strong> — ${item.name}
      <small>${item.tactics.join(', ') || 'no tactics'} · action: ${item.action}</small>
    `;
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
  } catch (error) {
    mitreList.innerHTML = '<li><strong>Falha ao carregar.</strong><small>Verifique URL/API key e backend.</small></li>';
    scenarioTechniqueSelect.innerHTML = '<option value="">Sem técnicas</option>';
    setStatus(`Erro ao carregar MITRE: ${error.message}`, 'error');
  }
};

const renderScenarioRuns = (runs) => {
  scenarioRunsList.innerHTML = '';
  const active = runs.filter((run) => run.status === 'running' || run.status === 'pending').length;
  activeScenarios.textContent = `${active} ativos`;

  runs.slice(0, 8).forEach((run) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <div>
        <strong>${run.scenario_name}</strong>
        <small>${run.id.slice(0, 8)} · ${run.status}</small>
      </div>
      <button class="btn ghost stop-btn" data-run-id="${run.id}">stop</button>
    `;
    scenarioRunsList.appendChild(li);
  });

  scenarioRunsList.querySelectorAll('.stop-btn').forEach((button) => {
    button.addEventListener('click', async () => {
      const runId = button.dataset.runId;
      await stopScenarioRun(runId);
      await fetchScenarioRuns();
    });
  });
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
  if (!selectedTechnique) {
    setStatus('Selecione uma técnica MITRE para iniciar.', 'error');
    return;
  }

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
    await fetchScenarioRuns();
  } catch (error) {
    setStatus(`Erro ao iniciar cenário: ${error.message}`, 'error');
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
  } catch (error) {
    setStatus(`Erro ao parar cenário: ${error.message}`, 'error');
  }
};

const renderBlueprints = (items) => {
  jobBlueprintSelect.innerHTML = '';
  if (!items.length) {
    jobBlueprintSelect.innerHTML = '<option value="">Nenhum blueprint</option>';
    return;
  }

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
    await fetchBlueprints();
  } catch (error) {
    setStatus(`Erro ao criar blueprint: ${error.message}`, 'error');
  }
};

const renderJobs = (jobs) => {
  jobsList.innerHTML = '';
  jobs.slice(0, 8).forEach((job) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <div>
        <strong>${job.action}</strong>
        <small>${job.id.slice(0, 8)} · ${job.status}</small>
      </div>
    `;
    jobsList.appendChild(li);
  });
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
  if (!blueprintId) {
    setStatus('Selecione um blueprint para enviar job.', 'error');
    return;
  }

  const payload = {
    action: jobActionSelect.value,
    target_blueprint_id: blueprintId,
    max_attempts: 2,
  };

  try {
    const response = await fetch(`${config.baseUrl}/jobs`, {
      method: 'POST',
      headers: requestHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const job = await response.json();
    setStatus(`Job enviado: ${job.id.slice(0, 8)}`, 'ok');
    await fetchJobs();
  } catch (error) {
    setStatus(`Erro ao enviar job: ${error.message}`, 'error');
  }
};

const bootstrap = async () => {
  const config = getConfig();
  apiBaseInput.value = config.baseUrl;
  apiKeyInput.value = config.apiKey;

  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
};

saveButton.addEventListener('click', async () => {
  saveConfig();
  await fetchMitreTechniques();
  await fetchScenarioRuns();
  await fetchBlueprints();
  await fetchJobs();
});

refreshMitreButton.addEventListener('click', fetchMitreTechniques);
refreshRunsButton.addEventListener('click', fetchScenarioRuns);
refreshJobsButton.addEventListener('click', fetchJobs);
startScenarioButton.addEventListener('click', startScenarioRun);
createBlueprintButton.addEventListener('click', createDemoBlueprint);
submitJobButton.addEventListener('click', submitJob);

setInterval(fetchScenarioRuns, 4000);
setInterval(fetchJobs, 5000);

bootstrap();
