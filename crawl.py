#!/usr/bin/env python3
"""
Interactive SimpleCrawl Deep Crawler

Crawls entire websites following links to subpages.

Usage:
    python crawl.py https://example.com
    python crawl.py  # prompts for URL
"""

import sys
import json
import time
import requests
from pathlib import Path
from urllib.parse import urlparse

API_BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent / "data"
MEDIA_DIR = Path(__file__).parent / "media" / "crawl"


def analyze_url(url: str) -> dict:
    """Analyze URL and get tag suggestions."""
    print(f"\nAnalyzing {url}...")
    resp = requests.post(
        f"{API_BASE}/v1/analyze",
        json={"url": url, "timeout": 30000},
        timeout=60
    )
    return resp.json()


def start_crawl(url: str, depth: int, limit: int, exclude_tags: list, include_images: bool) -> dict:
    """Start a crawl job."""
    formats = ["markdown", "metadata", "links"]  # links needed for crawling
    if include_images:
        formats.append("media")

    resp = requests.post(
        f"{API_BASE}/v1/crawl",
        json={
            "url": url,
            "depth": depth,
            "limit": limit,
            "scrape_options": {
                "formats": formats,
                "exclude_tags": exclude_tags
            }
        },
        timeout=30
    )
    return resp.json()


def check_status(job_id: str) -> dict:
    """Check crawl job status."""
    resp = requests.get(f"{API_BASE}/v1/crawl/{job_id}", timeout=30)
    return resp.json()


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {hint}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_int(question: str, default: int, min_val: int = 1, max_val: int = 1000) -> int:
    """Prompt for integer."""
    answer = input(f"{question} (default {default}): ").strip()
    if not answer:
        return default
    try:
        val = int(answer)
        return max(min_val, min(max_val, val))
    except ValueError:
        return default


def prompt_choice(question: str, options: list, default: int = 0) -> int:
    """Prompt for multiple choice."""
    print(f"\n{question}")
    for i, opt in enumerate(options):
        marker = "*" if i == default else " "
        print(f"  {marker} [{i+1}] {opt}")

    answer = input(f"Choice [1-{len(options)}] (default {default+1}): ").strip()
    if not answer:
        return default
    try:
        choice = int(answer) - 1
        if 0 <= choice < len(options):
            return choice
    except ValueError:
        pass
    return default


