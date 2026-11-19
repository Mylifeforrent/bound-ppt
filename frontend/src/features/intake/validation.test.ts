import { describe, expect, it } from "vitest";
import type { ClientConfigDTO, NoticeDTO } from "@/api/types";
import { checkFile, normalizeUrl, noticeGate, urlDisplayName } from "./validation";

const supportedTypes: ClientConfigDTO["supportedFileTypes"] = [
  { extension: ".pdf", mimeType: "application/pdf", maxBytes: 1_000, maxPages: null },
  { extension: ".txt", mimeType: "text/plain", maxBytes: 500, maxPages: null },
];

function notice(overrides: Partial<NoticeDTO> = {}): NoticeDTO {
  return {
    type: "DATA_NOTICE",
    version: "2026-11-01",
    title: "How we handle your materials",
    body: "Used only for this deck.",
    requiresConsent: true,
    acceptedAt: null,
    ...overrides,
  };
}

describe("normalizeUrl", () => {
  it("adds the default https scheme", () => {
    expect(normalizeUrl("example.com/article")).toBe("https://example.com/article");
  });

  it("accepts http and https URLs", () => {
    expect(normalizeUrl("http://example.com")).toBe("http://example.com/");
    expect(normalizeUrl("https://example.com/path?q=1")).toBe("https://example.com/path?q=1");
  });

  it("rejects empty, malformed, and non-http schemes", () => {
    expect(normalizeUrl("   ")).toBeNull();
    expect(normalizeUrl("not a url")).toBeNull();
    expect(normalizeUrl("ftp://example.com")).toBeNull();
    expect(normalizeUrl("javascript:alert(1)")).toBeNull();
  });

  it("derives a readable display name", () => {
    expect(urlDisplayName("https://example.com/a/b")).toBe("example.com/a/b");
  });
});

describe("checkFile", () => {
  it("accepts a supported extension within its per-type cap", () => {
    const file = new File(["ok"], "deck.pdf", { type: "application/pdf" });
    expect(checkFile(file, supportedTypes, 2_000)).toEqual({ ok: true, maxBytes: 1_000 });
  });

  it("rejects an unsupported extension", () => {
    const file = new File(["x"], "deck.exe", { type: "application/octet-stream" });
    expect(checkFile(file, supportedTypes, 2_000).errorKey).toBe("error.validation.unsupported_type");
  });

  it("rejects a file over its per-type cap", () => {
    const file = new File(["x".repeat(600)], "notes.txt", { type: "text/plain" });
    expect(checkFile(file, supportedTypes, 2_000).errorKey).toBe("error.validation.file_too_large");
  });
});

describe("noticeGate", () => {
  it("blocks until every required notice is accepted", () => {
    const gate = noticeGate([notice()]);
    expect(gate.blocked).toBe(true);
    expect(gate.unaccepted).toHaveLength(1);
  });

  it("unblocks when the required notice is accepted", () => {
    const gate = noticeGate([notice({ acceptedAt: "2026-11-19T08:00:00.000Z" })]);
    expect(gate.blocked).toBe(false);
    expect(gate.required).toHaveLength(1);
  });

  it("ignores notices that do not require consent", () => {
    const gate = noticeGate([notice({ requiresConsent: false })]);
    expect(gate.blocked).toBe(false);
    expect(gate.required).toHaveLength(0);
  });
});
