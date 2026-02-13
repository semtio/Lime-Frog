# План рефакторинга SEO-чекера на модульную архитектуру

**Дата:** 13.02.2026
**Цель:** Переход на модульную архитектуру без изменения функциональности
**Ответственность:** Разработчик — рефакторинг; Заказчик — функциональное тестирование

---

## 📋 ТЕКУЩЕЕ СОСТОЯНИЕ

### Структура проекта:
```
Lime-Frog/
├── app.py (222 строк) — Flask + все роуты + создание Job
├── templates/
│   └── index.html (871 строка) — монолитный HTML (CSS+JS inline)
├── site_checker/
│   ├── checks.py (637 строк) — ВСЕ проверки + оркестратор run_all_checks
│   ├── config.py (85 строк) — CheckOptions + RuntimeOptions + CHECK_LABELS
│   ├── jobs.py (230 строк) — JobManager + Job
│   └── exporters.py (216 строк) — rows_to_csv_bytes / rows_to_xlsx_bytes
└── static/ (не существует)
```

### Проблемы текущей архитектуры:
- ❌ `checks.py` — монолит 637 строк (10 проверок + утилиты в одном файле)
- ❌ `index.html` — 500+ строк инлайн-CSS + 300+ строк инлайн-JS
- ❌ Изменение одной проверки может повредить другие
- ❌ Сложно добавлять новые модули (WP, Forge)
- ❌ Нет точек расширения (registry, hooks)

### Что нельзя ломать:
- ✅ Flask маршруты и способ запуска (`start.py`)
- ✅ Ключи `CheckOptions` и связь с `data-option` во фронте
- ✅ Формат CSV/XLS (exporters.py поведение)
- ✅ Логика появления колонок через чекбоксы (`get_active_columns()`)
- ✅ Визуальный внешний вид и UX

---

## 🎯 ЦЕЛЕВАЯ СТРУКТУРА

### Новая архитектура:
```
Lime-Frog/
├── app.py (без изменений)
├── start.py (без изменений)
├── requirements.txt (без изменений)
│
├── tabs/                           ← ТОП-УРОВЕНЬ: контейнер для разных модулей
│   ├── __init__.py
│   └── seo_checker/                ← Каркас для будущего переезда SEO
│       └── __init__.py
│
├── templates/
│   ├── index.html (только HTML+подключения)
│   └── partials/                   ← Новое: разбитый шаблон
│       ├── runtime_settings.html
│       ├── checks_sections.html
│       ├── collect_headings.html
│       └── html_structure.html
│
├── static/                         ← Новое: вынесена статика
│   ├── css/
│   │   └── main.css               (весь inline CSS из index.html)
│   └── js/
│       └── app.js                 (весь inline JS из index.html)
│
└── site_checker/
    ├── checks.py                  (оркестратор run_all_checks)
    ├── config.py (без изменений)
    ├── jobs.py (без изменений)
    ├── exporters.py (без изменений)
    │
    ├── network/                   ← Новое: сетевые утилиты
    │   ├── __init__.py
    │   ├── fetcher.py             (fetch_with_retries, headers)
    │   └── url.py                 (normalize_url)
    │
    ├── parsers/                   ← Новое: общие парсеры
    │   ├── __init__.py
    │   └── meta.py                (extract_title, extract_description и т.д.)
    │
    └── checkers/                  ← Новое: независимые модули проверок
        ├── __init__.py
        ├── seo/
        │   ├── __init__.py
        │   ├── metadata.py        (Title, Description, Lang, Canonical, Robots-meta)
        │   ├── headings.py        (H1 + collect + дубли)
        │   ├── images.py          (Images + Alts)
        │   ├── structure.py       (HTML структура)
        │   ├── sitemap.py
        │   ├── robots.py
        │   └── http.py            (Status codes, 404, redirects)
        └── cms/
            ├── __init__.py
            └── detect.py          (check_cms)
```

---

## 📝 ЭТАП 1: ВЫНЕСТИ СТАТИКУ (CSS + JS)

