"""Database connection layer shared by every module.

All SQL in the project goes through the helpers here (query_all, query_one,
execute, transaction) so connections are opened, committed and closed in one
place, foreign keys are always on, and SQLite errors become our own
DatabaseError / IntegrityViolation.
"""
import os
import sqlite3
from collections import namedtuple
from contextlib import contextmanager

from modules.errors import DatabaseError, IntegrityViolation

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DEFAULT_DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "instance", "finance.db")

_db_path = os.environ.get("FINANCE_DB", DEFAULT_DB_PATH)

DEFAULT_CATEGORIES = {
    "income": ["Salary", "Business", "Allowance", "Gift", "Other income"],
    "expense": [
        "Food", "Rent", "Transport", "Airtime and data", "Utilities",
        "Education", "Health", "Entertainment", "Shopping", "Other expenses",
    ],
}

Result = namedtuple("Result", ["lastrowid", "rowcount"])


def set_db_path(path):
    """Point the whole application at a different database file (used by tests)."""
    global _db_path
    _db_path = path


def get_db_path():
    return _db_path


def get_connection():
    try:
        folder = os.path.dirname(_db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(_db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except (sqlite3.Error, OSError) as exc:
        raise DatabaseError(f"Could not open the database: {exc}") from exc


@contextmanager
def transaction():
    """Open a connection, commit on success, roll back on any error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise IntegrityViolation(str(exc)) from exc
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Database error: {exc}") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_all(sql, params=()):
    """Run a SELECT with bound parameters and return all rows."""
    with transaction() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql, params=()):
    """Run a SELECT with bound parameters and return the first row or None."""
    with transaction() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql, params=()):
    """Run an INSERT / UPDATE / DELETE with bound parameters."""
    with transaction() as conn:
        cursor = conn.execute(sql, params)
        return Result(cursor.lastrowid, cursor.rowcount)


def init_db():
    """Create tables (if missing) and the default categories. Safe to run repeatedly."""
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
            schema = handle.read()
    except OSError as exc:
        raise DatabaseError(f"Could not read schema.sql: {exc}") from exc

    conn = get_connection()
    try:
        conn.executescript(schema)
        for category_type, names in DEFAULT_CATEGORIES.items():
            for name in names:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (user_id, category_name, category_type) "
                    "VALUES (NULL, ?, ?)",
                    (name, category_type),
                )
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Could not set up the database: {exc}") from exc
    finally:
        conn.close()
