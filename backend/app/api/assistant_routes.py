from pydantic import BaseModel
from fastapi import APIRouter

from app.agents.router import route_message

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    portal_id: str | None = None
    project_id: str | None = None
    confirmation: bool | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    return await route_message(
        message=request.message,
        session_id=request.session_id,
        user_id=request.user_id,
        portal_id=request.portal_id,
        project_id=request.project_id,
        confirmation=request.confirmation,
    )
