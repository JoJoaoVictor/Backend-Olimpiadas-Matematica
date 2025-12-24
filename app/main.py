# app/main.py
# --------------------------------------------------------------------------------
# IMPORTAÇÕES
# --------------------------------------------------------------------------------
from contextlib import asynccontextmanager
import time
import logging

# FastAPI e Starlette
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Módulos Internos da Aplicação
from app.core.config import settings
from app.core.exceptions import AppException
from app.database import engine
from app.models import BaseModel as Base

# Importação das Rotas (Endpoints)
from app.api.v1 import auth, users, questions, categories, graus, exams, images

# --------------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DE LOGS (Para ver o que acontece no terminal)
# --------------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------
# 2. CICLO DE VIDA DA APLICAÇÃO (Lifespan)
# Executa código antes do servidor iniciar e depois que ele desliga
# --------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup (Início) ---
    logger.info("🚀 Iniciando aplicação FastAPI - MODO TESTE")
    
    # Cria as tabelas no banco de dados automaticamente se estiver em modo DEV
    if settings.is_development:
        logger.info("📦 Verificando/Criando tabelas do banco de dados...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelas sincronizadas com sucesso")
    
    yield # A aplicação roda aqui
    
    # --- Shutdown (Desligamento) ---
    logger.info("👋 Encerrando aplicação")

# --------------------------------------------------------------------------------
# 3. INICIALIZAÇÃO DO APP FASTAPI
# --------------------------------------------------------------------------------
app = FastAPI(
    title="Olimpíadas de Matemática API",
    description="API Backend para o sistema de provas e questões.",
    version="1.0.0",
    docs_url="/docs",               # URL da documentação Swagger
    redoc_url="/redoc",             # URL da documentação Redoc
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# --------------------------------------------------------------------------------
# 4. CONFIGURAÇÃO DE CORS (CRUCIAL PARA O FRONTEND + LOGIN GOOGLE)
# Define quem pode acessar este backend.
# --------------------------------------------------------------------------------
origins = [
    "http://localhost:5173",      # Vite / React (Seu Frontend)
    "http://127.0.0.1:5173",      # Variação do localhost
    "http://localhost:3000",      # Caso use Create React App (backup)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # Lista de endereços permitidos acima
    allow_credentials=True,       # IMPORTANTE: Permite cookies/sessões (Google Auth precisa disso)
    allow_methods=["*"],          # Permite GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],          # Permite enviar tokens e headers json
)

# --------------------------------------------------------------------------------
# 5. MIDDLEWARE DE LOGGING DE REQUISIÇÕES
# Monitora o tempo de resposta de cada chamada
# --------------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Loga a entrada da requisição
    logger.info(f"🌐 Recebendo: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Loga o tempo total e o status (200, 404, 500, etc)
    process_time = time.time() - start_time
    logger.info(f"✅ Finalizado: {request.method} {request.url.path} - Status: {response.status_code} - Tempo: {process_time:.4f}s")
    
    return response

# --------------------------------------------------------------------------------
# 6. TRATAMENTO DE ERROS (EXCEPTION HANDLERS)
# Captura erros inesperados para não derrubar o servidor
# --------------------------------------------------------------------------------
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Erro Crítico Não Tratado: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False, 
            "message": "Erro interno do servidor", 
            "detail": str(exc) if settings.is_development else "Contate o suporte."
        }
    )

# --------------------------------------------------------------------------------
# 7. ROTAS BÁSICAS E DE COMPATIBILIDADE (LEGACY)
# Endpoints temporários para garantir que o frontend antigo não quebre
# --------------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Olimpíadas rodando!", "docs": "/docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "server_time": time.time()}

# --- Endpoints Simulados (Mocks) para o Frontend ---
@app.get("/questoesAprovadas")
async def get_questoes_aprovadas():
    return {"message": "Endpoint legado - questões aprovadas", "data": []}

@app.get("/projects")
async def get_projects():
    return {"message": "Endpoint legado - projects", "data": []}

@app.get("/provasMontadas")
async def get_provas_montadas():
    return {"message": "Endpoint legado - provas montadas", "data": []}

@app.get("/categoris") # Mantido o nome original (typo) se o front chama assim
async def get_categoris():
    return {"message": "Endpoint legado - categoris", "data": []}

@app.get("/grau")
async def get_grau():
    return {"message": "Endpoint legado - grau", "data": []}

# --------------------------------------------------------------------------------
# 8. INCLUSÃO DAS ROTAS DA API V1 (OFICIAL)
# Conecta os arquivos da pasta /api/v1 ao app principal
# --------------------------------------------------------------------------------
try:
    # Autenticação (Login Google, etc)
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticação"])
    
    # Recursos do Sistema
    app.include_router(users.router, prefix="/api/v1/users", tags=["Usuários"])
    app.include_router(categories.router, prefix="/api/v1/categories", tags=["Categorias"])
    app.include_router(graus.router, prefix="/api/v1/graus", tags=["Graus"])
    app.include_router(images.router, prefix="/api/v1/images", tags=["Imagens"])
    app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questões"])
    app.include_router(exams.router, prefix="/api/v1/exams", tags=["Provas"])
    
    logger.info("✅ Todas as rotas da API V1 foram carregadas.")

except Exception as e:
    logger.warning(f"⚠️ AVISO: Alguma rota falhou ao carregar. Verifique os imports em app/api/v1/__init__.py. Erro: {e}")


# --------------------------------------------------------------------------------
# 9. EXECUÇÃO DIRETA (DEBUG)
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Roda o servidor na porta 8000
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)