### Что делать:
1. **Создать файлы:**
   - `static/css/main.css` ← скопировать весь `<style>...</style>` из index.html
   - `static/js/app.js` ← скопировать весь `<script>...</script>` из index.html

2. **В `index.html` оставить:**
   - `<!DOCTYPE html>` и теги head/body
   - Все структурные элементы: `<div class="container">`, `<header>`, `<div class="panel">` и т.д.
   - Все `data-option="{{ key }}"`, `id="urls"`, классы (без изменений!)
   - Вместо инлайн CSS: `<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">`
   - Вместо инлайн JS: `<script src="{{ url_for('static', filename='js/app.js') }}"></script>`

3. **Без изменений:**
   - id/class всех элементов
   - data-* атрибуты
   - структура Jinja2 переменных ({{ checks }}, {% for key %})

### Файлы для изменения:
- ✏️ `templates/index.html` (871 → ~200 строк)
- ✏️ `app.py` (добавить `app.static_folder = 'static'` если нужно)
- 📝 `static/css/main.css` (создать)
- 📝 `static/js/app.js` (создать)

### Критерий готовности:
- ✅ Проект запускается без ошибок
- ✅ UI выглядит идентично
- ✅ Все кнопки работают (Старт, Стоп, Скачать CSV, etc.)
- ✅ Чекбоксы работают, результаты появляются

---

## 📝 ЭТАП 2: РАЗБИТЬ ШАБЛОНЫ НА PARTIALS

### Что делать:
1. **Создать `templates/partials/`**

2. **Создать 4 файла partials:**

   **`partials/runtime_settings.html`** — параметры запуска
   ```html
   <div class="grid">
     <div class="field">
       <label for="concurrency">{{ labels.get('concurrency', 'Concurrency') }}</label>
       <input type="number" id="concurrency" value="{{ defaults.concurrency }}" />
     </div>
     <!-- timeout, retries, filename -->
   </div>
   ```

   **`partials/checks_sections.html`** — три секции: Main, Headings, HTML Structure
   ```html
   <!-- Просто перенести <div class="checks-section"> из index.html -->
   ```

   **`partials/collect_headings.html`** — кнопка "Скачать XLS" для заголовков

   **`partials/html_structure.html`** — остальное

3. **В `index.html` оставить:**
   ```html
   {% include 'partials/runtime_settings.html' %}
   {% include 'partials/checks_sections.html' %}
   {% include 'partials/collect_headings.html' %}
   {% include 'partials/html_structure.html' %}
   ```

4. **Без изменений:**
   - Всё остаётся на месте (id/class/data-option)
   - DOM структура не меняется
   - Jinja2 переменные передаются в partials

### Файлы для изменения:
- ✏️ `templates/index.html` (переделать на набор include)
- 📝 `templates/partials/runtime_settings.html` (создать)
- 📝 `templates/partials/checks_sections.html` (создать)
- 📝 `templates/partials/collect_headings.html` (создать)
- 📝 `templates/partials/html_structure.html` (создать)

### Критерий готовности:
- ✅ HTML всё ещё валидный
- ✅ UI работает идентично
- ✅ Чекбоксы группируются корректно (toggle-all по группам)
- ✅ Формы принимают данные и отправляют на бэк

---

## 📝 ЭТАП 3: ВЫНЕСТИ СЕТЕВЫЕ УТИЛИТЫ И ПАРСЕРЫ

### Что делать:

1. **Создать `site_checker/network/` папку**

   **`site_checker/network/__init__.py`** — пусто или re-export

   **`site_checker/network/fetcher.py`:**
   ```python
   # Откуда берём из checks.py:
   - USER_AGENT
   - BROWSER_HEADERS
   - fetch_with_retries(client, url, runtime, follow_redirects)
   ```

   **`site_checker/network/url.py`:**
   ```python
   # Откуда берём из checks.py:
   - normalize_url(raw)
   ```

