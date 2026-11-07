from __future__ import annotations

from expenses_bot.categories import default_router
from expenses_bot.models import Expense, WorksheetTarget


def test_rename_and_route_casual():
    router = default_router()
    expense = Expense(
        date="01.01.2026",
        description="Перекрёсток",
        category="Супермаркеты",
        amount=100,
    )
    prepared, target = router.prepare(expense)
    assert prepared.category == "Питание"
    assert target == WorksheetTarget.CASUAL


def test_transfers_get_blank_category():
    router = default_router()
    expense = Expense(
        date="01.01.2026",
        description="Анна Б.",
        category="Переводы",
        amount=1000,
    )
    prepared, target = router.prepare(expense)
    assert target == WorksheetTarget.TRANSFERS
    assert prepared.category == ""


def test_flat_and_big_routing():
    router = default_router()
    flat, t_flat = router.prepare(
        Expense("01.01.2026", "Икеа", "Все для дома", 5000)
    )
    big, t_big = router.prepare(
        Expense("01.01.2026", "Билет", "Путешествия", 15000)
    )
    assert t_flat == WorksheetTarget.FLAT
    assert flat.category == "Все для дома"
    assert t_big == WorksheetTarget.BIG
    assert big.category == "Путешествия"


def test_unknown_category_goes_to_transfers():
    router = default_router()
    prepared, target = router.prepare(
        Expense("01.01.2026", "Что-то", "НеизвестнаяКатегорияXYZ", 10)
    )
    assert target == WorksheetTarget.TRANSFERS
