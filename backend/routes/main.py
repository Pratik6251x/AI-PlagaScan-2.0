"""Public pages: home, about, contact, 404."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from models import log_activity, create_feedback
bp = Blueprint("main", __name__)
@bp.route("/")
def index():
    return render_template("index.html")
@bp.route("/about")
def about():
    return render_template("about.html")
@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not name or not email or not message:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("main.contact"))
        log_activity(None, name, "contact_message", request.remote_addr, f"{email}: {message[:200]}")
        flash("Thank you for contacting us. We will respond soon.", "success")
        return redirect(url_for("main.contact"))
    return render_template("contact.html")
@bp.route("/faq")
def faq():
    return render_template("faq.html")

@bp.route("/api/feedback", methods=["POST"])
def submit_feedback():
    data = request.get_json() or {}
    rating = data.get("rating")
    message = (data.get("message") or "").strip() or None
    
    # Validation
    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "Invalid rating. Must be 1-5."}), 400
    
    # Get user_id if logged in, otherwise None
    user_id = session.get("user_id") if "user_id" in session else None
    
    try:
        create_feedback(user_id, rating, message)
        return jsonify({"success": True, "message": "Thank you for your feedback!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500