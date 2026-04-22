# app/main.py
# --------------------------------------------------------------------------------
# CONFIGURAÇÃO INICIAL DO AMBIENTE (CRÍTICO PARA WINDOWS + PLAYWRIGHT)
# --------------------------------------------------------------------------------
import sys
import asyncio

# O Playwright no Windows exige o ProactorEventLoop para gerenciar subprocessos (navegador).
# O padrão do Uvicorn ou do Python em alguns ambientes é o SelectorEventLoop, que causa erro 500.
# Esta configuração força o loop correto imediatamente ao carregar o módulo.
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        # Apenas logamos silenciosamente caso já exista um loop rodando que impeça a troca
        pass

# --------------------------------------------------------------------------------
# IMPORTAÇÕES GERAIS
# --------------------------------------------------------------------------------

# Biblioteca para gerenciamento do ciclo de vida do Playwright (singleton)
from app.utils.playwright_manager import PlaywrightManager
# Utilizado para controlar o ciclo de vida da aplicação (startup e shutdown)
from contextlib import asynccontextmanager

# Utilizado para medir tempo de execução e fornecer timestamp
import time

# Biblioteca padrão de logging para registro de eventos do sistema
import logging

# Biblioteca padrão para manipulação de caminhos e sistema operacional
import os

# --------------------------------------------------------------------------------
# FastAPI e Starlette
# --------------------------------------------------------------------------------

# Classe principal do FastAPI e objetos de requisição/status
from fastapi import FastAPI, Request, status

# Middleware para configuração de CORS (Cross-Origin Resource Sharing)
from fastapi.middleware.cors import CORSMiddleware

# Classe para retornar respostas em formato JSON personalizado
from fastapi.responses import JSONResponse

# Suporte a arquivos estáticos (CSS, JS, Imagens)
from fastapi.staticfiles import StaticFiles 

# Exceção base HTTP do Starlette para tratamento de erros
from starlette.exceptions import HTTPException as StarletteHTTPException

# --------------------------------------------------------------------------------
# Módulos internos da aplicação
# --------------------------------------------------------------------------------

# Importa as configurações globais (variáveis de ambiente, flags)
from app.core.config import settings

# Importa o motor de banco de dados e a base declarativa do SQLAlchemy
from app.database import engine, Base 

# --------------------------------------------------------------------------------
# Importação das rotas da API
# --------------------------------------------------------------------------------

# Importa os roteadores de cada módulo da versão 1 da API
from app.api.v1 import auth, users, questions, categories, graus, exams, images, notifications

# --------------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DE LOGS
# --------------------------------------------------------------------------------

# Configura o sistema de logs com o nível definido nas configurações (INFO, DEBUG, etc.)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Cria o logger específico para este módulo
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------
# 2. CICLO DE VIDA DA APLICAÇÃO (LIFESPAN)
# --------------------------------------------------------------------------------

# Define o gerenciador de contexto para o ciclo de vida da aplicação
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código executado quando a aplicação inicia
    logger.info("🚀 Iniciando aplicação FastAPI")
    
    # Verifica e cria as tabelas do banco de dados apenas se estiver em ambiente de desenvolvimento
    if settings.is_development:
        try:
            logger.info("📦 Verificando tabelas do banco de dados...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Tabelas sincronizadas.")
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas: {e}")
    
    # Pausa a execução aqui enquanto a aplicação estiver rodando (yield)
    yield 
    
    # Código executado quando a aplicação é encerrada
    logger.info("👋 Encerrando aplicação")

# --------------------------------------------------------------------------------
# 3. INICIALIZAÇÃO DO APP
# --------------------------------------------------------------------------------

# Instancia a aplicação FastAPI com metadados e o gerenciador de ciclo de vida
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

# Define as origens que têm permissão para fazer chamadas nesta API
origins = [
    "http://localhost:5173",      # Vite Local
    "http://127.0.0.1:5173",
    "http://localhost:3000",      # React Padrão
    "http://localhost:5000",      # Json-server (se necessário)
    "http://localhost:5001",      # Backend (caso rode em porta alternativa)
]

