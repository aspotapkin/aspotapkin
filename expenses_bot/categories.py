from __future__ import annotations

from dataclasses import dataclass, field

from expenses_bot.models import Expense, WorksheetTarget

# Ported from notebook cell ~30 (T-Bank → sheet category names).
# Values of None mean "not a regular expense" — routed to Переводы for manual review
# (except true internal account moves, which parsers drop earlier).
CATEGORY_RENAME: dict[str, str | None] = {
    "Сервис": "Услуги",
    "Красота": "Красота",
    "Переводы": None,
    "Супермаркеты": "Питание",
    "Экосистема Яндекс": "Регулярные",
    "Местный транспорт": "Транспорт",
    "Фастфуд": "Кафе/Ресторан",
    "Услуги банка": "Регулярные",
    "Мобильная связь": "Регулярные",
    "Такси": "Транспорт",
    "Цветы": "Подарки",
    "Самокаты": "Транспорт",
    "Связь": "Регулярные",
    "Спорттовары": "Спорт и фитнес",
    "Цифровые товары": "Развлечения",
    "Тренировки": "Спорт и фитнес",
    "Ж/д билеты": "Путешествия",
    "Рестораны": "Кафе/Ресторан",
    "Другое": "Прочее",
    "Аптеки": "Здоровье",
    "Книги и\xa0канцтовары": "Прочее",
    "Книги и канцтовары": "Прочее",
    "Проценты": None,
    "Вклады": "Вклады",
    "Финансы": None,
    "Различные услуги": "Услуги",
    "Фото и копицентры": "Услуги",
    "Различные товары": "Прочее",
    "Наличные": None,
    "Турагентства": "Путешествия",
    "Развлечения": "Развлечения",
    "Отели": "Путешествия",
    "Одежда и обувь": "Одежда",
    "Маркетплейсы": "Маркетплейсы",
    "Ремонт и\xa0мебель": "Все для дома",
    "Ремонт и мебель": "Все для дома",
    "Медицина": "Здоровье",
    "Авиабилеты": "Путешествия",
    "Искусство": "Развлечения",
    "Животные": "Прочее",
    "Подарки и творчество": "Подарки",
    "Госуслуги": "Услуги",
    "НКО": "Благотворительность",
    "ЖКХ": "Коммунальные платежи",
    "Образование": "Образование",
    "Транспорт": "Транспорт",
    "Канцтовары": "Прочее",
    "Онлайн-кинотеатры": "Регулярные",
    "Спорт": "Спорт и фитнес",
    "Кредиты": "Кредиты",
    "Комиссия": "Регулярные",
    "Подписки": "Регулярные",
    "Здоровье и красота": "Здоровье",
}

DEFAULT_CASUAL = [
    "Питание",
    "Кафе/Ресторан",
    "Транспорт",
    "Подарки",
    "Здоровье",
    "Одежда",
    "Развлечения",
    "Регулярные",
    "Спорт и фитнес",
    "Маркетплейсы",
    "Красота",
    "Прочее",
    "Алкоголь",
    "Услуги",
]

DEFAULT_FLAT = [
    "Ремонт",
    "Аренда жилья",
    "ЖКХ",
    "Коммунальные платежи",
    "Все для дома",
]

DEFAULT_BIG = [
    "Путешествия",
    "Одежда",
    "Гаджеты",
    "Праздники",
    "Красота и здоровье",
    "Образование",
    "Кредиты",
    "Вклады",
    "Благотворительность",
]

# Description keyword → sheet category (Ozon / Yandex and fallbacks).
DESCRIPTION_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("YANDEX.TAXI", "YANDEX TAXI", "ТАКСИ"), "Транспорт"),
    (("YANDEX LAVKA", "YANDEX.LAVKA", "LAVKA"), "Питание"),
    (("YANDEX PLUS", "YANDEX.PLUS"), "Регулярные"),
    (("YANDEX.MARKET", "YANDEX MARKET"), "Маркетплейсы"),
    (("OZON", "ПЛАТФОРМЕ OZON"), "Маркетплейсы"),
    (("МЕТРО", "METRO", "САМОКАТ", "SCOOTER", "БЕРИ ЗАРЯД"), "Транспорт"),
    (("АПТЕК", "PHARM", "АПТЕКА"), "Здоровье"),
]


@dataclass
class CategoryRouter:
    casual: set[str] = field(default_factory=lambda: set(DEFAULT_CASUAL))
    flat: set[str] = field(default_factory=lambda: set(DEFAULT_FLAT))
    big: set[str] = field(default_factory=lambda: set(DEFAULT_BIG))
    rename: dict[str, str | None] = field(default_factory=lambda: dict(CATEGORY_RENAME))

    def normalize(self, category: str | None, description: str = "") -> str | None:
        raw = (category or "").strip()
        if raw in self.rename:
            mapped = self.rename[raw]
        else:
            mapped = raw or None

        if mapped is None and description:
            inferred = infer_category_from_description(description)
            if inferred:
                return inferred
        return mapped

    def route(self, expense: Expense) -> WorksheetTarget:
        category = expense.category.strip() if expense.category else ""
        if not category:
            return WorksheetTarget.TRANSFERS

        # Ambiguous categories present in more than one list: prefer flat, then big, then casual.
        # Notebook listed Одежда in both casual and big — prefer casual for day-to-day.
        # "Прочее" was in casual and flat notebook lists; send to casual.
        if category in self.flat and category not in self.casual:
            return WorksheetTarget.FLAT
        if category in self.big and category not in self.casual:
            return WorksheetTarget.BIG
        if category in self.casual:
            return WorksheetTarget.CASUAL
        if category in self.flat:
            return WorksheetTarget.FLAT
        if category in self.big:
            return WorksheetTarget.BIG
        return WorksheetTarget.TRANSFERS

    def prepare(self, expense: Expense) -> tuple[Expense, WorksheetTarget]:
        normalized = self.normalize(expense.category or expense.source_category, expense.description)
        if normalized is None:
            prepared = Expense(
                date=expense.date,
                description=expense.description,
                category="",  # blank → manual fill on Переводы
                amount=expense.amount,
                bank=expense.bank,
                source_category=expense.source_category or expense.category,
            )
            return prepared, WorksheetTarget.TRANSFERS

        prepared = Expense(
            date=expense.date,
            description=expense.description,
            category=normalized,
            amount=expense.amount,
            bank=expense.bank,
            source_category=expense.source_category or expense.category,
        )
        return prepared, self.route(prepared)


def infer_category_from_description(description: str) -> str | None:
    upper = description.upper()
    for keywords, category in DESCRIPTION_CATEGORY_RULES:
        if any(k in upper for k in keywords):
            return category
    return None


def default_router() -> CategoryRouter:
    return CategoryRouter()
