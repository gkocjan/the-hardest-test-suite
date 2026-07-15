"""Event store — the demo's stand-in for the production event database.

The simulator (one thread) writes, the tests (main thread) poll. SQLite in WAL
mode is enough for that; every caller gets its own connection.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording TEXT NOT NULL,
    request_type TEXT NOT NULL,      -- POST | PUT | TRACE
    event_type TEXT,                 -- recording_started | recording_finished (TRACE)
    event_id TEXT,
    plate TEXT,
    color TEXT,
    make TEXT,
    direction TEXT,
    frame_time INTEGER,              -- ms, recording time
    frame_src TEXT,                  -- rendered frame (evidence for the report)
    time_received REAL NOT NULL      -- wall clock
);
"""


class EventStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, **row) -> None:
        row.setdefault("time_received", time.time())
        columns = ", ".join(row)
        placeholders = ", ".join(f":{key}" for key in row)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO events ({columns}) VALUES ({placeholders})", row
            )

    def find(
        self,
        recording: str,
        request_types: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> List[dict]:
        query = "SELECT * FROM events WHERE recording = ?"
        params: list = [recording]
        if request_types:
            marks = ", ".join("?" for _ in request_types)
            query += f" AND request_type IN ({marks})"
            params.extend(request_types)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if event_id:
            query += " AND event_id = ?"
            params.append(event_id)
        query += " ORDER BY time_received"
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def last_frame_time(self, recording: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(frame_time) AS ft FROM events WHERE recording = ?",
                [recording],
            ).fetchone()
        return int(row["ft"] or 0)
