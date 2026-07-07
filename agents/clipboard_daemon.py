import os
import sys
import json
import time
import asyncio
import argparse
import requests
import websockets
import pyperclip

# Load config
CONFIG_PATH = "ember_config.json"
def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

config = load_config()


def _host_from_url(url):
    if not isinstance(url, str) or "://" not in url:
        return None
    try:
        return url.split("://", 1)[1].split(":", 1)[0].split("/", 1)[0]
    except Exception:
        return None


def resolve_api_host(config):
    api_host = config.get("api_host")
    if api_host:
        return api_host.rstrip("/")

    for key in ("llama_server_url", "chroma_server_url", "companion_client_url"):
        host = _host_from_url(config.get(key))
        if host and host not in {"127.0.0.1", "localhost", "0.0.0.0"}:
            return f"http://{host}:8000"

    return "http://127.0.0.1:8000"

# Defaults
DEFAULT_API_HOST = resolve_api_host(config)
DEFAULT_API_KEY = "ember-secret-key-123"

# Setup command line arguments
parser = argparse.ArgumentParser(description="E.M.B.E.R. Clipboard Sync Daemon")
parser.add_argument("--api-host", default=DEFAULT_API_HOST, help="API server root URL")
parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="Ember API Secret Key")
parser.add_argument("--source", default="host", choices=["host", "client"], help="Clipboard source identifier")
args = parser.parse_args()

api_host = args.api_host.rstrip("/")
api_key = args.api_key
source = args.source

print(f"[*] Starting Ember Clipboard Sync Daemon...")
print(f"[*] API Host: {api_host}")
print(f"[*] API Key: {api_key}")
print(f"[*] Source: {source}")

last_clipboard_val = ""

# Function to post to clipboard_sync endpoint
def post_clipboard(text):
    try:
        url = f"{api_host}/clipboard_sync"
        res = requests.post(
            url,
            json={"text": text, "source": source},
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=5
        )
        if res.status_code == 200:
            print(f"[->] Synced local clipboard change to backend (length: {len(text)})")
        else:
            print(f"[!] Sync request failed with status: {res.status_code}")
    except Exception as e:
        print(f"[!] Error posting clipboard: {e}")

# Task 1: Poll local clipboard changes and post them to API
async def clipboard_watcher():
    global last_clipboard_val
    try:
        # Initialize last_clipboard_val with current clipboard value to avoid sending history on startup
        last_clipboard_val = pyperclip.paste()
    except Exception:
        last_clipboard_val = ""

    while True:
        try:
            current_val = pyperclip.paste()
            if current_val and current_val != last_clipboard_val:
                last_clipboard_val = current_val
                # Run post_clipboard in a separate thread to avoid blocking the event loop
                await asyncio.to_thread(post_clipboard, current_val)
        except Exception as e:
            print(f"[!] Error reading clipboard: {e}")
        await asyncio.sleep(1.0)

# Task 2: Connect to WS endpoint and receive clipboard updates
async def websocket_listener():
    global last_clipboard_val
    ws_host = api_host.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_host}/ws"
    
    while True:
        try:
            print(f"[*] Connecting to WebSocket: {ws_url}")
            async with websockets.connect(ws_url) as websocket:
                # 1. Authenticate immediately as expected by backend
                await websocket.send(json.dumps({"api_key": api_key}))
                print("[*] WebSocket authenticated successfully!")
                
                # 2. Listen for events
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "ui_action":
                            action_data = json.loads(data.get("data", "{}"))
                            if action_data.get("action") == "sync_clipboard":
                                rx_text = action_data.get("text", "")
                                rx_source = action_data.get("source", "")
                                
                                # Do not write back if it originated from ourselves
                                if rx_source != source and rx_text != last_clipboard_val:
                                    print(f"[<-] Received clipboard sync from {rx_source} (length: {len(rx_text)})")
                                    last_clipboard_val = rx_text
                                    pyperclip.copy(rx_text)
                    except Exception as e:
                        print(f"[!] Error handling WS message: {e}")
        except Exception as e:
            print(f"[!] WebSocket connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5.0)

async def main():
    await asyncio.gather(
        clipboard_watcher(),
        websocket_listener()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Clipboard daemon stopped by user.")
        sys.exit(0)
