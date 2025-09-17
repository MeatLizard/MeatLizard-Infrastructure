"""
Shared configuration classes for MeatLizard AI Platform.
"""
import os
from typing import List, Dict, Any
from pydantic import BaseModel
import yaml

class ServerBotConfig(BaseModel):
    """Configuration for the Discord Server Bot."""
    
    # Discord settings
    DISCORD_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    CLIENT_BOT_ID: int = int(os.getenv("DISCORD_CLIENT_BOT_ID", "0"))
    GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID", "0"))
    ADMIN_ROLES: List[int] = []
    
    # Encryption
    PAYLOAD_ENCRYPTION_KEY: str = os.getenv("PAYLOAD_ENCRYPTION_KEY", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/meatlizard")
    
    # S3 Storage
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "meatlizard-storage")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Parse admin roles from comma-separated string
        admin_roles_str = os.getenv("DISCORD_ADMIN_ROLES", "")
        if admin_roles_str:
            self.ADMIN_ROLES = [int(role_id.strip()) for role_id in admin_roles_str.split(",")]

class ClientBotConfig:
    """Configuration for the Discord Client Bot."""
    
    def __init__(self, config_path: str = "client_bot/config.yml"):
        self.config_path = config_path
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Client bot settings
            client_bot = config.get("client_bot", {})
            self.token = client_bot.get("token", os.getenv("DISCORD_CLIENT_BOT_TOKEN", ""))
            self.server_bot_id = int(client_bot.get("server_bot_id", os.getenv("DISCORD_SERVER_BOT_ID", "0")))
            
            # Encryption
            self.payload_encryption_key = config.get("payload_encryption_key", os.getenv("PAYLOAD_ENCRYPTION_KEY", ""))
            
            # llama.cpp settings
            llama_cpp = config.get("llama_cpp", {})
            self.llama_cpp = LlamaCppConfig(
                executable_path=llama_cpp.get("executable_path", "/usr/local/bin/llama-cpp"),
                n_ctx=llama_cpp.get("n_ctx", 4096),
                threads=llama_cpp.get("threads", 6),
                n_gpu_layers=llama_cpp.get("n_gpu_layers", 28)
            )
            
            # Models
            self.models = {}
            for model in config.get("models", []):
                self.models[model["alias"]] = {
                    "path": model["path"],
                    "description": model.get("description", "")
                }
            
            # Monitoring
            monitoring = config.get("monitoring", {})
            self.enable_battery_monitor = monitoring.get("enable_battery_monitor", True)
            self.low_battery_threshold_percent = monitoring.get("low_battery_threshold_percent", 20)
            self.metrics_reporting_interval = monitoring.get("metrics_reporting_interval", 30)
            
        except FileNotFoundError:
            # Use defaults if config file not found
            self._load_defaults()
        except Exception as e:
            print(f"Error loading config: {e}")
            self._load_defaults()
    
    def _load_defaults(self):
        """Load default configuration."""
        self.token = os.getenv("DISCORD_CLIENT_BOT_TOKEN", "")
        self.server_bot_id = int(os.getenv("DISCORD_SERVER_BOT_ID", "0"))
        self.payload_encryption_key = os.getenv("PAYLOAD_ENCRYPTION_KEY", "")
        
        self.llama_cpp = LlamaCppConfig()
        self.models = {
            "default": {
                "path": os.getenv("DEFAULT_MODEL_PATH", ""),
                "description": "Default language model"
            }
        }
        
        self.enable_battery_monitor = True
        self.low_battery_threshold_percent = 20
        self.metrics_reporting_interval = 30

class LlamaCppConfig(BaseModel):
    """Configuration for llama.cpp integration."""
    
    executable_path: str = "/usr/local/bin/llama-cpp"
    n_ctx: int = 4096
    threads: int = 6
    n_gpu_layers: int = 28
    batch_size: int = 512
    
class WebServerConfig(BaseModel):
    """Configuration for the FastAPI web server."""
    
    # Application
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/meatlizard")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@meatlizard.com")
    
    # Storage
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "meatlizard-storage")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    # File limits
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB
    MAX_VIDEO_SIZE: int = int(os.getenv("MAX_VIDEO_SIZE", str(10 * 1024 * 1024 * 1024)))  # 10GB