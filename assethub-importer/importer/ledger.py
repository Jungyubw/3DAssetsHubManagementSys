"""Ledger: local SQLite (source of truth) + Google Sheet sync (SPEC 원장)."""
from __future__ import annotations

COLUMNS = (
    "drive_file_id",
    "shared_drive",
    "path",
    "file_name",
    "size_bytes",
    "md5",
    "modified_time",
    "group_id",
    "decision",
    "reason",
    "hub_project",
    "asset_name",
    "tags",
    "hub_asset_id",
    "hub_version",
    "status",
    "error",
    "updated_at",
)

STATUSES = ("planned", "uploaded", "verified", "failed")
