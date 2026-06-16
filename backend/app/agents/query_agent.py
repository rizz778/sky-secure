
import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException
from mistralai.client import Mistral

from app.tools.zoho_agent_tools import list_portals, list_projects, list_tasks

load_dotenv()

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MAX_TOOL_OUTPUT_CHARS = 12000

QUERY_TOOLS = {
    "list_portals": list_portals,
    "list_projects": list_projects,
    "list_tasks": list_tasks,
}


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


def validate_tool_input(tool_name: str, tool_input: dict[str, Any]) -> None:
    """Validate required fields for tool."""
    required = {
        "list_portals": [],
        "list_projects": ["portal_id"],
        "list_tasks": ["portal_id", "project_id"],
    }.get(tool_name, [])
    
    missing = [f for f in required if not tool_input.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing: {', '.join(missing)}")


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


def get_mistral_client() -> Mistral:
    """Get Mistral client, raise if API key missing."""
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Missing MISTRAL_API_KEY")
    return Mistral(api_key=key)


async def decide_query_tool(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    session_memory: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """LLM decides which query tool to use."""
    session_memory = session_memory or {}
    history_context = format_history_context(session_memory)
    
    client = get_mistral_client()
    response = await client.chat.complete_async(
        model=MISTRAL_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Route user questions to read-only Zoho tools.\n"
                    "Available:\n"
                    "- list_portals(): list portals.\n"
                    "- list_projects(portal_id): list projects in portal.\n"
                    "- list_tasks(portal_id, project_id): list tasks.\n\n"
                    "Return JSON: {\"tool_name\": \"...\", \"tool_input\": {...}}\n"
                    "Reference history items (e.g., '2nd project') or use explicit IDs."
                    + history_context
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Request: {message}\n"
                    f"Provided: portal_id={portal_id}, project_id={project_id}"
                ),
            },
        ],
    )
    
    parsed = parse_json_object(response.choices[0].message.content)
    tool_name = parsed.get("tool_name") or "list_portals"
    
    if tool_name not in QUERY_TOOLS:
        tool_name = "list_portals"
    
    tool_input = parsed.get("tool_input", {}) if isinstance(parsed.get("tool_input"), dict) else {}
    validate_tool_input(tool_name, tool_input)
    return tool_name, tool_input


async def execute_query_tool(tool_name: str, tool_input: dict[str, Any]) -> Any:
    """Execute the query tool."""
    if tool_name not in QUERY_TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
    return await QUERY_TOOLS[tool_name](**tool_input)


async def answer_from_tool_output(
    message: str,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: Any,
    session_memory: dict[str, Any] | None = None,
) -> str:
    """LLM generates answer from tool output."""
    client = get_mistral_client()
    output_text = json.dumps(tool_output, indent=2, default=str)[:MAX_TOOL_OUTPUT_CHARS]
    
    response = await client.chat.complete_async(
        model=MISTRAL_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a Zoho assistant. Answer only from tool output. Keep answers concise.",
            },
            {
                "role": "user",
                "content": (
                    f"Request: {message}\n\n"
                    f"Tool: {tool_name}\n"
                    f"Input: {json.dumps(tool_input, default=str)}\n"
                    f"Output:\n{output_text}"
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""


async def run_query_agent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    session_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run query agent: decide tool -> execute -> generate answer."""
    tool_name, tool_input = await decide_query_tool(
        message, portal_id, project_id, session_memory=session_memory or {}
    )
    tool_output = await execute_query_tool(tool_name, tool_input)
    answer = await answer_from_tool_output(
        message, tool_name, tool_input, tool_output, session_memory=session_memory or {}
    )
    
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
