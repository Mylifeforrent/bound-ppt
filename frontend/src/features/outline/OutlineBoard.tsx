import { useCallback, useEffect, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  pointerWithin,
  useDroppable,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { AlertTriangle, Loader2, Lock, Plus, RefreshCw, Sparkles } from "lucide-react";
import type { OutlineDTO, OutlinePageDTO, ProjectSnapshotDTO } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { ErrorCard, Skeleton, Spinner } from "@/components/ui/dialog";
import { stageRoute } from "@/hooks/useProjectData";
import { errorText, messageFor } from "@/lib/messages";
import { cn, pluralize } from "@/lib/utils";
import { useOutlineBoard } from "./useOutlineBoard";
import { isValidationError } from "./errors";
import { InsertPageDialog } from "./InsertPageDialog";
import { OutlineConfirmBar } from "./OutlineConfirmBar";
import {
  BodyStickyNote,
  FixedStickyNote,
  type NoteCallbacks,
} from "./StickyNote";
import {
  adjacentSectionTarget,
  deviationWarning,
  nextMoveTarget,
  pageCountLabel,
  type OutlineDroppableData,
  type OutlineSectionGroup,
  resolveDropTarget,
} from "./types";

type InsertTarget =
  | { mode: "after"; page: OutlinePageDTO; group: OutlineSectionGroup }
  | { mode: "section"; group: OutlineSectionGroup };

const collisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args);
  if (pointerCollisions.length > 0) return pointerCollisions;
  return closestCenter(args);
};

const STAGE_LABEL: Record<string, string> = {
  INTAKE: "material intake",
  RESEARCH: "research",
  OUTLINE: "outline",
  PLAN: "plan draft",
  STYLE: "style selection",
  DESIGN: "design draft",
};

function announceMove(direction: "up" | "down", page: OutlinePageDTO, group: OutlineSectionGroup) {
  return `Moved page ${page.position} ${direction} in ${group.title}.`;
}

