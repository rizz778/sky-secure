from pydantic import BaseModel
from fastapi import APIRouter

from app.agents.zoho_agent import run_zoho_agent

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str
    portal_id: str | None = None
    project_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    return await run_zoho_agent(
        message=request.message,
        portal_id=request.portal_id,
        project_id=request.project_id,
    )
