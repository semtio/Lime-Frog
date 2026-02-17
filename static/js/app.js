const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const downloadBtn = document.getElementById('download-btn');
const downloadXlsxBtn = document.getElementById('download-xlsx-btn');
const headingDownloadBtn = document.getElementById('heading-download-btn');
const clearBtn = document.getElementById('clear-btn');
const statusEl = document.getElementById('status');
const progressFill = document.getElementById('progress-fill');
const resourceEl = document.getElementById('resource');
const badge = document.getElementById('job-badge');
const settingsBlock = document.getElementById('settings');
const toggleSettings = document.getElementById('toggle-settings');
const magicLinksCards = document.getElementById('magic-links-cards');
const magicLinksAddBtn = document.getElementById('magic-links-add');
const magicLinksCardTemplate = document.getElementById('magic-links-card-template');
const statsDisplay = document.getElementById('stats-display');
const activeUsersEl = document.getElementById('active-users');
const queueCountEl = document.getElementById('queue-count');
const toolSelect = document.getElementById('tool-select');
const toolViews = document.querySelectorAll('[data-tool-view]');

const TOOL_STORAGE_KEY = 'active-tool';

let pollTimer = null;
let jobId = localStorage.getItem('seo-job-id');

// Генерация уникального ID сессии для данной вкладки
let sessionId = sessionStorage.getItem('seo-session-id');
if (!sessionId) {
  sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  sessionStorage.setItem('seo-session-id', sessionId);
}

// Отправка heartbeat для регистрации активной вкладки
async function sendHeartbeat() {
  try {
    await fetch('/api/heartbeat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId })
    });
  } catch (e) {
    /* ignore */
  }
}

function setActiveTool(toolName, updateUrl = true) {
  if (!toolSelect) return;
  const option = toolSelect.querySelector(`option[value="${toolName}"]`) || toolSelect.options[0];
  if (!option) return;

  const selectedName = option.value;
  toolSelect.value = selectedName;
  toolViews.forEach(view => {
    view.classList.toggle('active', view.dataset.toolView === selectedName);
  });

  if (option.dataset.title) document.title = option.dataset.title;

  localStorage.setItem(TOOL_STORAGE_KEY, selectedName);

  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set('module', selectedName);
    history.replaceState({}, '', url.toString());
  }
}

// ========== Функции для работы с localStorage ==========
const STORAGE_KEYS = {
  URLS: 'seo-urls-list',
  SETTINGS: 'seo-settings',
  RUNTIME: 'seo-runtime'
};

// Сохранить все данные
function saveAllData() {
  // Сохранить домены
  const urls = document.getElementById('urls').value;
  localStorage.setItem(STORAGE_KEYS.URLS, urls);

  // Сохранить настройки проверок
  const settings = {};
  document.querySelectorAll('input[type="checkbox"][data-option]').forEach(cb => {
    settings[cb.dataset.option] = cb.checked;
  });
  localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));

  // Сохранить параметры запуска
  const runtime = {
    concurrency: document.getElementById('concurrency').value,
    timeout: document.getElementById('timeout').value,
    retries: document.getElementById('retries').value,
    filename: document.getElementById('filename').value
  };
  localStorage.setItem(STORAGE_KEYS.RUNTIME, JSON.stringify(runtime));
}

// Загрузить все данные
function loadAllData() {
  // Загрузить домены
  const savedUrls = localStorage.getItem(STORAGE_KEYS.URLS);
  if (savedUrls) {
    document.getElementById('urls').value = savedUrls;
  }

  // Загрузить настройки проверок
  const savedSettings = localStorage.getItem(STORAGE_KEYS.SETTINGS);
  if (savedSettings) {
    try {
      const settings = JSON.parse(savedSettings);
      document.querySelectorAll('input[type="checkbox"][data-option]').forEach(cb => {
        if (cb.dataset.option in settings) {
          cb.checked = settings[cb.dataset.option];
        }
      });
    } catch (e) {
      console.error('Ошибка загрузки настроек:', e);
    }
  }

  // Загрузить параметры запуска
  const savedRuntime = localStorage.getItem(STORAGE_KEYS.RUNTIME);
  if (savedRuntime) {
    try {
      const runtime = JSON.parse(savedRuntime);
      if (runtime.concurrency) document.getElementById('concurrency').value = runtime.concurrency;
      if (runtime.timeout) document.getElementById('timeout').value = runtime.timeout;
      if (runtime.retries) document.getElementById('retries').value = runtime.retries;
      if (runtime.filename) document.getElementById('filename').value = runtime.filename;
    } catch (e) {
      console.error('Ошибка загрузки параметров:', e);
    }
  }
}

