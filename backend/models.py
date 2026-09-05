"""Data-access layer: one module per logical entity.

Each function returns plain dict rows (already converted by db.query).
Keeps SQL out of the route handlers.
"""
from db import query, query_one, execute, execute_update
from config import DB_BACKEND
from utils.auth import hash_password


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def get_role_id(name: str):
    row = query_one("SELECT id FROM roles WHERE name = %s", [name])
    return row["id"] if row else None


def get_all_roles():
    return query("SELECT * FROM roles ORDER BY id")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user_by_email(email: str):
    return query_one("SELECT * FROM users WHERE email = %s", [email])


def get_user_by_id(user_id: int):
    return query_one("SELECT * FROM users WHERE id = %s", [user_id])


def create_user(role_name: str, full_name: str, email: str, password: str,
                phone=None, department=None):
    role_id = get_role_id(role_name)
    if role_id is None:
        raise ValueError(f"Unknown role: {role_name}")
    uid = execute(
        "INSERT INTO users (role_id, full_name, email, password_hash, phone, department, is_active) "
        "VALUES (%s, %s, %s, %s, %s, %s, 1)",
        [role_id, full_name, email, hash_password(password), phone, department],
    )
    # Role-specific profile row
    if role_name == "student":
        code = f"STU-{uid:05d}"
        execute("INSERT INTO students (user_id, student_code) VALUES (%s, %s)", [uid, code])
    elif role_name == "teacher":
        code = f"TCH-{uid:05d}"
        execute("INSERT INTO teachers (user_id, employee_code) VALUES (%s, %s)", [uid, code])
    elif role_name == "authority":
        code = f"AUTH-{uid:05d}"
        execute("INSERT INTO authorities (user_id, admin_code) VALUES (%s, %s)", [uid, code])
    # Default settings row
    execute("INSERT INTO settings (user_id) VALUES (%s)", [uid])
    return uid


def update_user_profile(user_id: int, full_name: str, phone=None, department=None):
    execute(
        "UPDATE users SET full_name = %s, phone = %s, department = %s WHERE id = %s",
        [full_name, phone, department, user_id],
    )


def change_password(user_id: int, new_password: str):
    execute("UPDATE users SET password_hash = %s WHERE id = %s",
            [hash_password(new_password), user_id])


def set_reset_token(user_id: int, token: str, expires):
    execute("UPDATE users SET reset_token = %s, reset_expires = %s WHERE id = %s",
            [token, expires, user_id])


def get_user_by_reset_token(token: str):
    return query_one(
        "SELECT * FROM users WHERE reset_token = %s "
        "AND reset_expires IS NOT NULL AND reset_expires > CURRENT_TIMESTAMP",
        [token],
    )


def clear_reset_token(user_id: int):
    execute("UPDATE users SET reset_token = NULL, reset_expires = NULL WHERE id = %s", [user_id])


def list_users_by_role(role_name: str):
    return query(
        "SELECT u.id, u.full_name, u.email, u.department, u.is_active, u.created_at "
        "FROM users u JOIN roles r ON u.role_id = r.id WHERE r.name = %s ORDER BY u.id DESC",
        [role_name],
    )


def list_all_users():
    return query(
        "SELECT u.id, u.full_name, u.email, u.department, u.is_active, u.created_at, r.name AS role "
        "FROM users u JOIN roles r ON u.role_id = r.id ORDER BY u.id DESC"
    )


def set_user_active(user_id: int, active: bool):
    execute("UPDATE users SET is_active = %s WHERE id = %s", [1 if active else 0, user_id])


def delete_user(user_id: int):
    execute("DELETE FROM users WHERE id = %s", [user_id])


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def create_document(user_id, original_name, stored_name, file_path, file_type, file_size, title=None,
                    extracted_text=None, text_hash=None, status="uploaded"):
    return execute(
        "INSERT INTO documents (user_id, original_name, stored_name, file_path, file_type, file_size, "
        "title, extracted_text, text_hash, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        [user_id, original_name, stored_name, file_path, file_type, file_size, title,
         extracted_text, text_hash, status],
    )


def get_document(doc_id: int):
    return query_one("SELECT * FROM documents WHERE id = %s", [doc_id])


def list_documents_by_user(user_id: int):
    return query("SELECT * FROM documents WHERE user_id = %s ORDER BY id DESC", [user_id])


