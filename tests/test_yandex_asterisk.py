from __future__ import annotations

from pathlib import Path

from expenses_bot.categories import default_router, infer_category_from_description
from expenses_bot.models import Expense, sheets_literal_text
from expenses_bot.parsers.yandex import CARD_TOKEN_RE, _description_from_amount_line, parse_yandex

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = Path(
    "/cursor/stores/bc-f15be50e-b72c-4725-aa15-718881e668e3/samples/yandex/statement.pdf"
)


def test_card_token_spares_merchant_mcc():
    merchant = "Оплата товаров и услуг YANDEX*4121*TAXI"
    assert CARD_TOKEN_RE.sub("", merchant) == merchant
    assert _description_from_amount_line(
        "Оплата товаров и услуг YANDEX*4121*TAXI 14.02.2026 14.02.2026 *2678 –996,00 ₽"
    ) == "Оплата товаров и услуг YANDEX*4121*TAXI"


def test_card_token_strips_standalone_card():
    assert (
        CARD_TOKEN_RE.sub("", "Оплата товаров и услуг *2678").strip()
        == "Оплата товаров и услуг"
    )


def test_parse_preserves_asterisk_merchants():
    path = SAMPLE if SAMPLE.exists() else FIXTURES / "yandex" / "statement.pdf"
    rows = parse_yandex(path)
    taxi = [r for r in rows if "YANDEX*4121*TAXI" in r.description]
    assert taxi, "expected YANDEX*4121*TAXI rows from sample"
    for row in taxi:
        assert row.description.startswith("Оплата товаров и услуг YANDEX*4121*TAXI")
        assert "YANDEX*4" != row.description
        assert "*4121*" in row.description
        # Must not look like the reported sheet corruption.
        assert not row.description.startswith("оваров")


def test_asterisk_merchants_categorized():
    assert infer_category_from_description("YANDEX*4121*TAXI") == "Транспорт"
    assert infer_category_from_description("YANDEX*5411*LAVKA") == "Питание"
    assert infer_category_from_description("YANDEX*5814*EDA") == "Кафе/Ресторан"
    assert infer_category_from_description("YANDEX*5399*MARKET") == "Маркетплейсы"
    from expenses_bot.models import WorksheetTarget

    prepared, target = default_router().prepare(
        Expense(
            "14.02.2026",
            "Оплата товаров и услуг YANDEX*4121*TAXI",
            "Транспорт",
            996.0,
        )
    )
    assert prepared.category == "Транспорт"
    assert target == WorksheetTarget.CASUAL


def test_sheets_literal_preserves_asterisks():
    raw = "Оплата товаров и услуг YANDEX*4121*TAXI"
    cell = sheets_literal_text(raw)
    assert cell.startswith("'")
    assert "YANDEX*4121*TAXI" in cell
    row = Expense("14.02.2026", raw, "Транспорт", 996.0).as_sheet_row()
    assert row[1] == "'" + raw
