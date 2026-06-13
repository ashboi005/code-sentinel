import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from browser_use import Agent, Browser, ChatOpenAI

def setup_env():
    # Load environment variables from CLI tool root .env first
    cli_root = Path(__file__).resolve().parents[1]
    load_dotenv(cli_root / ".env")
    load_dotenv()  # Fallback to local process env

async def run_browser_agent(task: str, headless: bool, use_vision: bool, screenshot_path: str | None) -> dict:
    proxy_url = os.environ.get("CODESENTINEL_PROXY_URL", "http://localhost:8787/v1")
    proxy_token = os.environ.get("CODESENTINEL_PROXY_TOKEN", "replace-with-shared-demo-token")
    
    # Configure LangChain LLM to route through Elysia proxy
    llm = ChatOpenAI(
        base_url=proxy_url,
        api_key=proxy_token,
        model="codesentinel-proxy",
    )
    
    browser = Browser(headless=headless)
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision=use_vision
    )
    
    try:
        history = await agent.run()
        result_text = history.final_result()
        
        # Save screenshot if requested and session is active
        if screenshot_path:
            try:
                screenshot_file = Path(screenshot_path)
                screenshot_file.parent.mkdir(parents=True, exist_ok=True)
                await browser.take_screenshot(path=str(screenshot_file))
            except Exception as se:
                print(f"Warning: Failed to capture screenshot: {se}", file=sys.stderr)
        
        return {
            "status": "success",
            "message": result_text or "Agent task completed with no explicit final message.",
            "steps_taken": len(history.history)
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
    finally:
        await browser.close()

def main():
    setup_env()
    
    parser = argparse.ArgumentParser(description="CodeSentinel Browser Use Automation Tool")
    parser.add_argument("--task", required=True, help="Instruction/task for the browser agent")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headlessly")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run browser visually (headful)")
    parser.add_argument("--use-vision", action="store_true", default=False, help="Enable vision/screenshots for LLM reasoning")
    parser.add_argument("--screenshot", help="Optional path to save final screenshot")
    
    args = parser.parse_args()
    
    # Run async loop
    result = asyncio.run(run_browser_agent(
        task=args.task,
        headless=args.headless,
        use_vision=args.use_vision,
        screenshot_path=args.screenshot
    ))
    
    # Print JSON output to stdout for orchestration layer to parse
    print(json.dumps(result))
    
    if result["status"] == "success":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
