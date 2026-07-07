import json
import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ember_app.auth import get_api_key
from ember_app.state import get_state


router = APIRouter()


class SettingsRequest(BaseModel):
    voice: Optional[str] = None
    sd_api_url: Optional[str] = None
    system_prompt: Optional[str] = None
    dnd_enabled: Optional[bool] = None
    game_mode: Optional[bool] = None
    architect_mode: Optional[bool] = None
    complete_computer_control: Optional[bool] = None


class EditorContextRequest(BaseModel):
    filepath: str
    language: str
    activeLine: int
    totalLines: int
    selectedText: Optional[str] = ""
    codeContext: str


class RelationshipUpdateRequest(BaseModel):
    score: int


@router.get("/settings")
async def get_settings(api_key: str = Depends(get_api_key)):
    engine = get_state().engine
    return {
        "voice": engine.voice,
        "sd_api_url": engine.sd_api_url,
        "system_prompt": getattr(engine, "system_prompt", ""),
        "dnd_enabled": getattr(engine, "dnd_enabled", False),
        "game_mode": getattr(engine, "game_mode", False),
        "architect_mode": getattr(engine, "architect_mode", False),
        "complete_computer_control": getattr(engine, "complete_computer_control", False),
    }


@router.post("/settings")
async def update_settings(request: SettingsRequest, api_key: str = Depends(get_api_key)):
    engine = get_state().engine
    if request.voice:
        engine.voice = request.voice
    if request.sd_api_url:
        engine.sd_api_url = request.sd_api_url
    if request.system_prompt is not None:
        engine.set_system_prompt(request.system_prompt)
    if request.dnd_enabled is not None:
        engine.dnd_enabled = request.dnd_enabled
    if request.game_mode is not None:
        engine.game_mode = request.game_mode
    if request.architect_mode is not None:
        engine.set_architect_mode(request.architect_mode)
    if request.complete_computer_control is not None:
        if hasattr(engine, "set_complete_computer_control"):
            engine.set_complete_computer_control(request.complete_computer_control)
        else:
            engine.complete_computer_control = request.complete_computer_control
            engine.config["complete_computer_control"] = request.complete_computer_control
            try:
                from tools.permission_gate import update_policy
                update_policy("keyboard_mouse", "allow" if request.complete_computer_control else "ask")
            except Exception:
                pass

    config = engine.config
    config["voice"] = engine.voice
    config["sd_api_url"] = engine.sd_api_url
    config["dnd_enabled"] = getattr(engine, "dnd_enabled", False)
    config["game_mode"] = getattr(engine, "game_mode", False)
    config["architect_mode"] = getattr(engine, "architect_mode", False)
    config["complete_computer_control"] = getattr(engine, "complete_computer_control", False)
    with open("ember_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    return {"status": "success"}


@router.post("/wipe_memory")
async def wipe_memory(api_key: str = Depends(get_api_key)):
    engine = get_state().engine
    if engine.chroma_client:
        try:
            engine.chroma_client.delete_collection("conversations")
            engine.chroma_client.delete_collection("documents")
        except Exception:
            pass
        engine.mem_collection = engine.chroma_client.get_or_create_collection(name="conversations")
        engine.doc_collection = engine.chroma_client.get_or_create_collection(name="documents")
    engine.chat_context = [engine.chat_context[0]]
    return {"status": "wiped"}


@router.get("/api/tasks")
async def get_tasks(api_key: str = Depends(get_api_key)):
    return {"tasks": getattr(get_state().engine, "active_tasks", [])}


@router.post("/editor_context")
async def update_editor_context(request: EditorContextRequest, api_key: str = Depends(get_api_key)):
    get_state().engine.active_editor_context = {
        "filepath": request.filepath,
        "language": request.language,
        "activeLine": request.activeLine,
        "totalLines": request.totalLines,
        "selectedText": request.selectedText,
        "codeContext": request.codeContext,
        "updated_at": time.time(),
    }
    return {"status": "success"}


@router.get("/diary")
async def get_diary(api_key: str = Depends(get_api_key)):
    from tools.memory_manager import EmberMemoryManager

    mem_mgr = EmberMemoryManager()
    entries = mem_mgr.get_diary_entries(limit=10)
    return {"entries": [{"date": r[0], "summary": r[1], "mood": r[2]} for r in entries]}


@router.get("/relationship")
async def get_relationship(api_key: str = Depends(get_api_key)):
    from tools.memory_manager import EmberMemoryManager

    mem_mgr = EmberMemoryManager()
    return {"affinity_score": mem_mgr.get_affinity_score()}


@router.post("/relationship")
async def update_relationship(request: RelationshipUpdateRequest, api_key: str = Depends(get_api_key)):
    from tools.memory_manager import EmberMemoryManager

    mem_mgr = EmberMemoryManager()
    mem_mgr.set_affinity_score(request.score)
    return {"status": "success", "affinity_score": mem_mgr.get_affinity_score()}
