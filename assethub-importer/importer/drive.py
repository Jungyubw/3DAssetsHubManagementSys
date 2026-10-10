"""Google Drive: shared drive list, GLB listing, folder paths, download.

SPEC 처리 흐름 1 (inventory):
- drives.list for drive names
- files.list with corpora=allDrives, includeItemsFromAllDrives, supportsAllDrives
- build folder paths in memory from one folder listing per drive (no per-file parent walk)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    size_bytes: int
    md5: str
    modified_time: str
    drive_id: str
    shared_drive: str
    path: str  # path inside the shared drive, folders only


def list_glb_files() -> list[DriveFile]:
    raise NotImplementedError("inventory: not implemented yet")


def download(file_id: str, dest_path: str) -> None:
    raise NotImplementedError("download: not implemented yet")
