import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ember_engine")
import uuid
import json
import time
import subprocess
import requests
import base64
import re
import traceback
import chromadb
import ollama
from bs4 import BeautifulSoup
import numpy as np
import io
import threading
import queue
from ember_app.brain.personality import ARCHITECT_PROMPT, COMPANION_PROMPT
from ember_app.brain.speech import clean_assistant_text

CONFIG_FILE = "ember_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"ollama_model": "gemma4:12b", "voice": "af_bella", "google_home_webhook_key": ""}

class EmberCore:
    def __init__(self):
        self.config = load_config()
        self.llama_server_url = self.config.get("llama_server_url", "http://127.0.0.1:8080/v1")
        self.voice = self.config.get("voice", "af_bella")
        self.sd_api_url = "http://127.0.0.1:7860/sdapi/v1/txt2img"
        self.chroma_client = None
        self.mem_collection = None
        self.doc_collection = None
        self.stt_model = None
        self.tts_pipeline = None
        self.reminders = []
        self.active_tasks = []
        self.mood = "neutral"
        self.energy = 5
        self.dnd_enabled = False
        self.complete_computer_control = self.config.get("complete_computer_control", False)
        self.architect_mode = self.config.get("architect_mode", False)
        self.last_interaction_time = time.time()
        self.active_editor_context = {}
        
        self.system_prompt = self.config.get("system_prompt", COMPANION_PROMPT)
        
        self.chat_context = [
            {
                "role": "system", 
                "content": self.get_active_prompt()
            }
        ]


    def _call_llama_server(self, messages, stream=False, tools=None):
        import requests
        import json
        import base64
        
        # Format messages for OpenAI API (Vision support)
        formatted_messages = []
        for m in messages:
            msg_copy = {"role": m["role"]}
            
            if "images" in m and m["images"]:
                # Convert to OpenAI vision format
                content_arr = [{"type": "text", "text": m.get("content", "")}]
                for img_path in m["images"]:
                    try:
                        with open(img_path, "rb") as img_file:
                            b64_str = base64.b64encode(img_file.read()).decode('utf-8')
                        ext = os.path.splitext(img_path)[1][1:] or 'png'
                        content_arr.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{ext};base64,{b64_str}"}
                        })
                    except:
                        pass
                msg_copy["content"] = content_arr
            else:
                msg_copy["content"] = m.get("content", "")
                
            if "tool_calls" in m:
                msg_copy["tool_calls"] = m["tool_calls"]
            if "tool_call_id" in m:
                msg_copy["tool_call_id"] = m["tool_call_id"]
            if "name" in m:
                msg_copy["name"] = m["name"]
                
            formatted_messages.append(msg_copy)

        payload = {
            "model": self.config.get("model", "gemma-4b-it"),
            "messages": formatted_messages,
            "stream": stream,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
            
        headers = {"Content-Type": "application/json"}
        try:
            if stream:
                res = requests.post(self.llama_server_url + "/chat/completions", json=payload, headers=headers, stream=True)
                res.raise_for_status()
                def generate():
                    for line in res.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith("data: "):
                                line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                data = json.loads(line)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        yield {"message": {"content": delta["content"]}}
                            except:
                                pass
                return generate()
            else:
                res = requests.post(self.llama_server_url + "/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    msg = data["choices"][0].get("message", {})
                    # Ensure format matches what ollama returned
                    return {"message": msg}
                return {"message": {"content": ""}}
        except Exception as e:
            raise Exception(f"Llama Server error: {e}")

    def get_active_prompt(self):
        if self.architect_mode:
            return f"{self.system_prompt}\n\n# ARCHITECT MODE\nYou are currently in Architect Mode. Your primary focus is acting as an advanced, autonomous AI development command center and engineering manager. You are in charge of task decomposition, architectural planning, executing code modifications, and orchestrating sub-tasks.\n\nIMPORTANT CAPABILITIES: You are integrated directly into the user's local Windows OS. You have full terminal access, file editing capabilities, and browser automation tools. You can spawn background tasks to execute long-running operations in parallel.\n\nWORKFLOW: When given a goal, you should: 1. Use the `write_artifact` tool to write a markdown file named `implementation_plan.md`. 2. Await user approval. 3. Autonomously execute the plan using your tools. 4. Verify your work using the browser automation tools or test commands. 5. Present verifiable artifacts back to the user.\n\nCRITICAL RULE: Do NOT use the `control_computer` tool to physically type code. Use `write_artifact` and `edit_file` for code generation and file modifications. Never show raw tool JSON to Chris; use tools internally, then explain the result plainly."
        return self.system_prompt

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt
        self.config["system_prompt"] = prompt
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        
        if self.chat_context and self.chat_context[0]["role"] == "system":
            self.chat_context[0]["content"] = self.get_active_prompt()
        else:
            self.chat_context.insert(0, {"role": "system", "content": self.get_active_prompt()})

    def set_architect_mode(self, enabled: bool):
        self.architect_mode = enabled
        self.config["architect_mode"] = enabled
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        
        if self.chat_context and self.chat_context[0]["role"] == "system":
            self.chat_context[0]["content"] = self.get_active_prompt()
        else:
            self.chat_context.insert(0, {"role": "system", "content": self.get_active_prompt()})

    def set_complete_computer_control(self, enabled: bool):
        self.complete_computer_control = enabled
        self.config["complete_computer_control"] = enabled
        try:
            from tools.permission_gate import update_policy
            update_policy("keyboard_mouse", "allow" if enabled else "ask")
        except Exception:
            pass
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def init_memory(self):
        chroma_host = self.config.get("chroma_server_host", False)
        chroma_url = self.config.get("chroma_server_url", "http://100.100.150.74:8001")
        db_path = os.path.join(os.getcwd(), "companion_memory")
        
        if chroma_host:
            import subprocess
            import time
            print("[EmberCore] Starting centralized ChromaDB Server on port 8001...")
            subprocess.Popen(["chroma", "run", "--path", db_path, "--host", "0.0.0.0", "--port", "8001"])
            time.sleep(2) # Give server time to start
            self.chroma_client = chromadb.HttpClient(host="localhost", port=8001)
        else:
            import urllib.parse
            parsed = urllib.parse.urlparse(chroma_url)
            host = parsed.hostname or "100.100.150.74"
            port = parsed.port or 8001
            print(f"[EmberCore] Connecting to centralized memory server at {host}:{port}...")
            self.chroma_client = chromadb.HttpClient(host=host, port=port)
            
        self.mem_collection = self.chroma_client.get_or_create_collection(name="conversations")
        self.doc_collection = self.chroma_client.get_or_create_collection(name="documents")

    def init_stt(self):
        try:
            import site
            packages = site.getsitepackages()
            if hasattr(site, 'getusersitepackages'):
                packages.append(site.getusersitepackages())
                
            for pkg_dir in packages:
                for lib in ["cublas", "cudnn"]:
                    bin_dir = os.path.join(pkg_dir, "nvidia", lib, "bin")
                    if os.path.exists(bin_dir):
                        os.environ["PATH"] += os.pathsep + bin_dir
                        if hasattr(os, 'add_dll_directory'):
                            os.add_dll_directory(bin_dir)

            from faster_whisper import WhisperModel
            self.stt_model = WhisperModel("base.en", device="cuda", compute_type="float16")
        except Exception as e:
            try:
                from faster_whisper import WhisperModel
                self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            except Exception as fallback_e:
                logger.error(f"Total STT Failure: {fallback_e}")

    def init_tts(self):
        try:
            from kokoro import KPipeline
            self.tts_pipeline = KPipeline(lang_code='a')
        except Exception as e:
            logger.error(f"Voice Engine Error: {e}")

    def transcribe_audio(self, audio_data: np.ndarray):
        if not self.stt_model:
            return "STT Model not loaded."
        try:
            segments, _ = self.stt_model.transcribe(audio_data, beam_size=5)
            return "".join([segment.text for segment in segments]).strip()
        except Exception as e:
            return f"Transcription error: {e}"

    def generate_tts_chunk(self, text: str):
        if not self.tts_pipeline: return None
        clean_text = clean_assistant_text(text)
        clean_text = re.sub(r'[^\x00-\x7F]+', '', clean_text)
        if not clean_text.strip(): return None
        
        audio_chunks = []
        try:
            generator = self.tts_pipeline(clean_text, voice=self.voice, speed=1)
            for _, _, audio in generator:
                audio_chunks.append(audio)
            if audio_chunks:
                return np.concatenate(audio_chunks)
        except Exception as e:
            logger.error(f"TTS Chunk Error: {e}")
        return None

    def execute_tool(self, name, args):
        if name == "delegate_research":
            topic = args.get("topic", "")
            if not topic: return "Error: topic is required."
            try:
                from agents.researcher import ResearcherAgent
                agent = ResearcherAgent(topic=topic, event_queue=self._event_queue, llama_server_url=self.llama_server_url)
                agent.start()
                return f"Successfully delegated research on '{topic}' to the Background Researcher Agent."
            except Exception as e:
                return f"Failed to start Researcher Agent: {e}"

        if name == "list_research_reports":
            try:
                from tools.research_library import list_research_reports
                return list_research_reports(limit=int(args.get("limit", 10)))
            except Exception as e:
                return f"Failed to list research reports: {e}"

        if name == "find_research_report":
            try:
                from tools.research_library import find_research_report
                return find_research_report(args.get("query", ""))
            except Exception as e:
                return f"Failed to find research report: {e}"

        if name == "read_research_report":
            try:
                from tools.research_library import read_research_report
                return read_research_report(args.get("report_id_or_topic", ""), max_chars=int(args.get("max_chars", 8000)))
            except Exception as e:
                return f"Failed to read research report: {e}"

        if name == "find_research_images":
            try:
                from tools.research_library import find_research_images
                return find_research_images(args.get("query", ""), max_results=int(args.get("max_results", 8)))
            except Exception as e:
                return f"Failed to find research images: {e}"

        if name == "read_emails" or (name == "email" and args.get("action") == "read"):
            try:
                from email_agent import EmailAgent
                agent = EmailAgent()
                if not agent.authenticate(): return "Failed to authenticate with Gmail."
                return agent.get_unread_emails(max_results=5)
            except Exception as e:
                return f"Error reading emails: {e}"
        elif name == "send_email" or (name == "email" and args.get("action") == "send"):
            try:
                from email_agent import EmailAgent
                agent = EmailAgent()
                if not agent.authenticate(): return "Failed to authenticate with Gmail."
                to_email = args.get("to_email", "")
                subject = args.get("subject", "")
                content = args.get("content", "")
                return agent.send_email(to_email, subject, content)
            except Exception as e:
                return f"Error sending email: {e}"
        elif name == "delete_email" or (name == "email" and args.get("action") == "delete"):
            try:
                from email_agent import EmailAgent
                agent = EmailAgent()
                if not agent.authenticate(): return "Failed to authenticate with Gmail."
                message_id = args.get("message_id", "")
                return agent.delete_email(message_id)
            except Exception as e:
                return f"Error deleting email: {e}"

        try:
            tools_to_route = [
                "os_command", "launch_app", "control_computer", 
                "take_screenshot", "capture_webcam", "find_text_on_screen", "manage_window", 
                "minimize_all_windows", "manage_media", "kill_process",
                "lock_computer", "read_clipboard", "write_clipboard",
                "read_file", "write_file", "move_file", "organize_folder"
            ]
            client_url = self.config.get("companion_client_url", "http://localhost:8002")
            
            if name in tools_to_route:
                if name == "control_computer":
                    if not getattr(self, "complete_computer_control", False):
                        return "Complete computer control is turned off. Enable it in Settings before I can move the mouse or type."
                    try:
                        from tools.permission_gate import describe_permission_error, guard
                        guard("keyboard_mouse", args.get("action", "control_computer"), payload=args)
                    except Exception as e:
                        return describe_permission_error(e)
                try:
                    try:
                        from tools.ui_tabs import focus_tab
                        if name == "os_command":
                            focus_tab("terminal")
                        elif name in ["read_clipboard", "write_clipboard"]:
                            focus_tab("chat")
                        elif name in ["take_screenshot", "find_text_on_screen", "control_computer", "manage_window", "minimize_all_windows", "manage_media"]:
                            focus_tab("remote")
                    except Exception:
                        pass
                    res = requests.post(f"{client_url}/execute", json={"tool": name, "args": args}, timeout=20)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("status") == "success":
                            if name == "take_screenshot" and "image_b64" in data:
                                # Save image locally so the LLM can read it
                                img_data = base64.b64decode(data["image_b64"])
                                os.makedirs("companion_images", exist_ok=True)
                                filepath = os.path.abspath(f"companion_images/screenshot_tool_{int(time.time())}.jpg")
                                with open(filepath, "wb") as f:
                                    f.write(img_data)
                                return f"SCREENSHOT_PATH:{filepath}|1024|1024 (A 10x10 coordinate grid has been overlaid on the image. Use it to estimate X,Y coordinates for clicking.)"
                            elif name == "capture_webcam" and "image_b64" in data:
                                img_data = base64.b64decode(data["image_b64"])
                                os.makedirs("companion_images", exist_ok=True)
                                filepath = os.path.abspath(f"companion_images/webcam_tool_{int(time.time())}.jpg")
                                with open(filepath, "wb") as f:
                                    f.write(img_data)
                                return f"WEBCAM_PATH:{filepath} (The user's camera has captured this frame. Use it to analyze the user's expression or surroundings.)"
                            return data.get("output", "Success.")
                        else:
                            return f"Client Execution Error: {data.get('output')}"
                    else:
                        return f"Failed to reach Client PC at {client_url}: Status {res.status_code}"
                except requests.exceptions.RequestException as e:
                    return f"Connection to Client PC ({client_url}) failed: {e}. Are you sure the companion worker is running?"
            
            if name == "find_text_on_screen":
                text_to_find = args.get("text", "").lower()
                from PIL import ImageGrab
                import pytesseract
                import os
                if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
                    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                img = ImageGrab.grab()
                try:
                    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                    for i, word in enumerate(data['text']):
                        if word and text_to_find in word.lower():
                            x = data['left'][i] + data['width'][i] // 2
                            y = data['top'][i] + data['height'][i] // 2
                            return f"Found '{word}' at coordinates x={x}, y={y}. You can now use control_computer to click it."
                    return f"Could not find text '{text_to_find}' on the screen."
                except pytesseract.pytesseract.TesseractNotFoundError:
                    return "ERROR: Tesseract OCR is not installed or not in PATH. Please tell the user to install Tesseract OCR for Windows from https://github.com/UB-Mannheim/tesseract/wiki and restart the server."
                except Exception as e:
                    return f"OCR Error: {e}"
            elif name == "manage_window":
                action = args.get("action", "")
                window_title = args.get("window_title", "")
                
                if action == "minimize_all":
                    import pyautogui
                    pyautogui.hotkey('win', 'd')
                    return "Successfully minimized all windows using Win+D."
                    
                import pygetwindow as gw
                windows = gw.getWindowsWithTitle(window_title)
                if not windows:
                    return f"Could not find any window with title containing '{window_title}'."
                win = windows[0]
                try:
                    if action == "maximize": win.maximize()
                    elif action == "minimize": win.minimize()
                    elif action == "restore": win.restore()
                    elif action == "close": win.close()
                    elif action == "activate": win.activate()
                    else: return f"Unknown action: {action}"
                    return f"Successfully performed '{action}' on window '{win.title}'."
                except Exception as e:
                    return f"Failed to perform '{action}' on window '{win.title}': {e}"
            elif name == "minimize_all_windows":
                import pyautogui
                pyautogui.hotkey('win', 'd')
                return "Successfully minimized all windows to show the desktop."
            elif name == "launch_app":
                app_name = args.get("app_name", "")
                ps_cmd = f"Get-StartApps | Where-Object {{ $_.Name -match '(?i){app_name}' }} | ConvertTo-Json -Compress"
                p = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
                out = p.stdout.strip()
                if out:
                    import json
                    apps = json.loads(out)
                    if isinstance(apps, dict): apps = [apps]
                    if len(apps) >= 1:
                        subprocess.Popen(f"explorer.exe shell:AppsFolder\\{apps[0]['AppID']}", shell=True)
                        time.sleep(2.0) # Let the app open and grab focus
                        return f"Successfully Launched {apps[0]['Name']}."
                return f"Could not find app '{app_name}'."
            elif name == "search_files":
                try:
                    from tools.ui_tabs import focus_tab
                    focus_tab("files")
                except Exception:
                    pass
                file_name = args.get("file_name", "")
                ps_cmd = (
                    f"$files = Get-ChildItem -Path $HOME -Recurse -Filter '*{file_name}*' -ErrorAction SilentlyContinue | Select-Object -First 5 -ExpandProperty FullName; "
                    f"if ($null -eq $files) {{ "
                    f"  $files = Get-ChildItem -Path C:\\ -Recurse -Filter '*{file_name}*' -ErrorAction SilentlyContinue | Select-Object -First 5 -ExpandProperty FullName "
                    f"}}; "
                    f"$files | ConvertTo-Json -Compress"
                )
                p = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=30)
                out = p.stdout.strip()
                if out:
                    import json
                    files = json.loads(out)
                    if isinstance(files, str): files = [files]
                    elif isinstance(files, list): pass
                    else: files = []
                    if files: return f"Found matching files:\n" + "\n".join(files)
                return f"Could not find any files matching '{file_name}'."
            elif name == "web_search":
                query = args.get("query", "")
                from ddgs import DDGS
                results = DDGS().text(query, max_results=3)
                if results:
                    return "Web Search Results:\n" + "\n".join([f"- {r['body']}" for r in results])
                return "No web results found."
            elif name == "open_browser":
                url = args.get("url", "")
                if not url.startswith("http"):
                    url = "https://" + url
                import json
                self._event_queue.put_nowait(("ui_action", json.dumps({"action": "open_browser", "url": url})))
                return f"Successfully opened {url} in the EmberOS browser."
            elif name == "extract_url":
                try:
                    from tools.ui_tabs import focus_tab
                    focus_tab("browser", url=args.get("url", ""))
                except Exception:
                    pass
                url = args.get("url", "")
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, 'html.parser')
                text_content = "\n".join([p.get_text() for p in soup.find_all('p')])
                return f"Content from {url}:\n{text_content[:4000]}"
            elif name == "set_reminder":
                minutes = float(args.get("minutes", 0))
                msg = args.get("message", "")
                trigger = time.time() + (minutes * 60)
                self.reminders.append({"trigger_time": trigger, "message": msg})
                return f"Successfully set a reminder for {minutes} minutes from now."
            elif name == "send_push_notification":
                message = args.get("message", "")
                topic = self.config.get("ntfy_topic", "")
                if not topic: return "Failed: ntfy_topic is missing in config."
                ntfy_url = f"https://ntfy.sh/{topic}"
                res = requests.post(ntfy_url, data=message.encode('utf-8'), timeout=10)
                if res.status_code == 200: return f"Successfully sent push notification to {topic}"
                return f"Push notification failed with status {res.status_code}"
            elif name == "take_screenshot":
                try:
                    from tools.ui_tabs import focus_tab
                    focus_tab("remote")
                except Exception:
                    pass
                from PIL import ImageGrab, ImageDraw, ImageFont
                os.makedirs("companion_images", exist_ok=True)
                filepath = os.path.abspath(f"companion_images/screenshot_tool_{int(time.time())}.png")
                img = ImageGrab.grab()
                width, height = img.size
                
                # Draw coordinate grid overlay
                draw = ImageDraw.Draw(img, "RGBA")
                grid_color = (255, 0, 0, 128)
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except Exception:
                    font = ImageFont.load_default()
                    
                x_step = width // 10
                y_step = height // 10
                for x in range(0, width, x_step):
                    draw.line([(x, 0), (x, height)], fill=grid_color, width=2)
                    for y in range(0, height, y_step):
                        draw.text((x + 5, y + 5), f"{x},{y}", font=font, fill=(255,255,0,255))
                for y in range(0, height, y_step):
                    draw.line([(0, y), (width, y)], fill=grid_color, width=2)
                
                img.save(filepath)
                return f"SCREENSHOT_PATH:{filepath}|{width}|{height} (A 10x10 coordinate grid has been overlaid on the image. Use it to estimate X,Y coordinates for clicking.)"
            elif name == "schedule_background_task":
                minutes = float(args.get("minutes", 0))
                task_prompt = args.get("task_prompt", "")
                
                import uuid
                task_id = uuid.uuid4().hex[:8]
                task_obj = {
                    "id": task_id,
                    "prompt": task_prompt,
                    "status": "Scheduled",
                    "eta": time.time() + (minutes * 60)
                }
                self.active_tasks.append(task_obj)

                def bg_timer():
                    time.sleep(minutes * 60)
                    for t in self.active_tasks:
                        if t["id"] == task_id:
                            t["status"] = "Running"
                            break

                    msg = f"[BACKGROUND TASK]: {task_prompt}. Start working on this now. CRITICAL: When you are finished, you MUST use the 'send_push_notification' tool to send a push notification to Chris with your findings!"
                    
                    import queue
                    import threading
                    dummy_queue = queue.Queue()
                    bot_reply = ""
                    try:
                        for msg_type, content in self.generate_mixed_stream(msg, None, dummy_queue):
                            if msg_type == "text": bot_reply += content
                        self.add_assistant_reply(bot_reply)
                        threading.Thread(target=self.save_memory, args=(msg, bot_reply)).start()
                    except Exception as e:
                        print(f"Background task failed: {e}")
                    finally:
                        self.active_tasks = [t for t in self.active_tasks if t["id"] != task_id]

                import threading
                threading.Thread(target=bg_timer, daemon=True).start()
                return f"Successfully scheduled background task '{task_prompt}' in {minutes} minutes."
            elif name == "control_computer":
                return "Host computer control is disabled. Complete computer control only runs on the connected desktop client."
            elif name == "read_file":
                filepath = args.get("filepath", "")
                if not os.path.exists(filepath):
                    return f"Error: File '{filepath}' does not exist."
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 10000:
                    content = content[:10000] + "\n\n...[Content Truncated due to length]..."
                return f"File Contents:\n```\n{content}\n```"
            elif name == "organize_folder":
                folder_path = args.get("folder_path", "")
                if not folder_path or folder_path.lower() == "desktop":
                    folder_path = os.path.join(os.path.expanduser("~"), "Desktop")
                
                if not os.path.exists(folder_path):
                    return f"Error: Folder '{folder_path}' does not exist."
                    
                import shutil
                
                categories = {
                    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
                    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
                    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
                    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
                    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
                    "Executables": [".exe", ".msi", ".bat", ".cmd"],
                    "Code": [".py", ".js", ".html", ".css", ".json", ".xml", ".cpp", ".c", ".h", ".cs", ".java"]
                }
                
                moved_count = 0
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isfile(item_path):
                        _, ext = os.path.splitext(item)
                        ext = ext.lower()
                        
                        target_category = "Other"
                        for cat, exts in categories.items():
                            if ext in exts:
                                target_category = cat
                                break
                                
                        target_dir = os.path.join(folder_path, target_category)
                        os.makedirs(target_dir, exist_ok=True)
                        
                        try:
                            shutil.move(item_path, os.path.join(target_dir, item))
                            moved_count += 1
                        except Exception:
                            pass
                            
                return f"Successfully organized {moved_count} files in {folder_path} into categorized folders by file type."
            elif name == "organize_desktop":
                folder_path = os.path.join(os.path.expanduser("~"), "Desktop")
                if not os.path.exists(folder_path):
                    return f"Error: Folder '{folder_path}' does not exist."
                    
                import shutil
                categories = {
                    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
                    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
                    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
                    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
                    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
                    "Executables": [".exe", ".msi", ".bat", ".cmd"],
                    "Code": [".py", ".js", ".html", ".css", ".json", ".xml", ".cpp", ".c", ".h", ".cs", ".java"]
                }
                
                moved_count = 0
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if os.path.isfile(item_path):
                        _, ext = os.path.splitext(item)
                        ext = ext.lower()
                        target_category = "Other"
                        for cat, exts in categories.items():
                            if ext in exts:
                                target_category = cat
                                break
                        target_dir = os.path.join(folder_path, target_category)
                        os.makedirs(target_dir, exist_ok=True)
                        try:
                            shutil.move(item_path, os.path.join(target_dir, item))
                            moved_count += 1
                        except Exception:
                            pass
                return f"Successfully organized {moved_count} files on the Desktop into categorized folders."
            elif name == "cleanup_empty_folders":
                folder_path = args.get("folder_path", "")
                if not folder_path or folder_path.lower() == "desktop":
                    folder_path = os.path.join(os.path.expanduser("~"), "Desktop")
                
                if not os.path.exists(folder_path):
                    return f"Error: Folder '{folder_path}' does not exist."
                    
                deleted_count = 0
                for root, dirs, files in os.walk(folder_path, topdown=False):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        try:
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                deleted_count += 1
                        except Exception:
                            pass
                return f"Successfully scanned {folder_path} and deleted {deleted_count} empty folders."
            elif name == "move_file":
                source_path = args.get("source_path", "")
                destination_path = args.get("destination_path", "")
                if not os.path.exists(source_path):
                    return f"Error: Source file '{source_path}' does not exist."
                import shutil
                try:
                    shutil.move(source_path, destination_path)
                    return f"Successfully moved '{source_path}' to '{destination_path}'."
                except Exception as e:
                    return f"Error moving file: {e}"
            elif name == "open_file":
                filepath = args.get("filepath", "")
                app_name = args.get("app_name", "")
                if not os.path.exists(filepath):
                    return f"Error: File '{filepath}' does not exist."
                try:
                    import json
                    self._event_queue.put_nowait(("ui_action", json.dumps({"action": "open_editor", "file": filepath})))
                    return f"Successfully opened '{filepath}' in the EmberOS Code Editor."
                except Exception as e:
                    return f"Error opening file: {e}"
            elif name == "search_youtube":
                query = args.get("query", "")
                if not query:
                    return "Error: You must provide a search query."
                import urllib.parse
                import json
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                self._event_queue.put_nowait(("ui_action", json.dumps({"action": "open_browser", "url": url})))
                return f"Successfully opened YouTube in the EmberOS browser and searched for '{query}'."
            elif name == "search_youtube_music":
                query = args.get("query", "")
                if not query:
                    return "Error: You must provide a search query."
                import urllib.parse
                import json
                url = f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"
                self._event_queue.put_nowait(("ui_action", json.dumps({"action": "open_browser", "url": url})))
                return f"Successfully opened YouTube Music in the EmberOS browser and searched for '{query}'."
            elif name == "search_torrentday":
                query = args.get("query", "")
                if not query:
                    return "Error: You must provide a search query."
                import urllib.parse
                import json
                url = f"https://www.torrentday.com/t?q={urllib.parse.quote(query)}"
                self._event_queue.put_nowait(("ui_action", json.dumps({"action": "open_browser", "url": url})))
                return f"Successfully opened TorrentDay in the EmberOS browser and searched for '{query}'."
            elif name == "read_clipboard" or (name == "clipboard" and args.get("action") == "read"):
                p = subprocess.run(["powershell", "-Command", "Get-Clipboard"], capture_output=True, text=True)
                return f"Clipboard contents:\n{p.stdout.strip()}"
            elif name == "write_clipboard" or (name == "clipboard" and args.get("action") == "write"):
                text = args.get("text", "")
                if not text:
                    return "Error: You must provide text to write to the clipboard."
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
                    f.write(text)
                    temp_path = f.name
                subprocess.run(["powershell", "-Command", f"Get-Content '{temp_path}' -Raw | Set-Clipboard"])
                os.remove(temp_path)
                return "Successfully copied text to clipboard."
            elif name == "manage_media":
                action = args.get("action", "").lower()
                import pyautogui
                if action == "playpause": pyautogui.press('playpause')
                elif action == "next": pyautogui.press('nexttrack')
                elif action == "previous": pyautogui.press('prevtrack')
                elif action == "volume_up": pyautogui.press('volumeup')
                elif action == "volume_down": pyautogui.press('volumedown')
                elif action == "mute": pyautogui.press('volumemute')
                else: return f"Error: Unknown media action '{action}'"
                return f"Successfully executed media action: {action}"
            elif name == "kill_process":
                process_name = args.get("process_name", "")
                if not process_name: return "Error: You must provide a process name."
                p = subprocess.run(["powershell", "-Command", f"Stop-Process -Name '{process_name}' -Force"], capture_output=True, text=True)
                if p.returncode == 0: return f"Successfully killed process: {process_name}"
                else: return f"Failed to kill process: {p.stderr.strip()}"
            elif name == "check_system_stats":
                cpu_cmd = "Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average | Select-Object -ExpandProperty Average"
                ram_cmd = "$os = Get-WmiObject Win32_OperatingSystem; $free = [math]::Round($os.FreePhysicalMemory / 1024, 2); $total = [math]::Round($os.TotalVisibleMemorySize / 1024, 2); \"${free}MB free of ${total}MB\""
                cpu = subprocess.run(["powershell", "-Command", cpu_cmd], capture_output=True, text=True).stdout.strip()
                ram = subprocess.run(["powershell", "-Command", ram_cmd], capture_output=True, text=True).stdout.strip()
                return f"System Stats:\nCPU Load: {cpu}%\nRAM: {ram}"
            elif name == "empty_trash":
                p = subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Force -Confirm:$false"], capture_output=True, text=True)
                return "Successfully emptied the recycle bin."
            elif name == "get_active_window":
                try:
                    import pygetwindow
                    win = pygetwindow.getActiveWindow()
                    if win: return f"The user is currently looking at: {win.title}"
                    else: return "No active window found."
                except Exception as e: return f"Error getting active window: {e}"
            elif name == "manage_notes":
                action = args.get("action", "")
                notes_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ember_notes.txt")
                if action == "read":
                    if not os.path.exists(notes_file): return "Notes file is currently empty."
                    with open(notes_file, "r", encoding="utf-8") as f: return f"Notes:\n{f.read()}"
                elif action == "write":
                    text = args.get("text", "")
                    with open(notes_file, "a", encoding="utf-8") as f: f.write(text + "\n")
                    return f"Successfully added note: {text}"
                elif action == "clear":
                    if os.path.exists(notes_file): os.remove(notes_file)
                    return "Successfully cleared all notes."
                else: return "Unknown notes action. Use read, write, or clear."
            elif name == "lock_computer":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                return "Successfully locked the computer."
            elif name == "write_artifact":
                filename = args.get("filename", "")
                content = args.get("content", "")
                os.makedirs(os.path.dirname(os.path.abspath(filename)) or '.', exist_ok=True)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote artifact to {filename}"
            elif name == "edit_file":
                filepath = args.get("filepath", "")
                content = args.get("content", "")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully edited file {filepath}"
            elif name == "browser_verify":
                url = args.get("url", "")
                subprocess.Popen(["python", "browser_agent.py", url])
                return f"Spawned browser_agent.py to verify {url} in background."
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Tool execution failed: {e}"

    def generate_mixed_stream(self, user_text, attached_image_path=None, event_queue=None):
        self.last_interaction_time = time.time()
        self._event_queue = event_queue
        
        if not hasattr(self, 'bg_agents_started') and event_queue:
            self.bg_agents_started = True
            try:
                from agents.monitor import MonitorAgent
                from agents.communications import CommunicationsAgent
                MonitorAgent(event_queue=event_queue, downloads_folder=self.config.get("downloads_folder")).start()
                CommunicationsAgent(event_queue=event_queue).start()
            except Exception as e:
                print(f"Failed to start background agents: {e}")
        
        # Slightly adjust energy randomly
        self.energy = max(1, min(10, self.energy + np.random.choice([-1, 0, 1])))

        if user_text.strip().lower() in ["/clear", "clear memory"]:
            self.chat_context = [self.chat_context[0]]
            yield ("text", "Chat history has been cleared.")
            return

        if user_text:
            if not user_text.startswith("[GAME LOOP]") and not user_text.startswith("BACKGROUND TOOL RESULT") and not user_text.startswith("[SYSTEM NOTIFICATION"):
                self.chat_context.append({"role": "user", "content": user_text})
            else:
                # Add to messages_for_llm later, but don't pollute the long-term context
                pass
        
        retrieved_context = []
        if self.mem_collection:
            mem_results = self.mem_collection.query(query_texts=[user_text], n_results=2)
            if mem_results['documents'] and mem_results['documents'][0]:
                for doc, dist in zip(mem_results['documents'][0], mem_results['distances'][0]):
                    if dist < 1.2: retrieved_context.append(doc)
        if self.doc_collection:
            doc_results = self.doc_collection.query(query_texts=[user_text], n_results=2)
            if doc_results['documents'] and doc_results['documents'][0]:
                for doc, dist in zip(doc_results['documents'][0], doc_results['distances'][0]):
                    if dist < 1.2: retrieved_context.append(doc)

        import copy
        messages_for_llm = copy.deepcopy(self.chat_context)
        
        # Inject the ephemeral background/game triggers that were excluded from chat_context
        if user_text and (user_text.startswith("[GAME LOOP]") or user_text.startswith("BACKGROUND TOOL RESULT") or user_text.startswith("[SYSTEM NOTIFICATION")):
            messages_for_llm.append({"role": "user", "content": user_text})
            
        if retrieved_context:
            context_str = "\n".join(retrieved_context)
            messages_for_llm.insert(-1, {
                "role": "system",
                "content": f"Relevant context from past interactions or documents:\n\n{context_str}"
            })

        if attached_image_path and os.path.exists(attached_image_path):
            messages_for_llm[-1]["images"] = [attached_image_path]

        tools = [
            {"type": "function", "function": {"name": "os_command", "description": "Execute a PowerShell command on the host OS.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
            {"type": "function", "function": {"name": "launch_app", "description": "Launch a Windows application by name.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}},
            {"type": "function", "function": {"name": "search_files", "description": "Search for files on disk by name.", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}}, "required": ["file_name"]}}},
            {"type": "function", "function": {"name": "web_search", "description": "Search DuckDuckGo for real-time info (weather, news, facts).", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "open_browser", "description": "Open any URL in the user's browser. To search YouTube use https://www.youtube.com/results?search_query=QUERY, YouTube Music: https://music.youtube.com/search?q=QUERY, TorrentDay: https://www.torrentday.com/t?q=QUERY.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "extract_url", "description": "Extract text content from a URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {"name": "set_reminder", "description": "Set a reminder or timer.", "parameters": {"type": "object", "properties": {"minutes": {"type": "number"}, "message": {"type": "string"}}, "required": ["minutes", "message"]}}},
            {"type": "function", "function": {"name": "send_push_notification", "description": "Send a push notification to the user's phone.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
            {"type": "function", "function": {"name": "generate_image", "description": "Generate an image with Stable Diffusion.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}},
            {"type": "function", "function": {"name": "take_screenshot", "description": "Take a screenshot of the user's screen.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "schedule_background_task", "description": "Schedule a background task to run later.", "parameters": {"type": "object", "properties": {"minutes": {"type": "number"}, "task_prompt": {"type": "string"}}, "required": ["minutes", "task_prompt"]}}},
            {"type": "function", "function": {"name": "find_text_on_screen", "description": "OCR: find (X,Y) coords of any text on screen.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
            {"type": "function", "function": {"name": "manage_window", "description": "Manage windows. Actions: maximize, minimize, close, restore, activate, minimize_all (no window_title needed for minimize_all).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "window_title": {"type": "string"}}, "required": ["action"]}}},
            {"type": "function", "function": {"name": "read_file", "description": "Read a file from the local filesystem.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
            {"type": "function", "function": {"name": "organize_folder", "description": "Sort files in a folder into subfolders by type. Use folder_path='Desktop' for the desktop.", "parameters": {"type": "object", "properties": {"folder_path": {"type": "string"}}, "required": ["folder_path"]}}},
            {"type": "function", "function": {"name": "move_file", "description": "Move or rename a file.", "parameters": {"type": "object", "properties": {"source_path": {"type": "string"}, "destination_path": {"type": "string"}}, "required": ["source_path", "destination_path"]}}},
            {"type": "function", "function": {"name": "open_file", "description": "Open a file with its default or a specified app.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "app_name": {"type": "string"}}, "required": ["filepath"]}}},
            {"type": "function", "function": {"name": "clipboard", "description": "Read or write the system clipboard. Actions: read, write (needs text).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "text": {"type": "string"}}, "required": ["action"]}}},
            {"type": "function", "function": {"name": "manage_media", "description": "Control media/volume. Actions: playpause, next, previous, volume_up, volume_down, mute.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}}},
            {"type": "function", "function": {"name": "kill_process", "description": "Kill a running process by name.", "parameters": {"type": "object", "properties": {"process_name": {"type": "string"}}, "required": ["process_name"]}}},
            {"type": "function", "function": {"name": "check_system_stats", "description": "Get current CPU and RAM usage.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "empty_trash", "description": "Empty the Windows Recycle Bin.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "get_active_window", "description": "Get the title of the currently focused window.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "manage_notes", "description": "Read, write, or clear the notepad. Actions: read, write (needs text), clear.", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "text": {"type": "string"}}, "required": ["action"]}}},
            {"type": "function", "function": {"name": "lock_computer", "description": "Lock the Windows screen.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "delegate_research", "description": "Delegate research to a background agent. Reports back in a few minutes.", "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}}},
            {"type": "function", "function": {"name": "list_research_reports", "description": "List saved background research reports.", "parameters": {"type": "object", "properties": {"limit": {"type": "number"}}, "required": []}}},
            {"type": "function", "function": {"name": "find_research_report", "description": "Find a saved background research report by topic or keyword.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "read_research_report", "description": "Read a saved background research report by ID, topic, or filepath.", "parameters": {"type": "object", "properties": {"report_id_or_topic": {"type": "string"}, "max_chars": {"type": "number"}}, "required": ["report_id_or_topic"]}}},
            {"type": "function", "function": {"name": "find_research_images", "description": "Find images, pictures, diagrams, or schematics related to a research topic.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "number"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "email", "description": "Manage Gmail. Actions: read (no extra args), send (needs to_email, subject, content), delete (needs message_id).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "to_email": {"type": "string"}, "subject": {"type": "string"}, "content": {"type": "string"}, "message_id": {"type": "string"}}, "required": ["action"]}}}
        ]

        if getattr(self, "complete_computer_control", False):
            tools.append({"type": "function", "function": {"name": "control_computer", "description": "Control mouse/keyboard only when Chris has enabled complete computer control. Actions: click (needs x,y), type (needs text), press_key (needs text), scroll (needs amount), wait (needs amount).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "text": {"type": "string"}, "amount": {"type": "number"}}, "required": ["action"]}}})
        
        if getattr(self, 'architect_mode', False):
            tools.extend([
                {"type": "function", "function": {"name": "write_artifact", "description": "Write complete source code or text to a new file on disk.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string", "description": "The exact content to write. Remember to escape newlines as \\n in JSON."}}, "required": ["filename", "content"]}}},
                {"type": "function", "function": {"name": "edit_file", "description": "Overwrite an existing file with new content.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string", "description": "The new content. Remember to escape newlines as \\n in JSON."}}, "required": ["filepath", "content"]}}},
                {"type": "function", "function": {"name": "browser_verify", "description": "Run Playwright script to verify web app and capture a screenshot.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}
            ])

        import json
        
        # Phase 1: Tool Schema Dynamic Routing
        supports_native_tools = True
        
        import datetime
        current_time = datetime.datetime.now().strftime('%A, %B %d, %Y %I:%M %p')
        system_injection_base = f"\n\n# State\nTime: {current_time} | Mood: {self.mood} | Energy: {self.energy}/10 | DND: {'ON' if self.dnd_enabled else 'OFF'}\nUse tools when they directly help with the request, especially for current information, research, files, browser, or OS actions. Never roleplay tool actions with asterisks; use actual tool calls. Keep replies concise and give one final answer."
        system_injection_tools = f"\n# Internal Tool Protocol\nYou have access to the following tools:\n{json.dumps(tools, indent=2)}\n\nWhen native tool calling is unavailable, emit an internal JSON array exactly like [{{\"name\": \"tool_name\", \"arguments\": {{...}} }}]. This is not user-facing text. After tool results arrive, answer Chris normally and do not show JSON."
        
        # Ensure the system persona has the state (and manually-injected tools if not supported natively)
        for m in messages_for_llm:
            if m["role"] == "system":
                if "# Current Internal State" not in m["content"]:
                    if supports_native_tools:
                        m["content"] += system_injection_base
                    else:
                        m["content"] += (system_injection_base + system_injection_tools)
                break

        # Phase 3: Fast-Path Conversational Bypass
        skip_tool_loop = False
        if user_text:
            import re
            simple_phrases = ["ok", "okay", "yes", "no", "yeah", "yep", "nope", "haha", "lol", "good", "bad", "cool", "nice", "awesome", "thanks", "thank you", "hello", "hi", "hey", "morning", "night", "goodnight", "what's up", "whats up"]
            user_text_clean = re.sub(r'[^\w\s]', '', user_text.lower()).strip()
            
            # If it's a known short phrase, or highly likely to just be a short conversational reply
            if user_text_clean in simple_phrases or (len(user_text_clean.split()) <= 3 and not any(w in user_text_clean for w in ["do", "open", "search", "show", "play", "find", "look", "what", "where", "how", "why"])):
                skip_tool_loop = True

        loop_count = 0
        used_tools = False
        direct_reply = None
        if skip_tool_loop:
            loop_count = 5 # Skip the tool evaluation loop completely
            
        while loop_count < 5:
            try:
                if supports_native_tools:
                    res = self._call_llama_server(messages=messages_for_llm, stream=False, tools=tools)
                else:
                    res = self._call_llama_server(messages=messages_for_llm, stream=False)
            except Exception as e:
                err_str = str(e).lower()
                if "model output must contain either output text or tool calls" in err_str:
                    # Model completely failed to generate text. Give a fallback string to prevent crash.
                    res = {"message": {"role": "assistant", "content": "I apologize, but my vision processing is experiencing an error right now. I'm having trouble analyzing what I see."}}
                else:
                    try:
                        res = self._call_llama_server(messages=messages_for_llm, stream=False)
                    except Exception as fallback_e:
                        res = {"message": {"role": "assistant", "content": f"I apologize, but I encountered a critical LLM error: {fallback_e}"}}

            msg = res['message']
            reply_content = msg.get('content', '').strip()
            
            # Preserve native tool calls if present
            if 'tool_calls' not in msg or not msg['tool_calls']:
                msg['tool_calls'] = []
                if not user_text.startswith("BACKGROUND TOOL RESULT"):
                    import re
                    
                    def find_and_parse_tools(text):
                        found_calls = []
                        
                        def extract_tools(data):
                            if isinstance(data, dict):
                                if "name" in data and ("arguments" in data or "content" in data or "query" in data):
                                    name = data.pop("name")
                                    args = data.get("arguments", data)
                                    found_calls.append({"id": f"manual_{len(found_calls)}", "function": {"name": name, "arguments": args}})
                                elif "function" in data and isinstance(data["function"], dict) and "name" in data["function"]:
                                    data.setdefault("id", f"manual_{len(found_calls)}")
                                    found_calls.append(data)
                                else:
                                    for v in data.values():
                                        extract_tools(v)
                            elif isinstance(data, list):
                                for item in data:
                                    extract_tools(item)

                        # Try to catch Command R innate tool format: (tool call) ToolName input={...}
                        cmd_r_calls = re.findall(r'\(tool call\)\s+([\w_]+)\s+input\s*=\s*(\{.*?\})', text, re.DOTALL | re.IGNORECASE)
                        for t_name, t_args_str in cmd_r_calls:
                            try:
                                t_args = json.loads(t_args_str)
                                if t_name.lower() == "websearch": t_name = "web_search"
                                elif t_name.lower() == "webfetch": t_name = "extract_url"
                                found_calls.append({"id": f"manual_{len(found_calls)}", "function": {"name": t_name, "arguments": t_args}})
                            except: pass
                        if found_calls: return found_calls

                        # Try to find markdown blocks first
                        blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
                        for b in blocks:
                            try:
                                data = json.loads(b.replace(r"\_", "_"))
                                extract_tools(data)
                            except: pass
                            
                        if found_calls: return found_calls
                        
                        # Try brace counting for arrays
                        start = 0
                        while True:
                            idx = text.find('[', start)
                            if idx == -1: break
                            bracket_count = 0
                            for i in range(idx, len(text)):
                                if text[i] == '[': bracket_count += 1
                                elif text[i] == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        try:
                                            arr_str = text[idx:i+1].replace(r"\_", "_")
                                            data = json.loads(arr_str)
                                            extract_tools(data)
                                        except: pass
                                        break
                            start = idx + 1
                            
                        if found_calls: return found_calls
                        
                        # Try brace counting for loose objects
                        start = 0
                        while True:
                            idx = text.find('{', start)
                            if idx == -1: break
                            brace_count = 0
                            for i in range(idx, len(text)):
                                if text[i] == '{': brace_count += 1
                                elif text[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        try:
                                            obj_str = text[idx:i+1].replace(r"\_", "_")
                                            data = json.loads(obj_str)
                                            extract_tools(data)
                                        except: pass
                                        break
                            start = idx + 1
                            
                        return found_calls

                    msg['tool_calls'] = find_and_parse_tools(reply_content)
                    
            messages_for_llm.append(msg)
            
            if msg.get('tool_calls'):
                used_tools = True
                # Save tool call to context so she remembers she used it (prevents learning to hallucinate)
                msg_copy = dict(msg)
                msg_copy["content"] = ""
                msg_copy.pop('tool_calls', None) # Remove tool_calls field just in case it breaks vision models on next turn
                self.chat_context.append(msg_copy)
            
            if not msg['tool_calls']:
                if supports_native_tools:
                    direct_reply = reply_content
                    break
                else:
                    if not msg.get('content') or msg['content'].strip() == "":
                        messages_for_llm.append({"role": "user", "content": "System Warning: Your last output was completely empty. Please provide a text response to the user explaining what you saw or did."})
                        loop_count += 1
                        continue
                break
                
            for tc in msg['tool_calls']:
                fn = tc['function']['name']
                args = tc['function']['arguments']
                
                # Safely parse arguments in case the LLM returned a JSON string instead of a dict
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                elif not isinstance(args, dict):
                    args = {}
                
                if fn in ["search_files", "web_search", "generate_image"]:
                    def bg_task(func_name, arguments):
                        if func_name == "generate_image":
                            prompt = arguments.get("prompt", "")
                            img_b64 = self.generate_image(prompt)
                            if img_b64 and event_queue:
                                event_queue.put(("image_trigger", img_b64))
                                event_queue.put(("system_trigger", f"BACKGROUND TOOL RESULT for {func_name}:\nSuccessfully generated image. Tell the user you made it for them!"))
                            elif event_queue:
                                event_queue.put(("system_trigger", f"BACKGROUND TOOL RESULT for {func_name}:\nFailed to generate image. Tell the user there was an error."))
                        else:
                            res_text = self.execute_tool(func_name, arguments)
                            if len(res_text) > 3000:
                                res_text = res_text[:3000] + "\n\n...[Content Truncated Due to Length]..."
                            if event_queue:
                                event_queue.put(("system_trigger", f"BACKGROUND TOOL RESULT for {func_name}:\n{res_text}\nSummarize this for the user."))
                    threading.Thread(target=bg_task, args=(fn, args), daemon=True).start()
                    tool_msg = {"role": "tool", "content": "Tool started in background. Tell the user you are working on it right now.", "name": fn}
                    if tc.get("id"):
                        tool_msg["tool_call_id"] = tc["id"]
                    messages_for_llm.append(tool_msg)
                    self.chat_context.append(tool_msg)
                else:
                    res_text = self.execute_tool(fn, args)
                    if res_text.startswith("SCREENSHOT_PATH:"):
                        parts = res_text.split("|")
                        img_path = parts[0].split("SCREENSHOT_PATH:")[1]
                        width = parts[1] if len(parts) > 1 else "unknown"
                        height = parts[2] if len(parts) > 2 else "unknown"
                        
                        import base64
                        try:
                            with open(img_path, "rb") as img_file:
                                b64_str = base64.b64encode(img_file.read()).decode('utf-8')
                            if event_queue:
                                event_queue.put(("image_trigger", f"data:image/png;base64,{b64_str}"))
                        except Exception as e:
                            pass
                            
                        tool_msg = {"role": "tool", "content": f"Screenshot taken successfully. Screen resolution is {width}x{height}. You can now use control_computer or answer the user based on what you see. IMPORTANT: You must calculate the exact pixel X and Y coordinates based on this resolution to click accurately.", "name": fn}
                        if tc.get("id"):
                            tool_msg["tool_call_id"] = tc["id"]
                        messages_for_llm.append(tool_msg)
                        self.chat_context.append(tool_msg)
                        
                        try:
                            import ollama
                            logging.info("Sending autonomous screenshot to Llava for analysis...")
                            vision_resp = ollama.chat(
                                model='llava-llama3:8b',
                                messages=[{
                                    'role': 'user',
                                    'content': 'Please describe exactly what you see in this screen capture in detail. Include any text, icons, open windows, and overall context.',
                                    'images': [img_path]
                                }]
                            )
                            vision_text = vision_resp['message']['content']
                            messages_for_llm.append({"role": "user", "content": f"Here is the description of the screenshot you requested: {vision_text}"})
                            self.chat_context.append({"role": "user", "content": "Here is the screenshot you requested: [Image Omitted from History]"})
                        except Exception as e:
                            logging.error(f"Autonomous vision processing failed: {e}")
                            messages_for_llm.append({"role": "user", "content": "System Error: The Vision subsystem failed to process the screenshot."})
                    else:
                        if len(res_text) > 3000:
                            res_text = res_text[:3000] + "\n\n...[Content Truncated Due to Length]..."
                        tool_msg = {"role": "tool", "content": res_text, "name": fn}
                        if tc.get("id"):
                            tool_msg["tool_call_id"] = tc["id"]
                        messages_for_llm.append(tool_msg)
                        self.chat_context.append(tool_msg)
            loop_count += 1

        def stream_processor(stream_gen):
            sentence_buffer = ""
            for chunk in stream_gen:
                token = chunk if isinstance(chunk, str) else chunk['message']['content']
                yield ("text", token)
                sentence_buffer += token
                
                import re
                if re.search(r'[.?!]\s|\n', sentence_buffer):
                    sentences = re.split(r'(?<=[.?!])\s+|\n+', sentence_buffer)
                    for s in sentences[:-1]:
                        if len(s.strip()) > 1:
                            if "[GAME LOOP]" not in user_text:
                                audio = self.generate_tts_chunk(s.strip())
                                if audio is not None: yield ("audio", audio)
                    sentence_buffer = sentences[-1]
                    
            if len(sentence_buffer.strip()) > 1:
                if "[GAME LOOP]" not in user_text:
                    audio = self.generate_tts_chunk(sentence_buffer.strip())
                    if audio is not None: yield ("audio", audio)

        # The tool loop has finished. If no tools were needed, return the first
        # answer directly instead of asking the model to answer the same turn again.
        if not used_tools and direct_reply:
            yield from stream_processor([direct_reply])
            return

        # We now stream the final reply from the chat model.
        # Ensure we discard the tool model's un-streamed plain text response,
        # by passing the original context (with tool results) to the chat model.
        
        # Sanitize messages for the chat model (which might not support tools natively)
        sanitized_messages = []
        for m in messages_for_llm:
            if m["role"] == "system":
                if "# Current Internal State" in m["content"]:
                    m["content"] = m["content"].split("# Current Internal State")[0].strip()
                sanitized_messages.append(m)
            elif m["role"] == "tool":
                sanitized_messages.append({"role": "user", "content": f"[BACKGROUND PROCESS - TOOL RESULT: {m.get('name', 'unknown')}]\n{m.get('content', '')}"})
            elif m["role"] == "assistant" and (not m.get("content") or m["content"].strip() == ""):
                # Skip empty assistant messages created by the tool model
                continue
            elif m["role"] == "assistant" and m.get("tool_calls"):
                continue
            else:
                m = dict(m)
                m.pop("tool_calls", None)
                sanitized_messages.append(m)

        try:
            yield from stream_processor(self._call_llama_server(messages=sanitized_messages, stream=True))
        except Exception as e:
            yield ("error", f"Model streaming error: {e}")

    def add_assistant_reply(self, bot_reply):
        self.chat_context.append({"role": "assistant", "content": bot_reply})
        if len(self.chat_context) > 11:
            self.chat_context = [self.chat_context[0]] + self.chat_context[-10:]

    def save_memory(self, user_text, bot_reply):
        if self.mem_collection:
            try:
                memory_id = str(uuid.uuid4())
                self.mem_collection.add(
                    documents=[f"User: {user_text} | Ember: {bot_reply}"], 
                    metadatas=[{"role": "conversation"}], 
                    ids=[memory_id]
                )
            except Exception as e:
                logger.error(f"Memory save failed: {e}")

    def generate_image(self, sd_prompt):
        enhance_messages = [
            {"role": "system", "content": "You are an expert Stable Diffusion prompt generator... (Summarized)"},
            {"role": "user", "content": f"Enhance this prompt: {sd_prompt}"}
        ]
        enhance_response = self._call_llama_server(messages=enhance_messages, stream=False)
        enhanced_prompt = enhance_response['message']['content'].replace('"', '').strip()
        
        payload = {"prompt": enhanced_prompt, "steps": 25, "cfg_scale": 7, "width": 512, "height": 512}
        response = requests.post(self.sd_api_url, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json()['images'][0]
        return None
