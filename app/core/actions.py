"""
Page actions for interacting with pages before scraping.
"""

import os
from typing import Dict, Any, List
from playwright.async_api import Page

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Safe directory for screenshot storage
SCREENSHOT_BASE_DIR = "/tmp/simplecrawl_screenshots"


async def execute_actions(page: Page, actions: List[Dict[str, Any]]) -> None:
    """
    Execute a sequence of actions on a page.

    Args:
        page: Playwright page
        actions: List of action dictionaries

    Supported actions:
    - wait: Wait for time or selector
    - click: Click an element
    - scroll: Scroll the page
    - type/write: Type text into an input (Firecrawl uses "write", we support both)
    - press: Press a key
    - screenshot: Take a screenshot
    """
    for i, action in enumerate(actions):
        action_type = action.get("type")

        try:
            if action_type == "wait":
                await execute_wait(page, action)
            elif action_type == "click":
                await execute_click(page, action)
            elif action_type == "scroll":
                await execute_scroll(page, action)
            elif action_type in ("type", "write"):  # "write" is Firecrawl's name for "type"
                await execute_type(page, action)
            elif action_type == "press":
                await execute_press(page, action)
            elif action_type == "screenshot":
                await execute_screenshot(page, action)
            else:
                logger.warning("unknown_action_type", type=action_type, index=i)
            
            logger.debug("action_executed", type=action_type, index=i)
        
        except Exception as e:
            logger.error("action_failed", type=action_type, index=i, error=str(e))
            raise Exception(f"Action {i} ({action_type}) failed: {str(e)}")


async def execute_wait(page: Page, action: Dict[str, Any]) -> None:
    """
    Wait for time or selector.
    
    Params:
    - milliseconds: Time to wait in ms
    - selector: CSS selector to wait for
    - state: Element state to wait for (visible, hidden, attached, detached)
    """
    if "milliseconds" in action:
        await page.wait_for_timeout(action["milliseconds"])
    elif "selector" in action:
        state = action.get("state", "visible")
        timeout = action.get("timeout", 30000)
        await page.wait_for_selector(action["selector"], state=state, timeout=timeout)
    else:
        # Default wait for network idle
        await page.wait_for_load_state("networkidle")


async def execute_click(page: Page, action: Dict[str, Any]) -> None:
    """
    Click an element.
    
    Params:
    - selector: CSS selector of element to click
    - button: Mouse button (left, right, middle)
    - click_count: Number of clicks (1, 2, 3)
    - delay: Delay between mousedown and mouseup in ms
    """
    selector = action.get("selector")
    if not selector:
        raise ValueError("Click action requires 'selector'")
    
    button = action.get("button", "left")
    click_count = action.get("click_count", 1)
    delay = action.get("delay", 0)
    
    await page.click(selector, button=button, click_count=click_count, delay=delay)


async def execute_scroll(page: Page, action: Dict[str, Any]) -> None:
    """
    Scroll the page.
    
    Params:
    - direction: Scroll direction (up, down, left, right)
    - amount: Scroll amount in pixels (default: viewport height/width)
    - selector: Scroll within a specific element
    """
    direction = action.get("direction", "down")
    amount = action.get("amount")
    selector = action.get("selector")
    
    if selector:
        # Scroll within element
        await page.evaluate(f"""
            (selector, direction, amount) => {{
                const element = document.querySelector(selector);
                if (element) {{
                    if (direction === 'down') {{
                        element.scrollTop += amount || element.clientHeight;
                    }} else if (direction === 'up') {{
                        element.scrollTop -= amount || element.clientHeight;
                    }} else if (direction === 'right') {{
                        element.scrollLeft += amount || element.clientWidth;
                    }} else if (direction === 'left') {{
                        element.scrollLeft -= amount || element.clientWidth;
                    }}
                }}
            }}
        """, selector, direction, amount)
    else:
        # Scroll page
        if direction == "down":
            await page.evaluate(f"window.scrollBy(0, {amount or 'window.innerHeight'})")
        elif direction == "up":
            await page.evaluate(f"window.scrollBy(0, -{amount or 'window.innerHeight'})")
        elif direction == "right":
            await page.evaluate(f"window.scrollBy({amount or 'window.innerWidth'}, 0)")
        elif direction == "left":
            await page.evaluate(f"window.scrollBy(-{amount or 'window.innerWidth'}, 0)")


async def execute_type(page: Page, action: Dict[str, Any]) -> None:
    """
    Type text into an input (also available as "write" for Firecrawl compatibility).

    Params:
    - selector: CSS selector of input element
    - text: Text to type
    - delay: Delay between key presses in ms
    - clear: Clear existing text first

    Example actions:
    - {"type": "write", "selector": "#search", "text": "hello"}
    - {"type": "type", "selector": "input[name='q']", "text": "query", "clear": true}
    """
    selector = action.get("selector")
    text = action.get("text")
    
    if not selector or text is None:
        raise ValueError("Type action requires 'selector' and 'text'")
    
    delay = action.get("delay", 0)
    clear = action.get("clear", False)
    
    if clear:
        await page.fill(selector, "")
    
    await page.type(selector, text, delay=delay)


async def execute_press(page: Page, action: Dict[str, Any]) -> None:
    """
    Press a key.

    Params:
    - key: Key to press (Enter, Tab, Escape, ArrowDown, etc.)
    - selector: Optional selector to focus first

    Example actions:
    - {"type": "press", "key": "Enter"}
    - {"type": "press", "selector": "#search", "key": "Enter"}
    """
    key = action.get("key")
    if not key:
        raise ValueError("Press action requires 'key'")
    
    selector = action.get("selector")
    if selector:
        await page.focus(selector)
    
    await page.keyboard.press(key)


async def execute_screenshot(page: Page, action: Dict[str, Any]) -> None:
    """
    Take a screenshot (for debugging).

    Params:
    - filename: Filename for the screenshot (will be saved in safe directory)
    - full_page: Capture full page (default: true)

    Note: For security, screenshots are always saved in a designated safe directory.
    User-provided paths are treated as filenames only.
    """
    # Ensure screenshot directory exists
    os.makedirs(SCREENSHOT_BASE_DIR, exist_ok=True)

    # Extract just the filename (no path traversal)
    user_path = action.get("path", "action_screenshot.png")
    filename = os.path.basename(user_path)

    # Ensure it has a valid extension
    if not filename.endswith(('.png', '.jpg', '.jpeg')):
        filename = f"{filename}.png"

    # Build safe path
    safe_path = os.path.join(SCREENSHOT_BASE_DIR, filename)

    # Double-check the resolved path is within the safe directory
    real_safe_path = os.path.realpath(safe_path)
    real_base_dir = os.path.realpath(SCREENSHOT_BASE_DIR)
    if not real_safe_path.startswith(real_base_dir + os.sep):
        logger.warning("screenshot_path_traversal_blocked", requested=user_path)
        raise ValueError("Invalid screenshot path")

    full_page = action.get("full_page", True)

    await page.screenshot(path=safe_path, full_page=full_page)
    logger.info("screenshot_saved", path=safe_path)
