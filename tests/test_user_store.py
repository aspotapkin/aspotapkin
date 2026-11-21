from __future__ import annotations

from pathlib import Path

import pytest

from expenses_bot.user_store import (
    UserStore,
    extract_spreadsheet_id,
    mask_spreadsheet_id,
)

SAMPLE_ID = "1M4X9kFTgdTYL68QnBRIUkSA2IhV3hz00opUqaOC8Rcw"


def test_extract_from_url_and_raw():
    url = f"https://docs.google.com/spreadsheets/d/{SAMPLE_ID}/edit?usp=sharing"
    assert extract_spreadsheet_id(url) == SAMPLE_ID
    assert extract_spreadsheet_id(SAMPLE_ID) == SAMPLE_ID
    assert extract_spreadsheet_id(f"<{url}>") == SAMPLE_ID


def test_extract_rejects_garbage():
    with pytest.raises(ValueError):
        extract_spreadsheet_id("not-an-id")
    with pytest.raises(ValueError):
        extract_spreadsheet_id("")


def test_mask():
    masked = mask_spreadsheet_id(SAMPLE_ID)
    assert SAMPLE_ID[:4] in masked
    assert SAMPLE_ID[-4:] in masked
    assert SAMPLE_ID not in masked


def test_user_store_persist(tmp_path: Path):
    path = tmp_path / "users.json"
    store = UserStore(path)
    assert store.get_spreadsheet_id(42, SAMPLE_ID) == SAMPLE_ID
    assert store.get_user_spreadsheet_id(42) is None

    other = "1abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"
    store.set_spreadsheet_id(42, f"https://docs.google.com/spreadsheets/d/{other}/edit")
    assert store.get_user_spreadsheet_id(42) == other
    assert store.get_spreadsheet_id(42, SAMPLE_ID) == other

    reloaded = UserStore(path)
    assert reloaded.get_spreadsheet_id(42, SAMPLE_ID) == other

    reloaded.clear_spreadsheet_id(42)
    assert reloaded.get_user_spreadsheet_id(42) is None
    assert reloaded.get_spreadsheet_id(42, SAMPLE_ID) == SAMPLE_ID
