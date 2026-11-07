from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from expenses_bot.config import Settings, load_settings
from expenses_bot.models import WorksheetTarget
from expenses_bot.pipeline import process_file
from expenses_bot.sheets import SheetsClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _allowed(message: Message, settings: Settings) -> bool:
    if not settings.allowed_user_ids:
        return True
    user = message.from_user
    return bool(user and user.id in settings.allowed_user_ids)


def _format_result(result) -> str:
    lines = [
        f"Банк: {result.bank}",
        f"Распознано расходов: {result.total_parsed}",
        f"Записано в таблицу: {result.total_written}",
        "",
    ]
    labels = {
        WorksheetTarget.CASUAL: "Повседневные",
        WorksheetTarget.FLAT: "Квартира",
        WorksheetTarget.BIG: "Крупные",
        WorksheetTarget.TRANSFERS: "Переводы (ручная категория)",
    }
    for target, label in labels.items():
        if result.written:
            count = result.written.get(target.value, 0)
        else:
            count = len(result.grouped.get(target) or [])
        lines.append(f"• {label}: {count}")
    if result.grouped.get(WorksheetTarget.TRANSFERS):
        lines.append(
            "\nСтроки на листе «Переводы»: колонка «Категория» пустая — "
            "проставьте вручную в таблице."
        )
    return "\n".join(lines)


async def run_bot(settings: Settings) -> None:
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    sheets = SheetsClient(settings)
    settings.download_dir.mkdir(parents=True, exist_ok=True)

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await message.answer(
            "Пришлите выписку T Bank (CSV), Ozon Bank (PDF) или Yandex Bank (PDF).\n"
            "Расходы попадут в Повседневные / Квартира / Крупные; "
            "переводы и неопознанные категории — на лист Переводы."
        )

    @dp.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await message.answer(
            "Поддерживаемые файлы v1:\n"
            "• T Bank — CSV операций\n"
            "• Ozon Bank — PDF справка о движении (списания)\n"
            "• Yandex Bank — PDF выписка\n\n"
            "В таблицу пишутся только колонки: Дата, Трата, Категория, Стоимость.\n"
            "DW/MMYY не трогаем (формулы в таблице).\n"
            "Лист «Переводы» — для ручной категоризации переводов."
        )

    @dp.message(F.document)
    async def on_document(message: Message) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        doc = message.document
        if not doc:
            return
        name = doc.file_name or "statement"
        suffix = Path(name).suffix.lower()
        if suffix not in {".csv", ".pdf", ".txt"}:
            await message.answer("Нужен файл .csv или .pdf")
            return

        await message.answer(f"Обрабатываю «{name}»…")
        with tempfile.TemporaryDirectory(dir=settings.download_dir) as tmp:
            dest = Path(tmp) / name
            await bot.download(doc, destination=dest)
            try:
                result = await asyncio.to_thread(
                    process_file,
                    dest,
                    filename=name,
                    sheets=sheets,
                    write=True,
                )
            except Exception as exc:  # noqa: BLE001 — surface to user
                logger.exception("Failed to process %s", name)
                await message.answer(f"Ошибка: {exc}")
                return
        await message.answer(_format_result(result))

    @dp.message()
    async def fallback(message: Message) -> None:
        if not _allowed(message, settings):
            return
        await message.answer("Пришлите файл выписки (.csv / .pdf) или /help")

    logger.info("Bot started")
    await dp.start_polling(bot)


def main() -> None:
    settings = load_settings()
    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
