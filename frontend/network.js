const apiBaseInput = document.getElementById('api-base');
const apiKeyInput = document.getElementById('api-key');
const saveButton = document.getElementById('save-config');
<<<<<<< codex/verify-the-structure-srus8u
const refreshMitreButton = document.getElementById('refresh-mitre');
const refreshRunsButton = document.getElementById('refresh-runs');
=======
const refreshButton = document.getElementById('refresh-mitre');
>>>>>>> main
const statusText = document.getElementById('mitre-status');
const mitreList = document.getElementById('mitre-list');
const activeScenarios = document.getElementById('active-scenarios');

<<<<<<< codex/verify-the-structure-srus8u
const scenarioNameInput = document.getElementById('scenario-name');
const scenarioTechniqueSelect = document.getElementById('scenario-technique');
const startScenarioButton = document.getElementById('start-scenario');
const scenarioRunsList = document.getElementById('scenario-runs');

let cachedTechniques = [];

=======
>>>>>>> main
const getConfig = () => ({
  baseUrl: localStorage.getItem('orion.apiBase') || 'http://localhost:8000',
  apiKey: localStorage.getItem('orion.apiKey') || '',
});

<<<<<<< codex/verify-the-structure-srus8u
const requestHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const config = getConfig();
  if (config.apiKey) headers['x-api-key'] = config.apiKey;
  return headers;
};

=======
>>>>>>> main
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
<<<<<<< codex/verify-the-structure-srus8u
  scenarioTechniqueSelect.innerHTML = '';

=======
>>>>>>> main
  items.forEach((item) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <strong>${item.technique_id}</strong> — ${item.name}
      <small>${item.tactics.join(', ') || 'no tactics'} · action: ${item.action}</small>
    `;
    mitreList.appendChild(li);
<<<<<<< codex/verify-the-structure-srus8u

    const option = document.createElement('option');
    option.value = item.technique_id;
    option.textContent = `${item.technique_id} — ${item.name}`;
    scenarioTechniqueSelect.appendChild(option);
=======
>>>>>>> main
  });
};

const fetchMitreTechniques = async () => {
  const config = getConfig();
<<<<<<< codex/verify-the-structure-srus8u
  setStatus('Carregando técnicas MITRE...');

  try {
    const response = await fetch(`${config.baseUrl}/mitre/techniques`, { headers: requestHeaders() });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const payload = await response.json();
    const items = payload.items || [];
    cachedTechniques = items;
    renderMitreList(items);
    setStatus(`${items.length} técnicas carregadas.`, 'ok');
  } catch (error) {
    mitreList.innerHTML = '<li><strong>Falha ao carregar.</strong><small>Verifique URL/API key e backend.</small></li>';
    scenarioTechniqueSelect.innerHTML = '<option value="">Sem técnicas</option>';
=======
  const headers = {};

  if (config.apiKey) {
    headers['x-api-key'] = config.apiKey;
  }

  setStatus('Carregando técnicas MITRE...');

  try {
    const response = await fetch(`${config.baseUrl}/mitre/techniques`, { headers });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const items = payload.items || [];
    renderMitreList(items);
    activeScenarios.textContent = `${Math.max(0, items.length - 3)} ativos`;
    setStatus(`${items.length} técnicas carregadas.`, 'ok');
  } catch (error) {
    mitreList.innerHTML = '<li><strong>Falha ao carregar.</strong><small>Verifique URL/API key e backend.</small></li>';
>>>>>>> main
    setStatus(`Erro ao carregar MITRE: ${error.message}`, 'error');
  }
};

<<<<<<< codex/verify-the-structure-srus8u
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
  } catch (error) {
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

const bootstrap = async () => {
  const config = getConfig();
  apiBaseInput.value = config.baseUrl;
  apiKeyInput.value = config.apiKey;
  await fetchMitreTechniques();
  await fetchScenarioRuns();
};

saveButton.addEventListener('click', async () => {
  saveConfig();
  await fetchMitreTechniques();
  await fetchScenarioRuns();
});

refreshMitreButton.addEventListener('click', fetchMitreTechniques);
refreshRunsButton.addEventListener('click', fetchScenarioRuns);
startScenarioButton.addEventListener('click', startScenarioRun);

setInterval(fetchScenarioRuns, 4000);
=======
const bootstrap = () => {
  const config = getConfig();
  apiBaseInput.value = config.baseUrl;
  apiKeyInput.value = config.apiKey;
  fetchMitreTechniques();
};

saveButton.addEventListener('click', () => {
  saveConfig();
  fetchMitreTechniques();
});

refreshButton.addEventListener('click', fetchMitreTechniques);
>>>>>>> main

bootstrap();