def list_all_documents():
    return query("SELECT d.*, u.full_name AS owner_name FROM documents d "
                 "JOIN users u ON d.user_id = u.id ORDER BY d.id DESC")


def list_documents_excluding(user_id: int, exclude_doc_id: int = None):
    """All documents NOT owned by user_id (the comparison corpus)."""
    if exclude_doc_id:
        return query(
            "SELECT * FROM documents WHERE user_id != %s AND id != %s "
            "AND extracted_text IS NOT NULL AND length(extracted_text) > 0 "
            "ORDER BY id DESC",
            [user_id, exclude_doc_id],
        )
    return query(
        "SELECT * FROM documents WHERE user_id != %s "
        "AND extracted_text IS NOT NULL AND length(extracted_text) > 0 "
        "ORDER BY id DESC",
        [user_id],
    )


def update_document_text(doc_id: int, extracted_text: str, text_hash: str, status="processed"):
    execute("UPDATE documents SET extracted_text = %s, text_hash = %s, status = %s WHERE id = %s",
            [extracted_text, text_hash, status, doc_id])


def delete_document(doc_id: int):
    execute("DELETE FROM documents WHERE id = %s", [doc_id])


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def create_report(document_id, user_id, analysis: dict):
    import json
    rid = execute(
        "INSERT INTO reports (document_id, user_id, similarity_percent, original_percent, "
        "ai_probability, human_probability, confidence_score, category, matched_paragraphs, summary, scan_status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'processing')",
        [document_id, user_id, analysis["similarity_percent"], analysis["original_percent"],
         analysis["ai_probability"], analysis["human_probability"], analysis["confidence_score"],
         analysis["category"], json.dumps(analysis["matched_paragraphs"]), analysis["summary"]],
    )
    # Persist matched sources
    for m in analysis.get("matched_sources", []):
        execute(
            "INSERT INTO matched_sources (report_id, source_document_id, source_text, matched_text, "
            "similarity_percent, source_reference, citation_suggestion) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [rid, m.get("source_document_id"), m.get("source_text", ""),
             m.get("matched_text", ""), m.get("similarity_percent", 0),
             m.get("source_reference", ""), m.get("citation_suggestion", "")],
        )
    return rid


def update_report_status(report_id, status, scan_id=None, error_message=None):
    return execute_update(
        "UPDATE reports SET scan_status = %s, copyleaks_scan_id = COALESCE(%s, copyleaks_scan_id), error_message = %s "
        "WHERE id = %s AND scan_status <> 'completed'",
        [status, scan_id, error_message, report_id],
    )


def update_report_from_copyleaks(report_id, analysis):
    import json
    updated = execute_update(
        "UPDATE reports SET similarity_percent=%s, original_percent=%s, "
        "ai_probability=%s, human_probability=%s, confidence_score=%s, category=%s, "
        "matched_paragraphs=%s, summary=%s, scan_status='completed', error_message=NULL "
        "WHERE id=%s AND scan_status <> 'completed'",
        [analysis["similarity_percent"], analysis["original_percent"],
         analysis["ai_probability"], analysis["human_probability"],
         analysis["confidence_score"], analysis["category"],
         json.dumps(analysis.get("matched_paragraphs", [])), analysis["summary"], report_id],
    )
    if updated == 0:
        return False
    # Replace webhook matches only when the completed payload contains a source list.
    if analysis.get("matched_sources"):
        execute("DELETE FROM matched_sources WHERE report_id = %s", [report_id])
    for m in analysis.get("matched_sources", []):
        execute(
            "INSERT INTO matched_sources (report_id, source_document_id, source_text, matched_text, "
            "similarity_percent, source_reference, citation_suggestion) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [report_id, None, m.get("source_text", ""), m.get("matched_text", ""),
             m.get("similarity_percent", 0), m.get("source_reference", ""), m.get("citation_suggestion", "")],
        )
    return True


