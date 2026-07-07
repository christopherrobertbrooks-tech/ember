import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ember_app.auth import get_api_key
from ember_app.state import get_state
from tools.permission_gate import describe_permission_error, guard


router = APIRouter()


class ClipboardSyncRequest(BaseModel):
    text: str
    source: str


@router.post("/clipboard_sync")
async def clipboard_sync(request: ClipboardSyncRequest, api_key: str = Depends(get_api_key)):
    try:
        category = "clipboard_write" if request.source == "client" else "clipboard_read"
        guard(category, "clipboard_sync", source=request.source, payload={"text": request.text, "source": request.source})
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))

    if request.source == "client":
        try:
            import pyperclip
            pyperclip.copy(request.text)
        except Exception as e:
            print(f"Failed to set host clipboard: {e}")

    for ws in list(get_state().active_websockets):
        try:
            await ws.send_json({
                "type": "ui_action",
                "data": json.dumps({
                    "action": "sync_clipboard",
                    "text": request.text,
                    "source": request.source,
                }),
            })
        except Exception:
            pass
    return {"status": "success"}
