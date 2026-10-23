(() => {
  const list = document.getElementById('seo-column-order');
  if (!list) return;
  const storageKey = 'seo-column-order-v1';
  const cards = () => [...list.querySelectorAll('[data-column-group]')];
  const defaults = cards().map(card => card.dataset.columnGroup);
  const status = document.getElementById('seo-sort-status');
  const settings = document.getElementById('settings');
  let dragged = null;
  let dropTarget = null;
  let pointerStart = null;

  const letter = index => {
    let value = '';
    for (let n = index; n > 0; n = Math.floor((n - 1) / 26)) value = String.fromCharCode(65 + (n - 1) % 26) + value;
    return value;
  };
  const checked = key => Boolean(settings.querySelector(`input[data-option="${key}"]`)?.checked);
  const order = () => {
    const keys = cards().map(card => card.dataset.columnGroup);
    // Heading collection remains in its separate settings block.
    keys.splice(keys.indexOf('check_h1') + 1, 0, 'headings');
    return keys;
  };
  // Used when starting a job; the job retains its own order snapshot.
  window.seoColumnOrder = order;

  function refresh() {
    let column = 2;
    const headingCount = [1, 2, 3, 4, 5, 6].filter(n => checked(`collect_h${n}`)).length;
    let afterAlts = false;
    const current = cards();
    current.forEach((card, index) => {
      const key = card.dataset.columnGroup;
      let columns = JSON.parse(card.dataset.columns);
      const enabled = checked(key);
      card.classList.toggle('is-disabled', !enabled);
      card.querySelector('.seo-order-number').textContent = index + 1;
      card.querySelector('[data-move="-1"]').disabled = index === 0;
      card.querySelector('[data-move="1"]').disabled = index === current.length - 1;
      const position = card.querySelector('.seo-column-position');
      if (!enabled) {
        position.textContent = 'Не выводится';
        if (key === 'check_h1') column += headingCount;
        return;
      }
      const start = letter(column);
      const end = letter(column + columns.length - 1);
      position.textContent = afterAlts ? 'Позиция зависит от количества Alt перед этой группой' : `Колонки ${start}${start === end ? '' : '–' + end}`;
      if (key === 'check_images') {
        position.textContent += ' + Alt-1, Alt-2, …';
        afterAlts = true;
      }
      column += columns.length;
      if (key === 'check_h1') column += headingCount;
    });
    document.getElementById('seo-structure-disabled').hidden = checked('check_html_structure');
  }
  function save() {
    try { localStorage.setItem(storageKey, JSON.stringify(order())); }
    catch (error) { status.textContent = 'Порядок изменён. Браузер не разрешил сохранить его между посещениями.'; }
    refresh();
  }
  function restore(keys) {
    const byKey = new Map(cards().map(card => [card.dataset.columnGroup, card]));
    const tail = list.querySelector('.seo-behavior-option');
    const seen = new Set();
    [...keys, ...defaults].forEach(key => {
      if (byKey.has(key) && !seen.has(key)) { list.insertBefore(byKey.get(key), tail); seen.add(key); }
    });
    refresh();
  }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (Array.isArray(saved)) restore(saved);
  } catch (error) { /* Keep defaults when old storage is unavailable or invalid. */ }

  list.addEventListener('click', event => {
    const card = event.target.closest('[data-column-group]');
    // Native labels already toggle their input. Movement controls stay separate.
    if (!card || event.target.closest('button, input, label, a')) return;
    const checkbox = card.querySelector('input[type="checkbox"]');
    if (checkbox && !checkbox.disabled) checkbox.click();
  });

  list.addEventListener('click', event => {
    const button = event.target.closest('[data-move]');
    if (!button) return;
    const card = button.closest('[data-column-group]');
    const current = cards();
    const index = current.indexOf(card);
    const direction = Number(button.dataset.move);
    const target = current[index + direction];
    if (!target) return;
    list.insertBefore(card, direction < 0 ? target : target.nextElementSibling);
    save();
    status.textContent = `Группа перемещена на позицию ${index + direction + 1}`;
    card.querySelector(`[data-move="${direction}"]`).focus();
  });
  list.addEventListener('dragstart', event => event.preventDefault());
  list.addEventListener('pointerdown', event => {
    const handle = event.target.closest('.seo-drag-handle');
    if (!handle || event.button !== 0) return;
    event.preventDefault();
    dragged = event.target.closest('[data-column-group]');
    pointerStart = { x: event.clientX, y: event.clientY };
    handle.setPointerCapture(event.pointerId);
    handle.focus();
  });
  list.addEventListener('pointermove', event => {
    if (!dragged || !pointerStart) return;
    if (Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) < 5) return;
    dragged.classList.add('is-dragging');
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-column-group]');
    cards().forEach(card => card.classList.remove('is-drop-target'));
    dropTarget = target && target !== dragged && list.contains(target) ? target : null;
    dropTarget?.classList.add('is-drop-target');
    if (event.clientY < 90) window.scrollBy(0, -18);
    if (event.clientY > window.innerHeight - 50) window.scrollBy(0, 18);
  });
  function finishDrag(event) {
    if (dragged && dropTarget && event.type !== 'pointercancel') {
      const current = cards();
      list.insertBefore(dragged, current.indexOf(dragged) < current.indexOf(dropTarget) ? dropTarget.nextElementSibling : dropTarget);
      save();
      status.textContent = 'Порядок сохранён';
    }
    cards().forEach(card => card.classList.remove('is-dragging', 'is-drop-target'));
    dragged = null;
    dropTarget = null;
    pointerStart = null;
  }
  list.addEventListener('pointerup', finishDrag);
  list.addEventListener('pointercancel', finishDrag);
  list.addEventListener('lostpointercapture', finishDrag);
  settings.addEventListener('change', refresh);
  // Existing select-all handlers update checkboxes without firing change events.
  settings.addEventListener('click', event => {
    if (event.target.closest('.toggle-all-btn')) refresh();
  });
  document.getElementById('seo-reset-column-order').addEventListener('click', () => {
    restore(defaults); save(); status.textContent = 'Порядок по умолчанию восстановлен';
  });
  document.addEventListener('seo-settings-cleared', () => {
    restore(defaults);
    localStorage.removeItem(storageKey);
  });
  refresh();
})();
