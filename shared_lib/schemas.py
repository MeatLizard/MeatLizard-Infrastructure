# shared_lib/schemas.py
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime


class Request(BaseModel):
    session_id: uuid.UUID
    request_id: uuid.UUID
    prompt: str


class Response(BaseModel):
    session_id: uuid.UUID
    request_id: uuid.UUID
    response: str
    metrics: Optional[dict] = None


class Error(BaseModel):
    session_id: uuid.UUID
    request_id: uuid.UUID
    error_message: str
