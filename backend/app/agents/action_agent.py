import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from mistralai.client import Mistral

from app.tools.zoho_agent_tools import create_task, delete_task, update_task

load_dotenv()

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MAX_CONTEXT_CHARS = 8000


def create_action_state(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    confirmed: bool | None = None,
) -> dict[str, Any]:
    return {
        "message": message,
        "portal_id": portal_id,
        "project_id": project_id,
        "task_id": task_id,
        "action_name": None,
        "action_input": None,
        "confirmation_required": False,
        "confirmation_prompt": None,
        "confirmed": confirmed,
        "tool_output": None,
        "final_answer": None,
    }


def is_task_id_placeholder(task_id: Any) -> bool:
    if not isinstance(task_id, str):
        return False
    normalized = task_id.strip().lower()
    placeholders = {
        "last",
        "last_task",
        "last_task_id",
        "recent",
        "recent_task",
        "latest",
        "latest_task",
        "my_last_task",
        "most_recent_task",
        "this task",
    }
    if normalized in placeholders:
        return True
    return any(phrase in normalized for phrase in ["last", "recent", "latest"])


def normalize_action_input(state: dict[str, Any]) -> dict[str, Any]:
    action_input = dict(state.get("action_input") or {})
    if state.get("portal_id") and "portal_id" not in action_input:
        action_input["portal_id"] = state["portal_id"]
    if state.get("project_id") and "project_id" not in action_input:
        action_input["project_id"] = state["project_id"]

    task_id_in_input = action_input.get("task_id")
    resolved_task_id = state.get("task_id")
    if task_id_in_input is not None and is_task_id_placeholder(task_id_in_input):
        if resolved_task_id and not is_task_id_placeholder(resolved_task_id):
            action_input["task_id"] = resolved_task_id
        else:
            action_input.pop("task_id", None)
    elif task_id_in_input is None and resolved_task_id and not is_task_id_placeholder(resolved_task_id):
        action_input["task_id"] = resolved_task_id

    return {**state, "action_input": action_input}


def extract_task_id(tool_output: Any) -> str | None:
    if not isinstance(tool_output, dict):
        return None
    body = tool_output.get("body")
    if isinstance(body, dict):
        task_id = body.get("id") or body.get("task_id") or (body.get("task") and body["task"].get("id"))
        if isinstance(task_id, (int, str)):
            return str(task_id)
    return None


async def decide_action(state: dict[str, Any]) -> dict[str, Any]:
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing MISTRAL_API_KEY in backend/.env",
        )

    client = Mistral(api_key=mistral_api_key)
    prompt = (
        "Available actions:\n"
        "- create_task(portal_id, project_id, title, due_date?, assignee_id?, description?)\n"
        "- update_task(portal_id, project_id, task_id, status?, assignee_id?, due_date?, priority?, title?, description?)\n"
        "- delete_task(portal_id, project_id, task_id)\n\n"
        "Respond with valid JSON only, with these fields:\n"
        "{\n"
        "  \"action_name\": \"create_task\",\n"
        "  \"action_input\": { ... }\n"
        "}\n"
        "Use the provided portal_id/project_id when available."
    )

    response = await client.chat.complete_async(
        model=MISTRAL_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a Zoho action assistant. Determine whether the user wants to create, update, or delete a task.\n" + prompt,
            },
            {
                "role": "user",
                "content": (
                    f"User question:\n{state['message']}\n\n"
                    f"portal_id: {state.get('portal_id')}\n"
                    f"project_id: {state.get('project_id')}\n"
                    f"task_id: {state.get('task_id')}"
                ),
            },
        ],
    )

    parsed = parse_json_object(response.choices[0].message.content)
    action_name = parsed.get("action_name")
    action_input = parsed.get("action_input", {}) if isinstance(parsed.get("action_input"), dict) else {}

    if action_name not in {"create_task", "update_task", "delete_task"}:
        action_name = None

    state = {**state, "action_name": action_name, "action_input": action_input}
    state = normalize_action_input(state)

    confirmation_required = bool(action_name)
    confirmation_prompt = None

    if action_name == "create_task":
        confirmation_prompt = (
            f"I will create a task named '{state['action_input'].get('title')}' "
            f"in project {state['action_input'].get('project_id')}. Confirm?"
        )
    elif action_name == "update_task":
        confirmation_prompt = (
            f"I will update task {state['action_input'].get('task_id')} "
            f"with {state['action_input']}. Confirm?"
        )
    elif action_name == "delete_task":
        confirmation_prompt = (
            f"I will delete task {state['action_input'].get('task_id')}. This cannot be undone. Confirm?"
        )

    if action_name is None:
        return {
            **state,
            "confirmation_required": False,
            "final_answer": "I could not identify a valid Zoho action from your request.",
        }

    return {
        **state,
        "confirmation_required": confirmation_required,
        "confirmation_prompt": confirmation_prompt,
    }


async def execute_action(state: dict[str, Any]) -> dict[str, Any]:
    action_name = state.get("action_name")
    if not action_name:
        return {
            **state,
            "final_answer": "No action could be determined for this request.",
        }

    if state.get("confirmation_required") and state.get("confirmed") is not True:
        return {
            **state,
            "final_answer": state.get("confirmation_prompt") or "Please confirm the intended action before I execute it.",
        }

    if state.get("confirmed") is False:
        return {
            **state,
            "final_answer": "Action has been cancelled.",
        }

    action_input = state.get("action_input") or {}
    validate_action_input(action_name, action_input)
    tool_output: Any = None

    if action_name == "create_task":
        tool_output = await create_task(**action_input)
    elif action_name == "update_task":
        tool_output = await update_task(**action_input)
    elif action_name == "delete_task":
        tool_output = await delete_task(**action_input)
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    task_id = state.get("action_input", {}).get("task_id")
    if action_name == "create_task":
        task_id = extract_task_id(tool_output) or task_id

    return {
        **state,
        "tool_output": tool_output,
        "task_id": task_id,
        "final_answer": f"Action '{action_name}' completed successfully.",
    }


def validate_action_input(action_name: str, action_input: dict[str, Any]) -> None:
    required_fields = {
        "create_task": ["portal_id", "project_id", "title"],
        "update_task": ["portal_id", "project_id", "task_id"],
        "delete_task": ["portal_id", "project_id", "task_id"],
    }[action_name]

    missing = [field for field in required_fields if not action_input.get(field)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Missing required action input: {', '.join(missing)}",
                "action_name": action_name,
                "action_input": action_input,
            },
        )


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        object_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not object_match:
            return {}
        try:
            parsed = json.loads(object_match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}


async def run_action_agent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    confirmation: bool | None = None,
) -> dict[str, Any]:
    state = create_action_state(message, portal_id=portal_id, project_id=project_id, task_id=task_id, confirmed=confirmation)
    result = await decide_action(state)
    result = await execute_action(result)
    return {
        "answer": result.get("final_answer"),
        "portal_id": result.get("portal_id"),
        "project_id": result.get("project_id"),
        "task_id": result.get("task_id"),
        "action_name": result.get("action_name"),
        "action_input": result.get("action_input"),
        "confirmation_required": result.get("confirmation_required", False),
        "confirmation_prompt": result.get("confirmation_prompt"),
        "confirmed": result.get("confirmed"),
        "tool_output": result.get("tool_output"),
    }
