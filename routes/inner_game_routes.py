"""
Inner Game routes for PathForge application (Simplified 3-Table Version).
Handles personalized emotional regulation, confidence-building, and fear work.
"""
from datetime import datetime, timezone, timedelta
import requests
from flask import Blueprint, request, jsonify

from auth import require_login, get_current_user, sb_headers_service
from config import SUPABASE_URL

inner_game_bp = Blueprint('inner_game', __name__, url_prefix='/api/inner-game')

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_profile(user_id):
    """Get user's inner game profile"""
    url = f"{SUPABASE_URL}/rest/v1/inner_game_profiles?user_id=eq.{user_id}"
    response = requests.get(url, headers=sb_headers_service(), timeout=30)
    if response.status_code < 400:
        profiles = response.json()
        return profiles[0] if profiles else None
    return None

def update_profile_stats(user_id):
    """Update profile statistics (total reps, entries, streak)"""
    profile = get_profile(user_id)
    if not profile:
        return

    # Count completed reps
    reps_url = f"{SUPABASE_URL}/rest/v1/inner_game_activities?user_id=eq.{user_id}&activity_type=eq.daily_rep&status=eq.completed"
    reps_response = requests.get(reps_url, headers=sb_headers_service(), timeout=30)
    total_reps = len(reps_response.json()) if reps_response.status_code < 400 else 0

    # Count journal entries
    entries_url = f"{SUPABASE_URL}/rest/v1/inner_game_entries?user_id=eq.{user_id}&entry_type=in.(journal_quick,journal_full)"
    entries_response = requests.get(entries_url, headers=sb_headers_service(), timeout=30)
    total_entries = len(entries_response.json()) if entries_response.status_code < 400 else 0

    # Calculate streak
    today = datetime.now().date()
    last_activity = profile.get('last_activity_date')
    current_streak = profile.get('current_streak_days', 0)

    if last_activity:
        last_date = datetime.fromisoformat(str(last_activity)).date() if isinstance(last_activity, str) else last_activity
        days_diff = (today - last_date).days

        if days_diff == 0:
            # Same day, keep streak
            pass
        elif days_diff == 1:
            # Next day, increment streak
            current_streak += 1
        else:
            # Broke streak
            current_streak = 1
    else:
        current_streak = 1

    # Update profile
    update_url = f"{SUPABASE_URL}/rest/v1/inner_game_profiles?user_id=eq.{user_id}"
    update_data = {
        "total_reps_completed": total_reps,
        "total_journal_entries": total_entries,
        "current_streak_days": current_streak,
        "last_activity_date": str(today)
    }
    requests.patch(update_url, json=update_data, headers=sb_headers_service(), timeout=30)

# ============================================================
# ASSESSMENT & PROFILE
# ============================================================

