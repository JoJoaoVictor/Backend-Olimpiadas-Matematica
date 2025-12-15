"""Configuração do Gunicorn para produção."""

import multiprocessing
import os

# Servidor
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts
timeout = 30
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Processo
preload_app = True
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (descomente em produção com HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

def on_starting(server):
    """Callback executado no início."""
    server.log.info("🚀 Gunicorn iniciando...")

def on_reload(server):
    """Callback executado no reload."""
    server.log.info("🔄 Gunicorn recarregando...")

def worker_int(worker):
    """Callback para interrupção de worker.""" 
    worker.log.info("👋 Worker %s interrompido", worker.pid)

def post_fork(server, worker):
    """Callback após fork de worker."""
    server.log.info("👶 Worker %s iniciado", worker.pid)

def pre_exec(server):
    """Callback antes de exec."""
    server.log.info("📋 Gunicorn configurado: %d workers", server.num_workers)