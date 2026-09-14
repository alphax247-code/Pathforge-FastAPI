"""
PathForge - Main Application Entry Point
A comprehensive personal development platform with gamification and AI coaching.
"""
from datetime import timedelta

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import FLASK_SECRET_KEY, MAX_CONTENT_LENGTH, IS_PROD
from auth import get_current_user, generate_form_csrf

# ============================================================
# Flask App Initialization
# ============================================================
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.permanent_session_lifetime = timedelta(days=7)

# Railway proxy support
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Cookie hardening
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_NAME"] = "pathforge_session"
app.config["SESSION_COOKIE_PATH"] = "/"
app.config["SESSION_COOKIE_DOMAIN"] = None  # Let Flask automatically determine the domain
app.config["SESSION_REFRESH_EACH_REQUEST"] = False  # Important: Don't refresh on every request

# Set Secure=False for local development to allow cookies over HTTP
if IS_PROD:
    app.config["SESSION_COOKIE_SECURE"] = True
else:
    app.config["SESSION_COOKIE_SECURE"] = False

# Ensure session is always permanent when set
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# ============================================================
# Template Context Processor & Helper Functions
# ============================================================
from flask import url_for as flask_url_for

# Route name mapping for backward compatibility with templates
ROUTE_MAPPING = {
    # Auth routes
    'signup': 'auth.signup',
    'login': 'auth.login',
    'logout': 'auth.logout',
    'login_google': 'auth.login_google',
    'login_facebook': 'auth.login_facebook',
    'auth_callback': 'auth.auth_callback',

    # Main routes
    'index': 'main.index',
    'dashboard': 'main.dashboard',
    'profile': 'main.profile',
    'onboarding': 'main.onboarding',
    'lessons': 'main.lessons',
    'my_videos': 'main.lessons',
    'videos': 'main.lessons',
    'stream_video': 'main.stream_video',
    'challenges': 'main.challenges',
    'inner_game': 'main.inner_game',
    'community': 'main.community',
    'practice': 'main.practice',
    'ai_menu': 'main.ai_menu',
    'text_practice': 'main.text_practice',
    'speech_practice': 'main.speech_practice',
    'daily_directive': 'main.daily_directive',
    'pricing': 'main.pricing',
    'checkout': 'main.checkout',

    # Game routes
    'psychology_games': 'game.psychology_games',
    'attachment_game': 'game.attachment_game',
    'cognitive_distortions_game': 'game.cognitive_distortions_game',
    'communication_styles_game': 'game.communication_styles_game',
    'love_languages_game': 'game.love_languages_game',

    # Admin routes
    'admin_dashboard': 'admin.dashboard',
    'admin_users': 'admin.users',
    'admin_videos': 'admin.videos',
    'admin_forum_posts': 'admin.forum_posts',
    'admin_forum_tags': 'admin.forum_tags',
    'admin_database': 'admin.database',

    # API routes
    'save_assessment': 'api.save_assessment',
    'get_progress': 'api.get_progress',
    'save_progress': 'api.save_progress',
}

def url_for_compat(endpoint, **values):
    """
    Backward-compatible url_for that maps old route names to new blueprint routes.
    """
    # Map old route names to new blueprint routes
    if endpoint in ROUTE_MAPPING:
        endpoint = ROUTE_MAPPING[endpoint]
    return flask_url_for(endpoint, **values)

@app.before_request
def before_request():
    """Ensure session is properly configured before each request."""
    from flask import session
    from datetime import timedelta

    # Make session permanent if it contains user data
    if "user" in session and not session.permanent:
        session.permanent = True

    # Adjust session lifetime based on remember_me flag
    if "user" in session:
        if session.get("remember_me"):
            # Extended session: 30 days
            app.permanent_session_lifetime = timedelta(days=30)
        else:
            # Default session: 7 days
            app.permanent_session_lifetime = timedelta(days=7)

@app.context_processor
def inject_user():
    return dict(
        user=get_current_user(),
        csrf_token=generate_form_csrf(),
        url_for=url_for_compat  # Override url_for in templates
    )

@app.after_request
def after_request(response):
    """Ensure session cookies are set properly on all responses."""
    from flask import session as flask_session

    # Force session to be saved on redirects (fixes double login issue)
    if response.status_code in (301, 302, 303, 307, 308):
        if 'user' in flask_session:
            flask_session.modified = True

    # Ensure cookies work properly with redirects
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    # For redirects, ensure Vary header is set correctly for session cookies
    if response.status_code in (301, 302, 303, 307, 308):
        response.headers['Vary'] = 'Cookie'

    return response

# ============================================================
# Register Blueprints
# ============================================================
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.game_routes import game_bp
from routes.admin_routes import admin_bp
from routes.api_routes import api_bp
from routes.inner_game_routes import inner_game_bp

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(game_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)
app.register_blueprint(inner_game_bp)

# ============================================================
# Initialize Game Questions Cache (for faster loading)
# ============================================================
from game_cache import game_cache
print("Initializing game questions cache...")
game_cache.load_all_questions()
print("Game cache ready!")

# ============================================================
# Error Handlers
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

# ============================================================
# Main Entry Point
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
