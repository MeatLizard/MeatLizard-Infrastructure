# server/web/app/services/chat_service.py
import asyncio
import uuid
from fastapi import Request as FastAPIRequest
from fastapi import WebSocket
from sqlalchemy.orm import Session

from shared_lib.audit import log_audit_event
from shared_lib.crypto import get_encryptor
from shared_lib.moderation import moderate_prompt
from shared_lib.schemas import Request, Response


class ChatService:
    def __init__(self, request: FastAPIRequest):
        self.request = request

    async def create_session(self, db: Session):
        session_id = uuid.uuid4()
        # In a real app, you'd create a User and Session in the DB here
        log_audit_event(
            db,
            user_id="anonymous",
            action="create_session",
            resource_type="session",
            resource_id=str(session_id),
            old_values={},
            new_values={"session_id": str(session_id)},
        )
        message_queue = self.request.app.state.message_queue
        self.request.app.state.response_queues[str(session_id)] = asyncio.Queue()
        await message_queue.put({"action": "create_session", "session_id": str(session_id)})
        return {"session_id": str(session_id)}

    async def send_message(self, db: Session, request: Request):
        if not moderate_prompt(request.prompt):
            return Response(
                session_id=request.session_id,
                request_id=request.request_id,
                response="Your prompt contains inappropriate content.",
            )
        log_audit_event(
            db,
            user_id="anonymous",
            action="send_message",
            resource_type="message",
            resource_id=str(request.request_id),
            old_values={},
            new_values={"prompt": request.prompt},
        )
        encryptor = get_encryptor()
        encrypted_prompt = encryptor.encrypt(request.prompt)

        message_queue = self.request.app.state.message_queue
        await message_queue.put(
            {
                "action": "send_message",
                "session_id": str(request.session_id),
                "prompt": encrypted_prompt,
            }
        )

        response_queue = self.request.app.state.response_queues[str(request.session_id)]
        response = await response_queue.get()

        return Response(
            session_id=request.session_id,
            request_id=request.request_id,
            response=response,
        )

    async def handle_websocket(self, websocket: WebSocket, session_id: str, db: Session):
        await websocket.accept()
        response_queue = self.request.app.state.response_queues[session_id]
        while True:
            data = await websocket.receive_text()
            if not moderate_prompt(data):
                await websocket.send_text("Your prompt contains inappropriate content.")
                continue
            
            log_audit_event(
                db,
                user_id="anonymous",
                action="send_message_ws",
                resource_type="message",
                resource_id=str(uuid.uuid4()),
                old_values={},
                new_values={"prompt": data},
            )

            encryptor = get_encryptor()
            encrypted_prompt = encryptor.encrypt(data)

            message_queue = self.request.app.state.message_queue
            await message_queue.put(
                {
                    "action": "send_message",
                    "session_id": session_id,
                    "prompt": encrypted_prompt,
                }
            )
            
            response = await response_queue.get()
            await websocket.send_text(response)
