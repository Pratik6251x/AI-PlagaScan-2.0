"""Student dashboard."""
from flask import Blueprint, render_template
from models import (list_reports_by_user, list_documents_by_user,
                    list_history_by_user, analytics_counts)
from utils.auth import login_required, role_required, current_user
bp = Blueprint("student", __name__, url_prefix="/student")
@bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    u = current_user()
    reports = list_reports_by_user(u["id"])
    docs = list_documents_by_user(u["id"])
    history = list_history_by_user(u["id"], limit=5)
    counts = analytics_counts()
    completed_reports = [r for r in reports if r.get("scan_status") == "completed"]
    avg_sim = 0
    if completed_reports:
        avg_sim = round(sum(r["similarity_percent"] for r in completed_reports) / len(completed_reports), 2)
    return render_template("dashboards/student.html", reports=reports, docs=docs,
             history=history, counts=counts, avg_sim=avg_sim)