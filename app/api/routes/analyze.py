"""
Analyze endpoint to help users choose optimal scraping settings.

Provides tag analysis and suggests exclude_tags for cleaner output.
"""

from typing import List, Dict, Any, Optional
from collections import Counter

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, HttpUrl
from slowapi import Limiter
from slowapi.util import get_remote_address
from bs4 import BeautifulSoup

from app.config import settings
from app.core.browser import browser_pool
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class AnalyzeRequest(BaseModel):
    """Request model for page analysis."""

    url: HttpUrl = Field(..., description="URL to analyze")
    timeout: int = Field(
        default=30000,
        ge=5000,
        le=120000,
        description="Timeout in milliseconds"
    )


class TagInfo(BaseModel):
    """Information about an HTML tag."""

    tag: str = Field(..., description="HTML tag name")
    count: int = Field(..., description="Number of occurrences")
    sample_text: Optional[str] = Field(None, description="Sample text content (truncated)")
    sample_classes: List[str] = Field(default=[], description="Common CSS classes")
    recommendation: str = Field(..., description="Recommendation: 'exclude', 'keep', or 'optional'")
    reason: str = Field(..., description="Reason for recommendation")


class AnalyzeResponse(BaseModel):
    """Response model for page analysis."""

    success: bool
    url: str
    title: Optional[str] = None
    suggested_exclude_tags: List[str] = Field(
        default=[],
        description="Recommended tags to exclude for cleaner output"
    )
    suggested_exclude_tags_example: str = Field(
        default="",
        description="Copy-paste ready JSON array"
    )
    tag_analysis: List[TagInfo] = Field(
        default=[],
        description="Analysis of tags found on the page"
    )
    total_tags: int = 0
    error: Optional[Dict[str, Any]] = None


# Tags commonly excluded for cleaner content
COMMON_EXCLUDE_TAGS = {
    'nav': ('exclude', 'Navigation menus add noise to content'),
    'header': ('exclude', 'Site headers usually contain branding, not content'),
    'footer': ('exclude', 'Footers contain links and legal text'),
    'aside': ('optional', 'Sidebars may have related content or ads'),
    'script': ('exclude', 'JavaScript code should never be in output'),
    'style': ('exclude', 'CSS styles should never be in output'),
    'noscript': ('exclude', 'Fallback content for no-JS browsers'),
    'iframe': ('optional', 'Embedded content - depends on use case'),
    'form': ('optional', 'Forms are usually not needed for content'),
    'button': ('optional', 'Interactive elements not needed for content'),
    'svg': ('optional', 'SVG icons add visual noise to markdown'),
    'img': ('keep', 'Images - keep if you want image URLs in markdown'),
    'picture': ('keep', 'Picture elements contain images'),
    'video': ('keep', 'Video elements may have useful poster images'),
    'figure': ('keep', 'Figures usually contain important images/captions'),
    'article': ('keep', 'Main content is often in article tags'),
    'main': ('keep', 'Main content area'),
    'section': ('keep', 'Content sections'),
    'p': ('keep', 'Paragraphs are core content'),
    'h1': ('keep', 'Headings are important'),
    'h2': ('keep', 'Headings are important'),
    'h3': ('keep', 'Headings are important'),
    'ul': ('keep', 'Lists often contain important content'),
    'ol': ('keep', 'Lists often contain important content'),
    'table': ('keep', 'Tables may contain important data'),
    'blockquote': ('keep', 'Quotes are usually important'),
    'code': ('keep', 'Code blocks are important for technical content'),
    'pre': ('keep', 'Preformatted text is usually important'),
}


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(f"{settings.rate_limit_requests}/minute")
async def analyze_page(request: Request, analyze_request: AnalyzeRequest):
    """
    Analyze a page and suggest optimal exclude_tags.

    Returns:
    - Suggested exclude_tags for cleaner markdown
    - Tag-by-tag analysis with recommendations
    - Copy-paste ready JSON for the scrape request

    Use this before scraping to understand a page's structure and
    get recommendations for the best exclude_tags settings.

    Example response includes:
    ```json
    {
      "suggested_exclude_tags": ["nav", "header", "footer", "script", "style"],
      "suggested_exclude_tags_example": "[\"nav\", \"header\", \"footer\"]"
    }
    ```
    """
    url = str(analyze_request.url)

    try:
        logger.info("analyze_request", url=url)

        async with browser_pool.get_page() as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=analyze_request.timeout)
            html = await page.content()
            title = await page.title()

        soup = BeautifulSoup(html, 'lxml')

        # Count all tags
        tag_counter = Counter()
        tag_samples: Dict[str, Dict[str, Any]] = {}

        for tag in soup.find_all(True):
            tag_name = tag.name.lower()
            tag_counter[tag_name] += 1

            # Collect sample info for first occurrence
            if tag_name not in tag_samples:
                text = tag.get_text(strip=True)[:100] if tag.get_text(strip=True) else None
                classes = tag.get('class', [])[:3]  # First 3 classes
                tag_samples[tag_name] = {
                    'sample_text': text,
                    'sample_classes': classes
                }

        # Build tag analysis
        tag_analysis = []
        suggested_exclude = []

        for tag_name, count in tag_counter.most_common(30):
            rec, reason = COMMON_EXCLUDE_TAGS.get(tag_name, ('keep', 'Standard content tag'))
            sample = tag_samples.get(tag_name, {})

            tag_info = TagInfo(
                tag=tag_name,
                count=count,
                sample_text=sample.get('sample_text'),
                sample_classes=sample.get('sample_classes', []),
                recommendation=rec,
                reason=reason
            )
            tag_analysis.append(tag_info)

            # Add to suggested exclude if recommended
            if rec == 'exclude' and count > 0:
                suggested_exclude.append(tag_name)

        # Sort suggested_exclude in a logical order
        priority_order = ['script', 'style', 'noscript', 'nav', 'header', 'footer']
        suggested_exclude_sorted = []
        for tag in priority_order:
            if tag in suggested_exclude:
                suggested_exclude_sorted.append(tag)
        for tag in suggested_exclude:
            if tag not in suggested_exclude_sorted:
                suggested_exclude_sorted.append(tag)

        # Create copy-paste example
        example = '["' + '", "'.join(suggested_exclude_sorted) + '"]' if suggested_exclude_sorted else '[]'

        return AnalyzeResponse(
            success=True,
            url=url,
            title=title,
            suggested_exclude_tags=suggested_exclude_sorted,
            suggested_exclude_tags_example=example,
            tag_analysis=tag_analysis,
            total_tags=sum(tag_counter.values())
        )

    except Exception as e:
        logger.error("analyze_failed", url=url, error=str(e))
        return AnalyzeResponse(
            success=False,
            url=url,
            error={
                "code": "ANALYZE_FAILED",
                "message": str(e)
            }
        )
