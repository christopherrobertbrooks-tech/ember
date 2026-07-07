import os
import time
import webbrowser
from playwright.sync_api import sync_playwright
from tools.permission_gate import describe_permission_error, guard
from tools.ui_tabs import focus_tab

def navigate_and_screenshot(url: str) -> str:
    """
    Navigates to a specific URL in a headless browser and takes a full-page screenshot.
    This is useful for visually verifying a webpage.
    
    Args:
        url: The URL to navigate to (e.g., https://example.com)
        
    Returns:
        A string indicating the path where the screenshot was saved, or an error message.
    """
    print(f"Starting browser verification for: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
            time.sleep(2) # Give it a little extra time to render dynamic content
            
            os.makedirs("companion_images", exist_ok=True)
            screenshot_path = os.path.abspath(f"companion_images/browser_verify_{int(time.time())}.png")
            page.screenshot(path=screenshot_path, full_page=True)
            
            return f"Verification complete. Screenshot saved to {screenshot_path}"
        except Exception as e:
            return f"Failed to verify URL: {url}\nError: {e}"
        finally:
            browser.close()

def extract_text_from_page(url: str) -> str:
    """
    Navigates to a URL and extracts the main text content of the page.
    This is useful for reading articles, documentation, or searching for specific information on a page.
    
    Args:
        url: The URL to read.
        
    Returns:
        The text content of the page, or an error message.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
            text_content = page.evaluate("document.body.innerText")
            # Limit to a reasonable size so we don't blow up the context window
            return text_content[:5000] + ("..." if len(text_content) > 5000 else "")
        except Exception as e:
            return f"Failed to extract text from URL: {url}\nError: {e}"
        finally:
            browser.close()

def open_in_browser(url: str) -> str:
    """
    Opens a URL in the user's default visible desktop browser (Chrome, Edge, etc.).
    This is useful for when the user wants to watch a video, see a website, or interact with a webpage directly.
    
    Args:
        url: The URL to open.
        
    Returns:
        A success message indicating the browser was opened.
    """
    import requests
    try:
        guard("browser_open", "open_in_browser", payload={"url": url})
        focus_tab("browser", url=url)
        try:
            res = requests.post("http://127.0.0.1:8000/api/ui_action", json={"action": "open_browser", "url": url}, timeout=2)
            if res.status_code == 200:
                clients = res.json().get("clients_messaged", 0)
                if clients > 0:
                    return f"Successfully sent command to {clients} connected client(s) to open url: {url}"
                else:
                    pass # Fall back to local if no clients are connected
        except Exception as e:
            pass # Fall back to local
        
        import webbrowser
        webbrowser.open(url)
        return f"Successfully opened {url} in the browser."
    except Exception as e:
        if "Permission" in describe_permission_error(e):
            return describe_permission_error(e)
        import webbrowser
        webbrowser.open(url)
        return f"Successfully opened {url} in the browser."
    except Exception as e2:
        return f"Failed to open browser: {e2}"
