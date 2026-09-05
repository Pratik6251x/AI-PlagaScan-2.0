"""Teacher dashboard: view students, reports, analytics, search."""
from flask import Blueprint, render_template, request
from models import (list_users_by_role, list_all_reports, search_reports,
                    analytics_counts, list_all_documents)
from utils.auth import login_required, role_required
bp = Blueprint("teacher", __name__, url_prefix="/teacher")
@bp.route("/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    counts = analytics_counts()
    reports = list_all_reports()[:10]
    students = list_users_by_role("student")
    return render_template("dashboards/teacher.html", counts=counts,
                           reports=reports, students=students)
@bp.route("/students")
@login_required
@role_required("teacher")
def students():
    students = list_users_by_role("student")
    return render_template("teacher/students.html", students=students)
@bp.route("/reports")
@login_required
@role_required("teacher")
def reports():
    q = request.args.get("q", "").strip()
    reports = search_reports(q) if q else list_all_reports()
    return render_template("teacher/reports.html", reports=reports, q=q)