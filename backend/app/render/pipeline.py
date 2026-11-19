"""Render pipeline shared pieces: layout math, dispatch and subprocess contract."""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT

OUTPUT_NAMES: dict[str, str] = {
    "PPTX": "deck.pptx",
    "HTML": "deck.html",
    "PDF": "deck.pdf",
}
MIME_TYPES: dict[str, str] = {
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "HTML": "text/html",
    "PDF": "application/pdf",
}

DEFAULT_SLOT = {"key": "main", "x": 80, "y": 112, "w": 1120, "h": 472, "roles": []}
DEFAULT_CHROME = {
    "title": {"x": 64, "y": 32, "w": 900, "h": 48},
    "sectionLabel": {"x": 64, "y": 660, "w": 420, "h": 28},
    "pageNumber": {"x": 1120, "y": 656, "w": 96, "h": 32},
}


class ExportRenderError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def output_name(fmt: str) -> str:
    return OUTPUT_NAMES[(fmt or "").upper()]


def resolve_layout(layouts_data: dict[str, Any] | None, layout_id: str | None) -> dict[str, Any]:
    layouts = (layouts_data or {}).get("layouts") or {}
    spec = layouts.get(str(layout_id or "")) or layouts.get("single")
    if spec is None:
        spec = {"slots": [dict(DEFAULT_SLOT)]}
    return spec


