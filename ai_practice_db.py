"""
AI Practice Database Functions
Handles all database operations for AI practice sessions, conversations, and statistics.
"""
from datetime import datetime, timezone, date
from typing import Dict, List, Optional, Tuple
import requests

from config import SUPABASE_URL
from auth import get_current_user, sb_headers_service, sb_headers_user
from supabase_connection import get_supabase_session
from database import clear_profile_cache

# ============================================================
# Helper Functions
# ============================================================

def rest_url(table: str) -> str:
    """Build REST API URL for a table."""
    return f"{SUPABASE_URL}/rest/v1/{table}"

# ============================================================
# AI Practice Topics
# ============================================================

def get_practice_topics(practice_type: Optional[str] = None, use_service_role: bool = True):
    """Get all active practice topics, optionally filtered by type."""
    url = rest_url("ai_practice_topics")
    params = {"is_active": "eq.true", "order": "display_order.asc"}

    if practice_type:
        params["practice_type"] = f"eq.{practice_type}"

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

def get_topic_by_id(topic_id: str, use_service_role: bool = True):
    """Get a specific practice topic by ID."""
    url = rest_url("ai_practice_topics")
    params = {"id": f"eq.{topic_id}"}

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return None, r

    topics = r.json()
    return (topics[0] if topics else None), r

# ============================================================
# AI Practice Sessions
# ============================================================

