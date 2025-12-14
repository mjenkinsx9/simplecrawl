"""
Example: Basic scraping with SimpleCrawl API
"""

import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"


def scrape_basic():
    """Basic scraping example - get markdown and metadata."""
    print("=== Basic Scraping ===\n")
    
    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://example.com",
            "formats": ["markdown", "metadata"]
        }
    )
    
    data = response.json()
    
    if data["success"]:
        print("✓ Scrape successful!")
        print(f"\nMarkdown:\n{data['data']['markdown'][:200]}...\n")
        print(f"Title: {data['data']['metadata']['title']}")
        print(f"Language: {data['data']['metadata']['language']}")
    else:
        print(f"✗ Scrape failed: {data['error']}")


def scrape_with_actions():
    """Scraping with page actions."""
    print("\n=== Scraping with Actions ===\n")
    
    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://example.com",
            "formats": ["markdown"],
            "actions": [
                {"type": "wait", "milliseconds": 1000},
                {"type": "scroll", "direction": "down"}
            ]
        }
    )
    
    data = response.json()
    
    if data["success"]:
        print("✓ Scrape with actions successful!")
        print(f"\nContent length: {len(data['data']['markdown'])} characters")
    else:
        print(f"✗ Scrape failed: {data['error']}")


def scrape_all_formats():
    """Scraping with all formats."""
    print("\n=== Scraping All Formats ===\n")
    
    response = requests.post(
        f"{BASE_URL}/v1/scrape",
        json={
            "url": "https://example.com",
            "formats": ["markdown", "html", "links", "metadata"]
        }
    )
    
    data = response.json()
    
    if data["success"]:
        print("✓ Scrape successful!")
        print(f"\nMarkdown length: {len(data['data']['markdown'])} chars")
        print(f"HTML length: {len(data['data']['html'])} chars")
        print(f"Links found: {len(data['data']['links'])}")
        print(f"Metadata fields: {len(data['data']['metadata'])}")
    else:
        print(f"✗ Scrape failed: {data['error']}")


if __name__ == "__main__":
    scrape_basic()
    scrape_with_actions()
    scrape_all_formats()
