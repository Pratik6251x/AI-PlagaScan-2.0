"""API routes: file upload + AI analysis, report export, share."""
import json
import logging
import os
import threading
from flask import (Blueprint, request, jsonify, send_file, abort, url_for,
                   render_template, redirect, flash, session)
from models import (create_document, get_document, update_document_text,
                    create_report, get_report, update_report_status,
                    update_report_from_copyleaks, add_external_match,
                    get_report_with_doc, get_matched_sources, list_reports_by_user,
                    add_history, get_user_by_id, log_activity, create_notification)
from utils.auth import login_required, current_user
from utils.files import save_upload, extract_text, extraction_failed, text_hash
from utils.reports import generate_pdf, generate_docx, generate_excel
from ai.engine import category_for
from services.copyleaks import submit_file as copyleaks_submit_file, submit_text as copyleaks_submit_text, parse_completed, parse_new_result
from config import COPYLEAKS_WEBHOOK_SECRET
bp = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)
@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    """Upload a file, extract text, run analysis, store report."""
    u = current_user()
    file = request.files.get("file")
    title = request.form.get("title", "").strip() or None
    if not file:
        return jsonify({"error": "No file provided"}), 400
    try:
        stored_path, stored_name, ext, size = save_upload(file, u["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

# Extract text
    text = extract_text(stored_path, ext)
    is_image = ext in {"png", "jpg", "jpeg"}
    extraction_error = extraction_failed(text)
    stored_text = None if extraction_error else text
    th = text_hash(stored_text) if stored_text else None
    doc_id = create_document(u["id"], file.filename, stored_name, stored_path,
                             ext, size, title, stored_text, th,
                             status="processed" if stored_text else "uploaded")
    add_history(u["id"], "upload", f"Uploaded {file.filename}", document_id=doc_id)
    log_activity(u["id"], u["full_name"], "upload", request.remote_addr, file.filename)

    if not stored_text or len(stored_text.strip()) < 20:
        create_notification(u["id"], "Upload processed",
                            f"Could not extract enough text from {file.filename}.", "warning")
        if is_image:
            message = (
                "Could not read enough text from this image. Install Tesseract OCR "
                "and ensure it is available on PATH, then try again."
            )
        else:
            message = "Could not extract enough text from this file."
        return jsonify({"error": message}), 422

    # Create a placeholder report first. The Internet scan is asynchronous.
    initial = {
        "similarity_percent": 0.0,
        "original_percent": 0.0,
        "ai_probability": 0.0,
        "human_probability": 0.0,
        "confidence_score": 0.0,
        "category": "Very Low",
        "matched_paragraphs": [],
        "matched_sources": [],
        "summary": "Internet plagiarism scan is being processed. This page will update automatically when the online scan finishes.",
    }
    report_id = create_report(doc_id, u["id"], initial)
    update_report_status(report_id, "processing")
    try:
        if is_image:
            scan_id = copyleaks_submit_text(
                stored_text,
                report_id,
                filename=f"image-{report_id}.txt",
            )
        else:
            scan_id = copyleaks_submit_file(
                stored_path,
                filename=file.filename,
                report_id=report_id,
            )
        update_report_status(report_id, "processing", scan_id=scan_id)
    except Exception as e:
        update_report_status(report_id, "failed", error_message=str(e))
        create_notification(u["id"], "Internet scan failed", str(e)[:240], "danger")
        return jsonify({"error": str(e), "report_id": report_id}), 502
    add_history(u["id"], "analysis", f"Internet report #{report_id} submitted", document_id=doc_id, report_id=report_id)
    return jsonify({"report_id": report_id, "document_id": doc_id, "status": "processing"})

@bp.route("/text-check", methods=["POST"])
@login_required
def text_check():
    """Analyze plain text for plagiarism (no file upload required)."""
    u = current_user()
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    title = (data.get("title") or "").strip() or None

    # Validation
    if not text:
        return jsonify({"error": "No text provided"}), 400

    if len(text) < 20:
        return jsonify({"error": "Please enter at least 20 characters"}), 422

    # Create a document record for this text input
    th = text_hash(text)
    doc_id = create_document(
        user_id=u["id"],
        original_name="Text Input",
        stored_name="text_input",
        file_path="[text-input]",
        file_type="text",
        file_size=len(text),
        title=title,
        extracted_text=text,
        text_hash=th,
        status="processed"
    )
    add_history(u["id"], "text_check", "Text plagiarism check", document_id=doc_id)
    log_activity(u["id"], u["full_name"], "text_check", request.remote_addr, "Text plagiarism check")

    initial = {
        "similarity_percent": 0.0,
        "original_percent": 0.0,
        "ai_probability": 0.0,
        "human_probability": 0.0,
        "confidence_score": 0.0,
        "category": "Very Low",
        "matched_paragraphs": [],
        "matched_sources": [],
        "summary": "Internet plagiarism scan is being processed. This page will update automatically when the online scan finishes.",
    }
    report_id = create_report(doc_id, u["id"], initial)
    update_report_status(report_id, "processing")
    try:
        scan_id = copyleaks_submit_text(text, report_id)
        update_report_status(report_id, "processing", scan_id=scan_id)
    except Exception as e:
        update_report_status(report_id, "failed", error_message=str(e))
        create_notification(u["id"], "Internet scan failed", str(e)[:240], "danger")
        return jsonify({"error": str(e), "report_id": report_id}), 502
    add_history(u["id"], "analysis", f"Internet report #{report_id} submitted", document_id=doc_id, report_id=report_id)
    return jsonify({"report_id": report_id, "document_id": doc_id, "status": "processing"})

@bp.route("/report/<int:report_id>/status")
@login_required
def report_status(report_id):
    u = current_user()
    report = get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404
    if report["user_id"] != u["id"] and u["role"] not in ("teacher", "authority"):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({
        "report_id": report_id,
        "status": report.get("scan_status", "completed"),
        "error": report.get("error_message"),
        "similarity_percent": report.get("similarity_percent", 0),
    })

@bp.route("/copyleaks/webhook/<secret>/<int:report_id>/completed", methods=["POST"])
def copyleaks_completed_webhook(secret, report_id):
    """Receive Copyleaks status webhooks. No user session is required."""
    if secret != COPYLEAKS_WEBHOOK_SECRET:
        abort(403)
    payload = request.get_json(silent=True) or {}
    logger.info("Copyleaks completed callback received: report_id=%s payload_keys=%s",
                report_id, sorted(payload.keys()))
    try:
        parsed = parse_completed(payload)
    except ValueError as exc:
        logger.warning("Ignoring incomplete Copyleaks callback for report_id=%s: %s", report_id, exc)
        return jsonify({"ok": False, "error": str(exc)}), 422
    matches = []
    for item in parsed.get("internet_results", []):
        matches.append({
            "source_reference": item.get("url", ""),
            "similarity_percent": item.get("score", 0),
            "matched_text": item.get("matched_text", ""),
            "source_text": item.get("source_text", "Online source"),
            "citation_suggestion": f"Online source: {item.get('title') or item.get('url') or 'source'}",
        })
    summary = (f"Internet scan completed. Copyleaks found {parsed['matched_words']} matched word(s) "
               f"out of {parsed['total_words']} word(s) and an aggregated online similarity of "
               f"{parsed['similarity_percent']}%. Results are probabilistic and are not legal proof of plagiarism.")
    analysis = {
        "similarity_percent": parsed["similarity_percent"],
        "original_percent": max(0.0, min(100.0, 100.0 - parsed["similarity_percent"])),
        "ai_probability": parsed["ai_probability"],
        "human_probability": parsed["human_probability"],
        "confidence_score": parsed["confidence_score"],
        "category": category_for(parsed["similarity_percent"]),
        "matched_paragraphs": matches,
        "matched_sources": matches,
        "summary": (
            f"{summary} AI-generated probability is "
            f"{parsed['ai_probability']}% and human-written probability "
            f"is {parsed['human_probability']}%, with a confidence score "
            f"of {parsed['confidence_score']}%."
        ),
    }
    updated = update_report_from_copyleaks(report_id, analysis)
    if not updated:
        logger.warning("Ignoring duplicate or late completed callback: report_id=%s", report_id)
        return jsonify({"ok": True, "duplicate": True})
    report = get_report(report_id)
    if report:
        create_notification(report["user_id"], "Internet analysis complete", f"Report #{report_id} is ready.", "success")
    return jsonify({"ok": True})

@bp.route("/copyleaks/webhook/<secret>/<int:report_id>/error", methods=["POST"])
def copyleaks_error_webhook(secret, report_id):
    if secret != COPYLEAKS_WEBHOOK_SECRET:
        abort(403)
    payload = request.get_json(silent=True) or {}
    logger.info("Copyleaks error callback received: report_id=%s payload_keys=%s",
                report_id, sorted(payload.keys()))
    message = payload.get("message") or payload.get("error") or "Copyleaks reported an error."
    update_report_status(report_id, "failed", error_message=str(message)[:500])
    report = get_report(report_id)
    if report:
        create_notification(report["user_id"], "Internet scan failed", str(message)[:240], "danger")
    return jsonify({"ok": True})

@bp.route("/copyleaks/webhook/<secret>/<int:report_id>/new-result", methods=["POST"])
def copyleaks_new_result_webhook(secret, report_id):
    if secret != COPYLEAKS_WEBHOOK_SECRET:
        abort(403)
    payload = request.get_json(silent=True) or {}
    match = parse_new_result(payload)
    if match.get("url"):
        add_external_match(report_id, match)
    return jsonify({"ok": True})

@bp.route("/report/<int:report_id>/export/<fmt>")
@login_required
def export_report(report_id, fmt):
    """Export a report as pdf / docx / xlsx."""
    u = current_user()
    report = get_report(report_id)
    if not report:
        abort(404)
    if report["user_id"] != u["id"] and u["role"] not in ("teacher", "authority"):
        abort(403)
    report["matched_paragraphs"] = json.loads(report.get("matched_paragraphs") or "[]")
    report["matched_sources"] = _build_sources_for_export(report_id)
    doc = get_document(report["document_id"])
    user = get_user_by_id(report["user_id"])
    if fmt == "pdf":
        path = generate_pdf(report, user, doc)
        add_history(u["id"], "export_pdf", f"Report #{report_id}", report_id=report_id)
        return send_file(path, as_attachment=True, download_name=f"report_{report_id}.pdf")
    if fmt == "docx":
        path = generate_docx(report, user, doc)
        add_history(u["id"], "export_docx", f"Report #{report_id}", report_id=report_id)
        return send_file(path, as_attachment=True, download_name=f"report_{report_id}.docx")
    if fmt == "xlsx":
        path = generate_excel(report, user, doc)
        add_history(u["id"], "export_xlsx", f"Report #{report_id}", report_id=report_id)
        return send_file(path, as_attachment=True, download_name=f"report_{report_id}.xlsx")
    abort(404)
@bp.route("/report/<int:report_id>/share", methods=["POST"])
@login_required
def share_report(report_id):
    """Generate a shareable link (view-only) for a report."""
    u = current_user()
    report = get_report(report_id)
    if not report:
        abort(404)
    if report["user_id"] != u["id"] and u["role"] not in ("teacher", "authority"):
        abort(403)
    share_url = url_for("pages.view_report", report_id=report_id, _external=True)
    add_history(u["id"], "share", f"Report #{report_id}", report_id=report_id)
    return jsonify({"share_url": share_url})

def _build_sources_for_export(report_id):
    rows = get_matched_sources(report_id)
    sources = {}
    for r in rows:
        sid = r.get("source_document_id") or r["id"]
        if sid not in sources:
            sources[sid] = {
                "source_title": f"Document #{sid}",
                "source_reference": r.get("source_reference", ""),
                "similarity_percent": r.get("similarity_percent", 0),
                "matched_paragraphs": [],
            }
        sources[sid]["matched_paragraphs"].append({
            "matched_text": r.get("matched_text", ""),
            "source_text": r.get("source_text", ""),
            "similarity_percent": r.get("similarity_percent", 0),
            "citation_suggestion": r.get("citation_suggestion", ""),
        })
    return list(sources.values())
