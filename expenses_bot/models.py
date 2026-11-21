from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorksheetTarget(str, Enum):
    CASUAL = "Повседневные"
    FLAT = "Квартира"
    BIG = "Крупные"
    TRANSFERS = "Переводы"


def sheets_literal_text(value: str) -> str:
    """Keep USER_ENTERED from treating *, =, +, -, @ as formulas.

    Google Sheets may mangle values like ``YANDEX*4121*TAXI`` under
    ``USER_ENTERED``; a leading apostrophe forces literal text (not shown in UI).
    """
    if not value:
        return value
    if value[0] in "=+-@" or "*" in value:
        if value.startswith("'"):
            return value
        return "'" + value
    return value


@dataclass(slots=True)
class Expense:
    """One expense row ready for Google Sheets."""

    date: str  # DD.MM.YYYY
    description: str  # Трата
    category: str  # Категория (may be empty for Переводы)
    amount: float  # Стоимость, positive RUB
    bank: str = ""
    source_category: str = ""

    def as_sheet_row(self) -> list[str | float]:
        """Columns: Дата, Трата, Категория, Стоимость."""
        return [
            self.date,
            sheets_literal_text(self.description),
            sheets_literal_text(self.category),
            self.amount,
        ]
