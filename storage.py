"""
Storage module for PathForge application.
Handles Supabase Storage operations for file uploads and retrieval.
"""
from urllib.parse import quote
from flask import g
from datetime import datetime, timezone

from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from auth import sb_headers_service
from supabase_connection import get_supabase_session

# ============================================================
# Supabase Storage
# ============================================================
def storage_upload(bucket: str, path: str, file_bytes: bytes, content_type: str):
    """Upload a file to Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": content_type or "application/octet-stream",
        "x-upsert": "true",
    }
    return requests.put(url, headers=headers, data=file_bytes, timeout=180)

def storage_list(bucket: str, prefix: str):
    """
    List files in a Supabase Storage bucket with caching.
    Uses request-level cache to avoid repeated API calls.
    """
    # Check request-level cache
    cache_key = f"storage_list_{bucket}_{prefix}"
    if hasattr(g, cache_key):
        cached_response = getattr(g, cache_key)
        # Return a mock response object with cached data
        class CachedResponse:
            def __init__(self, data):
                self.status_code = 200
                self._json = data
            def json(self):
                return self._json
        return CachedResponse(cached_response)

    # Make API call with optimized timeout (5 seconds connect, 10 seconds read)
    url = f"{SUPABASE_URL}/storage/v1/object/list/{bucket}"
    payload = {"prefix": prefix, "limit": 100, "offset": 0, "sortBy": {"column": "name", "order": "asc"}}

    try:
        session = get_supabase_session()
        response = session.post(url, headers=sb_headers_service(), json=payload, timeout=(2, 8))

        # Cache successful responses
        if response.status_code < 400:
            setattr(g, cache_key, response.json())

        return response
    except Exception as e:
        # Return empty list on error to avoid blocking page load
        print(f"Storage list error for {bucket}/{prefix}: {e}")
        class ErrorResponse:
            def __init__(self):
                self.status_code = 500
            def json(self):
                return []
        return ErrorResponse()

def storage_signed_url(bucket: str, path: str, expires_in_seconds: int = 3600):
    """Generate a signed URL for accessing a file in Supabase Storage."""
    safe_path = quote(path)
    url = f"{SUPABASE_URL}/storage/v1/object/sign/{bucket}/{safe_path}"
    return requests.post(url, headers=sb_headers_service(), json={"expiresIn": expires_in_seconds}, timeout=30)

def storage_delete(bucket: str, paths: list):
    """Delete files from Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}"
    return requests.delete(url, headers=sb_headers_service(), json={"prefixes": paths}, timeout=30)
