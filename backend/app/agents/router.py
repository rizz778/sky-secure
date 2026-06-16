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
from app.memory.session_memory import (
    add_to_portal_history,
    add_to_project_history,
    add_to_task_history,
    get_portals_history,
    get_projects_history,
    get_tasks_history,
    load_session_memory,
    save_session_memory,
)
from app.memory.user_memory import load_user_memory, save_user_memory

load_dotenv()

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
DEFAULT_SESSION_ID = "default-session"
DEFAULT_USER_ID = "default-user"


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
    state = {
        "message": message,
        "session_id": session_id or DEFAULT_SESSION_ID,
        "user_id": user_id or DEFAULT_USER_ID,
        "portal_id": portal_id,
        "project_id": project_id,
        "task_id": task_id,
        "confirmation": confirmation,
    }
    result = await router_graph.ainvoke(state)
    return result["response"]


def load_memory_node(state: RouterState) -> RouterState:
    """Load session and user memory."""
    session_memory = load_session_memory(state["session_id"])
    user_memory = load_user_memory(state["user_id"])
    
    return {
        **state,
        "session_memory": session_memory,
        "user_memory": user_memory,
    }


async def classify_intent_node(state: RouterState) -> RouterState:
    """Classify intent: query or action."""
    if state.get("confirmation") is not None:
        return {
            **state,
            "agent": "action",
            "routing_reason": "confirmation supplied",
        }

    agent, reason = await classify_agent_intent(state["message"])
    return {**state, "agent": agent, "routing_reason": reason}


async def query_agent_node(state: RouterState) -> RouterState:
    """Route to query agent."""
    result = await run_query_agent(
        state["message"],
        portal_id=state.get("portal_id"),
        project_id=state.get("project_id"),
        session_memory=state.get("session_memory", {}),
    )
    return {**state, "agent_result": result}


async def action_agent_node(state: RouterState) -> RouterState:
    """Route to action agent."""
    action_message = state["message"]
    pending = state.get("session_memory", {}).get("pending_action", {})
    if state.get("confirmation") is not None and pending:
        action_message = pending.get("message") or action_message

    result = await run_action_agent(
        action_message,
        portal_id=state.get("portal_id"),
        project_id=state.get("project_id"),
        task_id=state.get("task_id"),
        confirmation=state.get("confirmation"),
        session_memory=state.get("session_memory", {}),
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

    # Track project history if we have a project_id
    if project_id:
        project_name = None
        # Try to extract project name from tool output if available
        if tool_name == "list_projects" and isinstance(tool_output, list):
            for proj in tool_output:
                if isinstance(proj, dict) and (proj.get("id") == project_id or proj.get("project_id") == project_id):
                    project_name = proj.get("name") or proj.get("title")
                    break
        
        add_to_project_history(
            session_id=state["session_id"],
            project_id=project_id,
            project_name=project_name,
            portal_id=portal_id,
        )

    # Track portal history if we have a portal_id
    if portal_id:
        portal_name = None
        # Try to extract portal name from tool output if available
        if tool_name == "list_portals" and isinstance(tool_output, list):
            for portal in tool_output:
                if isinstance(portal, dict) and (portal.get("id") == portal_id or portal.get("zsoid") == portal_id):
                    portal_name = portal.get("name") or portal.get("portal_name")
                    break
        
        add_to_portal_history(
            session_id=state["session_id"],
            portal_id=portal_id,
            portal_name=portal_name,
        )

    # Track task history if we have a task_id
    if task_id:
        task_name = None
        # Try to extract task name from tool output if available
        if tool_name == "list_tasks" and isinstance(tool_output, list):
            for task in tool_output:
                if isinstance(task, dict) and (task.get("id") == task_id or task.get("task_id") == task_id):
                    task_name = task.get("name") or task.get("title")
                    break
        
        add_to_task_history(
            session_id=state["session_id"],
            task_id=task_id,
            task_name=task_name,
            project_id=project_id,
        )

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
    """Route to query or action agent."""
    return state.get("agent", "query")


def build_router_graph():
    """Build LangGraph state machine."""
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
        {"query": "query_agent", "action": "action_agent"},
    )
    graph.add_edge("query_agent", "save_memory")
    graph.add_edge("action_agent", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


async def classify_agent_intent(message: str) -> tuple[str, str]:
    """Classify user intent as query or action."""
    try:
        client = mistral_client()
        response = await client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Route user request. Return JSON {\"agent\":\"query\"|\"action\",\"reason\":\"brief reason\"}. "
                        "Query: read-only (list, show, search). Action: write (create, update, delete)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Classify: {message}",
                },
            ],
        )
        parsed = parse_json_object(response.choices[0].message.content)
        agent = parsed.get("agent")
        reason = parsed.get("reason", "llm routing")
        if agent in {"query", "action"}:
            return agent, str(reason)
    except Exception:
        pass
    
    return ("action" if ACTION_KEYWORDS_RE.search(message.lower()) else "query"), "fallback"


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract JSON object from text."""
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


def mistral_client() -> Mistral:
    """Get Mistral client, raise if API key missing."""
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Missing MISTRAL_API_KEY")
    return Mistral(api_key=key)


ACTION_KEYWORDS_RE = re.compile(
    r"(create|update|delete|add|remove|mark|complete|assign|change|set|rename|modify)"
)

router_graph = build_router_graph()
