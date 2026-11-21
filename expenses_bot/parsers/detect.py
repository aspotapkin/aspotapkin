from __future__ import annotations

from pathlib import Path


def detect_bank(path: str | Path, filename: str | None = None) -> str:
    path = Path(path)
    name = (filename or path.name).lower()
    suffix = path.suffix.lower()

    if suffix in {".csv", ".txt"} or "operation" in name or "tbank" in name or "tinkoff" in name:
        if suffix in {".csv", ".txt"}:
            # Confirm T-Bank header when possible.
            try:
                head = path.read_bytes()[:4000]
                text = head.decode("utf-8", errors="ignore") + head.decode("cp1251", errors="ignore")
                if "Категория по-умолчанию" in text or "Дата операции" in text:
                    return "tbank"
            except OSError:
                pass
            if suffix == ".csv":
                return "tbank"

    if suffix == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                text = ""
                for page in pdf.pages[:2]:
                    text += page.extract_text() or ""
        except Exception:
            text = ""
        lower = text.lower()
        if "озон банк" in lower or "ozon" in lower and "справка о движении" in lower:
            return "ozon"
        if "яндекс банк" in lower or "счёт эдс" in lower or "yandex" in name:
            return "yandex"
        if "ozon" in name:
            return "ozon"
        if "yandex" in name or "яндекс" in name:
            return "yandex"

    raise ValueError(f"Cannot detect bank for {filename or path.name}")