// Очистить все сохранённые данные
function clearAllData() {
  if (confirm('Вы уверены? Будут очищены все сохранённые домены и настройки.')) {
    localStorage.removeItem(STORAGE_KEYS.URLS);
    localStorage.removeItem(STORAGE_KEYS.SETTINGS);
    localStorage.removeItem(STORAGE_KEYS.RUNTIME);
    // Очистить форму
    document.getElementById('urls').value = '';
    setStatus('Данные очищены');
  }
}

// ========== Инициализация ==========
loadAllData();
updateToggleButtons();

if (toolSelect) {
  const defaultTool = document.body.dataset.defaultTool;
  const savedTool = localStorage.getItem(TOOL_STORAGE_KEY);
  const params = new URLSearchParams(window.location.search);
  const queryTool = params.get('module');
  const initialTool = queryTool || savedTool || defaultTool || toolSelect.value;
  setActiveTool(initialTool, false);

  toolSelect.addEventListener('change', (event) => {
    setActiveTool(event.target.value, true);
  });
}

const setStatus = (text) => statusEl.textContent = text;
const setProgress = (completed, total) => {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  progressFill.style.width = pct + '%';
  statusEl.textContent = total ? `Обработано ${completed} из ${total} (${pct}%)` : 'Готово';
};

toggleSettings.addEventListener('click', () => {
  settingsBlock.classList.toggle('open');
});

function initMagicLinksCard(card) {
  if (card.dataset.mlBound === '1') return;
  card.dataset.mlBound = '1';

  const toggle = card.querySelector('[data-ml-toggle]');
  const settings = card.querySelector('[data-ml-settings]');
  if (toggle && settings) {
    toggle.addEventListener('click', () => {
      settings.classList.toggle('open');
    });
  }

  bindMagicLinksActions(card);
}

function applyMagicLinksIndex(card, index) {
  card.querySelectorAll('[data-ml-id]').forEach(el => {
    const baseId = el.dataset.mlId;
    el.id = `${baseId}-${index}`;
  });

  card.querySelectorAll('[data-ml-for]').forEach(label => {
    const baseFor = label.dataset.mlFor;
    label.setAttribute('for', `${baseFor}-${index}`);
  });

  card.querySelectorAll('[data-ml-name]').forEach(input => {
    const baseName = input.dataset.mlName;
    input.name = `${baseName}-${index}`;
  });
}

if (magicLinksCards) {
  const initialCards = magicLinksCards.querySelectorAll('[data-ml-card]');
  initialCards.forEach((card, idx) => {
    applyMagicLinksIndex(card, idx + 1);
    initMagicLinksCard(card);
  });
  updateMagicLinksAddState();
}

if (magicLinksAddBtn && magicLinksCardTemplate && magicLinksCards) {
  magicLinksAddBtn.addEventListener('click', () => {
    if (magicLinksCards.querySelectorAll('[data-ml-card]').length >= 6) {
      updateMagicLinksAddState();
      return;
    }
    const nextIndex = magicLinksCards.querySelectorAll('[data-ml-card]').length + 1;
    const fragment = magicLinksCardTemplate.content.cloneNode(true);
    const card = fragment.querySelector('[data-ml-card]');
    applyMagicLinksIndex(card, nextIndex);
    initMagicLinksCard(card);
    magicLinksCards.appendChild(fragment);
    updateMagicLinksAddState();
  });
}

const magicLinksPollers = new Map();

function updateMagicLinksAddState() {
  if (!magicLinksAddBtn || !magicLinksCards) return;
  const count = magicLinksCards.querySelectorAll('[data-ml-card]').length;
  magicLinksAddBtn.disabled = count >= 6;
  magicLinksAddBtn.title = count >= 6 ? 'Достигнут лимит (6)' : 'Добавить еще одну пару';
}

function getMagicLinksElements(card) {
  return {
    source: card.querySelector('[data-ml-id="magic-links-source"]'),
    target: card.querySelector('[data-ml-id="magic-links-target"]'),
    startBtn: card.querySelector('[data-ml-id="magic-links-start-btn"]'),
    stopBtn: card.querySelector('[data-ml-id="magic-links-stop-btn"]'),
    downloadBtn: card.querySelector('[data-ml-id="magic-links-download-xlsx-btn"]'),
    clearBtn: card.querySelector('[data-ml-id="magic-links-clear-btn"]'),
    status: card.querySelector('[data-ml-id="magic-links-status"]'),
    progressFill: card.querySelector('[data-ml-id="magic-links-progress-fill"]'),
    filename: card.querySelector('[data-ml-id="magic-links-filename"]'),
    concurrency: card.querySelector('[data-ml-id="magic-links-concurrency"]'),
    timeout: card.querySelector('[data-ml-id="magic-links-timeout"]'),
    retries: card.querySelector('[data-ml-id="magic-links-retries"]')
  };
}

