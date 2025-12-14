"""
Multi-page crawling functionality.
"""

import asyncio
from typing import Dict, Any, List, Set
from urllib.parse import urlparse, urljoin
from datetime import datetime
import fnmatch

from sqlalchemy.orm import Session

from app.config import settings
from app.core.scraper import scrape_url
from app.db.models import CrawlJob, get_session
from app.utils.logger import get_logger

logger = get_logger(__name__)


def crawl_website(job_id: str, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crawl a website starting from a URL (synchronous wrapper for Celery).
    
    Args:
        job_id: Job identifier
        url: Starting URL
        config: Crawl configuration
    
    Returns:
        Crawl results
    """
    logger.info("crawl_started", job_id=job_id, url=url)
    
    # Run async crawling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        results = loop.run_until_complete(_crawl_async(job_id, url, config))
        logger.info("crawl_completed", job_id=job_id, page_count=len(results))
        return {"results": results}
    finally:
        loop.close()


async def _crawl_async(job_id: str, start_url: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Async implementation of website crawling.
    
    Args:
        job_id: Job identifier
        start_url: Starting URL
        config: Crawl configuration
    
    Returns:
        List of crawled pages
    """
    limit = config.get("limit", 100)
    depth = config.get("depth", 3)
    scrape_options = config.get("scrape_options", {})
    include_patterns = config.get("include_patterns", [])
    exclude_patterns = config.get("exclude_patterns", [])
    
    # Parse base domain
    parsed_url = urlparse(start_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Initialize crawl state
    visited: Set[str] = set()
    to_visit: List[tuple[str, int]] = [(start_url, 0)]  # (url, depth)
    results: List[Dict[str, Any]] = []
    
    # Get database session
    db = get_session(settings.database_url)
    
    # Update job status
    update_job_status(db, job_id, "running", total=1)
    
    while to_visit and len(results) < limit:
        current_url, current_depth = to_visit.pop(0)
        
        # Skip if already visited
        if current_url in visited:
            continue
        
        # Skip if depth exceeded
        if current_depth > depth:
            continue
        
        # Check URL patterns
        if not should_crawl_url(current_url, include_patterns, exclude_patterns):
            continue
        
        visited.add(current_url)
        
        try:
            # Scrape the page
            formats = scrape_options.get("formats", ["markdown", "metadata"])
            exclude_tags = scrape_options.get("exclude_tags")
            
            data = await scrape_url(current_url, formats, exclude_tags)
            
            # Add to results
            results.append({
                "url": current_url,
                "depth": current_depth,
                **data
            })
            
            # Update job progress
            update_job_status(
                db, job_id, "running",
                total=len(to_visit) + len(results),
                completed=len(results)
            )
            
            # Extract links for next level
            if current_depth < depth and "links" in data:
                for link in data["links"]:
                    # Only crawl same domain
                    if link.startswith(base_domain) and link not in visited:
                        to_visit.append((link, current_depth + 1))
            
        except Exception as e:
            logger.error("crawl_page_failed", url=current_url, error=str(e))
            # Update failed count
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
            if job:
                job.failed += 1
                db.commit()
    
    # Mark job as completed
    update_job_status(
        db, job_id, "completed",
        total=len(results),
        completed=len(results),
        results=results,
        completed_at=datetime.utcnow()
    )
    
    db.close()
    return results


def should_crawl_url(url: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    """
    Check if URL should be crawled based on patterns.
    
    Args:
        url: URL to check
        include_patterns: Glob patterns to include
        exclude_patterns: Glob patterns to exclude
    
    Returns:
        True if URL should be crawled
    """
    # Check exclude patterns first
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(url, pattern):
            return False
    
    # If include patterns specified, URL must match at least one
    if include_patterns:
        return any(fnmatch.fnmatch(url, pattern) for pattern in include_patterns)
    
    return True


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    total: int = 0,
    completed: int = 0,
    results: Any = None,
    completed_at: Any = None
) -> None:
    """
    Update crawl job status in database.
    
    Args:
        db: Database session
        job_id: Job identifier
        status: Job status
        total: Total items
        completed: Completed items
        results: Job results
        completed_at: Completion timestamp
    """
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if job:
        job.status = status
        if total > 0:
            job.total = total
        if completed > 0:
            job.completed = completed
        if results is not None:
            job.results = {"data": results}
        if completed_at is not None:
            job.completed_at = completed_at
        db.commit()