@inner_game_bp.route('/assessment', methods=['POST'])
def submit_assessment():
    """Submit initial assessment"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        profile_data = {
            "user_id": user_id,
            "primary_goal": data.get("primary_goal"),
            "attachment_style": data.get("attachment_style"),
            "baseline_confidence": data.get("baseline_confidence"),
            "baseline_social_anxiety": data.get("baseline_social_anxiety"),
            "boundary_strength": data.get("boundary_strength"),
            "rumination_score": data.get("rumination_score"),
            "assessment_completed": True
        }

        # Check if profile exists
        existing = get_profile(user_id)

        if existing:
            # Update
            url = f"{SUPABASE_URL}/rest/v1/inner_game_profiles?user_id=eq.{user_id}"
            response = requests.patch(url, json=profile_data, headers=sb_headers_service(), timeout=30)
        else:
            # Create
            url = f"{SUPABASE_URL}/rest/v1/inner_game_profiles"
            response = requests.post(url, json=profile_data, headers=sb_headers_service(), timeout=30)

        if response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to save assessment"}), 500

        # Generate first weekly plan
        create_weekly_plan(user_id)

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error in submit_assessment: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@inner_game_bp.route('/profile', methods=['GET'])
def get_profile_endpoint():
    """Get user's profile - auto-create from onboarding data if needed"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        # Try to get existing inner game profile
        profile = get_profile(user_id)

        # If no profile exists, create one from onboarding data
        if not profile:
            from database import get_profile_row
            # Get user's onboarding profile
            onboarding_profile, _ = get_profile_row(user_id, use_service_role=True)

            if onboarding_profile and onboarding_profile.get("onboarding_completed"):
                # Auto-create inner game profile from onboarding data
                # Map goals to primary_goal
                goals = onboarding_profile.get("goals", "").lower()
                primary_goal = "confidence"  # default
                if "dating" in goals or "relationship" in goals:
                    primary_goal = "dating"
                elif "social" in goals:
                    primary_goal = "social_skills"
                elif "emotion" in goals or "anxiety" in goals:
                    primary_goal = "emotional_control"

                # Create profile with default values
                profile_data = {
                    "user_id": user_id,
                    "primary_goal": primary_goal,
                    "attachment_style": "secure",  # default, user can change later
                    "baseline_confidence": 5,
                    "baseline_social_anxiety": 5,
                    "boundary_strength": 5,
                    "rumination_score": 5,
                    "assessment_completed": True  # Mark as completed to skip assessment
                }

                url = f"{SUPABASE_URL}/rest/v1/inner_game_profiles"
                response = requests.post(url, json=profile_data, headers=sb_headers_service(), timeout=30)

                if response.status_code < 400:
                    profile = response.json()[0] if response.json() else None
                    # Create first weekly plan
                    create_weekly_plan(user_id)

        return jsonify({
            "success": True,
            "profile": profile,
            "needs_assessment": False  # Never show assessment if onboarding is done
        })

    except Exception as e:
        print(f"Error in get_profile: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# DASHBOARD
# ============================================================

@inner_game_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get personalized dashboard"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        profile = get_profile(user_id)
        if not profile:
            return jsonify({"success": False, "error": "No profile found"}), 404

        # Get today's rep
        today_rep = get_today_rep(user_id)

        # Get week stats
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date()
        reps_url = f"{SUPABASE_URL}/rest/v1/inner_game_activities?user_id=eq.{user_id}&activity_type=eq.daily_rep&date_assigned=gte.{week_start}"
        reps_response = requests.get(reps_url, headers=sb_headers_service(), timeout=30)
        week_reps = reps_response.json() if reps_response.status_code < 400 else []
        reps_completed_this_week = len([r for r in week_reps if r.get('status') == 'completed'])

        # Get stability rule
        attachment = profile.get('attachment_style', 'secure')
        stability_rules = {
            'anxious': "When uncertain, don't chase. One message then stop (24h).",
            'avoidant': "No disappearing; give a time you'll respond.",
            'fearful_avoidant': "No hot/cold swings; keep contact steady.",
            'secure': "Lead clearly; keep your standards."
        }

        dashboard = {
            "profile": profile,
            "stability_rule": stability_rules.get(attachment, "Stay grounded; act with intention."),
            "today_rep": today_rep,
            "week_stats": {
                "reps_completed": reps_completed_this_week,
                "total_reps": len(week_reps),
                "streak_days": profile.get('current_streak_days', 0)
            }
        }

        return jsonify({"success": True, "dashboard": dashboard})

    except Exception as e:
        print(f"Error in get_dashboard: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# JOURNAL ENTRIES
# ============================================================

@inner_game_bp.route('/journal', methods=['GET'])
def get_journal_entries():
    """Get journal entries"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        limit = request.args.get('limit', 50)
        url = f"{SUPABASE_URL}/rest/v1/inner_game_entries?user_id=eq.{user_id}&entry_type=in.(journal_quick,journal_full)&order=date_time.desc&limit={limit}"
        response = requests.get(url, headers=sb_headers_service(), timeout=30)

        if response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to load journal"}), 500

        return jsonify({"success": True, "entries": response.json()})

    except Exception as e:
        print(f"Error in get_journal_entries: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@inner_game_bp.route('/journal', methods=['POST'])
def create_journal_entry():
    """Create journal entry"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        entry_data = {
            "user_id": user_id,
            "entry_type": data.get('entry_type', 'journal_full'),
            "situation": data.get('situation'),
            "intensity_before": data.get('intensity_before'),
            "intensity_after": data.get('intensity_after'),
            "fear_prediction": data.get('fear_prediction'),
            "story_in_my_head": data.get('story_in_my_head'),
            "body_signal": data.get('body_signal'),
            "urge": data.get('urge'),
            "best_action": data.get('best_action'),
            "action_taken": data.get('action_taken'),
            "outcome": data.get('outcome'),
            "lesson_learned": data.get('lesson_learned'),
            "tags": data.get('tags', [])
        }

        url = f"{SUPABASE_URL}/rest/v1/inner_game_entries"
        response = requests.post(url, json=entry_data, headers=sb_headers_service(), timeout=30)

        if response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to create journal entry"}), 500

        # Update stats
        update_profile_stats(user_id)

        return jsonify({
            "success": True,
            "entry": response.json()[0] if response.json() else None
        })

    except Exception as e:
        print(f"Error in create_journal_entry: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# DAILY REPS
# ============================================================

@inner_game_bp.route('/reps/today', methods=['GET'])
def get_today_rep_endpoint():
    """Get or create today's rep"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        rep = get_today_rep(user_id)

        if not rep:
            # Create today's rep
            rep = create_today_rep(user_id)

        return jsonify({"success": True, "rep": rep})

    except Exception as e:
        print(f"Error in get_today_rep: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def get_today_rep(user_id):
    """Get today's rep if exists"""
    today = datetime.now().date()
    url = f"{SUPABASE_URL}/rest/v1/inner_game_activities?user_id=eq.{user_id}&activity_type=eq.daily_rep&date_assigned=eq.{today}"
    response = requests.get(url, headers=sb_headers_service(), timeout=30)

    if response.status_code < 400:
        reps = response.json()
        return reps[0] if reps else None
    return None

def create_today_rep(user_id):
    """Create today's rep based on user progress"""
    # Get recent reps to determine difficulty
    recent_url = f"{SUPABASE_URL}/rest/v1/inner_game_activities?user_id=eq.{user_id}&activity_type=eq.daily_rep&order=date_assigned.desc&limit=7"
    response = requests.get(recent_url, headers=sb_headers_service(), timeout=30)

    difficulty = 1
    if response.status_code < 400:
        recent_reps = response.json()
        if recent_reps:
            completed = len([r for r in recent_reps if r.get('status') == 'completed'])
            completion_rate = (completed / len(recent_reps)) * 100

            discomforts = [r.get('discomfort_after') for r in recent_reps
                          if r.get('status') == 'completed' and r.get('discomfort_after')]
            avg_discomfort = sum(discomforts) / len(discomforts) if discomforts else 10

            if completion_rate < 40:
                difficulty = max(1, difficulty - 1)
            elif completion_rate > 70 and avg_discomfort <= 6:
                difficulty = min(5, difficulty + 1)

    # Select rep
    rep_library = {
        1: [('eye_contact', 'Make eye contact and smile at 3 strangers'),
            ('ask_question', 'Ask a stranger for the time or directions')],
        2: [('small_talk', 'Start a brief conversation with someone new'),
            ('compliment', 'Give one genuine compliment and exit gracefully')],
        3: [('invite', 'Invite someone to a low-stakes activity (coffee, walk)'),
            ('ask_question', 'Ask someone an interesting question')],
        4: [('number_ask', 'Ask for someone\'s contact info'),
            ('invite', 'Propose a specific date plan')],
        5: [('handle_no', 'Practice hearing "no" calmly: do one risky ask'),
            ('number_ask', 'Ask for number + handle any outcome gracefully')]
    }

    import random
    rep_type, description = random.choice(rep_library.get(difficulty, rep_library[1]))

    rep_data = {
        "user_id": user_id,
        "activity_type": "daily_rep",
        "title": description,
        "description": description,
        "rep_type": rep_type,
        "difficulty_level": difficulty,
        "date_assigned": str(datetime.now().date()),
        "status": "active"
    }

    url = f"{SUPABASE_URL}/rest/v1/inner_game_activities"
    response = requests.post(url, json=rep_data, headers=sb_headers_service(), timeout=30)

    if response.status_code < 400:
        return response.json()[0] if response.json() else None
    return None

@inner_game_bp.route('/reps/<rep_id>/complete', methods=['POST'])
def complete_rep(rep_id):
    """Mark rep as completed"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True) or {}

        update_data = {
            "status": "completed",
            "discomfort_before": data.get('discomfort_before'),
            "discomfort_after": data.get('discomfort_after'),
            "what_learned": data.get('what_learned'),
            "date_completed": datetime.now(timezone.utc).isoformat()
        }

        url = f"{SUPABASE_URL}/rest/v1/inner_game_activities?id=eq.{rep_id}&user_id=eq.{user_id}"
        response = requests.patch(url, json=update_data, headers=sb_headers_service(), timeout=30)

        if response.status_code >= 400:
            return jsonify({"success": False, "error": "Failed to complete rep"}), 500

        # Update stats
        update_profile_stats(user_id)

        return jsonify({"success": True})

    except Exception as e:
        print(f"Error in complete_rep: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# TRIGGERS & INSTANT COACH
# ============================================================

@inner_game_bp.route('/triggered', methods=['POST'])
def instant_coach():
    """Get instant coaching when triggered"""
    guard = require_login()
    if guard:
        return guard

    try:
        u = get_current_user()
        user_id = u.get("id")

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        trigger_type = data.get('trigger_type')
        intensity = data.get('intensity', 5)

        profile = get_profile(user_id)
        attachment = profile.get('attachment_style') if profile else 'secure'

        # Generate coaching
        coaching = generate_coaching(trigger_type, attachment, intensity)

        # Log trigger
        trigger_data = {
            "user_id": user_id,
            "entry_type": "trigger",
            "trigger_type": trigger_type,
            "intensity_before": intensity,
            "coping_strategy_used": "instant_coach",
            "response_behavior": "calm"
        }

        url = f"{SUPABASE_URL}/rest/v1/inner_game_entries"
        requests.post(url, json=trigger_data, headers=sb_headers_service(), timeout=30)

        return jsonify({"success": True, "coaching": coaching})

    except Exception as e:
        print(f"Error in instant_coach: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def generate_coaching(trigger_type, attachment_style, intensity):
    """Generate personalized coaching"""
    response = {
        "calm_action": "Take 5 deep breaths (4-7-8 pattern)",
        "replacement_thought": "I'm safe. I choose how I respond.",
        "behavioral_rule": "Pause before reacting",
        "script": None,
        "challenge": "Do one grounding activity"
    }

    if trigger_type == 'slow_reply' and attachment_style == 'anxious' and intensity >= 7:
        response = {
            "calm_action": "4-7-8 breathing x 4 rounds (in 4, hold 7, out 8)",
            "replacement_thought": "No data yet. I'm safe. I don't chase uncertainty.",
            "behavioral_rule": "One-message rule: wait 24 hours",
            "script": "All good—hit me when you're free.",
            "challenge": "Do one Level 1 rep today"
        }
    elif trigger_type == 'intimacy' and attachment_style == 'avoidant' and intensity >= 7:
        response = {
            "calm_action": "10 slow breaths + short walk",
            "replacement_thought": "Closeness isn't danger. I can stay present.",
            "behavioral_rule": "No disappearing; set a time to respond",
            "script": "Busy day—I'll reply tonight at 8pm.",
            "challenge": "Share 1 honest feeling in one sentence"
        }
    elif trigger_type == 'conflict' and attachment_style == 'fearful_avoidant':
        response = {
            "calm_action": "Box breathing x 5 minutes (in 4, hold 4, out 4, hold 4)",
            "replacement_thought": "I can handle this without hot/cold swings.",
            "behavioral_rule": "No big decisions when activated. Ask for time.",
            "script": "I need 30 minutes to cool down, then let's talk.",
            "challenge": "Name the activation: 'I got triggered by X'"
        }
    elif trigger_type == 'rejection':
        response = {
            "calm_action": "60-second body scan: notice where you feel it",
            "replacement_thought": "This is one person, one moment. Not a verdict on me.",
            "behavioral_rule": "Debrief: what did I do well? What's out of my control?",
            "script": "No worries—have a good one.",
            "challenge": "Do another rep today (same level or easier)"
        }

    return response

# ============================================================
# WEEKLY PLANS
# ============================================================

def create_weekly_plan(user_id):
    """Create weekly plan based on profile"""
    profile = get_profile(user_id)
    if not profile:
        return None

    # Determine focus
    focus_skill = "Confidence building"
    behavioral_rule = "Take one brave action daily"

    if profile.get('baseline_social_anxiety', 0) >= 7:
        focus_skill = "Exposure ladder + anxiety regulation"
        behavioral_rule = "One Level 1 rep daily; breathe before each"
    elif profile.get('rumination_score', 0) >= 7:
        focus_skill = "Thought records + nervous system regulation"
        behavioral_rule = "When spiraling: facts first, then thought record"
    elif profile.get('boundary_strength', 0) <= 4:
        focus_skill = "Boundary setting + standards practice"
        behavioral_rule = "Say no to one thing that doesn't serve you daily"

    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date()
    week_end = week_start + timedelta(days=6)

    plan_data = {
        "user_id": user_id,
        "activity_type": "weekly_plan",
        "title": f"Week of {week_start}",
        "focus_skill": focus_skill,
        "week_start_date": str(week_start),
        "week_end_date": str(week_end),
        "reps_target": 5,
        "behavioral_rule": behavioral_rule,
        "practice_script": get_script(profile.get('attachment_style')),
        "status": "active"
    }

    url = f"{SUPABASE_URL}/rest/v1/inner_game_activities"
    requests.post(url, json=plan_data, headers=sb_headers_service(), timeout=30)

def get_script(attachment_style):
    """Get practice script"""
    scripts = {
        'anxious': "All good—hit me when you're free.",
        'avoidant': "Busy day—I'll reply tonight.",
        'fearful_avoidant': "I like you, and I'm keeping it steady.",
        'secure': "Let's do X on Thursday at 7."
    }
    return scripts.get(attachment_style, "I'm good. Let me know when works for you.")
