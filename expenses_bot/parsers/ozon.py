from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from expenses_bot.models import Expense

AMOUNT_RE = re.compile(
    r"([+\-–−])\s*([\d\s\u00a0]+[.,]\d{2})\s*₽",
    re.UNICODE,
)
DATE_RE = re.compile(r"^(\d{2}\.\d{2}\.\d{4})")


def _parse_amount(token: str) -> float | None:
    match = AMOUNT_RE.search(token.replace("\xa0", " "))
    if not match:
        return None
    sign = -1 if match.group(1) in "-–−" else 1
    number = match.group(2).replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return sign * float(number)
    except ValueError:
        return None


def _clean_description(text: str) -> str:
    parts = [p.strip() for p in (text or "").splitlines() if p.strip()]
    joined = " ".join(parts)
    joined = re.sub(r"\s+", " ", joined).strip()
    # Drop trailing VAT boilerplate.
    joined = re.sub(r"\.?\s*Без НДС\.?\s*$", "", joined, flags=re.IGNORECASE)
    return joined or "Озон"


def parse_ozon(path: str | Path) -> list[Expense]:
    """Parse Ozon Bank movement PDF (outflows and/or inflows).

    Only negative amounts (expenses) are returned. Inflows PDFs yield [].
    """
    path = Path(path)
    expenses: list[Expense] = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    date_cell = (row[0] or "").strip()
                    if not DATE_RE.match(date_cell):
                        continue
                    date = date_cell[:10]
                    description = _clean_description(row[2] or "")
                    amount = _parse_amount(row[3] or "")
                    if amount is None or amount >= 0:
                        continue

                    # Marketplace purchases on Ozon platform.
                    category = "Маркетплейсы"
                    if "перевод" in description.lower():
                        category = "Переводы"

                    expenses.append(
                        Expense(
                            date=date,
                            description=description,
                            category=category,
                            amount=round(abs(amount), 2),
                            bank="ozon",
                            source_category=category,
                        )
                    )
    return expenses