2. **Создать `site_checker/parsers/` папка**

   **`site_checker/parsers/__init__.py`** — пусто или re-export

   **`site_checker/parsers/meta.py`:**
   ```python
   # Откуда берём из checks.py:
   - extract_title(soup)
   - extract_description(soup)
   - extract_html_lang(soup)
   - extract_canonical(soup)
   - parse_robots_meta(response, soup)
   ```

3. **В `checks.py` обновить импорты:**
   ```python
   from .network.fetcher import fetch_with_retries, BROWSER_HEADERS
   from .network.url import normalize_url
   from .parsers.meta import extract_title, extract_description, ...
   ```

4. **Функции остаются теми же, вызовы не меняются**

### Файлы для изменения:
- ✏️ `site_checker/checks.py` (удалить 50-100 строк функций, добавить импорты)
- 📝 `site_checker/network/__init__.py` (создать)
- 📝 `site_checker/network/fetcher.py` (создать)
- 📝 `site_checker/network/url.py` (создать)
- 📝 `site_checker/parsers/__init__.py` (создать)
- 📝 `site_checker/parsers/meta.py` (создать)

### Критерий готовности:
- ✅ Проект запускается
- ✅ run_all_checks() возвращает тот же результат
- ✅ Все парсеры работают (Title, Description, Canonical и т.д.)
- ✅ Сетевые запросы работают (fetch_with_retries)

---

## 📝 ЭТАП 4: РАЗНЕСТИ ПРОВЕРКИ ПО МОДУЛЯМ

### Что делать:

1. **Создать `site_checker/checkers/` папка**

2. **Создать `site_checker/checkers/seo/` с файлами:**

   **`metadata.py`** — Title, Description, Canonical, Lang, Robots-meta
   ```python
   def check_title_and_description(soup, response, options):
       # вызвать extract_title, extract_description, extract_canonical, parse_robots_meta
       return {"Title": ..., "Description": ..., "Canonical": ..., ...}
   ```

   **`headings.py`** — H1 count, collect H1-H6, дубли H1/H2/H3
   ```python
   def check_headings(soup, options):
       # check_h1, collect_headings, find_heading_duplicates
       return {"Кол-во H1": ..., "H1": ..., "H2": ..., "Дубли H1/H2/H3": ...}
   ```

   **`images.py`** — Кол-во img, Кол-во alt, Alt-1..Alt-N
   ```python
   def check_images(soup, options):
       # check_images_alt
       return {"Кол-во img": ..., "Кол-во alt": ..., "Alt-1": ...}
   ```

   **`structure.py`** — HTML структура
   ```python
   def check_html_structure(soup, options):
       # build_html_structure
       return {"HTML структура": ...}
   ```

   **`sitemap.py`** — Sitemap 200
   ```python
   async def check_sitemap_status(base_url, client, runtime, options):
       # check_sitemap
       return {"Sitemap 200": ...}
   ```

   **`robots.py`** — Robots 200, Disallow, Sitemap
   ```python
   async def check_robots_status(base_url, client, runtime, options):
       # check_robots
       return {"Robots 200": ..., "Robots Disallow": ..., "Robots Sitemap": ...}
   ```

   **`http.py`** — Status codes, 404, redirects
   ```python
   async def check_http_info(normalized_url, response_no_follow, response, client, runtime, options):
       # check_404, редирект обработка, status codes
       return {"Код ответа": ..., "Редирект": ..., "Ссылка на стр.404": ...}
   ```

3. **Создать `site_checker/checkers/cms/`**

   **`detect.py`** — CMS detection
   ```python
   async def check_cms(soup, response, client, runtime):
       # check_cms
       return "WordPress" / "Forge" / "Unknown"
   ```

4. **В `checks.py` обновить:**
   ```python
   from .checkers.seo import metadata, headings, images, structure, sitemap, robots, http
   from .checkers.cms import detect

   # run_all_checks просто вызывает эти модули:
   metadata_result = metadata.check_title_and_description(soup, response, options)
   result.update(metadata_result)
   ...
   ```

