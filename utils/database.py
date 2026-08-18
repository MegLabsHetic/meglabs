"""SQLite database layer for DataAnalyst AI SaaS.

Handles users, projects, usage tracking, and session persistence.
"""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from config import DATABASE_PATH


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                tier TEXT DEFAULT 'free',
                api_key_anthropic TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                file_name TEXT,
                file_path TEXT,
                profile_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                intent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                project_id INTEGER,
                export_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)


# ──────────────────────────────────────────────
# User management
# ──────────────────────────────────────────────

def create_user(email: str, username: str, password: str) -> dict | None:
    """Create a new user. Returns user dict or None if already exists."""
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (email, username, password_hash, salt) VALUES (?, ?, ?, ?)",
                (email.lower().strip(), username.strip(), password_hash, salt),
            )
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
            return dict(user) if user else None
    except sqlite3.IntegrityError:
        return None


def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate a user. Returns user dict or None."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email.lower().strip(),),
        ).fetchone()
        if not user:
            return None
        user = dict(user)
        if _hash_password(password, user["salt"]) == user["password_hash"]:
            conn.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user["id"],),
            )
            return user
        return None


def get_user(user_id: int) -> dict | None:
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(user) if user else None


def update_user_tier(user_id: int, tier: str):
    with get_db() as conn:
        conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))


def update_user_api_key(user_id: int, api_key: str):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET api_key_anthropic = ? WHERE id = ?", (api_key, user_id)
        )


# ──────────────────────────────────────────────
# Project management
# ──────────────────────────────────────────────

def create_project(user_id: int, name: str, description: str = "",
                   file_name: str = None, file_path: str = None) -> int:
    """Create a project and return its ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO projects (user_id, name, description, file_name, file_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, name, description, file_name, file_path),
        )
        return cursor.lastrowid


def get_user_projects(user_id: int) -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


def update_project_profile(project_id: int, profile: dict):
    with get_db() as conn:
        conn.execute(
            "UPDATE projects SET profile_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(profile, default=str), project_id),
        )


def delete_project(project_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM chat_history WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM exports WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


# ──────────────────────────────────────────────
# Chat history
# ──────────────────────────────────────────────

def save_chat_message(project_id: int, user_id: int, role: str, content: str, intent: str = None):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_history (project_id, user_id, role, content, intent) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, user_id, role, content, intent),
        )


def get_chat_history(project_id: int, limit: int = 50) -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_history WHERE project_id = ? ORDER BY created_at ASC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Usage tracking
# ──────────────────────────────────────────────

def log_usage(user_id: int, action: str, details: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO usage_log (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details),
        )


def get_usage_today(user_id: int, action: str) -> int:
    """Count how many times a user performed an action today."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM usage_log "
            "WHERE user_id = ? AND action = ? AND date(created_at) = date('now')",
            (user_id, action),
        ).fetchone()
        return row["cnt"] if row else 0


def get_usage_stats(user_id: int) -> dict:
    """Get usage statistics for a user."""
    with get_db() as conn:
        today_uploads = get_usage_today(user_id, "upload")
        today_ai_queries = get_usage_today(user_id, "ai_query")
        total_projects = conn.execute(
            "SELECT COUNT(*) as cnt FROM projects WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]
        total_exports = conn.execute(
            "SELECT COUNT(*) as cnt FROM exports WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]
        return {
            "uploads_today": today_uploads,
            "ai_queries_today": today_ai_queries,
            "total_projects": total_projects,
            "total_exports": total_exports,
        }


# ──────────────────────────────────────────────
# Exports
# ──────────────────────────────────────────────

def save_export(user_id: int, project_id: int, export_type: str, file_path: str) -> int:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO exports (user_id, project_id, export_type, file_path) "
            "VALUES (?, ?, ?, ?)",
            (user_id, project_id, export_type, file_path),
        )
        return cursor.lastrowid


def get_user_exports(user_id: int, limit: int = 20) -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT e.*, p.name as project_name FROM exports e "
            "LEFT JOIN projects p ON e.project_id = p.id "
            "WHERE e.user_id = ? ORDER BY e.created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# Initialize DB on import
init_db()
