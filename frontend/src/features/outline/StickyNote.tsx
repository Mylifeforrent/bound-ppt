import type { ButtonHTMLAttributes, KeyboardEvent } from "react";
import type { DraggableAttributes } from "@dnd-kit/core";
import type { Transform } from "@dnd-kit/utilities";
import {
  ArrowDown,
  ArrowUp,
  GripVertical,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import type { OutlinePageDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";
import type { OutlineSectionGroup } from "./types";

export interface NoteCallbacks {
  onStartEdit: (page: OutlinePageDTO) => void;
  onTitleDraftChange: (value: string) => void;
  onSaveTitle: () => void;
  onCancelEdit: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onInsertAfter: () => void;
  onDelete: () => void;
}

interface NoteTitleProps {
  page: OutlinePageDTO;
  editing: boolean;
  titleDraft: string;
  titleError: string | null;
  busy: boolean;
  onStartEdit: (page: OutlinePageDTO) => void;
  onTitleDraftChange: (value: string) => void;
  onSaveTitle: () => void;
  onCancelEdit: () => void;
}

function NoteTitle({
  page,
  editing,
  titleDraft,
  titleError,
  busy,
  onStartEdit,
  onTitleDraftChange,
  onSaveTitle,
  onCancelEdit,
}: NoteTitleProps) {
  const inputId = `outline-title-${page.pageId}`;
  const errorId = `outline-title-error-${page.pageId}`;

  if (editing) {
    return (
      <div className="min-w-0 flex-1">
        <label htmlFor={inputId} className="sr-only">
          Page title
        </label>
        <input
          id={inputId}
          value={titleDraft}
          autoFocus
          className="field h-9 py-1 text-sm"
          onChange={(event) => onTitleDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.stopPropagation();
              onSaveTitle();
            } else if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              onCancelEdit();
            }
          }}
          aria-invalid={titleError ? true : undefined}
          aria-describedby={titleError ? errorId : undefined}
        />
        {titleError ? (
          <p
            id={errorId}
            role="alert"
            className="mt-1 rounded-md bg-white/80 px-2 py-1 text-[11px] font-medium text-danger"
          >
            {titleError}
          </p>
        ) : (
          <p className="mt-1 text-[11px] opacity-70">Enter saves · Esc cancels</p>
        )}
        <div className="mt-1.5 flex gap-1.5">
          <Button type="button" size="sm" onClick={onSaveTitle} disabled={busy}>
            Save
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={onCancelEdit}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onStartEdit(page)}
      className="min-w-0 flex-1 rounded-md text-left focus-visible:outline-2 focus-visible:outline-offset-2"
      aria-label={`Edit title of page ${page.position}: ${page.title}`}
    >
      <span className="line-clamp-2 block text-sm font-semibold leading-snug">
        {page.title}
      </span>
      <span className="mt-0.5 block text-[11px] opacity-65">Click to edit the title</span>
    </button>
  );
}

function NoteKeyPoints({ page, fixed }: { page: OutlinePageDTO; fixed: boolean }) {
  if (page.keyPoints.length === 0) {
    return (
      <p
        className={cn(
          "mt-2 text-xs italic",
          fixed ? "text-muted" : "text-[#6b5a2a]",
        )}
      >
        No key points yet
      </p>
    );
  }
  return (
    <ul className={cn("mt-2 space-y-1 text-xs leading-snug", fixed ? "text-ink-2" : "text-[#3c3410]")}>
      {page.keyPoints.map((point, index) => (
        <li key={`${page.pageId}-point-${index}`} className="flex gap-1.5">
          <span aria-hidden="true" className="mt-1 h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
          <span className="min-w-0">{point}</span>
        </li>
      ))}
    </ul>
  );
}

function PageNumber({
  page,
  pending,
  fixed,
}: {
  page: OutlinePageDTO;
  pending: boolean;
  fixed: boolean;
}) {
  return (
    <span
      className={cn(
        "mono inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
        fixed ? "bg-white text-ink-2" : "bg-white/70 text-[#3c3410]",
      )}
      aria-label={`Page ${page.position}`}
    >
      {pending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}
      #{page.position}
    </span>
  );
}

function NoteActions({
  page,
  busy,
  pending,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onInsertAfter,
  onDelete,
}: {
  page: OutlinePageDTO;
  busy: boolean;
  pending: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onInsertAfter: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-1 border-t border-black/10 pt-2">
      <Button
        type="button"
        variant="secondary"
        size="icon"
        className="h-7 w-7 bg-white/80"
        onClick={onMoveUp}
        disabled={busy || !canMoveUp}
        aria-label={`Move page ${page.position} up within its section`}
        title={canMoveUp ? "Move up" : "Already the first page in this section"}
      >
        <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="icon"
        className="h-7 w-7 bg-white/80"
        onClick={onMoveDown}
        disabled={busy || !canMoveDown}
        aria-label={`Move page ${page.position} down within its section`}
        title={canMoveDown ? "Move down" : "Already the last page in this section"}
      >
        <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="h-7 bg-white/80 px-2 text-[11px]"
        onClick={onInsertAfter}
        disabled={busy || pending}
        aria-label={`Insert a page after page ${page.position}`}
      >
        <Plus className="h-3.5 w-3.5" aria-hidden="true" />
        Insert after
      </Button>
      {page.deletable && page.pageType === "BODY" ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="ml-auto h-7 w-7 text-danger hover:bg-danger-soft"
          onClick={onDelete}
          disabled={busy || pending}
          aria-label={`Delete page ${page.position}: ${page.title}`}
          title="Delete this page"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      ) : null}
    </div>
  );
}