### Файлы для создания:
- 📝 `site_checker/checkers/__init__.py`
- 📝 `site_checker/checkers/seo/__init__.py`
- 📝 `site_checker/checkers/seo/metadata.py`
- 📝 `site_checker/checkers/seo/headings.py`
- 📝 `site_checker/checkers/seo/images.py`
- 📝 `site_checker/checkers/seo/structure.py`
- 📝 `site_checker/checkers/seo/sitemap.py`
- 📝 `site_checker/checkers/seo/robots.py`
- 📝 `site_checker/checkers/seo/http.py`
- 📝 `site_checker/checkers/cms/__init__.py`
- 📝 `site_checker/checkers/cms/detect.py`

### Файлы для изменения:
- ✏️ `site_checker/checks.py` (оставить только run_all_checks + импорты)

### Критерий готовности:
- ✅ Проект запускается
- ✅ Все проверки выполняются как раньше
- ✅ Опции/чекбоксы работают (check_h1, check_cms и т.д.)
- ✅ CSV/XLS содержат те же колонки в том же порядке

---

## 📝 ЭТАП 5: УНИФИЦИРОВАТЬ ПЕРЕДАЧУ ДАННЫХ (CheckContext)

### Что делать:

1. **Создать `site_checker/context.py`:**
   ```python
   from dataclasses import dataclass
   from typing import Optional
   import httpx
   from bs4 import BeautifulSoup
   from .config import CheckOptions, RuntimeOptions

   @dataclass
   class CheckContext:
       """Контекст проверки одного URL"""
       raw_url: str
       normalized_url: str
       response_no_follow: Optional[httpx.Response]
       response: Optional[httpx.Response]
       soup: Optional[BeautifulSoup]
       client: httpx.AsyncClient
       check_options: CheckOptions
       runtime: RuntimeOptions
       final_url: Optional[str] = None
   ```

2. **Обновить сигнатуры функций в модулях:**

   Вместо:
   ```python
   def check_h1(soup):
   ```

   На:
   ```python
   def check_h1(ctx: CheckContext):
       soup = ctx.soup
       # ...
   ```

3. **В `run_all_checks()` создавать контекст и передавать:**
   ```python
   async def run_all_checks(...):
       ctx = CheckContext(
           raw_url=raw_url,
           normalized_url=normalized_url,
           response_no_follow=response_no_follow,
           response=response,
           soup=soup,
           client=client,
           check_options=check_options,
           runtime=runtime,
           final_url=str(response.url) if response else None
       )

       metadata_result = metadata.check_title_and_description(ctx)
       headings_result = headings.check_headings(ctx)
       # ...
   ```

### Файлы для создания:
- 📝 `site_checker/context.py`

### Файлы для изменения:
- ✏️ `site_checker/checks.py` (обновить сигнатуры вызовов)
- ✏️ Все модули в `site_checker/checkers/` (принимают CheckContext)

### Критерий готовности:
- ✅ Код читаемый (нет жерди параметров)
- ✅ Модули независимы друг от друга
- ✅ Функциональность не изменилась
- ✅ Легче добавлять новые проверки

---

## 🗂️ СОЗДАНИЕ КАРКАСА TABS

### После этапа 1 (параллельно или сразу):

1. **Создать `tabs/` папка:**
   ```
   tabs/
   ├── __init__.py (пусто)
   └── seo_checker/
       └── __init__.py (пусто)
   ```

2. **Назначение:**
   - Топ-уровень для разных модулей (SEO, CMS, и т.д.)
   - На будущее: перенос UI и логики SEO сюда

3. **Без кода на этом этапе** — просто каркас

---

## 🔒 ПРАВИЛА ПО DEBUG И ЛОГИРОВАНИЮ

1. **Никакого debug в пользовательские файлы (CSV/XLS)**
   - Параметры, которых нет в `check_options` → не выводятся
   - Никаких диагностических данных, timestamps, trace-ов в экспорт

2. **Debug-режим (опционально, будущее):**
   - Отдельный лог-файл `logs/debug.log`
   - Включается флагом окружения: `DEBUG_MODE=1 python start.py`
   - Не влияет на exporters.py вывод

