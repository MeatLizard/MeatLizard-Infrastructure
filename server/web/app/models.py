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
import sqlalchemy as sa
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

class VideoStatus(str, enum.Enum):
    uploading = "uploading"
    processing = "processing"
    transcoding = "transcoding"
    ready = "ready"
    failed = "failed"
    deleted = "deleted"

class VideoVisibility(str, enum.Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"

class TranscodingStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ImportStatus(str, enum.Enum):
    queued = "queued"
    downloading = "downloading"
    processing = "processing"
    completed = "completed"
    failed = "failed"

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

# Video Platform Models

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    
    # Channel settings
    visibility = Column(SAEnum(VideoVisibility), default=VideoVisibility.public, nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)
    
    # Metadata
    banner_s3_key = Column(String(500))
    avatar_s3_key = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    creator = relationship("User")
    videos = relationship("Video", back_populates="channel")
    playlists = relationship("VideoPlaylist", back_populates="channel")

class VideoPlaylist(Base):
    __tablename__ = "video_playlists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=True, index=True)
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Playlist settings
    visibility = Column(SAEnum(VideoVisibility), default=VideoVisibility.public, nullable=False, index=True)
    auto_advance = Column(Boolean, default=True, nullable=False)
    shuffle_enabled = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    thumbnail_s3_key = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    creator = relationship("User")
    channel = relationship("Channel", back_populates="playlists")
    items = relationship("VideoPlaylistItem", back_populates="playlist", cascade="all, delete-orphan", order_by="VideoPlaylistItem.position")

class VideoPlaylistItem(Base):
    __tablename__ = "video_playlist_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playlist_id = Column(UUID(as_uuid=True), ForeignKey("video_playlists.id"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    
    position = Column(Integer, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    playlist = relationship("VideoPlaylist", back_populates="items")
    video = relationship("Video")
    
    # Ensure unique position per playlist
    __table_args__ = (
        sa.UniqueConstraint('playlist_id', 'position', name='uq_playlist_position'),
    )

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    tags = Column(JSONB, default=lambda: [])
    category = Column(String(50), nullable=True, index=True)
    
    # File information
    original_filename = Column(String(255), nullable=False)
    original_s3_key = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    
    # Video properties
    source_resolution = Column(String(20))  # "1920x1080"
    source_framerate = Column(Integer)
    source_codec = Column(String(50))
    source_bitrate = Column(Integer)
    
    # Status and visibility
    status = Column(SAEnum(VideoStatus), default=VideoStatus.uploading, nullable=False, index=True)
    visibility = Column(SAEnum(VideoVisibility), default=VideoVisibility.private, nullable=False, index=True)
    
    # Metadata
    thumbnail_s3_key = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    creator = relationship("User")
    channel = relationship("Channel", back_populates="videos")
    transcoding_jobs = relationship("TranscodingJob", back_populates="video", cascade="all, delete-orphan")
    view_sessions = relationship("ViewSession", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("VideoComment", back_populates="video", cascade="all, delete-orphan")
    likes = relationship("VideoLike", back_populates="video", cascade="all, delete-orphan")

class TranscodingJob(Base):
    __tablename__ = "transcoding_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    
    # Job configuration
    quality_preset = Column(String(20), nullable=False)  # "720p_30fps"
    target_resolution = Column(String(20), nullable=False)
    target_framerate = Column(Integer, nullable=False)
    target_bitrate = Column(Integer, nullable=False)
    
    # Job status
    status = Column(SAEnum(TranscodingStatus), default=TranscodingStatus.queued, nullable=False, index=True)
    progress_percent = Column(Integer, default=0, nullable=False)
    error_message = Column(Text)
    
    # Output information
    output_s3_key = Column(String(500))
    hls_manifest_s3_key = Column(String(500))
    output_file_size = Column(BigInteger)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    video = relationship("Video", back_populates="transcoding_jobs")

class ViewSession(Base):
    __tablename__ = "view_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Session data
    session_token = Column(String(100), unique=True, nullable=False, index=True)
    ip_address_hash = Column(String(64))
    user_agent_hash = Column(String(64))
    
    # Viewing progress
    current_position_seconds = Column(Integer, default=0, nullable=False)
    total_watch_time_seconds = Column(Integer, default=0, nullable=False)
    completion_percentage = Column(Integer, default=0, nullable=False)
    
    # Quality metrics
    qualities_used = Column(JSONB, default=lambda: [])
    quality_switches = Column(Integer, default=0, nullable=False)
    buffering_events = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime)
    
    # Relationships
    video = relationship("Video", back_populates="view_sessions")
    user = relationship("User")

class VideoComment(Base):
    __tablename__ = "video_comments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    parent_comment_id = Column(UUID(as_uuid=True), ForeignKey("video_comments.id"), nullable=True, index=True)
    
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    video = relationship("Video", back_populates="comments")
    user = relationship("User")
    parent_comment = relationship("VideoComment", remote_side=[id])
    replies = relationship("VideoComment", back_populates="parent_comment")

class VideoLike(Base):
    __tablename__ = "video_likes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    is_like = Column(Boolean, nullable=False)  # True for like, False for dislike
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    video = relationship("Video", back_populates="likes")
    user = relationship("User")
    
    # Ensure one like/dislike per user per video
    __table_args__ = (
        sa.UniqueConstraint('video_id', 'user_id', name='uq_video_user_like'),
    )

class VideoPermission(Base):
    """Model for explicit video permissions"""
    __tablename__ = "video_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    permission_type = Column(String(50), nullable=False, default="view")  # view, edit, admin
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    video = relationship("Video")
    user = relationship("User", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    # Ensure unique permission per user per video per type
    __table_args__ = (
        sa.UniqueConstraint('video_id', 'user_id', 'permission_type', name='uq_video_user_permission'),
    )

class ContentReport(Base):
    """Model for user-submitted content reports"""
    __tablename__ = "content_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content_type = Column(String(50), nullable=False)  # video, comment, user, channel
    content_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    reason = Column(String(100), nullable=False)
    description = Column(Text)
    evidence_urls = Column(JSONB, default=lambda: [])
    
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, resolved, dismissed
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_action = Column(String(50), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

class ModerationRecord(Base):
    """Model for moderation actions taken on content"""
    __tablename__ = "moderation_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_type = Column(String(50), nullable=False)
    content_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    action = Column(String(50), nullable=False)  # approved, flagged, hidden, removed, etc.
    reason = Column(String(100), nullable=False)
    moderator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # None for automated
    
    notes = Column(Text)
    duration_hours = Column(Integer, nullable=True)  # For temporary actions
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    moderator = relationship("User")

class ImportJob(Base):
    """Model for media import jobs using yt-dlp"""
    __tablename__ = "import_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String(2000), nullable=False)
    platform = Column(String(50), nullable=False, index=True)
    
    # Import configuration
    import_config = Column(JSONB, nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Status tracking
    status = Column(SAEnum(ImportStatus), default=ImportStatus.queued, nullable=False, index=True)
    progress_percent = Column(Integer, default=0, nullable=False)
    error_message = Column(Text)
    
    # Source metadata
    original_title = Column(String(500))
    original_description = Column(Text)
    original_uploader = Column(String(200))
    original_upload_date = Column(DateTime)
    original_duration = Column(Integer)
    original_view_count = Column(Integer)
    original_like_count = Column(Integer)
    
    # Output information
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=True)
    downloaded_file_path = Column(String(1000))
    
    # Discord integration
    discord_channel_id = Column(String(50))  # Channel where import was requested
    discord_message_id = Column(String(50))  # Message that triggered import
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    video = relationship("Video")
    requested_by_user = relationship("User", foreign_keys=[requested_by])

class ImportPreset(Base):
    """Model for import configuration presets"""
    __tablename__ = "import_presets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Default configuration
    config = Column(JSONB, nullable=False)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    creator = relationship("User")
