"""CodeSentinel JS Analyzer Tool

Lightweight tool that fetches a web page, discovers JavaScript bundles
via <script> tags, downloads them, and runs jsbeautifier to produce
human-readable source for vulnerability scanning.

Usage:
    # Crawl a page and download + beautify all discovered JS bundles
    python apps/cli-tool/tools/js_analyzer_tool.py --url https://example.com

    # Directly download and beautify a specific JS file
    python apps/cli-tool/tools/js_analyzer_tool.py --js-url https://example.com/static/js/main.abc123.js

    # Specify a custom output directory
    python apps/cli-tool/tools/js_analyzer_tool.py --url https://example.com --output-dir ./my_analysis
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import jsbeautifier
import requests
from bs4 import BeautifulSoup


DEFAULT_OUTPUT_DIR = "js_analysis"
REQUEST_TIMEOUT = 30
# Skip tiny inline-only or tracking scripts
MIN_BUNDLE_SIZE_BYTES = 512

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


def _safe_filename(url: str) -> str:
    """Derive a filesystem-safe filename from a URL."""
    parsed = urlparse(url)
    name = parsed.path.rstrip("/").split("/")[-1] or "index.js"
    # Strip query params but keep the base name
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    if not name.endswith(".js"):
        name += ".js"
    return name


def discover_scripts(base_url: str) -> list[str]:
    """Fetch the HTML at base_url and return absolute URLs for all <script> tags."""
    resp = requests.get(base_url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    script_urls: list[str] = []

    for tag in soup.find_all("script", src=True):
        src = tag["src"]
        absolute = urljoin(base_url, src)
        script_urls.append(absolute)

    return script_urls


def download_and_beautify(js_url: str, output_dir: Path) -> dict:
    """Download a single JS file, beautify it, and save to output_dir."""
    filename = _safe_filename(js_url)
    output_path = output_dir / filename

    try:
        resp = requests.get(js_url, headers=_headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        return {
            "url": js_url,
            "status": "failed",
            "error": f"Download failed: {e}",
        }

    raw_content = resp.text
    raw_size = len(raw_content)

    if raw_size < MIN_BUNDLE_SIZE_BYTES:
        return {
            "url": js_url,
            "status": "skipped",
            "reason": f"Too small ({raw_size} bytes), likely not a main bundle",
        }

    # Beautify
    opts = jsbeautifier.default_options()
    opts.indent_size = 2
    opts.wrap_line_length = 120
    beautified = jsbeautifier.beautify(raw_content, opts)

    output_path.write_text(beautified, encoding="utf-8")

    return {
        "url": js_url,
        "status": "success",
        "file": str(output_path),
        "original_size": raw_size,
        "beautified_size": len(beautified),
        "beautified_lines": beautified.count("\n") + 1,
    }


def run_analysis(
    base_url: str | None,
    js_url: str | None,
    output_dir: str,
) -> dict:
    """Main entry point: discover and/or download+beautify JS bundles."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    if js_url:
        # Direct single-file mode
        result = download_and_beautify(js_url, out)
        results.append(result)
    elif base_url:
        # Discovery mode: fetch HTML and find all scripts
        try:
            script_urls = discover_scripts(base_url)
        except requests.RequestException as e:
            return {
                "status": "failed",
                "error": f"Failed to fetch page: {e}",
                "files": [],
            }

        if not script_urls:
            return {
                "status": "warning",
                "message": "No <script src='...'> tags found on the page.",
                "files": [],
            }

        for url in script_urls:
            result = download_and_beautify(url, out)
            results.append(result)
    else:
        return {"status": "failed", "error": "Must provide --url or --js-url"}

    successful = [r for r in results if r.get("status") == "success"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    failed = [r for r in results if r.get("status") == "failed"]

    return {
        "status": "success" if successful else "warning",
        "summary": (
            f"Processed {len(results)} script(s): "
            f"{len(successful)} beautified, {len(skipped)} skipped, {len(failed)} failed"
        ),
        "output_directory": str(out),
        "files": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CodeSentinel JS Analyzer — download & beautify JS bundles from a website"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--url",
        help="Base URL of the website to crawl for JS bundles",
    )
    group.add_argument(
        "--js-url",
        help="Direct URL to a specific JS file to download and beautify",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save beautified JS files (default: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args()

    result = run_analysis(
        base_url=args.url,
        js_url=args.js_url,
        output_dir=args.output_dir,
    )

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
