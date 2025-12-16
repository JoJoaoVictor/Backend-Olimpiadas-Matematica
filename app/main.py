from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import logging
from typing import Union
 
from app.core.config import settings
from app.core.exceptions import AppException
from app.api.v1 import auth, users, questions, categories, graus, exams, images
from app.database import engine
from app.models import BaseModel as Base


# Configuração de logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de startup e shutdown da aplicação."""
    # Startup
    logger.info("🚀 Iniciando aplicação FastAPI")
    
    # Cria tabelas se não existirem (apenas em desenvolvimento)
    if settings.is_development:
        logger.info("📦 Criando tabelas do banco de dados...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelas criadas com sucesso")
    
    # Configuração adicional de startup
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
        logger.info("📊 Sentry configurado")
    
    yield
    
    # Shutdown
    logger.info("👋 Encerrando aplicação")


# Criação da app FastAPI
app = FastAPI(
    title="Olimpíadas de Matemática API",
    description="""
    API para sistema de gestão de olimpíadas de matemática.
    
    ## Funcionalidades
    
    * **Autenticação** - JWT com refresh tokens
    * **Usuários** - Gestão de professores e alunos  
    * **Questões** - CRUD com LaTeX e imagens
    * **Provas** - Montagem e geração de PDF
    * **Categorias** - Organização de questões
    * **Upload** - Imagens otimizadas
    """,
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan
)

# Middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
    
)
"""# Middleware de CORS - TESTE TEMPORÁRIO
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #  "*"  testes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""
# Middleware de hosts confiáveis (apenas em produção)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["olimpiadas-api.exemplo.com", "localhost"]
    )


# Middleware customizado para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware para logging detalhado de requests."""
    start_time = time.time()
    
    # Log da request
    logger.info(
        f"🌐 {request.method} {request.url.path} - "
        f"IP: {request.client.host} - "
        f"User-Agent: {request.headers.get('user-agent', 'Unknown')}"
    )
    
    # Processa request
    response = await call_next(request)
    
    # Log da response
    process_time = time.time() - start_time
    logger.info(
        f"✅ {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    # Adiciona header com tempo de processamento
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handler para exceções customizadas da aplicação."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_type": exc.__class__.__name__
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler para exceções HTTP padrão."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_type": "HTTPException"
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler para erros de validação Pydantic."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Dados de entrada inválidos",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler para exceções não tratadas."""
    logger.error(f"❌ Erro não tratado: {str(exc)}", exc_info=True)
    
    if settings.is_development:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Erro interno do servidor",
                "detail": str(exc),
                "error_type": exc.__class__.__name__
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Erro interno do servidor"
            }
        )


# Rotas de sistema
@app.get("/", tags=["Sistema"])
async def root():
    """Endpoint raiz da API."""
    return {
        "success": True,
        "message": "API Olimpíadas de Matemática",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs" if settings.is_development else "Desabilitado em produção"
    }


@app.get("/health", tags=["Sistema"])
async def health_check():
    """Health check da aplicação."""
    return {
        "success": True,
        "status": "healthy",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }


# Inclusão das rotas da API v1
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Autenticação"]
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["Usuários"]
)

app.include_router(
    categories.router,
    prefix="/api/v1/categories",
    tags=["Categorias"]
)

app.include_router(
    graus.router,
    prefix="/api/v1/graus", 
    tags=["Graus Educacionais"]
)

app.include_router(
    images.router,
    prefix="/api/v1/images",
    tags=["Imagens"]
)

app.include_router(
    questions.router,
    prefix="/api/v1/questions",
    tags=["Questões"]
)

app.include_router(
    exams.router,
    prefix="/api/v1/exams",
    tags=["Provas"]
)