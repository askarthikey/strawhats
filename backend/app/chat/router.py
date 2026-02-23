from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from app.chat.schemas import ChatRequest
from app.chat.service import rag_generate, get_chat_history, clear_chat_history
from app.auth.dependencies import get_current_user
import ujson

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """Stream RAG-powered chat response via Server-Sent Events."""

    async def event_generator():
        chat_history_dicts = [
            {"role": m.role, "content": m.content}
            for m in req.chat_history
        ]

        async for event in rag_generate(
            question=req.question,
            workspace_id=req.workspace_id,
            user_id=current_user["id"],
            chat_history=chat_history_dicts,
            template=req.template,
            provider_name=req.provider,
            top_k=req.top_k,
            temperature=req.temperature,
            use_mmr=req.use_mmr,
        ):
            yield {
                "event": event.get("type", "token"),
                "data": ujson.dumps(event),
            }

    return EventSourceResponse(event_generator())


@router.get("/history/{workspace_id}")
async def get_history(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Get chat history for a workspace."""
    history = await get_chat_history(workspace_id, limit)
    # Serialize ObjectId and datetime
    for log in history:
        for key, val in log.items():
            if hasattr(val, "isoformat"):
                log[key] = val.isoformat()
    return {"history": history}


@router.delete("/history/{workspace_id}")
async def clear_history(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Clear chat history for a workspace."""
    count = await clear_chat_history(workspace_id)
    return {"message": f"Deleted {count} chat logs"}
