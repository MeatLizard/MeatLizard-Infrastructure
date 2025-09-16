# server/web/app/api/chat.py
from fastapi import APIRouter, Depends, WebSocket
from shared_lib.schemas import Request, Response
from shared_lib.db import get_db_session
from sqlalchemy.orm import Session
from server.web.app.services.chat_service import ChatService

router = APIRouter()


@router.post("/chat/session")
async def create_session(
    db: Session = Depends(get_db_session), service: ChatService = Depends()
):
    return await service.create_session(db)


@router.post("/chat/message")
async def send_message(
    request: Request,
    db: Session = Depends(get_db_session),
    service: ChatService = Depends(),
):
    return await service.send_message(db, request)


@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db_session),
    service: ChatService = Depends(),
):
    await service.handle_websocket(websocket, session_id, db)
