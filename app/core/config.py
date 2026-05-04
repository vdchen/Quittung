from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union

# Bootstrap Settings class to detect environment without os.getenv
class EnvBootstrap(BaseSettings):
    ENVIRONMENT: str = "development"

_env = EnvBootstrap()
TARGET_ENV_FILE = ".env.test" if _env.ENVIRONMENT == "testing" else ".env"


class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Quittung"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_URL: str = "http://api:8000/api/v1"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

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

    # Webhook security: set this to a random secret and pass it when registering
    # the webhook with Telegram via set_webhook(secret_token=...).
    TELEGRAM_WEBHOOK_SECRET: str | None = None

    model_config = SettingsConfigDict(
        env_file=TARGET_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()