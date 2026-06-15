import json
import os
import re
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from fastapi import HTTPException
from mistralai.client import Mistral
from langgraph.graph import END, START, StateGraph

from app.agents.action_agent import run_action_agent
from app.agents.query_agent import run_query_agent
from app.memory.session_memory import load_session_memory, save_session_memory
from app.memory.user_memory import load_user_memory, save_user_memory

load_dotenv()

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
DEFAULT_SESSION_ID = "default-session"
DEFAULT_USER_ID = "default-user"

ACTION_KEYWORDS = [
    r"\bcreate\b",
    r"\badd\b",
    r"\bmake\b",
    r"\bupdate\b",
    r"\bedit\b",
    r"\bdelete\b",
    r"\bassign\b",
    r"\bcomplete\b",
    r"\bremove\b",
    r"\bchange\b",
]


class RouterState(TypedDict, total=False):
    message: str
    session_id: str
    user_id: str
    portal_id: str | None
    project_id: str | None
    confirmation: bool | None
    session_memory: dict[str, Any]
    user_memory: dict[str, Any]
    agent: Literal["query", "action"]
    routing_reason: str
    agent_result: dict[str, Any]
    response: dict[str, Any]
    task_id: str | None


async def route_message(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    confirmation: bool | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    result = await router_graph.ainvoke(
        {
            "message": message,
            "session_id": session_id or DEFAULT_SESSION_ID,
            "user_id": user_id or DEFAULT_USER_ID,
            "portal_id": portal_id,
            "project_id": project_id,
            "task_id": task_id,
            "confirmation": confirmation,
        }
    )
    return result["response"]


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


def infer_task_id_from_last_tasks(message: str, last_tasks: Any) -> str | None:
    if not isinstance(message, str) or not last_tasks:
        return None

    normalized = message.lower()
    reference_phrases = ["last task", "most recent task", "recent task", "last one", "latest task"]
    if not any(phrase in normalized for phrase in reference_phrases):
        return None

    tasks_list = last_tasks
    if isinstance(last_tasks, dict) and isinstance(last_tasks.get("tasks"), list):
        tasks_list = last_tasks["tasks"]

    if not isinstance(tasks_list, list):
        return None

    for task in reversed(tasks_list):
        if isinstance(task, dict):
            candidate = task.get("id") or task.get("task_id")
            if candidate is None and isinstance(task.get("task"), dict):
                candidate = task["task"].get("id")
            if isinstance(candidate, (int, str)):
                return str(candidate)
    return None


def load_memory_node(state: RouterState) -> RouterState:
    session_memory = load_session_memory(state["session_id"])
    user_memory = load_user_memory(state["user_id"])

    portal_id = (
        state.get("portal_id")
        or session_memory.get("pending_action", {}).get("portal_id")
        or session_memory.get("last_portal_id")
        or user_memory.get("default_portal_id")
    )
    project_id = (
        state.get("project_id")
        or session_memory.get("pending_action", {}).get("project_id")
        or session_memory.get("last_project_id")
        or user_memory.get("default_project_id")
    )
    request_task_id = state.get("task_id")
    if is_task_id_placeholder(request_task_id):
        request_task_id = None

    pending_task_id = session_memory.get("pending_action", {}).get("task_id")
    if is_task_id_placeholder(pending_task_id):
        pending_task_id = None

    task_id = (
        request_task_id
        or pending_task_id
        or session_memory.get("last_task_id")
        or user_memory.get("default_task_id")
    )

    if not task_id:
        task_id = infer_task_id_from_last_tasks(state.get("message", ""), session_memory.get("last_tasks"))

    return {
        **state,
        "portal_id": portal_id,
        "project_id": project_id,
        "task_id": task_id,
        "session_memory": session_memory,
        "user_memory": user_memory,
    }


async def classify_intent_node(state: RouterState) -> RouterState:
    if state.get("confirmation") is not None:
        return {
            **state,
            "agent": "action",
            "routing_reason": "confirmation supplied",
        }

    agent, reason = await classify_agent_intent(
        state["message"],
        portal_id=state.get("portal_id"),
        project_id=state.get("project_id"),
        session_memory=state.get("session_memory", {}),
        user_memory=state.get("user_memory", {}),
    )
    return {**state, "agent": agent, "routing_reason": reason}


async def query_agent_node(state: RouterState) -> RouterState:
    result = await run_query_agent(
        state["message"],
        portal_id=state.get("portal_id"),
        project_id=state.get("project_id"),
    )
    return {**state, "agent_result": result}


async def action_agent_node(state: RouterState) -> RouterState:
    action_message = state["message"]
    pending_action = state.get("session_memory", {}).get("pending_action")
    if state.get("confirmation") is not None and isinstance(pending_action, dict):
        action_message = pending_action.get("message") or action_message

    result = await run_action_agent(
        action_message,
        portal_id=state.get("portal_id"),
        project_id=state.get("project_id"),
        task_id=state.get("task_id"),
        confirmation=state.get("confirmation"),
    )
    return {**state, "agent_result": result}


def save_memory_node(state: RouterState) -> RouterState:
    result = state.get("agent_result", {})
    portal_id = (
        result.get("portal_id")
        or state.get("portal_id")
        or (result.get("action_input") or {}).get("portal_id")
    )
    project_id = (
        result.get("project_id")
        or state.get("project_id")
        or (result.get("action_input") or {}).get("project_id")
    )

    # Extract task id from action or query outputs
    task_id = (
        result.get("task_id")
        or (result.get("action_input") or {}).get("task_id")
        or state.get("task_id")
    )

    # If still missing, try to extract ids from query tool outputs (list_portals, list_projects)
    tool_name = result.get("tool_name")
    tool_output = result.get("tool_output")
    if not portal_id and tool_name == "list_portals" and isinstance(tool_output, list) and tool_output:
        first = tool_output[0]
        # common keys: 'id', 'zsoid', or 'portal_id'
        portal_id = str(first.get("id") or first.get("zsoid") or first.get("portal_id") or "") or None
        if portal_id == "":
            portal_id = None

    if not project_id and tool_name == "list_projects" and isinstance(tool_output, list) and tool_output:
        first = tool_output[0]
        # common keys: 'id' or 'project_id'
        project_id = str(first.get("id") or first.get("project_id") or "") or None
        if project_id == "":
            project_id = None

    session_updates: dict[str, Any] = {
        "last_message": state["message"],
        "last_agent": state.get("agent"),
        "last_portal_id": portal_id,
        "last_project_id": project_id,
        "last_tool_name": result.get("tool_name"),
        "last_tool_input": result.get("tool_input"),
        "last_action_name": result.get("action_name"),
        "last_action_input": result.get("action_input"),
    }

    if result.get("tasks") is not None:
        last_tasks_value = result.get("tasks")
        if isinstance(last_tasks_value, dict) and isinstance(last_tasks_value.get("tasks"), list):
            session_updates["last_tasks"] = last_tasks_value["tasks"]
        else:
            session_updates["last_tasks"] = last_tasks_value
    if task_id:
        session_updates["last_task_id"] = task_id
    if result.get("confirmation_required"):
        session_updates["pending_action"] = {
            "message": state["message"],
            "action_name": result.get("action_name"),
            "action_input": result.get("action_input"),
            "portal_id": portal_id,
            "project_id": project_id,
            "task_id": task_id,
        }
    elif state.get("confirmation") is not None:
        session_updates["pending_action"] = None

    save_session_memory(state["session_id"], session_updates)

    user_updates: dict[str, Any] = {}
    if portal_id:
        user_updates["default_portal_id"] = portal_id
    if project_id:
        user_updates["default_project_id"] = project_id
    if task_id:
        user_updates["default_task_id"] = task_id
    if user_updates:
        save_user_memory(state["user_id"], user_updates)

    response = {
        "agent": state.get("agent"),
        "routing_reason": state.get("routing_reason"),
        "session_id": state["session_id"],
        "user_id": state["user_id"],
        **result,
    }
    return {**state, "response": response}


def route_by_agent(state: RouterState) -> str:
    return state.get("agent", "query")


def build_router_graph():
    graph = StateGraph(RouterState)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("query_agent", query_agent_node)
    graph.add_node("action_agent", action_agent_node)
    graph.add_node("save_memory", save_memory_node)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_by_agent,
        {
            "query": "query_agent",
            "action": "action_agent",
        },
    )
    graph.add_edge("query_agent", "save_memory")
    graph.add_edge("action_agent", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


async def classify_agent_intent(
    message: str,
    portal_id: str | None = None,
    project_id: str | None = None,
    session_memory: dict[str, Any] | None = None,
    user_memory: dict[str, Any] | None = None,
) -> tuple[str, str]:
    try:
        client = mistral_client()
        response = await client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict router. Choose only 'query' or 'action'. "
                        "When unsure, choose 'query' because actions require confirmation. "
                        "Return valid JSON only with {\"agent\":\"query\",\"reason\":\"short reason\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Classify this Zoho assistant request.\n\n"
                        "Agents:\n"
                        "- query: read-only requests like list, show, summarize, search, explain, count, status checks.\n"
                        "- action: write requests that create, update, delete, assign, complete, rename, or otherwise modify Zoho data.\n\n"
                        f"User request: {message}\n"
                        f"Known portal_id: {portal_id}\n"
                        f"Known project_id: {project_id}\n"
                        f"Short-term memory: {json.dumps(session_memory or {}, default=str)[:2000]}\n"
                        f"Long-term memory: {json.dumps(user_memory or {}, default=str)[:2000]}"
                    ),
                },
            ],
        )
        parsed = parse_json_object(response.choices[0].message.content)
        agent_name = parsed.get("agent")
        reason = parsed.get("reason") or "llm routing"
        if agent_name in {"query", "action"}:
            return agent_name, str(reason)
    except Exception:
        pass

    return fallback_agent_intent(message)


def fallback_agent_intent(message: str) -> tuple[str, str]:
    if needs_action_agent(message):
        return "action", "keyword fallback matched an action phrase"
    return "query", "keyword fallback defaulted to query"


def needs_action_agent(message: str) -> bool:
    normalized = message.lower()
    for pattern in ACTION_KEYWORDS:
        if re.search(pattern, normalized):
            return True
    return False


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


def mistral_client():
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        raise HTTPException(status_code=500, detail="Missing MISTRAL_API_KEY in backend/.env")
    return Mistral(api_key=mistral_api_key)


router_graph = build_router_graph()
