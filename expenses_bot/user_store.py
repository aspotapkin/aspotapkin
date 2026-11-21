from __future__ import annotations

import json
import re
import threading
from pathlib import Path

# Google spreadsheet keys are URL-safe base64-ish, typically 44 chars.
SPREADSHEET_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{20,80}$")
SPREADSHEET_URL_RE = re.compile(
    r"(?:https?://)?(?:docs\.google\.com/spreadsheets/d/|sheets\.google\.com/.*[?&]id=)"
    r"([a-zA-Z0-9\-_]{20,80})"
)


def extract_spreadsheet_id(raw: str) -> str:
    """Accept a raw spreadsheet id or a Google Sheets URL."""
    text = (raw or "").strip().strip("<>").strip()
    if not text:
        raise ValueError("Пустой id таблицы")

    match = SPREADSHEET_URL_RE.search(text)
    if match:
        spreadsheet_id = match.group(1)
    else:
        # Bare id, optionally with trailing /edit...
        spreadsheet_id = text.split("/")[0].split("?")[0].strip()

    if not SPREADSHEET_ID_RE.fullmatch(spreadsheet_id):
        raise ValueError(
            "Неверный формат id. Пришлите id или ссылку вида "
            "https://docs.google.com/spreadsheets/d/<ID>/…"
        )
    return spreadsheet_id


def mask_spreadsheet_id(spreadsheet_id: str) -> str:
    if len(spreadsheet_id) <= 10:
        return spreadsheet_id
    return f"{spreadsheet_id[:4]}…{spreadsheet_id[-4:]} ({len(spreadsheet_id)} символов)"


class UserStore:
    """Per-Telegram-user JSON preferences on disk."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def get_user_spreadsheet_id(self, user_id: int) -> str | None:
        with self._lock:
            data = self._read()
            entry = data.get(str(user_id)) or {}
            value = (entry.get("spreadsheet_id") or "").strip()
            return value or None

    def get_spreadsheet_id(self, user_id: int, default: str) -> str:
        return self.get_user_spreadsheet_id(user_id) or default

    def set_spreadsheet_id(self, user_id: int, spreadsheet_id: str) -> str:
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_id)
        with self._lock:
            data = self._read()
            entry = dict(data.get(str(user_id)) or {})
            entry["spreadsheet_id"] = spreadsheet_id
            data[str(user_id)] = entry
            self._write(data)
        return spreadsheet_id

    def clear_spreadsheet_id(self, user_id: int) -> None:
        with self._lock:
            data = self._read()
            entry = dict(data.get(str(user_id)) or {})
            entry.pop("spreadsheet_id", None)
            if entry:
                data[str(user_id)] = entry
            else:
                data.pop(str(user_id), None)
            self._write(data)
