from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from expenses_bot.categories import CategoryRouter, default_router
from expenses_bot.config import Settings
from expenses_bot.models import Expense, WorksheetTarget

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

WRITE_HEADERS = ["Дата", "Трата", "Категория", "Стоимость"]


def get_credentials(client_secrets: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    if creds and creds.valid:
        return creds

    if not client_secrets.exists():
        raise FileNotFoundError(
            f"OAuth client secrets not found: {client_secrets}. "
            "Download Desktop OAuth JSON from Google Cloud Console."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


class SheetsClient:
    def __init__(self, settings: Settings, gc: gspread.Client | None = None):
        self.settings = settings
        if gc is None:
            creds = get_credentials(settings.oauth_client_secrets, settings.oauth_token)
            gc = gspread.authorize(creds)
        self.gc = gc
        self.spreadsheet = self.gc.open_by_key(settings.spreadsheet_id)

    def worksheet_titles(self) -> list[str]:
        return [ws.title for ws in self.spreadsheet.worksheets()]

    def ensure_transfers_sheet(self) -> gspread.Worksheet:
        """Return Переводы worksheet; create with header row if missing."""
        title = self.settings.ws_transfers
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info("Creating worksheet %s", title)
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=4)
            ws.append_row(WRITE_HEADERS, value_input_option="USER_ENTERED")
            return ws

    def load_router_from_directory(self) -> CategoryRouter:
        """Prefer live Справочники category lists when the sheet is present."""
        router = default_router()
        titles = self.worksheet_titles()
        if self.settings.ws_directory not in titles:
            logger.warning(
                "Worksheet %s not found; using notebook default category lists",
                self.settings.ws_directory,
            )
            return router

        ws = self.spreadsheet.worksheet(self.settings.ws_directory)
        values = ws.get_all_values()
        if not values:
            return router

        header = [h.strip() for h in values[0]]
        columns: dict[str, list[str]] = {h: [] for h in header if h}
        for row in values[1:]:
            for idx, name in enumerate(header):
                if not name or idx >= len(row):
                    continue
                cell = row[idx].strip()
                if cell:
                    columns[name].append(cell)

        def pick(*aliases: str) -> set[str] | None:
            for alias in aliases:
                for key, items in columns.items():
                    if key.strip().lower() == alias.lower() and items:
                        return set(items)
            return None

        casual = pick(self.settings.ws_casual, "Повседневные", "casual")
        flat = pick(self.settings.ws_flat, "Квартира", "flat")
        big = pick(self.settings.ws_big, "Крупные", "big")
        if casual:
            router.casual = casual
        if flat:
            router.flat = flat
        if big:
            router.big = big
        return router

    def append_expenses(
        self,
        target: WorksheetTarget | str,
        expenses: Iterable[Expense],
    ) -> int:
        rows = [e.as_sheet_row() for e in expenses]
        if not rows:
            return 0

        title = target.value if isinstance(target, WorksheetTarget) else target
        if title == self.settings.ws_transfers or target == WorksheetTarget.TRANSFERS:
            ws = self.ensure_transfers_sheet()
        else:
            ws = self.spreadsheet.worksheet(title)

        ws.append_rows(rows, value_input_option="USER_ENTERED")
        return len(rows)


def route_and_group(
    expenses: list[Expense],
    router: CategoryRouter | None = None,
) -> dict[WorksheetTarget, list[Expense]]:
    router = router or default_router()
    grouped: dict[WorksheetTarget, list[Expense]] = {
        WorksheetTarget.CASUAL: [],
        WorksheetTarget.FLAT: [],
        WorksheetTarget.BIG: [],
        WorksheetTarget.TRANSFERS: [],
    }
    for expense in expenses:
        prepared, target = router.prepare(expense)
        grouped[target].append(prepared)
    return grouped
