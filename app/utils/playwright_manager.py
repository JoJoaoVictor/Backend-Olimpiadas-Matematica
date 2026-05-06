# app/utils/playwright_manager.py
import logging
from playwright.async_api import async_playwright, Browser

logger = logging.getLogger(__name__)

class PlaywrightManager:
    """Gerencia o navegador Playwright de forma assíncrona (singleton)."""

    _playwright = None
    _browser: Browser | None = None

    @classmethod
    async def get_browser(cls) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            logger.info("🚀 Inicializando Playwright (assíncrono)")
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                ]
            )
        return cls._browser

    @classmethod
    async def close(cls):
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None