def create_practice_session(user_id: str, practice_type: str, topic_id: Optional[str] = None,
                           session_title: Optional[str] = None, scenario_context: Optional[Dict] = None,
                           use_service_role: bool = True):
    """Create a new AI practice session."""
    url = rest_url("ai_practice_sessions")

    payload = {
        "user_id": user_id,
        "practice_type": practice_type,
        "topic_id": topic_id,
        "session_title": session_title,
        "scenario_context": scenario_context,
        "status": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    headers["Prefer"] = "return=representation"

    session = get_supabase_session()
    r = session.post(url, headers=headers, json=payload, timeout=(2, 8))

    if r.status_code >= 400:
        return None, r

    sessions = r.json()
    return (sessions[0] if sessions else None), r

def get_user_sessions(user_id: str, practice_type: Optional[str] = None,
                      limit: int = 20, use_service_role: bool = True):
    """Get user's practice sessions."""
    url = rest_url("ai_practice_sessions")
    params = {
        "user_id": f"eq.{user_id}",
        "order": "created_at.desc",
        "limit": limit
    }

    if practice_type:
        params["practice_type"] = f"eq.{practice_type}"

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

def get_session_by_id(session_id: str, use_service_role: bool = True):
    """Get a specific practice session by ID."""
    url = rest_url("ai_practice_sessions")
    params = {"id": f"eq.{session_id}"}

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return None, r

    sessions = r.json()
    return (sessions[0] if sessions else None), r

def update_practice_session(session_id: str, updates: Dict, use_service_role: bool = True):
    """Update a practice session."""
    url = rest_url("ai_practice_sessions")
    params = {"id": f"eq.{session_id}"}

    # Add timestamp
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    headers["Prefer"] = "return=representation"

    session = get_supabase_session()
    r = session.patch(url, headers=headers, params=params, json=updates, timeout=(2, 8))

    return r

def complete_practice_session(session_id: str, user_score: Optional[int] = None,
                              ai_feedback: Optional[str] = None, use_service_role: bool = True):
    """Mark a practice session as completed."""
    updates = {
        "status": "completed",
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "user_score": user_score,
        "ai_feedback": ai_feedback
    }

    return update_practice_session(session_id, updates, use_service_role)

# ============================================================
# AI Conversation Messages
# ============================================================

def add_conversation_message(session_id: str, user_id: str, role: str, content: str,
                            message_order: int, technique_used: Optional[str] = None,
                            effectiveness_score: Optional[int] = None,
                            ai_analysis: Optional[str] = None, use_service_role: bool = True):
    """Add a message to a conversation."""
    url = rest_url("ai_conversation_messages")

    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "message_order": message_order,
        "technique_used": technique_used,
        "effectiveness_score": effectiveness_score,
        "ai_analysis": ai_analysis,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    headers["Prefer"] = "return=representation"

    session = get_supabase_session()
    r = session.post(url, headers=headers, json=payload, timeout=(2, 8))

    if r.status_code >= 400:
        return None, r

    messages = r.json()
    return (messages[0] if messages else None), r

def get_conversation_messages(session_id: str, use_service_role: bool = True):
    """Get all messages for a conversation session."""
    url = rest_url("ai_conversation_messages")
    params = {
        "session_id": f"eq.{session_id}",
        "order": "message_order.asc"
    }

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

# ============================================================
# User AI Practice Statistics
# ============================================================

def get_user_ai_stats(user_id: str, practice_type: Optional[str] = None, use_service_role: bool = True):
    """Get user's AI practice statistics."""
    url = rest_url("user_ai_practice_stats")
    params = {"user_id": f"eq.{user_id}"}

    if practice_type:
        params["practice_type"] = f"eq.{practice_type}"

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

def update_user_ai_stats(user_id: str, practice_type: str, stats_update: Dict, use_service_role: bool = True):
    """Update user's AI practice statistics."""
    url = rest_url("user_ai_practice_stats")

    # Try to get existing stats
    existing, _ = get_user_ai_stats(user_id, practice_type, use_service_role)

    if existing:
        # Update existing record
        params = {
            "user_id": f"eq.{user_id}",
            "practice_type": f"eq.{practice_type}"
        }

        stats_update["updated_at"] = datetime.now(timezone.utc).isoformat()

        headers = sb_headers_service() if use_service_role else sb_headers_user()
        session = get_supabase_session()
        r = session.patch(url, headers=headers, params=params, json=stats_update, timeout=(2, 8))
    else:
        # Create new record
        stats_update["user_id"] = user_id
        stats_update["practice_type"] = practice_type
        stats_update["created_at"] = datetime.now(timezone.utc).isoformat()

        headers = sb_headers_service() if use_service_role else sb_headers_user()
        headers["Prefer"] = "return=representation"

        session = get_supabase_session()
        r = session.post(url, headers=headers, json=stats_update, timeout=(2, 8))

    return r

# ============================================================
# AI Practice Achievements
# ============================================================

def get_all_achievements(practice_type: Optional[str] = None, use_service_role: bool = True):
    """Get all active achievements."""
    url = rest_url("ai_practice_achievements")
    params = {"is_active": "eq.true"}

    if practice_type:
        params["practice_type"] = f"eq.{practice_type},all"  # Get both specific and 'all' types

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

def get_user_achievements(user_id: str, use_service_role: bool = True):
    """Get achievements earned by a user."""
    url = rest_url("user_ai_achievements")
    params = {"user_id": f"eq.{user_id}", "select": "*,achievement:ai_practice_achievements(*)"}

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    session = get_supabase_session()
    r = session.get(url, headers=headers, params=params, timeout=(2, 8))

    if r.status_code >= 400:
        return [], r
    return r.json(), r

def award_achievement(user_id: str, achievement_id: str, use_service_role: bool = True):
    """Award an achievement to a user."""
    url = rest_url("user_ai_achievements")

    payload = {
        "user_id": user_id,
        "achievement_id": achievement_id,
        "earned_at": datetime.now(timezone.utc).isoformat()
    }

    headers = sb_headers_service() if use_service_role else sb_headers_user()
    headers["Prefer"] = "return=representation"

    session = get_supabase_session()
    r = session.post(url, headers=headers, json=payload, timeout=(2, 8))

    return r

# ============================================================
# Helper Functions
# ============================================================

def get_practice_dashboard_data(user_id: str):
    """Get all data needed for the practice dashboard."""
    # Get stats for all practice types
    stats, _ = get_user_ai_stats(user_id, use_service_role=True)

    # Get recent sessions
    sessions, _ = get_user_sessions(user_id, limit=5, use_service_role=True)

    # Get achievements
    achievements, _ = get_user_achievements(user_id, use_service_role=True)

    return {
        "stats": stats,
        "recent_sessions": sessions,
        "achievements": achievements
    }
