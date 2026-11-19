import { useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { CloudUpload, FileText, Link2, Clipboard, AlertTriangle, ShieldAlert } from "lucide-react";
import type { ClientConfigDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton, Textarea } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/controls";
import { Badge } from "@/components/ui/primitives";
import { cn, formatBytes } from "@/lib/utils";
import { messageFor } from "@/lib/messages";
import { MaterialChips } from "./MaterialChips";
import type { MaterialIntakeController } from "./useMaterialIntake";
import type { SkippedFile } from "./types";
import { acceptedTypesLabel, maxFileBytes } from "./validation";

type ComposerTab = "paste" | "file" | "url";

export interface MaterialComposerProps {
  controller: MaterialIntakeController;
  config?: ClientConfigDTO;
  limitReady: boolean;
  consentBlocked: boolean;
  consentLoading?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  readOnlyNote?: string;
  retryEnabled?: boolean;
  onRequireConsent?: () => void;
  heading?: string;
  emptyText?: string;
}

export function MaterialComposer({
  controller,
  config,
  limitReady,
  consentBlocked,
  consentLoading = false,
  disabled = false,
  readOnly = false,
  readOnlyNote,
  retryEnabled = true,
  onRequireConsent,
  heading = "Materials",
  emptyText,
}: MaterialComposerProps) {
  const [tab, setTab] = useState<ComposerTab>("paste");
  const [paste, setPaste] = useState("");
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [skipped, setSkipped] = useState<SkippedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const limit = controller.limit;
  const countLabel = useMemo(() => {
    if (!limitReady) return null;
    if (limit <= 0) return `${controller.count} materials`;
    return `${controller.count} / ${limit} materials`;
  }, [controller.count, limit, limitReady]);

  const canAdd = limitReady && !disabled && !consentBlocked && !controller.atLimit;
  const typesLabel = acceptedTypesLabel(config);
  const maxBytes = maxFileBytes(config);

  const reportGate = () => {
    if (disabled) return;
    if (!limitReady) {
      setFormError("Material limits are still loading. Try again in a moment.");
      return;
    }
    if (consentBlocked) {
      setFormError(messageFor("error.gate.consent_required"));
      onRequireConsent?.();
      return;
    }
    if (controller.atLimit) {
      setFormError(messageFor("error.gate.material_limit"));
      return;
    }
    setFormError(messageFor("error.internal.unexpected"));
  };

  const addPaste = () => {
    if (!canAdd) {
      reportGate();
      return;
    }
    const result = controller.addPaste(paste);
    if (result.ok) {
      setPaste("");
      setFormError(null);
    } else {
      setFormError(messageFor(result.errorKey));
      if (result.errorKey === "error.gate.consent_required") onRequireConsent?.();
    }
  };

  const addUrl = () => {
    if (!canAdd) {
      reportGate();
      return;
    }
    const result = controller.addUrl(url);
    if (result.ok) {
      setUrl("");
      setFormError(null);
    } else {
      setFormError(messageFor(result.errorKey));
      if (result.errorKey === "error.gate.consent_required") onRequireConsent?.();
    }
  };

  const addFiles = (files: File[]) => {
    if (!canAdd) {
      reportGate();
      return;
    }
    const result = controller.addFiles(files);
    setSkipped(result.skipped ?? []);
    if (result.ok && (result.added ?? 0) > 0) {
      setFormError(null);
    } else if (!result.ok) {
      setFormError(messageFor(result.errorKey));
      if (result.errorKey === "error.gate.consent_required") onRequireConsent?.();
    }
  };

  const onPasteKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      addPaste();
    }
  };

  const onUrlKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addUrl();
    }
  };

  const openPicker = () => {
    if (!canAdd) {
      reportGate();
      return;
    }
    fileInputRef.current?.click();
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (canAdd) setDragging(true);
  };

  const onDragLeave = () => setDragging(false);

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) addFiles(files);
  };

  if (readOnly) {
    return (
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">{heading}</h2>
          <Badge tone="neutral">{countLabel ?? `${controller.count} materials`}</Badge>
        </div>
        {readOnlyNote ? (
          <p className="mb-3 rounded-xl border border-amber-200 bg-warn-soft/70 px-3 py-2 text-sm text-warn">
            {readOnlyNote}
          </p>
        ) : null}
        <MaterialChips
          entries={controller.entries}
          onRemove={controller.remove}
          onRetry={controller.retry}
          retryEnabled={false}
          readOnly
          emptyText={emptyText ?? "No materials were added to this project."}
        />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">{heading}</h2>
        {countLabel ? (
          <Badge tone={controller.atLimit ? "warn" : "neutral"}>{countLabel}</Badge>
        ) : (
          <Skeleton className="h-5 w-24" />
        )}
      </div>

      {!limitReady ? (
        <p className="mb-3 text-xs text-muted">Loading the material limit and supported file types…</p>
      ) : null}

      {controller.atLimit ? (
        <p role="status" className="mb-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-sm text-warn">
          {messageFor("error.gate.material_limit")}
        </p>
      ) : null}

      {consentBlocked && !consentLoading ? (
        <div className="mb-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-sm text-warn">
          <p className="flex items-start gap-1.5">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{messageFor("error.gate.consent_required")}</span>
          </p>
          {onRequireConsent ? (
            <button
              type="button"
              className="mt-1 text-xs font-semibold text-brand-strong underline underline-offset-2"
              onClick={onRequireConsent}
            >
              Review the data notice
            </button>
          ) : null}
        </div>
      ) : null}

      <Tabs value={tab} onValueChange={(value) => setTab(value as ComposerTab)}>
        <TabsList aria-label="Material type" className="w-full justify-start">
          <TabsTrigger value="paste" className="flex items-center gap-1.5">
            <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
            Paste
          </TabsTrigger>
          <TabsTrigger value="file" className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            File
          </TabsTrigger>
          <TabsTrigger value="url" className="flex items-center gap-1.5">
            <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
            URL
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paste" className="mt-3">
          <Label htmlFor="material-paste">Paste text</Label>
          <Textarea
            id="material-paste"
            value={paste}
            onChange={(event) => setPaste(event.target.value)}
            onKeyDown={onPasteKeyDown}
            placeholder="Paste notes, a product brief, or any source text…"
            disabled={!limitReady || disabled}
            aria-describedby="material-paste-hint"
          />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <p id="material-paste-hint" className="text-xs text-muted">
              Cmd/Ctrl + Enter adds the text as one material.
            </p>
            <Button type="button" size="sm" onClick={addPaste} disabled={!canAdd}>
              Add text
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="file" className="mt-3">
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={cn(
              "flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-6 text-center transition-colors",
              dragging ? "border-brand bg-brand-soft/60" : "border-line-strong bg-surface-2",
              !canAdd && "opacity-70",
            )}
          >
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-brand-strong shadow-sm">
              <CloudUpload className="h-5 w-5" aria-hidden="true" />
            </span>
            <p className="text-sm font-medium text-ink">Drag files here</p>
            <p className="text-xs text-muted">
              {typesLabel ? `Supported: ${typesLabel}` : "Supported file types load from your plan."}
              {maxBytes ? ` · up to ${formatBytes(maxBytes)} each` : ""}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="sr-only"
              accept={config?.supportedFileTypes.map((entry) => entry.extension).join(",") || undefined}
              tabIndex={-1}
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                event.target.value = "";
                if (files.length > 0) addFiles(files);
              }}
            />
            <Button type="button" size="sm" variant="secondary" onClick={openPicker} disabled={!canAdd}>
              Choose files
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="url" className="mt-3">
          <Label htmlFor="material-url">Add a link</Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              id="material-url"
              type="text"
              inputMode="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              onKeyDown={onUrlKeyDown}
              placeholder="example.com/article"
              autoComplete="url"
              disabled={!limitReady || disabled}
              aria-describedby="material-url-hint"
            />
            <Button type="button" size="sm" className="sm:shrink-0" onClick={addUrl} disabled={!canAdd}>
              Add link
            </Button>
          </div>
          <p id="material-url-hint" className="mt-1.5 text-xs text-muted">
            A missing scheme is added automatically. Private and local addresses are rejected.
          </p>
        </TabsContent>
      </Tabs>

      {formError ? (
        <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger">
          {formError}
        </p>
      ) : null}

      {skipped.length > 0 ? (
        <div className="mt-3 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-xs text-warn">
          <p className="flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {skipped.length === 1 ? "1 file was not added" : `${skipped.length} files were not added`}
          </p>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {skipped.map((item) => (
              <li key={`${item.name}-${item.errorKey}`}>
                <span className="font-medium">{item.name}</span>: {messageFor(item.errorKey)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4">
        <MaterialChips
          entries={controller.entries}
          onRemove={controller.remove}
          onRetry={controller.retry}
          retryEnabled={retryEnabled}
          disabled={disabled}
          emptyText={emptyText}
        />
      </div>
    </div>
  );
}
