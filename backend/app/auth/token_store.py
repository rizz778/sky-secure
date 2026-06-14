import json
from pathlib import Path
from typing import Any

TOKEN_FILE = Path(__file__).resolve().parents[2] / ".zoho_tokens.json"


def load_tokens() -> dict[str, Any]:
    if not TOKEN_FILE.exists():
        return {}

    with TOKEN_FILE.open("r", encoding="utf-8") as token_file:
        return json.load(token_file)


def save_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    current_tokens = load_tokens()
    current_tokens.update({key: value for key, value in tokens.items() if value is not None})

    with TOKEN_FILE.open("w", encoding="utf-8") as token_file:
        json.dump(current_tokens, token_file, indent=2)

    return current_tokens


def has_refresh_token() -> bool:
    return bool(load_tokens().get("refresh_token"))
