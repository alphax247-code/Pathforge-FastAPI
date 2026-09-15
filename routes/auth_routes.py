"""Native FastAPI authentication routes for Pathforge."""
from __future__ import annotations

import base64
import hashlib
import os
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
from starlette.templating import Jinja2Templates

from config import (
    FLASK_SECRET_KEY,
    IS_PROD,
    SUPABASE_ANON_KEY,
    SUPABASE_REDIRECT_URL,
    SUPABASE_URL,
)

router = APIRouter(tags=["authentication"])
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "pathforge_session"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60

# Use Flask's serializer so native FastAPI authentication remains compatible
# with pages that still run through the Flask migration layer.
_cookie_app = Flask("pathforge_session_compat")
_cookie_app.secret_key = FLASK_SECRET_KEY
_serializer = SecureCookieSessionInterface().get_signing_serializer(_cookie_app)


def _load_session(request: Request) -> dict[str, Any]:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw or _serializer is None:
        return {}
    try:
        value = _serializer.loads(raw, max_age=COOKIE_MAX_AGE)
        return dict(value) if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_session(response, data: dict[str, Any], *, remember: bool = False) -> None:
    if _serializer is None:
        raise RuntimeError("Session serializer is unavailable")
    response.set_cookie(
        COOKIE_NAME,
        _serializer.dumps(data),
        max_age=COOKIE_MAX_AGE if remember else 7 * 24 * 60 * 60,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        path="/",
    )


def _flash(data: dict[str, Any], message: str, category: str) -> None:
    flashes = list(data.get("_flashes", []))
    flashes.append((category, message))
    data["_flashes"] = flashes


def _redirect(path: str, data: dict[str, Any], *, remember: bool = False):
    response = RedirectResponse(path, status_code=303)
    _save_session(response, data, remember=remember)
    return response


def _url_for(endpoint: str, **values: Any) -> str:
    routes = {
        "static": f"/static/{values.get('filename', '')}",
        "auth.signup": "/signup",
        "auth.login": "/login",
        "auth.logout": "/logout",
        "auth.login_google": "/login/google",
        "auth.login_facebook": "/login/facebook",
        "auth.auth_callback": "/auth/callback",
    }
    return routes.get(endpoint, "/")


def _template(request: Request, name: str, data: dict[str, Any], **context: Any):
    response = templates.TemplateResponse(
        request=request,
        name=name,
        context={"csrf_token": data.get("csrf_token"), "url_for": _url_for, **context},
    )
    _save_session(response, data)
    return response


def _new_csrf(data: dict[str, Any]) -> str:
    token = data.get("csrf_token") or token_urlsafe(32)
    data["csrf_token"] = token
    return token


def _valid_csrf(data: dict[str, Any], token: str) -> bool:
    return bool(token) and token == data.get("csrf_token")


async def _supabase(method: str, path: str, **kwargs: Any) -> httpx.Response:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase is not configured")
    headers = dict(kwargs.pop("headers", {}))
    headers.setdefault("apikey", SUPABASE_ANON_KEY)
    headers.setdefault("Authorization", f"Bearer {SUPABASE_ANON_KEY}")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3)) as client:
        return await client.request(method, f"{SUPABASE_URL}{path}", headers=headers, **kwargs)


