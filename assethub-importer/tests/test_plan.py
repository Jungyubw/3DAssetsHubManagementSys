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
    assert {rows["n1"]["asset_name"], rows["n2"]["asset_name"]} == {"obj_a_props_chair_v1", "obj_b_props_chair_v1"}


def test_summary_counts_match_plan():
    inv = [f("a", "a.glb", "x"), f("b", "b.glb", "old/x"), f("c", "c.glb", "y", drive=D2)]
    rows = build_plan(inv, [], [], [], CFG)
    summary = summarize(rows)
    assert sum(r["register"] + r["skip-excluded"] for r in summary) == len(rows)
    assert {r["hub_project"]: r["register"] for r in summary} == {D1: 1, D2: 1}


def test_clashing_names_get_parent_folder():
    inv = [f("q1", "0-0-0.glb", "06. 3D/glb/2종 GLB"), f("q2", "0-0-0.glb", "06. 3D/glb/1종 GLB"),
           f("q3", "door.glb", "A/props")]
    rows = by_id(build_plan(inv, [], [], [], CFG))
    assert rows["q1"]["asset_name"] == "obj_2종_glb_0_0_0_v1"
    assert rows["q2"]["asset_name"] == "obj_1종_glb_0_0_0_v1"
    assert rows["q3"]["asset_name"] == "obj_door_v1"  # no clash, no folder name


def test_clash_with_same_parent_name_goes_up_a_level():
    inv = [f("r1", "web.glb", "S1/glb"), f("r2", "web.glb", "S2/glb")]
    rows = by_id(build_plan(inv, [], [], [], CFG))
    assert {rows["r1"]["asset_name"], rows["r2"]["asset_name"]} == {"obj_s1_web_v1", "obj_s2_web_v1"}  # "glb" is a generic folder


def test_drive_default_category_applies_only_without_keyword():
    mapping = [{"shared_drive": D1, "hub_project": "P", "default_category": "twin"}]
    inv = [f("t1", "pump.glb", "1공장"), f("t2", "worker.glb", "캐릭터")]
    rows = by_id(build_plan(inv, [], [], mapping, CFG))
    assert rows["t1"]["asset_name"] == "twin_pump_v1"
    assert "category guess" not in rows["t1"]["reason"]
    assert rows["t2"]["asset_name"] == "char_worker_v1"


def test_test_and_delete_folders_excluded():
    inv = [f("u1", "a.glb", "#12. 테스트할 3D GLB"), f("u2", "b.glb", "s5_ optimization_test"),
           f("u3", "c.glb", "삭제예정"), f("u4", "d.glb", "testbed")]
    rows = by_id(build_plan(inv, [], [], [], CFG))
    assert [rows[i]["decision"] for i in ("u1", "u2", "u3", "u4")] == ["skip-excluded"] * 3 + ["register"]
