import base64
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from ember_app.auth import get_api_key
from ember_app.state import get_state
from tools.permission_gate import describe_permission_error, guard


router = APIRouter()


class ImageRequest(BaseModel):
    prompt: str


@router.post("/generate_image")
async def generate_image_endpoint(request: ImageRequest, api_key: str = Depends(get_api_key)):
    try:
        image_base64 = get_state().engine.generate_image(request.prompt)
        if not image_base64:
            raise HTTPException(status_code=500, detail="Image generation failed")
        return {"image_base64": image_base64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capture_webcam")
async def capture_webcam_endpoint(api_key: str = Depends(get_api_key)):
    try:
        guard("webcam", "capture_webcam_endpoint", source="api", payload={})
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))

    client_url = get_state().engine.config.get("companion_client_url", "http://localhost:8002")
    try:
        import requests

        res = requests.post(f"{client_url}/execute", json={"tool": "capture_webcam", "args": {}}, timeout=20)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return {"image_base64": data.get("image_b64")}
            raise HTTPException(status_code=500, detail=data.get("output", "Webcam capture failed"))
        raise HTTPException(status_code=500, detail=f"Webcam worker error: {res.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to capture webcam: {e}")


@router.post("/upload_document")
async def upload_document_endpoint(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    ingest_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ingest"))
    os.makedirs(ingest_dir, exist_ok=True)
    filepath = os.path.join(ingest_dir, file.filename)
    try:
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        return {"status": "success", "filepath": filepath}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {e}")


@router.get("/screenshot")
async def screenshot_endpoint(api_key: str = Depends(get_api_key)):
    try:
        guard("screenshot", "screenshot_endpoint", source="api", payload={})
        from PIL import ImageGrab
        import io

        img = ImageGrab.grab()
        img = img.convert("RGB")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return {"image_base64": b64}
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))
