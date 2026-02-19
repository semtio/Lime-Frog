#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АВТОМАТИЧЕСКАЯ ПРОВЕРКА САЙТОВ ЧЕРЕЗ GOOGLE PAGESPEED INSIGHTS API V5

ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ:
1. Установите библиотеку requests (если еще не установлена):
   pip install requests

2. Получите API-ключ Google PageSpeed Insights:
   - Перейдите на https://console.cloud.google.com/
   - Создайте проект или используйте существующий
   - Включите PageSpeed Insights API
   - Создайте API-ключ в разделе "Учетные данные"

3. Вставьте ваш API-ключ в переменную API_KEY ниже
4. Добавьте ваши URL в список URLS
5. При необходимости измените STRATEGY на "desktop" (по умолчанию "mobile")
6. Запустите скрипт: python pagespeed_batch.py

РЕЗУЛЬТАТ:
- Вывод в консоль для каждого URL
- Сохранение результатов в файл pagespeed_results.txt

запуск скрипта:
$ python pagespeed_batch.py
$ python pagespeed_batch.py --workers 5
$ python pagespeed_batch.py --strategy desktop
$ python pagespeed_batch.py --categories all
$ python pagespeed_batch.py --categories performance
$ python pagespeed_batch.py --categories accessibility
$ python pagespeed_batch.py --categories best-practices
$ python pagespeed_batch.py --categories seo
$ python pagespeed_batch.py --delay 3
$ python pagespeed_batch.py --max-attempts 5
$ python pagespeed_batch.py --retry-delay 20
$ python pagespeed_batch.py --categories performance,seo,accessibility
$ python pagespeed_batch.py --categories all --workers 5 --strategy desktop
$ python pagespeed_batch.py --categories all --workers 5 --strategy mobile

# для каждодневного использования (БЕЗ пробелов после запятой!)
#1 Полная проверка
python pagespeed_batch.py --categories performance,best-practices --workers 10 --strategy mobile

