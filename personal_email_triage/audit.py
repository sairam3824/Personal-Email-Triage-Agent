from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import DecisionRecord


class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    email_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    category TEXT NOT NULL,
                    reasoning_trace TEXT NOT NULL,
                    actions_json TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT NOT NULL,
                    correct_category TEXT NOT NULL,
                    learned_rule TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def log_decision(self, run_id: str, record: DecisionRecord, dry_run: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO decisions (
                    run_id,
                    email_id,
                    sender,
                    subject,
                    category,
                    reasoning_trace,
                    actions_json,
                    dry_run
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    record.email_id,
                    record.sender,
                    record.subject,
                    record.category,
                    record.reasoning_trace,
                    json.dumps(record.actions, ensure_ascii=True),
                    int(dry_run),
                ),
            )

    def latest_email_metadata(self, email_id: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT sender, subject, category
                FROM decisions
                WHERE email_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (email_id,),
            ).fetchone()
        if row is None:
            return None
        return {"sender": row[0], "subject": row[1], "category": row[2]}

    def log_feedback(self, email_id: str, correct_category: str, learned_rule: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback (email_id, correct_category, learned_rule)
                VALUES (?, ?, ?)
                """,
                (email_id, correct_category, learned_rule),
            )
