import type { ArtifactChromeDTO, DesignBodyV1, StyleDTO } from "@/api/types";
import { DesignDeckPage, ScaledDeckCanvas } from "@/render/DeckRenderer";
import { getTheme, type Theme } from "@/render/layouts";

function tokensFor(theme: Theme): Record<string, string | number> {
  const tokens: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(theme.tokens)) {
    if (typeof value === "string" || typeof value === "number") tokens[key] = value;
  }
  return tokens;
}

/**
 * A representative "company introduction" page built from the real theme
 * tokens. It is not a screenshot or a placeholder palette: the same
 * DesignDeckPage renderer used by the design stage draws it.
 */
export function buildStylePreviewBody(
  style: StyleDTO,
): { body: DesignBodyV1; chrome: ArtifactChromeDTO; theme: Theme } | null {
  const theme = getTheme(style.styleKey);
  if (theme.styleKey !== style.styleKey) return null;
  const text = theme.textStyles;
  const body: DesignBodyV1 = {
    schemaVersion: 1,
    canvas: { width: 1280, height: 720 },
    layoutId: "mix",
    density: "medium",
    style: {
      styleKey: theme.styleKey,
      styleVersion: theme.version,
      tokens: tokensFor(theme),
    },
    blocks: [
      {
        id: "preview-headline",
        slot: "header",
        role: "headline",
        text: "Company introduction",
        style: { textStyle: "headline", colorRole: text.headline.colorRole, align: "left" },
      },
      {
        id: "preview-metric-1",
        slot: "stat1",
        role: "metric",
        text: "98% customer retention",
        style: { textStyle: "metric", colorRole: text.metric.colorRole, align: "left" },
      },
      {
        id: "preview-metric-2",
        slot: "stat2",
        role: "metric",
        text: "24 markets served",
        style: { textStyle: "metric", colorRole: text.metric.colorRole, align: "left" },
      },
      {
        id: "preview-body",
        slot: "body",
        role: "body",
        text: "A representative page shows the type scale, cards, and accent colors before this style is applied to every deck page.",
        style: { textStyle: "body", colorRole: text.body.colorRole, align: "left" },
      },
      {
        id: "preview-callout",
        slot: "callout",
        role: "callout",
        text: "One clear takeaway per page.",
        style: { textStyle: "callout", colorRole: text.callout.colorRole, align: "left" },
      },
      {
        id: "preview-footer",
        slot: "footer",
        role: "footer",
        text: "Bound PPT · style preview",
        style: { textStyle: "footer", colorRole: text.footer.colorRole, align: "left" },
      },
    ],
    assets: [],
    meta: { title: `${style.name} preview` },
  };
  return {
    body,
    theme,
    chrome: {
      pageNumber: 2,
      deckOrder: 12,
      title: style.name,
      sectionLabel: "Company introduction",
      chromeVersion: "style-preview-v1",
    },
  };
}

export function StylePreview({ style }: { style: StyleDTO }) {
  const preview = buildStylePreviewBody(style);
  if (!preview) {
    return (
      <div
        className="grid aspect-video w-full place-items-center rounded-xl border border-line bg-surface-2 p-4 text-center text-xs text-muted"
        aria-hidden="true"
      >
        Preview unavailable for this style version
      </div>
    );
  }
  return (
    <div
      className="overflow-hidden rounded-xl border border-line"
      aria-hidden="true"
    >
      <ScaledDeckCanvas ariaLabel={`${style.name} style preview`}>
        <DesignDeckPage body={preview.body} chrome={preview.chrome} />
      </ScaledDeckCanvas>
    </div>
  );
}
