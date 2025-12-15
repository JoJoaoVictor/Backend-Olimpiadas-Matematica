from functools import lru_cache
from typing import List, Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Configurações da aplicação usando Pydantic Settings."""
    
    # Configurações do servidor
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    
    # Banco de dados
    DATABASE_URL: str
    DATABASE_TEST_URL: Optional[str] = None
     
    # Segurança
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # CORS - CONFIGURAÇÃO CORRIGIDA PARA HTML LOCAL
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",  # Para arquivos HTML locais
    ]
    CORS_METHODS: List[str] = ["*"]  # Permite todos os métodos
    CORS_HEADERS: List[str] = ["*"]  # Permite todos os headers
    
    # Upload de arquivos
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif", "svg"]
    UPLOAD_PATH: str = "./uploads"
    STATIC_PATH: str = "./static"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Sentry
    SENTRY_DSN: Optional[str] = None
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Converte string separada por vírgulas em lista."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("DATABASE_URL", pre=True)
    def assemble_database_url(cls, v, values):
        """Garante que DATABASE_URL está presente."""
        if not v:
            raise ValueError("DATABASE_URL é obrigatório")
        return v
    
    @property
    def is_development(self) -> bool:
        """Verifica se está em ambiente de desenvolvimento."""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_testing(self) -> bool:
        """Verifica se está em ambiente de teste."""
        return self.ENVIRONMENT == "testing"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna configurações cached (singleton).
    
    Returns:
        Settings: Instância das configurações da aplicação
    """
    return Settings()


# Instância global das configurações
settings = get_settings()