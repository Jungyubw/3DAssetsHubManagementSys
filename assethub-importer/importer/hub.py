"""AssetHub API client.

Read endpoints are confirmed (docs/SPEC.md, AssetHub API).
Write endpoints (project create, asset create, file upload, new version) are
pending dev team confirmation: keep them as interfaces until the spec arrives.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HubAsset:
    asset_id: str
    name: str
    project_id: str
    project_name: str
    tags: list[str]
    version: str
    file_names: list[str]
    file_sizes: list[int]


class HubClient:
    def __init__(self, api_base: str, token: str | None) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token

    # --- read (confirmed) ---
    def list_projects(self) -> list[dict]:
        """GET /projects?status=all"""
        raise NotImplementedError

    def list_assets(self) -> list[dict]:
        """GET /assets?page=N (pageSize fixed at 25)"""
        raise NotImplementedError

    def get_asset(self, asset_id: str) -> dict:
        """GET /assets/{id}"""
        raise NotImplementedError

    # --- write (pending dev team API spec) ---
    def create_project(self, name: str) -> str:
        raise NotImplementedError("AssetHub project create API pending dev team spec")

    def create_asset(self, project_id: str, name: str, description: str,
                     tags: list[str], change_memo: str, glb_path: str) -> str:
        raise NotImplementedError("AssetHub asset create/upload API pending dev team spec")
