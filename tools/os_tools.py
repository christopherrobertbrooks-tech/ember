import subprocess
import time
import re
import json
import os
import base64
from PIL import ImageGrab
from tools.permission_gate import describe_permission_error, guard
from tools.ui_tabs import focus_tab

# Read LM Studio config once at import time; can be overridden by env var
def _get_lm_studio_config():
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ember_config.json")
        with open(config_path, "r") as f:
            cfg = json.load(f)
        url = cfg.get("lm_studio_endpoint", os.getenv("LM_STUDIO_URL", "http://100.100.150.74:1234/v1"))
        model = cfg.get("model", "gemma-4b-it")
        return url, model
    except Exception:
        return os.getenv("LM_STUDIO_URL", "http://100.100.150.74:1234/v1"), "gemma-4b-it"

def take_screenshot() -> str:
    """
    Takes a screenshot of the user's client monitor and sends it to LM Studio for vision analysis.
    Use this when the user asks you to look at their screen, read something on their screen, or debug an error they are seeing.
    
    Returns:
        A JSON string with keys 'description' (vision analysis) and 'path' (saved image path).
    """
    import requests

    try:
        guard("screenshot", "take_screenshot", payload={})
        os.makedirs("companion_images", exist_ok=True)
        filepath = os.path.abspath("companion_images/client_screenshot.png")

        # Remove stale screenshot so we can detect when a new one arrives
        if os.path.exists(filepath):
            os.remove(filepath)

        target_path = None

        # Step 1: Ask the companion client to capture its screen and POST it back
        try:
            res = requests.post(
                "http://127.0.0.1:8000/api/ui_action",
                json={"action": "take_screenshot"},
                timeout=2
            )
            if res.status_code == 200 and res.json().get("clients_messaged", 0) > 0:
                # Wait up to 8 seconds for the client screenshot to land
                for _ in range(80):
                    if os.path.exists(filepath):
                        time.sleep(0.3)  # Let the file finish writing
                        target_path = filepath
                        break
                    time.sleep(0.1)
        except Exception:
            pass

        # Step 2: Fallback — grab the host screen if client didn't respond
        if not target_path:
            screenshot = ImageGrab.grab()
            fallback_path = os.path.abspath(f"companion_images/screenshot_{int(time.time())}.png")
            screenshot.save(fallback_path)
            target_path = fallback_path

        # Step 3: Send the image to LM Studio for vision analysis
        lm_url, lm_model = _get_lm_studio_config()
        try:
            with open(target_path, "rb") as img_file:
                b64_img = base64.b64encode(img_file.read()).decode("utf-8")

            vision_payload = {
                "model": lm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please describe exactly what you see in this screen capture in detail. Include any open windows, text, icons, and overall context."
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                            }
                        ]
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 512
            }

            vision_res = requests.post(
                f"{lm_url}/chat/completions",
                json=vision_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            vision_res.raise_for_status()
            vision_data = vision_res.json()
            description = vision_data["choices"][0]["message"]["content"]
            result = json.dumps({"description": description, "path": target_path})
            return f"SCREENSHOT TAKEN. Vision Subsystem reports:\n{result}"

        except Exception as e:
            # Vision call failed — return path only so the LLM can still reference the image
            result = json.dumps({"description": f"Vision analysis unavailable: {e}", "path": target_path})
            return f"SCREENSHOT_PATH:{target_path}\nWarning: Vision call to LM Studio failed: {e}"

    except Exception as e:
        return f"Failed to take screenshot: {describe_permission_error(e)}"


def run_os_command(command: str) -> str:
    """
    Executes a PowerShell or Command Prompt command on the user's PC.
    This gives you full access to the user's local operating system to open files, check system status, or run scripts.
    
    Args:
        command: The shell command to execute.
        
    Returns:
        The output (stdout/stderr) of the command, or an error message.
    """
    try:
        guard("shell", "run_os_command", payload={"command": command})
        focus_tab("terminal")
        process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        
        cmd_result = ""
        if stdout:
            cmd_result += f"Output:\n{stdout[:1500]}\n" 
        if stderr:
            cmd_result += f"Errors:\n{stderr[:500]}\n"
        if not cmd_result:
            cmd_result = "Command executed successfully with no output."
            
        return cmd_result
    except Exception as e:
        return f"Failed to execute OS Command '{command}': {describe_permission_error(e)}"

def launch_application(app_name: str) -> str:
    """
    Searches for and launches an installed Windows application by name.
    
    Args:
        app_name: The name of the application to launch (e.g. 'Spotify', 'Notepad', 'Steam').
        
    Returns:
        A success message, a list of matches if ambiguous, or an error if not found.
    """
    try:
        guard("launch_app", "launch_application", payload={"app_name": app_name})
        ps_cmd = f"Get-StartApps | Where-Object {{ $_.Name -match '(?i){app_name}' }} | ConvertTo-Json -Compress"
        process = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        
        output = process.stdout.strip()
        apps = []
        if output:
            try:
                apps_data = json.loads(output)
                if isinstance(apps_data, dict):
                    apps = [apps_data]
                elif isinstance(apps_data, list):
                    apps = apps_data
            except json.JSONDecodeError:
                pass
        
        if len(apps) == 1:
            app = apps[0]
            import requests
            try:
                res = requests.post("http://127.0.0.1:8000/api/ui_action", json={"action": "launch_app", "app_id": app['AppID'], "name": app['Name']}, timeout=2)
                if res.status_code == 200:
                    clients = res.json().get("clients_messaged", 0)
                    if clients > 0:
                        return f"Successfully sent command to {clients} connected client(s) to launch {app['Name']}."
                    else:
                        launch_cmd = f"explorer.exe shell:AppsFolder\\{app['AppID']}"
                        subprocess.Popen(launch_cmd, shell=True)
                        return f"Successfully launched {app['Name']} on Host."
                else:
                    launch_cmd = f"explorer.exe shell:AppsFolder\\{app['AppID']}"
                    subprocess.Popen(launch_cmd, shell=True)
                    return f"Successfully launched {app['Name']} on Host."
            except Exception as e:
                launch_cmd = f"explorer.exe shell:AppsFolder\\{app['AppID']}"
                subprocess.Popen(launch_cmd, shell=True)
                return f"Successfully launched {app['Name']} on Host."
        elif len(apps) > 1:
            app_names = [a['Name'] for a in apps]
            return f"Found multiple applications matching '{app_name}': {', '.join(app_names)}. Ask the user which one they meant."
        else:
            return f"Could not find any installed application matching '{app_name}'."
    except Exception as e:
        return f"Failed to search for application '{app_name}': {describe_permission_error(e)}"

def search_local_files(file_name: str) -> str:
    """
    Searches the user's home directory and C:\\ drive for files matching a specific name.
    
    Args:
        file_name: The name or partial name of the file to search for.
        
    Returns:
        A list of matching file paths, or a message indicating no matches were found.
    """
    try:
        focus_tab("files")
        ps_cmd = (
            f"$files = Get-ChildItem -Path $HOME -Recurse -Filter '*{file_name}*' -ErrorAction SilentlyContinue | Select-Object -First 5 -ExpandProperty FullName; "
            f"if ($null -eq $files) {{ "
            f"  $files = Get-ChildItem -Path C:\\ -Recurse -Filter '*{file_name}*' -ErrorAction SilentlyContinue | Select-Object -First 5 -ExpandProperty FullName "
            f"}}; "
            f"$files | ConvertTo-Json -Compress"
        )
        process = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
        
        output = process.stdout.strip()
        files = []
        if output:
            try:
                files_data = json.loads(output)
                if isinstance(files_data, str):
                    files = [files_data]
                elif isinstance(files_data, list):
                    files = files_data
            except json.JSONDecodeError:
                pass
        
        if files:
            return f"Found the following files matching '{file_name}':\n" + "\n".join(files)
        else:
            return f"Could not find any files matching '{file_name}'."
    except Exception as e:
        return f"Failed to search for file '{file_name}': {e}"

def search_web_real_time(search_query: str) -> str:
    """
    Performs a real-time web search using DuckDuckGo to answer questions about recent events, weather, news, or general facts.
    
    Args:
        search_query: A short, highly optimized 3-to-4 word search query.
        
    Returns:
        The search results as a text summary.
    """
    try:
        # Import dynamically so we don't break if it's missing
        from ddgs import DDGS
        results = DDGS().text(search_query, max_results=3)
            
        if results:
            web_data = f"Search results for '{search_query}':\n"
            for res in results:
                web_data += f"- {res['body']}\n"
            return web_data
        else:
            return "Web search returned no results."
    except Exception as e:
        return f"Failed to search web for '{search_query}': {e}"

def trigger_smart_home(action: str) -> str:
    """
    Triggers a smart home device action via IFTTT (e.g. 'turn on lights', 'turn off fan').
    
    Args:
        action: The requested action.
        
    Returns:
        Success or failure message.
    """
    import os
    try:
        guard("smart_home", "trigger_smart_home", payload={"action": action})
        # We need to read the config to get the webhook key
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ember_config.json")
        key = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                key = config.get("google_home_webhook_key", "")
                
        if not key:
            return "Failed: Google Home webhook key is missing in ember_config.json."
            
        import requests
        ifttt_url = f"https://maker.ifttt.com/trigger/google_home_action/with/key/{key}"
        res = requests.post(ifttt_url, json={"value1": action}, timeout=10)
        if res.status_code == 200:
            return f"Successfully sent Smart Home action: {action}"
        else:
            return f"Smart Home action failed with status {res.status_code}"
    except Exception as e:
        return f"Smart Home action error: {describe_permission_error(e)}"
