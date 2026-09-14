"""
Game routes for PathForge application.
Handles psychology game pages.
"""
from flask import Blueprint, render_template

from auth import require_login, get_current_user, is_user_admin
from database import ensure_profile_exists

game_bp = Blueprint('game', __name__)

@game_bp.route("/game")
@game_bp.route("/psychology-games")
def psychology_games():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("psychology_games.html", user=user, progress=profile, is_admin=is_user_admin())

@game_bp.route("/attachment-game")
def attachment_game():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("attachment_game.html", user=user, progress=profile, is_admin=is_user_admin())

@game_bp.route("/cognitive-distortions-game")
def cognitive_distortions_game():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("cognitive_distortions_game.html", user=user, progress=profile, is_admin=is_user_admin())

@game_bp.route("/communication-styles-game")
def communication_styles_game():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("communication_styles_game.html", user=user, progress=profile, is_admin=is_user_admin())

@game_bp.route("/love-languages-game")
def love_languages_game():
    guard = require_login()
    if guard:
        return guard
    user = get_current_user()
    profile = ensure_profile_exists() or {}
    return render_template("love_languages_game.html", user=user, progress=profile, is_admin=is_user_admin())
