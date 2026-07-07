import os

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader


API_KEY = os.getenv("EMBER_API_KEY", "ember-secret-key-123")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def get_api_key(api_key_header_value: str = Security(api_key_header)):
    if api_key_header_value == API_KEY:
        return api_key_header_value
    raise HTTPException(status_code=403, detail="Could not validate API key")
