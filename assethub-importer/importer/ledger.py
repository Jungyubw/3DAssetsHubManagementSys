"""Ledger: local SQLite is the source of truth; the Google Sheet is synced from it (SPEC 원장)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = (
    "drive_file_id", "shared_drive", "path", "file_name", "size_bytes", "md5", "modified_time",
    "group_id", "decision", "reason", "hub_project", "asset_name", "tags",
    "hub_asset_id", "hub_version", "status", "error", "updated_at",
)
STATUSES = ("planned", "uploaded", "verified", "failed")
DONE = ("uploaded", "verified")
PLAN_FIELDS = COLUMNS[:13]


class Ledger:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        cols = ", ".join(f"{c} TEXT" for c in COLUMNS[1:])
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS ledger (drive_file_id TEXT PRIMARY KEY, {cols})")

    def upsert_plan(self, rows: list[dict]) -> int:
        """Record plan decisions. Rows already uploaded/verified keep their hub fields and status.
        Returns how many rows were left untouched because they are already done."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        done = {r["drive_file_id"] for r in self.conn.execute(
            f"SELECT drive_file_id FROM ledger WHERE status IN ({','.join('?' * len(DONE))})", DONE)}
        placeholders = ", ".join("?" * (len(PLAN_FIELDS) + 2))
        updates = ", ".join(f"{c}=excluded.{c}" for c in PLAN_FIELDS[1:])
        with self.conn:
            for r in rows:
                if r["drive_file_id"] in done:
                    continue
                self.conn.execute(
                    f"INSERT INTO ledger ({', '.join(PLAN_FIELDS)}, status, updated_at) VALUES ({placeholders}) "
                    f"ON CONFLICT(drive_file_id) DO UPDATE SET {updates}, status=excluded.status, "
                    f"updated_at=excluded.updated_at",
                    [str(r.get(c, "")) for c in PLAN_FIELDS] + ["planned", now],
                )
        return sum(1 for r in rows if r["drive_file_id"] in done)

    def rows(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM ledger ORDER BY shared_drive, path, file_name")]
