"""
Admin routes for PathForge application.
Handles admin dashboard, user management, content management, and media uploads.
"""
import mimetypes

from flask import Blueprint, request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename

from auth import require_admin_auth, verify_form_csrf, supabase_admin_list_users
from storage import storage_upload, storage_list
from config import VIDEOS_BUCKET, PLAYLISTS
from media import upload_file_to_storage, list_storage_files, delete_storage_file

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route("/dashboard")
def dashboard():
    guard = require_admin_auth()
    if guard:
        return guard

    # Initialize default stats
    total_users = 0
    total_media = 0
    total_challenges = 0
    total_lessons = 0
    completed_challenges = 0
    total_xp = 0
    recent_users = []

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
        from datetime import datetime

        # Fetch user count and recent users
        try:
            users_response = supabase_admin_list_users(page=1, per_page=1000)
            if users_response.status_code < 400:
                users_data = users_response.json()
                all_users = users_data.get("users", [])
                total_users = len(all_users)

                # Process users for display
                processed_users = []
                for user in all_users:
                    metadata = user.get('user_metadata', {})
                    user_obj = {
                        'id': user.get('id'),
                        'email': user.get('email', 'N/A'),
                        'username': metadata.get('username') or user.get('email', 'N/A').split('@')[0],
                        'is_admin': metadata.get('is_admin', False),
                        'created_at': datetime.fromisoformat(user.get('created_at', '').replace('Z', '+00:00')) if user.get('created_at') else datetime.now()
                    }
                    processed_users.append(user_obj)

                # Sort by created_at and get 5 most recent
                processed_users.sort(key=lambda x: x['created_at'], reverse=True)
                recent_users = processed_users[:5]

                print(f"Dashboard: Found {total_users} users, showing {len(recent_users)} recent users")
        except Exception as e:
            print(f"Error fetching users: {e}")

        # Fetch videos count
        try:
            headers = {
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json"
            }

            videos_url = f"{SUPABASE_URL}/rest/v1/videos?select=*"
            videos_response = requests.get(videos_url, headers=headers, timeout=30)
            if videos_response.status_code < 400:
                videos_list = videos_response.json()
                total_media = len(videos_list)
                total_lessons = total_media
                print(f"Dashboard: Found {total_media} videos")
        except Exception as e:
            print(f"Error fetching videos: {e}")

    except Exception as e:
        print(f"Error loading dashboard stats: {e}")

    print(f"Dashboard rendering with: users={total_users}, media={total_media}, recent_users={len(recent_users)}")

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_challenges=total_challenges,
        total_lessons=total_lessons,
        total_media=total_media,
        completed_challenges=completed_challenges,
        total_xp=total_xp,
        recent_users=recent_users
    )

@admin_bp.route("/users")
def users():
    guard = require_admin_auth()
    if guard:
        return guard

    import requests
    from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

    r = supabase_admin_list_users(page=1, per_page=200)
    if r.status_code >= 400:
        return f"Failed to list users: {r.status_code}\n{r.text}", 500

    data = r.json()
    users = data.get("users", [])

    # Fetch profile data for all users
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        profiles_url = f"{SUPABASE_URL}/rest/v1/profiles?select=*"
        profiles_response = requests.get(profiles_url, headers=headers, timeout=30)

        if profiles_response.status_code < 400:
            profiles = profiles_response.json()
            # Create lookup dictionary by user_id
            profiles_dict = {p['user_id']: p for p in profiles}
        else:
            profiles_dict = {}
            print(f"Warning: Failed to fetch profiles: {profiles_response.status_code}")
    except Exception as e:
        print(f"Error fetching profiles: {e}")
        profiles_dict = {}

    # Merge user_metadata and profile data into main user object
    for user in users:
        user_id = user.get('id')
        metadata = user.get('user_metadata', {})

        # Add metadata
        user['is_admin'] = metadata.get('is_admin', False)
        user['subscription_status'] = metadata.get('subscription_status', 'free')
        user['is_premium'] = user['subscription_status'] in ['pro', 'premium']

        # Add username from metadata if available
        if 'username' not in user and user.get('email'):
            user['username'] = user['email'].split('@')[0]

        # Add profile data (XP, level, streak, etc.)
        profile = profiles_dict.get(user_id, {})
        user['progress'] = {
            'xp': profile.get('xp', 0),
            'level': profile.get('level', 1),
            'streak': profile.get('streak', 0),
            'onboarding_completed': profile.get('onboarding_completed', False),
            'completed_lessons': profile.get('completed_lessons', ''),
            'last_lesson_at': profile.get('last_lesson_at'),
            'created_at': profile.get('created_at'),
        }

    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)

    # Calculate user statistics
    premium_count = sum(1 for u in users if u.get('is_premium'))
    total_xp = sum(u.get('progress', {}).get('xp', 0) for u in users)
    avg_xp = total_xp // len(users) if users else 0

    user_stats = {
        'total': len(users),
        'premium': premium_count,
        'free': len(users) - premium_count,
        'total_xp': total_xp,
        'avg_xp': avg_xp
    }

    # Simple chart data (last 7 days)
    chart_data = {
        'labels': [],
        'data': []
    }

    return render_template("admin/users.html", users=users, user_stats=user_stats, chart_data=chart_data)


