import requests


def focus_tab(tab_name: str, **data) -> None:
    action = "open_chat" if tab_name == "chat" else f"open_{tab_name}"
    payload = {"action": action}
    payload.update({k: v for k, v in data.items() if v is not None})
    try:
        requests.post("http://127.0.0.1:8000/api/ui_action", json=payload, timeout=1)
    except Exception:
        pass
