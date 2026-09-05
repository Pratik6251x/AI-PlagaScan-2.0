"""Flask application factory."""
import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template

from config import (SECRET_KEY, UPLOAD_FOLDER, REPORT_FOLDER, MAX_CONTENT_LENGTH,
                    SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE,
                    PERMANENT_SESSION_LIFETIME)


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["REPORT_FOLDER"] = REPORT_FOLDER
    app.config["SESSION_COOKIE_HTTPONLY"] = SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = SESSION_COOKIE_SAMESITE
    app.config["PERMANENT_SESSION_LIFETIME"] = PERMANENT_SESSION_LIFETIME

    # Ensure folders exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(REPORT_FOLDER, exist_ok=True)

    # Pre-import heavy libraries so they are cached before any request runs
    # (avoids concurrent-import BlockingIOError under the debug reloader).
    import openpyxl, reportlab, docx, pdfplumber, pptx, PyPDF2  # noqa: F401

    # Initialise database (SQLite by default)
    from init_db import init_db
    init_db()

    # Register blueprints
    from routes.main import bp as main_bp
    from routes.auth import bp as auth_bp
    from routes.api import bp as api_bp
    from routes.pages import bp as pages_bp, inject_unread_count
    from routes.student import bp as student_bp
    from routes.teacher import bp as teacher_bp
    from routes.authority import bp as authority_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(authority_bp)

    # Context processors
    app.context_processor(inject_unread_count)
    app.context_processor(_inject_current_user)

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html",
                               message="File too large. Maximum upload size is 1 GB."), 413

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html",
                               message="Something went wrong on our side. Please try again."), 500

    return app


def _inject_current_user():
    from utils.auth import current_user
    return {"current_user": current_user()}


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
