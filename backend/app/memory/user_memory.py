from typing import Any

from app.memory.json_store import load_json, save_json
from app.auth.token_store import TOKEN_FILE

USER_MEMORY_FILE = TOKEN_FILE.with_name(".user_memory.json")


def load_user_memory(user_id: str) -> dict[str, Any]:
    all_users = load_json(USER_MEMORY_FILE)
    return all_users.get(user_id, {})


def save_user_memory(user_id: str, memory: dict[str, Any]) -> dict[str, Any]:
    all_users = load_json(USER_MEMORY_FILE)
    current = all_users.get(user_id, {})
    current.update({key: value for key, value in memory.items() if value is not None})
    all_users[user_id] = current
    save_json(USER_MEMORY_FILE, all_users)
    return current
