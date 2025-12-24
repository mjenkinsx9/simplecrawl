#!/usr/bin/env python3
"""
Ashes of Creation Wiki Crawler

Deep crawl of https://ashesofcreation.wiki/ with Cloudflare bypass.

Usage:
    python crawl_ashes.py
    python crawl_ashes.py --limit 500  # Custom page limit
    python crawl_ashes.py --no-images  # Skip image downloads
"""

import sys
import os
import json
import time
import shutil
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote

API_BASE = "http://localhost:8000"

# Google Drive output paths (WSL paths)
GDRIVE_BASE = Path("/mnt/g/My Drive/Ashes of Creation/ashesofcreation.wiki scrape")
PAGES_DIR = GDRIVE_BASE / "Pages"
IMAGES_DIR = GDRIVE_BASE / "Images"

# Local fallback if Google Drive not mounted
LOCAL_PAGES_DIR = Path(__file__).parent / "data" / "ashesofcreation"
LOCAL_MEDIA_DIR = Path(__file__).parent / "media" / "scrape"  # Where Docker saves images

# Wiki URL
WIKI_URL = "https://ashesofcreation.wiki/"

# MediaWiki namespaces to exclude (common wiki junk pages)
EXCLUDE_PATTERNS = [
    "*/Special:*",
    "*/User:*",
    "*/User_talk:*",
    "*/Talk:*",
    "*/File:*",
    "*/Template:*",
    "*/Template_talk:*",
    "*/Category:*",
    "*/Help:*",
    "*/MediaWiki:*",
    "*action=edit*",
    "*action=history*",
    "*oldid=*",
    "*diff=*",
    "*printable=*",
    "*mobileaction=*",
    "*/index.php?*",
]

# Tags to exclude from content (wiki navigation/boilerplate)
EXCLUDE_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "noscript", "iframe",
    # Wiki-specific elements
    ".mw-editsection",      # [edit] links
    ".navbox",              # Navigation boxes
    ".toc",                 # Table of contents (often not needed)
    ".mw-jump-link",        # Skip-to links
    ".printfooter",         # Print footer
    ".catlinks",            # Category links at bottom
    "#mw-navigation",       # Left sidebar
    "#footer",              # Footer
    ".noprint",             # Non-printable elements
]


def start_crawl(limit: int, include_images: bool) -> dict:
    """Start the wiki crawl job."""
    formats = ["markdown", "metadata", "links"]
    if include_images:
        formats.append("media")

    payload = {
        "url": WIKI_URL,
        "depth": 50,  # Deep crawl
        "limit": limit,
        "exclude_patterns": EXCLUDE_PATTERNS,
        "scrape_options": {
            "formats": formats,
            "exclude_tags": EXCLUDE_TAGS,
            "timeout": 60000,  # 60s timeout for Cloudflare pages
        }
    }

    print(f"Starting crawl with limit={limit}, images={include_images}")
    print(f"Exclude patterns: {len(EXCLUDE_PATTERNS)} wiki namespaces")

    resp = requests.post(
        f"{API_BASE}/v1/crawl",
        json=payload,
        timeout=30
    )
    return resp.json()


def check_status(job_id: str) -> dict:
    """Check crawl job status."""
    resp = requests.get(f"{API_BASE}/v1/crawl/{job_id}", timeout=30)
    return resp.json()


def url_to_filename(url: str) -> str:
    """Convert URL to a safe filename."""
    parsed = urlparse(url)
    path = unquote(parsed.path).strip("/")

    if not path:
        return "Main_Page"

    # Replace path separators and unsafe chars
    filename = path.replace("/", "_").replace(":", "_")
    # Limit length
    filename = filename[:100]
    return filename


def check_gdrive_available() -> bool:
    """Check if Google Drive is mounted."""
    return Path("/mnt/g").exists() and os.access("/mnt/g", os.W_OK)


