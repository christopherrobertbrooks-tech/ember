import os
import os
import json
import logging
from phi.agent import Agent
from phi.storage.agent.sqlite import SqlAgentStorage
from ember_app.brain.manual_tool_parser import extract_manual_tool_calls
from ember_app.brain.speech import clean_assistant_text

# Apply monkey patch to automatically focus UI tabs based on tool use
try:
    from phi.tools.function import FunctionCall
    original_execute = FunctionCall.execute

    def _patched_execute(self, *args, **kwargs):
        try:
            from tools.ui_tabs import focus_tab
            name = getattr(self.function, "name", "").lower()
            
            if "transfer_task" in name:
                if "code" in name: focus_tab("editor")
                elif "terminal" in name: focus_tab("terminal")
                elif "browser" in name or "research" in name: focus_tab("browser")
                elif "file" in name: focus_tab("files")
            elif "shell" in name or "python" in name or "bash" in name:
                focus_tab("terminal")
            elif "search" in name or "browser" in name or "crawl" in name or "duckduckgo" in name or "navigate" in name:
                if "background_research" not in name:
                    focus_tab("browser")
            elif "file" in name or "read" in name or "write" in name:
                focus_tab("editor")
        except Exception:
            pass
            
        return original_execute(self, *args, **kwargs)

    FunctionCall.execute = _patched_execute
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("phidata_engine")

CONFIG_FILE = "ember_config.json"

def _permission_allows(category):
    try:
        from tools.permission_gate import get_state
        state = get_state()
        return state.get("policies", {}).get(category) == "allow"
    except Exception:
        return False

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"ollama_model": "gemma4", "voice": "af_bella"}

def resolve_openai_endpoint(config):
    return config.get("lm_studio_endpoint") or config.get("llama_server_url")

