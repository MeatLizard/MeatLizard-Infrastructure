"""
SQLAlchemy 2.0 database models.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, BigInteger, DateTime, Enum as SAEnum, ForeignKey, Text, 
    Boolean, Integer
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB

Base = declarative_base()

class ContentTypeEnum(str, enum.Enum):
    aichat = "aichat"
    url = "url"
    paste = "paste"
    media = "media"
    comment = "comment"
    playlist = "playlist"

class PrivacyLevelEnum(str, enum.Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"
    password = "password"

class TranscodingStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class UserTierEnum(str, enum.Enum):
    guest = "guest"
    free = "free"
    vip = "vip"
    paid = "paid"
    business = "business"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_id = Column(BigInteger, unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    display_label = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    content = relationship("Content", back_populates="user")

class Content(Base):
    __tablename__ = "content"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    content_type = Column(SAEnum(ContentTypeEnum), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="content")
    
    __mapper_args__ = {'polymorphic_on': content_type}

class AIChatSession(Content):
    __tablename__ = "ai_chat_sessions"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    discord_channel_id = Column(BigInteger, unique=True, index=True, nullable=True)
    system_prompt = Column(Text, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    messages = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    __mapper_args__ = {'polymorphic_identity': ContentTypeEnum.aichat}

class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('ai_chat_sessions.id'), nullable=False, index=True)
    request_id = Column(UUID(as_uuid=True), unique=True, index=True)
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("AIChatSession", back_populates="messages")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('ai_chat_sessions.id'), nullable=False)
    s3_key = Column(String(500), nullable=False)
    format = Column(String(4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_bot_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    data = Column(JSONB, nullable=False)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String(100), primary_key=True)
    value = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)

class BackupLog(Base):
    __tablename__ = "backup_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backup_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

class URLShortener(Content):
    __tablename__ = "url_shortener"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    max_clicks = Column(Integer, nullable=True)
    click_count = Column(Integer, default=0, nullable=False)

    __mapper_args__ = {'polymorphic_identity': ContentTypeEnum.url}

class Paste(Content):
    __tablename__ = "pastes"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    paste_id = Column(String(10), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    max_views = Column(Integer, nullable=True)
    view_count = Column(Integer, default=0, nullable=False)

    __mapper_args__ = {'polymorphic_identity': ContentTypeEnum.paste}

class MediaFile(Content):
    __tablename__ = "media_files"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    media_id = Column(String(10), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    storage_path = Column(Text, nullable=False)
    
    transcoding_status = Column(SAEnum(TranscodingStatusEnum), default=TranscodingStatusEnum.pending, nullable=False)
    transcoded_files = Column(JSONB, default=lambda: {})
    transcoding_error = Column(Text, nullable=True)
    captions = Column(Text, nullable=True)

    __mapper_args__ = {'polymorphic_identity': ContentTypeEnum.media}

class Comment(Content):
    __tablename__ = "comments"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    parent_content_id = Column(UUID(as_uuid=True), ForeignKey('content.id'), nullable=False, index=True)
    text = Column(Text, nullable=False)
    
    __mapper_args__ = {
        'polymorphic_identity': ContentTypeEnum.comment,
        'inherit_condition': id == Content.id
    }

class Reaction(Base):
    __tablename__ = "reactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    content_id = Column(UUID(as_uuid=True), ForeignKey('content.id'), nullable=False, index=True)
    reaction_type = Column(String(50), nullable=False)

class Playlist(Content):
    __tablename__ = "playlists"
    id = Column(UUID(as_uuid=True), ForeignKey('content.id'), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    items = relationship("PlaylistItem", back_populates="playlist", cascade="all, delete-orphan")
    
    __mapper_args__ = {'polymorphic_identity': ContentTypeEnum.playlist}

class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playlist_id = Column(UUID(as_uuid=True), ForeignKey('playlists.id'), nullable=False, index=True)
    media_file_id = Column(UUID(as_uuid=True), ForeignKey('media_files.id'), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    
    playlist = relationship("Playlist", back_populates="items")

class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leaderboard_name = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    score = Column(BigInteger, nullable=False)
    rank = Column(Integer, nullable=False)

class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    content_id = Column(UUID(as_uuid=True), ForeignKey('content.id'), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    data = Column(JSONB, default=lambda: {})

class UptimeRecord(Base):
    __tablename__ = "uptime_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), nullable=False, index=True)
    is_online = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = Column(Text, nullable=True)

class TierConfiguration(Base):
    __tablename__ = "tier_configurations"
    tier = Column(SAEnum(UserTierEnum), primary_key=True)
    display_name = Column(String(50), nullable=False)
    allow_vanity_slugs = Column(Boolean, default=False, nullable=False)
    allow_custom_domains = Column(Boolean, default=False, nullable=False)
    storage_quota_gb = Column(Integer, default=1, nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    allow_custom_reactions = Column(Boolean, default=False, nullable=False)
    community_roles = Column(JSONB, default=lambda: [])

class UserTier(Base):
    __tablename__ = "user_tiers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    tier = Column(SAEnum(UserTierEnum), nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_date = Column(DateTime, nullable=True)
