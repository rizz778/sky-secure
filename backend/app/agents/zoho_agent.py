import json
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from fastapi import HTTPException
from google import genai
from langgraph.graph import END, START, StateGraph

from app.tools.zoho_client import get_portals, get_projects, get_tasks

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
MAX_CONTEXT_CHARS = 12000


class ZohoAgentState(TypedDict, total=False):
    message: str
    portal_id: str | None
    project_id: str | None
    context: dict[str, Any]
    answer: str


async def gather_zoho_context(state: ZohoAgentState) -> ZohoAgentState:
    context: dict[str, Any] = {}

    portals = await get_portals()
    context["portals"] = portals

    portal_id = state.get("portal_id") or infer_single_id(portals, ["id", "portal_id", "zpid"])
    if portal_id:
        context["projects"] = await get_projects(portal_id)

    project_id = state.get("project_id") or infer_single_id(
        context.get("projects"),
        ["id", "project_id", "id_string"],
    )
    if portal_id and project_id:
        context["tasks"] = await get_tasks(portal_id, project_id)

    return {
        **state,
        "portal_id": portal_id,
        "project_id": project_id,
        "context": context,
    }


async def answer_from_context(state: ZohoAgentState) -> ZohoAgentState:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing GEMINI_API_KEY in backend/.env",
        )

    client = genai.Client(api_key=gemini_api_key)
    context_text = json.dumps(state.get("context", {}), indent=2, default=str)
    context_text = context_text[:MAX_CONTEXT_CHARS]

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            f"User question:\n{state['message']}\n\n"
            f"Zoho context JSON:\n{context_text}"
        ),
        config={
            "system_instruction": (
                "You are a Zoho Project Assistant. Answer only from the provided "
                "Zoho context. If an ID is needed but missing, ask for the exact ID "
                "and explain where the user can get it. Keep answers concise and useful."
            )
        },
    )

    return {
        **state,
        "answer": response.text or "",
    }


def infer_single_id(data: Any, id_keys: list[str]) -> str | None:
    items = extract_items(data)
    if len(items) != 1:
        return None

    item = items[0]
    if not isinstance(item, dict):
        return None

    for key in id_keys:
        value = item.get(key)
        if value:
            return str(value)
    return None


def extract_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("portals", "projects", "tasks", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def build_zoho_agent():
    graph = StateGraph(ZohoAgentState)
    graph.add_node("gather_zoho_context", gather_zoho_context)
    graph.add_node("answer_from_context", answer_from_context)
    graph.add_edge(START, "gather_zoho_context")
    graph.add_edge("gather_zoho_context", "answer_from_context")
    graph.add_edge("answer_from_context", END)
    return graph.compile()


zoho_agent = build_zoho_agent()


async def run_zoho_agent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    result = await zoho_agent.ainvoke(
        {
            "message": message,
            "portal_id": portal_id,
            "project_id": project_id,
        }
    )
    return {
        "answer": result.get("answer"),
        "portal_id": result.get("portal_id"),
        "project_id": result.get("project_id"),
    }
