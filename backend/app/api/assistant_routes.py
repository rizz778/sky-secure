import logging

from pydantic import BaseModel
from fastapi import APIRouter

from app.agents.router import route_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    portal_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    confirmation: bool | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    logger.info(
        "assistant/chat request received: session_id=%s user_id=%s portal_id=%s project_id=%s task_id=%s confirmation=%s",
        request.session_id,
        request.user_id,
        request.portal_id,
        request.project_id,
        request.task_id,
        request.confirmation,
    )
    try:
        result = await route_message(
            message=request.message,
            session_id=request.session_id,
            user_id=request.user_id,
            # portal_id=request.portal_id,
            # project_id=request.project_id,
            # task_id=request.task_id,
            # confirmation=request.confirmation,
        )
        logger.info("assistant/chat response generated: agent=%s routing_reason=%s", result.get("agent"), result.get("routing_reason"))
        return result
    except Exception as exc:
        logger.exception("assistant/chat failed")
        raise
