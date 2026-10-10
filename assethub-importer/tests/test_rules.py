from importer import naming, rules
from importer.config import load_settings

CFG = load_settings().config


def test_excluded_folder_matches_glob_and_case():
    pats = CFG["selection"]["exclude_folders"]
    assert rules.excluded_folder("AED/웹콘텐츠/_이전_v1.14/3D에셋/glb", pats) == "_이전_v1.14"
    assert rules.excluded_folder("AED/Backup/glb", pats) == "Backup"
    assert rules.excluded_folder("03. 3D라이브러리/#08.개발GLB_bak", pats) == "#08.개발GLB_bak"
    # '백업' folders are registered by user decision (152 models exist only there)
    assert rules.excluded_folder("캐릭터/2022 캐릭터 백업", pats) is None
    # '과거' is not a keyword: TF_디지털트윈 keeps finished projects (382 unique models) under "99. 과거 파일"
    assert rules.excluded_folder("99. 과거 파일/0. 프로젝트/02. 리파코", pats) is None
    assert rules.excluded_folder("AED/이전파일", pats) == "이전파일"
    assert rules.excluded_folder("Bold/folder", pats) is None
    assert rules.excluded_folder("AED/웹콘텐츠/3D에셋/glb", pats) is None
    # substring is not enough: 'template' is not 'temp'
    assert rules.excluded_folder("AED/template", pats) is None


def test_strip_version():
    assert rules.strip_version("emt_v1.2") == ("emt", (1, 2))
    assert rules.strip_version("emt-V3") == ("emt", (3,))
    assert rules.strip_version("emt") == ("emt", None)
    assert rules.strip_version("v2") == ("v2", None)


def test_parse_name_suffix_and_folder_variants():
    v = CFG["variants"]
    p = rules.parse_name("Patient2_Dressed_v1.4.glb", "AED/glb", v["suffixes"], v["folders"])
    assert (p.target, p.variant, p.version) == ("patient2", "dressed", (1, 4))
    p = rules.parse_name("barista.glb", "AED/Unity", v["suffixes"], v["folders"])
    assert (p.target, p.variant) == ("barista", "unity")
    p = rules.parse_name("lite.glb", "AED", v["suffixes"], v["folders"])
    assert p.target == "lite"  # a lone suffix word is the target, not a variant


def test_content_key_ignores_version_marks():
    assert rules.content_key("AED/웹_v1.2/glb") == rules.content_key("AED/웹_v1.4/glb")
    assert rules.content_key("AED/glb") != rules.content_key("IP19/glb")


def test_classify_and_name():
    kw = CFG["classification"]
    assert naming.classify("barista.glb", "AED/캐릭터", kw) == ("char", False)
    assert naming.classify("fastening_asbuilt.glb", "신성/설비", kw)[0] == "twin"
    assert naming.classify("chair.glb", "AED/props", kw) == ("obj", True)  # 'hair' must not match
    assert naming.classify("velocity_bitmap.glb", "AED/animal", kw) == ("obj", True)
    assert naming.classify("Player2.glb", "AED/Animation", kw)[0] == "char"
    assert naming.asset_name("char", "patient2", "dressed", 1) == "char_patient2_dressed_v1"
    assert naming.asset_name("char", "barista", "", 2) == "char_barista_v2"


def test_tags_include_category_folder_and_import_tag():
    tags = naming.build_tags("char", "npc_barista.glb", "방송대 제안작업/AED_실감형콘텐츠_S2/glb", CFG, ["PJ_other"])
    assert tags == ["character", "npc", "AED_실감형콘텐츠_S2", "PJ_other", "drive-import-2026-10"]


def test_qualifier_folders_skip_generic_version_and_repeats():
    generic = CFG["naming"]["generic_folders"]
    path = "#2025/1. ETC/assets(v.1.7.33)/v.1.7.33/glbs"
    assert naming.qualifier_folders(path, "rice_small", generic)[:2] == ["assets_v_1_7_33", "1_etc"]
    assert naming.qualifier_folders("작업/eq_pump_a/glb", "eq_pump_a", generic) == ["작업"]
    assert naming.qualifier_folders("2022/20221103", "web", generic) == ["20221103", "2022"]
