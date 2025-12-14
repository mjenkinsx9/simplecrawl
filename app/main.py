"""
SimpleCrawl - Self-hosted web scraping and data extraction API.

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.utils.logger import configure_logging, get_logger
from app.db.models import init_db
from app.core.browser import browser_pool
from app.api.routes import health, scrape, map, crawl, extract, batch, monitor, search, analyze

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("application_starting", version="1.0.0")
    
    # Initialize database
    try:
        init_db(settings.database_url)
        # Don't log the full database URL as it may contain credentials
        db_type = settings.database_url.split(":")[0] if ":" in settings.database_url else "unknown"
        logger.info("database_initialized", type=db_type)
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise
    
    # Initialize browser pool
    try:
        await browser_pool.initialize()
        logger.info("browser_pool_initialized")
    except Exception as e:
        logger.error("browser_pool_initialization_failed", error=str(e))
        raise
    
    logger.info("application_started")
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    # Close browser pool
    try:
        await browser_pool.close()
        logger.info("browser_pool_closed")
    except Exception as e:
        logger.error("browser_pool_close_failed", error=str(e))
    
    logger.info("application_shutdown_complete")


# Create FastAPI app
app = FastAPI(
    title="SimpleCrawl API",
    description="Self-hosted web scraping and data extraction API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add rate limiter to app state and register exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
# Note: allow_credentials=False when using allow_origins=["*"] for security
# In production, specify explicit origins and set allow_credentials=True if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(scrape.router, prefix="/v1", tags=["Scraping"])
app.include_router(map.router, prefix="/v1", tags=["Mapping"])
app.include_router(crawl.router, prefix="/v1", tags=["Crawling"])
app.include_router(extract.router, prefix="/v1", tags=["Extraction"])
app.include_router(batch.router, prefix="/v1", tags=["Batch"])
app.include_router(monitor.router, prefix="/v1", tags=["Monitoring"])
app.include_router(search.router, prefix="/v1", tags=["Search"])
app.include_router(analyze.router, prefix="/v1", tags=["Analysis"])

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SimpleCrawl API",
        "version": "1.0.0",
        "description": "Self-hosted web scraping and data extraction API",
        "docs": "/docs",
        "health": "/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
