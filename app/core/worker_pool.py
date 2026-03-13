# app/core/worker_pool.py
import logging
from app.utils.pdf_worker_pool import PDFWorkerPool

logger = logging.getLogger(__name__)

_pool_instance = None

def init_pool(num_workers: int = 2) -> PDFWorkerPool:
    """Inicializa o pool de workers (chamado no startup)."""
    global _pool_instance
    if _pool_instance is None:
        logger.info(f"Inicializando PDFWorkerPool com {num_workers} workers")
        _pool_instance = PDFWorkerPool(num_workers=num_workers)
    return _pool_instance

def get_pool() -> PDFWorkerPool:
    """Retorna a instância do pool (deve ser chamada após init_pool)."""
    if _pool_instance is None:
        raise RuntimeError("PDFWorkerPool não foi inicializado. Chame init_pool primeiro.")
    return _pool_instance

def shutdown_pool():
    """Encerra o pool (chamado no shutdown)."""
    global _pool_instance
    if _pool_instance:
        logger.info("Encerrando PDFWorkerPool")
        try:
            _pool_instance.shutdown()
        except Exception as e:
            logger.warning(f"Erro ao encerrar pool (ignorado): {e}")
        _pool_instance = None