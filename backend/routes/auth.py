"""Authentication routes: register, login, logout, forgot password."""
import re
import secrets
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, session, jsonify)

from models import (get_user_by_email, create_user, get_user_by_id,
                    set_reset_token, get_user_by_reset_token, clear_reset_token,
                    change_password, log_activity)
from utils.auth import login_user, logout_user, verify_password, current_user, is_valid_phone, normalize_phone

bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SPECIAL_CHARACTERS = set("!@#$%^&*?")


def is_valid_password_length(password: str) -> bool:
    return 8 <= len(password) <= 16


def is_strong_password(password: str) -> bool:
    if not is_valid_password_length(password):
        return False
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(char in SPECIAL_CHARACTERS for char in password)
    return has_upper and has_lower and has_digit and has_special


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "student")
        department = request.form.get("department", "").strip() or None
        phone = request.form.get("phone", "").strip() or None

        # Validate phone if provided
        if phone:
            if not is_valid_phone(phone):
                flash("Phone number must be exactly 10 digits and may include an optional country code like +91.", "danger")
                return redirect(url_for("auth.register"))
            phone = normalize_phone(phone)

        if role not in ("student", "teacher", "authority"):
            flash("Invalid role selected.", "danger")
            return redirect(url_for("auth.register"))
        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))
        if not is_strong_password(password):
            flash("Password must be 8 to 16 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            return redirect(url_for("auth.register"))
        if get_user_by_email(email):
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("auth.register"))

        uid = create_user(role, full_name, email, password, phone, department)
        log_activity(uid, full_name, "register", request.remote_addr, f"New {role} account")
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for("auth.login"))
        if not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.login"))
        if not is_valid_password_length(password):
            flash("Password must be 8 to 16 characters long.", "danger")
            return redirect(url_for("auth.login"))

        user = get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))
        if not user["is_active"]:
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        login_user(user)
        log_activity(user["id"], user["full_name"], "login", request.remote_addr)
        # Route to role dashboard
        role = session.get("role")
        return redirect(url_for(f"{role}.dashboard") if role in ("student", "teacher", "authority")
                         else url_for("main.index"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    u = current_user()
    if u:
        log_activity(u["id"], u["full_name"], "logout", request.remote_addr)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.forgot_password"))
        user = get_user_by_email(email)
        if user:
            token = secrets.token_urlsafe(32)
            expires = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            set_reset_token(user["id"], token, expires)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            return render_template("forgot_password.html", reset_url=reset_url)
        else:
            flash("If that email exists, a reset link has been generated.", "info")
        return redirect(url_for("auth.forgot_password"))
    return render_template("forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = get_user_by_reset_token(token)
    if not user:
        flash("Invalid or expired reset token.", "danger")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(request.url)
        if not is_strong_password(password):
            flash("Password must be 8 to 16 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            return redirect(request.url)
        change_password(user["id"], password)
        clear_reset_token(user["id"])
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token)