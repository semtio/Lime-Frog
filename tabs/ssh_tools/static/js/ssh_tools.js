(function () {
  'use strict';

  const API = {
    LIST: '/api/ssh-tools/servers',
    CREATE: '/api/ssh-tools/servers',
    DELETE: (id) => `/api/ssh-tools/servers/${id}`,
    TEST: (id) => `/api/ssh-tools/servers/${id}/test`,
    EXEC: (id) => `/api/ssh-tools/servers/${id}/exec`,
    HOME_PATHS: (id) => `/api/ssh-tools/servers/${id}/home-paths`
  };

  const elements = {
    select: document.getElementById('ssh-server-select'),
    addBtn: document.getElementById('ssh-add-server'),
    editBtn: document.getElementById('ssh-edit-server'),
    deleteBtn: document.getElementById('ssh-delete-server'),
    testBtn: document.getElementById('ssh-test-connection'),
    status: document.getElementById('ssh-status'),
    consoleInput: document.getElementById('ssh-command-input'),
    consoleRun: document.getElementById('ssh-command-run'),
    consoleStatus: document.getElementById('ssh-command-status'),
    consoleOutput: document.getElementById('ssh-command-output'),
    consolePaths: document.getElementById('ssh-console-paths'),
    modal: document.getElementById('ssh-modal-overlay'),
    modalForm: document.getElementById('ssh-modal-form'),
    modalClose: document.getElementById('ssh-modal-close')
  };

  let currentMode = 'add';
  let editingServerId = null;

  if (!elements.select) {
    return;
  }

  try {
  function setStatus(message, type) {
    elements.status.textContent = message || '';
    elements.status.classList.remove('ok', 'error');
    if (type) {
      elements.status.classList.add(type);
    }
  }

  function setConsoleStatus(message, type) {
    if (!elements.consoleStatus) {
      return;
    }
    elements.consoleStatus.textContent = message || '';
    elements.consoleStatus.classList.remove('ok', 'error');
    if (type) {
      elements.consoleStatus.classList.add(type);
    }
  }

  function setConsolePaths(paths) {
    if (!elements.consolePaths) {
      return;
    }

    if (!paths || !paths.length) {
      elements.consolePaths.textContent = '';
      return;
    }

    elements.consolePaths.textContent = `Домены: ${paths.join(', ')}`;
  }

  function openModal(mode = 'add', server = null) {
    currentMode = mode;
    editingServerId = mode === 'edit' && server ? server.id : null;

    if (mode === 'edit' && server) {
      try {
        document.getElementById('ssh-name').value = server.name || '';
        document.getElementById('ssh-host').value = server.host || '';
        document.getElementById('ssh-port').value = server.port || 22;
        document.getElementById('ssh-username').value = server.username || '';
        document.getElementById('ssh-password').value = server.password || '';
      } catch (e) {
        // Ошибка заполнения формы
      }
    } else {
      elements.modalForm.reset();
      document.getElementById('ssh-port').value = '22';
    }

    elements.modal.classList.remove('hidden');
  }

  function closeModal() {
    elements.modal.classList.add('hidden');
    elements.modalForm.reset();
  }

  function setButtonsEnabled(enabled) {
    elements.deleteBtn.disabled = !enabled;
    elements.testBtn.disabled = !enabled;
    elements.editBtn.disabled = !enabled;
    if (elements.consoleRun) {
      elements.consoleRun.disabled = !enabled;
    }
    if (elements.consoleInput) {
      elements.consoleInput.disabled = !enabled;
    }
  }

  function renderServers(servers) {
    elements.select.innerHTML = '';
    if (!servers.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Серверы не добавлены';
      elements.select.appendChild(option);
      setButtonsEnabled(false);
      return;
    }

    servers.forEach((server) => {
      const option = document.createElement('option');
      option.value = server.id;
      option.textContent = `${server.name} (${server.host}:${server.port})`;
      elements.select.appendChild(option);
    });

    // Выбираем первый сервер по умолчанию
    if (elements.select.options.length > 0) {
      elements.select.options[0].selected = true;
      // Триггерим событие change чтобы активировать кнопки
      elements.select.dispatchEvent(new Event('change'));
    }

    setButtonsEnabled(true);
  }

  async function loadServers() {
    // Показать "Загрузка..."
    elements.select.innerHTML = '';
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Загрузка...';
    elements.select.appendChild(option);
    setButtonsEnabled(false);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 сек timeout

      const response = await fetch(API.LIST, {
        credentials: 'same-origin',
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        setStatus('Ошибка при загрузке списка серверов (HTTP ' + response.status + ')', 'error');
        elements.select.innerHTML = '';
        const errOption = document.createElement('option');
        errOption.value = '';
        errOption.textContent = 'Ошибка загрузки';
        elements.select.appendChild(errOption);
        return;
      }

      const data = await response.json();
      renderServers(data.servers || []);
      setStatus('Готово к подключению', null);
    } catch (error) {
      setStatus('Ошибка загрузки серверов: ' + (error.name === 'AbortError' ? 'timeout' : error.message), 'error');
      elements.select.innerHTML = '';
      const errOption = document.createElement('option');
      errOption.value = '';
      errOption.textContent = 'Ошибка: ' + (error.name === 'AbortError' ? 'timeout' : 'загрузка');
      elements.select.appendChild(errOption);
    }
  }

  async function addServer(payload) {
    const response = await fetch(API.CREATE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'Не удалось добавить сервер');
    }

    return response.json();
  }

  async function updateServer(serverId, payload) {
    const response = await fetch(`/api/ssh-tools/servers/${serverId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'Не удалось обновить сервер');
    }

    return response.json();
  }

  async function deleteServer(serverId) {
    const response = await fetch(API.DELETE(serverId), {
      method: 'DELETE',
      credentials: 'same-origin'
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'Не удалось удалить сервер');
    }
  }

  async function testServer(serverId) {
    const response = await fetch(API.TEST(serverId), {
      method: 'POST',
      credentials: 'same-origin'
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || 'Ошибка теста подключения');
    }

    return response.json();
  }

  async function executeCommand(serverId, command) {
    const response = await fetch(API.EXEC(serverId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ command })
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || 'Ошибка выполнения команды');
    }
    return data;
  }

  async function loadHomePaths(serverId) {
    if (!serverId) {
      setConsolePaths([]);
      return;
    }

    try {
      const response = await fetch(API.HOME_PATHS(serverId), {
        credentials: 'same-origin'
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setConsolePaths([]);
        return;
      }

      setConsolePaths(data.paths || []);
    } catch (error) {
      setConsolePaths([]);
    }
  }

  // Обработчик выбора сервера из списка
  elements.select.addEventListener('change', () => {
    const hasSelection = elements.select.value !== '';
    setButtonsEnabled(hasSelection);
    loadHomePaths(elements.select.value);
  });

  elements.addBtn.addEventListener('click', () => {
    openModal('add');
  });

  elements.editBtn.addEventListener('click', async () => {
    const serverId = elements.select.value;
    if (!serverId) {
      return;
    }

    try {
      const response = await fetch(`/api/ssh-tools/servers/${serverId}`, { credentials: 'same-origin' });
      if (!response.ok) {
        setStatus('Ошибка при загрузке данных сервера', 'error');
        return;
      }
      const server = await response.json();
      openModal('edit', server);
    } catch (error) {
      setStatus('Ошибка при загрузке данных сервера', 'error');
    }
  });

  elements.modalClose.addEventListener('click', () => {
    closeModal();
  });

  elements.modalForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(elements.modalForm);
    const payload = {
      name: String(formData.get('name') || '').trim(),
      host: String(formData.get('host') || '').trim(),
      port: Number(formData.get('port') || 22),
      username: String(formData.get('username') || '').trim(),
      password: String(formData.get('password') || '').trim()
    };

    if (!payload.name || !payload.host || !payload.username || !payload.password) {
      setStatus('Заполните все поля', 'error');
      return;
    }

    try {
      if (currentMode === 'add') {
        await addServer(payload);
        setStatus('Сервер добавлен', 'ok');
      } else if (currentMode === 'edit' && editingServerId) {
        await updateServer(editingServerId, payload);
        setStatus('Сервер обновлен', 'ok');
      }
      closeModal();
      await loadServers();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  if (elements.consoleRun && elements.consoleInput) {
    elements.consoleRun.addEventListener('click', async () => {
      const serverId = elements.select.value;
      const command = (elements.consoleInput.value || '').trimEnd();

      if (!serverId) {
        setConsoleStatus('Выберите сервер', 'error');
        return;
      }

      if (!command.trim()) {
        setConsoleStatus('Введите команду или скрипт', 'error');
        return;
      }

      setConsoleStatus('Выполняю...', null);
      if (elements.consoleOutput) {
        elements.consoleOutput.textContent = '';
      }
      elements.consoleRun.disabled = true;

      try {
        const result = await executeCommand(serverId, command);
        const stdout = result.stdout || '';
        const stderr = result.stderr || '';
        const exitCode = typeof result.exit_code === 'number' ? result.exit_code : null;

        if (elements.consoleOutput) {
          const combined = [
            stdout ? `STDOUT:\n${stdout}` : '',
            stderr ? `STDERR:\n${stderr}` : ''
          ].filter(Boolean).join('\n\n');
          elements.consoleOutput.textContent = combined || 'Команда выполнена без вывода.';
        }

        if (exitCode === 0 || exitCode === null) {
          setConsoleStatus('Готово', 'ok');
        } else {
          setConsoleStatus(`Завершено с кодом ${exitCode}`, 'error');
        }
      } catch (error) {
        setConsoleStatus(error.message || 'Ошибка выполнения команды', 'error');
        if (elements.consoleOutput) {
          elements.consoleOutput.textContent = error.message || 'Ошибка выполнения команды.';
        }
      } finally {
        elements.consoleRun.disabled = false;
      }
    });
  }

  elements.deleteBtn.addEventListener('click', async () => {
    const serverId = elements.select.value;
    if (!serverId) {
      return;
    }

    if (!confirm('Удалить сервер из списка?')) {
      return;
    }

    try {
      await deleteServer(serverId);
      setStatus('Сервер удален', 'ok');
      await loadServers();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  elements.testBtn.addEventListener('click', async () => {
    const serverId = elements.select.value;
    if (!serverId) {
      return;
    }

    setStatus('Проверяем подключение...', null);
    try {
      const result = await testServer(serverId);
      if (result.ok) {
        setStatus(result.message || 'Подключение успешно', 'ok');
      } else {
        setStatus(result.message || 'Ошибка подключения', 'error');
      }
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

  loadServers();
  } catch (error) {
    // Критическая ошибка
  }
})();
