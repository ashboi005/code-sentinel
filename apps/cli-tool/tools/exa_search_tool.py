"""CodeSentinel Exa Search Tool

General-purpose web search tool routing through the CodeSentinel proxy backend.
The agent can use this to look up vulnerabilities, Docker commands,
framework documentation, OSINT on targets, etc. without leaking the Exa API Key.

Usage:
    python apps/cli-tool/tools/exa_search_tool.py --query "Express.js SQL injection CVE 2024"
    python apps/cli-tool/tools/exa_search_tool.py --query "Docker run Semgrep container" --num-results 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


DEFAULT_NUM_RESULTS = 5


def setup_env() -> None:
    cli_root = Path(__file__).resolve().parents[1]
    load_dotenv(cli_root / ".env")
    load_dotenv()


def search(query: str, num_results: int) -> dict:
    proxy_url = os.environ.get("CODESENTINEL_PROXY_URL", "http://localhost:8787/v1").rstrip("/")
    proxy_token = os.environ.get("CODESENTINEL_PROXY_TOKEN", "").strip()

    if not proxy_token:
        return {
            "status": "failed",
            "error": "CODESENTINEL_PROXY_TOKEN environment variable is not set.",
        }

    if proxy_url.endswith("/v1"):
        search_endpoint = f"{proxy_url}/search"
    else:
        search_endpoint = f"{proxy_url}/v1/search"
    headers = {
        "Authorization": f"Bearer {proxy_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "numResults": num_results,
    }

    try:
        response = requests.post(search_endpoint, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            return {
                "status": "failed",
                "error": f"Proxy backend returned error {response.status_code}",
                "details": error_detail,
            }

        return response.json()
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Failed to connect to proxy backend search endpoint: {e}",
        }


def main() -> int:
    setup_env()

    parser = argparse.ArgumentParser(
        description="CodeSentinel Exa Search — proxy-routed web search for vulnerability research"
    )
    parser.add_argument(
        "--query",
        required=True,
        help="The search query",
    )
    parser.add_argument(
        "--num-results",
        type=int,
        default=DEFAULT_NUM_RESULTS,
        help=f"Number of results to return (default: {DEFAULT_NUM_RESULTS})",
    )

    args = parser.parse_args()
    result = search(args.query, args.num_results)

    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
