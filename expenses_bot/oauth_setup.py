from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from expenses_bot.config import load_settings
from expenses_bot.sheets import get_credentials


def main() -> None:
    parser = argparse.ArgumentParser(description="Authorize Google Sheets OAuth for expenses-bot")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    args = parser.parse_args()
    load_dotenv(args.env)

    # Token/client paths can be set without a Telegram token during setup.
    from os import getenv

    client = Path(getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "./secrets/client_secret.json"))
    token = Path(getenv("GOOGLE_OAUTH_TOKEN", "./secrets/token.json"))
    try:
        settings = load_settings(args.env)
        client = settings.oauth_client_secrets
        token = settings.oauth_token
    except RuntimeError:
        pass

    creds = get_credentials(client, token)
    print(f"OAuth OK. Token saved to {token}")
    print(f"Valid: {creds.valid}, scopes: {list(creds.scopes or [])}")


if __name__ == "__main__":
    main()
