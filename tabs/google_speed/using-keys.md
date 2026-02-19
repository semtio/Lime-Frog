# Быстрые примеры запуска

Все ключи необязательны, их можно комбинировать. Копируйте любую команду ниже и запускайте в PowerShell/CLI в папке проекта.

```powershell
# Минимальный запуск с настройками по умолчанию
python pagespeed_batch.py

# Мобильная проверка (по умолчанию) с 5 потоками
python pagespeed_batch.py --workers 5

# Десктопная проверка с 5 потоками
python pagespeed_batch.py --workers 5 --strategy desktop

# Проверка всех категорий (performance, accessibility, best-practices, seo)
python pagespeed_batch.py --categories all

# Несколько категорий через запятую (без пробелов)
python pagespeed_batch.py --categories performance,seo

# Ретраи и паузы
python pagespeed_batch.py --workers 10 --delay 1 --max-attempts 5 --retry-delay 20

# Полный пример: mobile + все категории + 8 потоков
python pagespeed_batch.py --categories all --workers 8 --strategy mobile --delay 2 --max-attempts 3 --retry-delay 15
```

## Ключи и значения

- `--workers <int>` — число потоков; `1` = последовательная проверка.
- `--strategy <mobile|desktop>` — стратегия PageSpeed.
- `--delay <float>` — пауза между доменами при последовательной проверке.
- `--max-attempts <int>` — сколько попыток на один домен.
- `--retry-delay <float>` — пауза между попытками одного домена.
- `--categories <all|список>` — `all` или список через запятую без пробелов, например: `performance,seo`.

## Конструктор команды (шаблон)

```powershell
python pagespeed_batch.py --workers <N> --strategy <mobile|desktop> --categories <all|performance,seo> --delay <сек> --max-attempts <N> --retry-delay <сек>
```

Можно указывать только нужные ключи, остальные значения возьмутся по умолчанию.
