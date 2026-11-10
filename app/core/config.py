"""Configuración central de la aplicación mediante variables de entorno."""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "RunSense AI Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Base de datos
    DATABASE_URL: str = "postgresql+psycopg2://runsense:runsense_pass@localhost:5432/runsense_db"

    # JWT
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:4200",
        "http://localhost",
    ]

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["fit", "gpx", "tcx", "csv"]

    # gRPC AI Service
    AI_SERVICE_HOST: str = "localhost"
    AI_SERVICE_PORT: int = 50051
    AI_SERVICE_TIMEOUT_SECONDS: int = 30
    AI_SERVICE_MAX_RETRIES: int = 2

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Admin
    FIRST_SUPERUSER_EMAIL: str = "admin@runsense.ai"
    FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"


settings = Settings()
