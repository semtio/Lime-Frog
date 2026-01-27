# SEO Checker

Проверка доменов по SEO-критериям. Результаты в CSV.

---

## Установка и запуск (Windows — Local Dev)

### Шаг 1. Установите Python
Скачайте и установите [Python 3.10.12+](https://www.python.org/downloads/)

### Шаг 2. Создайте виртуальное окружение
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### Шаг 3. Установите зависимости
```cmd
pip install -r requirements.txt
```

### Шаг 4. Запустите приложение
```cmd
python app.py
```

### Шаг 5. Откройте в браузере
```
http://127.0.0.1:5000
```

---

## Установка на сервер (Linux — Production)

### Быстрая установка (один скрипт)

```bash
# Загрузите проект на сервер и перейдите в папку
cd /path/to/Lime-Frog

# Сделайте скрипт исполняемым
chmod +x install.sh

# Запустите установку (требуется sudo)
sudo ./install.sh
```

**Скрипт автоматически:**
- Установит Python, Nginx, UFW
- Создаст виртуальное окружение и установит зависимости
- Настроит Gunicorn (bind на 127.0.0.1:8000)
- Настроит Nginx как reverse proxy (порт 80)
- Откроет порты 22, 80, 443 в UFW
- Создаст systemd сервис для автозапуска
- Запустит приложение

После установки приложение будет доступно по IP сервера:
```
http://your-server-ip
```

### Управление сервисом

```bash
# Статус
sudo systemctl status seo-checker

# Перезапуск
sudo systemctl restart seo-checker

# Остановка
sudo systemctl stop seo-checker

# Просмотр логов
sudo journalctl -u seo-checker -f
```

### Логи Nginx

```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

---

### macOS

#### Шаг 1. Установите Python через Homebrew (или скачайте с python.org)
```bash
brew install python3
```

#### Шаг 2. Создайте виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Шаг 3. Установите зависимости
```bash
pip install -r requirements.txt
```

#### Шаг 4. Запустите приложение
```bash
python3 app.py
```

#### Шаг 5. Откройте в браузере
```
http://127.0.0.1:5000
```

## Что проверяет
- Коды ответов (40x/50x)
- Редиректы
- Noindex/Nofollow, Canonical
- Title, Description
- Sitemap.xml, Robots.txt
- Страница 404 (URL, код ответа, корректность — в отдельных столбцах)
- H1 (количество и наличие пустых)
- Alt для изображений (кол-во img в body, кол-во заполненных alt)
- Доменные дубли (http/https, www)
- HTML структура (настраиваемая: H1–H6, P, семантические теги HTML5)
- Дубли заголовков (H1/H2/H3)

## Настройки HTML структуры
Вы можете выбрать, какие теги отслеживать:
- **Заголовки (H1-H6)** — все заголовки от первого до шестого уровня
- **Параграфы (P)** — текстовые параграфы
- **Семантика** — main, section, article, header, footer, nav, aside
- **Медиа** — figure, figcaption
- **Другое** — address, time

## Использование
1. Вставьте домены в поле (по одному в строке)
2. Выберите проверки (по умолчанию все включены)
3. Нажмите **Старт**
4. После завершения нажмите **Скачать CSV** или **Скачать XLS**
