import type { KeyboardEvent } from "react";
import { Check, Palette } from "lucide-react";
import type { StyleDTO } from "@/api/types";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import { StylePreview } from "./StylePreview";

const SWATCHES: Array<{ key: keyof StyleDTO["palette"]; label: string }> = [
  { key: "primary", label: "Primary" },
  { key: "secondary", label: "Secondary" },
  { key: "accent", label: "Accent" },
  { key: "background", label: "Background" },
  { key: "surface", label: "Surface" },
  { key: "text", label: "Text" },
];

export function StyleCard({
  style,
  index,
  selected,
  lastUsed,
  confirmed,
  focusable,
  disabled,
  onSelect,
  onKeyDown,
}: {
  style: StyleDTO;
  index: number;
  selected: boolean;
  lastUsed: boolean;
  confirmed: boolean;
  focusable: boolean;
  disabled: boolean;
  onSelect: (style: StyleDTO) => void;
  onKeyDown: (event: KeyboardEvent<HTMLDivElement>, index: number) => void;
}) {
  const descriptionId = `style-description-${style.styleKey}`;
  const useCaseId = `style-usecase-${style.styleKey}`;
  const label = [
    style.name,
    style.description,
    `Use case: ${style.useCase}`,
    lastUsed ? "Last used." : "",
    confirmed ? "Confirmed." : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      role="radio"
      aria-checked={selected}
      aria-label={label}
      aria-describedby={`${descriptionId} ${useCaseId}`}
      aria-disabled={disabled || undefined}
      data-style-index={index}
      tabIndex={focusable && !disabled ? 0 : -1}
      onClick={() => {
        if (!disabled) onSelect(style);
      }}
      onKeyDown={(event) => onKeyDown(event, index)}
      className={cn(
        "relative flex min-w-0 cursor-pointer flex-col rounded-2xl border bg-white p-3 text-left outline-none transition-shadow",
        "focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
        selected
          ? "border-brand ring-2 ring-brand/40 shadow-[var(--sh-2)]"
          : "border-line hover:border-line-strong hover:shadow-[var(--sh-2)]",
        disabled && "cursor-not-allowed opacity-70",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{style.name}</p>
          <p className="mt-0.5 text-[11px] text-muted">
            {style.scope === "BUILTIN" ? "Built-in" : style.scope} · v{style.version}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
          {lastUsed ? <Badge tone="brand">Last used</Badge> : null}
          {confirmed ? <Badge tone="ok">Confirmed</Badge> : null}
          <span
            className={cn(
              "grid h-5 w-5 place-items-center rounded-full border",
              selected
                ? "border-brand bg-brand text-white"
                : "border-line-strong bg-white text-transparent",
            )}
            aria-hidden="true"
          >
            <Check className="h-3 w-3" strokeWidth={3} />
          </span>
        </div>
      </div>

      <div className="mt-2.5">
        <StylePreview style={style} />
      </div>

      <p id={descriptionId} className="mt-2.5 text-xs leading-snug text-ink-2">
        {style.description}
      </p>
      <p id={useCaseId} className="mt-1 text-[11px] leading-snug text-muted">
        <span className="font-semibold text-ink-2">Use for:</span> {style.useCase}
      </p>

      <div className="mt-3 border-t border-line pt-2.5">
        <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
          <Palette className="h-3 w-3" aria-hidden="true" />
          Palette
        </p>
        <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label={`${style.name} palette`}>
          {SWATCHES.map((swatch) => {
            const value = style.palette[swatch.key];
            return (
              <li key={swatch.key} className="flex items-center gap-1">
                <span
                  className="h-5 w-5 rounded-full border border-line"
                  style={{ background: value }}
                  title={`${swatch.label}: ${value}`}
                  aria-hidden="true"
                />
                <span className="sr-only">
                  {swatch.label} {value}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
