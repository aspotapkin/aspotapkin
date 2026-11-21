from __future__ import annotations

from expenses_bot.bot import _format_result, _help_text, _start_text
from expenses_bot.models import Expense, WorksheetTarget
from expenses_bot.pipeline import ImportResult
from expenses_bot.user_store import mask_spreadsheet_id


def test_format_result_is_plain_text_with_underscored_ids():
    sid = "1M4X_kFT_gdTYL68QnBRIUkSA2IhV3hz00opUqaOC8Rcw"
    result = ImportResult(
        bank="tbank",
        total_parsed=2,
        grouped={
            WorksheetTarget.CASUAL: [
                Expense("01.01.2026", "file_name_with_underscores.csv", "Питание", 10.0)
            ],
            WorksheetTarget.FLAT: [],
            WorksheetTarget.BIG: [],
            WorksheetTarget.TRANSFERS: [],
        },
        written={
            WorksheetTarget.CASUAL.value: 1,
            WorksheetTarget.FLAT.value: 0,
            WorksheetTarget.BIG.value: 0,
            WorksheetTarget.TRANSFERS.value: 0,
        },
        spreadsheet_id=sid,
    )
    text = _format_result(result)
    assert "tbank" in text
    assert mask_spreadsheet_id(sid) in text
    # No Markdown code fences — safe for parse_mode=None.
    assert "`" not in text


def test_start_and_help_plain():
    sid = "1abc_def_ghijklmnopqrstuvwxyzABCDEFGHIJK"
    assert "`" not in _start_text(sid)
    assert "/help" in _start_text(sid)
    assert "/start" in _help_text()
    assert "`" not in _help_text()
