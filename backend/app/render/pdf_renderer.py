"""PDF composition with reportlab at a 960x540pt 16:9 page size."""

from __future__ import annotations

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
) -> None:
    line_height = size * 1.35
    cursor = top_pt
    painter.setFont(font, size)
    painter.setFillColor(color)
    for line in lines:
        if cursor - line_height < bottom_limit:
            break
        baseline = cursor - line_height * 0.78
        if align == "center":
            start = x_pt + max(0.0, (width_pt - stringWidth(line, font, size)) / 2)
        elif align == "right":
            start = x_pt + max(0.0, width_pt - stringWidth(line, font, size))
        else:
            start = x_pt
        painter.drawString(start, baseline, line)
        cursor -= line_height


def _draw_block(
    painter: Any,
    block: dict[str, Any],
    rect: tuple[float, float, float, float],
    *,
    theme: dict[str, Any],
) -> None:
    x, y, w, h = rect
    role = str(block.get("role") or "body")
    style = pipeline.style_for_role(theme, role)
    size = max(6.0, float(style.get("size") or 19) * PX_TO_PT)
    bold = int(style.get("weight") or 400) >= 600 or block.get("emphasis") == "primary"
    font = "Helvetica-Bold" if bold else "Helvetica"
    color = _color(pipeline.color_for(theme, str(style.get("colorRole") or "text")))
    raw_style = block.get("style") if isinstance(block.get("style"), dict) else {}
    align = str(raw_style.get("align") or ("center" if role in {"headline", "metric", "quote"} else "left"))
    x_pt = x * PX_TO_PT
    width_pt = max(24.0, (w - 16) * PX_TO_PT)
    top_pt = PAGE_HEIGHT - (y + 6) * PX_TO_PT
    bottom_limit = PAGE_HEIGHT - (y + h) * PX_TO_PT

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
        _width, height = table.wrapOn(painter, width_pt, max(20.0, h * PX_TO_PT))
        table.drawOn(painter, x_pt, max(bottom_limit, top_pt - height))
        return

    items = block.get("items")
    if items:
        lines: list[str] = []
        for item in items:
            wrapped = _wrap(f"• {item}", width_pt, font, size)
            lines.extend(wrapped)
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
        align=align,
        bottom_limit=bottom_limit,
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
    background = _color(pipeline.color_for(theme, "background"), "#ffffff")
    text_color = _color(pipeline.color_for(theme, "text"))
    muted = _color(pipeline.color_for(theme, "muted"), "#566079")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    painter = pdf_canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    painter.setTitle("Bound PPT export")

    for page in pages:
        painter.setFillColor(background)
        painter.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        body = page.get("body") or {}
        layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))

        _draw_chrome(
            painter,
            chrome["title"],
            str(page.get("title") or ""),
            size=13,
            bold=True,
            color=text_color,
            align="left",
        )
        _draw_chrome(
            painter,
            chrome["sectionLabel"],
            str(page.get("sectionLabel") or ""),
            size=8,
            bold=False,
            color=muted,
            align="left",
        )
        _draw_chrome(
            painter,
            chrome["pageNumber"],
            str(page.get("pageNumber") or page.get("position") or ""),
            size=8,
            bold=False,
            color=muted,
            align="right",
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
                _draw_block(painter, block, (slot_x + 8, cursor, slot_w, height), theme=theme)
                cursor += height + 8
        painter.showPage()

    painter.save()
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError("pdf_output_missing")
    with output_path.open("rb") as handle:
        header = handle.read(5)
    if header != b"%PDF-":
        raise RuntimeError("pdf_invalid_header")
    return {"pages": len(pages)}
