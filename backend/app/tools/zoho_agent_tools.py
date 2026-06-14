from typing import Any

from app.tools.zoho_client import (
    create_task as zoho_create_task,
    delete_task as zoho_delete_task,
    get_portals,
    get_projects,
    get_tasks,
    update_task as zoho_update_task,
)


async def list_portals() -> Any:
    return await get_portals()


async def list_projects(portal_id: str) -> Any:
    return await get_projects(portal_id)


async def list_tasks(portal_id: str, project_id: str) -> Any:
    return await get_tasks(portal_id, project_id)


async def create_task(
    portal_id: str,
    project_id: str,
    title: str,
    due_date: str | None = None,
    assignee_id: str | None = None,
    description: str | None = None,
) -> Any:
    payload: dict[str, Any] = {"name": title}
    if due_date:
        payload["end_date"] = due_date
    if assignee_id:
        payload["owner_id"] = assignee_id
    if description:
        payload["description"] = description

    return await zoho_create_task(portal_id, project_id, payload)


async def update_task(
    portal_id: str,
    project_id: str,
    task_id: str,
    status: str | None = None,
    assignee_id: str | None = None,
    due_date: str | None = None,
    priority: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> Any:
    payload: dict[str, Any] = {}
    if status is not None:
        payload["status"] = status
    if assignee_id is not None:
        payload["owner_id"] = assignee_id
    if due_date is not None:
        payload["end_date"] = due_date
    if priority is not None:
        payload["priority"] = priority
    if title is not None:
        payload["name"] = title
    if description is not None:
        payload["description"] = description

    if not payload:
        raise ValueError("At least one update field is required for update_task.")

    return await zoho_update_task(portal_id, project_id, task_id, payload)


async def delete_task(portal_id: str, project_id: str, task_id: str) -> Any:
    return await zoho_delete_task(portal_id, project_id, task_id)
