# app/core/config.py
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Configurações da aplicação.
    """

    # ------------------------------------------------------------------------
    # CONFIGURAÇÕES GERAIS
    # ------------------------------------------------------------------------
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True

    # ------------------------------------------------------------------------
    # BANCO DE DADOS
    # ------------------------------------------------------------------------
    DATABASE_URL: str
    DATABASE_TEST_URL: Optional[str] = None

    # ------------------------------------------------------------------------
    # SEGURANÇA
    # ------------------------------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    GOOGLE_CLIENT_ID: Optional[str] = None

    # ------------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",
    ]
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]

    # ------------------------------------------------------------------------
    # UPLOAD / STATIC
    # ------------------------------------------------------------------------
    MAX_FILE_SIZE: int = 10485760
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif", "svg"]
    UPLOAD_PATH: str = "./uploads"
    STATIC_PATH: str = "./static"

    STATIC_URL: str = "/static"
    UPLOAD_URL: str = "/uploads"

    # ------------------------------------------------------------------------
    # REDIS & EMAIL
    # ------------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    SENTRY_DSN: Optional[str] = None

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # ------------------------------------------------------------------------
    # VALIDADORES (Pydantic V2)
    # ------------------------------------------------------------------------
    @field_validator("ALLOWED_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("DATABASE_URL", mode="before")
    def assemble_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL é obrigatório")
        return v

    @field_validator("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_SERVER")
    def validate_mail_required_in_production(cls, v, info: ValidationInfo):
        env = info.data.get("ENVIRONMENT")
        if env == "production" and not v:
            raise ValueError(f"{info.field_name} é obrigatório em ambiente de produção")
        return v

    # ------------------------------------------------------------------------
    # PROPRIEDADES AUXILIARES
    # ------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"

    class Config:
        env_file = ".env.production"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()