@admin_bp.route("/users/<user_id>/edit", methods=["POST"])
def edit_user(user_id):
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        data = request.get_json()
        is_admin = data.get('is_admin', False)
        subscription_status = data.get('subscription_status', 'free')

        # Update user metadata in Supabase
        # Note: This updates user_metadata which is accessible to the user
        update_data = {
            "user_metadata": {
                "is_admin": is_admin,
                "subscription_status": subscription_status
            }
        }

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Update user via Supabase Admin API
        url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
        r = requests.put(url, headers=headers, json=update_data, timeout=30)

        if r.status_code >= 400:
            return {"success": False, "message": f"Failed to update user: {r.text}"}, 500

        return {"success": True, "message": "User updated successfully"}

    except Exception as e:
        return {"success": False, "message": str(e)}, 500


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
def delete_user(user_id):
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Delete user via Supabase Admin API
        url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"
        r = requests.delete(url, headers=headers, timeout=30)

        if r.status_code >= 400:
            return {"success": False, "message": f"Failed to delete user: {r.text}"}, 500

        return {"success": True, "message": "User deleted successfully"}

    except Exception as e:
        return {"success": False, "message": str(e)}, 500


# ============================================================================
# VIDEO MANAGEMENT
# ============================================================================

@admin_bp.route("/videos", methods=["GET", "POST"])
def videos():
    guard = require_admin_auth()
    if guard:
        return guard

    # Handle video upload
    if request.method == "POST":
        if not verify_form_csrf(request.form.get("csrf_token")):
            flash("Invalid CSRF token.", "error")
            return redirect(url_for("admin.videos"))

        try:
            import requests
            from auth import get_current_user

            # Get form data
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            playlist = request.form.get("playlist", "Lessons")
            is_premium = request.form.get("is_premium", "false") == "true"

            # Get chapters if provided
            import json
            chapters_json = request.form.get("chapters", "[]")
            try:
                chapters = json.loads(chapters_json) if chapters_json else []
            except:
                chapters = []

            # Get video file
            video_file = request.files.get("video_file")
            if not video_file or video_file.filename.strip() == "":
                flash("Please select a video file.", "error")
                return redirect(url_for("admin.videos"))

            # Validate file
            if not title:
                flash("Please provide a title for the video.", "error")
                return redirect(url_for("admin.videos"))

            # Secure filename
            filename = secure_filename(video_file.filename)
            storage_path = f"videos/{filename}"

            # Upload to Supabase Storage
            file_bytes = video_file.read()
            guessed_type, _ = mimetypes.guess_type(filename)
            content_type = video_file.mimetype or guessed_type or "application/octet-stream"

            upload_response = storage_upload(VIDEOS_BUCKET, storage_path, file_bytes, content_type)

            if upload_response.status_code >= 400:
                flash(f"Failed to upload video: {upload_response.text}", "error")
                return redirect(url_for("admin.videos"))

            # Get current user
            current_user = get_current_user()
            created_by = current_user.get("id") if current_user else None

            # Generate description if not provided
            if not description:
                description = f"Watch and learn from {title}. Complete this lesson to earn 25 XP!"

            # Save metadata to database
            video_metadata = {
                "filename": filename,
                "title": title,
                "description": description,
                "playlist": playlist,
                "category": playlist,  # Keep category for backwards compatibility
                "is_premium": is_premium,
                "required_level": 1,
                "is_published": True,
                "created_by": created_by,
                "chapters": chapters
            }

            headers = {
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }

            db_url = f"{SUPABASE_URL}/rest/v1/videos"
            db_response = requests.post(db_url, headers=headers, json=video_metadata, timeout=30)

            if db_response.status_code >= 400:
                flash(f"Video uploaded but failed to save metadata: {db_response.text}", "warning")
            else:
                access_level = "Premium" if is_premium else "Free"
                flash(f"Video '{title}' uploaded successfully as {access_level}!", "success")

            return redirect(url_for("admin.videos"))

        except Exception as e:
            print(f"Error uploading video: {e}")
            import traceback
            traceback.print_exc()
            flash(f"Error uploading video: {str(e)}", "error")
            return redirect(url_for("admin.videos"))

    # Handle GET request - display videos
    videos_list = []

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Fetch videos from storage
        storage_videos = list_storage_files("videos/")
        print(f"Found {len(storage_videos)} videos in storage")

        # Fetch videos from database
        db_url = f"{SUPABASE_URL}/rest/v1/videos?select=*&order=created_at.desc"
        db_response = requests.get(db_url, headers=headers, timeout=30)

        db_videos = {}
        if db_response.status_code < 400:
            for video in db_response.json():
                db_videos[video.get('filename')] = video
            print(f"Found {len(db_videos)} videos in database")

        # Merge storage and database data
        for storage_video in storage_videos:
            filename = storage_video.get('name', '')

            if filename in db_videos:
                # Video has database entry - use that
                videos_list.append(db_videos[filename])
            else:
                # Video only in storage - create default entry
                title = filename.replace('.mp4', '').replace('.webm', '').replace('.ogg', '').replace('_', ' ').title()
                videos_list.append({
                    'id': None,  # No database ID yet
                    'filename': filename,
                    'title': title,
                    'playlist': None,
                    'category': 'Uncategorized',
                    'is_premium': False,
                    'created_at': storage_video.get('created_at', ''),
                    'needs_sync': True  # Flag for UI
                })

        print(f"Total videos to display: {len(videos_list)}")

    except Exception as e:
        print(f"Error fetching videos: {e}")
        import traceback
        traceback.print_exc()

    return render_template("admin/videos.html", videos=videos_list, playlists=PLAYLISTS, bucket=VIDEOS_BUCKET)