function setMagicLinksStatus(card, text) {
  const elements = getMagicLinksElements(card);
  if (elements.status) elements.status.textContent = text;
}

function setMagicLinksProgress(card, completed, total) {
  const elements = getMagicLinksElements(card);
  if (!elements.progressFill) return;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  elements.progressFill.style.width = pct + '%';
}

function getMagicLinksMode(card) {
  const selected = card.querySelector('input[data-ml-name="magic-links-mode"]:checked');
  return selected ? selected.value : 'anchor';
}

function getMagicLinksRuntime(card) {
  const elements = getMagicLinksElements(card);
  return {
    concurrency: Number(elements.concurrency?.value || 3),
    timeout_seconds: Number(elements.timeout?.value || 15),
    retries: Number(elements.retries?.value || 2)
  };
}

async function startMagicLinksJob(card) {
  const elements = getMagicLinksElements(card);
  if (!elements.source || !elements.target) return;

  const sources = elements.source.value.trim();
  const targets = elements.target.value.trim();
  if (!sources && !targets) {
    setMagicLinksStatus(card, 'Добавьте хотя бы одну пару');
    return;
  }

  const payload = {
    session_id: sessionId,
    sources,
    targets,
    mode: getMagicLinksMode(card),
    runtime: getMagicLinksRuntime(card)
  };

  elements.startBtn.disabled = true;
  elements.stopBtn.disabled = false;
  elements.downloadBtn.disabled = true;
  setMagicLinksStatus(card, 'Запуск...');

  try {
    const res = await fetch('/api/magic-links/job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Ошибка запуска');
    card.dataset.mlJobId = data.job_id;
    pollMagicLinksStatus(card);
  } catch (err) {
    setMagicLinksStatus(card, err.message);
    elements.startBtn.disabled = false;
    elements.stopBtn.disabled = true;
  }
}

async function pollMagicLinksStatus(card) {
  const jobId = card.dataset.mlJobId;
  if (!jobId) return;

  if (magicLinksPollers.has(card)) {
    clearInterval(magicLinksPollers.get(card));
  }

  const elements = getMagicLinksElements(card);
  const fetchStatus = async () => {
    const res = await fetch(`/api/magic-links/job/${jobId}`);
    if (res.status === 404) {
      clearInterval(magicLinksPollers.get(card));
      magicLinksPollers.delete(card);
      delete card.dataset.mlJobId;
      setMagicLinksStatus(card, 'Задача не найдена');
      elements.startBtn.disabled = false;
      elements.stopBtn.disabled = true;
      elements.downloadBtn.disabled = true;
      return;
    }
    const data = await res.json();
    const { status, completed, total, error, queue_position } = data;
    setMagicLinksProgress(card, completed, total);

    let statusText = '';
    if (status === 'queued' && queue_position > 0) {
      statusText = `В очереди: позиция ${queue_position}`;
    } else if (status === 'running') {
      statusText = `Статус: выполняется. ${completed}/${total}`;
    } else {
      statusText = `Статус: ${status}. Выполнено ${completed}/${total}`;
    }
    if (error) statusText += `, ошибка: ${error}`;
    setMagicLinksStatus(card, statusText);

    elements.stopBtn.disabled = status !== 'running' && status !== 'queued';
    if (status === 'completed' || status === 'stopped' || status === 'error') {
      clearInterval(magicLinksPollers.get(card));
      magicLinksPollers.delete(card);
      elements.startBtn.disabled = false;
      elements.downloadBtn.disabled = !data.has_results;
    }
  };

  await fetchStatus();
  const timer = setInterval(fetchStatus, 2000);
  magicLinksPollers.set(card, timer);
}

async function stopMagicLinksJob(card) {
  const jobId = card.dataset.mlJobId;
  if (!jobId) return;
  await fetch(`/api/magic-links/job/${jobId}/stop`, { method: 'POST' });
  setMagicLinksStatus(card, 'Остановка...');
}

