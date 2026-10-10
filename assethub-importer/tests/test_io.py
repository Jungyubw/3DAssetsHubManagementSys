import httpx
import pytest

from importer import drive, hub
from importer.glbinfo import read_stats
from importer.ledger import Ledger


def test_build_path_walks_to_drive_root():
    folders = {"f3": ("glb", "f2"), "f2": ("3D에셋", "f1"), "f1": ("AED", "DRIVE")}
    assert drive.build_path("f3", "DRIVE", folders) == "AED/3D에셋/glb"
    assert drive.build_path("DRIVE", "DRIVE", folders) == ""
    loop = {"a": ("A", "b"), "b": ("B", "a")}
    assert drive.build_path("a", "DRIVE", loop) == "B/A"


def test_hub_client_pages_and_flattens(monkeypatch):
    def handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer t"
        page = int(request.url.params.get("page", 1))
        if request.url.path == "/assets":
            items = [{"id": str(i), "name": f"a{i}"} for i in range((page - 1) * 25, min(page * 25, 30))]
            return httpx.Response(200, json={"items": items, "total": 30, "page": page, "pageSize": 25})
        return httpx.Response(404)

    client = hub.HubClient("https://example.test", "t")
    client._http = httpx.Client(base_url="https://example.test", headers=client._http.headers,
                                transport=httpx.MockTransport(handler))
    assert len(client.list_assets()) == 30

    rows = hub.flatten_asset({
        "id": "1", "name": "n", "project": {"id": "p", "name": "P"}, "tags": [{"name": "space"}, "npc"],
        "currentVersion": {"version": "1.0", "files": [{"fileName": "a.glb", "sizeBytes": 5}]},
    })
    assert rows == [{"asset_id": "1", "name": "n", "project_id": "p", "project_name": "P",
                     "tags": "space;npc", "version": "1.0", "status": "", "file_name": "a.glb", "size_bytes": 5}]


def test_hub_client_requires_token():
    with pytest.raises(hub.HubAuthError):
        hub.HubClient("https://example.test", None)


def test_glb_stats(tmp_path):
    import struct

    from pygltflib import (GLTF2, Accessor, Animation, Buffer, BufferView, Mesh, Node, Primitive, Scene,
                           Attributes)

    positions = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0) * 2  # 2 triangles, 6 vertices
    gltf = GLTF2(
        scenes=[Scene(nodes=[0])], nodes=[Node(mesh=0)],
        meshes=[Mesh(primitives=[Primitive(attributes=Attributes(POSITION=0))])],
        accessors=[Accessor(bufferView=0, componentType=5126, count=6, type="VEC3",
                            max=[1, 1, 0], min=[0, 0, 0])],
        bufferViews=[BufferView(buffer=0, byteLength=len(positions))],
        buffers=[Buffer(byteLength=len(positions))],
        animations=[Animation(channels=[], samplers=[])],
    )
    gltf.set_binary_blob(positions)
    path = tmp_path / "t.glb"
    gltf.save_binary(str(path))
    s = read_stats(path)
    assert (s.triangles, s.meshes, s.animations) == (2, 1, 1)


def test_ledger_keeps_uploaded_rows(tmp_path):
    led = Ledger(tmp_path / "l.sqlite")
    row = {"drive_file_id": "a", "decision": "register", "asset_name": "obj_a_v1"}
    assert led.upsert_plan([row]) == 0
    led.conn.execute("UPDATE ledger SET status='uploaded', hub_asset_id='h1' WHERE drive_file_id='a'")
    led.conn.commit()
    assert led.upsert_plan([{**row, "asset_name": "changed"}]) == 1
    (r,) = led.rows()
    assert (r["status"], r["hub_asset_id"], r["asset_name"]) == ("uploaded", "h1", "obj_a_v1")