def chrome_rects(layouts_data: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    chrome = (layouts_data or {}).get("chrome") or {}
    return {
        key: {**DEFAULT_CHROME[key], **dict(chrome.get(key) or {})}
        for key in DEFAULT_CHROME
    }


def theme_text_styles(theme: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    styles = (theme or {}).get("textStyles") or {}
    return {str(key): dict(value) for key, value in styles.items() if isinstance(value, dict)}


def style_for_role(theme: dict[str, Any] | None, role: str) -> dict[str, Any]:
    styles = theme_text_styles(theme)
    return styles.get(role) or styles.get("body") or {
        "size": 19,
        "weight": 400,
        "colorRole": "text",
        "lineHeight": 1.5,
    }


def palette(theme: dict[str, Any] | None) -> dict[str, str]:
    raw = (theme or {}).get("palette") or {}
    return {str(key): str(value) for key, value in raw.items()}


def color_for(theme: dict[str, Any] | None, role: str) -> str:
    values = palette(theme)
    fallback = {
        "primary": "primary",
        "secondary": "secondary",
        "accent": "accent",
        "muted": "muted",
        "surface": "surface",
        "background": "background",
        "text": "text",
    }.get(role, role)
    return values.get(role) or values.get(fallback) or values.get("text") or "#111827"


def theme_fonts(theme: dict[str, Any] | None) -> dict[str, str]:
    raw = (theme or {}).get("fonts") or {}
    return {
        "display": str(raw.get("display") or "Arial"),
        "body": str(raw.get("body") or raw.get("display") or "Arial"),
    }


def slot_map(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    slots = layout.get("slots") or []
    return {str(slot.get("key")): dict(slot) for slot in slots if isinstance(slot, dict)}


def blocks_by_slot(body: dict[str, Any], layout: dict[str, Any]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    slots = slot_map(layout)
    first_key = next(iter(slots), DEFAULT_SLOT["key"])
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in slots}
    for block in body.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        slot_key = str(block.get("slot") or first_key)
        if slot_key not in grouped:
            slot_key = first_key
        grouped[slot_key].append(block)
    return [(slots[key], blocks) for key, blocks in grouped.items() if blocks]


def wrap_lines(text: str, width_px: float, font_px: float) -> int:
    per_line = max(8, int(width_px / max(1.0, font_px * 0.55)))
    total = 0
    for raw in str(text).split("\n"):
        total += max(1, math.ceil(len(raw) / per_line))
    return total


def block_height(block: dict[str, Any], width_px: float, theme: dict[str, Any] | None) -> float:
    style = style_for_role(theme, str(block.get("role") or "body"))
    size = float(style.get("size") or 19)
    line_height = float(style.get("lineHeight") or 1.4)
    role = str(block.get("role") or "body")
    if role == "table":
        rows = len(block.get("items") or []) or 1
        return max(40.0, rows * (size * 1.1 + 10))
    items = block.get("items")
    if items:
        lines = sum(wrap_lines(str(item), width_px, size) for item in items)
        return max(36.0, lines * size * line_height + 10)
    lines = wrap_lines(str(block.get("text") or ""), width_px, size)
    return max(24.0, lines * size * line_height + 8)


# ---- Theme and slot composition -------------------------------------------

FONT_SUBSTITUTIONS = {"Inter": "Arial", "Inter Display": "Arial"}
CARD_SLOTS = {
    "main",
    "left",
    "right",
    "col1",
    "col2",
    "col3",
    "support1",
    "support2",
    "support3",
    "primary",
    "secondary",
    "stat1",
    "stat2",
    "body",
    "callout",
}
FIXED_PAGE_TYPES = {"COVER", "TOC", "END"}


def export_font(name: str) -> str:
    return FONT_SUBSTITUTIONS.get(name, name)


def _hex(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except (ValueError, IndexError):
        return (17, 24, 39)


def blend(color: str, background: str, ratio: float) -> str:
    """Mix `color` into `background`; ratio 0 = background, 1 = color."""
    ratio = max(0.0, min(1.0, ratio))
    fr, fg, fb = _hex(color)
    br, bg, bb = _hex(background)
    red = int(round(fr * ratio + br * (1 - ratio)))
    green = int(round(fg * ratio + bg * (1 - ratio)))
    blue = int(round(fb * ratio + bb * (1 - ratio)))
    return f"#{red:02x}{green:02x}{blue:02x}"


def tint(color: str, ratio: float = 0.75) -> str:
    return blend("#ffffff", color, ratio)


def theme_tokens(theme: dict[str, Any] | None) -> dict[str, Any]:
    return dict((theme or {}).get("tokens") or {})


def page_type_of(page: dict[str, Any], index: int, total: int) -> str:
    explicit = str(page.get("pageType") or "").upper()
    if explicit in FIXED_PAGE_TYPES or explicit == "BODY":
        return explicit
    if index == 0:
        return "COVER"
    if index == 1:
        return "TOC"
    if index == total - 1:
        return "END"
    return "BODY"


def page_theme(theme: dict[str, Any] | None, page_type: str) -> dict[str, Any]:
    """Return the theme with a cover/end palette override; other pages are unchanged."""
    base = dict(theme or {})
    if page_type not in {"COVER", "END"}:
        return base
    palette = dict(base.get("palette") or {})
    secondary = str(palette.get("secondary") or "#1f2937")
    primary = str(palette.get("primary") or "#4f46e5")
    accent = str(palette.get("accent") or "#f59e0b")
    palette.update(
        {
            "background": secondary,
            "text": "#ffffff",
            "primary": tint(primary, 0.7),
            "secondary": "#ffffff",
            "accent": accent,
            "muted": blend(primary, "#ffffff", 0.55),
            "surface": secondary,
        }
    )
    return {**base, "palette": palette}


def is_card_slot(slot_key: str, page_type: str) -> bool:
    if page_type in {"COVER", "TOC", "END"}:
        return False
    return slot_key in CARD_SLOTS


def has_headline(body: dict[str, Any]) -> bool:
    return any(
        isinstance(block, dict) and str(block.get("role") or "") == "headline"
        for block in body.get("blocks") or []
    )


def _block_alignment(block: dict[str, Any]) -> str:
    raw = block.get("style") if isinstance(block.get("style"), dict) else {}
    align = str(raw.get("align") or "")
    return align if align in {"left", "center", "right"} else "left"


@dataclass
class FittedBlock:
    block: dict[str, Any]
    x: float
    y: float
    w: float
    h: float
    size: float
    line_height: float
    align: str
    role: str


def _natural_height(block: dict[str, Any], width_px: float, size: float, theme: dict[str, Any]) -> float:
    role = str(block.get("role") or "body")
    line_height = float(style_for_role(theme, role).get("lineHeight") or 1.4)
    if role == "table":
        rows = len(block.get("items") or []) or 1
        return max(40.0, rows * (size * 1.1 + 10))
    items = block.get("items")
    if items:
        lines = sum(wrap_lines(str(item), width_px, size) for item in items)
        return max(36.0, lines * size * line_height + 12)
    lines = wrap_lines(str(block.get("text") or ""), width_px, size)
    return max(24.0, lines * size * line_height + 8)


def fit_slot(
    blocks: list[dict[str, Any]],
    slot: dict[str, Any],
    theme: dict[str, Any],
    *,
    card: bool,
    min_size: float = 10.0,
    center_vertical: bool = False,
) -> list[FittedBlock]:
    """Lay a slot's blocks out top-to-bottom, shrinking type until it fits.

    The previous renderers clamped each box to the remaining slot height while
    keeping the theme font size, so long text visually overflowed into the next
    block. This fitter keeps every box inside the slot and never lets boxes
    overlap: type is scaled down first, then gaps close.
    """
    if not blocks:
        return []
    inset_x = 24.0 if card else 4.0
    inset_y = 20.0 if card else 4.0
    slot_x = float(slot.get("x", 80))
    slot_y = float(slot.get("y", 112))
    slot_w = float(slot.get("w", 1120))
    slot_h = float(slot.get("h", 472))
    left = slot_x + inset_x
    top = slot_y + inset_y
    width = max(32.0, slot_w - 2 * inset_x)
    available = max(24.0, slot_h - 2 * inset_y)

    base_sizes = [max(min_size, float(style_for_role(theme, str(b.get("role") or "body")).get("size") or 19)) for b in blocks]
    line_heights = [
        float(style_for_role(theme, str(b.get("role") or "body")).get("lineHeight") or 1.4) for b in blocks
    ]
    gap = 12.0 if card else 8.0
    scale = 1.0
    sizes = list(base_sizes)
    heights = [_natural_height(b, width, s, theme) for b, s in zip(blocks, sizes, strict=False)]
    total = sum(heights) + gap * (len(blocks) - 1)
    for _ in range(6):
        if total <= available:
            break
        ratio = available / total
        lower_bound = min_size / max(base_sizes)
        scale = max(lower_bound, scale * ratio * 0.98)
        sizes = [max(min_size, base * scale) for base in base_sizes]
        heights = [_natural_height(b, width, s, theme) for b, s in zip(blocks, sizes, strict=False)]
        total = sum(heights) + gap * (len(blocks) - 1)
    if total > available:
        gap = max(2.0, gap * 0.5)
        total = sum(heights) + gap * (len(blocks) - 1)
    if total > available:
        # Last resort: distribute the available height proportionally so boxes
        # remain disjoint; the viewer clips rather than overlaps.
        factor = available / total
        heights = [max(12.0, h * factor) for h in heights]

    entries: list[FittedBlock] = []
    cursor = top
    for block, size, height, line_height in zip(blocks, sizes, heights, line_heights, strict=False):
        remaining = max(12.0, top + available - cursor)
        height = min(height, remaining)
        entries.append(
            FittedBlock(
                block=block,
                x=left,
                y=cursor,
                w=width,
                h=height,
                size=size,
                line_height=line_height,
                align=_block_alignment(block),
                role=str(block.get("role") or "body"),
            )
        )
        cursor += height + gap
    if center_vertical and entries:
        content_height = entries[-1].y + entries[-1].h - top
        offset = max(0.0, (available - content_height) / 2)
        if offset:
            entries = [
                FittedBlock(
                    block=entry.block,
                    x=entry.x,
                    y=entry.y + offset,
                    w=entry.w,
                    h=entry.h,
                    size=entry.size,
                    line_height=entry.line_height,
                    align=entry.align,
                    role=entry.role,
                )
                for entry in entries
            ]
    return entries


def body_text(body: dict[str, Any]) -> str:
    chunks: list[str] = []
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    if meta.get("title"):
        chunks.append(str(meta["title"]))
    for block in body.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if block.get("text"):
            chunks.append(str(block["text"]))
        for item in block.get("items") or []:
            chunks.append(str(item))
    return "\n".join(chunks).strip()


def render_document(input_data: dict[str, Any], output_path: Path, fmt: str) -> dict[str, Any]:
    value = (fmt or input_data.get("format") or "").upper()
    if value == "PPTX":
        from app.render.pptx_renderer import render_pptx

        return render_pptx(input_data, output_path)
    if value == "HTML":
        from app.render.html_renderer import render_html

        return render_html(input_data, output_path)
    if value == "PDF":
        from app.render.pdf_renderer import render_pdf

        return render_pdf(input_data, output_path)
    raise ValueError(f"unknown format: {fmt}")


async def run_render_subprocess(
    input_data: dict[str, Any], fmt: str, timeout_seconds: float
) -> tuple[bytes, str]:
    """Run the renderer in an isolated subprocess and return (bytes, file_name)."""
    workdir = Path(tempfile.mkdtemp(prefix="bound-ppt-render-"))
    try:
        input_path = workdir / "input.json"
        input_path.write_text(json.dumps(input_data, ensure_ascii=False), encoding="utf-8")
        # The renderer needs no database URLs, provider keys, or bucket credentials.
        child_env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")
            if key in os.environ
        }
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.render.export_runner",
            "--input",
            str(input_path),
            "--output",
            str(workdir),
            "--format",
            fmt,
            cwd=str(REPO_ROOT / "backend"),
            env=child_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ExportRenderError("render_timeout") from exc
        if process.returncode != 0:
            raise ExportRenderError(f"render_exit_{process.returncode}")
        path = workdir / output_name(fmt)
        if not path.is_file() or path.stat().st_size <= 0:
            raise ExportRenderError("render_missing_output")
        return path.read_bytes(), path.name
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
