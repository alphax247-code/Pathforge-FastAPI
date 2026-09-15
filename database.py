"""
Database module for PathForge application.
Handles Supabase database operations for user profiles and progress tracking.
"""
from datetime import date, datetime, timezone
from flask import g, session

from config import SUPABASE_URL
from auth import get_current_user, sb_headers_service, sb_headers_user
from supabase_connection import get_supabase_session

CURRENT_ONBOARDING_VERSION = 2

# ============================================================
# Supabase DB (REST): onboarding + progress + personal info
# Table: public.user_profile
# ============================================================
def rest_url(table: str) -> str:
    """Build REST API URL for a table."""
    return f"{SUPABASE_URL}/rest/v1/{table}"

def is_onboarding_complete(profile: dict | None) -> bool:
    """Return True only when the full onboarding assessment was saved."""
    if not isinstance(profile, dict) or profile.get("onboarding_completed") is not True:
        return False
    if not str(profile.get("name") or "").strip() or profile.get("age") is None:
        return False

    assessment = profile.get("assessment_json")
    if not isinstance(assessment, dict) or not assessment.get("completedAt"):
        return False
    if assessment.get("onboardingVersion") != CURRENT_ONBOARDING_VERSION:
        return False

    for section in ("attachment", "archetype", "shadow"):
        result = assessment.get(section)
        if not isinstance(result, dict) or not result.get("dominant"):
            return False
    return True

def get_profile_row(user_id: str, use_service_role: bool = False):
    """
    Get a user profile row by user_id.

    Args:
        user_id: The user's UUID
        use_service_role: If True, uses service role key (bypasses RLS and token expiration).
                         If False, uses user's access token (subject to RLS).
    """
    url = rest_url("user_profile")
    params = {"user_id": f"eq.{user_id}", "select": "*"}
    headers = sb_headers_service() if use_service_role else sb_headers_user()

    # Use persistent session with connection pooling for faster requests
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return None, r
    rows = r.json() or []
    return (rows[0] if rows else None), r

def upsert_profile_row(payload: dict, use_service_role: bool = False):
    """
    Upsert a user profile row.

    Args:
        payload: Dictionary containing the profile data
        use_service_role: If True, uses service role key (bypasses RLS).
                         If False, uses user's access token (subject to RLS).
    """
    url = rest_url("user_profile")
    headers = sb_headers_service() if use_service_role else sb_headers_user()
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    params = {"on_conflict": "user_id"}
    # Use persistent session with connection pooling for faster requests
    session = get_supabase_session()
    return session.post(url, headers=headers, params=params, json=payload, timeout=(2, 8))

def ensure_profile_exists():
    """
    Ensure a user profile exists, creating it if necessary.
    Uses multi-level caching for performance:
    1. Request-level cache (flask.g) - lasts for single request
    2. Session cache - lasts for session duration
    3. Database fetch - only when cache misses
    """
    u = get_current_user()
    if not u:
        return None
    user_id = u.get("id")

    # Level 1: Check request-level cache (fastest)
    cache_key = f"profile_{user_id}"
    if hasattr(g, cache_key):
        return getattr(g, cache_key)

    # Level 2: Check session cache (fast)
    session_cache_key = f"cached_profile_{user_id}"
    if session_cache_key in session:
        cached_profile = session[session_cache_key]
        # Validate cache isn't too old (refresh if older than 5 minutes)
        cache_time = session.get(f"profile_cache_time_{user_id}")
        if cache_time:
            cache_age = (datetime.now(timezone.utc) - datetime.fromisoformat(cache_time)).total_seconds()
            if cache_age < 300:  # 5 minutes
                # Store in request cache for subsequent calls in same request
                setattr(g, cache_key, cached_profile)
                return cached_profile

    # Level 3: Fetch from database (slow - only when cache misses)
    row, _ = get_profile_row(user_id, use_service_role=True)

    if not row:
        # Create new profile if doesn't exist
        payload = {
            "user_id": user_id,
            "email": u.get("email"),
            "onboarding_completed": False,
            "xp": 0,
            "level": 1,
            "streak": 0,
            "last_activity": str(date.today()),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        rr = upsert_profile_row(payload, use_service_role=True)
        if rr.status_code >= 400:
            return None
        created = rr.json()
        row = created[0] if isinstance(created, list) and created else None

    # Store in both caches
    if row:
        setattr(g, cache_key, row)
        session[session_cache_key] = row
        session[f"profile_cache_time_{user_id}"] = datetime.now(timezone.utc).isoformat()

    return row

def clear_profile_cache(user_id: str = None):
    """Clear profile cache when profile is updated."""
    if user_id is None:
        u = get_current_user()
        if not u:
            return
        user_id = u.get("id")

    # Clear request cache
    cache_key = f"profile_{user_id}"
    if hasattr(g, cache_key):
        delattr(g, cache_key)

    # Clear session cache
    session_cache_key = f"cached_profile_{user_id}"
    if session_cache_key in session:
        del session[session_cache_key]
    if f"profile_cache_time_{user_id}" in session:
        del session[f"profile_cache_time_{user_id}"]

def update_streak_fields(row: dict) -> dict:
    """Update streak fields based on last activity."""
    last = row.get("last_activity")
    today = date.today()

    if not last:
        row["streak"] = max(int(row.get("streak") or 0), 1)
        row["last_activity"] = str(today)
        return row

    try:
        last_date = date.fromisoformat(last)
    except Exception:
        row["last_activity"] = str(today)
        row["streak"] = 1
        return row

    if last_date < today:
        diff = (today - last_date).days
        row["streak"] = (int(row.get("streak") or 0) + 1) if diff == 1 else 1
        row["last_activity"] = str(today)

    return row
