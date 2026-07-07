import json
import os
import time
import uuid
from typing import Any, Dict, Optional, Tuple


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMISSIONS_PATH = os.path.join(ROOT_DIR, "ember_permissions.json")

DEFAULT_POLICIES = {
    "browser_open": "allow",
    "email_read": "allow",
    "file_read": "allow",
    "screenshot": "ask",
    "webcam": "ask",
    "clipboard_read": "ask",
    "clipboard_write": "ask",
    "file_write": "ask",
    "keyboard_mouse": "ask",
    "launch_app": "ask",
    "shell": "ask",
    "terminal": "ask",
    "email_send": "ask",
    "email_delete": "ask",
    "smart_home": "ask",
    "system_power": "ask",
}

DEFAULT_CONFIG = {
    "enabled": True,
    "policies": DEFAULT_POLICIES,
    "trusted_sources": ["local_ui", "desktop_client", "web_client", "vscode", "model_tool"],
    "approved_once": [],
    "pending": [],
    "history": [],
}


class PermissionDenied(Exception):
    pass


class PermissionRequired(Exception):
    def __init__(self, request_id: str, category: str, reason: str):
        self.request_id = request_id
        self.category = category
        self.reason = reason
        super().__init__(reason)


def _read_config() -> Dict[str, Any]:
    if not os.path.exists(PERMISSIONS_PATH):
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        with open(PERMISSIONS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception:
        loaded = {}

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config.update({k: v for k, v in loaded.items() if k not in ("policies",)})
    config["policies"].update(loaded.get("policies", {}))
    config["approved_once"] = loaded.get("approved_once", [])
    config["pending"] = loaded.get("pending", [])
    config["history"] = loaded.get("history", [])
    return config


def _write_config(config: Dict[str, Any]) -> None:
    with open(PERMISSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def _summarize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return {}

    summary = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > 300:
            summary[key] = value[:300] + "..."
        else:
            summary[key] = value
    return summary


def check_permission(
    category: str,
    action: str,
    source: str = "model_tool",
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    config = _read_config()
    if not config.get("enabled", True):
        return True, None

    policy = config.get("policies", {}).get(category, "ask")
    if policy == "allow":
        return True, None

    payload_summary = _summarize_payload(payload)
    signature = {
        "category": category,
        "action": action,
        "payload": payload_summary,
    }

    approved_once = config.get("approved_once", [])
    remaining_once = []
    matched_once = False
    for approval in approved_once:
        if not matched_once and approval.get("signature") == signature:
            matched_once = True
        else:
            remaining_once.append(approval)
    if matched_once:
        config["approved_once"] = remaining_once
        _write_config(config)
        return True, None

    if policy == "deny":
        raise PermissionDenied(f"Permission denied for {category}: {action}")

    request_id = str(uuid.uuid4())
    request = {
        "id": request_id,
        "category": category,
        "action": action,
        "source": source,
        "payload": payload_summary,
        "signature": signature,
        "status": "pending",
        "created_at": time.time(),
    }

    pending = config.setdefault("pending", [])
    pending.append(request)
    config["pending"] = pending[-50:]
    _write_config(config)

    raise PermissionRequired(
        request_id,
        category,
        f"Permission required for {category}: {action}. Request id: {request_id}",
    )


def guard(
    category: str,
    action: str,
    source: str = "model_tool",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    check_permission(category, action, source=source, payload=payload)


def describe_permission_error(error: Exception) -> str:
    if isinstance(error, PermissionRequired):
        return (
            f"Permission required before I can do that. "
            f"Category: {error.category}. Request id: {error.request_id}."
        )
    if isinstance(error, PermissionDenied):
        return str(error)
    return str(error)


def get_state() -> Dict[str, Any]:
    return _read_config()


def update_policy(category: str, policy: str) -> Dict[str, Any]:
    if policy not in {"allow", "ask", "deny"}:
        raise ValueError("policy must be one of: allow, ask, deny")
    config = _read_config()
    config.setdefault("policies", {})[category] = policy
    _write_config(config)
    return config


def resolve_request(request_id: str, decision: str) -> Dict[str, Any]:
    if decision not in {"approved", "denied"}:
        raise ValueError("decision must be approved or denied")

    config = _read_config()
    pending = config.get("pending", [])
    match = None
    remaining = []
    for request in pending:
        if request.get("id") == request_id:
            match = request
        else:
            remaining.append(request)

    if not match:
        raise KeyError(f"No pending permission request found for id {request_id}")

    match["status"] = decision
    match["resolved_at"] = time.time()
    config["pending"] = remaining
    if decision == "approved":
        config.setdefault("approved_once", []).append({
            "request_id": request_id,
            "signature": match.get("signature"),
            "created_at": time.time(),
        })
        config["approved_once"] = config["approved_once"][-50:]
    config.setdefault("history", []).append(match)
    config["history"] = config["history"][-200:]
    _write_config(config)
    return match
