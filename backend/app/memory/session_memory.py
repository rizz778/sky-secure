from typing import Any

from app.memory.json_store import load_json, save_json
from app.auth.token_store import TOKEN_FILE

SESSION_MEMORY_FILE = TOKEN_FILE.with_name(".session_memory.json")


def load_session_memory(session_id: str) -> dict[str, Any]:
    all_sessions = load_json(SESSION_MEMORY_FILE)
    return all_sessions.get(session_id, {})


def save_session_memory(session_id: str, memory: dict[str, Any]) -> dict[str, Any]:
    all_sessions = load_json(SESSION_MEMORY_FILE)
    current = all_sessions.get(session_id, {})
    for key, value in memory.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    all_sessions[session_id] = current
    save_json(SESSION_MEMORY_FILE, all_sessions)
    return current
