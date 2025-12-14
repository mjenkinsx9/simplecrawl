"""
Celery tasks for async job processing.
"""

from celery import Celery

from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "simplecrawl",
    broker=settings.redis_url,
    backend=settings.redis_url
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
)


@celery_app.task(name="simplecrawl.crawl")
def crawl_task(job_id: str, url: str, config: dict) -> dict:
    """
    Celery task for crawling a website.
    
    Args:
        job_id: Unique job identifier
        url: Starting URL to crawl
        config: Crawl configuration
    
    Returns:
        Job result dictionary
    """
    # Import here to avoid circular imports
    from app.core.crawler import crawl_website
    
    try:
        result = crawl_website(job_id, url, config)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(name="simplecrawl.batch_scrape")
def batch_scrape_task(job_id: str, urls: list[str], config: dict) -> dict:
    """
    Celery task for batch scraping multiple URLs.
    
    Args:
        job_id: Unique job identifier
        urls: List of URLs to scrape
        config: Scrape configuration
    
    Returns:
        Job result dictionary
    """
    # Import here to avoid circular imports
    from app.core.scraper import batch_scrape_urls
    
    try:
        result = batch_scrape_urls(job_id, urls, config)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(name="simplecrawl.check_monitor")
def check_monitor_task(monitor_id: str) -> dict:
    """
    Celery task for checking content changes.
    
    Args:
        monitor_id: Monitor identifier
    
    Returns:
        Check result dictionary
    """
    # Import here to avoid circular imports
    from app.core.monitor import check_content_change
    
    try:
        result = check_content_change(monitor_id)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
