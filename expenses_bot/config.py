from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from expenses_bot.models import WorksheetTarget


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    spreadsheet_id: str
    oauth_client_secrets: Path
    oauth_token: Path
    allowed_user_ids: frozenset[int]
    ws_casual: str = WorksheetTarget.CASUAL.value
    ws_flat: str = WorksheetTarget.FLAT.value
    ws_big: str = WorksheetTarget.BIG.value
    ws_transfers: str = WorksheetTarget.TRANSFERS.value
    ws_directory: str = "Справочники"
    download_dir: Path = Path("downloads")
    data_dir: Path = Path("data")

    @property
    def user_store_path(self) -> Path:
        return self.data_dir / "users.json"


def _parse_user_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return frozenset(ids)


def load_settings(env_file: str | Path | None = ".env") -> Settings:
    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    spreadsheet_id = os.getenv(
        "GOOGLE_SPREADSHEET_ID",
        "1M4X9kFTgdTYL68QnBRIUkSA2IhV3hz00opUqaOC8Rcw",
    ).strip()

    return Settings(
        telegram_bot_token=token,
        spreadsheet_id=spreadsheet_id,
        oauth_client_secrets=Path(
            os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "./secrets/client_secret.json")
        ),
        oauth_token=Path(os.getenv("GOOGLE_OAUTH_TOKEN", "./secrets/token.json")),
        allowed_user_ids=_parse_user_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS")),
        ws_casual=os.getenv("WS_CASUAL", WorksheetTarget.CASUAL.value),
        ws_flat=os.getenv("WS_FLAT", WorksheetTarget.FLAT.value),
        ws_big=os.getenv("WS_BIG", WorksheetTarget.BIG.value),
        ws_transfers=os.getenv("WS_TRANSFERS", WorksheetTarget.TRANSFERS.value),
        ws_directory=os.getenv("WS_DIRECTORY", "Справочники"),
        download_dir=Path(os.getenv("DOWNLOAD_DIR", "downloads")),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
    )
