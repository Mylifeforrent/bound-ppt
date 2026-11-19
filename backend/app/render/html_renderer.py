"""Single-file, offline HTML composition with inline CSS only."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from app.render import pipeline


def _block_style(theme: dict[str, Any], block: dict[str, Any]) -> str:
    role = str(block.get("role") or "body")
    style = pipeline.style_for_role(theme, role)
    size = max(8.0, float(style.get("size") or 19))
    weight = int(style.get("weight") or 400)
    color = pipeline.color_for(theme, str(style.get("colorRole") or "text"))
    line_height = float(style.get("lineHeight") or 1.4)
    raw_style = block.get("style") if isinstance(block.get("style"), dict) else {}
    align = str(raw_style.get("align") or ("center" if role in {"headline", "metric", "quote"} else "left"))
    return (
        f"font-size:{size:.0f}px;font-weight:{weight};color:{html.escape(color, quote=True)};"
        f"line-height:{line_height};text-align:{html.escape(align, quote=True)};word-wrap:break-word;"
    )


def _render_block(theme: dict[str, Any], block: dict[str, Any]) -> str:
    role = str(block.get("role") or "body")
    style = _block_style(theme, block)
    items = block.get("items") or []
    if role == "table" and items:
        rows = [[cell.strip() for cell in str(item).split("|")] for item in items]
        columns = max((len(row) for row in rows), default=1)
        head = "".join(f'<col style="width:{100 / max(columns, 1):.4f}%">' for _ in range(columns))
        body = []
        for row in rows:
            cells = "".join(
                f"<td>{html.escape(row[index]) if index < len(row) else ''}</td>"
                for index in range(columns)
            )
            body.append(f"<tr>{cells}</tr>")
        return (
            f'<table style="{style}border-collapse:collapse;width:100%">'
            f"<colgroup>{head}</colgroup><tbody>{''.join(body)}</tbody></table>"
        )
    if items:
        entries = "".join(f"<li>{html.escape(str(item))}</li>" for item in items)
        return f'<ul style="{style}margin:0;padding-left:20px">{entries}</ul>'
    text = html.escape(str(block.get("text") or ""))
    return f'<div style="{style}white-space:pre-wrap">{text}</div>'


def _chrome_html(rect: dict[str, Any], text: str, extra: str) -> str:
    if not text:
        return ""
    style = (
        f"position:absolute;left:{int(rect.get('x', 0))}px;top:{int(rect.get('y', 0))}px;"
        f"width:{int(rect.get('w', 400))}px;height:{int(rect.get('h', 32))}px;"
        f"display:flex;align-items:center;{extra}"
    )
    return f'<div class="chrome" style="{style}">{html.escape(text)}</div>'


CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#e5e7eb;font-family:Inter,Helvetica,Arial,sans-serif}
.deck{display:flex;flex-direction:column;gap:24px;padding:24px;align-items:center}
.slide{position:relative;width:1280px;height:720px;overflow:hidden}
.slot{position:absolute;display:flex;flex-direction:column;gap:8px;padding:8px}
.chrome{font-weight:700}
@media print{
  html,body{background:#ffffff}
  .deck{padding:0;gap:0;display:block}
  .slide{page-break-after:always;break-after:page}
  @page{size:13.333in 7.5in;margin:0}
}
"""


def render_html(input_data: dict[str, Any], output_path: Path) -> dict[str, Any]:
    pages = list(input_data.get("pages") or [])
    theme = input_data.get("theme") or {}
    layout_data = input_data.get("layouts") or {}
    chrome = pipeline.chrome_rects(layout_data)
    background = pipeline.color_for(theme, "background")
    text_color = pipeline.color_for(theme, "text")
    muted = pipeline.color_for(theme, "muted")
    fonts = pipeline.theme_fonts(theme)

    sections: list[str] = []
    for index, page in enumerate(pages):
        body = page.get("body") or {}
        layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))
        parts = [
            f'<section class="slide" style="background:{html.escape(background, quote=True)};'
            f'color:{html.escape(text_color, quote=True)}">'
        ]
        parts.append(
            _chrome_html(
                chrome["title"],
                str(page.get("title") or ""),
                f'font-family:{html.escape(fonts["display"], quote=True)};font-size:18px;',
            )
        )
        parts.append(
            _chrome_html(
                chrome["sectionLabel"],
                str(page.get("sectionLabel") or ""),
                f"font-size:10px;color:{html.escape(muted, quote=True)};font-weight:400;",
            )
        )
        parts.append(
            _chrome_html(
                chrome["pageNumber"],
                str(page.get("pageNumber") or page.get("position") or index + 1),
                f"font-size:10px;color:{html.escape(muted, quote=True)};font-weight:400;"
                "justify-content:flex-end;",
            )
        )
        for slot, blocks in pipeline.blocks_by_slot(body, layout):
            slot_style = (
                f"left:{int(slot.get('x', 80))}px;top:{int(slot.get('y', 112))}px;"
                f"width:{int(slot.get('w', 1120))}px;height:{int(slot.get('h', 472))}px;"
            )
            rendered = "".join(_render_block(theme, block) for block in blocks)
            parts.append(f'<div class="slot" style="{slot_style}">{rendered}</div>')
        parts.append("</section>")
        sections.append("".join(parts))

    document = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        "<title>Bound PPT export</title>"
        f"<style>{CSS}</style></head>"
        f'<body><div class="deck">{"".join(sections)}</div></body></html>'
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError("html_output_missing")
    if "<script" in document.lower():
        raise RuntimeError("html_external_reference")
    return {"pages": len(pages)}
