import csv
import io
from typing import Iterable, List

from .checks import CSV_COLUMNS_BASE

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


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


def rows_to_xlsx_bytes(rows: Iterable[dict]) -> bytes:
    """Экспортирует данные в формат Excel (.xlsx)"""
    if not HAS_OPENPYXL:
        raise ImportError("openpyxl не установлена. Установите: pip install openpyxl")

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

    wb = Workbook()
    ws = wb.active
    ws.title = "SEO Check Results"

    # Стили для заголовка
    header_fill = PatternFill(
        start_color="4472C4", end_color="4472C4", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Добавляем заголовки
    for col_idx, fieldname in enumerate(fieldnames, start=1):
        cell = ws.cell(row=1, column=col_idx, value=fieldname)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        ws.column_dimensions[cell.column_letter].width = 18

    # Добавляем данные
    for row_idx, row_data in enumerate(rows_list, start=2):
        for col_idx, fieldname in enumerate(fieldnames, start=1):
            value = row_data.get(fieldname, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(
                horizontal="left", vertical="top", wrap_text=True
            )

    # Закрепляем заголовок
    ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
