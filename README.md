# Expenses bot (v1)

Telegram bot (Python + [aiogram](https://docs.aiogram.dev/)) that parses bank statement **CSV/PDF** files and appends expense rows to a Google Sheet via **OAuth**.

Spreadsheet: [Расходы](https://docs.google.com/spreadsheets/d/1M4X9kFTgdTYL68QnBRIUkSA2IhV3hz00opUqaOC8Rcw/)

## What it does

1. `/start` shows the current Google spreadsheet (masked) and how to change it.
2. You send a statement file in Telegram.
3. The bot detects the bank and parses **expenses only** (negative amounts; inflows skipped).
4. Categories are normalized (T-Bank rename map from the Colab notebook) and routed:
   - **Повседневные** / **Квартира** / **Крупные** — by category lists (prefer live **Справочники** when available).
   - **Переводы** — transfers and anything that needs a manual category (blank **Категория**).
5. Rows are appended with columns **Дата, Трата, Категория, Стоимость** only. **DW** / **MMYY** are left empty for sheet formulas.

### Per-user spreadsheet

Each Telegram user can point the bot at their own sheet:

| Command | Action |
|---------|--------|
| `/sheet` | Show current spreadsheet id (full + masked) and source |
| `/set_sheet <id_or_url>` | Save id from a raw key or Sheets URL; validates format and tries OAuth open |
| `/set_sheet` | Prompt: reply with id/URL next |
| `/reset_sheet` | Clear personal override → fall back to `GOOGLE_SPREADSHEET_ID` |

Prefs are stored on disk as JSON: `{DATA_DIR}/users.json` (default `./data/users.json`). If unset for a user, the bot uses `GOOGLE_SPREADSHEET_ID` from `.env`.

### Banks (v1)

| Bank | Format | Notes |
|------|--------|--------|
| T Bank | CSV (`;`) | Encoding via chardet; status `Ок`; drops inflows & internal «Между своими счетами» |
| Ozon Bank | PDF | Outflows statement; marketplace → Маркетплейсы |
| Yandex Bank | PDF | Outflows; keyword categories (Taxi, Lavka, Plus, Market, …) |
| Sber | — | Later |
| BNB | — | Out of scope |

### Worksheet **Переводы**

Transfers that the notebook used to drop (category «Переводы», unmatched / `None` after rename, interest/cash-like buckets) are written to sheet **Переводы** so you can categorize them in the spreadsheet.

- Same write columns: **Дата, Трата, Категория, Стоимость**.
- **Категория** is left **blank** for manual fill.
- If the tab is missing, the bot **creates** it with a header row on first write.
- You can also create it manually in Google Sheets with those four headers (plus any formula columns you want after them).

Internal T-Bank moves (`Между своими счетами` / `Перевод между счетами`) are still skipped to avoid double-counting between accounts.

## Setup

### 1. Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# or: pip install -e ".[dev]"
```

### 2. Telegram bot token

1. Create a bot with [@BotFather](https://t.me/BotFather).
2. Copy the token into `.env` (see `.env.example`).

### 3. Google OAuth (user account)

1. In [Google Cloud Console](https://console.cloud.google.com/): create/select a project → enable **Google Sheets API** and **Google Drive API**.
2. Configure **OAuth consent screen** (External or Internal).
3. Create credentials → **OAuth client ID** → application type **Desktop app**.
4. Download JSON → save as `secrets/client_secret.json` (path configurable).
5. Run the one-time local login:

```bash
mkdir -p secrets
cp .env.example .env   # fill TELEGRAM_BOT_TOKEN at least for the bot; OAuth script tolerates missing token if paths are set
python -m expenses_bot.oauth_setup
```

This opens a browser, then writes `secrets/token.json`. Do **not** commit `secrets/` or `.env`.

Share the spreadsheet with the same Google account you authorize.

### 4. Environment

```bash
cp .env.example .env
```

Required:

- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SPREADSHEET_ID` — default spreadsheet (overridable per user via `/set_sheet`)
- `GOOGLE_OAUTH_CLIENT_SECRETS` / `GOOGLE_OAUTH_TOKEN`

Optional:

- `TELEGRAM_ALLOWED_USER_IDS` — comma-separated Telegram user ids (allowlist unchanged)
- `DATA_DIR` — directory for `users.json` (default `./data`)
- `WS_CASUAL` / `WS_FLAT` / `WS_BIG` / `WS_TRANSFERS` / `WS_DIRECTORY` — worksheet titles

## Run locally

```bash
source .venv/bin/activate
python -m expenses_bot
# or: expenses-bot
```

Send a sample CSV/PDF to the bot in Telegram.

Dry-run parsers without Sheets/Telegram:

```bash
python - <<'PY'
from pathlib import Path
from expenses_bot.pipeline import process_file
from expenses_bot.categories import default_router

for path in [
    Path('tests/fixtures/tbank/operations.csv'),
    Path('tests/fixtures/ozon/outflows.pdf'),
    Path('tests/fixtures/yandex/statement.pdf'),
]:
    result = process_file(path, router=default_router(), write=False)
    print(path.name, result.bank, result.total_parsed,
          {k.value: len(v) for k, v in result.grouped.items()})
PY
```

## Tests

```bash
pytest -q
```

Fixtures under `tests/fixtures/` are trimmed/copied from the project Context samples.

## Layout

```
expenses_bot/
  bot.py              # aiogram entry (/start, /set_sheet, uploads)
  categories.py       # rename map + routing (incl. Переводы)
  config.py
  models.py
  pipeline.py
  sheets.py           # OAuth + append + Справочники + ensure Переводы
  user_store.py       # per-Telegram-user spreadsheet id (JSON)
  oauth_setup.py
  parsers/            # tbank / ozon / yandex
data/                 # runtime: users.json (gitignored)
tests/
scripts/
```
