import requests
from tools.permission_gate import describe_permission_error, guard

def _send_ui_action(action_data: dict) -> str:
    try:
        guard("keyboard_mouse", action_data.get("action", "remote_desktop_action"), payload=action_data)
        res = requests.post("http://127.0.0.1:8000/api/ui_action", json=action_data, timeout=2)
        if res.status_code == 200:
            clients = res.json().get("clients_messaged", 0)
            if clients > 0:
                return f"Successfully sent {action_data['action']} command to {clients} connected client(s)."
            else:
                return "No clients connected to receive the UI action."
        else:
            return f"API responded with error: {res.status_code}"
    except Exception as e:
        return f"API unreachable: {describe_permission_error(e)}"

def move_mouse(x: int, y: int) -> str:
    """
    Moves the mouse on the client's screen to the specified X and Y coordinates.
    
    Args:
        x: The X coordinate.
        y: The Y coordinate.
    """
    return _send_ui_action({"action": "mouse_move", "x": x, "y": y})

def click_mouse(button: str = "left") -> str:
    """
    Clicks the mouse on the client's screen at the current location.
    
    Args:
        button: The button to click ("left", "right", or "middle").
    """
    return _send_ui_action({"action": "mouse_click", "button": button})

def type_text(text: str) -> str:
    """
    Types text on the client's screen as if coming from a keyboard.
    
    Args:
        text: The text to type.
    """
    return _send_ui_action({"action": "keyboard_type", "text": text})
