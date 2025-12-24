#!/usr/bin/env python3
"""
Reddit Personal Finance Wiki Crawler

Crawls all sub-pages from r/personalfinance wiki index
"""

import sys
import json
import time
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote

API_BASE = "http://localhost:8000"
OUTPUT_DIR = Path(__file__).parent / "output" / "reddit_personalfinance"

# Reddit wiki URL
WIKI_URL = "https://www.reddit.com/r/personalfinance/wiki/index/"

def start_crawl() -> dict:
    """Start the wiki crawl job."""
    payload = {
        "url": WIKI_URL,
        "depth": 5,  # Deep enough to get all wiki subpages
        "limit": 200,  # Max pages
        "scrape_options": {
            "formats": ["markdown", "metadata", "links"],  # No media
            "exclude_tags": [
                "script", "style", "nav", "footer", "header",
                "img", "picture", "svg",  # Exclude images
                "aside", "noscript", "iframe"
            ],
            "timeout": 30000,
        }
    }

    print(f"Starting crawl of {WIKI_URL}")
    print(f"  Max depth: {payload['depth']}")
    print(f"  Max pages: {payload['limit']}")
    print(f"  No images: True\n")

    try:
        resp = requests.post(
            f"{API_BASE}/v1/crawl",
            json=payload,
            timeout=120  # 2 minute timeout for initial request
        )
        resp.raise_for_status()
        return resp.json()
    except requests.Timeout:
        print("Request timed out. Server may be processing...")
        # Try to get recent jobs
        try:
            jobs_resp = requests.get(f"{API_BASE}/v1/crawl", timeout=10)
            jobs = jobs_resp.json()
            if jobs and isinstance(jobs, list):
                latest = jobs[0]
                if latest.get('url') == WIKI_URL:
                    print(f"Found existing job: {latest.get('id')}")
                    return latest
        except:
            pass
        raise


def check_status(job_id: str) -> dict:
    """Check crawl job status."""
    resp = requests.get(f"{API_BASE}/v1/crawl/{job_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def url_to_filename(url: str) -> str:
    """Convert URL to a safe filename."""
    parsed = urlparse(url)
    path = unquote(parsed.path).strip("/")

    if not path or path == "r/personalfinance/wiki/index":
        return "index"

    # Extract the last part of the wiki path
    if "/wiki/" in path:
        wiki_part = path.split("/wiki/")[-1]
        filename = wiki_part.replace("/", "_")
    else:
        filename = path.replace("/", "_")

    # Limit length and clean up
    filename = filename[:100].strip("_")
    return filename or "page"


def save_results(pages: list):
    """Save crawl results."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving {len(pages)} pages to {OUTPUT_DIR}/")

    # Save individual pages as markdown
    saved_count = 0
    for page in pages:
        url = page.get("url", "")
        markdown = page.get("markdown", "")

        if markdown and len(markdown) > 100:  # Skip near-empty pages
            filename = url_to_filename(url)
            md_file = OUTPUT_DIR / f"{filename}.md"

            # Add source URL as header
            title = page.get("metadata", {}).get("title", "")
            content = f"# {title}\n\n<!-- Source: {url} -->\n\n{markdown}"

            with open(md_file, "w", encoding="utf-8") as f:
                f.write(content)
            saved_count += 1

    print(f"  ✓ Saved {saved_count} individual page files")

    # Save combined markdown
    combined_file = OUTPUT_DIR / "all_pages.md"
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write("# r/personalfinance Wiki - Complete Crawl\n\n")
        f.write(f"Source: {WIKI_URL}\n")
        f.write(f"Total pages: {len(pages)}\n\n")
        f.write("---\n\n")

        for page in pages:
            url = page.get("url", "")
            markdown = page.get("markdown", "")
            depth = page.get("depth", 0)

            if markdown and len(markdown) > 100:
                title = page.get("metadata", {}).get("title", url)
                f.write(f"## {title}\n")
                f.write(f"*URL: {url} | Depth: {depth}*\n\n")
                f.write(markdown)
                f.write("\n\n---\n\n")

    print(f"  ✓ Combined file: all_pages.md")

    # Save JSON data
    json_file = OUTPUT_DIR / "crawl_data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)
    print(f"  ✓ JSON data: crawl_data.json")

    return combined_file


def main():
    print("=" * 60)
    print("  r/personalfinance Wiki Crawler")
    print("=" * 60)
    print()

    # Start crawl
    try:
        result = start_crawl()
    except Exception as e:
        print(f"Failed to start crawl: {e}")
        print("\nMake sure the API server is running:")
        print("  Check: http://localhost:8000/health")
        sys.exit(1)

    if not result.get("success"):
        print(f"Failed to start crawl: {result.get('error')}")
        sys.exit(1)

    job_id = result.get("id")
    print(f"Crawl job started: {job_id}")
    print("=" * 60)
    print()

    # Poll for completion
    last_completed = 0
    start_time = time.time()

    while True:
        try:
            status = check_status(job_id)
        except requests.RequestException as e:
            print(f"  Connection error: {e}, retrying...")
            time.sleep(5)
            continue

        job_status = status.get("status", "unknown")
        completed = status.get("completed", 0)
        total = status.get("total", 0)
        failed = status.get("failed", 0)

        if completed > last_completed or (completed == 0 and total > 0):
            elapsed = int(time.time() - start_time)
            rate = completed / elapsed if elapsed > 0 else 0
            print(f"  [{elapsed:>4}s] Progress: {completed}/{total} pages " +
                  f"({rate:.1f}/s)" +
                  (f" | {failed} failed" if failed else ""))
            last_completed = completed

        if job_status == "completed":
            break
        elif job_status == "failed":
            print(f"\nCrawl failed: {status.get('error')}")
            sys.exit(1)

        time.sleep(3)

    # Get results
    pages = status.get("data", [])
    elapsed = int(time.time() - start_time)

    print()
    print("=" * 60)
    print(f"CRAWL COMPLETE!")
    print("=" * 60)
    print(f"  Pages scraped: {len(pages)}")
    print(f"  Failed: {status.get('failed', 0)}")
    print(f"  Time: {elapsed}s ({elapsed//60}m {elapsed%60}s)")
    print()

    # Save results
    combined_file = save_results(pages)

    # Summary
    total_chars = sum(len(p.get("markdown", "") or "") for p in pages)
    total_tokens = total_chars // 4  # Rough estimate

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total content: {total_chars:,} chars (~{total_tokens:,} tokens)")
    print(f"  Output: {OUTPUT_DIR}/")
    print(f"  Combined: {combined_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
