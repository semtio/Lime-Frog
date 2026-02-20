# План рефакторинга: Переход к модульной архитектуре

## Цель
Преобразовать монолитную структуру с централизованными `templates/` и `static/` в модульную архитектуру, где каждая вкладка (модуль) является **самодостаточной** с собственными шаблонами, стилями и скриптами.

---

## Текущая проблема

### Сейчас:
```
templates/
  index.html          ← 700+ строк, содержит ВСЕ вкладки
  partials/           ← Только для seo_checker
static/
  css/
    main.css          ← Общие стили
  js/
    app.js            ← Логика seo_checker
    google_speed.js   ← Логика google_speed
tabs/
  seo_checker/        ← Только Python-логика
  google_speed/       ← Только Python-логика
  magic_links/        ← Только Python-логика
  ssh_tools/          ← УЖЕ Blueprint с templates/static!
```

### Проблемы:
1. **index.html растет бесконтрольно** — добавление каждой новой вкладки = +100-200 строк
2. **Невозможно переиспользовать модули** — нельзя скопировать `google_speed/` в другой проект
3. **Сложность поддержки** — один файл для всех вкладок
4. **Непоследовательность** — ssh_tools уже Blueprint, остальные нет

---

## Целевая архитектура

### После рефакторинга:
```
templates/
  base.html           ← Базовый шаблон: <head>, header, auth модалки, общие скрипты

tabs/
  seo_checker/
    __init__.py       ← Blueprint: seo_checker_bp
    jobs.py
    checks.py
    exporters.py
    templates/
      seo_checker.html      ← Только HTML этой вкладки
    static/
      css/
        seo_checker.css     ← Стили только для этой вкладки
      js/
        seo_checker.js      ← Логика только для этой вкладки

  google_speed/
    __init__.py       ← Blueprint: google_speed_bp
    jobs.py
    exporters.py
    templates/
      google_speed.html
    static/
      css/
        google_speed.css
      js/
        google_speed.js

  magic_links/
    __init__.py       ← Blueprint: magic_links_bp
    jobs.py
    exporters.py
    templates/
      magic_links.html
    static/
      css/
        magic_links.css
      js/
        magic_links.js

  ssh_tools/
    ← Уже готов, ничего не менять!

static/
  css/
    base.css          ← Только общие стили (header, badges, модалки)
  js/
    base.js           ← Только общая логика (переключение вкладок, auth, stats)
```

### Преимущества:
✅ **Модульность** — каждую папку можно скопировать в другой проект
✅ **Изоляция** — изменения в одной вкладке не влияют на другие
✅ **Читаемость** — каждый шаблон ~50-100 строк вместо 2000
✅ **Единообразие** — все вкладки работают одинаково
✅ **Масштабируемость** — легко добавлять новые вкладки

---

## Пошаговый план рефакторинга

### Этап 1: Подготовка базового шаблона

#### 1.1. Создать `templates/base.html`
**Что переносим из `index.html`:**
- `<head>` (meta, title, общие CSS)
- `<header>` с селектором инструментов и счетчиками
- Модальное окно аутентификации (`#auth-overlay`)
- Модальное окно SSH (`#ssh-modal-overlay`)
- Общие скрипты (`auth.js`, скрипт переключения вкладок)
- Jinja-блок для подключения модулей: `{% block content %}{% endblock %}`

**Пример структуры:**
```jinja2
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>{{ page_title }}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}" />
  {% block extra_css %}{% endblock %}
</head>
<body>
  <header>
    <!-- Селектор инструментов, счетчики -->
  </header>

  <div class="container">
    {% block content %}{% endblock %}
  </div>

  <!-- Модалки auth и ssh -->

  <script src="{{ url_for('static', filename='js/base.js') }}"></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

#### 1.2. Создать `static/css/base.css`
**Что переносим из `main.css`:**
- CSS переменные (`:root`)
- Стили header, badge, stats-display
- Стили модалок auth и ssh
- Общие классы: `.tool-select`, `.panel`, `.field`, `.actions`, `.button`, `.status`, `.progress-bar`

**Что НЕ переносим (оставить в модульных CSS):**
- Специфичные стили для каждой вкладки (`.google-speed-api-help`, `.magic-links-grid`, `.replace-tool-panel`)

#### 1.3. Создать `static/js/base.js`
**Что переносим из `app.js`:**
- Переключение вкладок по URL параметру `?module=...`
- Обновление счетчиков пользователей (`updateStats()`)
- Логика отображения job-badge

**Что НЕ переносим:**
- Логику конкретных вкладок (polling, старт/стоп задач)

---

### Этап 2: Рефакторинг SEO Checker

#### 2.1. Создать Blueprint в `tabs/seo_checker/__init__.py`
```python
from flask import Blueprint

