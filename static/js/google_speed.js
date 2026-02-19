(function () {
  const urlsEl = document.getElementById('gs-urls');
  const startBtn = document.getElementById('gs-start-btn');
  const stopBtn = document.getElementById('gs-stop-btn');
  const downloadXlsxBtn = document.getElementById('gs-download-xlsx-btn');
  const clearBtn = document.getElementById('gs-clear-btn');
  const statusEl = document.getElementById('gs-status');
  const progressFill = document.getElementById('gs-progress-fill');
  const settingsBlock = document.getElementById('gs-settings');
  const toggleSettings = document.getElementById('gs-toggle-settings');
  const concurrencyEl = document.getElementById('gs-concurrency');
  const apiKeyEl = document.getElementById('gs-api-key');
  const strategyDesktopEl = document.getElementById('gs-strategy-desktop');
  const strategyMobileEl = document.getElementById('gs-strategy-mobile');
  const categoryPerformanceEl = document.getElementById('gs-category-performance');
  const categoryAccessibilityEl = document.getElementById('gs-category-accessibility');
  const categoryBestPracticesEl = document.getElementById('gs-category-best-practices');
  const categorySeoEl = document.getElementById('gs-category-seo');
  const validateKeyBtn = document.getElementById('gs-validate-key-btn');
  const apiKeyStatusEl = document.getElementById('gs-api-key-status');

  if (!urlsEl || !startBtn || !stopBtn || !downloadXlsxBtn || !clearBtn || !statusEl || !progressFill || !settingsBlock || !toggleSettings || !concurrencyEl || !apiKeyEl || !strategyDesktopEl || !strategyMobileEl || !categoryPerformanceEl || !categoryAccessibilityEl || !categoryBestPracticesEl || !categorySeoEl || !validateKeyBtn || !apiKeyStatusEl) {
    return;
  }

  const STORAGE_KEYS = {
    URLS: 'google-speed-urls',
    CONCURRENCY: 'google-speed-concurrency',
    API_KEY: 'google-speed-api-key',
    STRATEGIES: 'google-speed-strategies',
    CATEGORIES: 'google-speed-categories',
    JOB_ID: 'google-speed-job-id',
    DOWNLOAD_JOB_ID: 'google-speed-download-job-id'
  };

  let pollTimer = null;
  let jobId = localStorage.getItem(STORAGE_KEYS.JOB_ID);
  let downloadableJobId = localStorage.getItem(STORAGE_KEYS.DOWNLOAD_JOB_ID);
  let sessionId = sessionStorage.getItem('seo-session-id');
  if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 11);
    sessionStorage.setItem('seo-session-id', sessionId);
  }

  const setStatus = (text) => {
    statusEl.textContent = text;
  };

  const setProgress = (completed, total) => {
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    progressFill.style.width = pct + '%';
  };

  const selectedStrategies = () => {
    const values = [];
    if (strategyMobileEl.checked) values.push('mobile');
    if (strategyDesktopEl.checked) values.push('desktop');
    return values;
  };

  const selectedCategories = () => {
    const values = [];
    if (categoryPerformanceEl.checked) values.push('performance');
    if (categoryAccessibilityEl.checked) values.push('accessibility');
    if (categoryBestPracticesEl.checked) values.push('best-practices');
    if (categorySeoEl.checked) values.push('seo');
    return values;
  };

  const saveState = () => {
    localStorage.setItem(STORAGE_KEYS.URLS, urlsEl.value);
    localStorage.setItem(STORAGE_KEYS.CONCURRENCY, concurrencyEl.value);
    localStorage.setItem(STORAGE_KEYS.API_KEY, apiKeyEl.value);
    localStorage.setItem(STORAGE_KEYS.STRATEGIES, JSON.stringify(selectedStrategies()));
    localStorage.setItem(STORAGE_KEYS.CATEGORIES, JSON.stringify(selectedCategories()));
  };

  const loadState = () => {
    const savedUrls = localStorage.getItem(STORAGE_KEYS.URLS);
    if (savedUrls !== null) urlsEl.value = savedUrls;

    const savedConcurrency = localStorage.getItem(STORAGE_KEYS.CONCURRENCY);
    if (savedConcurrency) concurrencyEl.value = savedConcurrency;

    const savedApiKey = localStorage.getItem(STORAGE_KEYS.API_KEY);
    if (savedApiKey) apiKeyEl.value = savedApiKey;

    try {
      const savedStrategies = JSON.parse(localStorage.getItem(STORAGE_KEYS.STRATEGIES) || '[]');
      if (Array.isArray(savedStrategies) && savedStrategies.length) {
        strategyMobileEl.checked = savedStrategies.includes('mobile');
        strategyDesktopEl.checked = savedStrategies.includes('desktop');
      }
    } catch (e) {
      console.error('Ошибка загрузки стратегий Google Speed', e);
    }

    try {
      const savedCategories = JSON.parse(localStorage.getItem(STORAGE_KEYS.CATEGORIES) || '[]');
      if (Array.isArray(savedCategories) && savedCategories.length) {
        categoryPerformanceEl.checked = savedCategories.includes('performance');
        categoryAccessibilityEl.checked = savedCategories.includes('accessibility');
        categoryBestPracticesEl.checked = savedCategories.includes('best-practices');
        categorySeoEl.checked = savedCategories.includes('seo');
      }
    } catch (e) {
      console.error('Ошибка загрузки категорий Google Speed', e);
    }
  };

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const setIdleState = () => {
    startBtn.disabled = false;
    stopBtn.disabled = true;
  };

  const setRunningState = () => {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    downloadXlsxBtn.disabled = true;
  };

  async function pollStatus() {
    if (!jobId) return;
    try {
      const res = await fetch(`/api/google-speed/job/${jobId}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Ошибка статуса');
      }

      setProgress(data.completed || 0, data.total || 0);

      if (data.status === 'queued') {
        const queueInfo = data.queue_position ? ` (позиция в очереди: ${data.queue_position})` : '';
        setStatus(`В очереди${queueInfo}`);
        setRunningState();
        return;
      }

      if (data.status === 'running') {
        setStatus(`Обработано ${data.completed || 0} из ${data.total || 0}`);
        setRunningState();
        return;
      }

      if (data.status === 'completed') {
        setStatus('Проверка завершена');
        stopPolling();
        const finishedJobId = jobId;
        jobId = null;
        localStorage.removeItem(STORAGE_KEYS.JOB_ID);
        if (data.has_results && finishedJobId) {
          downloadableJobId = finishedJobId;
          localStorage.setItem(STORAGE_KEYS.DOWNLOAD_JOB_ID, downloadableJobId);
        }
        setIdleState();
        downloadXlsxBtn.disabled = !downloadableJobId;
        return;
      }

      if (data.status === 'stopped') {
        setStatus('Остановлено');
        stopPolling();
        const finishedJobId = jobId;
        jobId = null;
        localStorage.removeItem(STORAGE_KEYS.JOB_ID);
        if (data.has_results && finishedJobId) {
          downloadableJobId = finishedJobId;
          localStorage.setItem(STORAGE_KEYS.DOWNLOAD_JOB_ID, downloadableJobId);
        }
        setIdleState();
        downloadXlsxBtn.disabled = !downloadableJobId;
        return;
      }

      setStatus(data.error || 'Ошибка выполнения');
      stopPolling();
      const finishedJobId = jobId;
      jobId = null;
      localStorage.removeItem(STORAGE_KEYS.JOB_ID);
      if (data.has_results && finishedJobId) {
        downloadableJobId = finishedJobId;
        localStorage.setItem(STORAGE_KEYS.DOWNLOAD_JOB_ID, downloadableJobId);
      }
      setIdleState();
      downloadXlsxBtn.disabled = !downloadableJobId;
    } catch (err) {
      setStatus(err.message || 'Ошибка получения статуса');
      stopPolling();
      jobId = null;
      localStorage.removeItem(STORAGE_KEYS.JOB_ID);
      setIdleState();
    }
  }

  function startPolling() {
    stopPolling();
    pollStatus();
    pollTimer = setInterval(pollStatus, 1500);
  }

  toggleSettings.addEventListener('click', () => {
    settingsBlock.classList.toggle('open');
  });

  startBtn.addEventListener('click', async () => {
    saveState();

    const total = urlsEl.value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).length;
    if (!total) {
      setStatus('Добавьте хотя бы один домен');
      return;
    }

    if (!apiKeyEl.value.trim()) {
      setStatus('Укажите API-ключ');
      return;
    }

    const strategies = selectedStrategies();
    if (!strategies.length) {
      setStatus('Выберите хотя бы одну стратегию');
      return;
    }

    const categories = selectedCategories();
    if (!categories.length) {
      setStatus('Выберите хотя бы одну категорию');
      return;
    }

    const payload = {
      session_id: sessionId,
      urls: urlsEl.value,
      api_key: apiKeyEl.value.trim(),
      strategies,
      categories,
      runtime: {
        concurrency: Number(concurrencyEl.value || 5)
      }
    };

    setStatus('Запуск...');
    setProgress(0, 1);
    setRunningState();

    try {
      const res = await fetch('/api/google-speed/job', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Ошибка запуска');
      }

      jobId = data.job_id;
      localStorage.setItem(STORAGE_KEYS.JOB_ID, jobId);
      startPolling();
    } catch (err) {
      setStatus(err.message || 'Ошибка запуска');
      setIdleState();
      downloadXlsxBtn.disabled = !downloadableJobId;
    }
  });

  validateKeyBtn.addEventListener('click', async () => {
    const apiKey = apiKeyEl.value.trim();
    if (!apiKey) {
      apiKeyStatusEl.textContent = 'Введите API-ключ';
      return;
    }

    apiKeyStatusEl.textContent = 'Проверка...';
    validateKeyBtn.disabled = true;
    try {
      const res = await fetch('/api/google-speed/validate-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey })
      });
      const data = await res.json();
      apiKeyStatusEl.textContent = data.message || (data.valid ? 'API-ключ валиден' : 'Ключ не прошел проверку');
    } catch (e) {
      apiKeyStatusEl.textContent = 'Ошибка проверки API-ключа';
    } finally {
      validateKeyBtn.disabled = false;
    }
  });

  stopBtn.addEventListener('click', async () => {
    if (!jobId) {
      setIdleState();
      return;
    }
    try {
      await fetch(`/api/google-speed/job/${jobId}/stop`, { method: 'POST' });
    } catch (e) {
      console.error('Ошибка остановки Google Speed', e);
    }
    setStatus('Остановка...');
  });

  downloadXlsxBtn.addEventListener('click', () => {
    const downloadId = downloadableJobId || jobId;
    if (!downloadId) {
      setStatus('Нет задачи для скачивания');
      return;
    }
    const filename = 'google-speed';
    window.location.href = `/api/google-speed/job/${downloadId}/download-xlsx?filename=${encodeURIComponent(filename)}`;
  });

  clearBtn.addEventListener('click', () => {
    stopPolling();
    jobId = null;
    downloadableJobId = null;
    urlsEl.value = '';
    concurrencyEl.value = '5';
    apiKeyEl.value = '';
    apiKeyStatusEl.textContent = '';
    strategyMobileEl.checked = true;
    strategyDesktopEl.checked = true;
    categoryPerformanceEl.checked = true;
    categoryAccessibilityEl.checked = true;
    categoryBestPracticesEl.checked = true;
    categorySeoEl.checked = true;

    localStorage.removeItem(STORAGE_KEYS.URLS);
    localStorage.removeItem(STORAGE_KEYS.CONCURRENCY);
    localStorage.removeItem(STORAGE_KEYS.API_KEY);
    localStorage.removeItem(STORAGE_KEYS.STRATEGIES);
    localStorage.removeItem(STORAGE_KEYS.CATEGORIES);
    localStorage.removeItem(STORAGE_KEYS.JOB_ID);
    localStorage.removeItem(STORAGE_KEYS.DOWNLOAD_JOB_ID);

    setProgress(0, 1);
    downloadXlsxBtn.disabled = true;
    setIdleState();
    setStatus('Данные очищены');
  });

  [
    urlsEl,
    concurrencyEl,
    apiKeyEl,
    strategyDesktopEl,
    strategyMobileEl,
    categoryPerformanceEl,
    categoryAccessibilityEl,
    categoryBestPracticesEl,
    categorySeoEl
  ].forEach((el) => {
    el.addEventListener('input', saveState);
    el.addEventListener('change', saveState);
  });

  apiKeyEl.addEventListener('input', () => {
    apiKeyStatusEl.textContent = '';
  });

  loadState();
  setIdleState();
  downloadXlsxBtn.disabled = !downloadableJobId;
  if (jobId) {
    setRunningState();
    startPolling();
  }
})();
