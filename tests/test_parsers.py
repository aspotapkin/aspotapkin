from __future__ import annotations

from pathlib import Path

from expenses_bot.categories import default_router
from expenses_bot.models import WorksheetTarget
from expenses_bot.parsers import detect_bank, parse_ozon, parse_tbank, parse_yandex
from expenses_bot.pipeline import process_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_tbank_parses_expenses():
    path = FIXTURES / "tbank" / "operations.csv"
    assert detect_bank(path) == "tbank"
    rows = parse_tbank(path)
    assert len(rows) >= 3
    assert all(r.amount > 0 for r in rows)
    assert all(r.date.count(".") == 2 for r in rows)
    # Internal transfers / inflows must not appear.
    assert all("Между своими" not in r.description for r in rows)


def test_ozon_outflows_and_inflows():
    outflows = parse_ozon(FIXTURES / "ozon" / "outflows.pdf")
    inflows = parse_ozon(FIXTURES / "ozon" / "inflows.pdf")
    assert detect_bank(FIXTURES / "ozon" / "outflows.pdf") == "ozon"
    assert len(outflows) >= 3
    assert all(r.amount > 0 for r in outflows)
    assert sum(1 for r in outflows if r.category == "Маркетплейсы") >= 3
    assert inflows == []



def test_yandex_parses_expenses():
    path = FIXTURES / "yandex" / "statement.pdf"
    assert detect_bank(path) == "yandex"
    rows = parse_yandex(path)
    assert len(rows) >= 3
    assert all(r.amount > 0 for r in rows)
    descriptions = " ".join(r.description.upper() for r in rows)
    assert "TAXI" in descriptions or "LAVKA" in descriptions or "PLUS" in descriptions or "ОПЛАТА" in descriptions


def test_pipeline_routes_transfers():
    result = process_file(
        FIXTURES / "tbank" / "operations.csv",
        router=default_router(),
        write=False,
    )
    assert result.bank == "tbank"
    assert result.total_parsed >= 3
    # Переводы / unmatched land on transfers sheet target.
    assert WorksheetTarget.TRANSFERS in result.grouped
    # Sheet row order: Дата, Трата, Категория, Стоимость
    for group in result.grouped.values():
        for expense in group:
            row = expense.as_sheet_row()
            assert len(row) == 4
            assert isinstance(row[0], str)
            assert isinstance(row[3], float)


def test_transfer_category_blank():
    result = process_file(
        FIXTURES / "tbank" / "operations.csv",
        router=default_router(),
        write=False,
    )
    transfers = result.grouped[WorksheetTarget.TRANSFERS]
    # If sample has Переводы expenses, category must be blank for manual fill.
    for expense in transfers:
        assert expense.category == ""
