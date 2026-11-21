from __future__ import annotations

from pathlib import Path

from expenses_bot.models import Expense
from expenses_bot.parsers.detect import detect_bank
from expenses_bot.parsers.ozon import parse_ozon
from expenses_bot.parsers.tbank import parse_tbank
from expenses_bot.parsers.yandex import parse_yandex


def parse_statement(path: str | Path, filename: str | None = None) -> tuple[str, list[Expense]]:
    """Detect bank and parse expenses from a statement file."""
    path = Path(path)
    name = filename or path.name
    bank = detect_bank(path, name)
    if bank == "tbank":
        return bank, parse_tbank(path)
    if bank == "ozon":
        return bank, parse_ozon(path)
    if bank == "yandex":
        return bank, parse_yandex(path)
    raise ValueError(
        f"Unsupported statement: {name}. "
        "v1 supports T Bank CSV, Ozon Bank PDF, Yandex Bank PDF."
    )


__all__ = ["parse_statement", "detect_bank", "parse_tbank", "parse_ozon", "parse_yandex"]
