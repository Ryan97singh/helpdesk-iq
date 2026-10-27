import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.ratelimit import rate_limit
from app.core.security import CurrentUser, DbSession
from app.repositories.conversations import get_conversations
from app.schemas import ChatIn
from app.services.rag import answer_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream", dependencies=[Depends(rate_limit)])
def chat_stream(body: ChatIn, user: CurrentUser, db: DbSession):
    """Server-Sent Events: one `data: {json}` line per event (sources, token, done, error)."""

    def events():
        for event in answer_stream(db, user, body.message.strip()):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/history")
def history(user: CurrentUser, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    return get_conversations().recent(user.id, limit)


@router.delete("/history", status_code=204)
def clear_history(user: CurrentUser):
    get_conversations().clear(user.id)
