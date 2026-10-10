"""Asset name, tags and description (SPEC 규칙 4)."""
from __future__ import annotations

import re

from .rules import path_segments


def has_keyword(text: str, word: str) -> bool:
    """Latin keywords match whole words only ('hair' not in 'chair'); Korean ones match as substrings."""
    word = word.lower()
    if word.isascii():
        return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None
    return word in text


def _text(file_name: str, path: str) -> str:
    return " ".join(path_segments(path) + [file_name]).lower()


def classify(file_name: str, path: str, keywords: dict[str, list[str]]) -> tuple[str, bool]:
    """Return (category, ambiguous). First matching category in config order wins; none -> 'obj'."""
    text = _text(file_name, path)
    matches = [cat for cat, words in keywords.items() if any(has_keyword(text, w) for w in words)]
    if not matches:
        return "obj", True
    return matches[0], len(matches) > 1


def asset_name(category: str, target: str, variant: str, n: int) -> str:
    return f"{category}_{target}{'_' + variant if variant else ''}_v{n}"


def content_folder(path: str, level: int) -> str:
    """Folder name used as a tag: the `level`-th folder under the drive, else the deepest one."""
    segments = path_segments(path)
    if not segments:
        return ""
    return segments[level - 1] if len(segments) >= level else segments[-1]


def build_tags(category: str, file_name: str, path: str, config: dict,
               extra: list[str] | None = None) -> list[str]:
    text = _text(file_name, path)
    tags = [config["hub_category_tags"].get(category, "object")]
    for tag in config["detail_tags"]:
        if has_keyword(text, tag) or (tag == "animation" and category == "anim"):
            tags.append(tag)
    folder = content_folder(path, config.get("content_folder_level", 2))
    if folder:
        tags.append(folder)
    tags.extend(extra or [])
    tags.append(config["import_tag"])
    return list(dict.fromkeys(tags))


def description(template: str, *, drive: str, path: str, file_name: str, size_bytes: int,
                modified_time: str, file_id: str, triangles: int | str = "?",
                animations: int | str = "?") -> str:
    return template.format(
        drive=drive,
        subpath=path or "/",
        file_name=file_name,
        size_mb=f"{size_bytes / 1_000_000:.1f}",
        modified=modified_time[:10],
        triangles=triangles,
        animations=animations,
        file_id=file_id,
    )
