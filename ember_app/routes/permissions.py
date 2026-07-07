from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ember_app.auth import get_api_key
from tools.permission_gate import (
    get_state as get_permission_state,
    resolve_request,
    update_policy,
)


router = APIRouter()


class PermissionPolicyRequest(BaseModel):
    category: str
    policy: str


class PermissionResolveRequest(BaseModel):
    request_id: str
    decision: str


@router.get("/permissions")
async def get_permissions(api_key: str = Depends(get_api_key)):
    return get_permission_state()


@router.post("/permissions/policy")
async def set_permission_policy(request: PermissionPolicyRequest, api_key: str = Depends(get_api_key)):
    try:
        return update_policy(request.category, request.policy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/permissions/resolve")
async def resolve_permission_request(request: PermissionResolveRequest, api_key: str = Depends(get_api_key)):
    try:
        return resolve_request(request.request_id, request.decision)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
