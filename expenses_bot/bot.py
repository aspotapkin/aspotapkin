from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from expenses_bot.config import Settings, load_settings
from expenses_bot.models import WorksheetTarget
from expenses_bot.pipeline import process_file
from expenses_bot.sheets import SheetsClient
from expenses_bot.user_store import UserStore, extract_spreadsheet_id, mask_spreadsheet_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SheetSetup(StatesGroup):
    waiting_for_id = State()


def _allowed(message: Message, settings: Settings) -> bool:
    if not settings.allowed_user_ids:
        return True
    user = message.from_user
    return bool(user and user.id in settings.allowed_user_ids)


def _user_id(message: Message) -> int:
    if not message.from_user:
        raise RuntimeError("Message has no from_user")
    return message.from_user.id


def _format_result(result) -> str:
    lines = [
        f"Банк: {result.bank}",
        f"Таблица: {mask_spreadsheet_id(result.spreadsheet_id) if result.spreadsheet_id else '—'}",
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


def _help_text() -> str:
    return (
        "Команды:\n"
        "• `/start` — приветствие, текущая таблица, краткая подсказка\n"
        "• `/help` — этот список команд\n"
        "• `/sheet` — показать текущий spreadsheet id (полный и короткий)\n"
        "• `/set_sheet <id_или_url>` — сохранить таблицу (id или ссылка Google Sheets)\n"
        "• `/set_sheet` — затем пришлите id/ссылку следующим сообщением\n"
        "• `/reset_sheet` — сбросить персональную таблицу → `GOOGLE_SPREADSHEET_ID` из .env\n"
        "• `/cancel` — отменить ожидание id таблицы\n\n"
        "Файлы:\n"
        "• пришлите документ `.csv` / `.pdf` — разбор выписки и запись в таблицу\n"
        "  (T Bank CSV, Ozon Bank PDF, Yandex Bank PDF)\n\n"
        "В таблицу пишутся только: Дата, Трата, Категория, Стоимость.\n"
        "DW/MMYY не трогаем. Переводы и неопознанные категории → лист «Переводы»."
    )


def _start_text(sheet_id: str) -> str:
    return (
        "Бот учёта расходов.\n\n"
        f"Текущая Google-таблица: `{mask_spreadsheet_id(sheet_id)}`\n\n"
        "Пришлите выписку T Bank (CSV), Ozon Bank (PDF) или Yandex Bank (PDF).\n"
        "Расходы → Повседневные / Квартира / Крупные; переводы → Переводы.\n\n"
        "Список команд: `/help`\n\n"
        "Сменить таблицу: `/set_sheet <id_или_url>` или `/set_sheet` и ответом."
    )


async def _apply_sheet_id(
    message: Message,
    *,
    raw: str,
    settings: Settings,
    store: UserStore,
    sheets: SheetsClient,
    state: FSMContext,
) -> None:
    try:
        spreadsheet_id = extract_spreadsheet_id(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    ok, detail = await asyncio.to_thread(sheets.try_open, spreadsheet_id)
    if not ok:
        await message.answer(
            f"Id выглядит валидным (`{mask_spreadsheet_id(spreadsheet_id)}`), "
            f"но открыть таблицу не удалось:\n{detail}\n"
            "Проверьте доступ OAuth-аккаунта и попробуйте снова."
        )
        return

    store.set_spreadsheet_id(_user_id(message), spreadsheet_id)
    await state.clear()
    await message.answer(
        f"Таблица сохранена: `{mask_spreadsheet_id(spreadsheet_id)}`\n{detail}",
        parse_mode="Markdown",
    )


async def run_bot(settings: Settings) -> None:
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    sheets = SheetsClient(settings)
    store = UserStore(settings.user_store_path)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    @dp.message(CommandStart())
    async def start(message: Message, state: FSMContext) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await state.clear()
        sheet_id = store.get_spreadsheet_id(_user_id(message), settings.spreadsheet_id)
        await message.answer(_start_text(sheet_id), parse_mode="Markdown")

    @dp.message(Command("help"))
    async def help_cmd(message: Message) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await message.answer(_help_text(), parse_mode="Markdown")

    @dp.message(Command("sheet"))
    async def sheet_cmd(message: Message) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        personal = store.get_user_spreadsheet_id(_user_id(message))
        sheet_id = personal or settings.spreadsheet_id
        source = "персональная настройка" if personal else "GOOGLE_SPREADSHEET_ID (.env)"
        await message.answer(
            f"Текущая таблица: `{mask_spreadsheet_id(sheet_id)}`\nИсточник: {source}\n"
            f"Полный id: `{sheet_id}`",
            parse_mode="Markdown",
        )

    @dp.message(Command("set_sheet"))
    async def set_sheet_cmd(
        message: Message,
        command: CommandObject,
        state: FSMContext,
    ) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        arg = (command.args or "").strip()
        if arg:
            await _apply_sheet_id(
                message,
                raw=arg,
                settings=settings,
                store=store,
                sheets=sheets,
                state=state,
            )
            return
        await state.set_state(SheetSetup.waiting_for_id)
        await message.answer(
            "Пришлите id Google-таблицы или ссылку "
            "(https://docs.google.com/spreadsheets/d/…).\n"
            "Отмена: /cancel"
        )

    @dp.message(Command("reset_sheet"))
    async def reset_sheet_cmd(message: Message, state: FSMContext) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        store.clear_spreadsheet_id(_user_id(message))
        await state.clear()
        await message.answer(
            "Персональная таблица сброшена. "
            f"Используется `.env`: `{mask_spreadsheet_id(settings.spreadsheet_id)}`",
            parse_mode="Markdown",
        )

    @dp.message(Command("cancel"))
    async def cancel_cmd(message: Message, state: FSMContext) -> None:
        if not _allowed(message, settings):
            return
        await state.clear()
        await message.answer("Отменено.")

    @dp.message(StateFilter(SheetSetup.waiting_for_id), F.text)
    async def on_sheet_id_reply(message: Message, state: FSMContext) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await _apply_sheet_id(
            message,
            raw=message.text or "",
            settings=settings,
            store=store,
            sheets=sheets,
            state=state,
        )

    @dp.message(F.document)
    async def on_document(message: Message, state: FSMContext) -> None:
        if not _allowed(message, settings):
            await message.answer("Нет доступа.")
            return
        await state.clear()
        doc = message.document
        if not doc:
            return
        name = doc.file_name or "statement"
        suffix = Path(name).suffix.lower()
        if suffix not in {".csv", ".pdf", ".txt"}:
            await message.answer("Нужен файл .csv или .pdf")
            return

        spreadsheet_id = store.get_spreadsheet_id(_user_id(message), settings.spreadsheet_id)
        await message.answer(
            f"Обрабатываю «{name}» → `{mask_spreadsheet_id(spreadsheet_id)}`…",
            parse_mode="Markdown",
        )
        with tempfile.TemporaryDirectory(dir=settings.download_dir) as tmp:
            dest = Path(tmp) / name
            await bot.download(doc, destination=dest)
            try:
                result = await asyncio.to_thread(
                    process_file,
                    dest,
                    filename=name,
                    sheets=sheets,
                    spreadsheet_id=spreadsheet_id,
                    write=True,
                )
            except Exception as exc:  # noqa: BLE001 — surface to user
                logger.exception("Failed to process %s", name)
                await message.answer(f"Ошибка: {exc}")
                return
        await message.answer(_format_result(result), parse_mode="Markdown")

    @dp.message()
    async def fallback(message: Message) -> None:
        if not _allowed(message, settings):
            return
        await message.answer(
            "Пришлите файл выписки (.csv / .pdf) или /help"
        )

    logger.info("Bot started; user store at %s", settings.user_store_path)
    await dp.start_polling(bot)


def main() -> None:
    settings = load_settings()
    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
