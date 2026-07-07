import json
import time
import websocket
import threading

try:
    import pyautogui
except ImportError:
    print("pyautogui not installed. Please run 'pip install pyautogui websocket-client'")
    exit(1)

# Fail-safe to avoid out-of-control mouse movements
pyautogui.FAILSAFE = True
# Small pause after every pyautogui call
pyautogui.PAUSE = 0.1

WS_URL = "ws://127.0.0.1:5199/ws"

def on_message(ws, message):
    try:
        data = json.loads(message)
        if data.get("type") == "ui_action":
            action_data = data.get("data", {})
            if isinstance(action_data, str):
                action_data = json.loads(action_data)
                
            action = action_data.get("action")
            
            if action == "mouse_move":
                x = action_data.get("x", 0)
                y = action_data.get("y", 0)
                print(f"Moving mouse to ({x}, {y})")
                pyautogui.moveTo(x, y)
                
            elif action == "mouse_click":
                button = action_data.get("button", "left")
                print(f"Clicking mouse ({button})")
                pyautogui.click(button=button)
                
            elif action == "keyboard_type":
                text = action_data.get("text", "")
                print(f"Typing text: {text}")
                pyautogui.write(text, interval=0.05)
                
    except Exception as e:
        print(f"Error processing message: {e}")

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket connection closed. Retrying in 5 seconds...")
    time.sleep(5)
    connect()

def on_open(ws):
    print("Connected to Ember Server.")
    # Send a handshake to let it know we are the automation daemon
    ws.send(json.dumps({"api_key": "ember-secret-key-123", "client_type": "automation_daemon"}))

def connect():
    ws = websocket.WebSocketApp(WS_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    ws.run_forever()

if __name__ == "__main__":
    print("Starting Ember Client Automation Daemon...")
    print("Move mouse to any corner of the screen to trigger FAILSAFE and abort.")
    connect()
