import { useEffect, useId, useRef, useState } from "react";
import { Check, Loader2, Pencil } from "lucide-react";
import type { QuestionDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/controls";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { ErrorInfo } from "@/features/intake/errors";

export type QuestionCardState = "answered" | "current" | "editing" | "locked";

export interface QuestionCardProps {
  question: QuestionDTO;
  state: QuestionCardState;
  pending: boolean;
  error?: ErrorInfo | null;
  onEdit: () => void;
  onCancelEdit: () => void;
  onAnswer: (optionKey: string) => void;
}

function optionLabel(question: QuestionDTO, optionKey: string | undefined): string {
  if (!optionKey) return "No answer";
  return question.options.find((option) => option.key === optionKey)?.label ?? optionKey;
}

export function QuestionCard({
  question,
  state,
  pending,
  error,
  onEdit,
  onCancelEdit,
  onAnswer,
}: QuestionCardProps) {
  const baseId = useId();
  const titleId = `${baseId}-prompt`;
  const [optimisticOption, setOptimisticOption] = useState<string | null>(null);
  const submitRef = useRef(false);
  const optionsRef = useRef(question.options);
  optionsRef.current = question.options;
  const answerKeyRef = useRef(question.answer?.optionKey);
  answerKeyRef.current = question.answer?.optionKey;

  useEffect(() => {
    if (!pending) submitRef.current = false;
  }, [pending]);

  useEffect(() => {
    if (!pending) setOptimisticOption(null);
  }, [pending]);

  useEffect(() => {
    if (state !== "editing") return;
    const target = answerKeyRef.current ?? optionsRef.current[0]?.key;
    if (!target) return;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(`${baseId}-${target}`)?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [state, question.key, baseId]);

  const handleSelect = (optionKey: string) => {
    if (pending || submitRef.current) return;
    submitRef.current = true;
    setOptimisticOption(optionKey);
    onAnswer(optionKey);
  };

  if (state === "answered") {
    return (
      <Card className="p-4" data-question-key={question.key}>
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ok-soft text-ok">
            <Check className="h-3.5 w-3.5" strokeWidth={3} aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Question {question.position}</p>
            <p className="mt-0.5 text-sm font-medium text-ink-2">{question.prompt}</p>
            <p className="mt-1 text-sm text-ink">
              Recorded: <span className="font-semibold">{optionLabel(question, question.answer?.optionKey)}</span>
              <span aria-hidden="true"> · </span>
              <button
                type="button"
                id={`edit-${question.key}`}
                className="text-sm font-semibold text-brand-strong underline underline-offset-2"
                onClick={onEdit}
              >
                Edit
              </button>
            </p>
          </div>
        </div>
      </Card>
    );
  }

  if (state === "locked") {
    return (
      <Card className="border-dashed p-4 opacity-70" data-question-key={question.key}>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Question {question.position}</p>
        <p className="mt-1 text-sm text-muted">{question.prompt}</p>
        <p className="mt-1 text-xs text-faint">Answer the previous question first.</p>
      </Card>
    );
  }

  const selected = pending
    ? optimisticOption ?? question.answer?.optionKey ?? ""
    : question.answer?.optionKey ?? "";

  return (
    <Card
      className={cn("p-4", state === "current" ? "border-brand shadow-[var(--sh-2)]" : "border-brand/50")}
      aria-busy={pending}
      data-question-key={question.key}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-brand-strong">
          Question {question.position}
        </p>
        <div className="flex items-center gap-2">
          {pending ? (
            <span className="flex items-center gap-1 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              Recording…
            </span>
          ) : null}
          {state === "editing" ? (
            <Button type="button" variant="ghost" size="sm" onClick={onCancelEdit} disabled={pending}>
              Cancel
            </Button>
          ) : null}
        </div>
      </div>
      <p id={titleId} className="mt-1 text-sm font-semibold text-ink">
        {question.prompt}
      </p>
      <RadioGroup
        aria-labelledby={titleId}
        value={selected}
        onValueChange={handleSelect}
        disabled={pending}
        className="mt-3 space-y-2"
      >
        {question.options.map((option) => {
          const optionId = `${baseId}-${option.key}`;
          const checked = selected === option.key;
          return (
            <div
              key={option.key}
              onClick={() => handleSelect(option.key)}
              className={cn(
                "flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2 text-sm transition-colors",
                checked ? "border-brand bg-brand-soft/70 text-ink" : "border-line bg-white text-ink-2 hover:bg-surface-2",
                pending && "cursor-wait opacity-80",
              )}
            >
              <RadioGroupItem id={optionId} value={option.key} disabled={pending} />
              <span className="min-w-0">{option.label}</span>
            </div>
          );
        })}
      </RadioGroup>
      {error ? (
        <div role="alert" className="mt-3 rounded-lg border border-red-200 bg-danger-soft px-2.5 py-2 text-xs text-danger">
          <p>{error.message}</p>
          {error.reference ? <p className="mono mt-1 text-[11px] text-danger/80">Reference: {error.reference}</p> : null}
          <p className="mt-1">Choose an option to try again.</p>
        </div>
      ) : null}
      {state === "editing" ? (
        <p className="mt-2 flex items-center gap-1 text-xs text-muted">
          <Pencil className="h-3 w-3" aria-hidden="true" />
          Choosing an option overwrites the recorded answer.
        </p>
      ) : null}
    </Card>
  );
}
