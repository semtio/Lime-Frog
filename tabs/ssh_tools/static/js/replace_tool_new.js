/**
 * SSH Replace Tool - Frontend логика для поиска и замены текста в файлах
 */

(function () {
  'use strict';

  const API = {
    VALIDATE_PATHS: (id) => `/api/ssh-tools/servers/${id}/validate-paths`,
    PREVIEW: (id) => `/api/ssh-tools/servers/${id}/preview-replace`,
    EXECUTE: (id) => `/api/ssh-tools/servers/${id}/execute-replace`,
  };

  const elements = {
    // Основной контейнер
    panel: document.getElementById('replace-tool-panel'),
    // Домены/Пути
    domainsList: document.getElementById('replace-domains-list'),
    validateDomainsBtn: document.getElementById('replace-validate-domains'),
    domainsStats: document.getElementById('replace-domains-stats'),
    errorsSection: document.getElementById('replace-errors-section'),
    notFoundDomains: document.getElementById('replace-not-found-domains'),
    statAddedCount: document.getElementById('stat-added-count'),
    statFoundCount: document.getElementById('stat-found-count'),
    statErrorsCount: document.getElementById('stat-errors-count'),
    // Поиск и замена
    searchInput: document.getElementById('replace-search-text'),
    replacementsTextarea: document.getElementById('replace-replacements'),
    // Кнопки действия
    previewBtn: document.getElementById('replace-preview-btn'),
    executeBtn: document.getElementById('replace-execute-btn'),
    // Статус и результаты
    status: document.getElementById('replace-tool-status'),
    results: document.getElementById('replace-tool-results'),
  };

  // Проверить, доступен ли модуль
  if (!elements.panel || !elements.domainsList) {
    return;
  }

  let validatedDomains = [];  // Найденные на сервере пути

  // ========== Вспомогательные функции ==========

  /**
   * Очистить путь од схем, пробелов, запятых
   */
  function cleanPath(path) {
    if (!path) return '';

    return path
      .trim()
      .replace(/^https?:\/\//i, '')
      .replace(/^www\./i, '')
      .replace(/[,;]$/g, '')
      .trim()
      .toLowerCase();
  }

  /**
   * Получить список очищенных уникальных путей из TextArea
   */
  function getParsedPaths() {
    const rawText = elements.domainsList.value || '';
    const lines = rawText.split('\n');

    const paths = lines
      .map(line => cleanPath(line))
      .filter(path => path.length > 0);

    // Оставить только уникальные
    return [...new Set(paths)];
  }

  /**
   * Показать счётчик статистики
   */
  function updateDomainsStats(addedCount, foundCount, errorCount) {
    if (elements.statAddedCount) elements.statAddedCount.textContent = addedCount;
    if (elements.statFoundCount) elements.statFoundCount.textContent = foundCount;
    if (elements.statErrorsCount) elements.statErrorsCount.textContent = errorCount;

    if (elements.domainsStats) {
      elements.domainsStats.style.display = (addedCount > 0) ? 'flex' : 'none';
    }

    if (elements.errorsSection) {
      elements.errorsSection.style.display = (errorCount > 0) ? 'block' : 'none';
    }
  }

  /**
   * Показать ненайденные пути
   */
  function displayNotFoundPaths(notFoundList) {
    if (!elements.notFoundDomains) return;

    if (notFoundList.length === 0) {
      elements.notFoundDomains.value = '';
      return;
    }

    elements.notFoundDomains.value = notFoundList.join('\n');
  }

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

  // ========== Валидация путей ==========

  function setupValidateDomainsHandler() {
    if (!elements.validateDomainsBtn) return;

    elements.validateDomainsBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      const serverId = getCurrentServerId();

      if (!serverId) {
        setStatus('⚠️ Выберите сервер', 'error');
        return;
      }

      const paths = getParsedPaths();

      if (paths.length === 0) {
        setStatus('⚠️ Введите хотя бы один путь', 'error');
        return;
      }

      setStatus(`🔄 Проверяю ${paths.length} путь(ей)...`, 'info');
      elements.validateDomainsBtn.disabled = true;

      try {
        const response = await fetch(API.VALIDATE_PATHS(serverId), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paths: paths }),
        });

        const data = await response.json();

        if (response.ok) {
          validatedDomains = data.found || [];
          const notFound = data.not_found || [];

          updateDomainsStats(paths.length, validatedDomains.length, notFound.length);
          displayNotFoundPaths(notFound);

          setStatus(`✅ Найдено ${validatedDomains.length}/${paths.length} путей`, 'ok');

          // Включить поля поиска и замены если есть найденные пути
          if (validatedDomains.length > 0) {
            elements.searchInput.disabled = false;
            elements.replacementsTextarea.disabled = false;
            elements.previewBtn.disabled = false;
            elements.executeBtn.disabled = false;
            elements.searchInput.focus();
          } else {
            setStatus('⚠️ Не найдено ни одного пути', 'error');
            elements.searchInput.disabled = true;
            elements.replacementsTextarea.disabled = true;
            elements.previewBtn.disabled = true;
            elements.executeBtn.disabled = true;
          }
        } else {
          setStatus(`❌ ${data.error || 'Ошибка валидации'}`, 'error');
        }
      } catch (err) {
        setStatus(`❌ Ошибка: ${err.message}`, 'error');
      } finally {
        elements.validateDomainsBtn.disabled = false;
      }
    });
  }

  // ========== Предпросмотр ==========

  function setupPreviewHandler() {
    if (!elements.previewBtn) return;

    elements.previewBtn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (validatedDomains.length === 0) {
        setStatus('⚠️ Сначала проверьте пути файлов', 'error');
        return;
      }

      const searchText = elements.searchInput.value.trim();
      if (!searchText) {
        setStatus('⚠️ Укажите текст для поиска', 'error');
        return;
      }

      // Показать предпросмотр для первого файла
      const firstFile = validatedDomains[0];
      setStatus('🔄 Загрузка предпросмотра...', 'info');

      try {
        const response = await fetch(API.PREVIEW(getCurrentServerId()), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_path: firstFile,
            search_text: searchText,
            replace_text: '(замена будет применена)',
          }),
        });

        const data = await response.json();

        if (data.ok) {
          const preview = data.preview || {};
          const html = `
            <div class="replace-preview">
              <h4>Предпросмотр: ${firstFile}</h4>
              <p><strong>Найдено совпадений:</strong> ${preview.found_count || 0}</p>
              ${preview.preview_text ? `<pre><code>${escapeHtml(preview.preview_text)}</code></pre>` : ''}
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

  // ========== Выполнение замены ==========

  function setupExecuteHandler() {
    if (!elements.executeBtn) return;

    elements.executeBtn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (validatedDomains.length === 0) {
        setStatus('⚠️ Сначала проверьте пути файлов', 'error');
        return;
      }

      const searchText = elements.searchInput.value.trim();
      const replaceText = elements.replacementsTextarea.value.trim();

      if (!searchText) {
        setStatus('⚠️ Укажите текст для поиска', 'error');
        return;
      }

      if (!replaceText) {
        setStatus('⚠️ Укажите текст для замены', 'error');
        return;
      }

      // Запросить подтверждение
      if (!confirm(
        `Вы уверены? Будут обработаны ${validatedDomains.length} файл(ов).\n\n` +
        `Текст для поиска: ${searchText}\n` +
        `Текст для замены: ${replaceText}\n\n` +
        `Бэкапы будут созданы автоматически.`
      )) {
        return;
      }

      setStatus('🔄 Выполняю замену...', 'info');
      elements.executeBtn.disabled = true;

      try {
        const response = await fetch(API.EXECUTE(getCurrentServerId()), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            files: validatedDomains.map(path => ({ full_path: path })),
            search_text: searchText,
            replace_text: replaceText,
          }),
        });

        const data = await response.json();

        if (data.ok) {
          renderExecuteResults(data.details);
          setStatus(
            `✓ Замена завершена! Успешно: ${data.success_count}, Ошибок: ${data.error_count}`,
            data.error_count === 0 ? 'ok' : 'info'
          );
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
    if (!Array.isArray(details)) {
      details = [];
    }

    const html = `
      <div class="replace-results">
        <h4>Результаты замены</h4>
        <div class="replace-results-list">
          ${details.map((result) => `
            <div class="replace-result-item ${result.status === 'success' ? 'success' : 'error'}">
              <strong>${result.path || result.domain || 'N/A'}</strong>
              <p>${result.message}</p>
              ${result.backup_path ? `<small>Бэкап: ${result.backup_path}</small>` : ''}
              ${result.replacements_count ? `<small>Заменено: ${result.replacements_count} строк</small>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;
    setResults(html);
  }

  // ========== Инициализация ==========

  function init() {
    setupValidateDomainsHandler();
    setupPreviewHandler();
    setupExecuteHandler();

    // Отключить поля до валидации
    elements.searchInput.disabled = true;
    elements.replacementsTextarea.disabled = true;
    elements.previewBtn.disabled = true;
    elements.executeBtn.disabled = true;
  }

  // Запустить когда DOM готов
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