function downloadMagicLinksXlsx(card) {
  const jobId = card.dataset.mlJobId;
  if (!jobId) return;
  const elements = getMagicLinksElements(card);
  const customName = elements.filename?.value.trim();
  const url = customName
    ? `/api/magic-links/job/${jobId}/download-xlsx?filename=${encodeURIComponent(customName)}`
    : `/api/magic-links/job/${jobId}/download-xlsx`;
  window.location.href = url;
}

function clearMagicLinksCard(card) {
  const elements = getMagicLinksElements(card);
  if (elements.source) elements.source.value = '';
  if (elements.target) elements.target.value = '';
  if (elements.progressFill) elements.progressFill.style.width = '0%';
  if (elements.downloadBtn) elements.downloadBtn.disabled = true;
  setMagicLinksStatus(card, 'Готово к запуску');
}

function bindMagicLinksActions(card) {
  const elements = getMagicLinksElements(card);
  elements.startBtn?.addEventListener('click', () => startMagicLinksJob(card));
  elements.stopBtn?.addEventListener('click', () => stopMagicLinksJob(card));
  elements.downloadBtn?.addEventListener('click', () => downloadMagicLinksXlsx(card));
  elements.clearBtn?.addEventListener('click', () => clearMagicLinksCard(card));
}

// ========== Функция для обновления состояния кнопок переключения ==========
function updateToggleButtons() {
  document.querySelectorAll('.toggle-all-btn').forEach(btn => {
    const groupClass = btn.dataset.group;
    const section = btn.closest('.checks-section').querySelector(`.${groupClass}`);
    const checkboxes = section.querySelectorAll('input[type="checkbox"]');
    const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
    const totalCount = checkboxes.length;

    // Если все выбраны - показываем "Убрать всё"
    if (checkedCount === totalCount) {
      btn.textContent = 'Убрать всё';
      btn.classList.add('all-checked');
    } else {
      btn.textContent = 'Выбрать всё';
      btn.classList.remove('all-checked');
    }
  });
}

// ========== Обработчики для переключающейся кнопки ==========
document.querySelectorAll('.toggle-all-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    const groupClass = btn.dataset.group;
    const section = btn.closest('.checks-section').querySelector(`.${groupClass}`);
    const checkboxes = section.querySelectorAll('input[type="checkbox"]');
    const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
    const totalCount = checkboxes.length;

    // Если все выбраны - убираем все, иначе выбираем все
    const shouldCheck = checkedCount !== totalCount;
    checkboxes.forEach(cb => {
      cb.checked = shouldCheck;
    });

    saveAllData();
    updateToggleButtons();
  });
});

// Расподчик на изменение чекбоксов для обновления кнопок
document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
  checkbox.addEventListener('change', () => {
    updateToggleButtons();
  });
});

