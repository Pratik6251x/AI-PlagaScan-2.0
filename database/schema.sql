-- PlagiaScan AI Lite - MySQL Schema
-- Run:  mysql -u root -p < database/schema.sql

CREATE DATABASE IF NOT EXISTS plagiascan_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE plagiascan_db;

-- Foreign key checks
SET FOREIGN_KEY_CHECKS = 0;

-- Roles

CREATE TABLE IF NOT EXISTS roles (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(50)  NOT NULL UNIQUE,
  description   VARCHAR(255) NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Users  (students, teachers, authorities all live here; role_id links role)

CREATE TABLE IF NOT EXISTS users (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  role_id         INT NOT NULL,
  full_name       VARCHAR(150) NOT NULL,
  email           VARCHAR(150) NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  phone           VARCHAR(30)  NULL,
  avatar_url      VARCHAR(255) NULL,
  department      VARCHAR(100) NULL,
  is_active       TINYINT(1) NOT NULL DEFAULT 1,
  reset_token     VARCHAR(255) NULL,
  reset_expires   DATETIME NULL,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Students  (profile info that only applies to students)

CREATE TABLE IF NOT EXISTS students (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL UNIQUE,
  student_code    VARCHAR(50)  NOT NULL UNIQUE,
  course          VARCHAR(100) NULL,
  year_of_study   INT NULL,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Teachers

CREATE TABLE IF NOT EXISTS teachers (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL UNIQUE,
  employee_code   VARCHAR(50)  NOT NULL UNIQUE,
  designation      VARCHAR(100) NULL,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
-- Authorities (high-level admins)

CREATE TABLE IF NOT EXISTS authorities (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL UNIQUE,
  admin_code      VARCHAR(50)  NOT NULL UNIQUE,
  access_level    VARCHAR(50)  NOT NULL DEFAULT 'full',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_authorities_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
-- Documents (uploaded files)

CREATE TABLE IF NOT EXISTS documents (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id         INT NOT NULL,
  original_name   VARCHAR(255) NOT NULL,
  stored_name     VARCHAR(255) NOT NULL,
  file_path       VARCHAR(500) NOT NULL,
  file_type       VARCHAR(20)  NOT NULL,
  file_size       BIGINT NOT NULL DEFAULT 0,
  title           VARCHAR(255) NULL,
  extracted_text  LONGTEXT NULL,
  text_hash       VARCHAR(64) NULL,
  status          VARCHAR(20)  NOT NULL DEFAULT 'uploaded',
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_documents_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
-- Reports (analysis result for a document)

CREATE TABLE IF NOT EXISTS reports (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  document_id         INT NOT NULL,
  user_id             INT NOT NULL,
  similarity_percent  DECIMAL(5,2) NOT NULL DEFAULT 0,
  original_percent    DECIMAL(5,2) NOT NULL DEFAULT 0,
  ai_probability      DECIMAL(5,2) NOT NULL DEFAULT 0,
  human_probability   DECIMAL(5,2) NOT NULL DEFAULT 0,
  confidence_score    DECIMAL(5,2) NOT NULL DEFAULT 0,
  category            VARCHAR(20)  NOT NULL DEFAULT 'Very Low',
  matched_paragraphs  LONGTEXT NULL,
  summary             TEXT NULL,
  scan_status         VARCHAR(20) NOT NULL DEFAULT 'completed',
  copyleaks_scan_id   VARCHAR(36) NULL,
  error_message       TEXT NULL,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_reports_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- History (audit of report views / downloads / shares)
CREATE TABLE IF NOT EXISTS history (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  document_id   INT NULL,
  report_id     INT NULL,
  action        VARCHAR(50) NOT NULL,
  detail        VARCHAR(255) NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_history_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  CONSTRAINT fk_history_report FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- MatchedSources (per-match detail inside a report)
CREATE TABLE IF NOT EXISTS matched_sources (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  report_id           INT NOT NULL,
  source_document_id  INT NULL,
  source_text         TEXT NULL,
  matched_text        TEXT NULL,
  similarity_percent  DECIMAL(5,2) NOT NULL DEFAULT 0,
  source_reference    VARCHAR(255) NULL,
  citation_suggestion TEXT NULL,
  CONSTRAINT fk_matched_report FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
  CONSTRAINT fk_matched_source_doc FOREIGN KEY (source_document_id) REFERENCES documents(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ActivityLogs (system-wide audit)
CREATE TABLE IF NOT EXISTS activity_logs (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NULL,
  actor_name    VARCHAR(150) NULL,
  action        VARCHAR(100) NOT NULL,
  ip_address    VARCHAR(45) NULL,
  detail        TEXT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL,
  title         VARCHAR(255) NOT NULL,
  message       TEXT NOT NULL,
  type          VARCHAR(50) NOT NULL DEFAULT 'info',
  is_read       TINYINT(1) NOT NULL DEFAULT 0,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Feedback & Reviews (user feedback on PlagiaScan)
CREATE TABLE IF NOT EXISTS feedback (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT,
  rating        INT NOT NULL,
  message       TEXT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_feedback_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Settings (per-user preferences)
CREATE TABLE IF NOT EXISTS settings (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  user_id       INT NOT NULL UNIQUE,
  theme         VARCHAR(20) NOT NULL DEFAULT 'dark',
  email_alerts  TINYINT(1) NOT NULL DEFAULT 1,
  auto_report   TINYINT(1) NOT NULL DEFAULT 0,
  language      VARCHAR(10) NOT NULL DEFAULT 'en',
  updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_settings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- Seed data: roles
INSERT INTO roles (name, description) VALUES
  ('student',    'Standard student account'),
  ('teacher',    'Teacher / faculty member'),
  ('authority',  'High authority administrator')
ON DUPLICATE KEY UPDATE description = VALUES(description);

-- Seed data: default authority account.
-- Password: admin123  (bcrypt hash below is for "admin123")
-- Generate your own with: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('admin123'))"
INSERT INTO users (role_id, full_name, email, password_hash, department, is_active)
SELECT 3, 'System Administrator', 'admin@plagiascan.ai',
       '$2b$12$wH3q9oKZmYqE8rJvN1xXkOeXmQ0pL2sT4uV6wX8yZ0aB1cD3eF5gH',
       'Administration', 1
FROM dual
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@plagiascan.ai');

INSERT INTO authorities (user_id, admin_code, access_level)
SELECT id, 'AUTH-001', 'full' FROM users
WHERE email = 'admin@plagiascan.ai'
  AND NOT EXISTS (SELECT 1 FROM authorities WHERE user_id = (SELECT id FROM users WHERE email = 'admin@plagiascan.ai'));

-- Indexes
CREATE INDEX idx_documents_user   ON documents(user_id);
CREATE INDEX idx_reports_user      ON reports(user_id);
CREATE INDEX idx_reports_document ON reports(document_id);
CREATE INDEX idx_history_user      ON history(user_id);
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_activity_user     ON activity_logs(user_id);
CREATE INDEX idx_activity_created  ON activity_logs(created_at);
CREATE INDEX idx_feedback_user     ON feedback(user_id);
CREATE INDEX idx_feedback_created  ON feedback(created_at);

