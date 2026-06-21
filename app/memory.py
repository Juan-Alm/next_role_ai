# ============================================================
#  memory.py — Tracks which jobs the agent has already found
#
#  Uses a small local SQLite database so re-running searches
#  never shows you the same listing twice. "Seen" means the
#  job appeared in ANY past search result, whether or not it
#  was shown to you in a reply.
# ============================================================

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join("data", "seen_jobs.db")


def init_db() -> None:
    """Creates the database and table if they don't already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            first_seen TEXT
        )
    """)
    conn.commit()
    conn.close()


def has_seen(job_id: str) -> bool:
    """Returns True if this job_id has been recorded before."""
    if not job_id:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_seen(job_id: str, title: str = "", company: str = "") -> None:
    """Records a job as seen. Safe to call even if already recorded."""
    if not job_id:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR IGNORE INTO seen_jobs (job_id, title, company, first_seen)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, title, company, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def filter_unseen(jobs: list[dict]) -> list[dict]:
    """
    Takes a list of job dicts (must contain 'job_id'), marks all of
    them as seen, and returns only the ones that were NEW this call.
    """
    unseen = []
    for job in jobs:
        job_id = job.get("job_id")
        if not has_seen(job_id):
            unseen.append(job)
        mark_seen(job_id, job.get("title", ""), job.get("company", ""))

    return unseen


def seen_count() -> int:
    """Returns the total number of jobs ever recorded — useful for debugging."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT COUNT(*) FROM seen_jobs")
    count = cursor.fetchone()[0]
    conn.close()
    return count