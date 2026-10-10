"""Build the registration plan from inventory + hub snapshot + mapping (SPEC 처리 흐름 3)."""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import naming, rules

PLAN_COLUMNS = [
    "drive_file_id", "shared_drive", "path", "file_name", "size_bytes", "md5", "modified_time",
    "group_id", "decision", "reason", "hub_project", "new_project", "asset_name", "tags",
    "description_preview",
]


@dataclass(eq=False)
class _File:
    row: dict
    size: int
    excluded_by: str | None
    parsed: rules.ParsedName
    rev_key: tuple
    decision: str = ""
    reason: str = ""
    group_id: str = ""
    n: int = 1
    extra_tags: tuple[str, ...] = ()


def _rep_sort_key(f: _File):
    # 대표본: ① 제외 키워드 없는 경로 ② 최근 modifiedTime ③ 짧은 경로
    return (f.excluded_by is not None, _neg(f.row["modified_time"]), len(f.row["path"]))


def _neg(s: str) -> tuple[int, ...]:
    return tuple(-ord(c) for c in s)


def _gid(key) -> str:
    return hashlib.sha1("|".join(map(str, key)).encode()).hexdigest()[:10]


def build_plan(inventory: list[dict], hub_assets: list[dict], hub_projects: list[dict],
               mapping: list[dict], config: dict) -> list[dict]:
    sel, var = config["selection"], config["variants"]
    max_bytes = config["limits"]["max_upload_mb"] * 1_000_000
    hub_keys = {(r["file_name"].lower(), int(r["size_bytes"])) for r in hub_assets
                if r.get("file_name") and str(r.get("size_bytes", "")).isdigit()}

    files: list[_File] = []
    for row in inventory:
        parsed = rules.parse_name(row["file_name"], row["path"], var["suffixes"], var["folders"])
        files.append(_File(
            row=row,
            size=int(row["size_bytes"] or 0),
            excluded_by=rules.excluded_folder(row["path"], sel["exclude_folders"]),
            parsed=parsed,
            rev_key=(row["shared_drive"], rules.content_key(row["path"]), parsed.target, parsed.variant),
        ))

    # 1. 대상 선정: excluded drives / folders
    for f in files:
        if f.row["shared_drive"] in sel.get("exclude_drives", []):
            f.decision, f.reason = "skip-excluded", "excluded drive"
        elif f.excluded_by:
            f.decision, f.reason = "skip-excluded", f"excluded folder '{f.excluded_by}'"

    # 2a. 완전 중복 + 허브 기존 등록: group identical content (md5, else name+size)
    by_content: dict[str, list[_File]] = defaultdict(list)
    for f in files:
        key = f.row["md5"] or f"{f.row['file_name'].lower()}:{f.size}"
        by_content[key].append(f)

    reps: list[_File] = []
    for group in by_content.values():
        in_hub = [f for f in group if (f.row["file_name"].lower(), f.size) in hub_keys]
        if in_hub:
            for f in group:
                if f.decision:
                    continue
                if f in in_hub:
                    f.decision, f.reason = "skip-existing", "same file name and size already in hub"
                else:
                    f.decision, f.reason = "skip-duplicate", f"same content already in hub as {in_hub[0].row['file_name']}"
            continue
        candidates = [f for f in group if not f.decision]
        if not candidates:
            continue
        rep = sorted(candidates, key=_rep_sort_key)[0]
        rep.extra_tags = tuple(sorted({f.row["shared_drive"] for f in group} - {rep.row["shared_drive"]}))
        reps.append(rep)
        for f in candidates:
            if f is not rep:
                f.decision = "skip-duplicate"
                f.reason = f"same content as {rep.row['shared_drive']}/{rep.row['path']}/{rep.row['file_name']}"
                f.group_id = _gid(rep.rev_key)

    # 2b. 수정본: same drive + content folder + target + variant -> keep the latest
    by_rev: dict[tuple, list[_File]] = defaultdict(list)
    for f in reps:
        by_rev[f.rev_key].append(f)
    for key, group in by_rev.items():
        group.sort(key=_rep_sort_key)
        latest = group[0]
        gid = _gid(key)
        for f in group:
            f.group_id = gid
        latest.n = len(group)
        for f in group[1:]:
            f.decision, f.reason = "skip-older", f"older revision of {latest.row['file_name']} ({latest.row['modified_time'][:10]})"
        if latest.size > max_bytes:
            latest.decision, latest.reason = "too-large", f"{latest.size / 1_000_000:.1f}MB > {config['limits']['max_upload_mb']}MB"
        else:
            latest.decision = "register"
            latest.reason = "latest revision" if len(group) > 1 else "unique"

    # 3. 프로젝트 매핑
    drive_to_project = {m["shared_drive"].strip(): m["hub_project"].strip() for m in mapping if m.get("hub_project")}
    drive_category = {m["shared_drive"].strip(): m["default_category"].strip()
                      for m in mapping if (m.get("default_category") or "").strip()}
    hub_project_names = {p["name"].strip() for p in hub_projects}
    hub_names: dict[str, set[str]] = defaultdict(set)
    for r in hub_assets:
        hub_names[r["project_name"].strip()].add(r["name"])

    # 4. 이름: 분류_대상_변형_v번호, 같은 프로젝트에서 겹치면 상위 폴더명을 붙여 구분
    named = [f for f in files if f.decision in ("register", "too-large")]
    info: dict[int, dict] = {}
    for f in named:
        drive_name = f.row["shared_drive"].strip()
        category, ambiguous = naming.classify(f.row["file_name"], f.row["path"], config["classification"])
        if ambiguous and drive_name in drive_category:
            category, ambiguous = drive_category[drive_name], False
        info[id(f)] = {"project": drive_to_project.get(drive_name, drive_name), "category": category,
                       "ambiguous": ambiguous, "depth": 0,
                       "folders": naming.qualifier_folders(f.row["path"], f.parsed.target,
                                                           config["naming"].get("generic_folders", []))}
    max_depth = config["naming"].get("max_folder_qualifiers", 3)

    def name_of(f: _File) -> str:
        i = info[id(f)]
        qualifier = naming.folder_qualifier(i["folders"], i["depth"])
        target = f"{qualifier}_{f.parsed.target}" if qualifier else f.parsed.target
        return naming.asset_name(i["category"], target, f.parsed.variant, f.n)

    names = {id(f): name_of(f) for f in named}
    for _ in range(max_depth):
        groups: dict[tuple, list[_File]] = defaultdict(list)
        for f in named:
            groups[(info[id(f)]["project"], names[id(f)])].append(f)
        clashing = [g for (proj, name), g in groups.items() if len(g) > 1 or name in hub_names[proj]]
        if not clashing:
            break
        for g in clashing:
            for f in g:
                if info[id(f)]["depth"] < len(info[id(f)]["folders"]):
                    info[id(f)]["depth"] += 1
                    names[id(f)] = name_of(f)
    # Still clashing after folder qualifiers: number them in a stable order
    taken: dict[str, set[str]] = defaultdict(lambda: set())
    for proj, existing in hub_names.items():
        taken[proj] |= existing
    for f in sorted(named, key=lambda x: (x.row["path"], x.row["file_name"], x.row["drive_file_id"])):
        proj, name = info[id(f)]["project"], names[id(f)]
        base, n = name, 2
        while name in taken[proj]:
            name, n = f"{base}_{n}", n + 1
        taken[proj].add(name)
        names[id(f)] = name

    out = []
    for f in files:
        row = f.row
        drive_name = row["shared_drive"].strip()
        project = drive_to_project.get(drive_name, drive_name)
        name = tags = desc = ""
        reason = f.reason
        if id(f) in info:
            i = info[id(f)]
            name = names[id(f)]
            if i["depth"]:
                reason += "; folder name added to avoid a name clash"
            tags = ";".join(naming.build_tags(i["category"], row["file_name"], row["path"], config,
                                              list(f.extra_tags)))
            desc = naming.description(
                config["naming"]["description"], drive=row["shared_drive"], path=row["path"],
                file_name=row["file_name"], size_bytes=f.size, modified_time=row["modified_time"],
                file_id=row["drive_file_id"],
            )
            if i["ambiguous"]:
                reason += f"; category guess '{i['category']}'"
        out.append({
            "drive_file_id": row["drive_file_id"],
            "shared_drive": row["shared_drive"],
            "path": row["path"],
            "file_name": row["file_name"],
            "size_bytes": f.size,
            "md5": row["md5"],
            "modified_time": row["modified_time"],
            "group_id": f.group_id,
            "decision": f.decision,
            "reason": reason,
            "hub_project": project,
            "new_project": "yes" if project not in hub_project_names and name else "",
            "asset_name": name,
            "tags": tags,
            "description_preview": desc,
        })
    return out


def summarize(plan: list[dict]) -> list[dict]:
    """Per hub project: counts per decision, register size, whether the project is new."""
    by_project: dict[str, Counter] = defaultdict(Counter)
    size: Counter = Counter()
    new: dict[str, bool] = {}
    for r in plan:
        p = r["hub_project"]
        by_project[p][r["decision"]] += 1
        if r["decision"] == "register":
            size[p] += int(r["size_bytes"])
        new[p] = new.get(p, False) or bool(r["new_project"])
    rows = []
    for p in sorted(by_project, key=lambda x: -by_project[x]["register"]):
        c = by_project[p]
        rows.append({
            "hub_project": p,
            # SPEC: only create projects that get at least one GLB
            "new_project": "yes" if new[p] and c["register"] else "",
            **{d: c[d] for d in rules.DECISIONS},
            "register_mb": round(size[p] / 1_000_000, 1),
        })
    return rows