def add_external_match(report_id, match):
    source_reference = match.get("url", "")
    if source_reference and query_one(
        "SELECT id FROM matched_sources WHERE report_id = %s AND source_reference = %s LIMIT 1",
        [report_id, source_reference],
    ):
        return False
    execute(
        "INSERT INTO matched_sources (report_id, source_document_id, source_text, matched_text, "
        "similarity_percent, source_reference, citation_suggestion) VALUES (%s,NULL,%s,%s,%s,%s,%s)",
        [report_id, match.get("source_text", ""), match.get("matched_text", ""), match.get("score", 0), source_reference,
         f"Online source: {match.get('title') or 'source'}"],
    )
    return True

def get_report(report_id: int):
    return query_one("SELECT * FROM reports WHERE id = %s", [report_id])


def delete_report(report_id: int):
    execute("DELETE FROM reports WHERE id = %s", [report_id])


def delete_all_reports(user_id: int):
    execute("DELETE FROM reports WHERE user_id = %s", [user_id])


def get_report_with_doc(report_id: int):
    return query_one(
        "SELECT r.*, d.original_name, d.title AS doc_title, d.file_type, d.created_at AS upload_date "
        "FROM reports r JOIN documents d ON r.document_id = d.id WHERE r.id = %s",
        [report_id],
    )


def list_reports_by_user(user_id: int):
    return query(
        "SELECT r.*, d.original_name, d.title AS doc_title, d.file_type "
        "FROM reports r JOIN documents d ON r.document_id = d.id "
        "WHERE r.user_id = %s ORDER BY r.id DESC",
        [user_id],
    )


def list_all_reports():
    return query(
        "SELECT r.*, d.original_name, d.title AS doc_title, u.full_name AS owner_name "
        "FROM reports r JOIN documents d ON r.document_id = d.id "
        "JOIN users u ON r.user_id = u.id ORDER BY r.id DESC"
    )


def get_matched_sources(report_id: int):
    return query("SELECT * FROM matched_sources WHERE report_id = %s", [report_id])


def search_reports(query_str: str):
    like = f"%{query_str}%"
    return query(
        "SELECT r.*, d.original_name, u.full_name AS owner_name "
        "FROM reports r JOIN documents d ON r.document_id = d.id "
        "JOIN users u ON r.user_id = u.id "
        "WHERE d.original_name LIKE %s OR u.full_name LIKE %s OR r.category LIKE %s "
        "ORDER BY r.id DESC",
        [like, like, like],
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def add_history(user_id: int, action: str, detail: str = None, document_id: int = None, report_id: int = None):
    try:
        execute(
            "INSERT INTO history (user_id, document_id, report_id, action, detail) "
            "VALUES (%s, %s, %s, %s, %s)",
            [user_id, document_id, report_id, action, detail],
        )
    except Exception as e:
        # Log the error but don't fail the request if history insertion fails
        print(f"Warning: Failed to add history entry: {str(e)}")


def list_history_by_user(user_id: int, limit=50):
    return query(
        "SELECT h.*, d.original_name FROM history h "
        "LEFT JOIN documents d ON h.document_id = d.id "
        "WHERE h.user_id = %s ORDER BY h.id DESC LIMIT %s",
        [user_id, limit],
    )


def delete_history_entry(history_id: int, user_id: int):
    execute("DELETE FROM history WHERE id = %s AND user_id = %s", [history_id, user_id])


def delete_all_history(user_id: int):
    execute("DELETE FROM history WHERE user_id = %s", [user_id])


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------

def log_activity(user_id: int, actor_name: str, action: str, ip: str = None, detail: str = None):
    execute(
        "INSERT INTO activity_logs (user_id, actor_name, action, ip_address, detail) "
        "VALUES (%s, %s, %s, %s, %s)",
        [user_id, actor_name, action, ip, detail],
    )


def list_activity_logs(limit=200):
    return query(
        "SELECT a.*, u.full_name AS user_name FROM activity_logs a "
        "LEFT JOIN users u ON a.user_id = u.id "
        "ORDER BY a.id DESC LIMIT %s",
        [limit],
    )


def delete_activity_log(log_id: int):
    execute("DELETE FROM activity_logs WHERE id = %s", [log_id])


def clear_activity_logs():
    execute("DELETE FROM activity_logs")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(user_id: int, title: str, message: str, type="info"):
    execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (%s, %s, %s, %s)",
        [user_id, title, message, type],
    )


def list_notifications(user_id: int):
    return query("SELECT * FROM notifications WHERE user_id = %s ORDER BY id DESC", [user_id])


