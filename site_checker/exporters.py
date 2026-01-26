import csv
import io
from typing import Iterable, List

from .checks import CSV_COLUMNS_BASE


def rows_to_csv_bytes(rows: Iterable[dict]) -> bytes:
    rows_list = list(rows)
    if not rows_list:
        fieldnames = CSV_COLUMNS_BASE
    else:
        # Собираем все ключи из всех рядов для получения динамических Alt-колонок
        fieldnames = CSV_COLUMNS_BASE.copy()
        all_keys = set()
        for row in rows_list:
            all_keys.update(row.keys())
        # Добавляем Alt-колонки в правильном порядке
        alt_keys = sorted(
            [k for k in all_keys if k.startswith("Alt-")],
            key=lambda x: int(x.split("-")[1]),
        )
        fieldnames.extend(alt_keys)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows_list:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")
