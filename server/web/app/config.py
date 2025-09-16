from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MEDIA_STORAGE_PATH: str = "media"
    SECRET_KEY: str = "a-very-secret-key"

settings = Settings()