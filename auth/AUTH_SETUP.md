# Инструкция по настройке аутентификации

## Быстрый старт

### 1. Установка зависимостей

Убедитесь что bcrypt установлен:

```bash
pip install -r requirements.txt
```

### 2. Генерация учетных данных

Откройте Python интерпретатор и выполните:

```python
import bcrypt

# Генерируем хеш для логина
username = "ваш_логин"  # Замените на желаемый логин
username_hash = bcrypt.hashpw(username.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"Хеш логина: {username_hash}")

# Генерируем хеш для пароля
password = "ваш_пароль"  # Замените на желаемый пароль
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
print(f"Хеш пароля: {password_hash}")
```

**Пример вывода:**
```
Хеш логина: $2b$12$KIXxqF4Zm9N.kV8qZ9p5p.EhM3XqS7vN8pFJ9zK1L2m3N4o5P6q7R
Хеш пароля: $2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz123456789ABCDEFGHIJKLMNOPQ
```

### 3. Настройка credentials.json

Откройте файл `auth/credentials.json` и вставьте полученные хеши:

```json
{
  "_comment": "Инструкция: Сгенерируйте bcrypt хеши для логина и пароля, затем вставьте их ниже",
  "_example_generation": "Используйте Python: import bcrypt; bcrypt.hashpw('your_value'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')",
  "username_hash": "$2b$12$KIXxqF4Zm9N.kV8qZ9p5p.EhM3XqS7vN8pFJ9zK1L2m3N4o5P6q7R",
  "password_hash": "$2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz123456789ABCDEFGHIJKLMNOPQ"
}
```

**⚠️ ВАЖНО:**
- Замените примеры выше на **ваши** реальные хеши
- **НЕ** храните исходные логин и пароль в файлах проекта
- Запомните исходные значения логина и пароля - они понадобятся для входа

### 4. Запуск приложения

```bash
python start.py
```

При первом открытии браузера появится модальное окно с запросом логина и пароля.

## Архитектура безопасности

### Что хешируется

- ✅ **Логин** - хешируется через bcrypt
- ✅ **Пароль** - хешируется через bcrypt

### Защищенные endpoint'ы

Следующие API требуют авторизацию:

- `POST /api/job` - создание задачи
- `GET /api/job/<id>` - статус задачи
- `POST /api/job/<id>/stop` - остановка задачи
- `GET /api/job/<id>/log` - скачивание лога
- `GET /api/job/<id>/download` - скачивание CSV
- `GET /api/job/<id>/download-xlsx` - скачивание XLSX
- `GET /api/job/<id>/download-headings-xlsx` - скачивание заголовков
- `POST /api/heartbeat` - heartbeat от клиента

### Публичные endpoint'ы (без авторизации)

- `GET /` - главная страница (HTML)
- `GET /ssh-tools` - страница SSH Tools (HTML)
- `POST /api/auth/login` - вход в систему
- `POST /api/auth/verify` - проверка токена
- `POST /api/auth/logout` - выход
- `GET /api/resource` - использование ресурсов (открыто для статистики)
- `GET /api/stats` - статистика сайта (открыто)

## Механизм аутентификации

1. **Проверка при загрузке** - JavaScript ([auth.js](../static/js/auth.js)) проверяет наличие токена в cookies
2. **Модальное окно** - Если токена нет или он невалиден, показывается окно входа
3. **Отправка credentials** - POST запрос на `/api/auth/login` с логином и паролем
4. **Проверка bcrypt** - Backend проверяет хеши через модуль [auth/auth.py](auth/auth.py)
5. **Создание токена** - При успехе генерируется криптостойкий токен (64 символа)
6. **Сохранение в cookies** - Токен сохраняется с флагами `httponly` и `samesite=Lax`
7. **Проверка на каждом запросе** - Декоратор `@require_auth` проверяет токен

## Смена пароля

Для смены логина или пароля:

1. Сгенерируйте новые хеши (см. раздел "Генерация учетных данных")
2. Обновите `auth/credentials.json`
3. Перезапустите приложение
4. Все существующие сессии станут невалидными

## Безопасность

### Что используется

- ✅ **bcrypt** - современный алгоритм хеширования с солью
- ✅ **secrets.token_hex()** - криптостойкая генерация токенов
- ✅ **httponly cookies** - защита от XSS атак
- ✅ **SameSite=Lax** - защита от CSRF

### Ограничения текущей реализации

⚠️ **Сессии хранятся в памяти** - при перезапуске приложения все пользователи выйдут из системы. Для production рекомендуется использовать Redis или базу данных.

⚠️ **Один пользователь** - текущая реализация поддерживает только одну пару логин/пароль. Для многопользовательской системы расширьте `credentials.json`:

```json
{
  "users": [
    {
      "username_hash": "...",
      "password_hash": "..."
    },
    {
      "username_hash": "...",
      "password_hash": "..."
    }
  ]
}
```

## Устранение неполадок

### Не могу войти - "Invalid credentials"

1. Проверьте что хеши в `credentials.json` корректны (начинаются с `$2b$`)
2. Убедитесь что не осталось placeholder'ов `ВСТАВЬТЕ_СЮДА_ХЕШ_...`
3. Проверьте что вводите **исходные** логин и пароль, а не их хеши

### Приложение не запускается - ImportError: bcrypt

```bash
pip install bcrypt
```

### Модальное окно не появляется

1. Проверьте консоль браузера (F12) на наличие ошибок JavaScript
2. Убедитесь что файлы [auth.css](../static/css/auth.css) и [auth.js](../static/js/auth.js) загружаются
3. Очистите кеш браузера (Ctrl+Shift+R)

### Токен не сохраняется

Проверьте настройки браузера - cookies должны быть включены для данного домена.

## Файлы модуля аутентификации

```
auth/
├── __init__.py          # Экспорт публичного API
├── auth.py              # Backend логика (bcrypt, токены, сессии)
├── credentials.json     # Хешированные учетные данные
└── AUTH_SETUP.md        # Данная инструкция

static/
├── css/auth.css         # Стили модального окна
└── js/auth.js           # Frontend логика авторизации

app.py                   # Интеграция: декоратор, endpoints
templates/index.html     # Модальное окно в HTML
```

## Контакты

Вопросы и предложения: [@semtio](https://t.me/semtio)
