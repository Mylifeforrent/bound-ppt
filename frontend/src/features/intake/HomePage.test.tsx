import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ClientConfigDTO, NoticeDTO } from "@/api/types";
import { HomePage } from "@/pages/HomePage";

const config: ClientConfigDTO = {
  materialLimit: 6,
  pageLimit: 30,
  uploadMaxBytes: 10 * 1024 * 1024,
  supportedFileTypes: [
    { extension: ".pdf", mimeType: "application/pdf", maxBytes: 10 * 1024 * 1024, maxPages: null },
  ],
  searchCapPerProject: 12,
  exportFormats: ["PPTX", "HTML", "PDF"],
  deckCanvas: { width: 1280, height: 720 },
  questionCatalogVersion: "1",
  styleCatalogVersion: "1",
};

const unacceptedNotice: NoticeDTO = {
  type: "DATA_NOTICE",
  version: "2026-11-01",
  title: "How we handle your materials",
  body: "Used only for this deck.",
  requiresConsent: true,
  acceptedAt: null,
};

function envelope(data: unknown): Response {
  return new Response(
    JSON.stringify({
      ok: true,
      data,
      meta: {
        requestId: "req-test",
        traceId: "trace-test",
        serverTime: new Date().toISOString(),
      },
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}

function installFetch(notices: NoticeDTO[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === "/api/config") return envelope({ config });
    if (url === "/api/policy/notices") return envelope({ notices });
    return new Response(JSON.stringify({ ok: false, error: { messageKey: "error.not_found.project" } }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderHome() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <HomePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("HomePage", () => {
  it("blocks an empty topic and focuses the field", async () => {
    installFetch([]);
    renderHome();
    fireEvent.click(screen.getByRole("button", { name: /Start generating/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a topic before starting.");
    expect(screen.getByLabelText("Topic")).toHaveFocus();
  });

  it("gates materials until the data notice is accepted", async () => {
    installFetch([unacceptedNotice]);
    renderHome();
    expect(await screen.findByRole("button", { name: /Accept data notice/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add text" })).toBeDisabled();
  });

  it("fills the topic from a scenario chip and focuses Start", async () => {
    installFetch([]);
    renderHome();
    const scenario = await screen.findByRole("button", { name: "Dify company introduction" });
    fireEvent.click(scenario);
    expect(screen.getByLabelText("Topic")).toHaveValue("Dify company introduction");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Start generating/ })).toHaveFocus();
    });
  });
});
