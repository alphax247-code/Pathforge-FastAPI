"""
API routes for PathForge application.
Handles REST API endpoints for assessments and progress tracking.
"""
from datetime import datetime, timezone
import traceback
import requests

from flask import Blueprint, request, jsonify

from auth import require_login, get_current_user, require_admin_auth
from database import (
    ensure_profile_exists,
    get_profile_row,
    upsert_profile_row,
    update_streak_fields,
    clear_profile_cache,
    is_onboarding_complete,
    CURRENT_ONBOARDING_VERSION,
)
from storage import storage_list, storage_delete
from config import VIDEOS_BUCKET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY as SUPABASE_SERVICE_KEY
from flask import url_for
from game_cache import game_cache
from ai_practice_db import (
    get_practice_topics,
    create_practice_session,
    add_conversation_message,
    get_conversation_messages,
    complete_practice_session,
    get_user_ai_stats,
    get_practice_dashboard_data
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# -------- Assessment Save API --------
@api_bp.route("/assessment/save", methods=["POST"])
def save_assessment():
    guard = require_login()
    if guard:
        return guard

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    u = get_current_user()
    user_id = u.get("id")

    # Stamp completion server-side so old or sample assessment data cannot bypass onboarding.
    data["onboardingVersion"] = CURRENT_ONBOARDING_VERSION

    # Pull simple fields (optional)
    name = (data.get("name") or "").strip() or None
    age_raw = data.get("age")
    try:
        age = int(age_raw) if age_raw is not None and str(age_raw).strip() != "" else None
    except ValueError:
        age = None

    # Store assessment data
    payload = {
        "user_id": user_id,
        "email": u.get("email"),
        "name": name,
        "age": age,
        # Store full assessment result as JSONB
        "assessment_json": data,
        "onboarding_completed": True,  # Mark onboarding as complete
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    print(f"ASSESSMENT SAVE: User {user_id}, payload={payload}")

    # Use service role to bypass token expiration issues
    r = upsert_profile_row(payload, use_service_role=True)
    if r.status_code >= 400:
        print(f"ASSESSMENT SAVE ERROR: Status {r.status_code}, Response: {r.text}")
        return jsonify({"error": "Failed to save assessment", "details": r.text}), 400

    # Clear profile cache since we just updated it
    clear_profile_cache(user_id)

    # Supabase returns a list of rows when using return=representation
    saved = r.json()
    print(f"ASSESSMENT SAVE SUCCESS: Saved data for user {user_id}")

    return jsonify({
        "success": True,
        "row": (saved[0] if isinstance(saved, list) and saved else saved)
    }), 200

@api_bp.route("/progress", methods=["GET"])
def get_progress():
    guard = require_login()
    if guard:
        return guard

    u = get_current_user()
    user_id = u.get("id")
    # Use cached profile for performance
    row = ensure_profile_exists() or {}

    if not is_onboarding_complete(row):
        return jsonify({"error": "Onboarding not completed", "redirect": "/onboarding"}), 403

    updated = update_streak_fields(dict(row))
    if updated.get("last_activity") != row.get("last_activity") or updated.get("streak") != row.get("streak"):
        updated["user_id"] = user_id
        updated["updated_at"] = datetime.utcnow().isoformat() + "Z"
        # Use service role to bypass token expiration
        upsert_profile_row(updated, use_service_role=True)
        clear_profile_cache(user_id)
        row = updated

    return jsonify({
        "xp": row.get("xp", 0),
        "level": row.get("level", 1),
        "streak": row.get("streak", 0),
        "completed_lessons": row.get("completed_lessons", "").split(",") if row.get("completed_lessons") else [],
        "achievements": row.get("unlocked_achievements", "").split(",") if row.get("unlocked_achievements") else [],
    })

@api_bp.route("/progress", methods=["POST"])
def save_progress():
    guard = require_login()
    if guard:
        return guard

    u = get_current_user()
    user_id = u.get("id")

    # Use cached profile for performance
    row = ensure_profile_exists() or {}
    if not is_onboarding_complete(row):
        return jsonify({"error": "Onboarding not completed", "redirect": "/onboarding"}), 403

    data = request.get_json(silent=True) or {}
    payload = {"user_id": user_id, "updated_at": datetime.utcnow().isoformat() + "Z"}

    if "xp" in data:
        payload["xp"] = int(data["xp"])
    if "level" in data:
        payload["level"] = int(data["level"])

    if "completed_lesson" in data:
        current = [x for x in (row.get("completed_lessons") or "").split(",") if x]
        lid = str(data["completed_lesson"]).strip()
        if lid and lid not in current:
            current.append(lid)
        payload["completed_lessons"] = ",".join(current)

    if "unlock_achievement" in data:
        current = [x for x in (row.get("unlocked_achievements") or "").split(",") if x]
        aid = str(data["unlock_achievement"]).strip()
        if aid and aid not in current:
            current.append(aid)
        payload["unlocked_achievements"] = ",".join(current)

    merged = dict(row)
    merged.update(payload)
    merged = update_streak_fields(merged)
    payload["streak"] = merged.get("streak", row.get("streak", 0))
    payload["last_activity"] = merged.get("last_activity", row.get("last_activity"))

    # Use service role to bypass token expiration
    r = upsert_profile_row(payload, use_service_role=True)
    if r.status_code >= 400:
        return jsonify({"error": r.text}), 400

    # Clear profile cache since we just updated it
    clear_profile_cache(user_id)

    return jsonify({"success": True})

# -------- Lessons API --------
@api_bp.route("/lessons", methods=["GET"])
def get_lessons():
    """Get all video lessons"""
    guard = require_login()
    if guard:
        return guard

    try:
        # Get user profile to check access level and completed lessons
        u = get_current_user()
        user_id = u.get("id")
        # Use cached profile for performance
        profile = ensure_profile_exists() or {}
        user_level = profile.get("level", 1)
        is_premium = profile.get("subscription_status") in ['pro', 'premium']

        # Get list of completed lessons
        completed_lessons = [x for x in (profile.get("completed_lessons") or "").split(",") if x] if profile else []

        # Fetch video metadata from database
        import requests
        from auth import sb_headers_service

        db_url = f"{SUPABASE_URL}/rest/v1/videos?is_published=eq.true&order=display_order.asc,created_at.asc"
        db_response = requests.get(db_url, headers=sb_headers_service(), timeout=30)

        videos_metadata = {}
        if db_response.status_code < 400:
            db_videos = db_response.json()
            # Create a lookup dictionary by filename
            videos_metadata = {v["filename"]: v for v in db_videos}

        # List videos from storage
        r = storage_list(VIDEOS_BUCKET, "videos")

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load videos"}), 500

        files = r.json() if r.status_code < 400 else []

        # Transform videos into expected format
        lessons = []
        for idx, obj in enumerate(files):
            name = obj.get("name")
            if not name:
                continue

            # Supabase storage_list returns names without the prefix, so we need to add it back
            if not name.startswith("videos/"):
                full_path = f"videos/{name}"
            else:
                full_path = name

            # Extract filename for display
            display_name = name.split("/")[-1] if "/" in name else name

            # Get metadata from database if available
            metadata = videos_metadata.get(display_name, {})

            # Use metadata title if available, otherwise generate from filename
            if metadata.get("title"):
                title = metadata["title"]
            else:
                title_base = display_name.rsplit(".", 1)[0]
                title = title_base.replace("_", " ").replace("-", " ").strip().title()
                if title.replace(" ", "").isdigit():
                    title = f"Lesson {title}"

            # Use metadata description if available
            if metadata.get("description"):
                description = metadata["description"]
            else:
                description = f"Watch and learn from {title}. Complete this lesson to earn 25 XP!"

            # Use direct public URL for maximum speed (bucket is public)
            video_url = f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{full_path}"

            # Check if this lesson is completed
            is_completed = str(idx) in completed_lessons

            lessons.append({
                "id": idx,
                "title": title,
                "description": description,
                "category": metadata.get("category", "Lessons"),
                "playlist": metadata.get("playlist", metadata.get("category", "Lessons")),
                "is_unlocked": True,
                "completed": is_completed,
                "is_premium": metadata.get("is_premium", False),
                "has_access": is_premium or not metadata.get("is_premium", False),
                "required_level": metadata.get("required_level", 1),
                "thumbnail_url": metadata.get("thumbnail_url"),
                "duration_minutes": metadata.get("duration_seconds") // 60 if metadata.get("duration_seconds") else None,
                "url": video_url,
                "video_url": video_url,
                "filename": display_name,
                "chapters": metadata.get("chapters", [])
            })

        # Include user progress in response
        return jsonify({
            "success": True,
            "lessons": lessons,
            "user_xp": profile.get("xp", 0) if profile else 0,
            "user_level": user_level,
            "user_streak": profile.get("streak", 0) if profile else 0
        })

    except Exception as e:
        print(f"Error in get_lessons: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# -------- Video Token API --------
@api_bp.route("/video-token/<int:video_id>", methods=["GET"])
def get_video_token(video_id):
    """Get secure video token for a specific video"""
    guard = require_login()
    if guard:
        return guard

    try:
        # Get the video list to find the video by ID
        r = storage_list(VIDEOS_BUCKET, "videos")

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load videos"}), 500

        files = r.json() if r.status_code < 400 else []

        # Find the video by index
        if video_id >= len(files):
            return jsonify({"success": False, "error": "Video not found"}), 404

        video_obj = files[video_id]
        name = video_obj.get("name")

        if not name:
            return jsonify({"success": False, "error": "Invalid video"}), 404

        # Supabase storage_list returns names without the prefix, so we need to add it back
        # Ensure the full path includes the "videos/" prefix
        if not name.startswith("videos/"):
            full_path = f"videos/{name}"
        else:
            full_path = name

        # Since bucket is public, return direct public URL for maximum speed
        video_url = f"{SUPABASE_URL}/storage/v1/object/public/{VIDEOS_BUCKET}/{full_path}"

        return jsonify({
            "success": True,
            "video_url": video_url,
            "video_id": video_id
        })

    except Exception as e:
        print(f"Error in get_video_token: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# -------- Lessons Progress API --------
@api_bp.route("/lessons/<int:lesson_id>/progress", methods=["POST"])
def update_lesson_progress(lesson_id):
    """Update watch progress for a specific lesson"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True) or {}
        progress_data = data.get("progress_data", 0)

        # Get current profile (use cached for performance)
        profile = ensure_profile_exists() or {}

        # Store lesson progress in profile (you can customize this structure)
        # For now, we'll just acknowledge the request
        # In a full implementation, you'd store this in a separate table or JSONB field

        return jsonify({
            "success": True,
            "lesson_id": lesson_id,
            "progress": progress_data
        })

    except Exception as e:
        print(f"Error in update_lesson_progress: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
def complete_lesson(lesson_id):
    """Mark a lesson as completed and award XP"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        # Get current profile (use cached for performance)
        profile = ensure_profile_exists() or {}

        # Check if already completed
        completed_lessons = [x for x in (profile.get("completed_lessons") or "").split(",") if x]
        lesson_id_str = str(lesson_id)

        if lesson_id_str in completed_lessons:
            return jsonify({
                "success": True,
                "xp_awarded": 0,
                "message": "Lesson already completed"
            })

        # Award XP
        xp_award = 25
        current_xp = profile.get("xp", 0)
        new_xp = current_xp + xp_award

        # Calculate new level (every 100 XP = 1 level)
        new_level = max(1, new_xp // 100)

        # Add to completed lessons
        completed_lessons.append(lesson_id_str)

        # Update profile
        payload = {
            "user_id": user_id,
            "xp": new_xp,
            "level": new_level,
            "completed_lessons": ",".join(completed_lessons),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Update streak
        merged = dict(profile)
        merged.update(payload)
        merged = update_streak_fields(merged)
        payload["streak"] = merged.get("streak", profile.get("streak", 0))
        payload["last_activity"] = merged.get("last_activity", profile.get("last_activity"))

        r = upsert_profile_row(payload, use_service_role=True)
        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to save progress"}), 500

        # Clear profile cache since we just updated it
        clear_profile_cache(user_id)

        return jsonify({
            "success": True,
            "xp_awarded": xp_award,
            "new_xp": new_xp,
            "new_level": new_level,
            "message": f"Lesson completed! +{xp_award} XP"
        })

    except Exception as e:
        print(f"Error in complete_lesson: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# -------- Carousel Lessons API --------
@api_bp.route("/carousel-lessons", methods=["GET"])
def get_carousel_lessons():
    """Get all carousel text lessons with their slides"""
    guard = require_login()
    if guard:
        return guard

    try:
        from auth import sb_headers_service

        # Get user profile to check access level and completed lessons
        u = get_current_user()
        user_id = u.get("id")
        profile = ensure_profile_exists() or {}
        user_level = profile.get("level", 1)
        is_premium = profile.get("subscription_status") in ['pro', 'premium']

        # Get list of completed carousel lessons
        completed_carousel = [x for x in (profile.get("completed_carousel_lessons") or "").split(",") if x]

        # Fetch carousel lessons from database
        db_url = f"{SUPABASE_URL}/rest/v1/carousel_lessons?is_published=eq.true&order=display_order.asc,created_at.asc"
        db_response = requests.get(db_url, headers=sb_headers_service(), timeout=30)

        if db_response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load carousel lessons"}), 500

        lessons = db_response.json()

        # Fetch all slides for these lessons
        if lessons:
            lesson_ids = [lesson['id'] for lesson in lessons]
            # Construct a filter for lesson_ids using Supabase query syntax
            lesson_ids_filter = ','.join([f'"{lid}"' for lid in lesson_ids])
            slides_url = f"{SUPABASE_URL}/rest/v1/carousel_slides?lesson_id=in.({lesson_ids_filter})&order=slide_order.asc"
            slides_response = requests.get(slides_url, headers=sb_headers_service(), timeout=30)

            slides_by_lesson = {}
            if slides_response.status_code < 400:
                all_slides = slides_response.json()
                # Group slides by lesson_id
                for slide in all_slides:
                    lesson_id = slide['lesson_id']
                    if lesson_id not in slides_by_lesson:
                        slides_by_lesson[lesson_id] = []
                    slides_by_lesson[lesson_id].append({
                        'id': slide['id'],
                        'order': slide['slide_order'],
                        'title': slide.get('title'),
                        'content': slide['content'],
                        'image_url': slide.get('image_url')
                    })

        # Transform lessons into expected format
        carousel_lessons = []
        for lesson in lessons:
            lesson_id = lesson['id']
            is_completed = lesson_id in completed_carousel
            is_lesson_premium = lesson.get('is_premium', False)
            has_access = is_premium or not is_lesson_premium
            required_level = lesson.get('required_level', 1)
            is_unlocked = user_level >= required_level

            # Use playlist field, fallback to category for backwards compatibility
            playlist = lesson.get('playlist') or lesson.get('category', 'Lessons')

            carousel_lessons.append({
                'id': lesson_id,
                'title': lesson['title'],
                'description': lesson.get('description'),
                'playlist': playlist,
                'category': playlist,  # Keep for backwards compatibility
                'is_unlocked': is_unlocked,
                'completed': is_completed,
                'is_premium': is_lesson_premium,
                'has_access': has_access,
                'required_level': required_level,
                'thumbnail_url': lesson.get('thumbnail_url'),
                'estimated_minutes': lesson.get('estimated_minutes', 5),
                'xp_reward': lesson.get('xp_reward', 25),
                'slides': slides_by_lesson.get(lesson_id, []),
                'slide_count': len(slides_by_lesson.get(lesson_id, [])),
                'type': 'carousel'  # Identifier to distinguish from video lessons
            })

        return jsonify({
            'success': True,
            'lessons': carousel_lessons
        })

    except Exception as e:
        print(f"Error in get_carousel_lessons: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route("/carousel-lessons/<lesson_id>", methods=["GET"])
def get_carousel_lesson(lesson_id):
    """Get a specific carousel lesson with all its slides"""
    guard = require_login()
    if guard:
        return guard

    try:
        from auth import sb_headers_service

        # Fetch specific lesson
        lesson_url = f"{SUPABASE_URL}/rest/v1/carousel_lessons?id=eq.{lesson_id}&is_published=eq.true"
        lesson_response = requests.get(lesson_url, headers=sb_headers_service(), timeout=30)

        if lesson_response.status_code >= 400:
            return jsonify({'success': False, 'error': 'Failed to load lesson'}), 500

        lessons = lesson_response.json()
        if not lessons:
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404

        lesson = lessons[0]

        # Fetch slides for this lesson
        slides_url = f"{SUPABASE_URL}/rest/v1/carousel_slides?lesson_id=eq.{lesson_id}&order=slide_order.asc"
        slides_response = requests.get(slides_url, headers=sb_headers_service(), timeout=30)

        slides = []
        if slides_response.status_code < 400:
            slide_data = slides_response.json()
            slides = [{
                'id': slide['id'],
                'order': slide['slide_order'],
                'title': slide.get('title'),
                'content': slide['content'],
                'image_url': slide.get('image_url')
            } for slide in slide_data]

        # Use playlist field, fallback to category for backwards compatibility
        playlist = lesson.get('playlist') or lesson.get('category', 'Lessons')

        return jsonify({
            'success': True,
            'lesson': {
                'id': lesson['id'],
                'title': lesson['title'],
                'description': lesson.get('description'),
                'playlist': playlist,
                'category': playlist,  # Keep for backwards compatibility
                'xp_reward': lesson.get('xp_reward', 25),
                'slides': slides
            }
        })

    except Exception as e:
        print(f"Error in get_carousel_lesson: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route("/carousel-lessons/<lesson_id>/complete", methods=["POST"])
def complete_carousel_lesson(lesson_id):
    """Mark a carousel lesson as completed and award XP"""
    guard = require_login()
    if guard:
        return guard

    try:
        from auth import sb_headers_service

        u = get_current_user()
        user_id = u.get("id")

        # Get the lesson to find XP reward
        lesson_url = f"{SUPABASE_URL}/rest/v1/carousel_lessons?id=eq.{lesson_id}&is_published=eq.true"
        lesson_response = requests.get(lesson_url, headers=sb_headers_service(), timeout=30)

        if lesson_response.status_code >= 400 or not lesson_response.json():
            return jsonify({'success': False, 'error': 'Lesson not found'}), 404

        lesson = lesson_response.json()[0]

        # Get current profile
        profile = ensure_profile_exists() or {}

        # Check if already completed
        completed_carousel = [x for x in (profile.get("completed_carousel_lessons") or "").split(",") if x]

        if lesson_id in completed_carousel:
            return jsonify({
                'success': True,
                'xp_awarded': 0,
                'message': 'Lesson already completed'
            })

        # Award XP
        xp_award = lesson.get('xp_reward', 25)
        current_xp = profile.get("xp", 0)
        new_xp = current_xp + xp_award

        # Calculate new level (every 100 XP = 1 level)
        new_level = max(1, new_xp // 100)

        # Add to completed carousel lessons
        completed_carousel.append(lesson_id)

        # Update profile
        payload = {
            "user_id": user_id,
            "xp": new_xp,
            "level": new_level,
            "completed_carousel_lessons": ",".join(completed_carousel),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Update streak
        merged = dict(profile)
        merged.update(payload)
        merged = update_streak_fields(merged)
        payload["streak"] = merged.get("streak", profile.get("streak", 0))
        payload["last_activity"] = merged.get("last_activity", profile.get("last_activity"))

        r = upsert_profile_row(payload, use_service_role=True)
        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to save progress"}), 500

        # Clear profile cache since we just updated it
        clear_profile_cache(user_id)

        return jsonify({
            'success': True,
            'xp_awarded': xp_award,
            'new_xp': new_xp,
            'new_level': new_level,
            'message': f'Lesson completed! +{xp_award} XP'
        })

    except Exception as e:
        print(f"Error in complete_carousel_lesson: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route("/carousel-lessons/<lesson_id>/progress", methods=["POST"])
def update_carousel_progress(lesson_id):
    """Update progress for a carousel lesson (track which slide user is on)"""
    guard = require_login()
    if guard:
        return guard

    try:
        data = request.get_json(silent=True) or {}
        current_slide = data.get("current_slide", 0)

        # For now, just acknowledge the progress update
        # In a full implementation, you'd store this in a separate progress table
        return jsonify({
            'success': True,
            'lesson_id': lesson_id,
            'current_slide': current_slide
        })

    except Exception as e:
        print(f"Error in update_carousel_progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# -------- Challenges API --------
@api_bp.route("/challenges", methods=["GET"])
def get_challenges():
    """Get all challenges with user progress"""
    guard = require_login()
    if guard:
        return guard

    try:
        import requests
        from auth import sb_headers_service

        u = get_current_user()
        user_id = u.get("id")

        # Get user profile for level (use cached for performance)
        profile = ensure_profile_exists() or {}
        user_level = profile.get("level", 1)

        # Fetch all published challenges
        challenges_url = f"{SUPABASE_URL}/rest/v1/challenges?is_published=eq.true&order=day_number.asc"
        challenges_response = requests.get(challenges_url, headers=sb_headers_service(), timeout=30)

        if challenges_response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load challenges"}), 500

        challenges = challenges_response.json()

        # Fetch user's progress on challenges
        user_challenges_url = f"{SUPABASE_URL}/rest/v1/user_challenges?user_id=eq.{user_id}"
        user_progress_response = requests.get(user_challenges_url, headers=sb_headers_service(), timeout=30)

        user_progress = {}
        if user_progress_response.status_code < 400:
            progress_data = user_progress_response.json()
            user_progress = {p["challenge_id"]: p for p in progress_data}

        # Combine challenges with user progress
        result_challenges = []
        for challenge in challenges:
            challenge_id = challenge["id"]
            progress = user_progress.get(challenge_id, {})

            # Check if unlocked (based on required level)
            is_unlocked = user_level >= challenge.get("required_level", 1)

            result_challenges.append({
                "id": challenge_id,
                "day_number": challenge["day_number"],
                "category": challenge["category"],
                "task": challenge["task"],
                "difficulty": challenge["difficulty"],
                "interaction_type": challenge["interaction_type"],
                "points": challenge["points"],
                "why_matters": challenge["why_matters"],
                "reflection_prompt": challenge["reflection_prompt"],
                "status": progress.get("status", "not_started"),
                "is_unlocked": is_unlocked,
                "is_current": challenge["day_number"] == user_level  # Current challenge = user level
            })

        # Get daily progress (challenges completed today)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()

        completed_challenges_today_url = f"{SUPABASE_URL}/rest/v1/user_challenges?user_id=eq.{user_id}&status=eq.completed&completed_at=gte.{today}T00:00:00Z"
        completed_today_response = requests.get(completed_challenges_today_url, headers=sb_headers_service(), timeout=30)

        challenges_completed_today = 0
        if completed_today_response.status_code < 400:
            challenges_completed_today = len(completed_today_response.json())

        # Get completed lessons today (from completed_lessons field)
        completed_lessons = [x for x in (profile.get("completed_lessons") or "").split(",") if x] if profile else []
        # For now, we don't track when lessons were completed, so we can't determine "today"
        # This would require updating the lessons completion to track timestamp

        daily_progress = {
            "challenges": {"completed": challenges_completed_today, "required": 1},
            "ai": {"completed": 0, "required": 1},  # TODO: Track AI practice
            "videos": {"completed": 0, "required": 1},  # TODO: Track video completion dates
            "innergame": {"completed": 0, "required": 1}  # TODO: Track inner game
        }

        return jsonify({
            "success": True,
            "challenges": result_challenges,
            "current_day": user_level,  # Current day = user level
            "user_level": user_level,
            "daily_progress": daily_progress
        })

    except Exception as e:
        print(f"Error in get_challenges: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/challenges/<challenge_id>/start", methods=["POST"])
def start_challenge(challenge_id):
    """Start a challenge"""
    guard = require_login()
    if guard:
        return guard

    try:
        import requests
        from auth import sb_headers_service

        u = get_current_user()
        user_id = u.get("id")

        # Check if challenge exists
        challenge_url = f"{SUPABASE_URL}/rest/v1/challenges?id=eq.{challenge_id}"
        challenge_response = requests.get(challenge_url, headers=sb_headers_service(), timeout=30)

        if challenge_response.status_code >= 400 or not challenge_response.json():
            return jsonify({"success": False, "error": "Challenge not found"}), 404

        # Insert or update user_challenges
        payload = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "status": "in_progress",
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        # Upsert (insert or update if exists)
        upsert_url = f"{SUPABASE_URL}/rest/v1/user_challenges"
        headers = sb_headers_service()
        headers["Prefer"] = "resolution=merge-duplicates"

        upsert_response = requests.post(upsert_url, headers=headers, json=payload, timeout=30)

        if upsert_response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to start challenge"}), 500

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error in start_challenge: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/challenges/<challenge_id>/complete", methods=["POST"])
def complete_challenge(challenge_id):
    """Complete a challenge and award XP"""
    guard = require_login()
    if guard:
        return guard

    try:
        import requests
        from auth import sb_headers_service

        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True) or {}
        reflection = data.get("reflection", "")

        # Get challenge details
        challenge_url = f"{SUPABASE_URL}/rest/v1/challenges?id=eq.{challenge_id}&select=*"
        challenge_response = requests.get(challenge_url, headers=sb_headers_service(), timeout=30)

        if challenge_response.status_code >= 400:
            return jsonify({"success": False, "error": "Challenge not found"}), 404

        challenges = challenge_response.json()
        if not challenges:
            return jsonify({"success": False, "error": "Challenge not found"}), 404

        challenge = challenges[0]
        xp_award = challenge["points"]

        # Check if already completed
        user_challenge_url = f"{SUPABASE_URL}/rest/v1/user_challenges?user_id=eq.{user_id}&challenge_id=eq.{challenge_id}&select=*"
        user_challenge_response = requests.get(user_challenge_url, headers=sb_headers_service(), timeout=30)

        already_completed = False
        if user_challenge_response.status_code < 400:
            user_challenges = user_challenge_response.json()
            if user_challenges and user_challenges[0].get("status") == "completed":
                already_completed = True
                xp_award = 0  # Don't award XP again

        # Mark challenge as completed
        payload = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "status": "completed",
            "reflection": reflection,
            "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

        upsert_url = f"{SUPABASE_URL}/rest/v1/user_challenges"
        headers = sb_headers_service()
        headers["Prefer"] = "resolution=merge-duplicates"

        upsert_response = requests.post(upsert_url, headers=headers, json=payload, timeout=30)

        if upsert_response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to complete challenge"}), 500

        # Award XP if not already completed
        if not already_completed and xp_award > 0:
            # Use cached profile for performance
            profile = ensure_profile_exists() or {}

            current_xp = profile.get("xp", 0)
            new_xp = current_xp + xp_award
            old_level = profile.get("level", 1)
            new_level = max(1, new_xp // 100)

            # Update profile
            profile_payload = {
                "user_id": user_id,
                "xp": new_xp,
                "level": new_level,
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }

            # Update streak
            merged = dict(profile)
            merged.update(profile_payload)
            merged = update_streak_fields(merged)
            profile_payload["streak"] = merged.get("streak", profile.get("streak", 0))
            profile_payload["last_activity"] = merged.get("last_activity", profile.get("last_activity"))

            r = upsert_profile_row(profile_payload, use_service_role=True)
            if r.status_code >= 400:
                print(f"Warning: Failed to update XP: {r.text}")
            else:
                # Clear profile cache since we just updated it
                clear_profile_cache(user_id)

        # Get daily progress
        today = datetime.now(timezone.utc).date().isoformat()
        completed_today_url = f"{SUPABASE_URL}/rest/v1/user_challenges?user_id=eq.{user_id}&status=eq.completed&completed_at=gte.{today}T00:00:00Z"
        completed_today_response = requests.get(completed_today_url, headers=sb_headers_service(), timeout=30)

        challenges_completed_today = 0
        if completed_today_response.status_code < 400:
            challenges_completed_today = len(completed_today_response.json())

        daily_progress = {
            "challenges": {"completed": challenges_completed_today, "required": 1},
            "ai": {"completed": 0, "required": 1},
            "videos": {"completed": 0, "required": 1},
            "innergame": {"completed": 0, "required": 1}
        }

        return jsonify({
            "success": True,
            "xp_awarded": xp_award if not already_completed else 0,
            "leveled_up": new_level > old_level if not already_completed else False,
            "new_level": new_level if not already_completed else old_level,
            "daily_progress": daily_progress
        })

    except Exception as e:
        print(f"Error in complete_challenge: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# PSYCHOLOGY GAMES API
# ============================================

@api_bp.route("/games/stats", methods=["GET"])
def get_game_stats():
    """Get user's game statistics for all game types"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        user_id = user["id"]

        # Fetch stats for all game types
        stats_url = f"{SUPABASE_URL}/rest/v1/user_game_stats?user_id=eq.{user_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        }

        response = requests.get(stats_url, headers=headers)

        if response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to fetch game stats"}), 500

        stats = response.json()

        # Format stats by game type
        stats_by_type = {}
        for stat in stats:
            game_type = stat["game_type"]
            stats_by_type[game_type] = {
                "total_sessions": stat.get("total_sessions", 0),
                "total_questions_answered": stat.get("total_questions_answered", 0),
                "total_correct_answers": stat.get("total_correct_answers", 0),
                "total_xp_earned": stat.get("total_xp_earned", 0),
                "accuracy": round((stat.get("total_correct_answers", 0) / stat.get("total_questions_answered", 1)) * 100, 1) if stat.get("total_questions_answered", 0) > 0 else 0,
                "current_difficulty": stat.get("current_difficulty", "normal"),
                "best_streak": stat.get("best_streak", 0)
            }

        return jsonify({
            "success": True,
            "stats": stats_by_type
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/<game_type>/question", methods=["GET"])
def get_game_question(game_type):
    """Get a random question for the specified game type - OPTIMIZED with caching"""
    guard = require_login()
    if guard:
        return guard

    # Validate game type
    valid_game_types = ["attachment-game", "cognitive-distortions-game", "communication-styles-game", "love-languages-game"]
    if game_type not in valid_game_types:
        return jsonify({"success": False, "error": "Invalid game type"}), 400

    # Convert URL format to database format
    db_game_type = game_type.replace("-game", "").replace("-", "_")

    try:
        user = get_current_user()
        user_id = user["id"]

        # Get difficulty from query param (default to 'easy')
        difficulty = request.args.get("difficulty", "easy")

        # Get recently answered questions (optional - only if table exists)
        recent_question_ids = []
        try:
            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            }
            recent_url = f"{SUPABASE_URL}/rest/v1/user_answered_questions?user_id=eq.{user_id}&order=answered_at.desc&limit=10"
            recent_response = requests.get(recent_url, headers=headers, timeout=2)
            if recent_response.status_code == 200:
                recent_question_ids = [q["question_id"] for q in recent_response.json()]
        except:
            pass  # Table doesn't exist or error, continue without filtering

        # Get question from cache (FAST!)
        question = game_cache.get_random_question(db_game_type, difficulty, recent_question_ids)

        if not question:
            return jsonify({"success": False, "error": f"No questions available for {db_game_type}. Please add questions to the database."}), 404

        return jsonify({
            "success": True,
            "question": {
                "id": question["id"],
                "question_text": question["question_text"],
                "options": question["options"],
                "hint": question.get("hint"),
                "xp_reward": question.get("xp_reward", 5),
                "difficulty": question["difficulty"]
            }
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/<game_type>/answer", methods=["POST"])
def submit_game_answer(game_type):
    """Submit an answer to a game question"""
    guard = require_login()
    if guard:
        return guard

    # Validate game type
    valid_game_types = ["attachment-game", "cognitive-distortions-game", "communication-styles-game", "love-languages-game"]
    if game_type not in valid_game_types:
        return jsonify({"success": False, "error": "Invalid game type"}), 400

    # Convert URL format to database format
    db_game_type = game_type.replace("-game", "").replace("-", "_")

    try:
        user = get_current_user()
        user_id = user["id"]

        data = request.get_json()
        question_id = data.get("question_id")
        user_answer = data.get("answer")
        session_id = data.get("session_id")  # Optional - for tracking sessions

        if not question_id or not user_answer:
            return jsonify({"success": False, "error": "Missing question_id or answer"}), 400

        # Fetch the question to check the correct answer
        question_url = f"{SUPABASE_URL}/rest/v1/game_questions?id=eq.{question_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }

        question_response = requests.get(question_url, headers=headers)

        if question_response.status_code >= 400 or not question_response.json():
            return jsonify({"success": False, "error": "Question not found"}), 404

        question = question_response.json()[0]
        correct_answer = question["correct_answer"]
        is_correct = user_answer.strip() == correct_answer.strip()
        xp_earned = question.get("xp_reward", 5) if is_correct else 0

        # Record the answer
        answer_payload = {
            "user_id": user_id,
            "question_id": question_id,
            "session_id": session_id,
            "was_correct": is_correct
        }

        answer_url = f"{SUPABASE_URL}/rest/v1/user_answered_questions"
        answer_response = requests.post(answer_url, headers=headers, json=answer_payload)

        # Update user's XP if correct
        if is_correct and xp_earned > 0:
            profile_url = f"{SUPABASE_URL}/rest/v1/profiles?user_id=eq.{user_id}"
            profile_response = requests.get(profile_url, headers=headers)

            if profile_response.status_code == 200 and profile_response.json():
                profile = profile_response.json()[0]
                current_xp = profile.get("xp", 0)
                new_xp = current_xp + xp_earned
                new_level = max(1, new_xp // 100)

                # Update profile with new XP
                update_payload = {"xp": new_xp, "level": new_level}
                update_url = f"{SUPABASE_URL}/rest/v1/profiles?user_id=eq.{user_id}"
                requests.patch(update_url, headers=headers, json=update_payload)

        return jsonify({
            "success": True,
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanation": question.get("explanation"),
            "xp_earned": xp_earned
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/games/complete-session", methods=["POST"])
def complete_game_session():
    """Complete a game session and update overall statistics"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        user_id = user["id"]

        data = request.get_json()
        game_type = data.get("game_type")  # e.g., "attachment", "cognitive_distortions"
        questions_answered = data.get("questions_answered", 0)
        correct_answers = data.get("correct_answers", 0)
        total_xp_earned = data.get("total_xp_earned", 0)
        difficulty = data.get("difficulty", "normal")

        if not game_type:
            return jsonify({"success": False, "error": "Missing game_type"}), 400

        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }

        # Create session record
        session_payload = {
            "user_id": user_id,
            "game_type": game_type,
            "questions_answered": questions_answered,
            "correct_answers": correct_answers,
            "total_xp_earned": total_xp_earned,
            "difficulty": difficulty,
            "completed_at": "now()"
        }

        session_url = f"{SUPABASE_URL}/rest/v1/user_game_sessions"
        session_response = requests.post(session_url, headers=headers, json=session_payload)

        # Update or create user_game_stats
        stats_url = f"{SUPABASE_URL}/rest/v1/user_game_stats?user_id=eq.{user_id}&game_type=eq.{game_type}"
        stats_response = requests.get(stats_url, headers=headers)

        if stats_response.status_code == 200 and stats_response.json():
            # Update existing stats
            existing_stats = stats_response.json()[0]

            update_payload = {
                "total_sessions": existing_stats.get("total_sessions", 0) + 1,
                "total_questions_answered": existing_stats.get("total_questions_answered", 0) + questions_answered,
                "total_correct_answers": existing_stats.get("total_correct_answers", 0) + correct_answers,
                "total_xp_earned": existing_stats.get("total_xp_earned", 0) + total_xp_earned,
                "current_difficulty": difficulty,
                "updated_at": "now()"
            }

            update_url = f"{SUPABASE_URL}/rest/v1/user_game_stats?user_id=eq.{user_id}&game_type=eq.{game_type}"
            requests.patch(update_url, headers=headers, json=update_payload)
        else:
            # Create new stats record
            create_payload = {
                "user_id": user_id,
                "game_type": game_type,
                "total_sessions": 1,
                "total_questions_answered": questions_answered,
                "total_correct_answers": correct_answers,
                "total_xp_earned": total_xp_earned,
                "current_difficulty": difficulty,
                "best_streak": 0
            }

            create_url = f"{SUPABASE_URL}/rest/v1/user_game_stats"
            requests.post(create_url, headers=headers, json=create_payload)

        return jsonify({
            "success": True,
            "message": "Session completed successfully"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# AI PRACTICE API ENDPOINTS
# ============================================

@api_bp.route("/ai-practice/topics/<practice_type>", methods=["GET"])
def get_ai_topics(practice_type):
    """Get practice topics for a specific practice type"""
    guard = require_login()
    if guard:
        return guard

    try:
        topics, r = get_practice_topics(practice_type, use_service_role=True)

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load topics"}), 500

        return jsonify({"success": True, "topics": topics})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/session/start", methods=["POST"])
def start_ai_session():
    """Start a new AI practice session"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        data = request.get_json()

        session_data, r = create_practice_session(
            user_id=user["id"],
            practice_type=data.get("practice_type"),
            topic_id=data.get("topic_id"),
            session_title=data.get("title"),
            scenario_context=data.get("context"),
            use_service_role=True
        )

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to create session"}), 400

        return jsonify({"success": True, "session": session_data})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/message", methods=["POST"])
def save_ai_message():
    """Save a conversation message"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        data = request.get_json()

        message, r = add_conversation_message(
            session_id=data["session_id"],
            user_id=user["id"],
            role=data["role"],
            content=data["content"],
            message_order=data["message_order"],
            technique_used=data.get("technique"),
            effectiveness_score=data.get("score"),
            ai_analysis=data.get("analysis"),
            use_service_role=True
        )

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to save message"}), 400

        return jsonify({"success": True, "message": message})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/session/<session_id>/messages", methods=["GET"])
def get_ai_messages(session_id):
    """Get conversation history for a session"""
    guard = require_login()
    if guard:
        return guard

    try:
        messages, r = get_conversation_messages(session_id, use_service_role=True)

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load messages"}), 500

        return jsonify({"success": True, "messages": messages})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/session/<session_id>/complete", methods=["POST"])
def complete_ai_session(session_id):
    """Complete a practice session"""
    guard = require_login()
    if guard:
        return guard

    try:
        data = request.get_json()

        r = complete_practice_session(
            session_id=session_id,
            user_score=data.get("score"),
            ai_feedback=data.get("feedback"),
            use_service_role=True
        )

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to complete session"}), 400

        return jsonify({"success": True})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/stats", methods=["GET"])
def get_ai_stats():
    """Get user's AI practice statistics"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        practice_type = request.args.get("practice_type")

        stats, r = get_user_ai_stats(user["id"], practice_type, use_service_role=True)

        if r.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load stats"}), 500

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/ai-practice/dashboard", methods=["GET"])
def get_ai_dashboard():
    """Get all AI practice dashboard data"""
    guard = require_login()
    if guard:
        return guard

    try:
        user = get_current_user()
        data = get_practice_dashboard_data(user["id"])

        return jsonify({"success": True, **data})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# -------- Storage API (Admin Only) --------
# HIDDEN: Daily Directive API - feature temporarily disabled
# @api_bp.route("/daily-directive/complete", methods=["POST"])
# def complete_daily_directive():
#     """Complete a daily directive and award XP"""
#     guard = require_login()
#     if guard:
#         return guard
#
#     try:
#         user = get_current_user()
#         user_id = user.get("id")
#
#         # Get current profile
#         profile = ensure_profile_exists() or {}
#
#         # Award XP for completing daily directive
#         xp_award = 50
#         current_xp = profile.get("xp", 0)
#         new_xp = current_xp + xp_award
#
#         # Calculate new level (every 100 XP = 1 level)
#         new_level = max(1, new_xp // 100)
#
#         # Update profile
#         payload = {
#             "user_id": user_id,
#             "xp": new_xp,
#             "level": new_level,
#             "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
#         }
#
#         # Update streak
#         merged = dict(profile)
#         merged.update(payload)
#         merged = update_streak_fields(merged)
#         payload["streak"] = merged.get("streak", profile.get("streak", 0))
#         payload["last_activity"] = merged.get("last_activity", profile.get("last_activity"))
#
#         r = upsert_profile_row(payload, use_service_role=True)
#         if r.status_code >= 400:
#             return jsonify({"success": False, "error": "Failed to save progress"}), 500
#
#         # Clear profile cache since we just updated it
#         clear_profile_cache(user_id)
#
#         return jsonify({
#             "success": True,
#             "xp_awarded": xp_award,
#             "new_xp": new_xp,
#             "new_level": new_level,
#             "new_streak": payload["streak"],
#             "message": f"Daily directive completed! +{xp_award} XP"
#         })
#
#     except Exception as e:
#         print(f"Error in complete_daily_directive: {e}")
#         traceback.print_exc()
#         return jsonify({"success": False, "error": str(e)}), 500

# -------- Storage API (Admin Only) --------
@api_bp.route("/storage/videos", methods=["GET"])
def list_videos():
    """List all videos in storage"""
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        r = storage_list(VIDEOS_BUCKET, "videos")

        if r.status_code >= 400:
            return jsonify({"error": "Failed to list videos", "details": r.text}), 500

        videos = r.json()
        return jsonify(videos if isinstance(videos, list) else [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route("/storage/videos/<path:video_name>", methods=["DELETE"])
def delete_video(video_name):
    """Delete a video from storage"""
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        path = f"videos/{video_name}"
        r = storage_delete(VIDEOS_BUCKET, [path])

        if r.status_code >= 400:
            return jsonify({"success": False, "message": f"Failed to delete video: {r.text}"}), 500

        return jsonify({"success": True, "message": "Video deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
