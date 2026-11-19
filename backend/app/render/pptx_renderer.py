"""PPTX composition with native shapes, text, bullets and tables (python-pptx)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from app.render import pipeline

EMU_PER_PX = 9525
SLIDE_WIDTH = 1280 * EMU_PER_PX
SLIDE_HEIGHT = 720 * EMU_PER_PX
METRIC_PATTERN = re.compile(r"^([\d.,%+$€£-]+)\s*(.*)$")


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


def _apply_numbering(paragraph: Any, start: int) -> None:
    try:
        props = paragraph._p.get_or_add_pPr()
        element = props.makeelement(qn("a:buAutoNum"), {"type": "arabicPeriod", "startAt": str(start)})
        definition = props.find(qn("a:defRPr"))
        if definition is not None:
            definition.addprevious(element)
        else:
            props.append(element)
    except Exception:  # noqa: BLE001
        pass


def _set_hanging_indent(paragraph: Any, indent_px: float = 22.0) -> None:
    try:
        props = paragraph._p.get_or_add_pPr()
        props.set("marL", str(int(indent_px * EMU_PER_PX)))
        props.set("indent", str(-int(indent_px * EMU_PER_PX)))
    except Exception:  # noqa: BLE001
        pass


def _style_text_run(run: Any, *, size_pt: float, bold: bool, color: RGBColor, font: str) -> None:
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.name = pipeline.export_font(font)
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
    line_height: float = 1.4,
    numbered: bool = False,
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
            paragraph.line_spacing = max(0.9, float(line_height))
            paragraph.space_after = Pt(2)
            run = paragraph.add_run()
            run.text = str(item)
            _style_text_run(run, size_pt=size_pt, bold=bold, color=color, font=font)
            _set_hanging_indent(paragraph)
            if numbered:
                _apply_numbering(paragraph, index + 1)
            else:
                _apply_bullet(paragraph)
        return
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = max(0.9, float(line_height))
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = str(text or "")
    _style_text_run(run, size_pt=size_pt, bold=bold, color=color, font=font)


def _add_metric(slide: Any, entry: pipeline.FittedBlock, *, theme: dict[str, Any], font: str) -> None:
    role_style = pipeline.style_for_role(theme, "metric")
    size_pt = max(10.0, entry.size * 0.75)
    value_color = _rgb(pipeline.color_for(theme, str(role_style.get("colorRole") or "primary")))
    caption_color = _rgb(pipeline.color_for(theme, "muted"))
    value, caption = entry.block.get("text") or "", ""
    match = METRIC_PATTERN.match(str(value).strip())
    if match:
        value, caption = match.group(1), match.group(2).strip()
    x, y, w, h = entry.x, entry.y, entry.w, entry.h
    shape = slide.shapes.add_textbox(
        Emu(int(x * EMU_PER_PX)),
        Emu(int(y * EMU_PER_PX)),
        Emu(int(max(w, 24) * EMU_PER_PX)),
        Emu(int(max(h, 24) * EMU_PER_PX)),
    )
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    align = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}.get(entry.align, PP_ALIGN.LEFT)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = 0.95
    run = paragraph.add_run()
    run.text = str(value or entry.block.get("text") or "")
    _style_text_run(run, size_pt=min(70.0, size_pt * 1.3), bold=True, color=value_color, font=font)
    if caption:
        caption_paragraph = frame.add_paragraph()
        caption_paragraph.alignment = align
        caption_paragraph.line_spacing = 1.2
        caption_paragraph.space_before = Pt(6)
        caption_run = caption_paragraph.add_run()
        caption_run.text = caption
        _style_text_run(
            caption_run, size_pt=max(10.0, size_pt * 0.42), bold=False, color=caption_color, font=font
        )


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


def _add_shape(
    slide: Any,
    rect: tuple[float, float, float, float],
    *,
    fill: str,
    line: str | None = None,
    rounded: bool = False,
) -> None:
    x, y, w, h = rect
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Emu(int(x * EMU_PER_PX)),
        Emu(int(y * EMU_PER_PX)),
        Emu(int(max(w, 1) * EMU_PER_PX)),
        Emu(int(max(h, 1) * EMU_PER_PX)),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    if line:
        shape.line.color.rgb = _rgb(line)
        shape.line.width = Pt(1)
        try:
            shape.adjustments[0] = min(0.5, 18.0 / max(1.0, min(w, h)))
        except Exception:  # noqa: BLE001
            pass
    else:
        shape.line.fill.background()
    try:
        shape.shadow.inherit = False
    except Exception:  # noqa: BLE001
        pass


def _add_card(slide: Any, slot: dict[str, Any], theme: dict[str, Any]) -> None:
    tokens = pipeline.theme_tokens(theme)
    line = (
        pipeline.blend(
            pipeline.color_for(theme, "primary"), pipeline.color_for(theme, "background"), 0.16
        )
        if tokens.get("cardBorder", True)
        else None
    )
    _add_shape(
        slide,
        (float(slot.get("x", 80)), float(slot.get("y", 112)), float(slot.get("w", 1120)), float(slot.get("h", 472))),
        fill=pipeline.color_for(theme, "surface"),
        line=line,
        rounded=True,
    )


def _add_card_accent(slide: Any, slot: dict[str, Any], theme: dict[str, Any]) -> None:
    tokens = pipeline.theme_tokens(theme)
    width = float(tokens.get("accentBar") or 6)
    x = float(slot.get("x", 80))
    y = float(slot.get("y", 112)) + 18
    height = max(12.0, float(slot.get("h", 472)) - 36)
    _add_shape(slide, (x, y, width, height), fill=pipeline.color_for(theme, "accent"))


def _add_chrome(
    slide: Any,
    rect: dict[str, Any],
    text: str,
    *,
    size_pt: float,
    color: RGBColor,
    font: str,
    align: PP_ALIGN,
    bold: bool = False,
    uppercase: bool = False,
) -> None:
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
        text=text.upper() if uppercase else text,
        items=None,
        size_pt=size_pt,
        bold=bold,
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
    index: int,
    total: int,
) -> None:
    page_type = pipeline.page_type_of(page, index, total)
    render_theme = pipeline.page_theme(theme, page_type)
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(pipeline.color_for(render_theme, "background"), "#ffffff")

    fonts = {
        key: pipeline.export_font(value) for key, value in pipeline.theme_fonts(render_theme).items()
    }
    text_color = _rgb(pipeline.color_for(render_theme, "text"))
    muted = _rgb(pipeline.color_for(render_theme, "muted"))
    body = page.get("body") or {}
    layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))

    if page_type not in {"COVER", "END"}:
        if not pipeline.has_headline(body):
            _add_chrome(
                slide, chrome["title"], str(page.get("title") or ""), size_pt=12, color=text_color,
                font=fonts["display"], align=PP_ALIGN.LEFT, bold=True, uppercase=True,
            )
        _add_chrome(
            slide, chrome["sectionLabel"], str(page.get("sectionLabel") or ""), size_pt=9, color=muted,
            font=fonts["body"], align=PP_ALIGN.LEFT, uppercase=True,
        )
        _add_chrome(
            slide, chrome["pageNumber"],
            f"{page.get('position') or index + 1} / {total}", size_pt=9, color=muted,
            font=fonts["body"], align=PP_ALIGN.RIGHT,
        )
    else:
        _add_shape(
            slide,
            (0, 0, 1280, 10),
            fill=pipeline.color_for(render_theme, "accent"),
        )
        _add_shape(
            slide,
            (64, 112, 6, 472),
            fill=pipeline.color_for(render_theme, "accent"),
        )
    if page_type == "TOC":
        _add_shape(slide, (64, 112, 6, 472), fill=pipeline.color_for(render_theme, "primary"))

    for slot, blocks in pipeline.blocks_by_slot(body, layout):
        if page_type in {"COVER", "END"}:
            blocks = [block for block in blocks if str(block.get("role") or "") != "footer"]
        slot_key = str(slot.get("key") or "main")
        card = pipeline.is_card_slot(slot_key, page_type)
        entries = pipeline.fit_slot(
            blocks,
            slot,
            render_theme,
            card=card,
            center_vertical=card or page_type in {"COVER", "END"},
        )
        if page_type == "TOC" and slot_key == "main":
            anchor = next(
                (entry for entry in reversed(entries) if entry.role in {"headline", "subhead"}), None
            )
            if anchor:
                _add_shape(
                    slide,
                    (anchor.x, anchor.y + anchor.h + 2, 96, 3),
                    fill=pipeline.color_for(render_theme, "accent"),
                )
        if card:
            _add_card(slide, slot, render_theme)
            _add_card_accent(slide, slot, render_theme)
        if slot_key == "header" and pipeline.theme_tokens(render_theme).get("headingRule"):
            _add_shape(
                slide,
                (float(slot.get("x", 80)), float(slot.get("y", 104)) + float(slot.get("h", 72)) - 4, 96, 3),
                fill=pipeline.color_for(render_theme, "accent"),
            )
        for entry in entries:
            style = pipeline.style_for_role(render_theme, entry.role)
            size_pt = max(8.0, entry.size * 0.75)
            bold = int(style.get("weight") or 400) >= 600 or entry.block.get("emphasis") == "primary"
            color = _rgb(pipeline.color_for(render_theme, str(style.get("colorRole") or "text")))
            align = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}.get(entry.align, PP_ALIGN.LEFT)
            rect = (entry.x, entry.y, entry.w, entry.h)
            if entry.role == "metric":
                _add_metric(slide, entry, theme=render_theme, font=fonts["body"])
            elif entry.role == "table" and entry.block.get("items"):
                _add_table(
                    slide, rect, list(entry.block.get("items") or []), size_pt=size_pt,
                    color=color, font=fonts["body"],
                )
            elif entry.block.get("text") or entry.block.get("items"):
                text_rect = rect
                if entry.role == "quote":
                    _add_shape(slide, (entry.x - 12, entry.y + 2, 4, max(8.0, entry.h - 4)),
                               fill=pipeline.color_for(render_theme, "primary"))
                    text_rect = (entry.x, entry.y, entry.w, entry.h)
                _add_textbox(
                    slide,
                    text_rect,
                    text=entry.block.get("text"),
                    items=list(entry.block.get("items") or []) or None,
                    size_pt=size_pt,
                    bold=bold,
                    color=color,
                    font=fonts["body"],
                    align=align,
                    line_height=entry.line_height,
                    numbered=page_type == "TOC" and entry.role == "bullet_list",
                )


def render_pptx(input_data: dict[str, Any], output_path: Path) -> dict[str, Any]:
    pages = list(input_data.get("pages") or [])
    presentation = Presentation()
    presentation.slide_width = Emu(SLIDE_WIDTH)
    presentation.slide_height = Emu(SLIDE_HEIGHT)
    layout_data = input_data.get("layouts") or {}
    chrome = pipeline.chrome_rects(layout_data)
    theme = input_data.get("theme") or {}
    blank_layout = presentation.slide_layouts[6]
    total = len(pages)

    for index, page in enumerate(pages):
        slide = presentation.slides.add_slide(blank_layout)
        _render_slide(
            slide, page, theme=theme, layout_data=layout_data, chrome=chrome, index=index, total=total
        )

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
    return {"pages": len(slides), "textBlocks": text_blocks}