def unread_notification_count(user_id: int):
    row = query_one("SELECT COUNT(*) AS c FROM notifications WHERE user_id = %s AND is_read = 0", [user_id])
    return row["c"] if row else 0


def mark_notification_read(notif_id: int, user_id: int):
    execute("UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s", [notif_id, user_id])


def mark_all_notifications_read(user_id: int):
    execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", [user_id])


def delete_notification(notif_id: int, user_id: int):
    execute("DELETE FROM notifications WHERE id = %s AND user_id = %s", [notif_id, user_id])


def delete_all_notifications(user_id: int):
    execute("DELETE FROM notifications WHERE user_id = %s", [user_id])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_settings(user_id: int):
    s = query_one("SELECT * FROM settings WHERE user_id = %s", [user_id])
    if not s:
        execute("INSERT INTO settings (user_id) VALUES (%s)", [user_id])
        s = query_one("SELECT * FROM settings WHERE user_id = %s", [user_id])
    return s


def update_settings(user_id: int, theme="dark", email_alerts=1, auto_report=0, language="en"):
    execute(
        "UPDATE settings SET theme = %s, email_alerts = %s, auto_report = %s, language = %s "
        "WHERE user_id = %s",
        [theme, email_alerts, auto_report, language, user_id],
    )


# ---------------------------------------------------------------------------
# Feedback & Reviews
# ---------------------------------------------------------------------------

def create_feedback(user_id: int, rating: int, message: str = None):
    execute(
        "INSERT INTO feedback (user_id, rating, message) VALUES (%s, %s, %s)",
        [user_id, rating, message],
    )


def list_feedback_all():
    return query("SELECT f.*, u.full_name, u.email FROM feedback f LEFT JOIN users u ON f.user_id = u.id ORDER BY f.id DESC")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def analytics_daily_uploads(days=30):
    return query(
        "SELECT DATE(created_at) AS day, COUNT(*) AS count "
        "FROM documents WHERE created_at >= DATE('now', ?) "
        "GROUP BY DATE(created_at) ORDER BY day",
        [f"-{days} days"],
    )


def analytics_similarity_trends(days=30):
    return query(
        "SELECT DATE(created_at) AS day, ROUND(AVG(similarity_percent),2) AS avg_sim "
        "FROM reports WHERE scan_status = 'completed' AND created_at >= DATE('now', ?) "
        "GROUP BY DATE(created_at) ORDER BY day",
        [f"-{days} days"],
    )


def analytics_counts():
    students = query_one("SELECT COUNT(*) AS c FROM users u JOIN roles r ON u.role_id=r.id WHERE r.name='student'")["c"]
    teachers = query_one("SELECT COUNT(*) AS c FROM users u JOIN roles r ON u.role_id=r.id WHERE r.name='teacher'")["c"]
    docs = query_one("SELECT COUNT(*) AS c FROM documents")["c"]
    reports = query_one("SELECT COUNT(*) AS c FROM reports")["c"]
    return {"students": students, "teachers": teachers, "documents": docs, "reports": reports}


def analytics_category_distribution():
    return query(
        "SELECT category, COUNT(*) AS count FROM reports "
        "WHERE scan_status = 'completed' GROUP BY category"
    )


def analytics_department_stats():
    return query(
        "SELECT u.department, COUNT(d.id) AS docs, COUNT(r.id) AS reports "
        "FROM users u LEFT JOIN documents d ON d.user_id = u.id "
        "LEFT JOIN reports r ON r.user_id = u.id "
        "WHERE u.department IS NOT NULL AND u.department != '' "
        "GROUP BY u.department ORDER BY docs DESC"
    )


def analytics_monthly_stats():
    if DB_BACKEND == "mysql":
        return query(
            "SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, "
            "COUNT(*) AS uploads, ROUND(AVG(similarity_percent),2) AS avg_sim "
            "FROM reports WHERE scan_status = 'completed' "
            "GROUP BY month ORDER BY month DESC LIMIT 12"
        )
    return query(
        "SELECT strftime('%Y-%m', created_at) AS month, "
        "COUNT(*) AS uploads, ROUND(AVG(similarity_percent),2) AS avg_sim "
        "FROM reports WHERE scan_status = 'completed' "
        "GROUP BY month ORDER BY month DESC LIMIT 12"
    )
