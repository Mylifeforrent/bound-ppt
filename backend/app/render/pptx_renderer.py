"""PPTX composition with native shapes, text, bullets and tables (python-pptx)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from app.render import pipeline

EMU_PER_PX = 9525
SLIDE_WIDTH = 1280 * EMU_PER_PX
SLIDE_HEIGHT = 720 * EMU_PER_PX


def _rgb(value: str | None, fallback: str = "#111827") -> RGBColor:
    raw = (value or fallback).lstrip("#")
    if len(raw) == 3:
        raw = "".join(char * 2 for char in raw)
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    try:
        return RGBColor.from_string(raw.upper())
    except ValueError:
        return RGBColor(17, 24, 39)


def _apply_bullet(paragraph: Any) -> None:
    try:
        props = paragraph._p.get_or_add_pPr()
        element = props.makeelement(qn("a:buChar"), {"char": "•"})
        definition = props.find(qn("a:defRPr"))
        if definition is not None:
            definition.addprevious(element)
        else:
            props.append(element)
    except Exception:  # noqa: BLE001 - a missing bullet glyph never fails the export
        pass


def _style_text_run(run: Any, *, size_pt: float, bold: bool, color: RGBColor, font: str) -> None:
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = color


def _add_textbox(
    slide: Any,
    rect: tuple[float, float, float, float],
    *,
    text: str | None,
    items: list[Any] | None,
    size_pt: float,
    bold: bool,
    color: RGBColor,
    font: str,
    align: PP_ALIGN = PP_ALIGN.LEFT,
) -> None:
    x, y, w, h = rect
    shape = slide.shapes.add_textbox(
        Emu(int(x * EMU_PER_PX)),
        Emu(int(y * EMU_PER_PX)),
        Emu(int(max(w, 24) * EMU_PER_PX)),
        Emu(int(max(h, 20) * EMU_PER_PX)),
    )
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    if items:
        for index, item in enumerate(items):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.alignment = align
            paragraph.space_after = Pt(4)
            run = paragraph.add_run()
            run.text = str(item)
            _style_text_run(run, size_pt=size_pt, bold=bold, color=color, font=font)
            _apply_bullet(paragraph)
        return
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = str(text or "")
    _style_text_run(run, size_pt=size_pt, bold=bold, color=color, font=font)


def _add_table(
    slide: Any,
    rect: tuple[float, float, float, float],
    items: list[Any],
    *,
    size_pt: float,
    color: RGBColor,
    font: str,
) -> None:
    rows = [[cell.strip() for cell in str(item).split("|")] for item in items]
    if not rows:
        return
    columns = max(len(row) for row in rows)
    x, y, w, h = rect
    row_height = max(22.0, size_pt * 1.5)
    shape = slide.shapes.add_table(
        len(rows),
        columns,
        Emu(int(x * EMU_PER_PX)),
        Emu(int(y * EMU_PER_PX)),
        Emu(int(max(w, 40) * EMU_PER_PX)),
        Emu(int(max(row_height, min(h, row_height * len(rows))) * EMU_PER_PX)),
    )
    table = shape.table
    for row_index, row in enumerate(rows):
        for column_index in range(columns):
            cell = table.cell(row_index, column_index)
            cell.text = row[column_index] if column_index < len(row) else ""
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    _style_text_run(
                        run, size_pt=max(8.0, size_pt - 2), bold=False, color=color, font=font
                    )


def _add_chrome(slide: Any, rect: dict[str, Any], text: str, *, size_pt: float, color: RGBColor, font: str, align: PP_ALIGN) -> None:
    if not text:
        return
    _add_textbox(
        slide,
        (
            float(rect.get("x", 0)),
            float(rect.get("y", 0)),
            float(rect.get("w", 400)),
            float(rect.get("h", 32)),
        ),
        text=text,
        items=None,
        size_pt=size_pt,
        bold=True,
        color=color,
        font=font,
        align=align,
    )


def _render_slide(
    slide: Any,
    page: dict[str, Any],
    *,
    theme: dict[str, Any],
    layout_data: dict[str, Any],
    chrome: dict[str, dict[str, int]],
) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(pipeline.color_for(theme, "background"), "#ffffff")

    fonts = pipeline.theme_fonts(theme)
    text_color = _rgb(pipeline.color_for(theme, "text"))
    muted = _rgb(pipeline.color_for(theme, "muted"))
    body = page.get("body") or {}
    layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))

    _add_chrome(
        slide,
        chrome["title"],
        str(page.get("title") or body.get("meta", {}).get("title") or ""),
        size_pt=18,
        color=text_color,
        font=fonts["display"],
        align=PP_ALIGN.LEFT,
    )
    _add_chrome(
        slide,
        chrome["sectionLabel"],
        str(page.get("sectionLabel") or ""),
        size_pt=10,
        color=muted,
        font=fonts["body"],
        align=PP_ALIGN.LEFT,
    )
    _add_chrome(
        slide,
        chrome["pageNumber"],
        str(page.get("pageNumber") or page.get("position") or ""),
        size_pt=10,
        color=muted,
        font=fonts["body"],
        align=PP_ALIGN.RIGHT,
    )

    for slot, blocks in pipeline.blocks_by_slot(body, layout):
        slot_x = float(slot.get("x", 80))
        slot_y = float(slot.get("y", 112))
        slot_w = float(slot.get("w", 1120))
        slot_h = float(slot.get("h", 472))
        cursor = slot_y + 4
        for block in blocks:
            height = min(
                pipeline.block_height(block, slot_w - 16, theme),
                max(24.0, slot_y + slot_h - cursor),
            )
            role = str(block.get("role") or "body")
            style = pipeline.style_for_role(theme, role)
            size_pt = max(8.0, float(style.get("size") or 19) * 0.75)
            bold = int(style.get("weight") or 400) >= 600 or block.get("emphasis") == "primary"
            color = _rgb(pipeline.color_for(theme, str(style.get("colorRole") or "text")))
            align = PP_ALIGN.LEFT
            raw_style = block.get("style") if isinstance(block.get("style"), dict) else {}
            if raw_style.get("align") == "center":
                align = PP_ALIGN.CENTER
            elif raw_style.get("align") == "right":
                align = PP_ALIGN.RIGHT
            elif role in {"headline", "metric", "quote"}:
                align = PP_ALIGN.CENTER
            rect = (slot_x + 8, cursor, slot_w - 16, height)
            if role == "table" and block.get("items"):
                _add_table(
                    slide,
                    rect,
                    list(block.get("items") or []),
                    size_pt=size_pt,
                    color=color,
                    font=fonts["body"],
                )
            elif block.get("text") or block.get("items"):
                _add_textbox(
                    slide,
                    rect,
                    text=block.get("text"),
                    items=list(block.get("items") or []) or None,
                    size_pt=size_pt,
                    bold=bold,
                    color=color,
                    font=fonts["body"],
                    align=align,
                )
            cursor += height + 8


def render_pptx(input_data: dict[str, Any], output_path: Path) -> dict[str, Any]:
    pages = list(input_data.get("pages") or [])
    presentation = Presentation()
    presentation.slide_width = Emu(SLIDE_WIDTH)
    presentation.slide_height = Emu(SLIDE_HEIGHT)
    layout_data = input_data.get("layouts") or {}
    chrome = pipeline.chrome_rects(layout_data)
    theme = input_data.get("theme") or {}
    blank_layout = presentation.slide_layouts[6]

    for page in pages:
        slide = presentation.slides.add_slide(blank_layout)
        _render_slide(slide, page, theme=theme, layout_data=layout_data, chrome=chrome)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(output_path))

    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError("pptx_output_missing")
    reopened = Presentation(str(output_path))
    slides = list(reopened.slides)
    if len(slides) != len(pages):
        raise RuntimeError("pptx_slide_count_mismatch")
    text_blocks = 0
    for index, slide in enumerate(slides):
        slide_text = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                slide_text.append(shape.text_frame.text.strip())
                text_blocks += 1
        if not slide_text:
            raise RuntimeError(f"pptx_slide_{index}_empty")
        if len(slide_text) < 1:
            raise RuntimeError(f"pptx_slide_{index}_missing_text")
    return {"pages": len(slides), "textBlocks": text_blocks}
