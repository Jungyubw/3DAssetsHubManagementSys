"""AssetHub API client.

Read endpoints are confirmed (docs/SPEC.md, AssetHub API).
Write endpoints (project create, asset create, file upload, new version) and the
script auth method are pending dev team confirmation: the write methods stay as
interfaces until the spec arrives. Until then, ASSETHUB_TOKEN is sent as a Bearer
token, which may need to change once the auth method is confirmed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx

PAGE_SIZE = 25  # fixed by the API; pageSize=100 returns 400

HUB_ASSET_COLUMNS = [
    "asset_id", "name", "project_id", "project_name", "tags",
    "version", "status", "file_name", "size_bytes",
]
HUB_PROJECT_COLUMNS = ["project_id", "name", "status"]


class HubAuthError(RuntimeError):
    pass


class HubClient:
    def __init__(self, api_base: str, token: str | None, timeout: float = 30.0) -> None:
        if not token:
            raise HubAuthError(
                "ASSETHUB_TOKEN is not set. The script auth method is pending dev team "
                "confirmation (docs/SPEC.md). Do not copy browser cookies."
            )
        transport = httpx.HTTPTransport(retries=3)
        self._http = httpx.Client(
            base_url=api_base.rstrip("/"),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def _get(self, path: str, **params) -> dict | list:
        resp = self._http.get(path, params=params or None)
        if resp.status_code in (401, 403):
            raise HubAuthError(f"AssetHub rejected the token ({resp.status_code}) for GET {path}")
        resp.raise_for_status()
        return resp.json()

    # --- read (confirmed) ---
    def list_projects(self) -> list[dict]:
        """GET /projects?status=all"""
        data = self._get("/projects", status="all")
        return data["items"] if isinstance(data, dict) and "items" in data else data

    def list_assets(self, on_page=None) -> list[dict]:
        """GET /assets?page=N until all items are collected."""
        items: list[dict] = []
        page = 1
        while True:
            data = self._get("/assets", page=page)
            batch = data.get("items", [])
            items.extend(batch)
            if on_page:
                on_page(len(items), data.get("total"))
            if not batch or len(items) >= data.get("total", 0):
                return items
            page += 1

    def get_asset(self, asset_id: str) -> dict:
        """GET /assets/{id}"""
        return self._get(f"/assets/{asset_id}")

    def get_assets(self, asset_ids: list[str], concurrency: int = 8) -> list[dict]:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            return list(pool.map(self.get_asset, asset_ids))

    # --- write (pending dev team API spec) ---
    def create_project(self, name: str) -> str:
        raise NotImplementedError("AssetHub project create API pending dev team spec")

    def create_asset(self, project_id: str, name: str, description: str,
                     tags: list[str], change_memo: str, glb_path: str) -> str:
        raise NotImplementedError("AssetHub asset create/upload API pending dev team spec")


def flatten_asset(detail: dict) -> list[dict]:
    """One row per file of the asset's current version."""
    project = detail.get("project") or {}
    version = detail.get("currentVersion") or {}
    tags = detail.get("tags") or []
    tag_names = [t["name"] if isinstance(t, dict) else str(t) for t in tags]
    base = {
        "asset_id": detail.get("id", ""),
        "name": detail.get("name", ""),
        "project_id": project.get("id", ""),
        "project_name": project.get("name", ""),
        "tags": ";".join(tag_names),
        "version": version.get("version", ""),
        "status": detail.get("status", ""),
    }
    files = version.get("files") or []
    if not files:
        return [{**base, "file_name": "", "size_bytes": ""}]
    return [{**base, "file_name": f.get("fileName", ""), "size_bytes": f.get("sizeBytes", "")} for f in files]
