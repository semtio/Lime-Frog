#!/usr/bin/env python3
"""
Инструмент для извлечения значения атрибута alt из <img> внутри <a href="..."></a>.
Использование:
  python extract_alt_img.py --in input.txt --out result.csv --delay 0.5 --timeout 15 --flow 10
Параметры:
  --flow: количество параллельных потоков (по умолчанию 10)
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock
from typing import Iterable, List, Optional, Tuple
from urllib.parse import (
    parse_qsl,
    quote,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
    unquote,
)

import requests
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import RequestException, Timeout

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class ProcessResult:
    first_url: str
    second_url: str
    image_alt: str
    status: str


def canonicalize_url(url: str) -> str:
    if not url:
        return ""

    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    decoded_path = parsed.path or ""
    if decoded_path:
        decoded_path = unquote(decoded_path)
        if decoded_path != "/" and decoded_path.endswith("/"):
            decoded_path = decoded_path.rstrip("/")
    normalized_path = quote(decoded_path, safe="/:@-._~!$&'()*+,;=")

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_items.sort()
    canonical_query = urlencode(query_items, doseq=True)

    return urlunsplit((scheme, netloc, normalized_path, canonical_query, ""))


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def find_image_alt(html: str, base_url: str, target_url: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    base_tag = soup.find("base", href=True)
    effective_base = urljoin(base_url, base_tag["href"]) if base_tag else base_url

    target_absolute = urljoin(effective_base, target_url)
    target_canonical = canonicalize_url(target_absolute)

    direct_matches: List[List[str]] = []
    soft_matches: List[List[str]] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not href:
            continue

        resolved_href = urljoin(effective_base, href)
        images = anchor.find_all("img")
        if not images:
            continue

        alt_candidates = [_clean_text(img.get("alt", "")) for img in images]
        alt_candidates = [alt for alt in alt_candidates if alt]

        if not alt_candidates:
            continue

        if resolved_href == target_absolute:
            direct_matches.append(alt_candidates)
            continue

        candidate_canon = canonicalize_url(resolved_href)
        if candidate_canon == target_canonical:
            soft_matches.append(alt_candidates)

    for candidate_group in (direct_matches, soft_matches):
        if not candidate_group:
            continue
        for alts in candidate_group:
            if alts:
                return alts[0]
    return None


def read_input_lines(path: str) -> List[Tuple[int, str]]:
    lines: List[Tuple[int, str]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for idx, raw_line in enumerate(handle, 1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append((idx, stripped))
    return lines


def process_line(
    session: requests.Session,
    first_url: str,
    second_url: str,
    timeout: float,
) -> ProcessResult:
    try:
        response: Response = session.get(first_url, timeout=timeout)
    except Timeout:
        return ProcessResult(first_url, second_url, "", "timeout")
    except RequestException:
        return ProcessResult(first_url, second_url, "", "http_error:0")

    if response.status_code >= 400:
        return ProcessResult(
            first_url, second_url, "", f"http_error:{response.status_code}"
        )

    if not response.encoding:
        response.encoding = response.apparent_encoding or "utf-8"

    html = response.text
    try:
        image_alt = find_image_alt(html, response.url or first_url, second_url)
    except Exception:
        return ProcessResult(first_url, second_url, "", "parse_error")

    if image_alt is None:
        return ProcessResult(first_url, second_url, "", "not_found")

    return ProcessResult(first_url, second_url, image_alt, "ok")


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract <img alt> text inside anchor tags for paired URLs"
    )
    parser.add_argument(
        "--in", dest="input_path", required=True, help="Путь к входному файлу"
    )
    parser.add_argument(
        "--out", dest="output_path", default="out.csv", help="Путь к выходному CSV"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Задержка между запросами (сек)"
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0, help="HTTP-таймаут (сек)"
    )
    parser.add_argument(
        "--ua", dest="user_agent", default=DEFAULT_USER_AGENT, help="User-Agent"
    )
    parser.add_argument(
        "--flow", type=int, default=10, help="Количество параллельных потоков"
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    entries = read_input_lines(args.input_path)
    total = len(entries)

    session = build_session(args.user_agent)

    any_error_for_exit = False
    csv_lock = Lock()
    completed_count = 0
    count_lock = Lock()

    def process_entry(entry_data: Tuple[int, Tuple[int, str]]) -> None:
        nonlocal any_error_for_exit, completed_count

        index, (line_no, line) = entry_data

        # Задержка перед каждым запросом (кроме первого)
        if index > 1 and args.delay > 0:
            time.sleep(args.delay)

        parts = line.split()
        first_url = parts[0] if parts else ""
        second_url = parts[1] if len(parts) > 1 else ""

        if len(parts) < 2:
            status = "bad_input"
            result_row = [first_url, second_url, "", status]
            with csv_lock:
                writer.writerow(result_row)
            with count_lock:
                completed_count += 1
                print(
                    f"[{completed_count}/{total}] {first_url or '<missing>'} -> {status}"
                )
            return

        # Каждый поток создает свою сессию для thread-safety
        thread_session = build_session(args.user_agent)
        result = process_line(thread_session, first_url, second_url, args.timeout)

        result_row = [
            result.first_url,
            result.second_url,
            result.image_alt,
            result.status,
        ]

        with csv_lock:
            writer.writerow(result_row)

        with count_lock:
            completed_count += 1
            print(f"[{completed_count}/{total}] {first_url} -> {result.status}")

        if result.status.startswith("http_error") or result.status in {
            "timeout",
            "parse_error",
        }:
            any_error_for_exit = True

    with open(args.output_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["first_url", "second_url", "image_alt", "status"])

        # Подготовка данных для многопоточной обработки
        indexed_entries = [(index, entry) for index, entry in enumerate(entries, 1)]

        # Многопоточная обработка
        with ThreadPoolExecutor(max_workers=args.flow) as executor:
            futures = [
                executor.submit(process_entry, entry_data)
                for entry_data in indexed_entries
            ]

            # Ожидание завершения всех задач
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Ошибка в потоке: {e}")

    return 1 if any_error_for_exit else 0


if __name__ == "__main__":
    sys.exit(main())
