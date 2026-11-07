from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from expenses_bot.categories import infer_category_from_description
from expenses_bot.models import Expense

AMOUNT_RE = re.compile(r"([+\-–−])\s*([\d\s\u00a0]+,\d{2})\s*₽")
DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
TIME_RE = re.compile(r"в\s+\d{2}:\d{2}")
CARD_RE = re.compile(r"\*\d{4}")


def _parse_amount(text: str) -> float | None:
    match = AMOUNT_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    sign = -1 if match.group(1) in "-–−" else 1
    number = match.group(2).replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return sign * float(number)
    except ValueError:
        return None


def _category_for(description: str) -> str:
    inferred = infer_category_from_description(description)
    if inferred:
        return inferred
    low = description.lower()
    if "перевод" in low or "погашение" in low:
        return "Переводы"
    return "Прочее"


def _looks_like_continuation(line: str) -> bool:
    low = line.lower()
    if not line or "страница" in low or "продолжение" in low:
        return False
    if AMOUNT_RE.search(line) and DATE_RE.search(line):
        return False
    # Merchant / address fragments, optionally with time.
    if TIME_RE.search(line):
        return True
    if line.startswith("КС") or line.startswith("+7") or line[:1].isdigit():
        return True
    # ALLCAPS merchant fragments (PLUS, LAVKA, YANDEX.TAXI, …)
    letters = re.sub(r"[^A-Za-zА-Яа-яЁё.]", "", line)
    if letters and letters.upper() == letters and len(letters) >= 3:
        return True
    if any(k in line.upper() for k in ("YANDEX", "LAVKA", "TAXI", "PLUS", "MARKET")):
        return True
    return False


def parse_yandex(path: str | Path) -> list[Expense]:
    """Parse Yandex Bank PDF statement into expense rows (outflows only)."""
    path = Path(path)
    lines: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.splitlines():
                line = raw.replace("\xa0", " ").strip()
                if line:
                    lines.append(line)

    expenses: list[Expense] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        amount = _parse_amount(line)
        dates = DATE_RE.findall(line)
        if amount is None or not dates or "Всего" in line:
            i += 1
            continue

        date = dates[0]
        description = DATE_RE.split(line, maxsplit=1)[0].strip()
        description = CARD_RE.sub("", description).strip()

        # pdfplumber often puts merchant remainder on the next line: "YANDEX.TAXI в 15:14"
        j = i + 1
        extras: list[str] = []
        while j < len(lines) and _looks_like_continuation(lines[j]):
            extra = TIME_RE.sub("", lines[j]).strip(" ,")
            if extra:
                extras.append(extra)
            j += 1
            # Usually one merchant line; allow a couple for long SBP texts / contract ids.
            if len(extras) >= 3:
                break

        if extras:
            description = (description + " " + " ".join(extras)).strip()
        description = re.sub(r"\s+", " ", description)

        i = max(j, i + 1)

        if amount >= 0 or len(description) < 3:
            continue

        category = _category_for(description)
        expenses.append(
            Expense(
                date=date,
                description=description,
                category=category,
                amount=round(abs(amount), 2),
                bank="yandex",
                source_category=category,
            )
        )
    return expenses
