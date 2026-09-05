"""Authentication helpers: password hashing, session, role checks."""
from functools import wraps
from flask import session, redirect, url_for, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import re

from db import query_one


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def is_valid_phone(phone: str) -> bool:
    """Validate phone numbers.

    Accepts either a 10-digit number (e.g. 9876543210) or an optional leading
    country code prefixed with + (e.g. +91) followed immediately by a 10-digit
    local number. Spaces or single hyphen between country code and number are
    allowed when submitting, but stored form is normalized.
    """
    if not phone:
        return True
    # Strip common separators
    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not digits.isdigit():
            return False
        # must end with a 10-digit local number, and country code 1-3 digits
        if len(digits) <= 10:
            return False
        local = digits[-10:]
        country = digits[:-10]
        return local.isdigit() and len(local) == 10 and country.isdigit() and 1 <= len(country) <= 3
    # no plus: must be exactly 10 digits
    return cleaned.isdigit() and len(cleaned) == 10


def normalize_phone(phone: str) -> str:
    """Normalize phone to either 10 digits or +<country><10digits> with no separators.

    Returns the cleaned string (e.g. '1234567890' or '+911234567890'). If input
    is falsy returns an empty string.
    """
    if not phone:
        return ""
    cleaned = phone.replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        return f"+{digits}"
    return cleaned


def login_user(user_row: dict):
    """Persist the user in the session."""
    session.permanent = True
    session["user_id"] = user_row["id"]
    session["role_id"] = user_row["role_id"]
    session["full_name"] = user_row["full_name"]
    session["email"] = user_row["email"]
    # Look up role name
    role = query_one("SELECT name FROM roles WHERE id = %s", [user_row["role_id"]])
    session["role"] = role["name"] if role else "student"


def logout_user():
    session.clear()


def current_user():
    if "user_id" not in session:
        return None
    # Verify user still exists in database
    from models import get_user_by_id
    user = get_user_by_id(session.get("user_id"))
    if not user:
        # User was deleted; clear session
        session.clear()
        return None
    return {
        "id": session.get("user_id"),
        "role_id": session.get("role_id"),
        "full_name": session.get("full_name"),
        "email": session.get("email"),
        "role": session.get("role"),
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator
