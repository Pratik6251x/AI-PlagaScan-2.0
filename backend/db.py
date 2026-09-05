"""Database connection layer.

Provides a thin wrapper that works with both MySQL (PyMySQL) and SQLite so the
app runs out-of-the-box on SQLite for local demos and on MySQL in production.

All queries use parameterised placeholders. Callers use the DB module's
helpers (execute, query, query_one) which normalise the placeholder style.
"""
import sqlite3
import threading

try:
    import pymysql
    _HAS_PYMYSQL = True
except ImportError:
    _HAS_PYMYSQL = False

from config import DB_BACKEND, MYSQL_CONFIG, SQLITE_PATH

# SQLite connections cannot be shared across threads -> one per thread.
_sqlite_local = threading.local()


def _get_sqlite_conn():
    conn = getattr(_sqlite_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _sqlite_local.conn = conn
    return conn


def _get_mysql_conn():
    return pymysql.connect(
        host=MYSQL_CONFIG["host"],
        port=MYSQL_CONFIG["port"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"],
        database=MYSQL_CONFIG["database"],
        charset=MYSQL_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_conn():
    """Return a live connection for the configured backend."""
    if DB_BACKEND == "mysql":
        if not _HAS_PYMYSQL:
            raise RuntimeError("DB_BACKEND=mysql but PyMySQL is not installed. Run: pip install pymysql")
        return _get_mysql_conn()
    return _get_sqlite_conn()


def _convert_sql(sql):
    """Convert MySQL-style %s placeholders to SQLite ? placeholders."""
    if DB_BACKEND == "sqlite":
        return sql.replace("%s", "?")
    return sql


def query(sql, params=None):
    """Run a SELECT and return a list of dict rows."""
    params = params or []
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_convert_sql(sql), params)
        rows = cur.fetchall()
        if DB_BACKEND == "sqlite":
            return [dict(r) for r in rows]
        return list(rows)
    finally:
        if DB_BACKEND == "mysql":
            conn.close()


def query_one(sql, params=None):
    """Run a SELECT and return a single dict row (or None)."""
    params = params or []
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_convert_sql(sql), params)
        row = cur.fetchone()
        if row is None:
            return None
        if DB_BACKEND == "sqlite":
            return dict(row)
        return dict(row)
    finally:
        if DB_BACKEND == "mysql":
            conn.close()


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and return lastrowid."""
    params = params or []
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_convert_sql(sql), params)
        conn.commit()
        last_id = cur.lastrowid
        return last_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if DB_BACKEND == "mysql":
            conn.close()


def execute_update(sql, params=None):
    """Run an UPDATE/DELETE and return the number of affected rows."""
    params = params or []
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_convert_sql(sql), params)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        if DB_BACKEND == "mysql":
            conn.close()


def execute_many(sql, seq_of_params):
    seq_of_params = list(seq_of_params)
    if not seq_of_params:
        return 0
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.executemany(_convert_sql(sql), seq_of_params)
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        if DB_BACKEND == "mysql":
            conn.close()
