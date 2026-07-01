"""
Storage: a lightweight SQLite store for two jobs — don't redraft a story
that was already processed, and keep a run history so `cli.py status`
can answer "what's actually happened" without re-reading logs.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    fingerprint TEXT PRIMARY KEY,
    title TEXT,
    source_name TEXT,
    url TEXT,
    status TEXT,          -- ingested | scored | skipped | drafted | qa_done
    score REAL,
    headline TEXT,
    outbox_paths TEXT,    -- JSON list of written output files
    created_at TEXT,
    updated_at TEXT
);
"""


class Store:
    def __init__(self, db_path: str = "signal.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True) if Path(
            db_path
        ).parent != Path(".") else None
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def already_seen(self, fingerprint: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM items WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            return row is not None

    def upsert(self, fingerprint: str, **fields) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT 1 FROM items WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if "outbox_paths" in fields and isinstance(fields["outbox_paths"], list):
                fields["outbox_paths"] = json.dumps(fields["outbox_paths"])
            if existing:
                set_clause = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
                conn.execute(
                    f"UPDATE items SET {set_clause} WHERE fingerprint = ?",
                    (*fields.values(), now, fingerprint),
                )
            else:
                cols = ["fingerprint", *fields.keys(), "created_at", "updated_at"]
                placeholders = ", ".join("?" for _ in cols)
                conn.execute(
                    f"INSERT INTO items ({', '.join(cols)}) VALUES ({placeholders})",
                    (fingerprint, *fields.values(), now, now),
                )

    def recent(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM items ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def counts_by_status(self) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM items GROUP BY status"
            ).fetchall()
            return dict(rows)
