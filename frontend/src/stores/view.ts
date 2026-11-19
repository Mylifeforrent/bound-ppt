import { create } from "zustand";

interface ViewState {
  selectedPageId: string | null;
  pinnedPageId: string | null;
  lastDesignPageId: string | null;
  restartOpen: boolean;
  deleteOpen: boolean;
  exportOpen: boolean;
  navOpen: boolean;
  setSelectedPage: (pageId: string | null) => void;
  setPinnedPage: (pageId: string | null) => void;
  setLastDesignPage: (pageId: string | null) => void;
  setRestartOpen: (open: boolean) => void;
  setDeleteOpen: (open: boolean) => void;
  setExportOpen: (open: boolean) => void;
  setNavOpen: (open: boolean) => void;
  resetProjectView: () => void;
}

export const useViewStore = create<ViewState>((set) => ({
  selectedPageId: null,
  pinnedPageId: null,
  lastDesignPageId: null,
  restartOpen: false,
  deleteOpen: false,
  exportOpen: false,
  navOpen: false,
  setSelectedPage: (pageId) => set({ selectedPageId: pageId }),
  setPinnedPage: (pageId) => set({ pinnedPageId: pageId }),
  setLastDesignPage: (pageId) => set({ lastDesignPageId: pageId }),
  setRestartOpen: (restartOpen) => set({ restartOpen }),
  setDeleteOpen: (deleteOpen) => set({ deleteOpen }),
  setExportOpen: (exportOpen) => set({ exportOpen }),
  setNavOpen: (navOpen) => set({ navOpen }),
  resetProjectView: () =>
    set({ selectedPageId: null, pinnedPageId: null, lastDesignPageId: null, exportOpen: false, navOpen: false }),
}));

interface StreamState {
  status: "idle" | "connecting" | "live" | "reconnecting" | "resyncing" | "closed";
  outlineDeltas: Record<string, { sections: Array<{ sectionKey: string; title: string }>; pages: Array<{ title: string; sectionKey?: string }> }>;
  setStatus: (status: StreamState["status"]) => void;
  applyOutlineDelta: (projectId: string, payload: { chunkIndex: number; delta: { sections?: any[]; pages?: any[] } }) => void;
  clearOutlineDelta: (projectId: string) => void;
}

export const useStreamStore = create<StreamState>((set) => ({
  status: "idle",
  outlineDeltas: {},
  setStatus: (status) => set({ status }),
  applyOutlineDelta: (projectId, payload) =>
    set((state) => {
      const current = state.outlineDeltas[projectId] ?? { sections: [], pages: [] };
      const sections = [...current.sections];
      for (const section of payload.delta.sections ?? []) {
        if (section?.sectionKey && !sections.some((s) => s.sectionKey === section.sectionKey)) {
          sections.push({ sectionKey: section.sectionKey, title: section.title ?? section.sectionKey });
        }
      }
      const pages = [...current.pages];
      for (const page of payload.delta.pages ?? []) {
        pages.push({ title: page?.title ?? "Untitled page", sectionKey: page?.sectionKey });
      }
      return { outlineDeltas: { ...state.outlineDeltas, [projectId]: { sections, pages } } };
    }),
  clearOutlineDelta: (projectId) =>
    set((state) => ({ outlineDeltas: { ...state.outlineDeltas, [projectId]: { sections: [], pages: [] } } })),
}));
