# app/utils/playwright_manager.py
import threading
from playwright.sync_api import sync_playwright, Browser
import logging

logger = logging.getLogger(__name__)

class PlaywrightManager:
    _instance = None
    _lock = threading.Lock()
    _playwright = None
    _browser: Browser = None

    @classmethod
    def get_browser(cls) -> Browser:
        with cls._lock:
            if cls._browser is None:
                logger.info("🚀 Inicializando Playwright (singleton)")
                cls._playwright = sync_playwright().start()
                cls._browser = cls._playwright.chromium.launch(
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--disable-plugins",
                        "--memory-pressure-off",
                        "--js-flags=--max-old-space-size=1536" # Limita a memória do processo do navegador para 1.5GB, evitando estouros de memória em ambientes com recursos limitados
                    ]
                )
            return cls._browser

    @classmethod
    def close(cls):
        with cls._lock:
            if cls._browser:
                cls._browser.close()
                cls._browser = None
            if cls._playwright:
                cls._playwright.stop()
                cls._playwright = None
            logger.info("🛑 Playwright encerrado")