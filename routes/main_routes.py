"""
Main routes for PathForge application.
Handles dashboard, profile, onboarding, and main feature pages.
"""
import os
from datetime import datetime, timezone

from flask import Blueprint, request, redirect, url_for, render_template, flash, Response

import requests

from auth import require_login, get_current_user, verify_form_csrf, is_user_admin, sb_headers_service
from database import (
    ensure_profile_exists,
    get_profile_row,
    upsert_profile_row,
    clear_profile_cache
)
from storage import storage_list
from config import VIDEOS_BUCKET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

main_bp = Blueprint('main', __name__)

# Temporary XP rank names and thresholds. Keep these centralized so the names
# and progression can be redesigned later without changing templates.
XP_RANKS = (
    (3000, "Ultimate"),
    (1500, "Pro"),
    (500, "Intermediate"),
    (100, "Beginner"),
    (0, "Novice"),
)

def get_xp_rank(xp):
    try:
        total_xp = max(0, int(xp or 0))
    except (TypeError, ValueError):
        total_xp = 0
    for minimum_xp, name in XP_RANKS:
        if total_xp >= minimum_xp:
            return {"name": name, "minimum_xp": minimum_xp}

def needs_onboarding(profile):
    """Require both a completed onboarding flag and the user's chosen name."""
    return not profile.get("onboarding_completed") or not (profile.get("name") or "").strip()

@main_bp.route("/")
def index():
    user = get_current_user()
    if user:
        profile = ensure_profile_exists() or {}
        # Redirect to onboarding if not completed
        if needs_onboarding(profile):
            return redirect(url_for("main.onboarding"))
        is_admin = user.get("is_admin", False)
        return render_template("index.html", user=user, progress=profile, is_admin=is_admin)

    # For non-logged-in users, check if they've visited before
    has_visited = request.cookies.get("pathforge_visited")

    if has_visited:
        # Returning visitor - redirect to login
        return redirect(url_for("auth.login"))
    else:
        # First-time visitor - show welcome page and set cookie
        response = Response(render_template("welcome.html"))
        # Set cookie for 1 year to remember they've visited
        response.set_cookie(
            "pathforge_visited",
            "1",
            max_age=365*24*60*60,  # 1 year in seconds
            httponly=True,
            samesite="Lax"
        )
        return response

@main_bp.route("/dashboard")
def dashboard():
    guard = require_login()
    if guard:
        return guard

    user = get_current_user()

    # Use cached profile data for performance
    profile = ensure_profile_exists() or {}

    # Redirect to onboarding if not completed
    if needs_onboarding(profile):
        return redirect(url_for("main.onboarding"))

    is_admin = user.get("is_admin", False)
    return render_template("index.html", user=user, progress=profile, is_admin=is_admin)

# -------- Onboarding --------
@main_bp.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    guard = require_login()
    if guard:
        return guard

    if request.method == "POST":
        if not verify_form_csrf(request.form.get("csrf_token")):
            flash("Invalid CSRF token.", "error")
            return redirect(url_for("main.onboarding"))

        u = get_current_user()
        user_id = u.get("id")

        name = (request.form.get("name") or "").strip() or None
        age_raw = (request.form.get("age") or "").strip()
        age = int(age_raw) if age_raw.isdigit() else None

        payload = {
            "user_id": user_id,
            "email": u.get("email"),
            "name": name,
            "age": age,
            "goals": (request.form.get("goals") or "").strip(),
            "experience_level": (request.form.get("experience_level") or "").strip(),
            "time_commitment": (request.form.get("time_commitment") or "").strip(),
            "onboarding_completed": True,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Use service role to bypass token expiration issues
        r = upsert_profile_row(payload, use_service_role=True)

        if r.status_code >= 400:
            flash(f"Failed saving onboarding: {r.text}", "error")
            return redirect(url_for("main.onboarding"))

        # Clear profile cache since we just updated it
        clear_profile_cache(user_id)

        # Verify the profile was actually saved (use service role to bypass token expiration)
        saved_row, verify_r = get_profile_row(user_id, use_service_role=True)

        if saved_row and saved_row.get("onboarding_completed"):
            flash("Onboarding completed! Welcome to PathForge!", "info")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Onboarding data was not saved. Please try again or contact support.", "error")
            return redirect(url_for("main.onboarding"))

    row = ensure_profile_exists() or {}
    return render_template("onboarding.html", row=row)

@main_bp.route("/profile", methods=["GET", "POST"])
def profile():
    guard = require_login()
    if guard:
        return guard

    u = get_current_user()
    row = ensure_profile_exists() or {}

    if needs_onboarding(row):
        return redirect(url_for("main.onboarding"))

    if request.method == "POST":
        if not verify_form_csrf(request.form.get("csrf_token")):
            flash("Invalid security token. Please try again.", "error")
            return redirect(url_for("main.profile"))

        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Please enter the name you want displayed.", "error")
            return redirect(url_for("main.profile"))

        payload = {
            "user_id": u.get("id"),
            "name": name,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        response = upsert_profile_row(payload, use_service_role=True)
        if response.status_code >= 400:
            flash("We could not update your profile. Please try again.", "error")
            return redirect(url_for("main.profile"))

        clear_profile_cache(u.get("id"))
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))

    rank = get_xp_rank(row.get("xp"))
    subscription_status = row.get("subscription_status") or row.get("subscription_tier") or "Free"
    return render_template(
        "profile.html",
        user=u,
        progress=row,
        rank=rank,
        subscription_status=subscription_status,
        assessment=None,
        is_admin=is_user_admin(),
    )

