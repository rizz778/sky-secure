import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from google import genai

from app.tools.zoho_agent_tools import list_portals, list_projects, list_tasks

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
MAX_TOOL_OUTPUT_CHARS = 12000

QUERY_TOOLS = {
    "list_portals": list_portals,
    "list_projects": list_projects,
    "list_tasks": list_tasks,
}


async def run_query_agent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    tool_name, tool_input = await decide_query_tool(message, portal_id, project_id)
    tool_output = await execute_query_tool(tool_name, tool_input)
    answer = await answer_from_tool_output(message, tool_name, tool_input, tool_output)

    return {
        "answer": answer,
        "portal_id": tool_input.get("portal_id") or portal_id,
        "project_id": tool_input.get("project_id") or project_id,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "projects": tool_output if tool_name == "list_projects" else None,
        "tasks": tool_output if tool_name == "list_tasks" else None,
    }


async def decide_query_tool(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    client = gemini_client()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            "Choose the best Zoho read tool for this request.\n\n"
            "Tools:\n"
            "- list_portals(): list available portals.\n"
            "- list_projects(portal_id): list projects in a portal.\n"
            "- list_tasks(portal_id, project_id): list tasks in a project.\n\n"
            "Return valid JSON only:\n"
            "{\"tool_name\":\"list_tasks\",\"tool_input\":{\"portal_id\":\"...\",\"project_id\":\"...\"}}\n\n"
            f"User request: {message}\n"
            f"Known portal_id: {portal_id}\n"
            f"Known project_id: {project_id}"
        ),
        config={
            "system_instruction": (
                "You route user questions to read-only Zoho tools. "
                "Never choose create, update, or delete actions."
            )
        },
    )

    parsed = parse_json_object(response.text or "")
    tool_name = parsed.get("tool_name") or fallback_tool_name(message)
    if tool_name not in QUERY_TOOLS:
        tool_name = fallback_tool_name(message)

    tool_input = parsed.get("tool_input") if isinstance(parsed.get("tool_input"), dict) else {}
    tool_input = fill_known_ids(tool_name, tool_input, portal_id, project_id)
    validate_query_tool_input(tool_name, tool_input)
    return tool_name, tool_input


async def execute_query_tool(tool_name: str, tool_input: dict[str, Any]) -> Any:
    if tool_name not in QUERY_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown query tool: {tool_name}")
    return await QUERY_TOOLS[tool_name](**tool_input)


async def answer_from_tool_output(
    message: str,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: Any,
) -> str:
    client = gemini_client()
    tool_output_text = json.dumps(tool_output, indent=2, default=str)[:MAX_TOOL_OUTPUT_CHARS]

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"User request:\n{message}\n\n"
            f"Tool used: {tool_name}\n"
            f"Tool input: {json.dumps(tool_input, default=str)}\n"
            f"Tool output JSON:\n{tool_output_text}"
        ),
        config={
            "system_instruction": (
                "You are a Zoho Project Assistant. Answer only from the tool output. "
                "If an ID is missing, ask for it clearly. Keep answers concise and practical."
            )
        },
    )
    return response.text or ""


def fill_known_ids(
    tool_name: str,
    tool_input: dict[str, Any],
    portal_id: str | None,
    project_id: str | None,
) -> dict[str, Any]:
    hydrated = dict(tool_input)
    if tool_name in {"list_projects", "list_tasks"} and portal_id:
        hydrated.setdefault("portal_id", portal_id)
    if tool_name == "list_tasks" and project_id:
        hydrated.setdefault("project_id", project_id)
    return hydrated


def validate_query_tool_input(tool_name: str, tool_input: dict[str, Any]) -> None:
    required = {
        "list_portals": [],
        "list_projects": ["portal_id"],
        "list_tasks": ["portal_id", "project_id"],
    }[tool_name]

    missing = [field for field in required if not tool_input.get(field)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Missing required tool input: {', '.join(missing)}",
                "tool_name": tool_name,
                "tool_input": tool_input,
            },
        )


def fallback_tool_name(message: str) -> str:
    normalized = message.lower()
    if any(word in normalized for word in ("task", "todo", "deadline", "due")):
        return "list_tasks"
    if "project" in normalized:
        return "list_projects"
    return "list_portals"


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


def gemini_client():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY in backend/.env")
    return genai.Client(api_key=gemini_api_key)
