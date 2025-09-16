"""
Configuration management system with environment variable validation.
Provides centralized configuration for all system components.
"""

import os
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from pydantic_settings import BaseSettings
from enum import Enum
import json
from dotenv import load_dotenv


class LogLevel(str, Enum):
    """Supported logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    url: Optional[str] = None
    host: str = Field(..., description="Database host")
    port: int = Field(5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    pool_size: int = Field(10, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(20, ge=0, le=100, description="Max pool overflow")
    
    def get_url(self) -> str:
        """Get PostgreSQL connection URL."""
        if self.url:
            return self.url
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseModel):
    """Redis connection configuration."""
    host: str = Field("localhost", description="Redis host")
    port: int = Field(6379, ge=1, le=65535, description="Redis port")
    password: Optional[str] = Field(None, description="Redis password")
    db: int = Field(0, ge=0, le=15, description="Redis database number")
    max_connections: int = Field(20, ge=1, le=100, description="Max connections")
    
    @property
    def url(self) -> str:
        """Get Redis connection URL."""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class S3Config(BaseModel):
    """S3 storage configuration."""
    bucket_name: str = Field(..., description="S3 bucket name")
    region: str = Field("us-east-1", description="AWS region")
    access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    secret_access_key: Optional[str] = Field(None, description="AWS secret access key")
    endpoint_url: Optional[str] = Field(None, description="Custom S3 endpoint URL")


class DiscordConfig(BaseModel):
    """Discord bot configuration."""
    bot_token: str = Field(..., description="Discord bot token")
    guild_id: int = Field(..., description="Discord guild ID")
    admin_role_ids: List[int] = Field(default_factory=list, description="Admin role IDs")
    command_prefix: str = Field("!", description="Bot command prefix")
    max_message_length: int = Field(2000, ge=1, le=4000, description="Max message length")


class LLMConfig(BaseModel):
    """LLM processing configuration."""
    model_path: str = Field(..., description="Path to LLM model file")
    context_length: int = Field(4096, ge=512, le=32768, description="Context window size")
    threads: int = Field(8, ge=1, le=64, description="Processing threads")
    gpu_layers: int = Field(-1, ge=-1, description="GPU layers (-1 for all)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling")
    max_tokens: int = Field(512, ge=1, le=4096, description="Max output tokens")
    mps_enabled: bool = Field(True, description="Enable Metal Performance Shaders")
    server_port: int = Field(8080, ge=1024, le=65535, description="llama.cpp server port")


class SecurityConfig(BaseModel):
    """Security and encryption configuration."""
    encryption_key: str = Field(..., description="Base64-encoded AES-256 key")
    jwt_secret: str = Field(..., description="JWT signing secret")
    session_timeout: int = Field(3600, ge=300, le=86400, description="Session timeout in seconds")
    rate_limit_requests: int = Field(100, ge=1, description="Rate limit requests per window")
    rate_limit_window: int = Field(3600, ge=60, description="Rate limit window in seconds")
    
    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v):
        """Validate encryption key format."""
        try:
            import base64
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError("Encryption key must decode to 32 bytes")
            return v
        except Exception:
            raise ValueError("Invalid base64 encryption key")


class WebServerConfig(BaseModel):
    """Web server configuration."""
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, ge=1024, le=65535, description="Server port")
    cors_origins: List[str] = Field(default_factory=list, description="CORS allowed origins")
    max_request_size: int = Field(1048576, ge=1024, description="Max request size in bytes")
    workers: int = Field(1, ge=1, le=16, description="Number of worker processes")


class MediaConfig(BaseModel):
    """Media service configuration."""
    allowed_mime_types: List[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "video/mp4"],
        description="Allowed MIME types for media uploads"
    )
    clamd_socket: str = Field("/var/run/clamav/clamd.ctl", description="Path to ClamAV socket")




class SystemConfig(BaseSettings):
    """
    Main system configuration with environment variable validation.
    
    Environment variables are automatically loaded and validated.
    Supports .env files and system environment variables.
    """
    
    # Environment and logging
    environment: str = Field("development", description="Environment name")
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
    debug: bool = Field(False, description="Enable debug mode")
    
    # Component configurations
    database: DatabaseConfig
    redis: RedisConfig
    s3: S3Config
    discord: DiscordConfig
    llm: LLMConfig
    security: SecurityConfig
    web_server: WebServerConfig
    media: Optional[MediaConfig] = None
    
    # Feature flags
    enable_fallback: bool = Field(True, description="Enable Markov fallback")
    enable_metrics: bool = Field(True, description="Enable metrics collection")
    enable_transcripts: bool = Field(True, description="Enable transcript generation")

    # Background worker settings
    cleanup_interval_seconds: int = Field(300, ge=60, description="Interval for cleaning up expired pastes")
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False
    )
    
    @classmethod
    def from_env(cls) -> 'SystemConfig':
        """Load configuration from environment variables."""
        try:
            return cls()
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SystemConfig':
        """Load configuration from dictionary."""
        try:
            return cls(**config_dict)
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return self.dict()
    
    def validate_required_env_vars(self) -> List[str]:
        """
        Validate that all required environment variables are set.
        
        Returns:
            List of missing environment variable names
        """
        missing_vars = []
        
        # Check critical environment variables
        required_vars = [
            "DATABASE__HOST",
            "DATABASE__DATABASE", 
            "DATABASE__USERNAME",
            "DATABASE__PASSWORD",
            "DISCORD__BOT_TOKEN",
            "DISCORD__GUILD_ID",
            "SECURITY__ENCRYPTION_KEY",
            "SECURITY__JWT_SECRET",
            "LLM__MODEL_PATH"
        ]
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        return missing_vars


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    pass


def load_config() -> SystemConfig:
    """
    Load and validate system configuration.
    
    Returns:
        Validated SystemConfig instance
        
    Raises:
        ConfigurationError: If configuration is invalid or missing required values
    """
    load_dotenv()
    try:
        config = SystemConfig.from_env()
        
        # Validate required environment variables
        missing_vars = config.validate_required_env_vars()
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        return config
        
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")


def create_sample_env_file(filepath: str = ".env.example") -> None:
    """
    Create a sample .env file with all configuration options.
    
    Args:
        filepath: Path to create the sample file
    """
    sample_content = '''# AI Chat Discord System Configuration

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=false

# Database Configuration
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=ai_chat_system
DATABASE__USERNAME=postgres
DATABASE__PASSWORD=your_password_here
DATABASE__POOL_SIZE=10
DATABASE__MAX_OVERFLOW=20

# Redis Configuration  
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__PASSWORD=
REDIS__DB=0
REDIS__MAX_CONNECTIONS=20

# S3 Configuration
S3__BUCKET_NAME=ai-chat-transcripts
S3__REGION=us-east-1
S3__ACCESS_KEY_ID=your_access_key_here
S3__SECRET_ACCESS_KEY=your_secret_key_here
S3__ENDPOINT_URL=

# Discord Configuration
DISCORD__BOT_TOKEN=your_bot_token_here
DISCORD__GUILD_ID=123456789012345678
DISCORD__ADMIN_ROLE_IDS=["123456789012345678"]
DISCORD__COMMAND_PREFIX=!
DISCORD__MAX_MESSAGE_LENGTH=2000

# LLM Configuration
LLM__MODEL_PATH=/path/to/your/model.gguf
LLM__CONTEXT_LENGTH=4096
LLM__THREADS=8
LLM__GPU_LAYERS=-1
LLM__TEMPERATURE=0.7
LLM__TOP_P=0.9
LLM__MAX_TOKENS=512
LLM__MPS_ENABLED=true
LLM__SERVER_PORT=8080

# Security Configuration
SECURITY__ENCRYPTION_KEY=your_base64_encoded_32_byte_key_here
SECURITY__JWT_SECRET=your_jwt_secret_here
SECURITY__SESSION_TIMEOUT=3600
SECURITY__RATE_LIMIT_REQUESTS=100
SECURITY__RATE_LIMIT_WINDOW=3600

# Web Server Configuration
WEB_SERVER__HOST=0.0.0.0
WEB_SERVER__PORT=8000
WEB_SERVER__CORS_ORIGINS=["http://localhost:3000"]
WEB_SERVER__MAX_REQUEST_SIZE=1048576
WEB_SERVER__WORKERS=1

# Media Configuration
MEDIA__ALLOWED_MIME_TYPES=["image/jpeg", "image/png", "video/mp4"]
MEDIA__CLAMD_SOCKET=/var/run/clamav/clamd.ctl


# Feature Flags
ENABLE_FALLBACK=true
ENABLE_METRICS=true
ENABLE_TRANSCRIPTS=true

# Background Worker
CLEANUP_INTERVAL_SECONDS=300
'''
    
    with open(filepath, 'w') as f:
        f.write(sample_content)


# Global configuration instance
_config: Optional[SystemConfig] = None


def get_config() -> SystemConfig:
    """
    Get the global configuration instance.
    
    Returns:
        SystemConfig instance
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> SystemConfig:
    """
    Reload configuration from environment.
    
    Returns:
        New SystemConfig instance
    """
    global _config
    _config = load_config()
    return _config