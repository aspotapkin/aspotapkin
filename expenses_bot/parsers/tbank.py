from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import chardet

from expenses_bot.models import Expense

INTERNAL_TRANSFER_DESCRIPTIONS = {
    "Перевод между счетами",
    "Между своими счетами",
}


def _detect_encoding(raw: bytes) -> str:
    guess = chardet.detect(raw) or {}
    encoding = guess.get("encoding") or "utf-8"
    # T-Bank exports are often UTF-8 (sometimes with BOM) or Windows-1251.
    for candidate in (encoding, "utf-8-sig", "utf-8", "cp1251"):
        try:
            raw.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _parse_amount(value: str) -> float:
    cleaned = value.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    return float(cleaned)


def parse_tbank(path: str | Path) -> list[Expense]:
    path = Path(path)
    raw = path.read_bytes()
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding)
    reader = csv.DictReader(StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("T Bank CSV has no header")

    expenses: list[Expense] = []
    for row in reader:
        status = (row.get("Статус") or "").strip()
        if status and status != "Ок":
            continue

        description = (row.get("Описание") or "").strip()
        if description in INTERNAL_TRANSFER_DESCRIPTIONS:
            continue

        amount_raw = row.get("Сумма операции") or ""
        try:
            amount = _parse_amount(amount_raw)
        except ValueError:
            continue

        # Expenses only (negative amounts). Inflows / credits dropped.
        if amount >= 0:
            continue

        date_raw = (row.get("Дата операции") or "").strip()
        date = date_raw[:10]
        category = (row.get("Категория по-умолчанию") or "").strip()
        # Prefer user category when set.
        your_cat = (row.get("Ваша категория") or "").strip()
        if your_cat:
            category = your_cat

        expenses.append(
            Expense(
                date=date,
                description=description or category or "Без описания",
                category=category,
                amount=round(abs(amount), 2),
                bank="tbank",
                source_category=category,
            )
        )
    return expenses
