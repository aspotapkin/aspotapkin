from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorksheetTarget(str, Enum):
    CASUAL = "Повседневные"
    FLAT = "Квартира"
    BIG = "Крупные"
    TRANSFERS = "Переводы"


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
        return [self.date, self.description, self.category, self.amount]