def _error_detail(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return fallback
    return str(payload.get("msg") or payload.get("message") or payload.get("error_description") or fallback)


def _user_session(user: dict[str, Any], access: str, refresh: str | None, remember: bool) -> dict[str, Any]:
    metadata = user.get("user_metadata") or {}
    email = user.get("email") or ""
    return {
        "_permanent": True,
        "user": {
            "id": user.get("id"),
            "email": email,
            "username": metadata.get("username") or email.split("@")[0],
            "created_at": user.get("created_at"),
            "is_admin": bool(metadata.get("is_admin", False)),
        },
        "access_token": access,
        "refresh_token": refresh,
        "remember_me": remember,
    }


@router.get("/signup", response_class=HTMLResponse, name="auth.signup")
async def signup_page(request: Request):
    data = _load_session(request)
    _new_csrf(data)
    return _template(request, "signup.html", data)


@router.post("/signup", name="auth.signup_post")
async def signup(request: Request, email: str = Form(""), password: str = Form(""), csrf_token: str = Form("")):
    data = _load_session(request)
    if not _valid_csrf(data, csrf_token):
        _flash(data, "Invalid CSRF token.", "error")
        return _redirect("/signup", data)
    email, password = email.strip(), password.strip()
    if not email or not password:
        _flash(data, "Email and password are required.", "error")
        return _redirect("/signup", data)
    try:
        response = await _supabase("POST", "/auth/v1/signup", json={"email": email, "password": password})
    except (httpx.HTTPError, RuntimeError):
        _flash(data, "Signup service is temporarily unavailable.", "error")
        return _redirect("/signup", data)
    if response.is_error:
        detail = _error_detail(response, "Signup failed")
        lowered = detail.lower()
        if "already" in lowered:
            detail = "This email is already registered. Please log in instead."
        elif "password" in lowered and ("short" in lowered or "least" in lowered):
            detail = "Password is too short. Please use at least 6 characters."
        _flash(data, detail, "error")
        return _redirect("/signup", data)
    _flash(data, "Account created! Check your email if confirmation is required.", "success")
    return _redirect("/login", data)


@router.get("/login", response_class=HTMLResponse, name="auth.login")
async def login_page(request: Request):
    data = _load_session(request)
    _new_csrf(data)
    return _template(request, "login.html", data)


@router.post("/login", name="auth.login_post")
async def login(
    request: Request,
    email: str = Form(""),
    password: str = Form(""),
    csrf_token: str = Form(""),
    remember_me: str | None = Form(None),
):
    data = _load_session(request)
    if not _valid_csrf(data, csrf_token):
        _flash(data, "Invalid CSRF token.", "error")
        return _redirect("/login", data)
    if not email.strip() or not password.strip():
        _flash(data, "Email and password are required.", "error")
        return _redirect("/login", data)
    try:
        response = await _supabase(
            "POST", "/auth/v1/token?grant_type=password",
            json={"email": email.strip(), "password": password.strip()},
        )
    except (httpx.HTTPError, RuntimeError):
        _flash(data, "Login service is temporarily unavailable.", "error")
        return _redirect("/login", data)
    if response.is_error:
        _flash(data, _error_detail(response, "Invalid email or password."), "error")
        return _redirect("/login", data)
    payload = response.json()
    user = payload.get("user") or {}
    remember = remember_me == "1"
    data = _user_session(user, payload.get("access_token", ""), payload.get("refresh_token"), remember)
    _flash(data, "Logged in!", "info")
    target = "/admin/dashboard" if data["user"]["is_admin"] else "/dashboard"
    return _redirect(target, data, remember=remember)


@router.get("/logout", name="auth.logout")
async def logout():
    data: dict[str, Any] = {}
    _flash(data, "Logged out.", "info")
    return _redirect("/", data)


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _callback_url(request: Request) -> str:
    return SUPABASE_REDIRECT_URL or str(request.url_for("auth.auth_callback"))


async def _oauth_redirect(request: Request, provider: str):
    data = _load_session(request)
    verifier, challenge = _pkce_pair()
    data["pkce_verifier"] = verifier
    params = urlencode({
        "provider": provider,
        "redirect_to": _callback_url(request),
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return _redirect(f"{SUPABASE_URL}/auth/v1/authorize?{params}", data, remember=True)


@router.get("/auth/google", name="auth.google")
@router.get("/login/google", name="auth.login_google")
async def login_google(request: Request):
    return await _oauth_redirect(request, "google")


@router.get("/auth/facebook", name="auth.facebook")
@router.get("/login/facebook", name="auth.login_facebook")
async def login_facebook(request: Request):
    return await _oauth_redirect(request, "facebook")


@router.get("/auth/callback", response_class=HTMLResponse, name="auth.auth_callback")
async def auth_callback(request: Request, code: str | None = None, error: str | None = None, error_description: str = ""):
    data = _load_session(request)
    if error:
        _flash(data, f"OAuth error: {error} {error_description}".strip(), "error")
        return _redirect("/login", data)
    # Some Supabase configurations return tokens in the URL fragment. The
    # browser callback template securely forwards those tokens to the endpoint below.
    if not code:
        return _template(request, "auth_callback.html", data)
    verifier = data.get("pkce_verifier")
    if not verifier:
        _flash(data, "Missing PKCE verifier. Please try logging in again.", "error")
        return _redirect("/login", data)
    response = await _supabase(
        "POST", "/auth/v1/token?grant_type=pkce",
        json={"auth_code": code, "code_verifier": verifier},
    )
    if response.is_error:
        _flash(data, "OAuth exchange failed.", "error")
        return _redirect("/login", data)
    payload = response.json()
    access = payload.get("access_token")
    if not access:
        _flash(data, "OAuth exchange returned no access token.", "error")
        return _redirect("/login", data)
    user_response = await _supabase("GET", "/auth/v1/user", headers={"Authorization": f"Bearer {access}"})
    if user_response.is_error:
        _flash(data, "Could not retrieve your user account.", "error")
        return _redirect("/login", data)
    data = _user_session(user_response.json(), access, payload.get("refresh_token"), True)
    _flash(data, "Logged in with OAuth!", "info")
    target = "/admin/dashboard" if data["user"]["is_admin"] else "/dashboard"
    return _redirect(target, data, remember=True)


@router.post("/api/auth/session", name="auth.browser_session")
async def browser_session(request: Request):
    payload = await request.json()
    access = str(payload.get("access_token") or "")
    if not access:
        return JSONResponse({"success": False, "error": "Missing access token"}, status_code=400)
    try:
        user_response = await _supabase("GET", "/auth/v1/user", headers={"Authorization": f"Bearer {access}"})
    except (httpx.HTTPError, RuntimeError):
        return JSONResponse({"success": False, "error": "Authentication service unavailable"}, status_code=503)
    if user_response.is_error:
        return JSONResponse({"success": False, "error": "Invalid access token"}, status_code=401)
    data = _user_session(user_response.json(), access, payload.get("refresh_token"), True)
    response = JSONResponse({
        "success": True,
        "redirect": "/admin/dashboard" if data["user"]["is_admin"] else "/dashboard",
    })
    _save_session(response, data, remember=True)
    return response

