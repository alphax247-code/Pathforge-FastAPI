"""
Authentication module for PathForge application.
Handles user sessions, CSRF protection, OAuth, and Supabase authentication.
"""
import os
import base64
import hashlib
from datetime import datetime
from secrets import token_urlsafe
from urllib.parse import urlencode

from flask import session, redirect, url_for, flash, request
from supabase_connection import get_supabase_session

from config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_REDIRECT_URL,
    ADMIN_USERNAME,
    ADMIN_PASSWORD
)

# ============================================================
# USER ELEMENTS: session/user helpers + CSRF
# ============================================================
def get_current_user():
    """Get the current logged-in user from session."""
    user_data = session.get("user")
    if not user_data or "email" not in user_data:
        return None

    # Create a copy to avoid modifying the session directly
    user_copy = dict(user_data)

    # Add username field for template compatibility
    if "username" not in user_copy:
        user_copy["username"] = user_copy["email"].split("@")[0]

    # Parse created_at if it's a string
    if "created_at" in user_copy and isinstance(user_copy["created_at"], str):
        try:
            user_copy["created_at"] = datetime.fromisoformat(user_copy["created_at"].replace("Z", "+00:00"))
        except:
            pass

    return user_copy

def is_user_admin():
    """Check if the current user is an admin."""
    user = get_current_user()
    return user.get("is_admin", False) if user else False

def require_login():
    """Require user to be logged in. Returns redirect if not logged in."""
    if not session.get("user"):
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))
    return None

def generate_form_csrf():
    """Generate a CSRF token for forms."""
    if "csrf_token" not in session:
        session["csrf_token"] = token_urlsafe(32)
    return session["csrf_token"]

def verify_form_csrf(token: str) -> bool:
    """Verify a CSRF token."""
    return bool(token) and token == session.get("csrf_token")

def csrf_input_html() -> str:
    """Generate HTML input for CSRF token."""
    return f'<input type="hidden" name="csrf_token" value="{generate_form_csrf()}"/>'

# ============================================================
# Supabase headers
# ============================================================
def sb_headers_anon():
    """Headers for anonymous Supabase requests."""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }

def sb_headers_service():
    """Headers for service role Supabase requests."""
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

def sb_headers_user():
    """Headers for user-authenticated Supabase requests."""
    token = session.get("access_token", "")
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ============================================================
# OAuth PKCE helpers
# ============================================================
def b64url(data: bytes) -> str:
    """Base64 URL-safe encoding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def make_pkce_pair():
    """Generate PKCE verifier and challenge pair."""
    verifier = b64url(os.urandom(32))
    challenge = b64url(hashlib.sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge

def current_redirect_url():
    """Get the current OAuth redirect URL."""
    if SUPABASE_REDIRECT_URL:
        return SUPABASE_REDIRECT_URL
    try:
        return url_for("auth_callback", _external=True)
    except RuntimeError:
        return "http://localhost:5000/auth/callback"

# ============================================================
# Supabase Auth
# ============================================================
def supabase_signup(email: str, password: str):
    """Sign up a new user with Supabase."""
    url = f"{SUPABASE_URL}/auth/v1/signup"
    session = get_supabase_session()
    return session.post(url, headers=sb_headers_anon(), json={"email": email, "password": password}, timeout=(2, 10))

def supabase_login(email: str, password: str):
    """Log in a user with Supabase."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    sess = get_supabase_session()
    return sess.post(url, headers=sb_headers_anon(), json={"email": email, "password": password}, timeout=(2, 10))

def supabase_get_user(access_token: str):
    """Get user information from Supabase."""
    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {access_token}"}
    sess = get_supabase_session()
    return sess.get(url, headers=headers, timeout=(2, 8))

def supabase_exchange_code_for_session(code: str, code_verifier: str):
    """Exchange OAuth code for session."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce"
    headers = sb_headers_anon()
    sess = get_supabase_session()
    payloads = [
        {"auth_code": code, "code_verifier": code_verifier},
        {"code": code, "code_verifier": code_verifier},
    ]
    last = None
    for p in payloads:
        r = sess.post(url, headers=headers, json=p, timeout=(2, 10))
        if r.status_code < 400:
            return r
        last = r
    return last

def oauth_redirect(provider: str):
    """Redirect to OAuth provider with PKCE."""
    verifier, challenge = make_pkce_pair()
    session.permanent = True
    session["pkce_verifier"] = verifier
    session.modified = True  # Explicitly mark session as modified

    redirect_url = current_redirect_url()

    params = {
        "provider": provider,
        "redirect_to": redirect_url,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    }

    auth_url = f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"

    return redirect(auth_url)

# ============================================================
# Supabase Admin
# ============================================================
def supabase_admin_list_users(page: int = 1, per_page: int = 200):
    """List all users (admin function)."""
    url = f"{SUPABASE_URL}/auth/v1/admin/users?page={page}&per_page={per_page}"
    headers = {"apikey": SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"}
    sess = get_supabase_session()
    return sess.get(url, headers=headers, timeout=(2, 10))

def require_admin_auth():
    """Require admin authentication - checks session for is_admin flag."""
    user = get_current_user()

    # First check if user is logged in and has admin flag in session
    if user and user.get("is_admin", False):
        return None

    # Fallback to HTTP Basic Auth for backward compatibility
    auth = request.authorization
    if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
        return ("Admin auth required", 401, {"WWW-Authenticate": 'Basic realm="Admin Area"'})
    return None
