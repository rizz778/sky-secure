import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from google import genai

from app.tools.zoho_agent_tools import create_task, delete_task, update_task

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_CONTEXT_CHARS = 8000


def create_action_state(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    confirmed: bool | None = None,
) -> dict[str, Any]:
    return {
        "message": message,
        "portal_id": portal_id,
        "project_id": project_id,
        "action_name": None,
        "action_input": None,
        "confirmation_required": False,
        "confirmation_prompt": None,
        "confirmed": confirmed,
        "tool_output": None,
        "final_answer": None,
    }


def normalize_action_input(state: dict[str, Any]) -> dict[str, Any]:
    action_input = dict(state.get("action_input") or {})
    if state.get("portal_id") and "portal_id" not in action_input:
        action_input["portal_id"] = state["portal_id"]
    if state.get("project_id") and "project_id" not in action_input:
        action_input["project_id"] = state["project_id"]
    return {**state, "action_input": action_input}


async def decide_action(state: dict[str, Any]) -> dict[str, Any]:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing GEMINI_API_KEY in backend/.env",
        )

    client = genai.Client(api_key=gemini_api_key)
    prompt = (
        "You are a Zoho action assistant. Determine whether the user wants to create, update, or delete a task.\n"
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

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"User question:\n{state['message']}\n\n"
            f"portal_id: {state.get('portal_id')}\n"
            f"project_id: {state.get('project_id')}\n\n"
            f"{prompt}"
        ),
        config={"system_instruction": "Decide the action name and input parameters from the user request."},
    )

    parsed = parse_json_object(response.text or "")
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

    return {
        **state,
        "tool_output": tool_output,
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
    confirmation: bool | None = None,
) -> dict[str, Any]:
    state = create_action_state(message, portal_id=portal_id, project_id=project_id, confirmed=confirmation)
    result = await decide_action(state)
    result = await execute_action(result)
    return {
        "answer": result.get("final_answer"),
        "portal_id": result.get("portal_id"),
        "project_id": result.get("project_id"),
        "action_name": result.get("action_name"),
        "action_input": result.get("action_input"),
        "confirmation_required": result.get("confirmation_required", False),
        "confirmation_prompt": result.get("confirmation_prompt"),
        "confirmed": result.get("confirmed"),
        "tool_output": result.get("tool_output"),
    }