#2 только performance
python pagespeed_batch.py --categories performance --workers 10 --strategy mobile
"""

import argparse
import concurrent.futures
import requests
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse


# ==================== НАСТРОЙКИ ====================
# Вставьте ваш API-ключ Google PageSpeed Insights
API_KEY = "AIzaSyDb-kJrCHI42NOPvrc03W4VidAP7LeV7Lw"

# Список URL для проверки (добавьте свои сайты)
URLS = [
    "fragagiris-az.ink",
    "fragabet-giris-az.ink",
    "fraga-giris-az.ink",
    "fragabetyukle.net",
    "fragabet-giris-az.site",
    "fraga-giris-az.com",
    "fragagiris-az.live",
    "fragagiris-az.site",
    "fragagiris-az.com",
    "fragagiris-az.org",
    "fragabetindir.com",
    "fragabetyukle.live",
    "fragabetyukle.org",
    "fraga-giris-az.live",
    "fragabetyukle.site",
    "fragabet-azerbaycan.ink",
    "fragabetyukle.ink",
    "fraga-giris-az.net",
    "fragagiris-az.net",
    "fraga-kazino.click",
    "fragacasino-az.site",
    "fraga-giris-az.site",
    "fragabetgiris-az.site",
    "fragabetgiris-az.com",
    "fragabet-kazinoaz.live",
    "fraga-kazino.net",
    "fraga-kazino.ink",
    "fragabetgiris-az.live",
    "fragabet-giris-az.com",
    "fraga-kazino.com",
    "fragabet-kazino.com",
    "fragabet-giris-az.net",
    "fragabet-kazinoaz.com",
    "fragabetindir.net",
    "fragacasino-az.ink",
    "fragabetgiris-az.net",
    "fraga-giris-az.org",
    "fragabet-kazino.live",
    "fragabetindir.live",
    "fraga-kazino.live",
    "fragacasino-az.live",
    "fragabet-giris-az.live",
    "fragabet-casino-az.com",
    "fragabetyukle.com",
]

# Стратегия проверки: "mobile" или "desktop"
STRATEGY = "mobile"

# Задержка между запросами (в секундах) между разными доменами
DELAY_BETWEEN_REQUESTS = 2

# Максимальное количество попыток проверки одного домена при ошибках
MAX_ATTEMPTS_PER_URL = 3
# Задержка между повторными попытками одного и того же домена (секунды)
PER_URL_RETRY_DELAY_SECONDS = 15
# ===================================================


class PageSpeedChecker:
    """Класс для проверки производительности сайтов через PageSpeed Insights API"""

    API_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def __init__(
        self, api_key: str, strategy: str = "mobile", categories: List[str] = None
    ):
        """
        Инициализация проверки

        Args:
            api_key: API-ключ Google PageSpeed Insights
            strategy: Стратегия проверки ("mobile" или "desktop")
            categories: Список категорий для проверки (performance, accessibility, best-practices, seo)
        """
        self.api_key = api_key
        self.strategy = strategy
        self.categories = categories or ["performance"]
        self.results = []

    def check_url(self, url: str) -> Dict[str, any]:
        """
        Проверка одного URL через PageSpeed Insights API

        Args:
            url: URL для проверки

        Returns:
            Словарь с результатами проверки
        """
        params = {"url": url, "key": self.api_key, "strategy": self.strategy}

        # Добавляем категории в параметры запроса
        # Маппинг для API (API использует SCREAMING_CASE для некоторых категорий)
        category_api_names = {
            "performance": "PERFORMANCE",
            "accessibility": "ACCESSIBILITY",
            "best-practices": "BEST_PRACTICES",
            "seo": "SEO",
        }

        # Формируем список кортежей для параметров (чтобы category повторялся)
        param_list = [("url", url), ("key", self.api_key), ("strategy", self.strategy)]
        for category in self.categories:
            api_name = category_api_names.get(category, category.upper())
            param_list.append(("category", api_name))

        try:
            print(f"Проверяю: {url} ({self.strategy})...", end=" ")

            response = requests.get(self.API_ENDPOINT, params=param_list, timeout=60)
            response.raise_for_status()

            data = response.json()

            # Извлекаем все запрошенные категории
            categories_data = data.get("lighthouseResult", {}).get("categories", {})

            # Маппинг названий категорий
            category_mapping = {
                "performance": "performance",
                "accessibility": "accessibility",
                "best-practices": "best-practices",
                "seo": "seo",
            }

            scores = {}
            missing_categories = []

            for category in self.categories:
                api_category = category_mapping.get(category, category)
                score = categories_data.get(api_category, {}).get("score")

                if score is not None:
                    # Конвертируем из диапазона 0-1 в 0-100
                    scores[category] = round(score * 100)
                else:
                    scores[category] = None
                    missing_categories.append(category)

            # Формируем вывод
            score_strings = [
                f"{cat.upper()}: {scores[cat]}"
                for cat in self.categories
                if scores[cat] is not None
            ]
            if score_strings:
                print(f"✓ {', '.join(score_strings)}")

            result = {
                "url": url,
                "strategy": self.strategy,
                "scores": scores,
                "status": "success" if not missing_categories else "warning",
            }

            if missing_categories:
                result["error"] = (
                    f"Категории не найдены: {', '.join(missing_categories)}"
                )
                print(f"⚠ Предупреждение: {result['error']}")

            # Для обратной совместимости
            result["performance_score"] = scores.get("performance")

            return result

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP ошибка {response.status_code}"
            try:
                error_details = response.json()
                if "error" in error_details:
                    error_msg += f": {error_details['error'].get('message', '')}"
            except:
                pass

            print(f"✗ ERROR: {error_msg}")
            return {
                "url": url,
                "strategy": self.strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": error_msg,
            }

        except requests.exceptions.Timeout:
            print(f"✗ ERROR: Таймаут запроса")
            return {
                "url": url,
                "strategy": self.strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": "Таймаут запроса",
            }

        except requests.exceptions.RequestException as e:
            print(f"✗ ERROR: {str(e)}")
            return {
                "url": url,
                "strategy": self.strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": str(e),
            }

        except Exception as e:
            print(f"✗ ERROR: Неожиданная ошибка - {str(e)}")
            return {
                "url": url,
                "strategy": self.strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": f"Неожиданная ошибка: {str(e)}",
            }

    def check_url_with_retries(
        self,
        url: str,
        max_attempts: int,
        per_url_retry_delay: float,
        idx: int,
        total: int,
    ) -> Dict:
        """Повторяет запрос к API несколько раз перед фиксацией ошибки"""
        print(f"[{idx}/{total}] ДОМЕН: {url}")
        attempts = 0
        final_result = None

        while attempts < max_attempts:
            attempts += 1
            print(f"  Попытка {attempts}/{max_attempts}: ", end="")
            result = self.check_url(url)
            final_result = result
            if result["status"] == "success":
                break
            if attempts < max_attempts:
                time.sleep(per_url_retry_delay)

        if final_result and final_result["status"] != "success":
            final_result["error"] = (
                f"{final_result.get('error','Unknown')} (FAILED after {attempts} attempts)"
            )
        return final_result

    def check_multiple_urls(
        self,
        urls: List[str],
        delay: float = 2,
        max_attempts: int = 3,
        per_url_retry_delay: float = 15,
        max_workers: int = 1,
    ) -> List[Dict]:
        """
        Проверка списка URL с возможностью параллельного запуска

        Args:
            urls: Список URL для проверки
            delay: Задержка между запросами в секундах (используется при последовательной проверке)
            max_attempts: Максимум попыток на домен
            per_url_retry_delay: Пауза между попытками одного домена
            max_workers: Количество потоков для параллельной проверки
        """
        print(f"\n{'='*70}")
        print(f"НАЧАЛО ПРОВЕРКИ: {len(urls)} URL(s)")
        print(f"Стратегия: {self.strategy.upper()}")
        print(f"Потоков: {max_workers}")
        print(f"{'='*70}\n")

        if max_workers <= 1:
            for i, url in enumerate(urls, 1):
                result = self.check_url_with_retries(
                    url,
                    max_attempts=max_attempts,
                    per_url_retry_delay=per_url_retry_delay,
                    idx=i,
                    total=len(urls),
                )
                self.results.append(result)
                if i < len(urls):
                    time.sleep(delay)
            return self.results

        ordered_results: List[Optional[Dict]] = [None] * len(urls)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(
                    self.check_url_with_retries,
                    url,
                    max_attempts,
                    per_url_retry_delay,
                    idx,
                    len(urls),
                ): idx
                for idx, url in enumerate(urls, 1)
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                result = future.result()
                ordered_results[idx - 1] = result

        self.results.extend(ordered_results)
        return self.results

    def save_to_txt(self, filename: str = "pagespeed_results.txt"):
        """
        Сохранение результатов в TXT-файл

        Args:
            filename: Имя файла для сохранения
        """
        if not self.results:
            print("\nНет результатов для сохранения")
            return

        try:
            with open(filename, "w", encoding="utf-8") as txtfile:
                for result in self.results:
                    # Извлекаем домен из URL
                    parsed_url = urlparse(result["url"])
                    domain = parsed_url.netloc or parsed_url.path

                    # Формируем строку результата
                    if result["status"] == "error":
                        txtfile.write(f"{domain} = ERROR\n")
                    else:
                        scores = result.get("scores", {})
                        score_parts = []
                        for category in self.categories:
                            score = scores.get(category)
                            if score is not None:
                                score_parts.append(f"{category.upper()}={score}")
                            else:
                                score_parts.append(f"{category.upper()}=N/A")

                        txtfile.write(f"{domain} = {', '.join(score_parts)}\n")

            print(f"\n✓ Результаты сохранены в файл: {filename}")
        except Exception as e:
            print(f"\n✗ Ошибка при сохранении в TXT: {str(e)}")

    def print_summary(self):
        """Вывод итоговой статистики"""
        if not self.results:
            print("\nНет результатов для отображения")
            return

        print(f"\n{'='*70}")
        print("ИТОГОВАЯ СТАТИСТИКА")
        print(f"{'='*70}\n")

        successful = [r for r in self.results if r["status"] == "success"]
        errors = [r for r in self.results if r["status"] == "error"]
        warnings = [r for r in self.results if r["status"] == "warning"]

        print(f"Всего проверено: {len(self.results)}")
        print(f"Успешно: {len(successful)}")
        print(f"Ошибки: {len(errors)}")
        print(f"Предупреждения: {len(warnings)}")

        if successful:
            # Статистика по каждой категории
            for category in self.categories:
                category_scores = [
                    r["scores"].get(category)
                    for r in successful
                    if r["scores"].get(category) is not None
                ]
                if category_scores:
                    avg_score = sum(category_scores) / len(category_scores)
                    print(f"\n{category.upper()}:")
                    print(f"  Средний Score: {avg_score:.1f}")
                    print(f"  Минимальный: {min(category_scores)}")
                    print(f"  Максимальный: {max(category_scores)}")

        # Markdown таблица
        print(f"\n{'='*70}")
        print("РЕЗУЛЬТАТЫ В ФОРМАТЕ MARKDOWN TABLE")
        print(f"{'='*70}\n")

        # Формируем заголовок таблицы
        header_categories = " | ".join([cat.upper() for cat in self.categories])
        print(f"| URL | Strategy | {header_categories} |")
        separator = (
            "|".join(["-" * 5, "-" * 10] + ["-" * 10 for _ in self.categories]) + "|"
        )
        print(separator)

        for result in self.results:
            scores = result.get("scores", {})
            score_values = []

            for category in self.categories:
                score = scores.get(category)
                if result["status"] == "error":
                    score_values.append("ERROR")
                elif score is not None:
                    score_values.append(str(score))
                else:
                    score_values.append("N/A")

            scores_str = " | ".join(score_values)
            print(f"| {result['url']} | {result['strategy']} | {scores_str} |")


def main():
    """Основная функция запуска скрипта"""

    parser = argparse.ArgumentParser(description="PageSpeed Insights batch checker")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Количество параллельных потоков (1 = последовательно)",
    )
    parser.add_argument(
        "--strategy",
        choices=["mobile", "desktop"],
        default=STRATEGY,
        help="Стратегия проверки: mobile или desktop",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DELAY_BETWEEN_REQUESTS,
        help="Пауза между доменами при последовательной проверке",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS_PER_URL,
        help="Количество попыток для одного домена",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=PER_URL_RETRY_DELAY_SECONDS,
        help="Пауза между попытками для одного домена",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default="performance",
        help="Категории для проверки: all, performance, accessibility, best-practices, seo (можно указать несколько через запятую, например: performance,seo)",
    )

    args = parser.parse_args()

    # Проверка наличия API-ключа
    if API_KEY == "ВАШ_API_КЛЮЧ":
        print("=" * 70)
        print("ОШИБКА: Необходимо указать API-ключ!")
        print("=" * 70)
        print("\nПожалуйста, замените 'ВАШ_API_КЛЮЧ' на реальный API-ключ")
        print("Google PageSpeed Insights API.\n")
        print("Как получить API-ключ:")
        print("1. Перейдите на https://console.cloud.google.com/")
        print("2. Создайте проект или используйте существующий")
        print("3. Включите PageSpeed Insights API")
        print("4. Создайте API-ключ в разделе 'Учетные данные'")
        print("=" * 70)
        return

    # Проверка наличия URL
    if not URLS:
        print("ОШИБКА: Список URL пуст. Добавьте URL в переменную URLS")
        return

    # Автоматическое добавление https:// к URL без протокола
    normalized_urls = []
    for url in URLS:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            print(f"ℹ Добавлен протокол: {url}")
        normalized_urls.append(url)

    # Обработка категорий
    if args.categories.lower() == "all":
        categories = ["performance", "accessibility", "best-practices", "seo"]
    else:
        categories = [cat.strip().lower() for cat in args.categories.split(",")]

    # Валидация категорий
    valid_categories = ["performance", "accessibility", "best-practices", "seo"]
    invalid = [cat for cat in categories if cat not in valid_categories]
    if invalid:
        print(f"ОШИБКА: Неверные категории: {', '.join(invalid)}")
        print(f"Допустимые значения: {', '.join(valid_categories)}, all")
        return

    # Создание экземпляра проверки
    checker = PageSpeedChecker(
        api_key=API_KEY, strategy=args.strategy, categories=categories
    )

    # Проверка всех URL с повторными попытками при ошибках
    checker.check_multiple_urls(
        normalized_urls,
        delay=args.delay,
        max_attempts=args.max_attempts,
        per_url_retry_delay=args.retry_delay,
        max_workers=max(args.workers, 1),
    )

    # Сохранение результатов в TXT
    checker.save_to_txt()

    # Вывод итоговой статистики
    checker.print_summary()


if __name__ == "__main__":
    main()
