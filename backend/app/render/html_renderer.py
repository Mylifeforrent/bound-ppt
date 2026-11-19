"""Single-file, offline HTML composition with inline CSS only."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from app.render import pipeline

METRIC_PATTERN = re.compile(r"^([\d.,%+$€£-]+)\s*(.*)$")


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _block_colors(theme: dict[str, Any], block: dict[str, Any]) -> tuple[str, int, int, float, str]:
    role = str(block.get("role") or "body")
    style = pipeline.style_for_role(theme, role)
    color = pipeline.color_for(theme, str(style.get("colorRole") or "text"))
    return (
        color,
        int(style.get("size") or 19),
        int(style.get("weight") or 400),
        float(style.get("lineHeight") or 1.4),
        role,
    )


def _content_html(entry: pipeline.FittedBlock, theme: dict[str, Any]) -> str:
    block = entry.block
    color, _size, weight, line_height, role = _block_colors(theme, block)
    align = entry.align
    font_family = pipeline.theme_fonts(theme)["display" if role == "headline" else "body"]
    base = (
        f"font-family:{_esc(font_family)};font-size:{entry.size:.2f}px;font-weight:{weight};"
        f"line-height:{max(0.9, entry.line_height):.2f};color:{_esc(color)};text-align:{align};"
        "overflow-wrap:anywhere;"
    )
    items = block.get("items") or []
    if role == "metric":
        text = str(block.get("text") or "")
        match = METRIC_PATTERN.match(text.strip())
        value, caption = (match.group(1), match.group(2).strip()) if match else (text, "")
        value_size = min(70.0, entry.size * 1.3)
        caption_html = (
            f'<div style="font-size:{max(10.0, entry.size * 0.42):.2f}px;font-weight:400;'
            f'line-height:1.25;color:{_esc(pipeline.color_for(theme, "muted"))};margin-top:8px">'
            f"{_esc(caption)}</div>"
            if caption
            else ""
        )
        return (
            f'<div style="height:100%;display:flex;flex-direction:column;justify-content:center;'
            f'text-align:{align}">'
            f'<div style="{base}font-size:{value_size:.2f}px;font-weight:800;line-height:0.95">'
            f"{_esc(value)}</div>{caption_html}</div>"
        )
    if role == "table" and items:
        rows = [[cell.strip() for cell in str(item).split("|")] for item in items]
        columns = max((len(row) for row in rows), default=1)
        head = "".join(f'<col style="width:{100 / max(columns, 1):.4f}%">' for _ in range(columns))
        body = []
        for row in rows:
            cells = "".join(
                f"<td>{_esc(row[index]) if index < len(row) else ''}</td>"
                for index in range(columns)
            )
            body.append(f"<tr>{cells}</tr>")
        return (
            f'<table style="{base}border-collapse:collapse;width:100%;height:100%">'
            f"<colgroup>{head}</colgroup><tbody>{''.join(body)}</tbody></table>"
        )
    if items:
        if role == "bullet_list" and theme.get("_toc"):
            entries = "".join(f"<li>{_esc(str(item))}</li>" for item in items)
            return f'<ol style="{base}margin:0;padding-left:24px">{entries}</ol>'
        entries = "".join(f"<li>{_esc(str(item))}</li>" for item in items)
        return f'<ul style="{base}margin:0;padding-left:20px">{entries}</ul>'
    if role == "quote":
        return (
            f'<div style="{base}border-left:4px solid {_esc(pipeline.color_for(theme, "primary"))};'
            f'padding-left:14px;white-space:pre-wrap">{_esc(block.get("text") or "")}</div>'
        )
    text = _esc(block.get("text") or "")
    extra = 'letter-spacing:-0.02em;' if role == "headline" else ""
    return f'<div style="{base}{extra}white-space:pre-wrap">{text}</div>'


def _chrome_html(rect: dict[str, Any], text: str, extra: str) -> str:
    if not text:
        return ""
    style = (
        f"position:absolute;left:{int(rect.get('x', 0))}px;top:{int(rect.get('y', 0))}px;"
        f"width:{int(rect.get('w', 400))}px;height:{int(rect.get('h', 32))}px;"
        f"display:flex;align-items:center;{extra}"
    )
    return f'<div class="chrome" style="{style}">{_esc(text)}</div>'


CSS = """
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#e5e7eb}
.deck{display:flex;flex-direction:column;gap:24px;padding:24px;align-items:center}
.slide{position:relative;width:1280px;height:720px;overflow:hidden;font-family:Inter,Helvetica,Arial,sans-serif}
.chrome{font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.card{position:absolute;border:1px solid;border-radius:18px}
.accent{position:absolute;border-radius:3px}
.block{position:absolute;overflow:hidden}
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
    total = len(pages)

    sections: list[str] = []
    for index, page in enumerate(pages):
        body = page.get("body") or {}
        page_type = pipeline.page_type_of(page, index, total)
        page_theme = pipeline.page_theme(theme, page_type)
        layout = pipeline.resolve_layout(layout_data, body.get("layoutId"))
        background = _esc(pipeline.color_for(page_theme, "background"))
        text_color = _esc(pipeline.color_for(page_theme, "text"))
        muted = _esc(pipeline.color_for(page_theme, "muted"))
        fonts = pipeline.theme_fonts(page_theme)
        parts = [
            f'<section class="slide" style="background:{background};color:{text_color};'
            f'font-family:{_esc(fonts["body"])},Inter,Helvetica,Arial,sans-serif">'
        ]
        if page_type not in {"COVER", "END"}:
            if not pipeline.has_headline(body):
                parts.append(
                    _chrome_html(
                        chrome["title"],
                        str(page.get("title") or ""),
                        f'font-family:{_esc(fonts["display"])};font-size:11px;opacity:.75;',
                    )
                )
            parts.append(
                _chrome_html(
                    chrome["sectionLabel"],
                    str(page.get("sectionLabel") or ""),
                    f"font-size:9px;color:{muted};font-weight:600;",
                )
            )
            parts.append(
                _chrome_html(
                    chrome["pageNumber"],
                    f"{page.get('position') or index + 1} / {total}",
                    f"font-size:9px;color:{muted};font-weight:500;justify-content:flex-end;",
                )
            )
        else:
            parts.append(
                f'<div class="accent" style="left:0;top:0;width:1280px;height:10px;'
                f'background:{_esc(pipeline.color_for(page_theme, "accent"))}"></div>'
            )
            parts.append(
                f'<div class="accent" style="left:64px;top:112px;width:6px;height:472px;'
                f'background:{_esc(pipeline.color_for(page_theme, "accent"))}"></div>'
            )
        if page_type == "TOC":
            parts.append(
                f'<div class="accent" style="left:64px;top:112px;width:6px;height:472px;'
                f'background:{_esc(pipeline.color_for(page_theme, "primary"))}"></div>'
            )
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
                    parts.append(
                        f'<div class="accent" style="left:{anchor.x:.1f}px;'
                        f'top:{anchor.y + anchor.h + 2:.1f}px;width:96px;height:3px;'
                        f'background:{_esc(pipeline.color_for(page_theme, "accent"))}"></div>'
                    )
            if card:
                parts.append(
                    f'<div class="card" style="left:{int(slot.get("x", 80))}px;top:{int(slot.get("y", 112))}px;'
                    f'width:{int(slot.get("w", 1120))}px;height:{int(slot.get("h", 472))}px;'
                    f'background:{_esc(pipeline.color_for(page_theme, "surface"))};'
                    f'border-color:{_esc(pipeline.blend(pipeline.color_for(page_theme, "primary"), pipeline.color_for(page_theme, "background"), 0.16))};'
                    f'border-radius:{int(pipeline.theme_tokens(page_theme).get("radius") or 18)}px"></div>'
                )
                parts.append(
                    f'<div class="accent" style="left:{int(slot.get("x", 80))}px;top:{int(slot.get("y", 112)) + 18}px;'
                    f'width:{int(pipeline.theme_tokens(page_theme).get("accentBar") or 6)}px;'
                    f'height:{max(12, int(slot.get("h", 472)) - 36)}px;'
                    f'background:{_esc(pipeline.color_for(page_theme, "accent"))}"></div>'
                )
            if slot_key == "header" and pipeline.theme_tokens(page_theme).get("headingRule"):
                parts.append(
                    f'<div class="accent" style="left:{int(slot.get("x", 80))}px;'
                    f'top:{int(slot.get("y", 104)) + int(slot.get("h", 72)) - 4}px;width:96px;height:3px;'
                    f'background:{_esc(pipeline.color_for(page_theme, "accent"))}"></div>'
                )
            for entry in entries:
                content = _content_html(
                    entry,
                    {**page_theme, "_toc": page_type == "TOC" and entry.role == "bullet_list"},
                )
                parts.append(
                    f'<div class="block" style="left:{entry.x:.1f}px;top:{entry.y:.1f}px;'
                    f'width:{entry.w:.1f}px;height:{entry.h:.1f}px">{content}</div>'
                )
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
