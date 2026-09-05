"""Shared pages: upload, report view, history, notifications, settings, profile."""
import json
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, jsonify, session)
from models import (get_report, get_report_with_doc, get_matched_sources,
                    list_reports_by_user, list_history_by_user, list_notifications,
                    unread_notification_count, mark_notification_read, mark_all_notifications_read,
                    delete_notification, delete_all_notifications, get_settings, update_settings, get_user_by_id, update_user_profile,
                    change_password, add_history, list_documents_by_user, get_document,
                    delete_document, delete_report, delete_all_reports, delete_history_entry, delete_all_history,
                    create_notification, log_activity)
from utils.auth import login_required, current_user, verify_password, is_valid_phone, normalize_phone

bp = Blueprint("pages", __name__)
SPECIAL_CHARACTERS = set("!@#$%^&*?")

def _is_strong_password(password: str) -> bool:
    if not 8 <= len(password) <= 16:
        return False
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(char in SPECIAL_CHARACTERS for char in password)
    return has_upper and has_lower and has_digit and has_special

@bp.route("/upload")
@login_required
def upload_page():
    return render_template("upload.html")

@bp.route("/text-checker")
@login_required
def text_checker():
    return render_template("text_checker.html")

@bp.route("/report/<int:report_id>")
@login_required
def view_report(report_id):
    u = current_user()
    report = get_report_with_doc(report_id)
    if not report:
        abort(404)
    if report["user_id"] != u["id"] and u["role"] not in ("teacher", "authority"):
        abort(403)
    matched_paragraphs = json.loads(report.get("matched_paragraphs") or "[]")
    sources = get_matched_sources(report_id)
    add_history(u["id"], "view_report", f"Report #{report_id}", report_id=report_id)
    return render_template("report.html", report=report,
                           matched_paragraphs=matched_paragraphs, sources=sources)
@bp.route("/history")
@login_required
def history():
    u = current_user()
    items = list_history_by_user(u["id"])
    return render_template("history.html", items=items)

@bp.route("/history/<int:history_id>/delete", methods=["POST"])
@login_required
def delete_history_route(history_id):
    u = current_user()
    delete_history_entry(history_id, u["id"])
    flash("History entry deleted.", "info")
    return redirect(url_for("pages.history"))

@bp.route("/history/delete-all", methods=["POST"])
@login_required
def delete_all_history_route():
    u = current_user()
    delete_all_history(u["id"])
    flash("All history deleted.", "info")
    return redirect(url_for("pages.history"))

@bp.route("/reports")
@login_required
def reports_list():
    u = current_user()
    reports = list_reports_by_user(u["id"])
    return render_template("reports.html", reports=reports)

@bp.route("/report/<int:report_id>/delete", methods=["POST"])
@login_required
def delete_report_route(report_id):
    u = current_user()
    report = get_report(report_id)
    if not report:
        abort(404)
    if report["user_id"] != u["id"] and u["role"] != "authority":
        abort(403)
    delete_report(report_id)
    flash("Report deleted.", "info")
    return redirect(url_for("pages.reports_list"))

@bp.route("/reports/delete-all", methods=["POST"])
@login_required
def delete_all_reports_route():
    u = current_user()
    delete_all_reports(u["id"])
    flash("All reports deleted.", "info")
    return redirect(url_for("pages.reports_list"))

@bp.route("/documents")
@login_required
def documents_list():
    u = current_user()
    docs = list_documents_by_user(u["id"])
    return render_template("documents.html", docs=docs)
@bp.route("/document/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_doc(doc_id):
    u = current_user()
    doc = get_document(doc_id)
    if not doc:
        abort(404)
    if doc["user_id"] != u["id"] and u["role"] != "authority":
        abort(403)
    try:
        if doc["file_path"] and __import__("os").path.exists(doc["file_path"]):
            __import__("os").remove(doc["file_path"])
    except Exception:
        pass
    delete_document(doc_id)
    flash("Document deleted.", "info")
    return redirect(url_for("pages.documents_list"))
@bp.route("/notifications")
@login_required
def notifications():
    u = current_user()
    items = list_notifications(u["id"])
    return render_template("notifications.html", items=items)
@bp.route("/notifications/<int:nid>/read", methods=["POST"])
@login_required
def read_notification(nid):
    u = current_user()
    mark_notification_read(nid, u["id"])
    return jsonify({"ok": True})
@bp.route("/notifications/<int:nid>/delete", methods=["POST"])
@login_required
def delete_notif(nid):
    u = current_user()
    delete_notification(nid, u["id"])
    return jsonify({"ok": True})
@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    u = current_user()
    mark_all_notifications_read(u["id"])
    flash("All notifications marked as read.", "info")
    return redirect(url_for("pages.notifications"))
@bp.route("/notifications/delete-all", methods=["POST"])
@login_required
def delete_all_notifications_route():
    u = current_user()
    delete_all_notifications(u["id"])
    flash("All notifications deleted.", "info")
    return redirect(url_for("pages.notifications"))
@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    u = current_user()
    if request.method == "POST":
        theme = request.form.get("theme", "dark")
        email_alerts = 1 if request.form.get("email_alerts") else 0
        auto_report = 1 if request.form.get("auto_report") else 0
        language = request.form.get("language", "en")
        update_settings(u["id"], theme, email_alerts, auto_report, language)
        flash("Settings updated.", "success")
        return redirect(url_for("pages.settings"))
    s = get_settings(u["id"])
    return render_template("settings.html", settings=s)
@bp.route("/profile", methods=["GET", "POST"])

@login_required
def profile():
    u = current_user()
    user = get_user_by_id(u["id"])
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip() or None
            department = request.form.get("department", "").strip() or None
            # Validate phone if provided
            if phone and not is_valid_phone(phone):
                flash("Phone number must be exactly 10 digits and may include an optional country code like +91.", "danger")
                return redirect(url_for("pages.profile"))
            if phone:
                phone = normalize_phone(phone)
            if not full_name:
                flash("Name is required.", "danger")
                return redirect(url_for("pages.profile"))
            update_user_profile(u["id"], full_name, phone, department)
            session["full_name"] = full_name
            flash("Profile updated.", "success")
        elif action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not verify_password(current_pw, user["password_hash"]):
                flash("Current password is incorrect.", "danger")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "danger")
            elif not _is_strong_password(new_pw):
                flash("Password must be 8 to 16 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            else:
                change_password(u["id"], new_pw)
                flash("Password changed.", "success")
        return redirect(url_for("pages.profile"))
    return render_template("profile.html", user=user)
# Context processor for unread notification count
def inject_unread_count():
    if "user_id" in session:
        return {"unread_count": unread_notification_count(session["user_id"])}
    return {"unread_count": 0}