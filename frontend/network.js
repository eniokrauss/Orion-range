const apiBaseInput = document.getElementById('api-base');
const apiKeyInput = document.getElementById('api-key');
const saveButton = document.getElementById('save-config');
const refreshButton = document.getElementById('refresh-mitre');
const statusText = document.getElementById('mitre-status');
const mitreList = document.getElementById('mitre-list');
const activeScenarios = document.getElementById('active-scenarios');

const getConfig = () => ({
  baseUrl: localStorage.getItem('orion.apiBase') || 'http://localhost:8000',
  apiKey: localStorage.getItem('orion.apiKey') || '',
});

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
  items.forEach((item) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <strong>${item.technique_id}</strong> — ${item.name}
      <small>${item.tactics.join(', ') || 'no tactics'} · action: ${item.action}</small>
    `;
    mitreList.appendChild(li);
  });
};

const fetchMitreTechniques = async () => {
  const config = getConfig();
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
    setStatus(`Erro ao carregar MITRE: ${error.message}`, 'error');
  }
};

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

bootstrap();
