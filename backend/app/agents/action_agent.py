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


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract JSON from text, handling fenced code blocks."""
    text = text.strip()
    if not text:
        return {}
    
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    
    try:
        return json.loads(text) if isinstance(json.loads(text), dict) else {}
    except ValueError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0)) if isinstance(json.loads(match.group(0)), dict) else {}
            except ValueError:
                pass
    return {}


def extract_task_id(tool_output: Any) -> str | None:
    """Extract task ID from tool output."""
    if not isinstance(tool_output, dict):
        return None
    body = tool_output.get("body", {})
    task_id = body.get("id") or body.get("task_id") or (body.get("task") or {}).get("id")
    return str(task_id) if task_id else None


def validate_action_input(action_name: str, action_input: dict[str, Any]) -> None:
    """Validate required fields for action."""
    required = {
        "create_task": ["portal_id", "project_id", "title"],
        "update_task": ["portal_id", "project_id", "task_id"],
        "delete_task": ["portal_id", "project_id", "task_id"],
    }.get(action_name, [])
    
    missing = [f for f in required if not action_input.get(f)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}",
        )


def format_history_context(session_memory: dict[str, Any]) -> str:
    """Format history chains for LLM context."""
    context = ""
    
    portals = session_memory.get("portals_history", [])
    if portals:
        context += "\n\nRecent portals:\n"
        for i, p in enumerate(portals[:5], 1):
            context += f"{i}. {p.get('name')} (ID: {p.get('id')})\n"
    
    projects = session_memory.get("projects_history", [])
    if projects:
        context += "\n\nRecent projects:\n"
        for i, p in enumerate(projects[:5], 1):
            context += f"{i}. {p.get('name')} (ID: {p.get('id')}, Portal: {p.get('portal_id')})\n"
    
    tasks = session_memory.get("tasks_history", [])
    if tasks:
        context += "\n\nRecent tasks:\n"
        for i, t in enumerate(tasks[:5], 1):
            context += f"{i}. {t.get('name')} (ID: {t.get('id')}, Project: {t.get('project_id')})\n"
    
    return context


async def decide_action(state: dict[str, Any]) -> dict[str, Any]:
    """LLM decides which action to take."""
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        raise HTTPException(status_code=500, detail="Missing MISTRAL_API_KEY")
    
    session_memory = state.get("session_memory", {})
    history_context = format_history_context(session_memory)
    
    client = Mistral(api_key=mistral_api_key)
    response = await client.chat.complete_async(
        model=MISTRAL_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Zoho action assistant. Determine if user wants to create, update, or delete a task.\n"
                    "Available actions:\n"
                    "- create_task(portal_id, project_id, title, due_date?, assignee_id?, description?)\n"
                    "- update_task(portal_id, project_id, task_id, status?, assignee_id?, due_date?, priority?, title?, description?)\n"
                    "- delete_task(portal_id, project_id, task_id)\n\n"
                    "Return JSON: {\"action_name\": \"...\", \"action_input\": {...}}\n"
                    "Reference history items (e.g., '2nd project') or use explicit IDs."
                    + history_context
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Request: {state['message']}\n"
                    f"Provided: portal_id={state.get('portal_id')}, "
                    f"project_id={state.get('project_id')}, task_id={state.get('task_id')}"
                ),
            },
        ],
    )
    
    parsed = parse_json_object(response.choices[0].message.content)
    action_name = parsed.get("action_name")
    action_input = parsed.get("action_input", {}) if isinstance(parsed.get("action_input"), dict) else {}
    
    if action_name not in {"create_task", "update_task", "delete_task"}:
        return {**state, "action_name": None, "confirmation_required": False, 
                "final_answer": "Could not identify a valid action."}
    
    confirmation_prompts = {
        "create_task": f"Create task '{action_input.get('title')}' in project {action_input.get('project_id')}?",
        "update_task": f"Update task {action_input.get('task_id')}?",
        "delete_task": f"Delete task {action_input.get('task_id')}? (Cannot be undone)",
    }
    
    return {
        **state,
        "action_name": action_name,
        "action_input": action_input,
        "confirmation_required": True,
        "confirmation_prompt": confirmation_prompts.get(action_name),
    }


async def execute_action(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the decided action."""
    action_name = state.get("action_name")
    
    if not action_name:
        return {**state, "final_answer": "No action to execute."}
    
    if state.get("confirmation_required") and state.get("confirmed") is not True:
        return {**state, "final_answer": state.get("confirmation_prompt") or "Awaiting confirmation."}
    
    if state.get("confirmed") is False:
        return {**state, "final_answer": "Action cancelled."}
    
    action_input = state.get("action_input", {})
    validate_action_input(action_name, action_input)
    
    if action_name == "create_task":
        action_input.pop("task_id", None)
        output = await create_task(**action_input)
        task_id = extract_task_id(output)
    elif action_name == "update_task":
        output = await update_task(**action_input)
        task_id = action_input.get("task_id")
    else:  # delete_task
        output = await delete_task(**action_input)
        task_id = action_input.get("task_id")
    
    return {
        **state,
        "tool_output": output,
        "task_id": task_id,
        "final_answer": f"Action '{action_name}' completed successfully.",
    }


async def run_action_agent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    confirmation: bool | None = None,
    session_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run action agent: decide -> execute -> return result."""
    state = {
        "message": message,
        "portal_id": portal_id,
        "project_id": project_id,
        "task_id": task_id,
        "session_memory": session_memory or {},
        "confirmed": confirmation,
    }
    
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
