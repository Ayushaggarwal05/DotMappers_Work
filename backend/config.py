from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""
    
    # App Information
    APP_NAME: str = "TracePath AI - Customer Support Analytics"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    # Database & Data
    DATABASE_URL: str = "sqlite:///./support_analytics.db"
    DATASET_PATH: str = "data/support_tickets.csv"
    AUTO_INGEST_ON_STARTUP: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]
    
    # LLM Settings (for subsequent phases)
    XAI_API_KEY: Optional[str] = None
    XAI_MODEL: str = "grok-2-latest"
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @property
    def dataset_absolute_path(self) -> Path:
        """Resolve dataset path relative to root workspace."""
        path = Path(self.DATASET_PATH)
        if not path.is_absolute():
            # If running from backend/ or root, resolve against project root
            cwd = Path.cwd()
            if (cwd / path).exists():
                return cwd / path
            # Check parent directory if cwd is backend
            if (cwd.parent / path).exists():
                return cwd.parent / path
            return cwd / path
        return path

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