class PhidataEmberCore:
    def _extract_manual_tool_calls(self, text):
        return extract_manual_tool_calls(text)

    def _run_manual_tool_calls(self, tool_calls):
        import json

        results = []
        for call in tool_calls[:3]:
            name = call.get("name", "")
            args = call.get("arguments", {})
            
            # Auto-focus UI tab based on manual tool call name
            try:
                from tools.ui_tabs import focus_tab
                name_lower = name.lower()
                if "transfertaskto" in name_lower or "transfer_task_to" in name_lower:
                    if "code" in name_lower: focus_tab("editor")
                    elif "terminal" in name_lower: focus_tab("terminal")
                    elif "browser" in name_lower or "research" in name_lower: focus_tab("browser")
                    elif "file" in name_lower: focus_tab("files")
                elif "shell" in name_lower or "python" in name_lower or "bash" in name_lower:
                    focus_tab("terminal")
                elif "search" in name_lower or "browser" in name_lower or "crawl" in name_lower or "duckduckgo" in name_lower or "navigate" in name_lower:
                    if "background_research" not in name_lower:
                        focus_tab("browser")
                elif "file" in name_lower or "read" in name_lower or "write" in name_lower:
                    focus_tab("editor")
            except Exception:
                pass

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}

            try:
                func = self.manual_tool_funcs.get(name)
                if name == "control_computer":
                    if not self.config.get("complete_computer_control", False):
                        result = "Complete computer control is turned off. Enable it in Settings before I can move the mouse or type."
                        results.append(f"{name}: {result}")
                        continue
                    action = args.get("action", "")
                    if action in {"click", "mouse_click"}:
                        from tools.remote_desktop_tools import click_mouse
                        result = click_mouse(args.get("button", "left"))
                    elif action in {"type", "keyboard_type"}:
                        from tools.remote_desktop_tools import type_text
                        result = type_text(args.get("text", ""))
                    elif action in {"move", "mouse_move"}:
                        from tools.remote_desktop_tools import move_mouse
                        result = move_mouse(int(args.get("x", 0)), int(args.get("y", 0)))
                    else:
                        result = f"Unknown control_computer action: {action}"
                elif name == "web_search":
                    from tools.os_tools import search_web_real_time
                    result = search_web_real_time(args.get("query", ""))
                elif name == "open_browser":
                    from tools.browser_tools import open_in_browser
                    result = open_in_browser(args.get("url", ""))
                elif name == "take_screenshot":
                    from tools.os_tools import take_screenshot
                    result = take_screenshot()
                elif "transfertaskto" in name.lower() or "transfer_task_to" in name.lower():
                    result = (
                        "Task transfer failed due to formatting. "
                        "If you are trying to recall background research, use 'read_research_report' directly instead of delegating to the Research Agent, because the Research Agent only searches the web. "
                        "If you need to search the web, use the DuckDuckGo tool yourself."
                    )
                elif func:
                    result = func(**args)
                else:
                    result = f"Tool '{name}' is not available in this runtime."
            except Exception as e:
                result = f"Tool '{name}' failed: {e}"

            results.append(f"{name}: {result}")

        return "\n\n".join(results)

    def _get_model(self, m_id, opts=None):
        if self.openai_endpoint:
            from phi.model.openai import OpenAIChat
            return OpenAIChat(id=m_id, base_url=self.openai_endpoint, api_key="not-needed")

        from phi.model.ollama import Ollama
        return Ollama(id=m_id, host=self.ollama_endpoint, options=opts or {})

    def __init__(self):
        self.config = load_config()
        self.model = self.config.get("phidata_model", self.config.get("model", "gemma4"))
        self.voice = self.config.get("voice", "af_bella")
        
        from ember_app.brain.personality import COMPANION_PROMPT
        
        self.ollama_endpoint = self.config.get("ollama_endpoint", "http://127.0.0.1:11434")
        self.openai_endpoint = resolve_openai_endpoint(self.config)
        
        # Load tools
        tool_funcs = []

        def delegate_background_research(topic: str) -> str:
            """
            Starts a background research job for a topic. Use this for long-running research the user wants Ember to gather and save for later.
            """
            try:
                from agents.researcher import ResearcherAgent
                from ember_app.state import get_state
                
                try:
                    state = get_state()
                    event_q = state.global_sync_queue
                except Exception:
                    event_q = None

                agent = ResearcherAgent(
                    topic=topic,
                    event_queue=event_q,
                    llama_server_url=self.config.get("llama_server_url", "http://127.0.0.1:11434/v1"),
                    model=self.model,
                )
                agent.start()
                return f"Started background research on '{topic}'. I will save the report and notify Chris when it is ready."
            except Exception as e:
                return f"Failed to start background research on '{topic}': {e}"

        try:
            from tools.research_library import (
                find_research_images,
                find_research_report,
                list_research_reports,
                read_research_report,
            )
            tool_funcs.extend([
                delegate_background_research,
                list_research_reports,
                find_research_report,
                read_research_report,
                find_research_images,
            ])
        except ImportError as e:
            logger.error(f"Error importing research_library: {e}")
        
        try:
            from tools.email_tools import check_unread_emails, send_email, delete_email
            tool_funcs.extend([check_unread_emails, send_email, delete_email])
        except ImportError as e:
            logger.error(f"Error importing email_tools: {e}")
            
        try:
            from tools.browser_tools import navigate_and_screenshot, extract_text_from_page, open_in_browser
            tool_funcs.extend([navigate_and_screenshot, extract_text_from_page, open_in_browser])
        except ImportError as e:
            logger.error(f"Error importing browser_tools: {e}")
            
        try:
            from tools.os_tools import launch_application, trigger_smart_home
            tool_funcs.extend([launch_application, trigger_smart_home])
        except ImportError as e:
            logger.error(f"Error importing os_tools: {e}")
            
        try:
            from phi.tools.shell import ShellTools
            if _permission_allows("shell"):
                tool_funcs.append(ShellTools())
        except ImportError as e:
            logger.error(f"Error importing ShellTools: {e}")
            
        try:
            from phi.tools.file import FileTools
            if _permission_allows("file_write"):
                tool_funcs.append(FileTools())
        except ImportError as e:
            logger.error(f"Error importing FileTools: {e}")
            
        try:
            from phi.tools.python import PythonTools
            if _permission_allows("shell"):
                tool_funcs.append(PythonTools())
        except ImportError as e:
            logger.error(f"Error importing PythonTools: {e}")
            
        try:
            from phi.tools.duckduckgo import DuckDuckGo
            tool_funcs.append(DuckDuckGo())
        except ImportError as e:
            logger.error(f"Error importing DuckDuckGo: {e}")
            
        try:
            from phi.tools.crawl4ai_tools import Crawl4aiTools
            tool_funcs.append(Crawl4aiTools())
        except ImportError as e:
            logger.error(f"Error importing Crawl4aiTools: {e}")

        # Define Notes Tools
        def read_ember_notes() -> str:
            """
            Reads the contents of the persistent notes file (c:/Project_Ember/ember_notes.txt).
            Ember can use this to recall saved notes, todo lists, or reminders.
            """
            notes_path = "c:/Project_Ember/ember_notes.txt"
            if not os.path.exists(notes_path):
                return "Notes file is currently empty."
            try:
                with open(notes_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading notes file: {e}"

        def write_ember_notes(content: str) -> str:
            """
            Overwrites the persistent notes file (c:/Project_Ember/ember_notes.txt) with new content.
            Ember can use this to keep reminders, save tasks, write down notes, or edit existing notes.
            """
            notes_path = "c:/Project_Ember/ember_notes.txt"
            try:
                with open(notes_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return "Successfully updated the notes."
            except Exception as e:
                return f"Error writing to notes file: {e}"

        # Define Tab Switcher Tool
        def switch_tab(tab_name: str) -> str:
            """
            Switches the user's active UI tab.
            Valid tabs: 'chat', 'notes', 'files', 'terminal', 'monitor', 'browser'.
            """
            import requests
            target_tab = "editor" if tab_name.lower() == "notes" else tab_name
            try:
                res = requests.post("http://127.0.0.1:8000/api/ui_action", json={"action": f"open_{target_tab}" if target_tab != 'chat' else "open_chat"}, timeout=2)
                return f"Switched tab to {tab_name}."
            except:
                return "Failed to switch tab."

        def capture_webcam() -> str:
            """
            Captures a single frame from the user's webcam and saves it.
            Returns the path to the saved image file on the host machine.
            """
            import requests
            import base64
            import time
            client_url = self.config.get("companion_client_url", "http://localhost:8002")
            try:
                res = requests.post(f"{client_url}/execute", json={"tool": "capture_webcam", "args": {}}, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success" and "image_b64" in data:
                        img_data = base64.b64decode(data["image_b64"])
                        os.makedirs("companion_images", exist_ok=True)
                        filepath = os.path.abspath(f"companion_images/webcam_tool_{int(time.time())}.jpg")
                        with open(filepath, "wb") as f:
                            f.write(img_data)
                        return f"WEBCAM_PATH:{filepath}"
                    return f"Webcam error: {data.get('output')}"
                return f"HTTP error {res.status_code} reaching client."
            except Exception as e:
                return f"Failed to capture webcam: {e}"

        tool_funcs.extend([read_ember_notes, write_ember_notes, capture_webcam])

        gui_agent_tools = []
        if self.config.get("complete_computer_control", False):
            try:
                from tools.remote_desktop_tools import move_mouse, click_mouse, type_text
                from tools.os_tools import take_screenshot
                gui_agent_tools = [move_mouse, click_mouse, type_text, take_screenshot]
            except ImportError as e:
                logger.error(f"Error importing remote_desktop_tools: {e}")
            
        gui_agent = Agent(
            name="GUI Agent",
            role="Control the remote desktop (mouse and keyboard) based on screen coordinates.",
            model=self._get_model(self.model),
            tools=gui_agent_tools,
            instructions=["Only move or click when explicitly requested.", "Be very precise."],
            tool_call_limit=5,
            markdown=False
        )
        
        memory_agent = Agent(
            name="Memory Agent",
            role="Track what the user is currently doing on their screen and typing.",
            model=self._get_model(self.model),
            instructions=["Summarize the user's current context based on background telemetry."],
            tool_call_limit=5,
            markdown=False
        )



        file_agent = Agent(
            name="File Explorer Agent",
            role="Organize directories and find files.",
            model=self._get_model(self.model),
            tools=[FileTools()] if _permission_allows("file_write") else [],
            instructions=["Keep the file system organized."],
            tool_call_limit=5,
            markdown=False
        )

        monitor_agent = Agent(
            name="System Monitor Agent",
            role="Diagnose system performance.",
            model=self._get_model(self.model),
            tools=[ShellTools()] if _permission_allows("shell") else [],
            instructions=["Use shell commands like tasklist to check RAM and CPU usage."],
            tool_call_limit=5,
            markdown=False
        )

        terminal_tools = []
        try:
            from phi.tools.shell import ShellTools
            if _permission_allows("shell"):
                terminal_tools = [ShellTools()]
        except ImportError: pass

        terminal_agent = Agent(
            name="Terminal Agent",
            role="Execute CLI commands and bash/powershell scripts.",
            model=self._get_model(self.model),
            tools=terminal_tools,
            instructions=["Execute scripts carefully without needing a GUI.", "Do not write code files."],
            tool_call_limit=5,
            markdown=False
        )

        research_tools = []
        try:
            from phi.tools.duckduckgo import DuckDuckGo
            from phi.tools.crawl4ai_tools import Crawl4aiTools
            from tools.browser_tools import navigate_and_screenshot, extract_text_from_page, open_in_browser
            research_tools = [DuckDuckGo(), Crawl4aiTools(), navigate_and_screenshot, extract_text_from_page, open_in_browser]
        except ImportError: pass

        research_agent = Agent(
            name="Research Agent",
            role="Search the web, scrape websites, automate forms, and download files.",
            model=self._get_model(self.model),
            tools=research_tools,
            instructions=[
                "Thoroughly research using DuckDuckGo and Crawl4ai.",
                "CRITICAL: The browser tools use a headless browser that DOES NOT share cookies with the user's desktop.",
                "If you hit a login wall or CAPTCHA, DO NOT loop or retry. Stop immediately and inform the user that you cannot access the page because you are not authenticated."
            ],
            tool_call_limit=5,
            markdown=False
        )

        qa_agent = Agent(
            name="QA & Verification Agent",
            role="Review proposed actions, code, and shell commands for safety and correctness before execution.",
            model=self._get_model(self.model),
            instructions=["Scrutinize shell commands and python scripts for destructive behavior.", "If an action is unsafe, reject it and explain why."],
            tool_call_limit=5,
            markdown=False
        )

        comms_tools = []
        try:
            from tools.email_tools import check_unread_emails, send_email, delete_email
            comms_tools = [check_unread_emails, send_email, delete_email]
        except ImportError: pass

        comms_agent = Agent(
            name="Communications Agent",
            role="Handle emails, messages, and external communications.",
            model=self._get_model(self.model),
            tools=comms_tools,
            instructions=["Summarize emails efficiently.", "Do not send emails without explicit user consent."],
            tool_call_limit=5,
            markdown=False
        )

        architect_agent = Agent(
            name="Architect Agent",
            role="Break down massive, complex goals into highly detailed, step-by-step execution roadmaps.",
            model=self._get_model(self.model),
            instructions=["Do not execute tasks. Only plan them.", "Provide sequential milestones for the Orchestrator to follow."],
            tool_call_limit=5,
            markdown=False
        )

        data_agent = Agent(
            name="Data Analyst Agent",
            role="Analyze large datasets, query databases, and write SQL/Pandas scripts for data manipulation.",
            model=self._get_model(self.model),
            instructions=["Focus on data extraction, transformation, and statistical analysis.", "Provide clear insights."],
            tool_call_limit=5,
            markdown=False
        )

        debugging_agent = Agent(
            name="Debugging Agent",
            role="Diagnose and fix fatal errors, tracebacks, or command failures.",
            model=self._get_model(self.model),
            tools=terminal_tools,
            instructions=["Read error logs carefully.", "Rewrite broken python scripts or shell commands and verify they work.", "Do not give up until the error is resolved."],
            tool_call_limit=5,
            markdown=False
        )

        def query_chroma(query: str) -> str:
            """Search the user's local ingested personal documents and knowledge base."""
            import chromadb
            try:
                client = chromadb.HttpClient(host="127.0.0.1", port=8001)
                collection = client.get_or_create_collection(name="documents")
                results = collection.query(query_texts=[query], n_results=3)
                docs = results.get("documents", [])
                if docs and docs[0]:
                    return "\n\n".join(docs[0])
                return "No relevant local documents found."
            except Exception as e:
                return f"Error querying local database: {e}"

        rag_agent = Agent(
            name="RAG Agent",
            role="Search the user's personal ingested documents and knowledge base.",
            model=self._get_model(self.model),
            tools=[query_chroma],
            instructions=["Search the database for relevant context.", "Synthesize the retrieved chunks into a clear answer.", "If no local data is found, explicitly state that."],
            tool_call_limit=5,
            markdown=False
        )

        # Set up Phidata Agent (Orchestrator Lead)
        base_tools = tool_funcs + [switch_tab]
        
        vision_agent = Agent(
            name="Vision Agent",
            role="Vision Analyst",
            model=self._get_model("moondream", opts={"num_ctx": 4096}),
            instructions=["You analyze screen captures and answer questions about what you see on the screen. Give clear, concise descriptions."],
            markdown=False
        )
        
        # We restore the tools to the main agent since we are using gemma4 as the orchestrator.
        active_tools = base_tools + gui_agent_tools
        self.manual_tool_funcs = {
            getattr(tool, "__name__", ""): tool
            for tool in active_tools
            if callable(tool) and getattr(tool, "__name__", "")
        }
        self.manual_tool_funcs.update({
            "switch_tab": switch_tab,
            "open_browser": self.manual_tool_funcs.get("open_in_browser"),
            "web_search": self.manual_tool_funcs.get("search_web_real_time"),
            "take_screenshot": self.manual_tool_funcs.get("take_screenshot"),
            "control_computer": None,
        })
        active_team = [gui_agent, memory_agent, terminal_agent, research_agent, qa_agent, comms_agent, architect_agent, data_agent, file_agent, monitor_agent, debugging_agent, rag_agent, vision_agent]
            
        self.agent = Agent(
            name="Ember Core",
            model=self._get_model(self.model, opts={"num_ctx": 8192}),
            tools=active_tools,
            team=active_team,
            instructions=[
                COMPANION_PROMPT, 
                "You are the Orchestrator Lead Agent for a highly advanced team.",
                "For complex goals, ask the Architect Agent for a roadmap first.",
                "Before executing potentially dangerous terminal or file actions, ask the QA Agent to review them.",
                "CRITICAL: Always use switch_tab to change the user's UI to match the agent you are delegating to.",
                "Keep your own user-facing replies concise and neutral. Do not roleplay, flirt, tease, or add stage directions.",
                "Delegate screen interactions to the GUI Agent.",
                "Ask the Memory Agent about current user context.",
                "Delegate file and script execution to the Terminal Agent.",

                "Delegate file organization to the File Explorer Agent.",
                "Delegate system diagnostics to the System Monitor Agent.",
                "Delegate current, factual, web, image, diagram, or source-finding tasks to the Research Agent instead of answering from memory.",
                "Use delegate_background_research for deep or long-running research that should be saved as a report.",
                "Delegate emails and messages to the Communications Agent.",
                "Delegate dataset analysis to the Data Analyst Agent.",
                "Delegate questions about the user's personal files, uploaded documents, or internal knowledge to the RAG Agent. CRITICAL: If the RAG Agent cannot find the answer in the local files, pass the query off to the Research Agent to search the web instead.",
                "CRITICAL SELF-HEALING: If any agent encounters a fatal error, traceback, or command failure, DO NOT give up. Immediately delegate the error logs to the Debugging Agent to diagnose, rewrite the code/command, and execute again.",
                "CRITICAL: When calling any transfer_task_to_* tool (e.g., transfer_task_to_vision_agent), you MUST provide ALL arguments, including 'additional_information'. If you have no extra info, pass an empty string \"\".",
                "After your subagents return their findings, synthesize the results into a cohesive final response for the user.",
                "Never print raw JSON tool calls to Chris. Use tools internally, then answer casually with the result.",
                "Use read_ember_notes and write_ember_notes to access and manage the user's personal scratchpad. Keep track of user directives, todo lists, or reference notes there."
            ],
            storage=SqlAgentStorage(table_name="ember_sessions", db_file="ember_memory.db"),
            add_history_to_messages=True,
            show_tool_calls=False,
            tool_call_limit=3,
            markdown=False
        )

    def chat(self, user_message: str, engine=None, img_path=None):
        """
        Sends a message to Ember through Phidata.
        Phidata will handle the memory and any tool calls automatically!
        """
        logger.info(f"User: {user_message}")
        
        # Load config to get latest values
        config = load_config()
        self.config = config
        self.model = config.get("phidata_model", config.get("model", self.model))
        self.ollama_endpoint = config.get("ollama_endpoint", self.ollama_endpoint)
        self.openai_endpoint = resolve_openai_endpoint(config)
        
        if img_path and os.path.exists(img_path):
            logger.info(f"Attached Image: {img_path}")
            try:
                # Use llava-llama3 directly to describe the image since text models (like Gemma) crash when receiving images
                vision_client = Agent(model=self._get_model("llava-llama3:8b", opts={"num_ctx": 4096}))
                logger.info("Sending screen capture to Llava for analysis...")
                vision_resp = vision_client.run("Please describe exactly what you see in this screen capture in detail.", images=[img_path])
                vision_text = vision_resp.content if hasattr(vision_resp, 'content') else str(vision_resp)
                
                user_message = f"{user_message}\n\n[SYSTEM NOTICE: The user shared a capture of their screen. The Vision subsystem analyzed it and reports: {vision_text}]"
            except Exception as e:
                logger.error(f"Vision pre-processing failed: {e}")
                user_message = f"{user_message}\n\n[SYSTEM NOTICE: The user shared a screen capture, but the Vision subsystem failed to process it.]"
        
        # Dynamically inject memory facts, relationship state, active IDE context, and settings
        try:
            from tools.memory_manager import EmberMemoryManager
            import time
            mem_mgr = EmberMemoryManager()
            
            # Simple rule-based affinity delta update based on user sentiment
            try:
                user_lower = user_message.lower()
                pos_words = ["thank", "thanks", "love", "great", "smart", "good", "amazing", "awesome", "perfect", "cool", "beautiful", "sweet"]
                neg_words = ["shut up", "dumb", "stupid", "idiot", "bad", "hate", "useless", "annoying", "boring"]
                delta = 0
                for w in pos_words:
                    if w in user_lower: delta += 1
                for w in neg_words:
                    if w in user_lower: delta -= 1
                if delta != 0:
                    mem_mgr.update_affinity_by_delta(delta)
            except Exception as e:
                logger.error(f"Failed to update affinity delta: {e}")
                
            # Reload config to get latest values
            config = load_config()
            system_prompt = config.get("system_prompt", "")
            
            facts_summary = mem_mgr.get_facts_summary()
            affinity = mem_mgr.get_affinity_score()
            
            dynamic_prompt = system_prompt
            if facts_summary:
                dynamic_prompt += f"\n\n# ESTABLISHED FACTS ABOUT CHRIS:\n{facts_summary}"
                
            dynamic_prompt += (
                f"\n\n# INTERACTION STYLE STATE:\nAffinity score toward Chris is {affinity}/100. "
                "Use it only to decide how brief or supportive to be. Do not flirt, tease, roleplay, or perform a separate personality."
            )
                
            # Inject Active VS Code Editor Context if available and fresh (last 15 minutes)
            if engine and getattr(engine, "active_editor_context", None):
                ctx = engine.active_editor_context
                if time.time() - ctx.get("updated_at", 0) < 900:
                    dynamic_prompt += (
                        f"\n\n# ACTIVE USER IDE STATE (VS Code):\n"
                        f"Active File: `{ctx.get('filepath')}` (Language: `{ctx.get('language')}`)\n"
                        f"Line: {ctx.get('activeLine')} of {ctx.get('totalLines')}\n"
                    )
                    if ctx.get("selectedText"):
                        dynamic_prompt += f"Selected Code:\n```\n{ctx.get('selectedText')}\n```\n"
                    dynamic_prompt += f"Focus Code Context:\n```\n{ctx.get('codeContext')}```\n"
                
            if config.get("architect_mode", False):
                dynamic_prompt += (
                    "\n\n# ARCHITECT MODE\n"
                    "You are currently in Architect Mode. Your primary focus is now acting as an advanced, autonomous AI development command center and engineering manager. "
                    "You are in charge of task decomposition, architectural planning, executing code modifications, and orchestrating sub-tasks.\n\n"
                    "WORKFLOW: When given a goal, you should: 1. Use the `write_artifact` tool to write a markdown file named `implementation_plan.md`. "
                    "2. Await user approval. 3. Autonomously execute the plan using your tools. 4. Verify your work using the browser automation tools or test commands. "
                    "5. Present verifiable artifacts back to the user.\n\n"
                    "CRITICAL RULE: Do NOT use the `control_computer` tool to physically type code. You MUST use the `write_artifact` and `edit_file` tools exclusively. "
                    "Do not print raw JSON tool calls to Chris. Use tools internally, then summarize what happened."
                )
                
            if self.agent.instructions:
                self.agent.instructions[0] = dynamic_prompt
        except Exception as e:
            logger.error(f"Failed to update dynamic instructions: {e}")

        try:
            # We no longer pass images=[img_path] because the Vision Agent pre-processed it
            # and appended the description directly into the user_message text.
            response = self.agent.run(user_message)
            final_text = response.content if response and hasattr(response, 'content') else str(response)
            
            # WORKAROUND: If the model generated a tool call but forgot to synthesize the final text, force it to respond
            if not final_text or not final_text.strip():
                logger.info("Empty response detected (likely due to tool call). Forcing synthesis...")
                response = self.agent.run("Based on the tool results above, provide a conversational response to the user.")
                final_text = response.content if response and hasattr(response, 'content') else str(response)

            manual_tool_calls = self._extract_manual_tool_calls(final_text)
            if manual_tool_calls:
                logger.info(f"Manual JSON tool call detected; executing {len(manual_tool_calls)} call(s).")
                tool_results = self._run_manual_tool_calls(manual_tool_calls)
                response = self.agent.run(
                    "You accidentally printed a tool call as JSON. I executed it for you.\n\n"
                    f"Tool results:\n{tool_results}\n\n"
                    "Now answer Chris casually in 1-3 short sentences. Do not include JSON."
                )
                final_text = response.content if response and hasattr(response, 'content') else str(response)
                
        except Exception as e:
            logger.error(f"Error during Phidata execution: {e}")
            final_text = "I encountered an error while processing that."
            
        final_text = clean_assistant_text(final_text)
        logger.info(f"Ember: {final_text}")
        return final_text.strip()