@admin_bp.route("/videos/delete/<path:video_path>", methods=["POST"])
def delete_video(video_path):
    guard = require_admin_auth()
    if guard:
        return guard

    if not verify_form_csrf(request.form.get("csrf_token")):
        flash("Invalid CSRF token.", "error")
        return redirect(url_for("admin.videos"))

    success = delete_storage_file(f"videos/{video_path}")

    if success:
        flash("Video deleted successfully!", "success")
    else:
        flash("Failed to delete video.", "error")

    return redirect(url_for("admin.videos"))


@admin_bp.route("/videos/<int:video_id>/edit", methods=["POST"])
def edit_video(video_id):
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        playlist = data.get('playlist', '').strip()
        chapters = data.get('chapters', [])

        if not title:
            return {"success": False, "message": "Title is required"}, 400

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Update video metadata in database
        update_data = {
            "title": title,
            "description": description,
            "playlist": playlist,
            "category": playlist,  # Keep category in sync with playlist
            "chapters": chapters  # Store chapters as JSONB array
        }

        db_url = f"{SUPABASE_URL}/rest/v1/videos?id=eq.{video_id}"
        db_response = requests.patch(db_url, headers=headers, json=update_data, timeout=30)

        if db_response.status_code >= 400:
            return {"success": False, "message": f"Failed to update video: {db_response.text}"}, 500

        return {"success": True, "message": "Video updated successfully"}

    except Exception as e:
        print(f"Error updating video: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}, 500


@admin_bp.route("/videos/import-chapters", methods=["POST"])
def import_chapters():
    """Import chapters for multiple videos from JSON"""
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        # Get JSON data from request
        chapters_data = request.get_json()

        if not chapters_data or not isinstance(chapters_data, dict):
            return {"success": False, "message": "Invalid JSON format"}, 400

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Get all videos from database
        db_url = f"{SUPABASE_URL}/rest/v1/videos?select=id,filename"
        db_response = requests.get(db_url, headers=headers, timeout=30)

        if db_response.status_code >= 400:
            return {"success": False, "message": "Failed to fetch videos from database"}, 500

        videos = db_response.json()
        filename_to_id = {v["filename"]: v["id"] for v in videos}

        # Update chapters for each video in the JSON
        updated_count = 0
        errors = []

        for filename, chapters in chapters_data.items():
            if filename not in filename_to_id:
                errors.append(f"Video not found: {filename}")
                continue

            video_id = filename_to_id[filename]

            # Validate chapters format
            if not isinstance(chapters, list):
                errors.append(f"Invalid chapters format for {filename}")
                continue

            # Validate each chapter
            valid_chapters = []
            for chapter in chapters:
                if not isinstance(chapter, dict) or 'time' not in chapter or 'title' not in chapter:
                    errors.append(f"Invalid chapter format in {filename}")
                    continue
                valid_chapters.append({
                    "time": int(chapter["time"]),
                    "title": str(chapter["title"])
                })

            if not valid_chapters:
                continue

            # Sort chapters by time
            valid_chapters.sort(key=lambda x: x["time"])

            # Update video with chapters
            update_url = f"{SUPABASE_URL}/rest/v1/videos?id=eq.{video_id}"
            update_response = requests.patch(
                update_url,
                headers=headers,
                json={"chapters": valid_chapters},
                timeout=30
            )

            if update_response.status_code < 400:
                updated_count += 1
            else:
                errors.append(f"Failed to update {filename}: {update_response.text}")

        result = {
            "success": True,
            "updated": updated_count,
            "total": len(chapters_data),
        }

        if errors:
            result["errors"] = errors

        return result

    except Exception as e:
        print(f"Error importing chapters: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}, 500


@admin_bp.route("/videos/export-chapters", methods=["GET"])
def export_chapters():
    """Export all video chapters as JSON"""
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        }

        # Get all videos with chapters
        db_url = f"{SUPABASE_URL}/rest/v1/videos?select=filename,chapters"
        db_response = requests.get(db_url, headers=headers, timeout=30)

        if db_response.status_code >= 400:
            return {"success": False, "message": "Failed to fetch videos"}, 500

        videos = db_response.json()

        # Build chapters dictionary
        chapters_dict = {}
        for video in videos:
            filename = video.get("filename")
            chapters = video.get("chapters", [])

            # Only include videos that have chapters
            if filename and chapters and len(chapters) > 0:
                chapters_dict[filename] = chapters

        return {
            "success": True,
            "chapters": chapters_dict,
            "count": len(chapters_dict)
        }

    except Exception as e:
        print(f"Error exporting chapters: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}, 500


@admin_bp.route("/videos/<int:video_id>/toggle-premium", methods=["POST"])
def toggle_video_premium(video_id):
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        data = request.get_json()
        is_premium = data.get('is_premium', False)

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Update video premium status in database
        update_data = {"is_premium": is_premium}
        db_url = f"{SUPABASE_URL}/rest/v1/videos?id=eq.{video_id}"
        db_response = requests.patch(db_url, headers=headers, json=update_data, timeout=30)

        if db_response.status_code >= 400:
            return {"success": False, "message": f"Failed to update video: {db_response.text}"}, 500

        return {"success": True, "message": f"Video set to {'premium' if is_premium else 'free'}"}

    except Exception as e:
        return {"success": False, "message": str(e)}, 500


@admin_bp.route("/playlists/add", methods=["POST"])
def add_playlist():
    """
    Playlists are now hardcoded. This endpoint returns an info message.
    To add a new playlist category, update the hardcoded list in the videos() function.
    """
    guard = require_admin_auth()
    if guard:
        return guard

    return {
        "success": False,
        "message": "Playlists are now managed as hardcoded categories. Update the code to add new categories."
    }, 400


@admin_bp.route("/videos/sync", methods=["POST"])
def sync_video():
    guard = require_admin_auth()
    if guard:
        return guard

    try:
        import requests
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
        from auth import get_current_user

        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return {"success": False, "message": "Filename is required"}, 400

        # Get current admin user ID
        current_user = get_current_user()
        created_by = current_user.get("id") if current_user else None

        # Generate title from filename
        title = filename.replace('.mp4', '').replace('.webm', '').replace('.ogg', '').replace('_', ' ').replace('-', ' ').strip().title()
        if title.replace(' ', '').isdigit():
            title = f"Lesson {title}"

        # Create database entry for video
        video_data = {
            "filename": filename,
            "title": title,
            "description": f"Watch and learn from {title}. Complete this lesson to earn 25 XP!",
            "playlist": "Lessons",
            "category": "Lessons",  # Keep category for backwards compatibility
            "is_premium": False,
            "required_level": 1,
            "is_published": True,
            "created_by": created_by
        }

        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        db_url = f"{SUPABASE_URL}/rest/v1/videos"
        db_response = requests.post(db_url, headers=headers, json=video_data, timeout=30)

        if db_response.status_code >= 400:
            return {"success": False, "message": f"Failed to sync video: {db_response.text}"}, 500

        return {"success": True, "message": "Video synced to database successfully"}

    except Exception as e:
        return {"success": False, "message": str(e)}, 500


# ============================================================================
# COMMUNITY/FORUM MANAGEMENT
# ============================================================================

@admin_bp.route("/forum-posts")
def forum_posts():
    guard = require_admin_auth()
    if guard:
        return guard

    # Placeholder: Forum posts
    posts = []
    stats = {
        'total_posts': 0,
        'total_comments': 0,
        'total_likes': 0
    }

    return render_template("admin/forum_posts.html", posts=posts, stats=stats)


@admin_bp.route("/forum-tags")
def forum_tags():
    guard = require_admin_auth()
    if guard:
        return guard

    # Placeholder: Forum tags
    tags = []

    return render_template("admin/forum_tags.html", tags=tags)


# ============================================================================
# DATABASE MANAGEMENT
# ============================================================================

@admin_bp.route("/database")
def database():
    guard = require_admin_auth()
    if guard:
        return guard

    # Placeholder: Database info
    db_info = {
        'tables': [],
        'size': 'N/A',
        'status': 'Connected to Supabase'
    }

    return render_template("admin/database.html", db_info=db_info)
