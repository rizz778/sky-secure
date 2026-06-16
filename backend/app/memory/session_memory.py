import time
from typing import Any

from app.memory.json_store import load_json, save_json
from app.auth.token_store import TOKEN_FILE

SESSION_MEMORY_FILE = TOKEN_FILE.with_name(".session_memory.json")
MAX_HISTORY_ITEMS = 50


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


def add_to_project_history(
    session_id: str,
    project_id: str,
    project_name: str | None = None,
    portal_id: str | None = None,
) -> None:
    """Add a project to the session's project history."""
    if not project_id:
        return
    
    current_memory = load_session_memory(session_id)
    history = current_memory.get("projects_history", [])
    
    # Remove if already exists (to update position)
    history = [p for p in history if p.get("id") != project_id]
    
    # Add to front with timestamp
    history.insert(0, {
        "id": project_id,
        "name": project_name or f"Project {project_id}",
        "portal_id": portal_id,
        "timestamp": int(time.time()),
    })
    
    # Keep only recent history
    history = history[:MAX_HISTORY_ITEMS]
    
    save_session_memory(session_id, {"projects_history": history})


def get_project_from_history(session_id: str, index: int) -> dict[str, Any] | None:
    """Get project at given index (0-based, most recent first)."""
    current_memory = load_session_memory(session_id)
    history = current_memory.get("projects_history", [])
    
    if 0 <= index < len(history):
        return history[index]
    return None


def get_projects_history(session_id: str) -> list[dict[str, Any]]:
    """Get full project history for a session."""
    current_memory = load_session_memory(session_id)
    return current_memory.get("projects_history", [])


def add_to_portal_history(
    session_id: str,
    portal_id: str,
    portal_name: str | None = None,
) -> None:
    """Add a portal to the session's portal history."""
    if not portal_id:
        return
    
    current_memory = load_session_memory(session_id)
    history = current_memory.get("portals_history", [])
    
    # Remove if already exists (to update position)
    history = [p for p in history if p.get("id") != portal_id]
    
    # Add to front with timestamp
    history.insert(0, {
        "id": portal_id,
        "name": portal_name or f"Portal {portal_id}",
        "timestamp": int(time.time()),
    })
    
    # Keep only recent history
    history = history[:MAX_HISTORY_ITEMS]
    
    save_session_memory(session_id, {"portals_history": history})


def get_portals_history(session_id: str) -> list[dict[str, Any]]:
    """Get full portal history for a session."""
    current_memory = load_session_memory(session_id)
    return current_memory.get("portals_history", [])


def add_to_task_history(
    session_id: str,
    task_id: str,
    task_name: str | None = None,
    project_id: str | None = None,
) -> None:
    """Add a task to the session's task history."""
    if not task_id:
        return
    
    current_memory = load_session_memory(session_id)
    history = current_memory.get("tasks_history", [])
    
    # Remove if already exists (to update position)
    history = [t for t in history if t.get("id") != task_id]
    
    # Add to front with timestamp
    history.insert(0, {
        "id": task_id,
        "name": task_name or f"Task {task_id}",
        "project_id": project_id,
        "timestamp": int(time.time()),
    })
    
    # Keep only recent history
    history = history[:MAX_HISTORY_ITEMS]
    
    save_session_memory(session_id, {"tasks_history": history})


def get_tasks_history(session_id: str) -> list[dict[str, Any]]:
    """Get full task history for a session."""
    current_memory = load_session_memory(session_id)
    return current_memory.get("tasks_history", [])