# Adiciona o middleware de CORS para permitir requisições das origens listadas
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------------
# 5. ARQUIVOS ESTÁTICOS
# --------------------------------------------------------------------------------

# Garante que o diretório de uploads existe
os.makedirs("uploads/images", exist_ok=True)

# Serve arquivos estáticos (se houver)
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve arquivos de upload
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configuração para servir arquivos estáticos (atualmente desativada/comentada)
# os.makedirs("static/images", exist_ok=True) 
# app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------------------------------------------------------------
# 6. MIDDLEWARE DE LOGGING DE REQUISIÇÕES
# --------------------------------------------------------------------------------

# Middleware que intercepta todas as requisições HTTP para logging de performance
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Registra o tempo inicial
    start_time = time.time()

    # Processa a requisição e aguarda a resposta
    response = await call_next(request)

    # Calcula a duração total
    process_time = time.time() - start_time

    # Loga o método, caminho, status HTTP e tempo decorrido
    logger.info(
        f"✅ {request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s"
    )

    return response

# --------------------------------------------------------------------------------
# 7. TRATAMENTO DE ERROS GLOBAIS
# --------------------------------------------------------------------------------

# Captura qualquer exceção não tratada na aplicação
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Registra o erro no log
    logger.error(f"❌ Erro Crítico: {str(exc)}")

    # Retorna um JSON amigável com código 500
    return JSONResponse(
        status_code=500,
        content={
            "success": False, 
            "message": "Erro interno do servidor", 
            "detail": str(exc) if settings.is_development else "Contate o suporte."
        }
    )

# --------------------------------------------------------------------------------
# 8. ROTAS LEGADO
# --------------------------------------------------------------------------------

# Rota raiz simples para verificar se a API está de pé
@app.get("/")
async def root():
    return {"message": "API Olimpíadas rodando!", "docs": "/docs"}

# Rota para verificação de saúde do sistema (Health Check)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "server_time": time.time()}

# Rotas simuladas para manter compatibilidade com chamadas antigas do frontend
@app.get("/questoesAprovadas")
async def get_questoes_aprovadas():
    return {"data": []}

@app.get("/projects")
async def get_projects():
    return {"data": []}

@app.get("/provasMontadas")
async def get_provas_montadas():
    return {"data": []}

# --------------------------------------------------------------------------------
# 9. ROTAS DA API V1 (OFICIAL)
# --------------------------------------------------------------------------------

# Inclui os roteadores organizados por funcionalidade, com prefixos e tags
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticação"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Usuários"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["Categorias"])
app.include_router(graus.router, prefix="/api/v1/graus", tags=["Graus"])
app.include_router(images.router, prefix="/api/v1/images", tags=["Imagens"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questões"])
app.include_router(exams.router, prefix="/api/v1/exams", tags=["Provas"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notificações"])

# --------------------------------------------------------------------------------
# 10. EXECUÇÃO DA APLICAÇÃO
# --------------------------------------------------------------------------------

# Este bloco só executa se você rodar "python app/main.py"
if __name__ == "__main__":
    import uvicorn
    
    # Reforça a política de eventos caso o bloco superior não tenha surtido efeito
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Inicia o servidor Uvicorn na porta 8000
    # reload=True habilita reinício automático ao alterar código
    # Ao rodar por aqui, garantimos que o loop configurado acima seja o utilizado
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# --------------------------------------------------------------------------------
# 11. CICLO DE VIDA DO PLAYWRIGHT (INICIALIZAÇÃO E ENC
# --------------------------------------------------------------------------------

# O Playwright é inicializado no startup da aplicação e encerrado no shutdown para garantir que o navegador seja gerenciado corretamente.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        logger.info("🚀 Iniciando aplicação")
        if settings.is_development:
            Base.metadata.create_all(bind=engine)
        # Aquece o Playwright
        PlaywrightManager.get_browser()
        yield
        # Shutdown
        PlaywrightManager.close()
        logger.info("👋 Encerrando aplicação")