def save_results(pages: list, include_images: bool):
    """Save crawl results to Google Drive (or local fallback)."""

    # Determine output directories
    if check_gdrive_available():
        pages_dir = PAGES_DIR
        images_dir = IMAGES_DIR
        print(f"\n  Google Drive detected at /mnt/g")
    else:
        pages_dir = LOCAL_PAGES_DIR
        images_dir = LOCAL_MEDIA_DIR
        print(f"\n  Google Drive not mounted - using local folders")
        print(f"  (Mount G: drive or copy files later)")

    pages_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving {len(pages)} pages to {pages_dir}/")

    # Save individual pages as markdown
    saved_count = 0
    for page in pages:
        url = page.get("url", "")
        markdown = page.get("markdown", "")

        if markdown and len(markdown) > 100:  # Skip near-empty pages
            filename = url_to_filename(url)
            md_file = pages_dir / f"{filename}.md"

            # Add source URL as header
            content = f"<!-- Source: {url} -->\n\n{markdown}"

            with open(md_file, "w", encoding="utf-8") as f:
                f.write(content)
            saved_count += 1

    print(f"  Saved {saved_count} individual page files")

    # Save combined markdown
    combined_file = pages_dir / "_all_pages.md"
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write("# Ashes of Creation Wiki - Complete Crawl\n\n")
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

    print(f"  Combined file: _all_pages.md")

    # Save JSON data
    json_file = pages_dir / "_crawl_data.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)
    print(f"  JSON data: _crawl_data.json")

    # Handle images
    if include_images:
        total_images = sum(len(p.get("media", [])) for p in pages)
        print(f"\n  Total images extracted: {total_images}")

        # Copy images from Docker's media folder to target
        if LOCAL_MEDIA_DIR.exists() and check_gdrive_available():
            images_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for img_file in LOCAL_MEDIA_DIR.glob("*"):
                if img_file.is_file():
                    dest = images_dir / img_file.name
                    shutil.copy2(img_file, dest)
                    copied += 1
            print(f"  Copied {copied} images to {images_dir}/")
        else:
            print(f"  Images location: {LOCAL_MEDIA_DIR}/")

    return combined_file


def main():
    parser = argparse.ArgumentParser(description="Crawl Ashes of Creation Wiki")
    parser.add_argument("--limit", type=int, default=1500,
                        help="Maximum pages to crawl (default: 1500)")
    parser.add_argument("--no-images", action="store_true",
                        help="Skip downloading images")
    args = parser.parse_args()

    include_images = not args.no_images
    limit = args.limit

    print("=" * 60)
    print("  Ashes of Creation Wiki Crawler")
    print("  (with Cloudflare bypass via FlareSolverr)")
    print("=" * 60)
    print(f"\n  Target: {WIKI_URL}")
    print(f"  Max pages: {limit}")
    print(f"  Download images: {'Yes' if include_images else 'No'}")

    if check_gdrive_available():
        print(f"  Pages output: {PAGES_DIR}/")
        if include_images:
            print(f"  Images output: {IMAGES_DIR}/")
    else:
        print(f"  Pages output: {LOCAL_PAGES_DIR}/ (G: drive not mounted)")
        if include_images:
            print(f"  Images output: {LOCAL_MEDIA_DIR}/ (G: drive not mounted)")
        print("\n  To mount Google Drive in WSL, ensure Google Drive")
        print("  for Desktop is running and G: is your drive letter.")
    print()

    # Start crawl
    result = start_crawl(limit, include_images)

    if not result.get("success"):
        print(f"Failed to start crawl: {result.get('error')}")
        print("\nMake sure Docker services are running:")
        print("  docker-compose up -d")
        sys.exit(1)

    job_id = result.get("id")
    print(f"Crawl job started: {job_id}")
    print("=" * 60)
    print("CRAWLING (this may take a while for 1000+ pages)...")
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

        if completed > last_completed or total > 0:
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
    print(f"  Time elapsed: {elapsed}s ({elapsed//60}m {elapsed%60}s)")
    print()

    # Save results
    combined_file = save_results(pages, include_images)

    # Summary
    total_chars = sum(len(p.get("markdown", "") or "") for p in pages)
    total_tokens = total_chars // 4  # Rough token estimate

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total content: {total_chars:,} chars (~{total_tokens:,} tokens)")
    print(f"  Ready for LLM: {combined_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
