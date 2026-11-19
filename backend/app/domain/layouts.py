from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.core.config import REPO_ROOT

SHARED = REPO_ROOT / "shared"


@lru_cache
def layouts() -> dict[str, Any]:
    return json.loads((SHARED / "layouts" / "layouts.json").read_text(encoding="utf-8"))


@lru_cache
def themes() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted((SHARED / "themes").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result[data["styleKey"]] = data
    return result


def theme(style_key: str) -> dict[str, Any]:
    return themes()[style_key]


def layout_ids() -> list[str]:
    return list(layouts()["layouts"].keys())


def layout(layout_id: str) -> dict[str, Any]:
    return layouts()["layouts"][layout_id]


LAYOUT_ROTATION = ["hero", "three_col", "async", "two_col", "mix", "single"]


def layout_for_page(page_type: str, position: int) -> str:
    if page_type in {"COVER", "TOC", "END"}:
        return "single"
    return LAYOUT_ROTATION[(position - 1) % len(LAYOUT_ROTATION)]


def section_label(layout_id: str, slot_key: str) -> dict[str, Any] | None:
    for slot in layout(layout_id)["slots"]:
        if slot["key"] == slot_key:
            return slot
    return None
