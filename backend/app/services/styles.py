"""Built-in style catalog and project style selections.

The catalog is seeded lazily from `shared/themes/*.json`; the four M1 built-ins are
the only active definitions.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import layouts as layout_domain
from app.models import StyleDefinition, StyleSelection
from app.schemas.dto import StyleDTO, StylePaletteDTO, StyleSelectionDTO

PALETTE_FIELDS = ("primary", "secondary", "accent", "background", "surface", "text")


def _preview_url(style_key: str) -> str:
    return f"/shared/themes/{style_key}.json"


async def seed_styles(session: AsyncSession) -> bool:
    """Insert any missing built-in definitions. Returns True when rows were added."""
    created = False
    for style_key, theme in layout_domain.themes().items():
        version = int(theme.get("version") or 1)
        existing = await session.scalar(
            select(StyleDefinition).where(
                StyleDefinition.key == style_key, StyleDefinition.version == version
            )
        )
        if existing is not None:
            continue
        tokens: dict[str, Any] = {
            **dict(theme.get("tokens") or {}),
            "textStyles": theme.get("textStyles") or {},
            "fonts": theme.get("fonts") or {},
            "palette": theme.get("palette") or {},
            "styleKey": style_key,
            "version": version,
            "name": theme.get("name") or style_key,
        }
        session.add(
            StyleDefinition(
                key=style_key,
                name=str(theme.get("name") or style_key),
                version=version,
                scope=str(theme.get("scope") or "BUILTIN"),
                palette=dict(theme.get("palette") or {}),
                tokens=tokens,
                preview_ref=_preview_url(style_key),
                description=str(theme.get("description") or ""),
                use_case=str(theme.get("useCase") or ""),
                license_status="CLEARED",
                is_active=True,
            )
        )
        created = True
    if created:
        await session.flush()
    return created


async def list_styles(session: AsyncSession) -> list[StyleDefinition]:
    return list(
        (
            await session.scalars(
                select(StyleDefinition)
                .where(StyleDefinition.is_active.is_(True))
                .order_by(StyleDefinition.name, StyleDefinition.version)
            )
        ).all()
    )


async def get_style(
    session: AsyncSession, style_key: str, version: int | None = None
) -> StyleDefinition | None:
    query = select(StyleDefinition).where(
        StyleDefinition.key == style_key,
        StyleDefinition.is_active.is_(True),
    )
    if version is not None:
        query = query.where(StyleDefinition.version == version)
    return await session.scalar(query.order_by(StyleDefinition.version.desc()).limit(1))


def style_dto(definition: StyleDefinition) -> StyleDTO:
    palette_raw = dict(definition.palette or {})
    tokens = dict(definition.tokens or {})
    theme_palette = tokens.get("palette") if isinstance(tokens.get("palette"), dict) else {}
    merged = {**theme_palette, **palette_raw}
    palette = StylePaletteDTO(
        primary=str(merged.get("primary") or "#111827"),
        secondary=str(merged.get("secondary") or "#374151"),
        accent=str(merged.get("accent") or "#2563eb"),
        background=str(merged.get("background") or "#ffffff"),
        surface=str(merged.get("surface") or "#f3f4f6"),
        text=str(merged.get("text") or "#0b0f19"),
    )
    preview = definition.preview_ref or _preview_url(definition.key)
    return StyleDTO(
        style_key=definition.key,
        name=definition.name,
        version=definition.version,
        scope=definition.scope,
        description=definition.description,
        palette=palette,
        preview_url=preview,
        license_status=definition.license_status,
        use_case=definition.use_case,
    )


def selection_dto(selection: StyleSelection, definition: StyleDefinition | None) -> StyleSelectionDTO:
    return StyleSelectionDTO(
        style_selection_id=selection.id,
        style_key=definition.key if definition else "unknown",
        style_version=selection.style_version,
        confirmed=bool(selection.confirmed_at),
        confirmed_at=selection.confirmed_at,
        remember_preference=bool(selection.remember_preference),
        created_at=selection.created_at,
    )


def theme_json(definition: StyleDefinition) -> dict[str, Any]:
    """Return the shared theme JSON for a definition (used by render/composition)."""
    return layout_domain.themes()[definition.key]


def theme_dump(definition: StyleDefinition) -> str:
    return json.dumps(theme_json(definition), ensure_ascii=False, sort_keys=True)
