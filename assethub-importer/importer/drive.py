"""Google Drive: shared drive list, GLB listing, folder paths, download.

SPEC 처리 흐름 1 (inventory):
- drives.list for drive names
- files.list with corpora=allDrives, includeItemsFromAllDrives, supportsAllDrives
- build folder paths in memory from one folder listing per drive (no per-file parent walk)
"""
from __future__ import annotations

import io
from dataclasses import dataclass, fields
from pathlib import Path

from .config import Settings

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]
FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass(frozen=True)
class DriveFile:
    drive_file_id: str
    file_name: str
    size_bytes: int
    md5: str
    modified_time: str
    drive_id: str
    shared_drive: str
    path: str  # folders inside the shared drive joined by "/", "" at drive root


INVENTORY_COLUMNS = [f.name for f in fields(DriveFile)]


def get_credentials(settings: Settings):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_file = settings.google_token_file
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not settings.google_client_secret_file.exists():
            raise FileNotFoundError(
                f"Google OAuth client file not found: {settings.google_client_secret_file}. "
                "Create a desktop OAuth client in Google Cloud Console and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(settings.google_client_secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(settings: Settings):
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=get_credentials(settings), cache_discovery=False)


def _paged(request_fn, key: str, **params) -> list[dict]:
    items: list[dict] = []
    token = None
    while True:
        resp = request_fn(**params, pageToken=token).execute(num_retries=3)
        items.extend(resp.get(key, []))
        token = resp.get("nextPageToken")
        if not token:
            return items


def list_drives(service) -> dict[str, str]:
    drives = _paged(service.drives().list, "drives", pageSize=100, fields="nextPageToken, drives(id, name)")
    return {d["id"]: d["name"] for d in drives}


def list_folders(service, drive_id: str) -> dict[str, tuple[str, str | None]]:
    """Return {folder_id: (name, parent_id)} for every folder in one shared drive."""
    folders = _paged(
        service.files().list,
        "files",
        corpora="drive",
        driveId=drive_id,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        q=f"mimeType='{FOLDER_MIME}' and trashed=false",
        pageSize=1000,
        fields="nextPageToken, files(id, name, parents)",
    )
    return {f["id"]: (f["name"], (f.get("parents") or [None])[0]) for f in folders}


def build_path(parent_id: str | None, drive_id: str, folders: dict[str, tuple[str, str | None]]) -> str:
    """Join folder names from the drive root down to parent_id."""
    parts: list[str] = []
    seen: set[str] = set()
    current = parent_id
    while current and current != drive_id and current in folders and current not in seen:
        seen.add(current)
        name, current = folders[current]
        parts.append(name)
    return "/".join(reversed(parts))


def list_glb_files(service, extensions: list[str], mime_types: list[str],
                   on_progress=None) -> list[DriveFile]:
    mime_q = " or ".join(f"mimeType='{m}'" for m in mime_types)
    name_q = " or ".join(f"name contains '{e}'" for e in extensions)
    raw = _paged(
        service.files().list,
        "files",
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        q=f"({mime_q} or {name_q}) and trashed=false",
        pageSize=1000,
        fields="nextPageToken, files(id, name, size, md5Checksum, modifiedTime, parents, driveId)",
    )
    exts = tuple(e.lower() for e in extensions)
    # Only shared drives: files without driveId live in My Drive / computer backups (excluded by SPEC).
    raw = [f for f in raw if f.get("driveId") and f["name"].lower().endswith(exts)]

    drive_names = list_drives(service)
    files: list[DriveFile] = []
    for drive_id in sorted({f["driveId"] for f in raw}):
        folders = list_folders(service, drive_id)
        if on_progress:
            on_progress(drive_names.get(drive_id, drive_id))
        for f in (x for x in raw if x["driveId"] == drive_id):
            files.append(DriveFile(
                drive_file_id=f["id"],
                file_name=f["name"],
                size_bytes=int(f.get("size") or 0),
                md5=f.get("md5Checksum", ""),
                modified_time=f.get("modifiedTime", ""),
                drive_id=drive_id,
                shared_drive=drive_names.get(drive_id, drive_id).strip(),
                path=build_path((f.get("parents") or [None])[0], drive_id, folders),
            ))
    return files


def download(service, file_id: str, dest_path: Path) -> None:
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=16 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=3)
