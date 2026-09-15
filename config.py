"""
Configuration module for PathForge application.
Handles environment variables and application settings.
"""
import os
import sys
from dotenv import load_dotenv

# Load .env for local development
load_dotenv()

# Flask configuration
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Storage configuration
VIDEOS_BUCKET = os.getenv("VIDEOS_BUCKET", "videos")
SUPABASE_REDIRECT_URL = os.getenv("SUPABASE_REDIRECT_URL", "").strip()

# Admin configuration
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin-password-change-this")

# Application settings
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
IS_PROD = bool(os.getenv("PORT")) and os.getenv("FLASK_ENV", "").lower() != "development"

# Video playlists/categories (merged from playlists table)
PLAYLISTS = [
    {"id": 1, "name": "Lessons", "description": "Educational video lessons"},
    {"id": 2, "name": "Challenges", "description": "Challenge and exercise videos"},
    {"id": 3, "name": "Inner Game", "description": "Personal development and mindset videos"},
    {"id": 4, "name": "Practice", "description": "Practice and demonstration videos"},
    {"id": 5, "name": "Community", "description": "Community-contributed content"}
]

# Allow the web process to start before Supabase is configured. Routes that rely
# on authentication, database data, or storage will remain unavailable until all
# three values are supplied in the deployment environment.
SUPABASE_CONFIGURED = bool(
    SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY
)

if not SUPABASE_CONFIGURED:
    print(
        "WARNING: Supabase is not configured. The application will start, but "
        "authentication, database, and storage features are disabled until "
        "SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY are set.",
        file=sys.stderr,
    )
