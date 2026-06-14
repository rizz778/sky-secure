from fastapi import APIRouter

from app.tools.zoho_client import debug_portal_endpoints, get_portals, get_projects, get_tasks

router = APIRouter(prefix="/zoho", tags=["zoho"])


@router.get("/portals")
async def portals():
    return await get_portals()


@router.get("/projects")
async def projects(portal_id: str):
    return await get_projects(portal_id)


@router.get("/tasks")
async def tasks(portal_id: str, project_id: str):
    return await get_tasks(portal_id, project_id)


@router.get("/debug/portals")
async def debug_portals():
    return await debug_portal_endpoints()