seo_checker_bp = Blueprint(
    'seo_checker',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/seo-checker/static'
)

# Импорт роутов если нужно
# from . import routes
```

#### 2.2. Создать структуру папок
```bash
tabs/seo_checker/
  templates/
    seo_checker.html
  static/
    css/
      seo_checker.css
    js/
      seo_checker.js
```

#### 2.3. Создать `tabs/seo_checker/templates/seo_checker.html`
**Что переносим из `index.html`:**
- Весь блок `<div class="tool-view" data-tool-view="seo_checker">...</div>`
- Заменить на наследование от base:
```jinja2
{% extends "base.html" %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('seo_checker.static', filename='css/seo_checker.css') }}" />
{% endblock %}

{% block content %}
<div class="tool-view active" data-tool-view="seo_checker">
  <div class="tool-description">...</div>
  <!-- Весь контент вкладки -->
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('seo_checker.static', filename='js/seo_checker.js') }}"></script>
{% endblock %}
```

#### 2.4. Создать `tabs/seo_checker/static/css/seo_checker.css`
**Переместить из `main.css`:**
- Стили специфичные для SEO Checker
- `.checks-section`, `.checks`, `.check-item`, `.grid`

#### 2.5. Создать `tabs/seo_checker/static/js/seo_checker.js`
**Переместить из `app.js`:**
- Всю логику работы с SEO Checker
- Event listeners для кнопок `#start-btn`, `#stop-btn`, `#download-btn`
- Функции `pollStatus()`, `startJob()`, `stopJob()`
- localStorage логика

#### 2.6. Переместить partials
```
tabs/seo_checker/templates/
  partials/
    runtime_settings.html
    main_checks.html
    heading_checks.html
    html_structure_checks.html
```

Обновить include в `seo_checker.html`:
```jinja2
{% include 'partials/runtime_settings.html' %}
```

---

### Этап 3: Рефакторинг Google Speed

#### 3.1. Создать Blueprint в `tabs/google_speed/__init__.py`
```python
from flask import Blueprint

google_speed_bp = Blueprint(
    'google_speed',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/google-speed/static'
)
```

#### 3.2. Создать структуру
```bash
tabs/google_speed/
  templates/
    google_speed.html
  static/
    css/
      google_speed.css
    js/
      google_speed.js
```

#### 3.3. Создать `tabs/google_speed/templates/google_speed.html`
**Переместить из `index.html`:**
- Блок `<div class="tool-view" data-tool-view="google_speed">...</div>`
- Использовать наследование от `base.html`

#### 3.4. Создать `tabs/google_speed/static/css/google_speed.css`
**Переместить из `main.css`:**
- `.google-speed-api-help`
- `.google-speed-key-actions`

#### 3.5. Создать `tabs/google_speed/static/js/google_speed.js`
**Переместить из `static/js/google_speed.js`:**
- Весь текущий код без изменений

---

### Этап 4: Рефакторинг Magic Links

#### 4.1. Создать Blueprint в `tabs/magic_links/__init__.py`
```python
from flask import Blueprint

magic_links_bp = Blueprint(
    'magic_links',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/magic-links/static'
)
```

#### 4.2. Создать структуру
```bash
tabs/magic_links/
  templates/
    magic_links.html
  static/
    css/
      magic_links.css
    js/
      magic_links.js
```

#### 4.3. Создать `tabs/magic_links/templates/magic_links.html`
**Переместить из `index.html`:**
- Блок `<div class="tool-view" data-tool-view="magic_links">...</div>`
- `<template id="magic-links-card-template">...</template>`

#### 4.4. Создать `tabs/magic_links/static/css/magic_links.css`
**Переместить из `main.css`:**
- `.magic-links-cards`
- `.magic-links-grid`
- `.magic-links-mode`
- `.magic-links-card`
- `.magic-links-add`

#### 4.5. Создать `tabs/magic_links/static/js/magic_links.js`
**Переместить из `app.js`:**
- Вся логика Magic Links
- Управление множественными карточками
- Динамическое добавление/удаление пар

---

### Этап 5: Обновление app.py

