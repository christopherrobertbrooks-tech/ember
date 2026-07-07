import os
import sys
import json
import time
import subprocess
import signal

CONFIG_PATH = "ember_config.json"
processes = []

# --- Tailscale permanent IPs ---
HOST_IP = "100.100.150.74"   # Server PC (runs LM Studio + Ember backend)
CLIENT_IP = "100.119.115.117" # Main PC (runs the desktop client)

def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=========================================================")
    print("                 E.M.B.E.R. LAUNCHER                     ")
    print("=========================================================")
    print("")

def update_config_host(is_host, client_ip=None):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        if is_host:
            config["chroma_server_host"] = True
            config["chroma_server_url"] = "http://127.0.0.1:8001"
            # Point LLM at LM Studio running on this host
            config["llama_server_url"] = f"http://{HOST_IP}:1234/v1"
            # Tell Ember where its desktop client is calling from
            config["companion_client_url"] = f"http://{CLIENT_IP}:8002"
        else:
            config["chroma_server_host"] = False
            if client_ip:
                config["chroma_server_url"] = f"http://{client_ip}:8001"
            
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            
        host_ip = config.get("chroma_server_url", "http://127.0.0.1:8001").split("://")[1].split(":")[0]
        
        # 1. (Vite Config is now dynamically read from ember_config.json, no patching needed!)
                
        # 2. Update Wake Word Listener
        ww_path = "wake_word_listener.py"
        if os.path.exists(ww_path):
            with open(ww_path, "r", encoding="utf-8") as f:
                ww_content = f.read()
            import re
            ww_content = re.sub(r'API_URL = "http://[^"]+"/api/remote_command', f'API_URL = "http://{HOST_IP}:8000/api/remote_command"', ww_content)
            with open(ww_path, "w", encoding="utf-8") as f:
                f.write(ww_content)
                
    except Exception as e:
        print(f"Warning: Could not update config: {e}")

def spawn_process(name, cmd_list, cwd=None, quiet=False):
    print(f"[*] Starting {name}...")
    try:
        # Create a new process group so we can kill the whole tree easily on Windows
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        kwargs = {
            "cwd": cwd,
            "creationflags": flags
        }
        if quiet:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL
            if sys.platform == 'win32':
                kwargs["creationflags"] |= 0x08000000 # CREATE_NO_WINDOW
                
        p = subprocess.Popen(cmd_list, **kwargs)
        processes.append((name, p))
    except Exception as e:
        print(f"[!] Failed to start {name}: {e}")

def kill_all_processes():
    print("\n[!] Shutting down all Ember components safely...")
    for name, p in processes:
        print(f"    Stopping {name} (PID: {p.pid})...")
        try:
            if sys.platform == 'win32':
                # Force kill the process tree to prevent locking
                os.system(f"taskkill /F /T /PID {p.pid} >nul 2>&1")
            else:
                p.terminate()
        except Exception:
            pass
    print("Shutdown complete. Goodbye!")
    sys.exit(0)

def main():
    # Setup signal handlers for graceful exit
    signal.signal(signal.SIGINT, lambda s, f: kill_all_processes())
    signal.signal(signal.SIGTERM, lambda s, f: kill_all_processes())

    print_header()
    print("Please select deployment mode:")
    print("  [1] Host PC Mode     (Runs the Brain: API & Database Server)")
    print("  [2] Client PC Mode   (Runs the Body: Desktop UI & Background Agents)")
    print("  [3] Standalone Mode  (Runs Everything on a single PC)")
    print("")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice not in ["1", "2", "3"]:
        print("Invalid choice. Exiting.")
        return

    print_header()
    
    if choice == "1":
        print("Deploying HOST PC Architecture...")
        update_config_host(True)
        # Note: Ollama runs as a background service on Windows, so no need to launch it manually.
        spawn_process("ChromaDB Server", ["chroma", "run", "--path", "data/chroma", "--host", "0.0.0.0", "--port", "8001"], quiet=True)
        spawn_process("Ember API Engine", [sys.executable, "ember_api.py"])
        spawn_process("Ember Web Client (PWA)", ["cmd", "/c", "npm run dev"], cwd="clients/ember-web-client")
        spawn_process("Host Clipboard Daemon", [sys.executable, "agents/clipboard_daemon.py", "--source", "host"])
        
    elif choice == "2":
        print("Deploying CLIENT PC Architecture...")
        print(f"\n[*] Using hardcoded Tailscale Host IP: {HOST_IP}")
        update_config_host(False, HOST_IP)
        spawn_process("Librarian Agent", [sys.executable, "agents/ingestion_agent.py"])
        spawn_process("Iron Man Agent", [sys.executable, "wake_word_listener.py"])
        
        # Give agents a second to initialize
        time.sleep(1)
        
        # Launch Vite UI using cmd /c to bypass execution policies
        spawn_process("Ember Desktop Client", ["cmd", "/c", "npm run electron:dev"], cwd="clients/ember-desktop-client")
        
    elif choice == "3":
        print("Deploying STANDALONE Architecture...")
        update_config_host(True)
        spawn_process("ChromaDB Server", ["chroma", "run", "--path", "data/chroma", "--host", "0.0.0.0", "--port", "8001"], quiet=True)
        spawn_process("Ember API Engine", [sys.executable, "ember_api.py"])
        spawn_process("Librarian Agent", [sys.executable, "agents/ingestion_agent.py"])
        spawn_process("Iron Man Agent", [sys.executable, "wake_word_listener.py"])
        time.sleep(3) # Give API time to start
        spawn_process("Ember Desktop Client", ["cmd", "/c", "npm run electron:dev"], cwd="clients/ember-desktop-client")
        
    print("\n=========================================================")
    print(" ALL SYSTEMS GO. DO NOT CLOSE THIS WINDOW.")
    print(" Press Ctrl+C in this terminal to gracefully shut down.")
    print("=========================================================\n")

    # Keep the main thread alive to catch Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        kill_all_processes()

if __name__ == "__main__":
    main()
