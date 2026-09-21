import sqlite3
from pathlib import Path
from typing import Any, Optional


class SessionStore:
    """SQLite-backed store for hpc-gpt session usage records."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    duration_sec INTEGER NOT NULL,
                    exit_code INTEGER NOT NULL,
                    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)"
            )
            conn.commit()

    def insert_session(
        self,
        session_id: str,
        username: str,
        hostname: str,
        started_at: str,
        ended_at: str,
        duration_sec: int,
        exit_code: int,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, username, hostname, started_at, ended_at,
                    duration_sec, exit_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    username=excluded.username,
                    hostname=excluded.hostname,
                    started_at=excluded.started_at,
                    ended_at=excluded.ended_at,
                    duration_sec=excluded.duration_sec,
                    exit_code=excluded.exit_code,
                    received_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                """,
                (
                    session_id,
                    username,
                    hostname,
                    started_at,
                    ended_at,
                    duration_sec,
                    exit_code,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row)

    def list_sessions(
        self, username: Optional[str] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        with self._connect() as conn:
            if username:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE username = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (username, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_sessions,
                    COUNT(DISTINCT username) AS unique_users,
                    COALESCE(SUM(duration_sec), 0) AS total_duration_sec,
                    COALESCE(AVG(duration_sec), 0) AS avg_duration_sec
                FROM sessions
                """
            ).fetchone()
        return {
            "total_sessions": int(row["total_sessions"]),
            "unique_users": int(row["unique_users"]),
            "total_duration_sec": int(row["total_duration_sec"]),
            "avg_duration_sec": float(row["avg_duration_sec"]),
        }
