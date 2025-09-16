# shared_lib/models.py
import enum
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Enum,
    Float,
    Text,
    Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # Discord user ID or a unique identifier for web users
    user_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)  # Discord username or "User #N"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)

    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discord_channel_id = Column(String, unique=True, nullable=False)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    system_prompt = Column(Text, nullable=True)
    model_parameters = Column(JSON, default={})

    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    transcript = relationship("Transcript", back_populates="session", uselist=False)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    message_id = Column(String, unique=True, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    # 'user' or 'ai'
    sender_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="messages")


class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True)
    transcript_id = Column(String, unique=True, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    storage_provider = Column(String, default="s3")
    storage_path = Column(String, nullable=False)  # e.g., "s3://bucket-name/transcripts/transcript_id.json"
    format = Column(String, default="json")  # 'json' or 'csv'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_public = Column(Boolean, default=False) # For opt-in sharing

    session = relationship("Session", back_populates="transcript")


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    metric_name = Column(String, nullable=False, index=True) # e.g., 'tokens_per_second', 'gpu_utilization'
    value = Column(Float, nullable=False)
    tags = Column(JSON, nullable=True) # e.g., {"client_id": "client-1", "model": "vicuna-13b"}


class SystemConfig(Base):
    __tablename__ = "system_configs"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BackupStatus(Base):
    __tablename__ = "backup_status"
    id = Column(Integer, primary_key=True)
    backup_id = Column(String, unique=True, nullable=False, index=True)
    backup_type = Column(String, nullable=False) # 'database' or 'transcripts'
    status = Column(String, nullable=False) # 'started', 'completed', 'failed'
    storage_path = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


# Example of how to create the engine and tables
if __name__ == "__main__":
    # This is for demonstration/testing purposes.
    # In the actual app, this would be configured from environment variables.
    DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print("Database tables created.")