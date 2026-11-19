from __future__ import annotations

from typing import Any

from app.core.ids import digest_json


def plan_fingerprint(
    *,
    project_id: str,
    page_id: str,
    page_type: str,
    section_key: str,
    key_points: list[str],
    layout_vocabulary: str = "v1",
    generation_profile: str = "plan.economy@1",
    prompt_version: str = "plan@1",
    fingerprint_version: int = 1,
) -> str:
    return digest_json(
        {
            "artifactKind": "PLAN",
            "projectId": project_id,
            "pageId": page_id,
            "pageType": page_type,
            "sectionKey": section_key,
            "keyPoints": key_points,
            "outlinePageSchemaVersion": 1,
            "layoutVocabularyVersion": layout_vocabulary,
            "generationProfile": generation_profile,
            "promptVersion": prompt_version,
            "planSchemaVersion": 1,
            "fingerprintVersion": fingerprint_version,
        }
    )


def design_fingerprint(
    *,
    project_id: str,
    page_id: str,
    plan_artifact_version_id: str,
    style_definition_id: str,
    style_version: int,
    design_vocabulary: str = "v1",
    generation_profile: str = "design.quality@1",
    prompt_version: str = "design@1",
    fingerprint_version: int = 1,
) -> str:
    return digest_json(
        {
            "artifactKind": "DESIGN",
            "projectId": project_id,
            "pageId": page_id,
            "planArtifactVersionId": plan_artifact_version_id,
            "styleDefinitionId": style_definition_id,
            "styleVersion": style_version,
            "designVocabularyVersion": design_vocabulary,
            "generationProfile": generation_profile,
            "promptVersion": prompt_version,
            "designSchemaVersion": 1,
            "fingerprintVersion": fingerprint_version,
        }
    )


def chrome_version(
    *,
    page_id: str,
    title: str,
    position: int,
    deck_order: int,
    section_key: str,
    section_label: str | None,
) -> str:
    return digest_json(
        {
            "pageId": page_id,
            "title": title,
            "position": position,
            "deckOrder": deck_order,
            "sectionKey": section_key,
            "sectionLabel": section_label,
            "chromeSchemaVersion": 1,
        }
    )


def profile_fingerprint(
    *,
    answers: dict[str, str],
    material_ids: list[str],
    gap_selected_ids: list[str],
    web_skipped: bool,
    source_ids: list[str],
) -> str:
    return digest_json(
        {
            "answers": dict(sorted(answers.items())),
            "materialIds": sorted(material_ids),
            "gapSelectedIds": sorted(gap_selected_ids),
            "webSkipped": web_skipped,
            "sourceIds": sorted(source_ids),
            "profileFingerprintVersion": 1,
        }
    )


def canonical(value: Any) -> str:
    return digest_json(value)
