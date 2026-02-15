/**
 * SSH Replace Tool - Frontend логика для поиска и замены текста в файлах
 */

(function () {
  'use strict';

  const API = {
    SET_BASE_PATH: (id) => `/api/ssh-tools/servers/${id}/set-base-path`,
    FIND_FILES: (id) => `/api/ssh-tools/servers/${id}/find-files`,
    PREVIEW: (id) => `/api/ssh-tools/servers/${id}/preview-replace`,
    EXECUTE: (id) => `/api/ssh-tools/servers/${id}/execute-replace`,
  };

  const elements = {
    // Основной контейнер
    panel: document.getElementById('replace-tool-panel'),
    // Шаг 1: Base Path
    basePathInput: document.getElementById('replace-base-path'),
    basePathBtn: document.getElementById('replace-confirm-base-path'),
    basePathStatus: document.getElementById('replace-base-path-status'),
    // Шаг 2: Relative Path
    relativePathInput: document.getElementById('replace-relative-path'),
    findFilesBtn: document.getElementById('replace-find-files'),
    filesList: document.getElementById('replace-files-list'),
    // Шаг 3: Поиск текста
    searchInput: document.getElementById('replace-search-text'),
    // Шаг 4: Замена текста
    replacementsTextarea: document.getElementById('replace-replacements'),
    // Кнопки действия
    previewBtn: document.getElementById('replace-preview-btn'),
    executeBtn: document.getElementById('replace-execute-btn'),
    // Статус и результаты
    status: document.getElementById('replace-tool-status'),
    results: document.getElementById('replace-tool-results'),
  };

  // Проверить, доступен ли модуль
  if (!elements.panel || !elements.basePathInput) {
    return;
  }

  let currentServer = null;
  let selectedFiles = [];

  function getCurrentServerId() {
    const select = document.getElementById('ssh-server-select');
    return select ? select.value : null;
  }

  function setStatus(message, type = null) {
    if (elements.status) {
      elements.status.textContent = message || '';
      elements.status.classList.remove('ok', 'error', 'info');
      if (type) {
        elements.status.classList.add(type);
      }
    }
  }

  function setResults(html) {
    if (elements.results) {
      elements.results.innerHTML = html;
      elements.results.style.display = html ? 'block' : 'none';
    }
  }

  // ========== Шаг 1: Установка Base Path ==========

  function setupBasePathHandler() {
    if (!elements.basePathBtn) return;

    elements.basePathBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const serverId = getCurrentServerId();
      const basePath = elements.basePathInput.value.trim();

      if (!serverId) {
        setStatus('⚠️ Выберите сервер', 'error');
        return;
      }

      if (!basePath) {
        setStatus('⚠️ Укажите путь до папки с доменами', 'error');
        return;
      }

      setStatus('🔄 Проверка пути...', 'info');
      elements.basePathBtn.disabled = true;

      try {
        const response = await fetch(API.SET_BASE_PATH(serverId), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_path: basePath }),
        });

        const data = await response.json();

        if (response.ok) {
          currentServer = serverId;
          setStatus(data.message, 'ok');

          elements.basePathInput.disabled = true;
          elements.basePathBtn.disabled = true;
          elements.relativePathInput.disabled = false;
          elements.findFilesBtn.disabled = false;
          elements.relativePathInput.focus();
        } else {
          setStatus(`❌ ${data.error || 'Ошибка проверки пути'}`, 'error');
        }
      } catch (err) {
        setStatus(`❌ Ошибка: ${err.message}`, 'error');
      } finally {
        elements.basePathBtn.disabled = false;
      }
    });
  }

  // ========== Шаг 2: Поиск файлов ==========

  function setupFindFilesHandler() {
    if (!elements.findFilesBtn) return;

    elements.findFilesBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const serverId = currentServer || getCurrentServerId();
      const relativePath = elements.relativePathInput.value.trim();

      if (!serverId) {
        setStatus('⚠️ Выберите сервер и установите base path', 'error');
        return;
      }

      if (!relativePath) {
        setStatus('⚠️ Укажите относительный путь до файла', 'error');
        return;
      }

      setStatus('🔄 Поиск файлов...', 'info');
      elements.findFilesBtn.disabled = true;

      try {
        const url = new URL(API.FIND_FILES(serverId), window.location.origin);
        url.searchParams.append('relative_path', relativePath);

        const response = await fetch(url.toString());
        const data = await response.json();

        if (data.ok && data.files) {
          selectedFiles = data.files;
          renderFilesList(data.files);
          setStatus(`✓ Найдено ${data.files.length} файл(ов)`, 'ok');
          renderReplacementsTemplate(data.files);
        } else {
          setStatus(`❌ ${data.files?.[0]?.error || 'Файлы не найдены'}`, 'error');
        }
      } catch (err) {
        setStatus(`❌ Ошибка: ${err.message}`, 'error');
      } finally {
        elements.findFilesBtn.disabled = false;
      }
    });
  }

  function renderFilesList(files) {
    if (!elements.filesList) return;

    const html = files.map((file, index) => `
      <div class="replace-file-item">
        <strong>${index + 1}. ${file.domain}</strong>
        <code>${file.full_path}</code>
      </div>
    `).join('');

    elements.filesList.innerHTML = html;

    // Разблокировать поля после успешного поиска
    if (elements.searchInput) elements.searchInput.disabled = false;
    if (elements.replacementsTextarea) elements.replacementsTextarea.disabled = false;
    if (elements.previewBtn) elements.previewBtn.disabled = false;
    if (elements.executeBtn) elements.executeBtn.disabled = false;
  }

  function renderReplacementsTemplate(files) {
    if (!elements.replacementsTextarea) return;

    // Создать шаблон: по одной строке на домен
    const template = files.map((file) => `# ${file.domain}`).join('\n');
    elements.replacementsTextarea.placeholder = `Введите замену для каждого домена (по одной строке на домен)\n\nПример:\n${template}`;
  }

  // ========== Шаг 3-4: Предпросмотр и Замена ==========

  function setupPreviewHandler() {
    if (!elements.previewBtn) return;

    elements.previewBtn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (selectedFiles.length === 0) {
        setStatus('⚠️ Сначала найдите файлы', 'error');
        return;
      }

      const searchText = elements.searchInput.value.trim();
      if (!searchText) {
        setStatus('⚠️ Укажите текст для поиска', 'error');
        return;
      }

      // Показать предпросмотр для первого файла
      const firstFile = selectedFiles[0];
      setStatus('🔄 Загрузка предпросмотра...', 'info');

      try {
        const response = await fetch(API.PREVIEW(currentServer || getCurrentServerId()), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_path: firstFile.full_path,
            search_text: searchText,
            replace_text: '(замена выполнится после применения)',
          }),
        });

        const data = await response.json();

        if (data.ok) {
          const preview = data.preview;
          const html = `
            <div class="replace-preview">
              <h4>Предпросмотр замены в ${firstFile.domain}</h4>
              <p><strong>Вхождений найдено:</strong> ${preview.found_count}</p>

              <div class="replace-preview-before">
                <strong>До:</strong>
                <code>${escapeHtml(preview.before)}</code>
              </div>

              <div class="replace-preview-after">
                <strong>После:</strong>
                <code>${escapeHtml(preview.after)}</code>
              </div>

              ${preview.will_replace_all ? '<p style="color: orange;">⚠️ ВНИМАНИЕ: будут заменены ВСЕ вхождения</p>' : ''}
            </div>
          `;
          setResults(html);
          setStatus('✓ Предпросмотр готов', 'ok');
        } else {
          setStatus(`❌ ${data.error || 'Ошибка предпросмотра'}`, 'error');
        }
      } catch (err) {
        setStatus(`❌ Ошибка: ${err.message}`, 'error');
      }
    });
  }

  function setupExecuteHandler() {
    if (!elements.executeBtn) return;

    elements.executeBtn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (selectedFiles.length === 0) {
        setStatus('⚠️ Сначала найдите файлы', 'error');
        return;
      }

      const searchText = elements.searchInput.value.trim();
      const replacementsText = elements.replacementsTextarea.value.trim();

      if (!searchText) {
        setStatus('⚠️ Укажите текст для поиска', 'error');
        return;
      }

      if (!replacementsText) {
        setStatus('⚠️ Укажите замены для доменов', 'error');
        return;
      }

      // Парсить замены: строка = домен -> замена
      const replacementsLines = replacementsText.split('\n').filter((l) => l.trim());
      const replacements = {};

      selectedFiles.forEach((file, index) => {
        replacements[file.domain] = replacementsLines[index] || '';
      });

      // Проверить, что замены совпадают с количеством файлов
      if (Object.values(replacements).some((v) => !v)) {
        setStatus('⚠️ Количество строк замены не совпадает с количеством файлов', 'error');
        return;
      }

      // Запросить подтверждение
      if (!confirm(`Вы уверены? Будут заменены ${selectedFiles.length} файл(ов). Бэкапы будут созданы автоматически.`)) {
        return;
      }

      setStatus('🔄 Выполняю замену...', 'info');
      elements.executeBtn.disabled = true;

      try {
        const response = await fetch(API.EXECUTE(currentServer || getCurrentServerId()), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            files: selectedFiles,
            search_text: searchText,
            replacements: replacements,
          }),
        });

        const data = await response.json();

        if (data.ok) {
          renderExecuteResults(data.details);
          setStatus(`✓ Замена завершена! Успешно: ${data.success_count}, Ошибок: ${data.error_count}`, 'ok');
        } else {
          setStatus(`❌ ${data.error || 'Ошибка выполнения'}`, 'error');
        }
      } catch (err) {
        setStatus(`❌ Ошибка: ${err.message}`, 'error');
      } finally {
        elements.executeBtn.disabled = false;
      }
    });
  }

  function renderExecuteResults(details) {
    const html = `
      <div class="replace-results">
        <h4>Результаты замены</h4>
        ${details.map((result) => `
          <div class="replace-result-item ${result.status === 'success' ? 'success' : 'error'}">
            <strong>${result.domain}</strong>
            <p>${result.message}</p>
            ${result.backup_path ? `<small>Бэкап: ${result.backup_path}</small>` : ''}
            ${result.replacements_count ? `<small>Заменено: ${result.replacements_count}</small>` : ''}
          </div>
        `).join('')}
      </div>
    `;
    setResults(html);
  }

  function escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
  }

  // ========== Инициализация ==========

  function init() {
    setupBasePathHandler();
    setupFindFilesHandler();
    setupPreviewHandler();
    setupExecuteHandler();
  }

  // Запустить когда DOM готов
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