# -------- Video/Lessons --------
@main_bp.route("/my-videos")
@main_bp.route("/videos")
@main_bp.route("/lessons")
def lessons():
    guard = require_login()
    if guard:
        return guard

    user = get_current_user()
    profile = ensure_profile_exists() or {}

    # Lazy load videos list (make it optional and load via AJAX instead)
    # For now, keep simple list but with timeout
    items = []
    try:
        prefix = "videos"
        r = storage_list(VIDEOS_BUCKET, prefix)
        if r.status_code < 400:
            files = r.json() or []

            for obj in files:
                name = obj.get("name")
                if not name:
                    continue
                # Supabase storage_list returns names without the prefix, so we need to add it back
                # Ensure the full path includes the "videos/" prefix
                if not name.startswith("videos/"):
                    full_path = f"videos/{name}"
                else:
                    full_path = name
                # Extract just the filename for display
                display_name = name.split("/")[-1] if "/" in name else name
                # Use direct public URL for maximum speed (bucket is public)
                play_url = f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{full_path}"
                items.append({"name": display_name, "path": full_path, "url": play_url})
    except Exception as e:
        print(f"Error loading videos: {e}")
        # Continue rendering page even if videos fail to load

    return render_template("lessons.html", user=user, progress=profile, items=items, is_admin=is_user_admin())

@main_bp.route("/stream/<path:video_path>")
def stream_video(video_path):
    """
    Redirect directly to public Supabase Storage URL.
    Since the bucket is public, this is the fastest approach with full CDN benefits.
    """
    guard = require_login()
    if guard:
        return guard

    # Since bucket is public, use direct public URL (much faster, better caching)
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{video_path}"

    # Redirect directly to the public URL with caching headers
    response = redirect(public_url)
    response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    return response

