"""
HTML to Markdown conversion utilities with smart content extraction.
"""

import re
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup
from markdownify import markdownify as md

# Try to import smart extraction libraries
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    import ftfy
    FTFY_AVAILABLE = True
except ImportError:
    FTFY_AVAILABLE = False

from app.utils.logger import get_logger

logger = get_logger(__name__)


# Default tags to exclude from markdown conversion
DEFAULT_EXCLUDE_TAGS = [
    'script', 'style', 'nav', 'footer', 'header',
    'aside', 'iframe', 'noscript', 'svg'
]

# Additional boilerplate patterns to remove
BOILERPLATE_PATTERNS = [
    r'cookie\s*(policy|consent|notice)',
    r'privacy\s*policy',
    r'terms\s*(of\s*service|and\s*conditions)',
    r'subscribe\s*to\s*(our)?\s*newsletter',
    r'sign\s*up\s*for\s*(our)?\s*(newsletter|updates)',
    r'follow\s*us\s*on',
    r'share\s*(this|on)\s*(facebook|twitter|linkedin)',
    r'advertisement',
    r'sponsored\s*content',
]


def clean_html(html: str, exclude_tags: Optional[List[str]] = None) -> str:
    """
    Clean HTML by removing unwanted tags.
    
    Args:
        html: Raw HTML content
        exclude_tags: List of tag names to remove
    
    Returns:
        Cleaned HTML string
    """
    if exclude_tags is None:
        exclude_tags = DEFAULT_EXCLUDE_TAGS
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove excluded tags
    for tag_name in exclude_tags:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
        comment.extract()
    
    return str(soup)


def html_to_markdown(html: str, exclude_tags: Optional[List[str]] = None) -> str:
    """
    Convert HTML to clean markdown.
    
    Args:
        html: Raw HTML content
        exclude_tags: List of tag names to exclude
    
    Returns:
        Markdown string
    """
    # Clean HTML first
    cleaned_html = clean_html(html, exclude_tags)
    
    # Convert to markdown
    markdown = md(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=['a']  # Remove links but keep text
    )
    
    # Clean up excessive whitespace
    lines = markdown.split('\n')
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        line = line.rstrip()
        is_empty = len(line) == 0
        
        # Skip multiple consecutive empty lines
        if is_empty and prev_empty:
            continue
        
        cleaned_lines.append(line)
        prev_empty = is_empty
    
    return '\n'.join(cleaned_lines).strip()


def extract_text_content(html: str) -> str:
    """
    Extract plain text content from HTML.

    Args:
        html: Raw HTML content

    Returns:
        Plain text string
    """
    soup = BeautifulSoup(html, 'lxml')

    # Remove script and style tags
    for tag in soup(['script', 'style']):
        tag.decompose()

    # Get text
    text = soup.get_text(separator='\n', strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)


def fix_encoding(text: str) -> str:
    """
    Fix text encoding issues using ftfy.

    Args:
        text: Text that may have encoding problems

    Returns:
        Fixed text
    """
    if FTFY_AVAILABLE and text:
        return ftfy.fix_text(text)
    return text


def remove_boilerplate(text: str) -> str:
    """
    Remove common boilerplate text patterns.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line_lower = line.lower()
        is_boilerplate = False

        for pattern in BOILERPLATE_PATTERNS:
            if re.search(pattern, line_lower):
                is_boilerplate = True
                break

        if not is_boilerplate:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def calculate_quality_score(markdown: str) -> float:
    """
    Calculate a quality score for extracted markdown content.

    Score is based on:
    - Content length (longer is generally better, up to a point)
    - Presence of structure (headings, lists)
    - Text-to-whitespace ratio
    - Absence of boilerplate

    Args:
        markdown: Extracted markdown content

    Returns:
        Quality score between 0.0 and 1.0
    """
    if not markdown or len(markdown.strip()) == 0:
        return 0.0

    score = 0.0

    # Length score (0-0.3)
    length = len(markdown)
    if length < 100:
        length_score = 0.05
    elif length < 500:
        length_score = 0.15
    elif length < 2000:
        length_score = 0.25
    else:
        length_score = 0.30
    score += length_score

    # Structure score (0-0.3)
    structure_score = 0.0
    heading_count = len(re.findall(r'^#{1,6}\s', markdown, re.MULTILINE))
    list_count = len(re.findall(r'^[\-\*]\s', markdown, re.MULTILINE))

    if heading_count > 0:
        structure_score += min(heading_count * 0.05, 0.15)
    if list_count > 0:
        structure_score += min(list_count * 0.02, 0.15)
    score += structure_score

    # Text density score (0-0.2)
    lines = [l for l in markdown.split('\n') if l.strip()]
    if lines:
        avg_line_length = sum(len(l) for l in lines) / len(lines)
        if avg_line_length > 50:
            score += 0.2
        elif avg_line_length > 30:
            score += 0.15
        elif avg_line_length > 15:
            score += 0.1
        else:
            score += 0.05

    # Readability score (0-0.2)
    word_count = len(markdown.split())
    sentence_markers = len(re.findall(r'[.!?]', markdown))
    if sentence_markers > 0 and word_count > 0:
        avg_sentence_length = word_count / sentence_markers
        if 10 <= avg_sentence_length <= 25:
            score += 0.2
        elif 5 <= avg_sentence_length <= 35:
            score += 0.1
        else:
            score += 0.05

    return min(score, 1.0)


def html_to_markdown_smart(
    html: str,
    exclude_tags: Optional[List[str]] = None,
    use_trafilatura: bool = True
) -> Dict[str, Any]:
    """
    Smart HTML to markdown conversion with quality scoring.

    Uses trafilatura for article extraction when available,
    falls back to standard markdownify method.

    Args:
        html: Raw HTML content
        exclude_tags: List of tag names to exclude
        use_trafilatura: Whether to try trafilatura first

    Returns:
        Dictionary with:
        - markdown: Extracted markdown content
        - quality_score: Quality rating 0.0-1.0
        - method: Extraction method used ("trafilatura" or "markdownify")
    """
    markdown = ""
    method = "markdownify"

    # Try trafilatura first (best for articles)
    if use_trafilatura and TRAFILATURA_AVAILABLE:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=False,
                output_format='markdown',
                favor_precision=True
            )

            if extracted and len(extracted.strip()) > 100:
                markdown = extracted
                method = "trafilatura"
                logger.debug("trafilatura_extraction_success", length=len(markdown))
        except Exception as e:
            logger.debug("trafilatura_extraction_failed", error=str(e))

    # Fall back to markdownify if trafilatura didn't work
    if not markdown:
        markdown = html_to_markdown(html, exclude_tags)
        method = "markdownify"

    # Post-process the markdown
    markdown = fix_encoding(markdown)
    markdown = remove_boilerplate(markdown)

    # Clean up excessive whitespace
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = markdown.strip()

    # Calculate quality score
    quality_score = calculate_quality_score(markdown)

    return {
        "markdown": markdown,
        "quality_score": round(quality_score, 2),
        "method": method
    }
