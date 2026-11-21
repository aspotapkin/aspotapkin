#!/usr/bin/env python3
"""Dry-run parsers against fixtures (no Google / Telegram)."""

from __future__ import annotations

from pathlib import Path

from expenses_bot.categories import default_router
from expenses_bot.pipeline import process_file

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> None:
    paths = [
        FIXTURES / "tbank" / "operations.csv",
        FIXTURES / "ozon" / "outflows.pdf",
        FIXTURES / "ozon" / "inflows.pdf",
        FIXTURES / "yandex" / "statement.pdf",
    ]
    router = default_router()
    for path in paths:
        result = process_file(path, router=router, write=False)
        counts = {k.value: len(v) for k, v in result.grouped.items()}
        print(f"{path.name}: bank={result.bank} parsed={result.total_parsed} routed={counts}")


if __name__ == "__main__":
    main()
