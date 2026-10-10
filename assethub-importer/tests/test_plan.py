from importer.config import load_settings
from importer.plan import build_plan, summarize

CFG = load_settings().config
D1, D2 = "PJ_2026 광진 아메리카", "PJ_신성이엔지"


def f(fid, name, path, size=1000, md5=None, mod="2026-05-01T00:00:00.000Z", drive=D1):
    return {"drive_file_id": fid, "file_name": name, "path": path, "size_bytes": str(size),
            "md5": md5 or f"md5-{fid}", "modified_time": mod, "drive_id": "x", "shared_drive": drive}


def by_id(rows):
    return {r["drive_file_id"]: r for r in rows}


MAPPING = [{"shared_drive": D1, "hub_project": "[광진 아메리카] Smart Factory 구축"}]
PROJECTS = [{"project_id": "p1", "name": "[광진 아메리카] Smart Factory 구축", "status": "active"}]


def test_spec_scenarios():
    inv = [
        # three barista files: web-light, original folder, Unity folder -> 3 variants, all registered
        f("a1", "barista.glb", "AED/캐릭터/glb", 952_000),
        f("a2", "barista.glb", "AED/캐릭터/원본", 5_800_000),
        f("a3", "barista.glb", "AED/캐릭터/Unity", 892_000),
        # old version folder -> excluded
        f("b1", "emt.glb", "AED/웹콘텐츠/_이전_v1.14/3D에셋/glb"),
        # revisions in the same content folder: latest wins, n=2
        f("c1", "door_v1.2.glb", "AED/props", mod="2026-01-01T00:00:00.000Z"),
        f("c2", "door_v1.4.glb", "AED/props", mod="2026-03-01T00:00:00.000Z"),
        # exact duplicate across drives: latest drive wins, other drive name becomes a tag
        f("d1", "robot.glb", "factory", md5="same", mod="2026-02-01T00:00:00.000Z"),
        f("d2", "robot_copy.glb", "설비", md5="same", mod="2026-04-01T00:00:00.000Z", drive=D2),
        # already in hub (same name + size) -> skip-existing
        f("e1", "ConvenienceStore.glb", "map", 173_800_000),
        # too large
        f("g1", "huge.glb", "map", 250_000_000),
    ]
    hub = [{"asset_id": "h1", "name": "[AED] 편의점", "project_id": "p1",
            "project_name": "[광진 아메리카] Smart Factory 구축", "tags": "", "version": "1.0",
            "status": "", "file_name": "ConvenienceStore.glb", "size_bytes": "173800000"}]
    rows = by_id(build_plan(inv, hub, PROJECTS, MAPPING, CFG))

    assert [rows[i]["decision"] for i in ("a1", "a2", "a3")] == ["register"] * 3
    assert {rows[i]["asset_name"] for i in ("a1", "a2", "a3")} == {
        "char_barista_v1", "char_barista_원본_v1", "char_barista_unity_v1"}

    assert rows["b1"]["decision"] == "skip-excluded"

    assert rows["c1"]["decision"] == "skip-older"
    assert rows["c2"]["decision"] == "register"
    assert rows["c2"]["asset_name"] == "obj_door_v2"
    assert rows["c1"]["group_id"] == rows["c2"]["group_id"]

    assert rows["d1"]["decision"] == "skip-duplicate"
    assert rows["d2"]["decision"] == "register"
    assert rows["d2"]["hub_project"] == D2 and rows["d2"]["new_project"] == "yes"
    assert D1 in rows["d2"]["tags"].split(";")

    assert rows["e1"]["decision"] == "skip-existing"
    assert rows["g1"]["decision"] == "too-large"

    assert rows["a1"]["hub_project"] == "[광진 아메리카] Smart Factory 구축"
    assert rows["a1"]["new_project"] == ""
    assert "Drive ID a1" in rows["a1"]["description_preview"]


def test_duplicate_of_hub_file_under_other_name_is_skipped():
    inv = [f("x1", "store.glb", "map", 10, md5="m"), f("x2", "ConvenienceStore.glb", "map", 10, md5="m")]
    hub = [{"asset_id": "h", "name": "n", "project_id": "p", "project_name": "P", "tags": "",
            "version": "1.0", "status": "", "file_name": "ConvenienceStore.glb", "size_bytes": "10"}]
    rows = by_id(build_plan(inv, hub, [], [], CFG))
    assert rows["x2"]["decision"] == "skip-existing"
    assert rows["x1"]["decision"] == "skip-duplicate"


def test_name_collision_in_project_is_renamed():
    inv = [f("n1", "chair.glb", "A/props"), f("n2", "chair.glb", "B/props")]
    rows = by_id(build_plan(inv, [], [], [], CFG))
    assert {rows["n1"]["asset_name"], rows["n2"]["asset_name"]} == {"obj_chair_v1", "obj_chair_v1_2"}


def test_summary_counts_match_plan():
    inv = [f("a", "a.glb", "x"), f("b", "b.glb", "old/x"), f("c", "c.glb", "y", drive=D2)]
    rows = build_plan(inv, [], [], [], CFG)
    summary = summarize(rows)
    assert sum(r["register"] + r["skip-excluded"] for r in summary) == len(rows)
    assert {r["hub_project"]: r["register"] for r in summary} == {D1: 1, D2: 1}
