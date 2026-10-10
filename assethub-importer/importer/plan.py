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

    # 3. 프로젝트 매핑, 4. 이름·태그·설명
    drive_to_project = {m["shared_drive"].strip(): m["hub_project"].strip() for m in mapping if m.get("hub_project")}
    hub_project_names = {p["name"].strip() for p in hub_projects}
    used_names: dict[str, set[str]] = defaultdict(set)
    for r in hub_assets:
        used_names[r["project_name"].strip()].add(r["name"])

    out = []
    for f in files:
        row = f.row
        project = drive_to_project.get(row["shared_drive"].strip(), row["shared_drive"].strip())
        category, ambiguous = naming.classify(row["file_name"], row["path"], config["classification"])
        name = tags = desc = ""
        reason = f.reason
        if f.decision in ("register", "too-large"):
            name = naming.asset_name(category, f.parsed.target, f.parsed.variant, f.n)
            base, i = name, 2
            while name in used_names[project]:
                name, i = f"{base}_{i}", i + 1
            if name != base:
                reason += f"; name collision, renamed from {base}"
            used_names[project].add(name)
            tags = ";".join(naming.build_tags(category, row["file_name"], row["path"], config, list(f.extra_tags)))
            desc = naming.description(
                config["naming"]["description"], drive=row["shared_drive"], path=row["path"],
                file_name=row["file_name"], size_bytes=f.size, modified_time=row["modified_time"],
                file_id=row["drive_file_id"],
            )
            if ambiguous:
                reason += f"; category guess '{category}'"
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
