# app/utils/pdf_worker_pool.py
import asyncio
import io
import queue
import threading
import uuid
from typing import Any, Dict, Optional

from app.utils.pdf_generator import AdvancedPDFGenerator
from app.utils.playwright_manager import PlaywrightManager
import logging

logger = logging.getLogger(__name__)


class PDFWorkerPool:
    def __init__(self, num_workers: int = 2):
        self.task_queue = queue.Queue()
        self.result_store: Dict[str, Any] = {}
        self.result_lock = threading.Lock()
        self.shutdown_flag = threading.Event()
        self.workers = []
        self.num_workers = num_workers
        self._start_workers()

    def _worker_loop(self):
        """Executado em cada thread worker."""
        browser = PlaywrightManager.get_browser()
        logger.info(f"Worker thread {threading.get_ident()} iniciado com browser {browser}")

        while not self.shutdown_flag.is_set():
            try:
                task_id, exam, questions, options = self.task_queue.get(timeout=1)
                logger.info(f"Worker processando tarefa {task_id}")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro ao obter tarefa: {e}")
                continue

            try:
                pdf_buffer = AdvancedPDFGenerator.create_exam_pdf(exam, questions, options)
                with self.result_lock:
                    self.result_store[task_id] = pdf_buffer
                logger.info(f"Tarefa {task_id} concluída com sucesso")
            except Exception as e:
                logger.error(f"Erro na tarefa {task_id}: {e}")
                with self.result_lock:
                    self.result_store[task_id] = e
            finally:
                self.task_queue.task_done()

        PlaywrightManager.close()
        logger.info(f"Worker thread {threading.get_ident()} encerrado")

    def _start_workers(self):
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"PDFWorker-{i}")
            self.workers.append(t)
            t.start()
            logger.info(f"Worker {i} iniciado")

    async def generate_pdf_async(self, exam: Any, questions: list, options: Optional[Dict] = None) -> io.BytesIO:
        task_id = str(uuid.uuid4())
        self.task_queue.put((task_id, exam, questions, options or {}))

        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(0.1)
            with self.result_lock:
                if task_id in self.result_store:
                    result = self.result_store.pop(task_id)
                    if isinstance(result, Exception):
                        raise result
                    return result

    def shutdown(self):
        self.shutdown_flag.set()
        for t in self.workers:
            t.join(timeout=5)
        logger.info("PDFWorkerPool encerrado.")