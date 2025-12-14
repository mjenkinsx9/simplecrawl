#!/usr/bin/env python3
"""
Interactive SimpleCrawl CLI

Usage:
    python scrape.py https://example.com
    python scrape.py  # prompts for URL
"""

import sys
import json
import requests
from pathlib import Path

API_BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent / "data"
MEDIA_DIR = Path(__file__).parent / "media" / "scrape"


def analyze_url(url: str) -> dict:
    """Analyze URL and get tag suggestions."""
    print(f"\nAnalyzing {url}...")
    resp = requests.post(
        f"{API_BASE}/v1/analyze",
        json={"url": url, "timeout": 30000},
        timeout=60
    )
    return resp.json()


def scrape_url(url: str, exclude_tags: list, include_images: bool) -> dict:
    """Scrape URL with given options."""
    formats = ["markdown", "metadata"]
    if include_images:
        formats.append("media")

    print(f"\nScraping {url}...")
    print(f"  Formats: {formats}")
    print(f"  Exclude tags: {exclude_tags}")

    resp = requests.post(
        f"{API_BASE}/v1/scrape",
        json={
            "url": url,
            "formats": formats,
            "exclude_tags": exclude_tags,
            "timeout": 90000
        },
        timeout=120
    )
    return resp.json()


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {hint}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


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


def main():
    # Get URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter URL to scrape: ").strip()

    if not url.startswith("http"):
        url = "https://" + url

    # Analyze first
    analysis = analyze_url(url)

    if not analysis.get("success"):
        print(f"Analysis failed: {analysis.get('error')}")
        sys.exit(1)

    print(f"\nPage: {analysis.get('title', 'Unknown')}")
    print(f"Total tags found: {analysis.get('total_tags', 0)}")

    # Show suggested exclude tags
    suggested = analysis.get("suggested_exclude_tags", [])
    print(f"\nSuggested exclude tags: {suggested}")

    # Prompt for exclude tags
    print("\n" + "="*50)
    exclude_choice = prompt_choice(
        "Which tags do you want to EXCLUDE from the content?",
        [
            f"Suggested: {suggested}",
            "Suggested + images: " + str(suggested + ["img", "picture", "svg"]),
            "Minimal: ['script', 'style']",
            "None (keep everything)",
            "Custom (enter your own)"
        ],
        default=1  # Suggested + images is best for LLM
    )

    if exclude_choice == 0:
        exclude_tags = suggested
    elif exclude_choice == 1:
        exclude_tags = suggested + ["img", "picture", "svg"]
    elif exclude_choice == 2:
        exclude_tags = ["script", "style"]
    elif exclude_choice == 3:
        exclude_tags = []
    else:
        custom = input("Enter tags separated by commas: ").strip()
        exclude_tags = [t.strip() for t in custom.split(",") if t.strip()]

    # Prompt for images
    print("\n" + "="*50)
    include_images = prompt_yes_no(
        "Download images to media/scrape/?",
        default=True
    )

    # Confirm
    print("\n" + "="*50)
    print("SUMMARY:")
    print(f"  URL: {url}")
    print(f"  Exclude tags: {exclude_tags}")
    print(f"  Download images: {'Yes' if include_images else 'No'}")

    if not prompt_yes_no("\nProceed with scrape?", default=True):
        print("Cancelled.")
        sys.exit(0)

    # Scrape
    result = scrape_url(url, exclude_tags, include_images)

    if not result.get("success"):
        print(f"Scrape failed: {result.get('error')}")
        sys.exit(1)

    data = result.get("data", {})

    # Save markdown
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Generate filename from URL
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace("www.", "").replace(".", "_")
    md_file = DATA_DIR / f"{domain}.md"
    json_file = DATA_DIR / f"{domain}.json"

    # Save markdown
    markdown = data.get("markdown", "")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    # Save full JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Summary
    print("\n" + "="*50)
    print("COMPLETE!")
    print(f"\n  Markdown saved: {md_file}")
    print(f"    Size: {len(markdown):,} chars (~{len(markdown)//4:,} tokens)")
    print(f"\n  Full JSON: {json_file}")

    if include_images:
        media = data.get("media", [])
        total_size = sum(m.get("size", 0) for m in media)
        print(f"\n  Images downloaded: {len(media)} files")
        print(f"    Location: {MEDIA_DIR}/")
        print(f"    Total size: {total_size // 1024:,} KB")

    # Quality info
    quality = data.get("quality_score")
    if quality:
        print(f"\n  Quality score: {quality:.2f}")

    print("\n" + "="*50)
    print(f"Ready to use with LLM: {md_file}")


if __name__ == "__main__":
    main()
