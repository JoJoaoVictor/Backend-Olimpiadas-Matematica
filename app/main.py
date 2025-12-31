# app/main.py
# --------------------------------------------------------------------------------
# IMPORTAÇÕES
# --------------------------------------------------------------------------------
from contextlib import asynccontextmanager
import time
import logging
import os

# FastAPI e Starlette
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles # Importante para imagens
from starlette.exceptions import HTTPException as StarletteHTTPException

# Módulos Internos da Aplicação
from app.core.config import settings
from app.database import engine, Base # Geralmente o Base vem daqui

# Importação das Rotas (Endpoints)
# Certifique-se que app/api/v1/__init__.py exporta todos estes nomes
from app.api.v1 import auth, users, questions, categories, graus, exams, images

# --------------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DE LOGS
# --------------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------
# 2. CICLO DE VIDA (Lifespan)
# --------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("🚀 Iniciando aplicação FastAPI")
    
    # Cria tabelas automaticamente em ambiente de desenvolvimento
    if settings.is_development:
        try:
            logger.info("📦 Verificando tabelas do banco de dados...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Tabelas sincronizadas.")
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas: {e}")
    
    yield # Aplicação roda aqui
    
    # --- Shutdown ---
    logger.info("👋 Encerrando aplicação")

# --------------------------------------------------------------------------------
# 3. INICIALIZAÇÃO DO APP
# --------------------------------------------------------------------------------
app = FastAPI(
    title="Olimpíadas de Matemática API",
    description="API Backend para o sistema de provas e questões.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# --------------------------------------------------------------------------------
# 4. CONFIGURAÇÃO DE CORS
# --------------------------------------------------------------------------------
origins = [
    "http://localhost:5173",      # Vite Local
    "http://127.0.0.1:5173",
    "http://localhost:3000",      # React Padrão
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------------
# 5. ARQUIVOS ESTÁTICOS (IMAGENS)
# Se você salva imagens em uma pasta 'uploads' ou 'static', descomente abaixo:
# --------------------------------------------------------------------------------
# os.makedirs("static/images", exist_ok=True) # Garante que a pasta existe
# app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------------------------------------------------------------
# 6. MIDDLEWARE DE LOGGING (Performance)
# --------------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Loga apenas se for erro ou se for lento (opcional), ou tudo (como está abaixo)
    logger.info(f"✅ {request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    
    return response

# --------------------------------------------------------------------------------
# 7. TRATAMENTO DE ERROS GLOBAIS
# --------------------------------------------------------------------------------
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erro Crítico: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False, 
            "message": "Erro interno do servidor", 
            "detail": str(exc) if settings.is_development else "Contate o suporte."
        }
    )

# --------------------------------------------------------------------------------
# 8. ROTAS LEGADO (Compatibilidade com Front antigo)
# --------------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Olimpíadas rodando!", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "server_time": time.time()}

# Mocks para evitar erros 404 no front antigo
@app.get("/questoesAprovadas")
async def get_questoes_aprovadas(): return {"data": []}

@app.get("/projects")
async def get_projects(): return {"data": []}

@app.get("/provasMontadas")
async def get_provas_montadas(): return {"data": []}

# --------------------------------------------------------------------------------
# 9. ROTAS DA API V1 (OFICIAL)
# Importante: Sem try/except para garantir que erros de importação apareçam
# --------------------------------------------------------------------------------

# Autenticação
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticação"])

# Recursos
app.include_router(users.router, prefix="/api/v1/users", tags=["Usuários"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["Categorias"])
app.include_router(graus.router, prefix="/api/v1/graus", tags=["Graus"])
app.include_router(images.router, prefix="/api/v1/images", tags=["Imagens"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questões"])
app.include_router(exams.router, prefix="/api/v1/exams", tags=["Provas"])

# Se existir o admin.py e você quiser usar:
# from app.api.v1 import admin
# app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


# --------------------------------------------------------------------------------
# 10. EXECUÇÃO
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)