import { useId, type RefObject } from "react";
import { Sparkles, SlidersHorizontal } from "lucide-react";
import type { ProjectMode } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/controls";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export interface TopicFieldProps {
  id?: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  hint?: string;
  disabled?: boolean;
  inputRef?: RefObject<HTMLInputElement | null>;
}

export function TopicField({
  id = "project-topic",
  label = "Topic",
  value,
  onChange,
  error,
  hint,
  disabled,
  inputRef,
}: TopicFieldProps) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = error ? errorId : hint ? hintId : undefined;
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        ref={inputRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="What should the deck be about?"
        autoComplete="off"
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {error ? (
        <p id={errorId} role="alert" className="mt-1.5 text-sm font-medium text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

const SCENARIOS = [
  "Dify company introduction",
  "AI writing assistant launch",
  "Quarterly business review",
  "Seed round investor pitch",
] as const;

export function ScenarioChips({
  onSelect,
  disabled,
}: {
  onSelect: (topic: string) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-muted">Try an example</p>
      <div className="flex flex-wrap gap-2">
        {SCENARIOS.map((scenario, index) => (
          <Button
            key={scenario}
            type="button"
            variant="secondary"
            size="sm"
            className={cn("rounded-full font-medium", index >= 2 && "max-[480px]:hidden")}
            disabled={disabled}
            onClick={() => onSelect(scenario)}
          >
            {scenario}
          </Button>
        ))}
      </div>
    </div>
  );
}

const MODES: Array<{
  value: ProjectMode;
  label: string;
  description: string;
  icon: typeof Sparkles;
  badge?: string;
}> = [
  {
    value: "FULLY_AUTOMATIC",
    label: "Fully automatic",
    description: "The agent runs research, outline, and plan, pausing only for your style review.",
    icon: Sparkles,
    badge: "Default",
  },
  {
    value: "EXPERT_COPILOT",
    label: "Expert copilot",
    description: "Each stage waits for your explicit confirmation before moving on.",
    icon: SlidersHorizontal,
  },
];

export function ModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: ProjectMode;
  onChange: (mode: ProjectMode) => void;
  disabled?: boolean;
}) {
  const groupId = useId();
  return (
    <div>
      <p id={`${groupId}-label`} className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-muted">
        Generation mode
      </p>
      <RadioGroup
        value={value}
        onValueChange={(next) => onChange(next as ProjectMode)}
        aria-labelledby={`${groupId}-label`}
        className="grid gap-2 sm:grid-cols-2"
        disabled={disabled}
      >
        {MODES.map((mode) => {
          const Icon = mode.icon;
          const itemId = `${groupId}-${mode.value}`;
          const checked = value === mode.value;
          return (
            <div
              key={mode.value}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                checked ? "border-brand bg-brand-soft/70" : "border-line bg-white hover:bg-surface-2",
                disabled && "cursor-not-allowed opacity-60",
              )}
              onClick={() => {
                if (!disabled) onChange(mode.value);
              }}
            >
              <RadioGroupItem
                id={itemId}
                value={mode.value}
                className="mt-0.5"
                aria-describedby={`${itemId}-description`}
              />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    <Icon className="h-4 w-4 text-brand-strong" aria-hidden="true" />
                    {mode.label}
                  </span>
                  {mode.badge ? <Badge tone="brand">{mode.badge}</Badge> : null}
                </div>
                <p id={`${itemId}-description`} className="mt-1 text-xs leading-relaxed text-muted">
                  {mode.description}
                </p>
              </div>
            </div>
          );
        })}
      </RadioGroup>
    </div>
  );
}