#### 5.1. Импортировать и зарегистрировать Blueprint'ы
```python
from tabs.seo_checker import seo_checker_bp
from tabs.google_speed import google_speed_bp
from tabs.magic_links import magic_links_bp
from tabs.ssh_tools.routes import ssh_tools_bp  # Уже существует

app.register_blueprint(seo_checker_bp, url_prefix='/seo-checker')
app.register_blueprint(google_speed_bp, url_prefix='/google-speed')
app.register_blueprint(magic_links_bp, url_prefix='/magic-links')
app.register_blueprint(ssh_tools_bp, url_prefix='/ssh-tools')
```

#### 5.2. Обновить роуты API
**Переместить API эндпоинты в Blueprint'ы:**

**Пример для Google Speed:**
В `tabs/google_speed/routes.py`:
```python
from flask import jsonify, request
from . import google_speed_bp
from .jobs import GoogleSpeedJobManager

@google_speed_bp.route('/api/job', methods=['POST'])
@require_auth
def create_job():
    # Логика создания задачи
    pass

@google_speed_bp.route('/api/job/<job_id>', methods=['GET'])
@require_auth
def get_job_status(job_id):
    # Логика статуса
    pass
```

Аналогично для SEO Checker и Magic Links.

#### 5.3. Обновить главный роут
```python
@app.route('/')
@require_auth
def index():
    module = request.args.get('module', 'seo_checker')

    # Маппинг модулей на их Blueprint'ы
    module_templates = {
        'seo_checker': 'seo_checker/seo_checker.html',
        'google_speed': 'google_speed/google_speed.html',
        'magic_links': 'magic_links/magic_links.html',
        'ssh_tools': 'ssh_tools/ssh_tools.html',
    }

    template = module_templates.get(module, 'seo_checker/seo_checker.html')

    return render_template(
        template,
        page_title='Lime-Frog SEO & SSH Tools',
        selected_tool=module,
        tools=REGISTERED_TOOLS
    )
```

---

### Этап 6: Обновление регистрации модулей

#### 6.1. Обновить `tabs/__init__.py`
```python
REGISTERED_TOOLS = [
    {
        'name': 'seo_checker',
        'label': 'SEO Checker',
        'title': 'SEO Checker',
        'description': 'Проверка SEO-параметров сайтов',
        'path': '/?module=seo_checker',
        'blueprint': 'seo_checker'
    },
    {
        'name': 'google_speed',
        'label': 'Google Speed',
        'title': 'Google PageSpeed Insights',
        'description': 'Проверка скорости загрузки через PageSpeed API',
        'path': '/?module=google_speed',
        'blueprint': 'google_speed'
    },
    # ...
]
```

---

### Этап 7: Миграция данных и тестирование

#### 7.1. Проверить пути к статическим файлам
**В каждом HTML-шаблоне:**
```jinja2
<!-- Было -->
<script src="{{ url_for('static', filename='js/google_speed.js') }}"></script>

<!-- Стало -->
<script src="{{ url_for('google_speed.static', filename='js/google_speed.js') }}"></script>
```

#### 7.2. Обновить импорты в JavaScript
Если есть зависимости между модулями — вынести в `base.js`

#### 7.3. Тестирование
```bash
# Запустить приложение
python start.py

# Проверить каждую вкладку:
http://localhost:5000/?module=seo_checker
http://localhost:5000/?module=google_speed
http://localhost:5000/?module=magic_links
http://localhost:5000/?module=ssh_tools
```

#### 7.4. Проверить функциональность
- [ ] Переключение вкладок работает
- [ ] Старт/стоп задач
- [ ] Скачивание XLS/CSV
- [ ] Сохранение в localStorage
- [ ] Валидация API ключей
- [ ] SSH подключения
- [ ] Replace Tool

---

### Этап 8: Очистка старых файлов

#### 8.1. Удалить старые файлы (после тестирования!)
```
templates/
  index.html          ← УДАЛИТЬ, заменен на base.html + модульные
  partials/           ← ПЕРЕМЕСТИТЬ в tabs/seo_checker/templates/

static/
  js/
    app.js            ← УДАЛИТЬ, разбит по модулям
    google_speed.js   ← УДАЛИТЬ, перемещен в tabs/google_speed/static/
  css/
    main.css          ← Переименовать в base.css, удалить специфичные стили
```

#### 8.2. Обновить .gitignore (если нужно)
```
# Игнорировать локальные конфиги модулей
tabs/*/config.local.py
```

---

## Дополнительные улучшения (опционально)

