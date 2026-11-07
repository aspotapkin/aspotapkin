from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from expenses_bot.categories import CategoryRouter, default_router
from expenses_bot.models import Expense, WorksheetTarget
from expenses_bot.parsers import parse_statement
from expenses_bot.sheets import SheetsClient, route_and_group


@dataclass
class ImportResult:
    bank: str
    total_parsed: int
    grouped: dict[WorksheetTarget, list[Expense]]
    written: dict[str, int]

    @property
    def total_written(self) -> int:
        return sum(self.written.values())


def process_file(
    path: str | Path,
    *,
    filename: str | None = None,
    sheets: SheetsClient | None = None,
    router: CategoryRouter | None = None,
    write: bool = True,
) -> ImportResult:
    bank, expenses = parse_statement(path, filename=filename)
    if sheets is not None and router is None:
        router = sheets.load_router_from_directory()
    router = router or default_router()
    grouped = route_and_group(expenses, router)

    written: dict[str, int] = {}
    if write and sheets is not None:
        title_map = {
            WorksheetTarget.CASUAL: sheets.settings.ws_casual,
            WorksheetTarget.FLAT: sheets.settings.ws_flat,
            WorksheetTarget.BIG: sheets.settings.ws_big,
            WorksheetTarget.TRANSFERS: sheets.settings.ws_transfers,
        }
        for target, rows in grouped.items():
            if not rows:
                written[title_map[target]] = 0
                continue
            count = sheets.append_expenses(target, rows)
            written[title_map[target]] = count

    return ImportResult(
        bank=bank,
        total_parsed=len(expenses),
        grouped=grouped,
        written=written,
    )
