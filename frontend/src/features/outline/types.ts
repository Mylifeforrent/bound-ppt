import type { OutlineDTO, OutlinePageDTO } from "@/api/types";

export interface MoveTarget {
  toSectionKey: string;
  beforePageId?: string;
  toPosition?: number;
}

export interface InsertPageInput {
  sectionKey: string;
  afterPageId?: string;
  title: string;
  keyPoints: string[];
}

export interface OutlineSectionGroup {
  sectionKey: string;
  title: string;
  position: number;
  pages: OutlinePageDTO[];
}

export interface FixedPageSlots {
  cover: OutlinePageDTO | null;
  toc: OutlinePageDTO | null;
  end: OutlinePageDTO | null;
}

export interface OutlineDropPageData {
  type: "page";
  pageId: string;
  sectionKey: string;
}

export interface OutlineDropSectionData {
  type: "section";
  sectionKey: string;
}

export type OutlineDroppableData = OutlineDropPageData | OutlineDropSectionData;

const FIXED_ORDER: Record<string, number> = { COVER: 0, TOC: 1, END: 3 };

export function isBodyPage(page: OutlinePageDTO): boolean {
  return page.pageType === "BODY";
}

export function isFixedPage(page: OutlinePageDTO): boolean {
  return page.pageType !== "BODY";
}

export function sortByPosition<T extends { position: number }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.position - b.position);
}

/**
 * Groups body pages by their outline section. Sections with no body pages are
 * kept so page insertion and drop zones remain available. Unknown section keys
 * found on pages are appended rather than dropped.
 */
export function buildSectionGroups(outline: OutlineDTO): OutlineSectionGroup[] {
  const groups = new Map<string, OutlineSectionGroup>();
  const sortedSections = sortByPosition(outline.sections);
  sortedSections.forEach((section, index) => {
    groups.set(section.sectionKey, {
      sectionKey: section.sectionKey,
      title: section.title,
      position: section.position ?? index,
      pages: [],
    });
  });
  for (const page of sortByPosition(outline.pages)) {
    if (!isBodyPage(page)) continue;
    let group = groups.get(page.sectionKey);
    if (!group) {
      group = {
        sectionKey: page.sectionKey,
        title: page.sectionKey,
        position: sortedSections.length + groups.size,
        pages: [],
      };
      groups.set(page.sectionKey, group);
    }
    group.pages.push(page);
  }
  for (const group of groups.values()) {
    group.pages.sort((a, b) => a.position - b.position);
  }
  return [...groups.values()].sort((a, b) => a.position - b.position);
}

export function fixedPageSlots(outline: OutlineDTO): FixedPageSlots {
  const pages = sortByPosition(outline.pages);
  return {
    cover: pages.find((page) => page.pageType === "COVER") ?? null,
    toc: pages.find((page) => page.pageType === "TOC") ?? null,
    end: pages.find((page) => page.pageType === "END") ?? null,
  };
}

export function pageCountLabel(counts: OutlineDTO["counts"]): string {
  return `${counts.pages} ${counts.pages === 1 ? "page" : "pages"} · ${counts.sections} ${
    counts.sections === 1 ? "section" : "sections"
  }`;
}

export function deviationWarning(counts: OutlineDTO["counts"]): boolean {
  return counts.deviationWarning || Math.abs(counts.deviation) > 2;
}

/**
 * Computes a local preview of a move so drag/drop responds immediately. The
 * server-authored outline always replaces this preview after the command.
 */
export function buildOptimisticMove(
  outline: OutlineDTO,
  pageId: string,
  target: MoveTarget,
): OutlineDTO | null {
  const moving = outline.pages.find((page) => page.pageId === pageId);
  if (!moving || moving.pageType !== "BODY") return null;

  const groups = buildSectionGroups(outline).map((group) => ({
    ...group,
    pages: group.pages.filter((page) => page.pageId !== pageId),
  }));
  const targetGroup = groups.find((group) => group.sectionKey === target.toSectionKey);
  if (!targetGroup) return null;

  let insertAt = targetGroup.pages.length;
  if (target.beforePageId) {
    const index = targetGroup.pages.findIndex((page) => page.pageId === target.beforePageId);
    insertAt = index >= 0 ? index : targetGroup.pages.length;
  } else if (target.toPosition !== undefined) {
    // toPosition is the 1-based destination slot; clamp for preview purposes.
    insertAt = Math.max(0, Math.min(targetGroup.pages.length, target.toPosition - 1));
  }
  targetGroup.pages.splice(insertAt, 0, { ...moving, sectionKey: target.toSectionKey });

  const fixed = sortByPosition(outline.pages).filter(isFixedPage);
  fixed.sort((a, b) => (FIXED_ORDER[a.pageType] ?? 2) - (FIXED_ORDER[b.pageType] ?? 2));
  const coverToc = fixed.filter((page) => page.pageType === "COVER" || page.pageType === "TOC");
  const end = fixed.filter((page) => page.pageType === "END");
  const ordered = [...coverToc, ...groups.flatMap((group) => group.pages), ...end].map((page, index) => ({
    ...page,
    position: index + 1,
  }));

  return { ...outline, pages: ordered };
}

export function resolveDropTarget(
  activePageId: string,
  overData: OutlineDroppableData | undefined,
  groups: OutlineSectionGroup[],
): MoveTarget | null {
  if (!overData) return null;
  if (overData.type === "page") {
    if (overData.pageId === activePageId) return null;
    return { toSectionKey: overData.sectionKey, beforePageId: overData.pageId };
  }
  const group = groups.find((item) => item.sectionKey === overData.sectionKey);
  const length = group?.pages.length ?? 0;
  return { toSectionKey: overData.sectionKey, toPosition: Math.max(1, length + 1) };
}

export function nextMoveTarget(
  group: OutlineSectionGroup,
  page: OutlinePageDTO,
  direction: "up" | "down",
): MoveTarget | null {
  const index = group.pages.findIndex((item) => item.pageId === page.pageId);
  if (index < 0) return null;
  if (direction === "up") {
    if (index === 0) return null;
    return { toSectionKey: group.sectionKey, beforePageId: group.pages[index - 1].pageId };
  }
  if (index >= group.pages.length - 1) return null;
  const afterNext = group.pages[index + 2];
  if (afterNext) {
    return { toSectionKey: group.sectionKey, beforePageId: afterNext.pageId };
  }
  return { toSectionKey: group.sectionKey, toPosition: group.pages.length + 1 };
}

export function adjacentSectionTarget(
  groups: OutlineSectionGroup[],
  sectionKey: string,
  direction: "left" | "right",
): MoveTarget | null {
  const index = groups.findIndex((group) => group.sectionKey === sectionKey);
  if (index < 0) return null;
  const next = groups[index + (direction === "right" ? 1 : -1)];
  if (!next) return null;
  return { toSectionKey: next.sectionKey, toPosition: Math.max(1, next.pages.length + 1) };
}
