"""Parsing helpers for selection and duplicate / revision / variant decisions (SPEC 규칙 1-2)."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass

DECISIONS = (
    "register",
    "skip-existing",
    "skip-duplicate",
    "skip-older",
    "skip-excluded",
    "too-large",
)

_STEM_VERSION = re.compile(r"[_\-\s.]*v(\d+(?:[._]\d+)*)$", re.IGNORECASE)
_SEGMENT_VERSION = re.compile(r"[_\-\s]*v\d+(?:\.\d+)*", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\s\-.]+")


def path_segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def excluded_folder(path: str, patterns: list[str]) -> str | None:
    """Return the first folder name in path matching an exclusion pattern (case-insensitive)."""
    lowered = [p.lower() for p in patterns]
    for segment in path_segments(path):
        name = segment.lower()
        if any(fnmatch.fnmatchcase(name, p) for p in lowered):
            return segment
    return None


def split_stem(file_name: str) -> str:
    return file_name.rsplit(".", 1)[0] if "." in file_name else file_name


def strip_version(stem: str) -> tuple[str, tuple[int, ...] | None]:
    """'emt_v1.2' -> ('emt', (1, 2)); 'emt' -> ('emt', None)."""
    m = _STEM_VERSION.search(stem)
    if not m or m.start() == 0:
        return stem, None
    version = tuple(int(x) for x in re.split(r"[._]", m.group(1)))
    return stem[: m.start()], version


def normalize_token(text: str) -> str:
    text = _SEPARATORS.sub("_", text.strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def content_key(path: str) -> str:
    """Parent folder path with version marks removed, so '…/AED_v1.2/glb' and '…/AED_v1.4/glb' match."""
    parts = [normalize_token(_SEGMENT_VERSION.sub("", s)) for s in path_segments(path)]
    return "/".join(p for p in parts if p)


@dataclass(frozen=True)
class ParsedName:
    target: str
    variant: str  # "" when none; several joined with "_"
    version: tuple[int, ...] | None


def parse_name(file_name: str, path: str, variant_suffixes: list[str], variant_folders: list[str]) -> ParsedName:
    stem, version = strip_version(split_stem(file_name))
    tokens = normalize_token(stem).split("_")
    suffixes = {s.lower() for s in variant_suffixes}
    found: list[str] = []
    while len(tokens) > 1 and tokens[-1] in suffixes:
        found.insert(0, tokens.pop())
    folders = {f.lower() for f in variant_folders}
    folder_variants = [normalize_token(s) for s in path_segments(path) if s.lower() in folders]
    variant = "_".join(dict.fromkeys(folder_variants + found))
    return ParsedName(target="_".join(tokens), variant=variant, version=version)
