"""
Celery tasks for async job processing.

Includes Celery Beat configuration for scheduled tasks.
"""

from datetime import datetime
from celery import Celery
from celery.schedules import crontab

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
    task_time_limit=172800,  # 48 hours max per task (for long Cloudflare crawls)
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
)

# Celery Beat schedule - periodic tasks
celery_app.conf.beat_schedule = {
    # Scan for monitors due for checking every minute
    "scan-monitors-every-minute": {
        "task": "simplecrawl.scan_monitors",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Clean up old completed jobs every hour
    "cleanup-old-jobs-hourly": {
        "task": "simplecrawl.cleanup_old_jobs",
        "schedule": crontab(minute=0),  # Every hour at minute 0
    },
}


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


@celery_app.task(name="simplecrawl.scan_monitors")
def scan_monitors_task() -> dict:
    """
    Periodic task to scan for monitors due for checking.

    This task runs every minute via Celery Beat and queues
    check_monitor_task for any monitors whose next_check time has passed.

    Returns:
        Dictionary with count of monitors queued
    """
    # Import here to avoid circular imports
    from app.db.models import Monitor, get_session_context

    queued = 0

    try:
        with get_session_context(settings.database_url) as db:
            # Find active monitors due for checking
            now = datetime.utcnow()
            due_monitors = db.query(Monitor).filter(
                Monitor.active == True,
                Monitor.next_check <= now
            ).all()

            for monitor in due_monitors:
                # Queue a check task for each due monitor
                check_monitor_task.delay(monitor.id)
                queued += 1

        return {
            "success": True,
            "queued_count": queued,
            "scanned_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task(name="simplecrawl.cleanup_old_jobs")
def cleanup_old_jobs_task() -> dict:
    """
    Periodic task to clean up old completed/failed jobs.

    This task runs hourly via Celery Beat and removes jobs older than
    the configured retention period.

    Returns:
        Dictionary with count of jobs cleaned up
    """
    # Import here to avoid circular imports
    from datetime import timedelta
    from app.db.models import CrawlJob, BatchJob, get_session_context

    deleted_crawl = 0
    deleted_batch = 0

    try:
        retention_hours = settings.job_retention_hours
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)

        with get_session_context(settings.database_url) as db:
            # Delete old crawl jobs
            old_crawl = db.query(CrawlJob).filter(
                CrawlJob.created_at < cutoff,
                CrawlJob.status.in_(["completed", "failed"])
            ).all()

            for job in old_crawl:
                db.delete(job)
                deleted_crawl += 1

            # Delete old batch jobs
            old_batch = db.query(BatchJob).filter(
                BatchJob.created_at < cutoff,
                BatchJob.status.in_(["completed", "failed"])
            ).all()

            for job in old_batch:
                db.delete(job)
                deleted_batch += 1

        return {
            "success": True,
            "deleted_crawl_jobs": deleted_crawl,
            "deleted_batch_jobs": deleted_batch,
            "cleaned_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
