"""High authority dashboard: manage users, analytics, activity logs."""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, jsonify)

from models import (analytics_counts, list_all_users, list_activity_logs,
                    list_users_by_role, set_user_active, delete_user as remove_user,
                    analytics_daily_uploads, analytics_similarity_trends,
                    analytics_category_distribution, analytics_department_stats,
                    analytics_monthly_stats, list_all_reports, list_all_documents,
                    log_activity, delete_activity_log as delete_log_entry,
                    clear_activity_logs as clear_all_activity_logs)
from utils.auth import login_required, role_required, current_user

bp = Blueprint("authority", __name__, url_prefix="/authority")

@bp.route("/dashboard")
@login_required
@role_required("authority")
def dashboard():
    counts = analytics_counts()
    daily = analytics_daily_uploads()
    trends = analytics_similarity_trends()
    categories = analytics_category_distribution()
    departments = analytics_department_stats()
    monthly = analytics_monthly_stats()
    return render_template("dashboards/authority.html", counts=counts, daily=daily,
                           trends=trends, categories=categories,
                           departments=departments, monthly=monthly)

@bp.route("/users")
@login_required
@role_required("authority")
def users():
    users = list_all_users()
    return render_template("authority/users.html", users=users)

@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required("authority")
def toggle_user(user_id):
    u = current_user()
    if user_id == u["id"]:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("authority.users"))
    from models import get_user_by_id
    target = get_user_by_id(user_id)
    if not target:
        abort(404)
    new_state = not bool(target["is_active"])
    set_user_active(user_id, new_state)
    log_activity(u["id"], u["full_name"], "toggle_user", request.remote_addr,
                 f"{target['full_name']} -> {'active' if new_state else 'inactive'}")
    flash(f"User {'activated' if new_state else 'deactivated'}.", "info")
    return redirect(url_for("authority.users"))

@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("authority")
def delete_user(user_id):
    u = current_user()
    if user_id == u["id"]:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("authority.users"))
    from models import get_user_by_id
    target = get_user_by_id(user_id)
    if not target:
        abort(404)
    name = target["full_name"]
    remove_user(user_id)
    log_activity(u["id"], u["full_name"], "delete_user", request.remote_addr, name)
    flash("User deleted.", "info")
    return redirect(url_for("authority.users"))

@bp.route("/activity-logs")
@login_required
@role_required("authority")
def activity_logs():
    logs = list_activity_logs()
    return render_template("authority/activity_logs.html", logs=logs)

@bp.route("/activity-logs/<int:log_id>/delete", methods=["POST"])
@login_required
@role_required("authority")
def delete_activity_log_route(log_id):
    delete_log_entry(log_id)
    flash("Activity log deleted.", "info")
    return redirect(url_for("authority.activity_logs"))

@bp.route("/activity-logs/clear", methods=["POST"])
@login_required
@role_required("authority")
def clear_activity_logs_route():
    clear_all_activity_logs()
    flash("All activity logs cleared.", "info")
    return redirect(url_for("authority.activity_logs"))

@bp.route("/reports")
@login_required
@role_required("authority")
def reports():
    reports = list_all_reports()
    return render_template("authority/reports.html", reports=reports)
@bp.route("/database")
@login_required
@role_required("authority")
def database():
    counts = analytics_counts()
    return render_template("authority/database.html", counts=counts)