def save_results(domain: str, pages: list, include_images: bool):
    """Save crawl results to files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Create domain folder
    domain_dir = DATA_DIR / domain
    domain_dir.mkdir(exist_ok=True)

    # Save individual pages as markdown
    for i, page in enumerate(pages):
        url = page.get("url", "")
        markdown = page.get("markdown", "")

        if markdown:
            # Create filename from URL path
            parsed = urlparse(url)
            path = parsed.path.strip("/").replace("/", "_") or "index"
            path = path[:50]  # Limit length
            md_file = domain_dir / f"{path}.md"

            # Add URL header to markdown
            content = f"<!-- Source: {url} -->\n\n{markdown}"

            with open(md_file, "w", encoding="utf-8") as f:
                f.write(content)

    # Save combined markdown (all pages)
    combined_file = domain_dir / "_all_pages.md"
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write(f"# {domain} - Complete Crawl\n\n")
        f.write(f"Total pages: {len(pages)}\n\n")
        f.write("---\n\n")

        for page in pages:
            url = page.get("url", "")
            markdown = page.get("markdown", "")
            depth = page.get("depth", 0)

            f.write(f"## [{url}]({url})\n")
            f.write(f"*Depth: {depth}*\n\n")
            f.write(markdown or "*No content*")
            f.write("\n\n---\n\n")

    # Save full JSON
    json_file = domain_dir / "_crawl_data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)

    return domain_dir, combined_file


def main():
    print("=" * 60)
    print("  SimpleCrawl - Deep Website Crawler")
    print("=" * 60)

    # Get URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("\nEnter starting URL: ").strip()

    if not url.startswith("http"):
        url = "https://" + url

    # Extract domain
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    # Analyze first
    analysis = analyze_url(url)

    if not analysis.get("success"):
        print(f"Analysis failed: {analysis.get('error')}")
        sys.exit(1)

    print(f"\nSite: {analysis.get('title', domain)}")

    # Get suggested exclude tags
    suggested = analysis.get("suggested_exclude_tags", [])
    print(f"Suggested exclude tags: {suggested}")

    # Prompt for crawl settings
    print("\n" + "=" * 60)
    print("CRAWL SETTINGS")
    print("=" * 60)

    depth = prompt_int(
        "\nMax depth (1=homepage only, 2=+subpages, 3=+sub-subpages)",
        default=3,
        min_val=1,
        max_val=50
    )

    limit = prompt_int(
        "Max pages to crawl",
        default=50,
        min_val=1,
        max_val=5000
    )

    # Prompt for exclude tags
    print("\n" + "=" * 60)
    exclude_choice = prompt_choice(
        "Which tags do you want to EXCLUDE from content?",
        [
            f"Suggested: {suggested}",
            "Suggested + images (best for LLM): " + str(suggested + ["img", "picture", "svg"]),
            "Minimal: ['script', 'style']",
            "None (keep everything)"
        ],
        default=1
    )

    if exclude_choice == 0:
        exclude_tags = suggested
    elif exclude_choice == 1:
        exclude_tags = suggested + ["img", "picture", "svg"]
    elif exclude_choice == 2:
        exclude_tags = ["script", "style"]
    else:
        exclude_tags = []

    # Prompt for images
    print("\n" + "=" * 60)
    include_images = prompt_yes_no(
        "Download images from all pages?",
        default=False  # Default no for crawls (can be a lot!)
    )

    # Confirm
    print("\n" + "=" * 60)
    print("CRAWL SUMMARY")
    print("=" * 60)
    print(f"  Starting URL: {url}")
    print(f"  Domain: {domain}")
    print(f"  Max depth: {depth}")
    print(f"  Max pages: {limit}")
    print(f"  Exclude tags: {exclude_tags}")
    print(f"  Download images: {'Yes' if include_images else 'No'}")

    if not prompt_yes_no("\nStart crawl?", default=True):
        print("Cancelled.")
        sys.exit(0)

    # Start crawl
    print("\n" + "=" * 60)
    print("CRAWLING...")
    print("=" * 60)

    result = start_crawl(url, depth, limit, exclude_tags, include_images)

    if not result.get("success"):
        print(f"Failed to start crawl: {result.get('error')}")
        sys.exit(1)

    job_id = result.get("id")
    print(f"\nCrawl job started: {job_id}")
    print("Polling for progress...\n")

    # Poll for completion
    last_completed = 0
    while True:
        status = check_status(job_id)
        job_status = status.get("status", "unknown")
        completed = status.get("completed", 0)
        total = status.get("total", 0)
        failed = status.get("failed", 0)

        if completed > last_completed:
            print(f"  Progress: {completed}/{total} pages crawled" +
                  (f" ({failed} failed)" if failed else ""))
            last_completed = completed

        if job_status in ("completed", "failed"):
            break

        time.sleep(2)

    if job_status == "failed":
        print(f"\nCrawl failed: {status.get('error')}")
        sys.exit(1)

    # Get results
    pages = status.get("data", [])
    print(f"\n  Crawl complete! {len(pages)} pages scraped.")

    # Save results
    print("\n" + "=" * 60)
    print("SAVING RESULTS...")
    print("=" * 60)

    domain_dir, combined_file = save_results(domain, pages, include_images)

    # Summary
    total_chars = sum(len(p.get("markdown", "")) for p in pages)
    total_tokens = total_chars // 4

    print(f"\n  Saved to: {domain_dir}/")
    print(f"  Individual pages: {len(pages)} .md files")
    print(f"  Combined file: _all_pages.md")
    print(f"  Full data: _crawl_data.json")
    print(f"\n  Total content: {total_chars:,} chars (~{total_tokens:,} tokens)")

    if include_images:
        total_images = sum(len(p.get("media", [])) for p in pages)
        print(f"  Total images: {total_images}")

    print("\n" + "=" * 60)
    print(f"Ready for LLM: {combined_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
