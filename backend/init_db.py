"""SQLite schema + seed data.

Creates the SQLite database file (database/plagiascan.db) with the same
table layout as database/schema.sql, and seeds the three roles plus a
default authority account (admin@plagiascan.ai / admin123).

Safe to run repeatedly: uses CREATE TABLE IF NOT EXISTS and checks before
inserting seed rows.
"""
import os
import sqlite3

from config import SQLITE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  description   TEXT,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  role_id         INTEGER NOT NULL,
  full_name       TEXT NOT NULL,
  email           TEXT NOT NULL UNIQUE,
  password_hash   TEXT NOT NULL,
  phone           TEXT,
  avatar_url      TEXT,
  department      TEXT,
  is_active       INTEGER NOT NULL DEFAULT 1,
  reset_token     TEXT,
  reset_expires   TEXT,
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS students (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL UNIQUE,
  student_code    TEXT NOT NULL UNIQUE,
  course          TEXT,
  year_of_study   INTEGER,
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teachers (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL UNIQUE,
  employee_code   TEXT NOT NULL UNIQUE,
  designation     TEXT,
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS authorities (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL UNIQUE,
  admin_code      TEXT NOT NULL UNIQUE,
  access_level    TEXT NOT NULL DEFAULT 'full',
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS documents (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL,
  original_name   TEXT NOT NULL,
  stored_name     TEXT NOT NULL,
  file_path       TEXT NOT NULL,
  file_type       TEXT NOT NULL,
  file_size       INTEGER NOT NULL DEFAULT 0,
  title           TEXT,
  extracted_text  TEXT,
  text_hash       TEXT,
  status          TEXT NOT NULL DEFAULT 'uploaded',
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id         INTEGER NOT NULL,
  user_id             INTEGER NOT NULL,
  similarity_percent  REAL NOT NULL DEFAULT 0,
  original_percent    REAL NOT NULL DEFAULT 0,
  ai_probability      REAL NOT NULL DEFAULT 0,
  human_probability   REAL NOT NULL DEFAULT 0,
  confidence_score    REAL NOT NULL DEFAULT 0,
  category            TEXT NOT NULL DEFAULT 'Very Low',
  matched_paragraphs   TEXT,
  summary             TEXT,
  scan_status         TEXT NOT NULL DEFAULT 'completed',
  copyleaks_scan_id   TEXT,
  error_message       TEXT,
  created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  document_id   INTEGER,
  report_id     INTEGER,
  action        TEXT NOT NULL,
  detail        TEXT,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matched_sources (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  report_id           INTEGER NOT NULL,
  source_document_id  INTEGER,
  source_text         TEXT,
  matched_text        TEXT,
  similarity_percent  REAL NOT NULL DEFAULT 0,
  source_reference   TEXT,
  citation_suggestion TEXT,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER,
  actor_name    TEXT,
  action        TEXT NOT NULL,
  ip_address    TEXT,
  detail        TEXT,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  title         TEXT NOT NULL,
  message       TEXT NOT NULL,
  type          TEXT NOT NULL DEFAULT 'info',
  is_read       INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedback (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER,
  rating        INTEGER NOT NULL,
  message       TEXT,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL UNIQUE,
  theme         TEXT NOT NULL DEFAULT 'dark',
  email_alerts  INTEGER NOT NULL DEFAULT 1,
  auto_report   INTEGER NOT NULL DEFAULT 0,
  language      TEXT NOT NULL DEFAULT 'en',
  updated_at    TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_user   ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_user      ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_document ON reports(document_id);
CREATE INDEX IF NOT EXISTS idx_history_user      ON history(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_user     ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_created  ON activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_user     ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created  ON feedback(created_at);
"""

def init_db():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.executescript(SCHEMA)
    # Lightweight migration for databases created by older versions.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
    migrations = {
        "scan_status": "ALTER TABLE reports ADD COLUMN scan_status TEXT NOT NULL DEFAULT 'completed'",
        "copyleaks_scan_id": "ALTER TABLE reports ADD COLUMN copyleaks_scan_id TEXT",
        "error_message": "ALTER TABLE reports ADD COLUMN error_message TEXT",
    }
    for name, sql in migrations.items():
        if name not in columns:
            conn.execute(sql)
    conn.commit()

    # Seed roles
    roles = [("student", "Standard student account"),
             ("teacher", "Teacher / faculty member"),
             ("authority", "High authority administrator")]
    for name, desc in roles:
        existing = conn.execute("SELECT id FROM roles WHERE name = ?", (name,)).fetchone()
        if existing:
            continue
        conn.execute("INSERT INTO roles (name, description) VALUES (?, ?)", (name, desc))
    conn.commit()

    # Seed default authority account
    from werkzeug.security import generate_password_hash
    admin_email = "admin@plagiascan.ai"
    admin = conn.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
    if not admin:
        role_id = conn.execute("SELECT id FROM roles WHERE name = 'authority'").fetchone()[0]
        pw = generate_password_hash("admin123")
        cur = conn.execute(
            "INSERT INTO users (role_id, full_name, email, password_hash, department, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (role_id, "System Administrator", admin_email, pw, "Administration"),
        )
        uid = cur.lastrowid
        conn.execute(
            "INSERT INTO authorities (user_id, admin_code, access_level) VALUES (?, ?, ?)",
            (uid, "AUTH-001", "full"),
        )
        conn.execute(
            "INSERT INTO settings (user_id) VALUES (?)",
            (uid,),
        )
    conn.commit()
    conn.close()
    print(f"[init_db] SQLite database ready at {SQLITE_PATH}")
if __name__ == "__main__":
    init_db()
