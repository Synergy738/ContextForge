import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path.home() / ".contextforge" / "sessions.db"


def _get_connection():
    """Get a database connection with row factory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database and create tables if missing."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path        TEXT NOT NULL,
            task_description    TEXT NOT NULL,
            ide                 TEXT NOT NULL,
            language            TEXT,
            context_snapshot    TEXT,
            generated_rules     TEXT,
            git_hash_before     TEXT,
            git_hash_after      TEXT,
            rating              INTEGER,
            timestamp           TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_session(
    project_path: str,
    task: str,
    ide: str,
    language: str,
    context_snapshot: dict,
    generated_rules: str,
    git_hash_before: str,
) -> int:
    """Save a session and return the new ID."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (
            project_path, task_description, ide, language,
            context_snapshot, generated_rules, git_hash_before, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_path, task, ide, language,
        str(context_snapshot), generated_rules, git_hash_before,
        datetime.now().isoformat()
    ))
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def rate_last_session(project_path: str, rating: int, git_hash_after: str) -> bool:
    """Rate the most recent unrated session for this project."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sessions
        SET rating = ?, git_hash_after = ?
        WHERE id = (
            SELECT id FROM sessions
            WHERE project_path = ? AND rating IS NULL
            ORDER BY timestamp DESC
            LIMIT 1
        )
    """, (rating, git_hash_after, project_path))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_project_sessions(project_path: str) -> list:
    """Get all rated sessions for a project, newest first."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM sessions
        WHERE project_path = ? AND rating IS NOT NULL
        ORDER BY timestamp DESC
    """, (project_path,))
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions


def get_patterns(project_path: str) -> dict:
    """Analyze patterns from rated sessions. Requires 3+ rated sessions."""
    sessions = get_project_sessions(project_path)
    if len(sessions) < 3:
        return {}

    total = len(sessions)
    good = sum(1 for s in sessions if s["rating"] == 1)
    bad = total - good

    # Extract keywords from good tasks
    good_tasks = [s["task_description"] for s in sessions if s["rating"] == 1]
    word_counts = {}
    for task in good_tasks:
        words = [w.lower() for w in task.split() if len(w) > 4]
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

    common_keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    common_keywords = [w for w, c in common_keywords]

    # IDE scores
    ide_scores = {}
    for s in sessions:
        ide = s["ide"]
        if ide not in ide_scores:
            ide_scores[ide] = {"good": 0, "bad": 0}
        if s["rating"] == 1:
            ide_scores[ide]["good"] += 1
        else:
            ide_scores[ide]["bad"] += 1

    return {
        "total_sessions": total,
        "good_sessions": good,
        "bad_sessions": bad,
        "common_good_task_keywords": common_keywords,
        "ide_scores": ide_scores,
    }