interface NoteCommonProps {
  page: OutlinePageDTO;
  editingPageId: string | null;
  titleDraft: string;
  titleError: string | null;
  busy: boolean;
  pendingPageId: string | null;
  callbacks: NoteCallbacks;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}

export function BodyStickyNote({
  page,
  group,
  indexInSection,
  sectionSize,
  editingPageId,
  titleDraft,
  titleError,
  busy,
  pendingPageId,
  callbacks,
  onKeyDown,
  sortable,
}: NoteCommonProps & {
  group: OutlineSectionGroup;
  indexInSection: number;
  sectionSize: number;
  sortable: {
    setNodeRef: (element: HTMLElement | null) => void;
    attributes: DraggableAttributes;
    listeners: Record<string, Function> | undefined;
    transform: Transform | null;
    transition: string | undefined;
    isDragging: boolean;
  };
}) {
  const editing = editingPageId === page.pageId;
  const pending = pendingPageId === page.pageId;
  const canMoveUp = indexInSection > 0;
  const canMoveDown = indexInSection >= 0 && indexInSection < sectionSize - 1;

  return (
    <article
      ref={sortable.setNodeRef}
      data-note-id={page.pageId}
      tabIndex={0}
      role="group"
      aria-label={`Page ${page.position}: ${page.title}. Section ${group.title}. ${
        page.keyPoints.length
      } key points. Use Alt plus Arrow Up or Arrow Down to reorder within the section.`}
      className={cn(
        "relative flex min-w-0 flex-col rounded-xl border border-amber-200 bg-accent-soft p-3 text-[#3c3410] shadow-sm outline-none transition-shadow",
        "focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
        sortable.isDragging && "z-20 opacity-70 shadow-[var(--sh-3)]",
        pending && "opacity-70",
        editing && "ring-2 ring-brand/40",
      )}
      style={{
        transform: sortable.transform
          ? `translate3d(${sortable.transform.x}px, ${sortable.transform.y}px, 0) scaleX(${sortable.transform.scaleX}) scaleY(${sortable.transform.scaleY})`
          : undefined,
        transition: sortable.transition,
      }}
      onKeyDown={onKeyDown}
    >
      <div className="flex items-start gap-1.5">
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0 cursor-grab touch-none text-[#3c3410]/70 hover:bg-white/60 active:cursor-grabbing"
          aria-label={`Drag page ${page.position} to reorder. Press Space, then use arrow keys.`}
          title="Drag to reorder"
          {...(sortable.attributes as unknown as ButtonHTMLAttributes<HTMLButtonElement>)}
          {...(sortable.listeners as unknown as ButtonHTMLAttributes<HTMLButtonElement> | undefined)}
          disabled={busy || editing}
        >
          <GripVertical className="h-4 w-4" aria-hidden="true" />
        </Button>
        <PageNumber page={page} pending={pending} fixed={false} />
        <Badge tone="neutral" className="ml-auto bg-white/70 text-[10px] text-[#3c3410]">
          Body
        </Badge>
      </div>

      <div className="mt-2 flex min-w-0 items-start">
        <NoteTitle
          page={page}
          editing={editing}
          titleDraft={titleDraft}
          titleError={titleError}
          busy={busy}
          onStartEdit={callbacks.onStartEdit}
          onTitleDraftChange={callbacks.onTitleDraftChange}
          onSaveTitle={callbacks.onSaveTitle}
          onCancelEdit={callbacks.onCancelEdit}
        />
      </div>
      <NoteKeyPoints page={page} fixed={false} />
      <NoteActions
        page={page}
        busy={busy}
        pending={pending}
        canMoveUp={canMoveUp}
        canMoveDown={canMoveDown}
        onMoveUp={callbacks.onMoveUp}
        onMoveDown={callbacks.onMoveDown}
        onInsertAfter={callbacks.onInsertAfter}
        onDelete={callbacks.onDelete}
      />
    </article>
  );
}

export function FixedStickyNote({
  page,
  label,
  editingPageId,
  titleDraft,
  titleError,
  busy,
  pendingPageId,
  callbacks,
}: NoteCommonProps & { label: string }) {
  const editing = editingPageId === page.pageId;
  const pending = pendingPageId === page.pageId;
  return (
    <article
      data-note-id={page.pageId}
      tabIndex={0}
      role="group"
      aria-label={`${label} page ${page.position}: ${page.title}. Fixed page; title can be edited but the page cannot be moved or deleted.`}
      className={cn(
        "relative flex min-w-0 flex-col rounded-xl border border-line-strong bg-surface-2 p-3 text-ink shadow-sm outline-none",
        "focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
        pending && "opacity-70",
        editing && "ring-2 ring-brand/40",
      )}
    >
      <div className="flex items-start gap-1.5">
        <PageNumber page={page} pending={pending} fixed />
        <Badge tone="brand" className="ml-auto text-[10px]">
          {label}
        </Badge>
      </div>
      <div className="mt-2 flex min-w-0 items-start">
        <NoteTitle
          page={page}
          editing={editing}
          titleDraft={titleDraft}
          titleError={titleError}
          busy={busy}
          onStartEdit={callbacks.onStartEdit}
          onTitleDraftChange={callbacks.onTitleDraftChange}
          onSaveTitle={callbacks.onSaveTitle}
          onCancelEdit={callbacks.onCancelEdit}
        />
      </div>
      <NoteKeyPoints page={page} fixed />
      <p className="mt-3 border-t border-line pt-2 text-[11px] text-faint">
        Fixed position · no move or delete action
      </p>
    </article>
  );
}
