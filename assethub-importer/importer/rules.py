"""Selection and duplicate / revision / variant decisions (SPEC 규칙 1-2)."""
from __future__ import annotations

DECISIONS = (
    "register",
    "skip-existing",
    "skip-duplicate",
    "skip-older",
    "skip-excluded",
    "too-large",
)
