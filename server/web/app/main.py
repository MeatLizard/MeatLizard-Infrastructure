# server/web/app/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

# A placeholder for database session management
# In a real app, this would be properly configured with dependencies.
def get_db():
    # This is a placeholder.
    # from server.web.database import SessionLocal
    # db = SessionLocal()
    # try:
    #     yield db
    # finally:
    #     db.close()
    yield None


app = FastAPI(
    title="MeatLizard AI Platform API",
    description="API for managing AI chat sessions.",
    version="1.0.0",
)

# --- Pydantic Models for API Requests/Responses ---

class SessionCreateRequest(BaseModel):
    user_id: str # A unique identifier for the user
    initial_prompt: str | None = None

class SessionResponse(BaseModel):
    session_id: str
    discord_channel_id: str
    start_time: str

class MessageSendRequest(BaseModel):
    prompt: str

class MessageResponse(BaseModel):
    request_id: str
    status: str # e.g., "processing", "complete"
    response: str | None = None


# --- API Endpoints ---

@app.post("/api/v1/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest, db: Session = Depends(get_db)):
    """
    Creates a new chat session.

    This endpoint is called by the web UI when a user starts a new conversation.
    It should:
    1. Create a new user in the DB if they don't exist.
    2. Create a new session in the DB.
    3. Signal the server-bot to create a private Discord channel.
    4. Return the session details.
    """
    print(f"Received request to create session for user: {request.user_id}")

    # --- Placeholder Logic ---
    # 1. Find or create user in DB.
    # 2. Create Session object in DB.
    # 3. Use a message queue (e.g., Redis Pub/Sub) or an internal API
    #    call to notify the server-bot to create the Discord channel.
    #    The bot would then update the session record with the channel ID.

    # For now, return dummy data.
    dummy_session_id = f"sess_{request.user_id}_{abs(hash(request.user_id))}"
    dummy_channel_id = "123456789012345678"

    return SessionResponse(
        session_id=dummy_session_id,
        discord_channel_id=dummy_channel_id,
        start_time="2025-09-16T20:00:00Z",
    )


@app.post("/api/v1/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, request: MessageSendRequest, db: Session = Depends(get_db)):
    """
    Sends a message to an existing chat session.

    This is the primary endpoint for user interaction. It should:
    1. Validate the session_id.
    2. Save the user's message to the database.
    3. Relay the message to the server-bot for processing by the client-bot.
    4. Return a confirmation that the message is being processed.
    """
    print(f"Received message for session {session_id}: {request.prompt}")

    # --- Placeholder Logic ---
    # 1. Look up session in DB. If not found, raise HTTPException(404).
    # 2. Save the user's Message object to the DB.
    # 3. Relay the prompt to the server-bot. This is the start of the
    #    complex data flow described in the architecture document.

    # For now, return a dummy response.
    dummy_request_id = f"req_{abs(hash(request.prompt))}"

    return MessageResponse(
        request_id=dummy_request_id,
        status="processing",
        response="The AI is thinking..." # Or this could be handled by the frontend
    )


@app.get("/api/v1/sessions/{session_id}/messages", response_model=List[dict])
async def get_session_history(session_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the message history for a session.
    """
    print(f"Fetching history for session {session_id}")
    # --- Placeholder Logic ---
    # 1. Look up session in DB.
    # 2. Query all messages associated with the session_id.
    # 3. Return them in a structured format.
    return [
        {"sender": "user", "text": "Hello!"},
        {"sender": "ai", "text": "Hi there! How can I help you today?"},
    ]


@app.get("/health", status_code=200)
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "ok"}

# To run this skeleton for testing:
# uvicorn server.web.app.main:app --reload
