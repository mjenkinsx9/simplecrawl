"""
Playwright browser pool management for efficient browser reuse.
"""

import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserPool:
    """
    Manages a pool of Playwright browser contexts for efficient reuse.
    """
    
    def __init__(self, pool_size: int = 5, headless: bool = True, user_agent: Optional[str] = None):
        """
        Initialize the browser pool.
        
        Args:
            pool_size: Maximum number of browser contexts to maintain
            headless: Whether to run browsers in headless mode
            user_agent: Custom user agent string
        """
        self.pool_size = pool_size
        self.headless = headless
        self.user_agent = user_agent or settings.user_agent
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: list[BrowserContext] = []
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the browser pool."""
        if self._initialized:
            return
        
        logger.info("browser_pool_initializing", pool_size=self.pool_size)
        
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        self._initialized = True
        logger.info("browser_pool_initialized")
    
    async def close(self) -> None:
        """Close all browser contexts and the browser."""
        logger.info("browser_pool_closing")
        
        # Close all contexts
        for context in self._contexts:
            try:
                await context.close()
            except Exception as e:
                logger.warning("context_close_failed", error=str(e))
        
        self._contexts.clear()
        
        # Close browser
        if self._browser:
            await self._browser.close()
        
        # Stop playwright
        if self._playwright:
            await self._playwright.stop()
        
        self._initialized = False
        logger.info("browser_pool_closed")
    
    @asynccontextmanager
    async def get_context(self):
        """
        Get a browser context from the pool.
        
        Yields:
            BrowserContext: A Playwright browser context
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._lock:
            # Reuse existing context if available
            if self._contexts:
                context = self._contexts.pop()
                logger.debug("context_reused", pool_size=len(self._contexts))
            else:
                # Create new context
                context = await self._browser.new_context(
                    user_agent=self.user_agent,
                    viewport={'width': 1920, 'height': 1080}
                )
                logger.debug("context_created", pool_size=len(self._contexts))
        
        try:
            yield context
        finally:
            # Return context to pool or close if pool is full
            async with self._lock:
                if len(self._contexts) < self.pool_size:
                    # Clear cookies and storage before returning to pool
                    try:
                        await context.clear_cookies()
                    except Exception:
                        pass
                    
                    self._contexts.append(context)
                    logger.debug("context_returned", pool_size=len(self._contexts))
                else:
                    # Pool is full, close the context
                    await context.close()
                    logger.debug("context_closed_pool_full", pool_size=len(self._contexts))
    
    @asynccontextmanager
    async def get_page(self):
        """
        Get a new page from a browser context.
        
        Yields:
            Page: A Playwright page
        """
        async with self.get_context() as context:
            page = await context.new_page()
            try:
                yield page
            finally:
                await page.close()


# Global browser pool instance
browser_pool = BrowserPool(
    pool_size=settings.browser_pool_size,
    headless=settings.headless,
    user_agent=settings.user_agent
)
