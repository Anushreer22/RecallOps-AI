from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "RecallOps-AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./recallops.db"
    
    # LLM Settings
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2
    
    # Operational Constants
    SIMILARITY_THRESHOLD: float = 0.15
    MAX_HISTORICAL_RECALL: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
