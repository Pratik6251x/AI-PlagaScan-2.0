"""Application configuration.

Database selection is controlled by the DB_BACKEND environment variable.
  - mysql  : use a real MySQL / MariaDB server (production)
  - sqlite : use a local SQLite file (development / demo, default)

When using MySQL, set the MYSQL_* environment variables (or edit the values
below). The full MySQL schema lives in database/schema.sql.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get("SECRET_KEY", "plagiascan-ai-lite-secret-key-change-me")

# Upload / report folders (absolute paths)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
REPORT_FOLDER = os.path.join(BASE_DIR, "reports")

# 1 GB max upload (bytes)
MAX_CONTENT_LENGTH = 1 * 1024 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "txt", "rtf", "odt",
    "csv", "xls", "xlsx", "png", "jpg", "jpeg",
}

# Session
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = 3600 * 8  # 8 hours

# Database backend
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").lower()

# MySQL connection settings (used when DB_BACKEND=mysql)
MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "plagiascan_db"),
    "charset": "utf8mb4",
}
# SQLite path (used when DB_BACKEND=sqlite)
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(BASE_DIR, "database", "plagiascan.db"))
# Copyleaks Internet plagiarism integration
COPYLEAKS_EMAIL = os.environ.get("COPYLEAKS_EMAIL", "").strip()
COPYLEAKS_API_KEY = os.environ.get("COPYLEAKS_API_KEY", "").strip()
COPYLEAKS_SANDBOX = os.environ.get("COPYLEAKS_SANDBOX", "false").lower() in ("1", "true", "yes", "on")
# Public URL that Copyleaks can reach for webhooks. Example with ngrok:
# https://abcd-1234.ngrok-free.app
COPYLEAKS_WEBHOOK_BASE_URL = os.environ.get("COPYLEAKS_WEBHOOK_BASE_URL", "").rstrip("/")
COPYLEAKS_WEBHOOK_SECRET = os.environ.get("COPYLEAKS_WEBHOOK_SECRET", "change-this-webhook-secret")
