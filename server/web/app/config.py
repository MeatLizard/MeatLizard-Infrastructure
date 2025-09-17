from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "MeatLizard AI Platform"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "a-very-secret-key-change-in-production"
    JWT_SECRET_KEY: str = "jwt-secret-key-change-in-production"
    DOMAIN: str = "localhost:8000"
    
    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/meatlizard"
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379"
    
    # Discord Bot settings
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_CLIENT_BOT_TOKEN: str = ""
    DISCORD_GUILD_ID: int = 0
    DISCORD_CLIENT_BOT_ID: int = 0
    DISCORD_ADMIN_ROLES: str = ""  # Comma-separated role IDs
    
    # Encryption settings
    PAYLOAD_ENCRYPTION_KEY: str = ""  # Base64 encoded 32-byte key
    
    # Email settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@meatlizard.com"
    ADMIN_EMAIL: str = "admin@meatlizard.com"
    
    # File storage settings
    MEDIA_STORAGE_PATH: str = "media"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: str = "jpg,jpeg,png,gif,mp4,mov,avi,mkv,pdf,txt,md"
    
    # Video upload settings
    MAX_VIDEO_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB
    MAX_VIDEO_DURATION: int = 4 * 60 * 60  # 4 hours in seconds
    CHUNK_SIZE: int = 5 * 1024 * 1024  # 5MB chunks
    
    # S3 settings
    S3_BUCKET_NAME: str = "meatlizard-storage"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = ""  # For S3-compatible services
    
    # Transcoding settings
    TRANSCODING_TEMP_DIR: str = "/tmp/transcoding"
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"
    
    # AI/LLM settings
    LLAMA_CPP_PATH: str = "/usr/local/bin/llama-cpp"
    DEFAULT_MODEL_PATH: str = ""
    MAX_CONTEXT_LENGTH: int = 4096
    DEFAULT_TEMPERATURE: float = 0.7
    
    # Rate limiting settings
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # URL Shortener settings
    SHORT_URL_LENGTH: int = 6
    CUSTOM_DOMAIN: str = ""
    
    # Pastebin settings
    PASTE_ID_LENGTH: int = 8
    MAX_PASTE_SIZE: int = 1024 * 1024  # 1MB
    DEFAULT_PASTE_EXPIRY_DAYS: int = 30
    
    # Analytics settings
    ANALYTICS_RETENTION_DAYS: int = 365
    ENABLE_ANALYTICS: bool = True
    
    # Security settings
    BCRYPT_ROUNDS: int = 12
    SESSION_TIMEOUT_HOURS: int = 24
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    
    # Content moderation
    ENABLE_CONTENT_MODERATION: bool = True
    AUTO_MODERATE_THRESHOLD: float = 0.8
    
    # Background tasks
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # Import settings
    YTDLP_PATH: str = "yt-dlp"
    MAX_IMPORT_SIZE: int = 5 * 1024 * 1024 * 1024  # 5GB
    IMPORT_TEMP_DIR: str = "/tmp/imports"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()