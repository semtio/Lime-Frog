# PageSpeed Insights Batch Checker

Автоматическая проверка списка сайтов через Google PageSpeed Insights API v5.

## Быстрый старт

### 1. Установите зависимости

```powershell
pip install -r requirements.txt
```

или напрямую:

```powershell
pip install requests
```

### 2. Получите API-ключ

1. Перейдите на https://console.cloud.google.com/
2. Создайте проект или используйте существующий
3. Включите **PageSpeed Insights API**
4. Создайте API-ключ в разделе "Учетные данные"

### 3. Настройте скрипт

Откройте `pagespeed_batch.py` и измените:

```python
# Вставьте ваш API-ключ
API_KEY = "ВАШ_API_КЛЮЧ"

# Добавьте ваши URL
URLS = [
    "https://example.com",
    "https://another-site.com",
]

# Выберите стратегию: "mobile" или "desktop"
STRATEGY = "mobile"
```

### 4. Запустите

```powershell
python pagespeed_batch.py
```

Для параллельной проверки доменов добавьте количество потоков:

```powershell
python pagespeed_batch.py --workers 5
```

## Результаты

Скрипт выводит:

1. **В консоль** - прогресс проверки каждого URL
2. **CSV-файл** (`pagespeed_results.csv`) - результаты в табличном формате
3. **Статистика** - средний балл, мин/макс значения
4. **Markdown-таблица** - для копирования в документацию

## Пример вывода

```
======================================================================
НАЧАЛО ПРОВЕРКИ: 3 URL(s)
Стратегия: MOBILE
======================================================================

[1/3] Проверяю: https://www.google.com (mobile)... ✓ Performance: 92
[2/3] Проверяю: https://www.youtube.com (mobile)... ✓ Performance: 78
[3/3] Проверяю: https://www.wikipedia.org (mobile)... ✓ Performance: 85

✓ Результаты сохранены в файл: pagespeed_results.csv

======================================================================
ИТОГОВАЯ СТАТИСТИКА
======================================================================

Всего проверено: 3
Успешно: 3
Ошибки: 0
Предупреждения: 0

Средний Performance Score: 85.0
Минимальный: 78
Максимальный: 92
```

## Настройки

В начале файла `pagespeed_batch.py` вы можете изменить:

- `API_KEY` - ваш API-ключ Google PageSpeed Insights
- `URLS` - список URL для проверки
- `STRATEGY` - стратегия проверки (`"mobile"` или `"desktop"`)
- `DELAY_BETWEEN_REQUESTS` - задержка между запросами (секунды)

## Обработка ошибок

Скрипт автоматически обрабатывает:

- HTTP ошибки (4xx, 5xx)
- Таймауты
- Отсутствие Performance Score в ответе
- Ограничения API (rate limiting)

При ошибке проверка продолжается для остальных URL.

## Формат CSV

Файл `pagespeed_results.csv` содержит столбцы:

- `URL` - проверенный URL
- `Strategy` - стратегия (mobile/desktop)
- `PerformanceScore` - балл производительности (0-100)
- `Status` - статус проверки (success/error/warning)
- `Error` - описание ошибки (если есть)

## Требования

- Python 3.6+
- библиотека `requests`
- API-ключ Google PageSpeed Insights

## Лицензия

Свободное использование
