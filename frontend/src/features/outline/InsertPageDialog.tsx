import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Input,
  Label,
  Textarea,
} from "@/components/ui/dialog";

export interface InsertPageTarget {
  mode: "after" | "section";
  sectionTitle: string;
  afterTitle?: string;
}

export function InsertPageDialog({
  target,
  pending,
  error,
  onClose,
  onSubmit,
}: {
  target: InsertPageTarget | null;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (title: string, keyPoints: string[]) => void;
}) {
  const [title, setTitle] = useState("");
  const [points, setPoints] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const open = target !== null;

  const targetKey = target
    ? `${target.mode}:${target.sectionTitle}:${target.afterTitle ?? ""}`
    : "closed";

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setPoints("");
    setLocalError(null);
  }, [open, targetKey]);

  const message = localError ?? error;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !pending) onClose();
      }}
    >
      <DialogContent>
        <DialogTitle>Insert a page</DialogTitle>
        <DialogDescription>
          {target?.mode === "after"
            ? `The new body page is added after “${target.afterTitle ?? "the selected note"}” in “${target.sectionTitle}”.`
            : `The new body page is appended to the end of “${target?.sectionTitle ?? "the section"}”.`}
        </DialogDescription>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = title.trim();
            if (!trimmed) {
              setLocalError("Enter a page title.");
              return;
            }
            setLocalError(null);
            const keyPoints = points
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean);
            onSubmit(trimmed, keyPoints);
          }}
        >
          <div>
            <Label htmlFor="outline-insert-title">Page title</Label>
            <Input
              id="outline-insert-title"
              value={title}
              autoFocus
              onChange={(event) => {
                setLocalError(null);
                setTitle(event.target.value);
              }}
              aria-invalid={message ? true : undefined}
              aria-describedby={message ? "outline-insert-error" : undefined}
              placeholder="e.g. Market landscape"
            />
          </div>
          <div>
            <Label htmlFor="outline-insert-points">Key content points (one per line)</Label>
            <Textarea
              id="outline-insert-points"
              value={points}
              onChange={(event) => setPoints(event.target.value)}
              placeholder={"Three competitors\nMarket size and growth\nWhere we differentiate"}
            />
          </div>
          {message ? (
            <p
              id="outline-insert-error"
              role="alert"
              className="rounded-lg border border-red-200 bg-danger-soft px-3 py-2 text-xs font-medium text-danger"
            >
              {message}
            </p>
          ) : null}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={onClose} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              {pending ? "Inserting…" : "Insert page"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