3. **Текущее состояние:**
   - В `checks.py` нет println/logging → оставить как есть
   - При необходимости → добавить `import logging` позже

---

## ✅ КРИТЕРИИ ПРИЁМКИ

### По завершении всех 5 этапов:

1. **Функциональность:**
   - ✅ Проект запускается (`python start.py`)
   - ✅ UI загружается без ошибок в консоли/браузере
   - ✅ Все кнопки работают (Старт, Стоп, Скачать CSV, Скачать XLS)
   - ✅ Чекбоксы включают/отключают проверки
   - ✅ Прогрессбар работает
   - ✅ Результаты выводятся в таблицу

2. **Проверки SEO:**
   - ✅ Все 10+ проверок выполняются
   - ✅ Результаты содержат все параметры (Title, Description, H1, и т.д.)
   - ✅ CMS определяется корректно (WordPress / Unknown)
   - ✅ Чекбоксы влияют на/отключают параметры в экспорте

3. **Экспорт:**
   - ✅ CSV содержит правильные колонки и данные
   - ✅ XLS содержит правильные колонки и стили
   - ✅ Заголовки скачиваются отдельным файлом (если включено)
   - ✅ Никаких лишних/debug-параметров в файлах

4. **Архитектура:**
   - ✅ `checks.py` перестал быть монолитом (проверки в `checkers/`)
   - ✅ Статика вынесена в `static/`
   - ✅ Шаблон разбит на `partials/`
   - ✅ Сетевые утилиты в `network/`
   - ✅ Парсеры в `parsers/`
   - ✅ Контекст унифицирован через `CheckContext`
   - ✅ Архитектура модульна; для добавления новой проверки нужно добавить модуль в `site_checker/checkers/` и подключить его вызов в `run_all_checks()` ([site_checker/checks.py](site_checker/checks.py#L190-L220)). Registry/pipeline пока не реализован.

5. **Документация:**
   - ✅ Инструкция запуска
   - ✅ Список файлов (созданы / изменены / удалены)
   - ✅ Описание "что перенесено куда"

---

## 📦 ЧТО ПРЕДОСТАВИТЬ ПО ИТОГАМ

1. **Коммит(ы) или архив** с изменениями
2. **Файл `REFACTOR_SUMMARY.md`:**
   ```markdown
   # Итоги рефакторинга SEO-чекера

   ## Созданные файлы:
   - static/css/main.css
   - static/js/app.js
   - templates/partials/...
   - site_checker/network/...
   - site_checker/parsers/...
   - site_checker/checkers/...
   - site_checker/context.py
   - tabs/seo_checker/

   ## Изменённые файлы:
   - templates/index.html
   - site_checker/checks.py
   - app.py (если были изменения)

   ## Инструкция запуска:
   ```
   python start.py
   ```

   ## Тестирование (выполнить заказчиком):
   - Открыть http://localhost:5000
   - Добавить 5-10 URL-ов
   - Включить/отключить чекбоксы
   - Нажать "Старт"
   - Скачать CSV и XLS
   - Прверить результаты
   ```

---

## 📊 СВОДНАЯ ТАБЛИЦА ЭТАПОВ

| Этап | Время | Рёбра | Критерий | Риск |
|------|-------|-------|----------|------|
| 1. Статика | 1-2ч | CSS+JS в static/ | UI работает | 🟢 Низкий |
| 2. Partials | 1-2ч | templates/partials/ | DOM тот же | 🟢 Низкий |
| 3. Утилиты | 2-3ч | network/ + parsers/ | Импорты работают | 🟡 Средний |
| 4. Модули | 3-4ч | checkers/ | Проверки работают | 🟡 Средний |
| 5. Контекст | 2-3ч | CheckContext | Код читаемый | 🟢 Низкий |
| Каркас tabs | 30мин | tabs/ | Просто папки | 🟢 Низкий |

**Итого:** ~10-15 часов разработки

---

**Начинаем с Этапа 1?**
