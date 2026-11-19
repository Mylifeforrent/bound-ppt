import { useEffect, useRef, useState } from "react";
import type { ArtifactChromeDTO, DesignBodyV1, PlanBlockV1, PlanBodyV1 } from "@/api/types";
import { CANVAS, CHROME, getLayout, getTheme, type Theme } from "@/render/layouts";
import { cn } from "@/lib/utils";

export function ScaledDeckCanvas({
  children,
  className,
  ariaLabel,
}: {
  children: React.ReactNode;
  className?: string;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      setScale(element.clientWidth / CANVAS.width);
    });
    observer.observe(element);
    setScale(element.clientWidth / CANVAS.width);
    return () => observer.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={cn("relative w-full overflow-hidden rounded-xl bg-white", className)}
      style={{ aspectRatio: "16 / 9" }}
      role="img"
      aria-label={ariaLabel ?? "Deck page"}
    >
      <div
        style={{
          width: CANVAS.width,
          height: CANVAS.height,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
          opacity: scale ? 1 : 0,
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function ChromeOverlay({ chrome, hideTitle = false }: { chrome: ArtifactChromeDTO | null; hideTitle?: boolean }) {
  if (!chrome) return null;
  const titleBox = CHROME.title;
  const sectionBox = CHROME.sectionLabel;
  const pageBox = CHROME.pageNumber;
  return (
    <div className="pointer-events-none absolute inset-0">
      {hideTitle ? null : (
        <div
          style={{ left: titleBox.x, top: titleBox.y, width: titleBox.w, height: titleBox.h }}
          className="absolute flex items-center overflow-hidden"
        >
          <span className="truncate text-[13px] font-semibold uppercase tracking-[0.16em] opacity-70">
            {chrome.title}
          </span>
        </div>
      )}
      {chrome.sectionLabel ? (
        <div
          style={{ left: sectionBox.x, top: sectionBox.y, width: sectionBox.w, height: sectionBox.h }}
          className="absolute flex items-center overflow-hidden"
        >
          <span className="truncate text-[12px] font-medium uppercase tracking-[0.14em] opacity-60">
            {chrome.sectionLabel}
          </span>
        </div>
      ) : null}
      <div
        style={{ left: pageBox.x, top: pageBox.y, width: pageBox.w, height: pageBox.h }}
        className="absolute flex items-center justify-end"
      >
        <span className="text-[12px] font-semibold tabular-nums opacity-60">
          {chrome.pageNumber} / {chrome.deckOrder}
        </span>
      </div>
    </div>
  );
}

export function PlanDeckPage({
  body,
  chrome,
  pageType = "BODY",
}: {
  body: PlanBodyV1;
  chrome?: ArtifactChromeDTO | null;
  pageType?: string;
}) {
  const layout = getLayout(body.layoutId);
  const bySlot = groupBySlot(body.blocks);
  const hasHeadline = body.blocks.some((block) => block.role === "headline");
  return (
    <div className="relative h-full w-full bg-white text-[#1f2937]">
      <div className="absolute inset-0">
        {layout.slots.map((slot) => (
          <div
            key={slot.key}
            className="absolute flex flex-col gap-3"
            style={{ left: slot.x, top: slot.y, width: slot.w, height: slot.h }}
          >
            {(bySlot[slot.key] ?? []).map((block) => (
              <PlanBlockView key={block.id} block={block} />
            ))}
          </div>
        ))}
      </div>
      <ChromeOverlay chrome={chrome ?? null} hideTitle={hasHeadline} />
      {!body.blocks.length ? (
        <div className="absolute inset-0 grid place-items-center text-sm text-gray-400">No layout blocks</div>
      ) : null}
      {pageType === "COVER" ? <div className="absolute inset-x-0 top-0 h-2 bg-gray-800" /> : null}
    </div>
  );
}

function PlanBlockView({ block }: { block: PlanBlockV1 }) {
  const label = roleLabel(block.role);
  const base = "relative rounded-lg border border-dashed border-gray-300 bg-gray-50/80 p-3";
  return (
    <div className={cn(base, growClass(block.role))}>
      <span className="absolute right-2 top-1.5 rounded bg-gray-200 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <BlockContent block={block} plan />
    </div>
  );
}

export function DesignDeckPage({
  body,
  chrome,
}: {
  body: DesignBodyV1;
  chrome?: ArtifactChromeDTO | null;
}) {
  const layout = getLayout(body.layoutId);
  const theme = getTheme(body.style.styleKey);
  const bySlot = groupBySlot(body.blocks);
  const hasHeadline = body.blocks.some((block) => block.role === "headline");
  const isCover = chrome?.pageNumber === 1;
  const isEnd = !!chrome && chrome.deckOrder > 1 && chrome.pageNumber === chrome.deckOrder;
  const fixedPage = isCover || isEnd;
  const isToc = chrome?.pageNumber === 2;
  const displayTheme: Theme = fixedPage
    ? {
        ...theme,
        palette: {
          ...theme.palette,
          background: theme.palette.secondary,
          text: "#ffffff",
          primary: tintColor(theme.palette.primary, 0.7),
          secondary: "#ffffff",
          surface: theme.palette.secondary,
          muted: tintColor(theme.palette.primary, 0.55),
        },
      }
    : theme;
  return (
    <div
      className="deck-root relative h-full w-full"
      style={{ background: displayTheme.palette.background, color: displayTheme.palette.text }}
    >
      {fixedPage ? (
        <>
          <div
            className="absolute inset-x-0 top-0 h-[10px]"
            style={{ background: displayTheme.palette.accent }}
          />
          <div
            className="absolute"
            style={{ left: 64, top: 112, width: 6, height: 472, background: displayTheme.palette.accent }}
          />
        </>
      ) : null}
      {isToc ? (
        <div
          className="absolute"
          style={{ left: 64, top: 112, width: 6, height: 472, background: displayTheme.palette.primary }}
        />
      ) : null}
      <div className="absolute inset-0">
        {layout.slots.map((slot) => (
          <div
            key={slot.key}
            className="absolute flex flex-col gap-3"
            style={{ left: slot.x, top: slot.y, width: slot.w, height: slot.h }}
          >
            {(bySlot[slot.key] ?? []).map((block) => (
              <DesignBlockView
                key={block.id}
                block={block}
                theme={displayTheme}
                numbered={isToc && block.role === "bullet_list"}
              />
            ))}
          </div>
        ))}
      </div>
      {fixedPage ? null : <ChromeOverlay chrome={chrome ?? null} hideTitle={hasHeadline} />}
      {!body.blocks.length ? (
        <div className="absolute inset-0 grid place-items-center text-sm" style={{ color: displayTheme.palette.muted }}>
          No design blocks
        </div>
      ) : null}
    </div>
  );
}

function DesignBlockView({
  block,
  theme,
  numbered = false,
}: {
  block: PlanBlockV1 & { style?: { textStyle: string; colorRole: string; align?: string } };
  theme: Theme;
  numbered?: boolean;
}) {
  const styleKey = block.style?.textStyle ?? block.role;
  const textStyle = theme.textStyles[styleKey] ?? theme.textStyles.body;
  const color = theme.palette[block.style?.colorRole ?? textStyle.colorRole] ?? theme.palette.text;
  const isCard = ["body", "bullet_list", "callout", "metric", "quote", "image", "chart", "table"].includes(block.role);
  return (
    <div
      className={cn("relative flex flex-col justify-center overflow-hidden", growClass(block.role))}
      style={{
        background: isCard ? theme.palette.surface : "transparent",
        borderRadius: Number(theme.tokens.radius ?? 16),
        padding: isCard ? "20px 22px" : 0,
        border: theme.tokens.cardBorder && isCard ? `1px solid ${withAlpha(theme.palette.primary, 0.16)}` : "1px solid transparent",
        textAlign: (block.style?.align as "left" | "center" | "right") ?? "left",
      }}
    >
      {block.role === "metric" ? <MetricBlock block={block} color={color} theme={theme} /> : null}
      {block.role !== "metric" ? (
        <BlockContent
          block={block}
          plan={false}
          numbered={numbered}
          color={color}
          fontSize={textStyle.size}
          fontWeight={textStyle.weight}
          lineHeight={textStyle.lineHeight}
          fontFamily={block.role === "headline" ? theme.fonts.display : theme.fonts.body}
        />
      ) : null}
      {block.role === "callout" ? (
        <span className="mt-3 block h-1.5 w-16 rounded-full" style={{ background: theme.palette.accent }} />
      ) : null}
    </div>
  );
}

function MetricBlock({ block, color, theme }: { block: PlanBlockV1; color: string; theme: Theme }) {
  const text = block.text ?? "";
  const match = text.match(/^([\d.,%+$€£-]+)\s*(.*)$/);
  const value = match?.[1] ?? text;
  const caption = match?.[2] ?? "";
  return (
    <div className="flex h-full flex-col justify-center">
      <span style={{ color, fontSize: 58, fontWeight: 800, lineHeight: 1, letterSpacing: "-0.03em" }}>{value}</span>
      {caption ? (
        <span style={{ color: theme.palette.muted, fontSize: 16, marginTop: 8, lineHeight: 1.4 }}>{caption}</span>
      ) : null}
    </div>
  );
}

function BlockContent({
  block,
  plan,
  color,
  fontSize,
  fontWeight,
  lineHeight,
  fontFamily,
  numbered = false,
}: {
  block: PlanBlockV1;
  plan: boolean;
  color?: string;
  fontSize?: number;
  fontWeight?: number;
  lineHeight?: number;
  fontFamily?: string;
  numbered?: boolean;
}) {
  const style: React.CSSProperties = {
    color: color ?? (plan ? "#374151" : undefined),
    fontSize: fontSize ?? planFontSize(block.role),
    fontWeight: fontWeight ?? (block.role === "headline" ? 700 : 400),
    lineHeight: lineHeight ?? 1.35,
    fontFamily,
    overflowWrap: "anywhere",
  };
  if (block.role === "metric") {
    return (
      <div style={style}>
        <div className="text-[44px] font-bold leading-none">{block.text || "00%"}</div>
      </div>
    );
  }
  if (block.role === "bullet_list" && block.items?.length) {
    const ListTag = numbered ? "ol" : "ul";
    return (
      <ListTag
        className={cn("m-0 space-y-1.5", numbered ? "list-decimal pl-6" : "list-disc pl-5")}
        style={style}
      >
        {block.items.map((item, index) => (
          <li key={`${block.id}-${index}`}>{item}</li>
        ))}
      </ListTag>
    );
  }
  if (block.role === "image" || block.role === "chart" || block.role === "table") {
    return (
      <div className="grid min-h-[80px] flex-1 place-items-center rounded-md border border-dashed" style={{ borderColor: plan ? "#d1d5db" : "rgba(0,0,0,.15)" }}>
        <span className="text-[10px] font-semibold uppercase tracking-widest opacity-60">
          {block.role}
          {block.assetRef ? ` · ${block.assetRef}` : " placeholder"}
        </span>
      </div>
    );
  }
  if (block.role === "quote") {
    return (
      <blockquote className="m-0 border-l-4 pl-4" style={{ ...style, borderColor: color ?? "#374151" }}>
        {block.text || "A supporting quote belongs here."}
      </blockquote>
    );
  }
  return (
    <div style={style} className={block.role === "headline" ? "tracking-tight" : undefined}>
      {block.text || (block.items?.length ? block.items.join(" · ") : "")}
    </div>
  );
}

function groupBySlot(blocks: PlanBlockV1[]): Record<string, PlanBlockV1[]> {
  const result: Record<string, PlanBlockV1[]> = {};
  for (const block of blocks) {
    (result[block.slot] ??= []).push(block);
  }
  return result;
}

function growClass(role: string): string {
  if (role === "headline") return "shrink-0";
  if (role === "subhead") return "shrink-0";
  if (role === "footer") return "mt-auto shrink-0";
  return "flex-1 min-h-0";
}

function roleLabel(role: string): string {
  return (
    {
      headline: "Headline",
      subhead: "Subhead",
      body: "Body copy",
      bullet_list: "Key points",
      metric: "Metric",
      quote: "Quote",
      image: "Image",
      chart: "Chart",
      table: "Table",
      callout: "Callout",
      footer: "Footer",
    }[role] ?? role
  );
}

function planFontSize(role: string): number {
  return (
    {
      headline: 34,
      subhead: 22,
      body: 15,
      bullet_list: 15,
      metric: 40,
      quote: 18,
      callout: 15,
      footer: 12,
    }[role] ?? 15
  );
}

export function withAlpha(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return hex;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function tintColor(hex: string, ratio: number): string {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) return hex;
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  const mix = (value: number) => Math.round(value + (255 - value) * ratio);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}
