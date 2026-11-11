from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "RecallOps-AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./recallops.db"
    
    # LLM Settings
    LLM_PROVIDER: str = "openai"  # openai, mock, etc.
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 2
    
    # Webhook Ingestion & Security
    PAGERDUTY_WEBHOOK_SECRET: Optional[str] = None
    DATADOG_WEBHOOK_TOKEN: Optional[str] = None
    ALERTMANAGER_WEBHOOK_TOKEN: Optional[str] = None
    WEBHOOK_AUTH_REQUIRED: bool = True
    WEBHOOK_MAX_PAYLOAD_BYTES: int = 2 * 1024 * 1024  # 2 MB limit
    
    # JWT & Authentication
    JWT_SECRET_KEY: str = "recallops-dev-secret-key-change-in-production-12345678"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    PASSWORD_MIN_LENGTH: int = 8
    
    # Operational Constants
    SIMILARITY_THRESHOLD: float = 0.15
    MAX_HISTORICAL_RECALL: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