# -------- Main feature routes --------
@main_bp.route("/challenges")
def challenges():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("challenges.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/inner-game")
def inner_game():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("inner_game.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/community", methods=["GET", "POST"])
def community():
    guard = require_login()
    if guard:
        return guard

    user = get_current_user()
    user_id = user.get("id")
    profile = ensure_profile_exists() or {}

    if request.method == "POST":
        # Handle post creation
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        selected_tags = request.form.getlist("tags[]")

        if not title or not content:
            flash("Please provide both title and content", "error")
            return redirect(url_for("main.community"))

        # Create post in Supabase
        post_data = {
            "user_id": user_id,
            "title": title,
            "content": content
        }

        url = f"{SUPABASE_URL}/rest/v1/forum_posts"
        headers_dict = sb_headers_service()
        headers_dict["Prefer"] = "return=representation"

        response = requests.post(url, json=post_data, headers=headers_dict, timeout=10)

        if response.status_code >= 400:
            flash("Failed to create post", "error")
            return redirect(url_for("main.community"))

        # Get the created post
        created_post = response.json()
        if created_post and isinstance(created_post, list) and len(created_post) > 0:
            post_id = created_post[0].get("id")

            # Add tags if selected
            if selected_tags and post_id:
                for tag_name in selected_tags:
                    # Get tag ID
                    tag_url = f"{SUPABASE_URL}/rest/v1/forum_tags?name=eq.{tag_name}"
                    tag_response = requests.get(tag_url, headers=sb_headers_service(), timeout=10)

                    if tag_response.status_code == 200:
                        tags_data = tag_response.json()
                        if tags_data and len(tags_data) > 0:
                            tag_id = tags_data[0].get("id")

                            # Create post-tag relationship
                            post_tag_url = f"{SUPABASE_URL}/rest/v1/forum_post_tags"
                            post_tag_data = {"post_id": post_id, "tag_id": tag_id}
                            requests.post(post_tag_url, json=post_tag_data, headers=sb_headers_service(), timeout=10)

        flash("Post created successfully!", "success")
        return redirect(url_for("main.community"))

    # GET request - fetch posts
    selected_tag = request.args.get("tag")

    # Fetch all tags
    tags_url = f"{SUPABASE_URL}/rest/v1/forum_tags?order=name.asc"
    tags_response = requests.get(tags_url, headers=sb_headers_service(), timeout=10)
    tags = tags_response.json() if tags_response.status_code == 200 else []

    # Fetch posts
    posts_url = f"{SUPABASE_URL}/rest/v1/forum_posts?order=is_pinned.desc,created_at.desc"
    posts_response = requests.get(posts_url, headers=sb_headers_service(), timeout=10)

    if posts_response.status_code == 200:
        posts = posts_response.json()
        print(f"✓ Fetched {len(posts)} posts from database")
    else:
        posts = []
        print(f"✗ Failed to fetch posts: {posts_response.status_code}")
        print(f"Response: {posts_response.text}")
        if posts_response.status_code == 404:
            flash("Forum tables not found. Please run the SQL migration first.", "error")
        elif posts_response.status_code >= 400:
            flash(f"Error loading posts: {posts_response.text}", "error")

    # Enrich posts with author data and tags
    for post in posts:
        post_user_id = post.get("user_id")

        # Get author profile
        profile_url = f"{SUPABASE_URL}/rest/v1/profiles?user_id=eq.{post_user_id}"
        profile_response = requests.get(profile_url, headers=sb_headers_service(), timeout=10)

        if profile_response.status_code == 200:
            profiles = profile_response.json()
            if profiles and len(profiles) > 0:
                post["author"] = {
                    "username": profiles[0].get("name") or profiles[0].get("email", "Anonymous").split("@")[0],
                    "level": profiles[0].get("level", 1),
                    "xp": profiles[0].get("xp", 0)
                }
            else:
                post["author"] = {"username": "Anonymous", "level": 1, "xp": 0}
        else:
            post["author"] = {"username": "Anonymous", "level": 1, "xp": 0}

        # Convert created_at to datetime object
        from datetime import datetime
        if isinstance(post.get("created_at"), str):
            post["created_at"] = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))

        # Get comments count
        comments_url = f"{SUPABASE_URL}/rest/v1/forum_comments?post_id=eq.{post['id']}"
        comments_response = requests.get(comments_url, headers=sb_headers_service(), timeout=10)
        post["comments"] = comments_response.json() if comments_response.status_code == 200 else []

        # Get post tags
        post_tags_url = f"{SUPABASE_URL}/rest/v1/forum_post_tags?post_id=eq.{post['id']}&select=tag_id"
        post_tags_response = requests.get(post_tags_url, headers=sb_headers_service(), timeout=10)

        post["tags"] = []
        if post_tags_response.status_code == 200:
            post_tag_ids = [pt["tag_id"] for pt in post_tags_response.json()]
            post["tags"] = [tag for tag in tags if tag["id"] in post_tag_ids]

    # Add post count to tags
    for tag in tags:
        tag_posts_url = f"{SUPABASE_URL}/rest/v1/forum_post_tags?tag_id=eq.{tag['id']}"
        tag_posts_response = requests.get(tag_posts_url, headers=sb_headers_service(), timeout=10)
        tag["posts"] = tag_posts_response.json() if tag_posts_response.status_code == 200 else []

    return render_template("community.html", user=user, progress=profile, is_admin=is_user_admin(),
                         posts=posts, tags=tags, selected_tag=selected_tag)

@main_bp.route("/practice")
def practice():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("practice.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/ai-menu")
def ai_menu():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("ai/ai_menu.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/text-practice")
def text_practice():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("ai/text-practice.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/speech-practice")
def speech_practice():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("ai/speech-practice.html", user=user, progress=profile, is_admin=is_user_admin())

# HIDDEN: Daily directive feature temporarily disabled
# @main_bp.route("/daily-directive")
# def daily_directive():
#     guard = require_login()
#     if guard:
#         return guard
#     user = get_current_user()
#     profile = ensure_profile_exists() or {}
#     return render_template("daily_directive.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/pricing")
def pricing():
    user = get_current_user()
    profile = ensure_profile_exists() if user else {}
    return render_template("pricing.html", user=user, progress=profile, is_admin=is_user_admin())

@main_bp.route("/checkout")
def checkout():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("checkout_page.html", user=user, progress=profile, is_admin=is_user_admin())

# -------- Favicon --------
@main_bp.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    from flask import current_app
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )
