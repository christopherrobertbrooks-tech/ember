import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ember_app.auth import get_api_key
from tools.permission_gate import describe_permission_error, guard


router = APIRouter()


class FileWriteRequest(BaseModel):
    content: str


@router.get("/files")
async def api_files(path: str = ".", api_key: str = Depends(get_api_key)):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    try:
        items = []
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            is_dir = os.path.isdir(full_path)
            size = os.path.getsize(full_path) if not is_dir else 0
            items.append({"name": name, "path": full_path, "isDirectory": is_dir, "size": size})
        items.sort(key=lambda x: (not x["isDirectory"], x["name"].lower()))
        return {"items": items, "currentPath": os.path.abspath(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/read")
async def api_files_read(path: str, api_key: str = Depends(get_api_key)):
    try:
        guard("file_read", "files_read", source="api", payload={"path": path})
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/write")
async def api_files_write(path: str, request: FileWriteRequest, api_key: str = Depends(get_api_key)):
    try:
        guard("file_write", "files_write", source="api", payload={"path": path})
        with open(path, "w", encoding="utf-8") as f:
            f.write(request.content)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))
