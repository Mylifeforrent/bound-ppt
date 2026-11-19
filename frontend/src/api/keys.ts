export const qk = {
  auth: ["auth", "me"] as const,
  config: ["config"] as const,
  notices: ["policy", "notices"] as const,
  snapshot: (projectId: string) => ["project", projectId, "snapshot"] as const,
  materials: (projectId: string) => ["project", projectId, "materials"] as const,
  research: (projectId: string) => ["project", projectId, "research"] as const,
  sources: (projectId: string) => ["project", projectId, "sources"] as const,
  outline: (projectId: string) => ["project", projectId, "outline"] as const,
  pages: (projectId: string) => ["project", projectId, "pages"] as const,
  artifact: (projectId: string, pageId: string, kind: "plan" | "design") =>
    ["project", projectId, "page", pageId, "artifact", kind] as const,
  history: (projectId: string, pageId: string, kind: "plan" | "design") =>
    ["project", projectId, "history", pageId, kind] as const,
  job: (projectId: string, jobId: string) => ["project", projectId, "job", jobId] as const,
  exportJob: (projectId: string, exportId: string) => ["project", projectId, "export", exportId] as const,
  styles: ["styles"] as const,
};