### 1. Вынести общие компоненты
Если есть переиспользуемые UI-компоненты (прогресс-бары, кнопки, модалки):
```
templates/
  components/
    progress_bar.html
    action_buttons.html
    settings_toggle.html
```

Использование:
```jinja2
{% include 'components/progress_bar.html' %}
```

### 2. Создать requirements.txt для каждого модуля
```
tabs/google_speed/
  requirements.txt    ← requests, openpyxl
```

Это позволит понять зависимости каждого модуля при миграции.

### 3. Добавить README.md в каждый модуль
```markdown
# Google Speed Module

## Описание
Проверка скорости загрузки через Google PageSpeed Insights API

## Зависимости
- requests
- openpyxl

## API ключ
Требуется API ключ Google Cloud с доступом к PageSpeed Insights API
```

### 4. Унифицировать API эндпоинты
Сделать единый формат для всех модулей:
```
GET  /api/{module}/job         - Список задач
POST /api/{module}/job         - Создать задачу
GET  /api/{module}/job/{id}    - Статус задачи
POST /api/{module}/job/{id}/stop - Остановить задачу
GET  /api/{module}/job/{id}/download - Скачать результат
```

---

## Чек-лист выполнения

### Подготовка
- [ ] Создать `templates/base.html`
- [ ] Создать `static/css/base.css`
- [ ] Создать `static/js/base.js`

### SEO Checker
- [ ] Создать Blueprint `tabs/seo_checker/__init__.py`
- [ ] Создать `tabs/seo_checker/templates/seo_checker.html`
- [ ] Создать `tabs/seo_checker/static/css/seo_checker.css`
- [ ] Создать `tabs/seo_checker/static/js/seo_checker.js`
- [ ] Переместить partials из `templates/partials/`
- [ ] Создать `tabs/seo_checker/routes.py`

### Google Speed
- [ ] Создать Blueprint `tabs/google_speed/__init__.py`
- [ ] Создать `tabs/google_speed/templates/google_speed.html`
- [ ] Создать `tabs/google_speed/static/css/google_speed.css`
- [ ] Переместить `static/js/google_speed.js` → `tabs/google_speed/static/js/`
- [ ] Создать `tabs/google_speed/routes.py`

### Magic Links
- [ ] Создать Blueprint `tabs/magic_links/__init__.py`
- [ ] Создать `tabs/magic_links/templates/magic_links.html`
- [ ] Создать `tabs/magic_links/static/css/magic_links.css`
- [ ] Создать `tabs/magic_links/static/js/magic_links.js`
- [ ] Создать `tabs/magic_links/routes.py`

### Интеграция
- [ ] Обновить `app.py` — зарегистрировать все Blueprint'ы
- [ ] Обновить `tabs/__init__.py` — добавить blueprint в REGISTERED_TOOLS
- [ ] Переместить API роуты из `app.py` в модульные `routes.py`

### Тестирование
- [ ] Проверить работу каждой вкладки
- [ ] Проверить API эндпоинты
- [ ] Проверить localStorage
- [ ] Проверить экспорт XLS/CSV
- [ ] Проверить auth и ssh модалки

### Очистка
- [ ] Удалить старый `templates/index.html`
- [ ] Удалить `static/js/app.js`
- [ ] Переименовать `main.css` → `base.css`
- [ ] Удалить неиспользуемые CSS

---

## Риски и как их избежать

### Риск 1: Сломается маршрутизация
**Решение:** Сначала создать Blueprint'ы, зарегистрировать их, протестировать — только потом удалять старые файлы.

### Риск 2: Потеряются стили
**Решение:** Тестировать каждый модуль отдельно после миграции CSS.

### Риск 3: Не работает localStorage
**Решение:** Префиксы в ключах localStorage должны остаться прежними (`google-speed-api-key`, `magic-links-urls-1`).

### Риск 4: API эндпоинты переезжают
**Решение:** В JavaScript обновить URL'ы:
```javascript
// Было
fetch('/api/google-speed/job', ...)

// Остается так же (Blueprint использует url_prefix)
fetch('/api/google-speed/job', ...)
```

---

## Итоговый результат

После рефакторинга:
- ✅ Каждый модуль полностью автономен
- ✅ Можно копировать папку модуля в другой проект
- ✅ Легко добавлять новые вкладки
- ✅ Простая поддержка и отладка
- ✅ Единообразная архитектура для всех модулей
- ✅ Масштабируемость до десятков вкладок

**Время выполнения:** 4-6 часов работы для всех модулей.

**Приоритет:** Средний (сейчас работает, но при масштабировании станет критично).
