from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union
import os

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Quittung"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    API_URL: str = "http://api:8000/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Security
    SECRET_KEY: str
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v
    
    # Integrations
    GOOGLE_API_KEY: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None

    model_config = SettingsConfigDict(
        # Look for .env first, then override with .env.test if it exists
        env_file=(".env", ".env.test"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()