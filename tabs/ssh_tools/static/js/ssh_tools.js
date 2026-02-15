(function () {
  'use strict';

  const API = {
    LIST: '/api/ssh-tools/servers',
    CREATE: '/api/ssh-tools/servers',
    DELETE: (id) => `/api/ssh-tools/servers/${id}`,
    TEST: (id) => `/api/ssh-tools/servers/${id}/test`
  };

  const elements = {
    select: document.getElementById('ssh-server-select'),
    addBtn: document.getElementById('ssh-add-server'),
    deleteBtn: document.getElementById('ssh-delete-server'),
    testBtn: document.getElementById('ssh-test-connection'),
    status: document.getElementById('ssh-status'),
    modal: document.getElementById('ssh-modal-overlay'),
    modalForm: document.getElementById('ssh-modal-form'),
    modalClose: document.getElementById('ssh-modal-close')
  };

  if (!elements.select) {
    return;
  }

  function setStatus(message, type) {
    elements.status.textContent = message || '';
    elements.status.classList.remove('ok', 'error');
    if (type) {
      elements.status.classList.add(type);
    }
  }

  function openModal() {
    elements.modal.classList.remove('hidden');
  }

  function closeModal() {
    elements.modal.classList.add('hidden');
    elements.modalForm.reset();
  }

  function setButtonsEnabled(enabled) {
    elements.deleteBtn.disabled = !enabled;
    elements.testBtn.disabled = !enabled;
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
    setButtonsEnabled(true);
  }

  async function loadServers() {
    try {
      const response = await fetch(API.LIST, { credentials: 'same-origin' });
      if (!response.ok) {
        setStatus('Не удалось загрузить список серверов', 'error');
        return;
      }
      const data = await response.json();
      renderServers(data.servers || []);
    } catch (error) {
      setStatus('Ошибка загрузки серверов', 'error');
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

  elements.addBtn.addEventListener('click', () => {
    openModal();
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
      await addServer(payload);
      setStatus('Сервер добавлен', 'ok');
      closeModal();
      await loadServers();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  });

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
})();