async function startJob() {
  const urls = document.getElementById('urls').value.trim();
  if (!urls) { setStatus('Добавьте хотя бы один домен'); return; }
  // Сохранить данные перед запуском
  saveAllData();
  const options = {};
  document.querySelectorAll('input[type="checkbox"][data-option]').forEach(cb => {
    options[cb.dataset.option] = cb.checked;
  });
  const payload = {
    session_id: sessionId,
    urls,
    options,
    runtime: {
      concurrency: Number(document.getElementById('concurrency').value || 3),
      timeout_seconds: Number(document.getElementById('timeout').value || 15),
      retries: Number(document.getElementById('retries').value || 2),
    }
  };
  startBtn.disabled = true;
  stopBtn.disabled = false;
  downloadBtn.disabled = true;
  setStatus('Запуск...');
  try {
    const res = await fetch('/api/job', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Ошибка запуска');
    jobId = data.job_id;
    localStorage.setItem('seo-job-id', jobId);
    badge.style.display = 'inline-flex';
    pollStatus();
  } catch (err) {
    setStatus(err.message);
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
}

async function pollStatus() {
  if (!jobId) return;
  clearInterval(pollTimer);
  const fetchStatus = async () => {
    const res = await fetch(`/api/job/${jobId}`);
    if (res.status === 404) {
      clearInterval(pollTimer);
      localStorage.removeItem('seo-job-id');
      jobId = null;
      badge.style.display = 'none';
      setStatus('Задача не найдена');
      startBtn.disabled = false;
      stopBtn.disabled = true;
      downloadBtn.disabled = true;
      return;
    }
    const data = await res.json();
    const { status, completed, total, error, queue_position } = data;
    const pct = total ? Math.round((completed / total) * 100) : 0;
    progressFill.style.width = pct + '%';

    // Отобразить позицию в очереди
    let statusText = '';
    if (status === 'queued' && queue_position > 0) {
      statusText = `В очереди: позиция ${queue_position}`;
      badge.style.display = 'inline-flex';
      badge.textContent = `В очереди #${queue_position}`;
    } else if (status === 'running') {
      statusText = `Статус: выполняется. ${completed}/${total}`;
      badge.style.display = 'inline-flex';
      badge.textContent = 'Задача активна';
    } else {
      statusText = `Статус: ${status}. Выполнено ${completed}/${total}`;
      badge.style.display = 'none';
    }

    if (error) statusText += `, ошибка: ${error}`;
    setStatus(statusText);

    stopBtn.disabled = status !== 'running' && status !== 'queued';
    if (status === 'completed' || status === 'stopped' || status === 'error') {
      clearInterval(pollTimer);
      startBtn.disabled = false;
      downloadBtn.disabled = !data.has_results;
      downloadXlsxBtn.disabled = !data.has_results;
      if (headingDownloadBtn) headingDownloadBtn.disabled = !data.has_results;
      if (!data.has_results) localStorage.removeItem('seo-job-id');
    }
  };
  await fetchStatus();
  pollTimer = setInterval(fetchStatus, 2000);
}

async function stopJob() {
  if (!jobId) return;
  await fetch(`/api/job/${jobId}/stop`, { method: 'POST' });
  setStatus('Остановка...');
}

async function downloadCsv() {
  if (!jobId) return;
  const customName = document.getElementById('filename').value.trim();
  const url = customName
    ? `/api/job/${jobId}/download?filename=${encodeURIComponent(customName)}`
    : `/api/job/${jobId}/download`;
  window.location.href = url;
}

async function downloadXlsx() {
  if (!jobId) return;
  const customName = document.getElementById('filename').value.trim();
  const url = customName
    ? `/api/job/${jobId}/download-xlsx?filename=${encodeURIComponent(customName)}`
    : `/api/job/${jobId}/download-xlsx`;
  window.location.href = url;
}

async function downloadHeadingsXlsx() {
  if (!jobId) return;
  const customName = document.getElementById('filename').value.trim();

  // Получить выбранные заголовки
  const headingCheckboxes = document.querySelectorAll('input[data-option^="collect_h"]');
  const enabledHeadings = [];
  headingCheckboxes.forEach(cb => {
    if (cb.checked) {
      const hTag = cb.dataset.option.replace('collect_', '').toUpperCase();
      enabledHeadings.push(hTag);
    }
  });

  let url = `/api/job/${jobId}/download-headings-xlsx`;
  const params = new URLSearchParams();
  if (customName) params.append('filename', customName);
  if (enabledHeadings.length > 0) params.append('headings', enabledHeadings.join(','));

  if (params.toString()) {
    url += '?' + params.toString();
  }
  window.location.href = url;
}

async function fetchResource() {
  try {
    const res = await fetch('/api/resource');
    const data = await res.json();
    if (data.available) {
      resourceEl.style.display = 'block';
      resourceEl.textContent = `CPU: ${data.cpu}% | RAM: ${data.memory_percent}%`;
    }
  } catch (e) {
    /* ignore */
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    // Всегда показывать статистику
    activeUsersEl.textContent = data.active_users || 0;
    queueCountEl.textContent = data.queued || 0;
  } catch (e) {
    /* ignore */
  }
}

startBtn.addEventListener('click', startJob);
stopBtn.addEventListener('click', stopJob);
downloadBtn.addEventListener('click', downloadCsv);
downloadXlsxBtn.addEventListener('click', downloadXlsx);
if (headingDownloadBtn) headingDownloadBtn.addEventListener('click', downloadHeadingsXlsx);
clearBtn.addEventListener('click', clearAllData);

// Сохранять данные при изменении
document.getElementById('urls').addEventListener('change', saveAllData);
document.getElementById('concurrency').addEventListener('change', saveAllData);
document.getElementById('timeout').addEventListener('change', saveAllData);
document.getElementById('retries').addEventListener('change', saveAllData);
document.getElementById('filename').addEventListener('change', saveAllData);
document.querySelectorAll('input[type="checkbox"][data-option]').forEach(cb => {
  cb.addEventListener('change', saveAllData);
});

if (jobId) { pollStatus(); }
setInterval(fetchResource, 5000);
setInterval(fetchStats, 3000);
setInterval(sendHeartbeat, 5000); // Отправлять heartbeat каждые 5 секунд
fetchStats(); // Загрузить сразу
sendHeartbeat(); // Отправить сразу при загрузке
