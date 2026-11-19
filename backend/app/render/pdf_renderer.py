"""PDF composition with reportlab at a 960x540pt 16:9 page size."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors as pdf_colors
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Table, TableStyle

from app.render import pipeline

PAGE_WIDTH = 960
PAGE_HEIGHT = 540
PX_TO_PT = 0.75
METRIC_PATTERN = re.compile(r"^([\d.,%+$€£-]+)\s*(.*)$")


def _color(value: str | None, fallback: str = "#111827") -> Any:
    raw = value or fallback
    try:
        return pdf_colors.HexColor(raw if raw.startswith("#") else f"#{raw}")
    except Exception:  # noqa: BLE001
        return pdf_colors.HexColor(fallback)


def _wrap(text: str, width_pt: float, font: str, size: float) -> list[str]:
    lines: list[str] = []
    for raw in str(text).split("\n"):
        lines.extend(simpleSplit(raw, font, size, max(width_pt, 24)))
    return lines or [""]


def _draw_lines(
    painter: Any,
    lines: list[str],
    *,
    x_pt: float,
    top_pt: float,
    width_pt: float,
    size: float,
    font: str,
    color: Any,
    align: str,
    bottom_limit: float,
    line_height: float = 1.35,
) -> None:
    line_height_pt = size * max(0.9, line_height)
    cursor = top_pt
    painter.setFont(font, size)
    painter.setFillColor(color)
    for line in lines:
        if cursor - line_height_pt < bottom_limit:
            break
        baseline = cursor - line_height_pt * 0.78
        if align == "center":
            start = x_pt + max(0.0, (width_pt - stringWidth(line, font, size)) / 2)
        elif align == "right":
            start = x_pt + max(0.0, width_pt - stringWidth(line, font, size))
        else:
            start = x_pt
        painter.drawString(start, baseline, line)
        cursor -= line_height_pt


def _rect_pt(rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x, y, w, h = rect
    return x * PX_TO_PT, PAGE_HEIGHT - (y + h) * PX_TO_PT, w * PX_TO_PT, h * PX_TO_PT


def _draw_card(painter: Any, slot: dict[str, Any], theme: dict[str, Any]) -> None:
    tokens = pipeline.theme_tokens(theme)
    x, y, w, h = _rect_pt(
        (float(slot.get("x", 80)), float(slot.get("y", 112)), float(slot.get("w", 1120)), float(slot.get("h", 472)))
    )
    radius = float(tokens.get("radius") or 18) * PX_TO_PT
    painter.setFillColor(_color(pipeline.color_for(theme, "surface")))
    if tokens.get("cardBorder", True):
        painter.setStrokeColor(
            _color(pipeline.blend(pipeline.color_for(theme, "primary"), pipeline.color_for(theme, "background"), 0.16))
        )
        painter.setLineWidth(0.75)
        painter.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    else:
        painter.roundRect(x, y, w, h, radius, fill=1, stroke=0)


def _draw_shape(painter: Any, rect: tuple[float, float, float, float], color: str) -> None:
    x, y, w, h = _rect_pt(rect)
    painter.setFillColor(_color(color))
    painter.rect(x, y, w, h, fill=1, stroke=0)


def _draw_metric(painter: Any, entry: pipeline.FittedBlock, theme: dict[str, Any]) -> None:
    style = pipeline.style_for_role(theme, "metric")
    size = max(8.0, entry.size * PX_TO_PT)
    color = _color(pipeline.color_for(theme, str(style.get("colorRole") or "primary")))
    muted = _color(pipeline.color_for(theme, "muted"))
    raw = str(entry.block.get("text") or "")
    match = METRIC_PATTERN.match(raw.strip())
    value, caption = (match.group(1), match.group(2).strip()) if match else (raw, "")
    x_pt, _y_pt, _w_pt, _h_pt = _rect_pt((entry.x, entry.y, entry.w, entry.h))
    width_pt = max(24.0, (entry.w - 8) * PX_TO_PT)
    top_pt = PAGE_HEIGHT - (entry.y + 8) * PX_TO_PT
    bottom_limit = PAGE_HEIGHT - (entry.y + entry.h - 4) * PX_TO_PT
    value_size = min(52.0, size * 1.3)
    _draw_lines(
        painter, _wrap(value, width_pt, "Helvetica-Bold", value_size),
        x_pt=x_pt, top_pt=top_pt, width_pt=width_pt, size=value_size, font="Helvetica-Bold",
        color=color, align=entry.align, bottom_limit=bottom_limit, line_height=0.95,
    )
    if caption:
        caption_size = max(8.0, size * 0.42)
        caption_top = top_pt - value_size * 1.5
        _draw_lines(
            painter, _wrap(caption, width_pt, "Helvetica", caption_size),
            x_pt=x_pt, top_pt=caption_top, width_pt=width_pt, size=caption_size, font="Helvetica",
            color=muted, align=entry.align, bottom_limit=bottom_limit, line_height=1.25,
        )


def _draw_block(painter: Any, entry: pipeline.FittedBlock, *, theme: dict[str, Any], toc: bool) -> None:
    block = entry.block
    role = entry.role
    style = pipeline.style_for_role(theme, role)
    size = max(6.0, entry.size * PX_TO_PT)
    bold = int(style.get("weight") or 400) >= 600 or block.get("emphasis") == "primary"
    font = "Helvetica-Bold" if bold else "Helvetica"
    color = _color(pipeline.color_for(theme, str(style.get("colorRole") or "text")))
    x_pt = entry.x * PX_TO_PT
    width_pt = max(24.0, (entry.w - 8) * PX_TO_PT)
    top_pt = PAGE_HEIGHT - (entry.y + 6) * PX_TO_PT
    bottom_limit = PAGE_HEIGHT - (entry.y + entry.h) * PX_TO_PT

    if role == "metric":
        _draw_metric(painter, entry, theme)
        return
    if role == "table" and block.get("items"):
        rows = [[cell.strip() for cell in str(item).split("|")] for item in block.get("items") or []]
        if not rows:
            return
        columns = max(len(row) for row in rows)
        data = [[row[index] if index < len(row) else "" for index in range(columns)] for row in rows]
        column_width = width_pt / columns
        table = Table(
            data,
            colWidths=[column_width] * columns,
            rowHeights=[max(14.0, size * 1.6)] * len(data),
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, _color(pipeline.color_for(theme, "muted"), "#566079")),
                    ("FONT", (0, 0), (-1, -1), "Helvetica", max(6.0, size - 1)),
                    ("TEXTCOLOR", (0, 0), (-1, -1), color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        _width, height = table.wrapOn(painter, width_pt, max(20.0, entry.h * PX_TO_PT))
        table.drawOn(painter, x_pt, max(bottom_limit, top_pt - height))
        return

    items = block.get("items")
    if items:
        lines: list[str] = []
        for index, item in enumerate(items):
            prefix = f"{index + 1}. " if toc else "• "
            lines.extend(_wrap(f"{prefix}{item}", width_pt, font, size))
    else:
        lines = _wrap(str(block.get("text") or ""), width_pt, font, size)
    if not lines or not "".join(lines).strip():
        return
    _draw_lines(
        painter,
        lines,
        x_pt=x_pt,
        top_pt=top_pt,
        width_pt=width_pt,
        size=size,
        font=font,
        color=color,
        align=entry.align,
        bottom_limit=bottom_limit,
        line_height=entry.line_height,
    )


def _draw_chrome(
    painter: Any,
    rect: dict[str, Any],
    text: str,
    *,
    size: float,
    bold: bool,
    color: Any,
    align: str,
) -> None:
    if not text:
        return
    x = float(rect.get("x", 0)) * PX_TO_PT
    y = float(rect.get("y", 0)) * PX_TO_PT
    w = float(rect.get("w", 400)) * PX_TO_PT
    h = float(rect.get("h", 32)) * PX_TO_PT
    font = "Helvetica-Bold" if bold else "Helvetica"
    painter.setFont(font, size)
    painter.setFillColor(color)
    text_width = stringWidth(text, font, size)
    baseline = PAGE_HEIGHT - y - h * 0.7
    if align == "center":
        painter.drawString(x + (w - text_width) / 2, baseline, text)
    elif align == "right":
        painter.drawString(x + w - text_width, baseline, text)
    else:
        painter.drawString(x, baseline, text)


def render_pdf(input_data: dict[str, Any], output_path: Path) -> dict[str, Any]:
    pages = list(input_data.get("pages") or [])
    theme = input_data.get("theme") or {}
    layout_data = input_data.get("layouts") or {}
    chrome = pipeline.chrome_rects(layout_data)
    total = len(pages)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    painter = pdf_canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    painter.setTitle("Bound PPT export")

    for index, page in enumerate(pages):
        body = page.get("body") or {}
        page_type = pipeline.page_type_of(page, index, total)
        page_theme = pipeline.page_theme(theme, page_type)
        layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))
        background = _color(pipeline.color_for(page_theme, "background"), "#ffffff")
        text_color = _color(pipeline.color_for(page_theme, "text"))
        muted = _color(pipeline.color_for(page_theme, "muted"))

        painter.setFillColor(background)
        painter.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)

        if page_type not in {"COVER", "END"}:
            if not pipeline.has_headline(body):
                _draw_chrome(
                    painter, chrome["title"], str(page.get("title") or ""),
                    size=9, bold=True, color=text_color, align="left",
                )
            _draw_chrome(
                painter, chrome["sectionLabel"], str(page.get("sectionLabel") or "").upper(),
                size=7, bold=False, color=muted, align="left",
            )
            _draw_chrome(
                painter, chrome["pageNumber"], f"{page.get('position') or index + 1} / {total}",
                size=7, bold=False, color=muted, align="right",
            )
        else:
            _draw_shape(painter, (0, 0, 1280, 10), pipeline.color_for(page_theme, "accent"))
            _draw_shape(painter, (64, 112, 6, 472), pipeline.color_for(page_theme, "accent"))
        if page_type == "TOC":
            _draw_shape(painter, (64, 112, 6, 472), pipeline.color_for(page_theme, "primary"))

        for slot, blocks in pipeline.blocks_by_slot(body, layout):
            if page_type in {"COVER", "END"}:
                blocks = [block for block in blocks if str(block.get("role") or "") != "footer"]
            slot_key = str(slot.get("key") or "main")
            card = pipeline.is_card_slot(slot_key, page_type)
            entries = pipeline.fit_slot(
                blocks,
                slot,
                page_theme,
                card=card,
                center_vertical=card or page_type in {"COVER", "END"},
            )
            if page_type == "TOC" and slot_key == "main":
                anchor = next(
                    (entry for entry in reversed(entries) if entry.role in {"headline", "subhead"}), None
                )
                if anchor:
                    _draw_shape(
                        painter,
                        (anchor.x, anchor.y + anchor.h + 2, 96, 3),
                        pipeline.color_for(page_theme, "accent"),
                    )
            if card:
                _draw_card(painter, slot, page_theme)
                _draw_shape(
                    painter,
                    (
                        float(slot.get("x", 80)),
                        float(slot.get("y", 112)) + 18,
                        float(pipeline.theme_tokens(page_theme).get("accentBar") or 6),
                        max(12.0, float(slot.get("h", 472)) - 36),
                    ),
                    pipeline.color_for(page_theme, "accent"),
                )
            if slot_key == "header" and pipeline.theme_tokens(page_theme).get("headingRule"):
                _draw_shape(
                    painter,
                    (
                        float(slot.get("x", 80)),
                        float(slot.get("y", 104)) + float(slot.get("h", 72)) - 4,
                        96,
                        3,
                    ),
                    pipeline.color_for(page_theme, "accent"),
                )
            for entry in entries:
                if entry.role == "quote":
                    _draw_shape(
                        painter,
                        (entry.x - 12, entry.y + 2, 4, max(8.0, entry.h - 4)),
                        pipeline.color_for(page_theme, "primary"),
                    )
                _draw_block(painter, entry, theme=page_theme, toc=page_type == "TOC" and entry.role == "bullet_list")
        painter.showPage()

    painter.save()
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError("pdf_output_missing")
    with output_path.open("rb") as handle:
        header = handle.read(5)
    if header != b"%PDF-":
        raise RuntimeError("pdf_invalid_header")
    return {"pages": len(pages)}