export function OutlineBoard({
  projectId,
  snapshot,
}: {
  projectId: string;
  snapshot: ProjectSnapshotDTO;
}) {
  const board = useOutlineBoard({ projectId, snapshot });
  const [editingPageId, setEditingPageId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [titleError, setTitleError] = useState<string | null>(null);
  const [insertTarget, setInsertTarget] = useState<InsertTarget | null>(null);
  const [insertError, setInsertError] = useState<string | null>(null);
  const [focusTarget, setFocusTarget] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [draggingPageId, setDraggingPageId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const outline = board.outline;

  useEffect(() => {
    if (!focusTarget) return;
    const frame = window.requestAnimationFrame(() => {
      const element = document.querySelector<HTMLElement>(
        `[data-note-id="${focusTarget}"]`,
      );
      if (element) {
        element.focus();
        setFocusTarget(null);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusTarget, outline]);

  useEffect(() => {
    if (!editingPageId || !outline) return;
    if (!outline.pages.some((page) => page.pageId === editingPageId)) {
      setEditingPageId(null);
      setTitleError(null);
    }
  }, [editingPageId, outline]);

  const scheduleFocus = useCallback((pageId: string) => {
    setFocusTarget(pageId);
  }, []);

  const beginEdit = useCallback(
    (page: OutlinePageDTO) => {
      if (board.busy) return;
      board.pauseCountdown("edit");
      setEditingPageId(page.pageId);
      setTitleDraft(page.title);
      setTitleError(null);
    },
    [board],
  );

  const cancelEdit = useCallback(() => {
    setEditingPageId(null);
    setTitleError(null);
  }, []);

  const saveTitle = useCallback(
    (page: OutlinePageDTO) => {
      if (board.busy) return;
      const title = titleDraft.trim();
      if (!title) {
        setTitleError(messageFor("ui.form.title_required"));
        return;
      }
      if (title === page.title) {
        setEditingPageId(null);
        setTitleError(null);
        return;
      }
      board.actions.saveTitle(page.pageId, title, {
        onSuccess: () => {
          setEditingPageId(null);
          setTitleError(null);
          scheduleFocus(page.pageId);
          setAnnouncement(`Title saved for page ${page.position}.`);
        },
        onError: (error) => {
          if (isValidationError(error)) {
            setTitleError(errorText(error));
            return;
          }
          setEditingPageId(null);
          setTitleError(null);
        },
      });
    },
    [board.actions, board.busy, scheduleFocus, titleDraft],
  );

  const moveWithin = useCallback(
    (page: OutlinePageDTO, group: OutlineSectionGroup, direction: "up" | "down") => {
      const target = nextMoveTarget(group, page, direction);
      if (!target) {
        setAnnouncement(
          `Page ${page.position} is already at the ${
            direction === "up" ? "start" : "end"
          } of ${group.title}.`,
        );
        return;
      }
      setAnnouncement(announceMove(direction, page, group));
      scheduleFocus(page.pageId);
      board.actions.move(page.pageId, target, {
        onSuccess: () => scheduleFocus(page.pageId),
      });
    },
    [board.actions, scheduleFocus],
  );

  const moveToAdjacentSection = useCallback(
    (
      page: OutlinePageDTO,
      group: OutlineSectionGroup,
      direction: "left" | "right",
    ) => {
      const target = adjacentSectionTarget(board.groups, group.sectionKey, direction);
      if (!target) {
        setAnnouncement(`There is no section to the ${direction} of ${group.title}.`);
        return;
      }
      setAnnouncement(`Moving page ${page.position} to the ${direction} section.`);
      scheduleFocus(page.pageId);
      board.actions.move(page.pageId, target, {
        onSuccess: () => scheduleFocus(page.pageId),
      });
    },
    [board.actions, board.groups, scheduleFocus],
  );

  const handleNoteKeyDown = useCallback(
    (page: OutlinePageDTO, group: OutlineSectionGroup, event: KeyboardEvent<HTMLElement>) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, button, a, [contenteditable='true']")) {
        return;
      }
      const vertical = event.altKey && !event.shiftKey && (event.key === "ArrowUp" || event.key === "ArrowDown");
      const horizontal =
        event.altKey && event.shiftKey && (event.key === "ArrowLeft" || event.key === "ArrowRight");
      if (!vertical && !horizontal) return;
      event.preventDefault();
      if (vertical) {
        moveWithin(page, group, event.key === "ArrowUp" ? "up" : "down");
      } else {
        moveToAdjacentSection(page, group, event.key === "ArrowLeft" ? "left" : "right");
      }
    },
    [moveToAdjacentSection, moveWithin],
  );

  const openInsertAfter = useCallback(
    (page: OutlinePageDTO, group: OutlineSectionGroup) => {
      if (board.busy) return;
      board.pauseCountdown("edit");
      setInsertError(null);
      setInsertTarget({ mode: "after", page, group });
    },
    [board],
  );

  const openInsertSection = useCallback(
    (group: OutlineSectionGroup) => {
      if (board.busy) return;
      board.pauseCountdown("edit");
      setInsertError(null);
      setInsertTarget({ mode: "section", group });
    },
    [board],
  );

  const confirmDelete = useCallback(
    (page: OutlinePageDTO) => {
      if (!page.deletable || page.pageType !== "BODY") return;
      const confirmed = window.confirm(
        `Delete “${page.title}”? The page, its plan draft, and its design for this page are removed. This cannot be undone here.`,
      );
      if (!confirmed) return;
      board.actions.removePage(page.pageId, {
        onSuccess: (result) => {
          const pages = [...result.outline.pages].sort((a, b) => a.position - b.position);
          const next = pages.find((candidate) => candidate.pageType === "BODY") ?? pages[0];
          if (next) scheduleFocus(next.pageId);
          setAnnouncement(`Page “${page.title}” deleted.`);
        },
      });
    },
    [board.actions, scheduleFocus],
  );

  const handleInsertSubmit = useCallback(
    (title: string, keyPoints: string[]) => {
      if (!insertTarget || board.inserting) return;
      const group =
        board.groups.find((candidate) => candidate.sectionKey === insertTarget.group.sectionKey) ??
        insertTarget.group;
      const afterPageId =
        insertTarget.mode === "after"
          ? insertTarget.page.pageId
          : group.pages[group.pages.length - 1]?.pageId;
      board.actions.insert(
        { sectionKey: group.sectionKey, afterPageId, title, keyPoints },
        {
          onSuccess: (result) => {
            setInsertTarget(null);
            setInsertError(null);
            scheduleFocus(result.pageId);
            setAnnouncement(`Inserted a new page in ${group.title}.`);
          },
          onError: (error) => {
            if (isValidationError(error)) setInsertError(errorText(error));
          },
        },
      );
    },
    [board.actions, board.groups, board.inserting, insertTarget, scheduleFocus],
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      board.pauseCountdown("edit");
      setDraggingPageId(String(event.active.id));
      setAnnouncement("Drag started. Drop on a note to insert before it, or on a section end zone to append.");
    },
    [board],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setDraggingPageId(null);
      const pageId = String(event.active.id);
      const overData = event.over?.data.current as OutlineDroppableData | undefined;
      if (!board.outline) return;
      const page = board.outline.pages.find((candidate) => candidate.pageId === pageId);
      if (!page) return;
      const group = board.groups.find((candidate) => candidate.sectionKey === page.sectionKey);
      if (!group) return;
      const target = resolveDropTarget(pageId, overData, board.groups);
      if (!target) return;
      const index = group.pages.findIndex((candidate) => candidate.pageId === pageId);
      if (target.toSectionKey === page.sectionKey) {
        const currentNext = index >= 0 ? group.pages[index + 1]?.pageId : undefined;
        if (target.beforePageId && target.beforePageId === currentNext) return;
        if (
          target.toPosition !== undefined &&
          index === group.pages.length - 1 &&
          target.toPosition >= group.pages.length
        ) {
          return;
        }
      }
      board.actions.move(pageId, target, {
        onSuccess: () => {
          scheduleFocus(pageId);
          setAnnouncement("Outline updated.");
        },
        onError: () => setAnnouncement("The move could not be applied."),
      });
    },
    [board, scheduleFocus],
  );

  if (board.isLoading) return <OutlineBoardSkeleton />;

  if (board.outlineNotFound) {
    return (
      <OutlineEmptyState
        board={board}
        onGenerate={board.actions.generate}
        generating={board.generating}
      />
    );
  }

  if (board.queryError && !outline) {
    return (
      <ErrorCard
        message={errorText(board.queryError) || "The outline could not be loaded."}
        reference={
          board.queryError && typeof board.queryError === "object" && "requestId" in board.queryError
            ? (board.queryError as { requestId?: string }).requestId
            : undefined
        }
        onRetry={() => void board.outlineQuery.refetch()}
      />
    );
  }

  if (!outline) return <OutlineBoardSkeleton />;

  const fixed = board.fixed;
  const counts = outline.counts;
  const warned = deviationWarning(counts);
  const otherBlockers = board.stageBlockers.filter(
    (blocker) => !(board.profileDirty && blocker.code === "profile_dirty"),
  );

  return (
    <div className="min-w-0">
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>

      {board.profileDirty ? (
        <div
          role="alert"
          className="mb-4 flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-amber-200 bg-warn-soft p-4"
        >
          <div className="flex items-start gap-3">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-ink">Update the requirements profile first</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">
                The profile changed after this outline was generated. Update and reconfirm the profile
                before the outline can advance to the plan draft.
              </p>
            </div>
          </div>
          <Link
            to={stageRoute(projectId, "RESEARCH")}
            className="inline-flex min-h-[36px] items-center rounded-xl border border-amber-300 bg-white px-3 text-xs font-semibold text-warn hover:bg-warn-soft"
          >
            Open research
          </Link>
        </div>
      ) : null}

      {otherBlockers.length > 0 ? (
        <div role="alert" className="mb-4 space-y-2 rounded-2xl border border-amber-200 bg-warn-soft p-4">
          <p className="text-sm font-semibold text-ink">This outline is not ready to advance</p>
          <ul className="space-y-1.5">
            {otherBlockers.map((blocker) => (
              <li key={`${blocker.code}-${blocker.messageKey}`} className="text-xs text-muted">
                {messageFor(blocker.messageKey)}
                {blocker.stage ? (
                  <>
                    {" "}
                    <Link
                      to={stageRoute(projectId, blocker.stage)}
                      className="font-semibold text-warn underline"
                    >
                      Open {STAGE_LABEL[blocker.stage] ?? "previous stage"}
                    </Link>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {board.commandError ? (
        <div
          role="alert"
          className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-xs text-danger"
        >
          <span>{board.commandError}</span>
          <button
            type="button"
            className="rounded-md border border-red-300 bg-white px-2 py-1 font-semibold"
            onClick={board.clearCommandError}
          >
            Dismiss
          </button>
        </div>
      ) : null}

      <section aria-labelledby="outline-board-title" className="app-card p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="outline-board-title" className="text-lg font-semibold text-ink">
              Sticky-note board
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              {pageCountLabel(counts)}
              {counts.agreedPageCount > 0 ? ` · agreed ${counts.agreedPageCount}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={outline.confirmed ? "ok" : "warn"}>
              {outline.confirmed ? "Confirmed" : "Not confirmed"}
            </Badge>
            {warned ? (
              <Badge tone="warn">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                Page count off by {Math.abs(counts.deviation)}
              </Badge>
            ) : null}
            {board.activeOutlineJob ? (
              <Badge tone="brand">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                Updating
              </Badge>
            ) : null}
          </div>
        </div>

        {warned ? (
          <p
            role="status"
            className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-warn-soft px-3 py-2 text-xs font-medium text-warn"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              The outline has {pluralize(counts.pages, "page")} against an agreed{" "}
              {pluralize(counts.agreedPageCount, "page")} (deviation {counts.deviation > 0 ? "+" : ""}
              {counts.deviation}). This warning does not block confirmation.
            </span>
          </p>
        ) : null}

        {board.activeOutlineJob ? (
          <p
            role="status"
            className="mt-3 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-medium text-brand-strong"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            The agent is updating this outline. The saved version stays visible until the new one lands.
          </p>
        ) : null}

        <OutlineConfirmBar
          outline={outline}
          modeAuto={board.modeAuto}
          autoEligible={board.countdownEligible}
          blocked={board.blocked}
          advancing={board.advancing}
          advanceError={board.advanceError}
          pauseReason={board.countdown.pausedReason}
          running={board.countdown.running}
          remainingSeconds={board.countdown.remainingSeconds}
          progress={board.countdown.progress}
          onPause={() => board.pauseCountdown("user")}
          onResume={board.resumeCountdown}
          onConfirm={() => void board.confirmNow()}
          onContinue={board.continueToPlan}
        />

        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetection}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setDraggingPageId(null)}
        >
          <div className="mt-5 space-y-5">
            {fixed && (fixed.cover || fixed.toc) ? (
              <div role="group" aria-label="Fixed pages" className="grid gap-3 sm:grid-cols-2">
                {fixed.cover ? (
                  <FixedStickyNote
                    page={fixed.cover}
                    label="Cover"
                    editingPageId={editingPageId}
                    titleDraft={titleDraft}
                    titleError={titleError}
                    busy={board.busy}
                    pendingPageId={board.pendingPageId}
                    callbacks={noteCallbacks(
                      fixed.cover,
                      groupForPage(board.groups, fixed.cover) ?? emptyGroup(fixed.cover),
                      beginEdit,
                      setTitleDraft,
                      saveTitle,
                      cancelEdit,
                      moveWithin,
                      openInsertAfter,
                      confirmDelete                    )}
                    onKeyDown={() => undefined}
                  />
                ) : null}
                {fixed.toc ? (
                  <FixedStickyNote
                    page={fixed.toc}
                    label="Contents"
                    editingPageId={editingPageId}
                    titleDraft={titleDraft}
                    titleError={titleError}
                    busy={board.busy}
                    pendingPageId={board.pendingPageId}
                    callbacks={noteCallbacks(
                      fixed.toc,
                      groupForPage(board.groups, fixed.toc) ?? emptyGroup(fixed.toc),
                      beginEdit,
                      setTitleDraft,
                      saveTitle,
                      cancelEdit,
                      moveWithin,
                      openInsertAfter,
                      confirmDelete                    )}
                    onKeyDown={() => undefined}
                  />
                ) : null}
              </div>
            ) : null}

            {board.groups.map((group) => (
              <SectionGroupView
                key={group.sectionKey}
                group={group}
                editingPageId={editingPageId}
                titleDraft={titleDraft}
                titleError={titleError}
                busy={board.busy}
                pendingPageId={board.pendingPageId}
                onStartEdit={beginEdit}
                onTitleDraftChange={setTitleDraft}
                onSaveTitle={saveTitle}
                onCancelEdit={cancelEdit}
                onMoveWithin={moveWithin}
                onInsertAfter={openInsertAfter}
                onInsertSection={openInsertSection}
                onDelete={confirmDelete}
                onNoteKeyDown={handleNoteKeyDown}
              />
            ))}

            {fixed?.end ? (
              <div role="group" aria-label="Closing page">
                <h3 className="mb-2 text-sm font-semibold text-ink">Closing</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FixedStickyNote
                    page={fixed.end}
                    label="Closing"
                    editingPageId={editingPageId}
                    titleDraft={titleDraft}
                    titleError={titleError}
                    busy={board.busy}
                    pendingPageId={board.pendingPageId}
                    callbacks={noteCallbacks(
                      fixed.end,
                      groupForPage(board.groups, fixed.end) ?? emptyGroup(fixed.end),
                      beginEdit,
                      setTitleDraft,
                      saveTitle,
                      cancelEdit,
                      moveWithin,
                      openInsertAfter,
                      confirmDelete                    )}
                    onKeyDown={() => undefined}
                  />
                </div>
              </div>
            ) : null}

            {board.groups.length === 0 && !fixed?.cover && !fixed?.toc && !fixed?.end ? (
              <p className="rounded-xl border border-dashed border-line-strong bg-surface-2 p-4 text-sm text-muted">
                This outline has no pages. Use the outline actions to regenerate it.
              </p>
            ) : null}
          </div>
        </DndContext>

        <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-3 text-[11px] text-muted">
          <span>
            <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">Alt</kbd>{" "}
            + <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">↑</kbd>/
            <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">↓</kbd>{" "}
            moves a focused note within its section.
          </span>
          <span>
            <kbd className="rounded border border-line bg-white px-1 py-0.5 font-sans text-[10px]">Shift</kbd>{" "}
            + Alt + ←/→ moves it to the end of an adjacent section.
          </span>
          <span>Drag a note onto another note to insert before it.</span>
          {draggingPageId ? <span className="font-semibold text-brand-strong">Dragging…</span> : null}
        </p>
      </section>

      <InsertPageDialog
        target={
          insertTarget
            ? {
                mode: insertTarget.mode,
                sectionTitle: insertTarget.group.title,
                afterTitle:
                  insertTarget.mode === "after" ? insertTarget.page.title : undefined,
              }
            : null
        }
        pending={board.inserting}
        error={insertError}
        onClose={() => {
          setInsertTarget(null);
          setInsertError(null);
        }}
        onSubmit={handleInsertSubmit}
      />
    </div>
  );
}

function groupForPage(
  groups: OutlineSectionGroup[],
  page: OutlinePageDTO,
): OutlineSectionGroup | undefined {
  return groups.find((group) => group.sectionKey === page.sectionKey);
}

function emptyGroup(page: OutlinePageDTO): OutlineSectionGroup {
  return {
    sectionKey: page.sectionKey,
    title: page.sectionKey,
    position: page.position,
    pages: [],
  };
}

function noteCallbacks(
  page: OutlinePageDTO,
  group: OutlineSectionGroup,
  onStartEdit: (page: OutlinePageDTO) => void,
  onTitleDraftChange: (value: string) => void,
  onSaveTitle: (page: OutlinePageDTO) => void,
  onCancelEdit: () => void,
  onMoveWithin: (page: OutlinePageDTO, group: OutlineSectionGroup, direction: "up" | "down") => void,
  onInsertAfter: (page: OutlinePageDTO, group: OutlineSectionGroup) => void,
  onDelete: (page: OutlinePageDTO) => void
): NoteCallbacks {
  return {
    onStartEdit,
    onTitleDraftChange,
    onSaveTitle: () => onSaveTitle(page),
    onCancelEdit,
    onMoveUp: () => onMoveWithin(page, group, "up"),
    onMoveDown: () => onMoveWithin(page, group, "down"),
    onInsertAfter: () => onInsertAfter(page, group),
    onDelete: () => onDelete(page),
  };
}

interface SectionGroupViewProps {
  group: OutlineSectionGroup;
  editingPageId: string | null;
  titleDraft: string;
  titleError: string | null;
  busy: boolean;
  pendingPageId: string | null;
  onStartEdit: (page: OutlinePageDTO) => void;
  onTitleDraftChange: (value: string) => void;
  onSaveTitle: (page: OutlinePageDTO) => void;
  onCancelEdit: () => void;
  onMoveWithin: (page: OutlinePageDTO, group: OutlineSectionGroup, direction: "up" | "down") => void;
  onInsertAfter: (page: OutlinePageDTO, group: OutlineSectionGroup) => void;
  onInsertSection: (group: OutlineSectionGroup) => void;
  onDelete: (page: OutlinePageDTO) => void;
  onNoteKeyDown: (
    page: OutlinePageDTO,
    group: OutlineSectionGroup,
    event: KeyboardEvent<HTMLElement>,
  ) => void;
}

function SectionGroupView({
  group,
  editingPageId,
  titleDraft,
  titleError,
  busy,
  pendingPageId,
  onStartEdit,
  onTitleDraftChange,
  onSaveTitle,
  onCancelEdit,
  onMoveWithin,
  onInsertAfter,
  onInsertSection,
  onDelete,
  onNoteKeyDown,
}: SectionGroupViewProps) {
  return (
    <section
      aria-label={`Section ${group.title}`}
      className="rounded-xl border border-line bg-surface-2/70 p-3"
    >
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink">{group.title}</h3>
          <p className="text-[11px] text-muted">
            {pluralize(group.pages.length, "page")} in this section
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => onInsertSection(group)}
          disabled={busy}
          aria-label={`Insert a page at the end of ${group.title}`}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          Insert page
        </Button>
      </div>

      <SortableContext
        items={group.pages.map((page) => page.pageId)}
        strategy={rectSortingStrategy}
      >
        <div className="grid gap-3 sm:grid-cols-2 min-[1180px]:grid-cols-3">
          {group.pages.map((page, index) => (
            <SortableBodyNote
              key={page.pageId}
              page={page}
              group={group}
              indexInSection={index}
              sectionSize={group.pages.length}
              editingPageId={editingPageId}
              titleDraft={titleDraft}
              titleError={titleError}
              busy={busy}
              pendingPageId={pendingPageId}
              callbacks={noteCallbacks(
                page,
                group,
                onStartEdit,
                onTitleDraftChange,
                onSaveTitle,
                onCancelEdit,
                onMoveWithin,
                onInsertAfter,
                onDelete,
              )}
              onKeyDown={(event) => onNoteKeyDown(page, group, event)}
            />
          ))}
          <SectionDropZone group={group} hasPages={group.pages.length > 0} />
        </div>
      </SortableContext>

      {group.pages.length === 0 ? (
        <p className="mt-2 text-xs text-muted">
          No pages in this section yet. Insert one or drop a note from another section.
        </p>
      ) : null}
    </section>
  );
}

function SortableBodyNote({
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
}: {
  page: OutlinePageDTO;
  group: OutlineSectionGroup;
  indexInSection: number;
  sectionSize: number;
  editingPageId: string | null;
  titleDraft: string;
  titleError: string | null;
  busy: boolean;
  pendingPageId: string | null;
  callbacks: NoteCallbacks;
  onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
}) {
  const sortable = useSortable({
    id: page.pageId,
    data: { type: "page", pageId: page.pageId, sectionKey: group.sectionKey },
    disabled: busy || editingPageId === page.pageId,
  });
  return (
    <BodyStickyNote
      page={page}
      group={group}
      indexInSection={indexInSection}
      sectionSize={sectionSize}
      editingPageId={editingPageId}
      titleDraft={titleDraft}
      titleError={titleError}
      busy={busy}
      pendingPageId={pendingPageId}
      callbacks={callbacks}
      onKeyDown={onKeyDown}
      sortable={sortable}
    />
  );
}

function SectionDropZone({
  group,
  hasPages,
}: {
  group: OutlineSectionGroup;
  hasPages: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `outline-section-${group.sectionKey}`,
    data: { type: "section", sectionKey: group.sectionKey } satisfies OutlineDroppableData,
  });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "grid min-h-[104px] place-items-center rounded-xl border border-dashed p-3 text-center text-[11px] font-medium transition-colors",
        isOver
          ? "border-brand bg-brand-soft text-brand-strong"
          : "border-line-strong bg-white/60 text-faint",
      )}
    >
      {hasPages ? "Drop here to append to this section" : "Drop a note here to start this section"}
    </div>
  );
}

function OutlineEmptyState({
  board,
  onGenerate,
  generating,
}: {
  board: ReturnType<typeof useOutlineBoard>;
  onGenerate: () => void;
  generating: boolean;
}) {
  const visibleBlockers = board.stageBlockers.filter(
    (blocker) => !(board.profileDirty && blocker.code === "profile_dirty"),
  );
  const canGenerate = !board.profileDirty && visibleBlockers.length === 0;
  return (
    <div className="min-w-0">
      {board.hasStreamDeltas && board.streamDeltas ? (
        <StreamingPreview deltas={board.streamDeltas} />
      ) : null}

      <section aria-labelledby="outline-empty-title" className="app-card mt-4 p-6">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-strong">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 id="outline-empty-title" className="text-lg font-semibold text-ink">
              No outline yet
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              The agent turns the requirements profile, interview answers, and selected sources into a
              page-by-page outline. Generate it to open the sticky-note board.
            </p>
          </div>
        </div>

        {board.profileDirty ? (
          <div className="mt-4 rounded-xl border border-amber-200 bg-warn-soft p-4">
            <p className="text-sm font-medium text-ink">
              Update the requirements profile before generating the outline.
            </p>
            <Link
              to={stageRoute(board.projectId, "RESEARCH")}
              className="mt-2 inline-flex font-semibold text-warn underline"
            >
              Open research
            </Link>
          </div>
        ) : null}

        {visibleBlockers.length > 0 ? (
          <ul className="mt-4 space-y-1.5">
            {visibleBlockers.map((blocker) => (
              <li
                key={`${blocker.code}-${blocker.messageKey}`}
                className="rounded-lg border border-amber-200 bg-warn-soft px-3 py-2 text-xs text-warn"
              >
                {messageFor(blocker.messageKey)}
                {blocker.stage ? (
                  <>
                    {" "}
                    <Link
                      to={stageRoute(board.projectId, blocker.stage)}
                      className="font-semibold underline"
                    >
                      Open {STAGE_LABEL[blocker.stage] ?? "previous stage"}
                    </Link>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {board.activeOutlineJob ? (
          <p
            role="status"
            className="mt-4 flex items-center gap-2 rounded-xl border border-indigo-200 bg-brand-soft px-3 py-2 text-xs font-medium text-brand-strong"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            Generating the outline… Notes will stream in and be replaced by the saved outline.
          </p>
        ) : null}

        {board.generationError ? (
          <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-danger-soft p-3 text-xs text-danger">
            <p className="font-semibold">The outline could not be generated.</p>
            <p className="mt-0.5 leading-snug">{board.generationError}</p>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {canGenerate ? (
            <Button
              onClick={onGenerate}
              disabled={generating || Boolean(board.activeOutlineJob) || board.hasStreamDeltas}
            >
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              )}
              {generating
                ? "Starting generation…"
                : board.generationError
                  ? "Retry outline generation"
                  : "Generate outline"}
            </Button>
          ) : (
            <span className="text-xs text-muted">
              Update the profile and resolve the blockers above before generating the outline.
            </span>
          )}
        </div>
      </section>
    </div>
  );
}

function StreamingPreview({
  deltas,
}: {
  deltas: NonNullable<ReturnType<typeof useOutlineBoard>["streamDeltas"]>;
}) {
  return (
    <section
      aria-labelledby="outline-stream-title"
      aria-live="off"
      className="app-card border-indigo-200 bg-brand-soft/40 p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="brand">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
          Streaming
        </Badge>
        <h2 id="outline-stream-title" className="text-sm font-semibold text-ink">
          Agent is drafting the outline
        </h2>
      </div>
      <p className="mt-1 text-xs text-muted">
        These notes are a live, unsaved preview. The saved outline replaces them when generation
        completes.
      </p>
      {deltas.sections.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {deltas.sections.map((section) => (
            <Badge key={section.sectionKey} tone="neutral">
              {section.title}
            </Badge>
          ))}
        </div>
      ) : null}
      {deltas.pages.length > 0 ? (
        <ol className="mt-3 grid gap-2 sm:grid-cols-2 min-[1180px]:grid-cols-3">
          {deltas.pages.map((page, index) => (
            <li
              key={`${page.title}-${index}`}
              className="rounded-xl border border-amber-200 bg-accent-soft px-3 py-2 text-xs font-medium text-[#3c3410]"
            >
              {page.title}
            </li>
          ))}
        </ol>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2 min-[1180px]:grid-cols-3" aria-hidden="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-20 w-full bg-white/70" />
          ))}
        </div>
      )}
    </section>
  );
}

function OutlineBoardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the outline board">
      <div className="sr-only">
        <Spinner label="Loading outline" />
      </div>
      <div className="app-card p-5">
        <div className="flex items-center justify-between gap-3">
          <Skeleton className="h-5 w-44" />
          <Skeleton className="h-6 w-28" />
        </div>
        <Skeleton className="mt-3 h-16 w-full" />
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 min-[1180px]:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-32 w-full" />
          ))}
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs text-muted">
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
        Loading the saved outline…
      </div>
    </div>
  );
}
