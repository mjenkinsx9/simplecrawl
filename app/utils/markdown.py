"""
HTML to Markdown conversion utilities.
"""

from typing import List, Optional
from bs4 import BeautifulSoup
from markdownify import markdownify as md


# Default tags to exclude from markdown conversion
DEFAULT_EXCLUDE_TAGS = [
    'script', 'style', 'nav', 'footer', 'header',
    'aside', 'iframe', 'noscript', 'svg'
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
