import json
import os
import tempfile
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ember_app.auth import get_api_key
from ember_app.state import get_state


router = APIRouter()


@router.get("/download-update")
async def download_update():
    target_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    temp_zip = tempfile.mktemp(suffix=".zip")

    with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(target_dir):
            for excluded in ["node_modules", "dist", "myenv", ".git", ".gemini", "chroma_db", "__pycache__"]:
                if excluded in dirs:
                    dirs.remove(excluded)
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, target_dir)
                zipf.write(file_path, arcname)

    return FileResponse(temp_zip, media_type="application/zip", filename="ember-desktop-client-update.zip")


@router.get("/models")
async def get_models(api_key: str = Depends(get_api_key)):
    import requests as req

    try:
        with open("ember_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        lm_url = cfg.get("lm_studio_endpoint", "http://100.100.150.74:1234/v1")
        current_model = cfg.get("model", "google/gemma-4-e4b:2")
    except Exception:
        lm_url = "http://100.100.150.74:1234/v1"
        current_model = "google/gemma-4-e4b:2"

    try:
        res = req.get(f"{lm_url}/models", timeout=3)
        res.raise_for_status()
        data = res.json().get("data", [])
        model_names = [m.get("id", "") for m in data if m.get("id")]
        return {"models": model_names or [current_model]}
    except Exception:
        return {"models": [current_model]}


@router.get("/api/lmstudio_status")
async def lmstudio_status(api_key: str = Depends(get_api_key)):
    import requests

    try:
        with open("ember_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        lm_url = cfg.get("lm_studio_endpoint", "http://100.100.150.74:1234/v1")
    except Exception:
        lm_url = "http://100.100.150.74:1234/v1"

    try:
        res = requests.get(f"{lm_url}/models", timeout=3)
        models = res.json().get("data", []) if res.ok else []
        return {
            "status": "ok",
            "available": res.ok,
            "endpoint": lm_url,
            "models": [m.get("id") for m in models],
        }
    except Exception as e:
        return {"status": "error", "available": False, "endpoint": lm_url, "detail": str(e)}


@router.get("/api/engine_status")
async def engine_status(api_key: str = Depends(get_api_key)):
    engine = get_state().engine
    return {
        "voice": getattr(engine, "voice", None),
        "architect_mode": getattr(engine, "architect_mode", False),
        "game_mode": getattr(engine, "game_mode", False),
        "dnd_enabled": getattr(engine, "dnd_enabled", False),
    }
