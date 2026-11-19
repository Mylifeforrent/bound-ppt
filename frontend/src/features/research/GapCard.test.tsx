import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GapStateDTO } from "@/api/types";
import { GapCard } from "./GapCard";

const gaps: GapStateDTO = {
  batch: 1,
  suggestions: [
    {
      id: "gap-competitors",
      label: "Competitor comparison",
      reason: "Your materials do not compare alternatives.",
      recommended: true,
      status: "SUGGESTED",
    },
    {
      id: "gap-market",
      label: "Market size",
      reason: "Adds a current market figure.",
      recommended: false,
      status: "SUGGESTED",
    },
  ],
  decision: null,
};

describe("GapCard", () => {
  it("pre-checks recommended gaps", () => {
    render(<GapCard gaps={gaps} pending={false} onConfirm={() => undefined} />);
    expect(screen.getByLabelText(/Competitor comparison/)).toBeChecked();
    expect(screen.getByLabelText(/Market size/)).not.toBeChecked();
  });

  it("confirms the recommended selection", () => {
    const onConfirm = vi.fn();
    render(<GapCard gaps={gaps} pending={false} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm gaps" }));
    expect(onConfirm).toHaveBeenCalledWith({
      selectedSuggestionIds: ["gap-competitors"],
      webSkipped: false,
    });
  });

  it("'Not needed' clears the selection and confirms webSkipped", () => {
    const onConfirm = vi.fn();
    render(<GapCard gaps={gaps} pending={false} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: /Not needed/ }));
    expect(screen.getByLabelText(/Competitor comparison/)).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Confirm gaps" }));
    expect(onConfirm).toHaveBeenCalledWith({
      selectedSuggestionIds: [],
      webSkipped: true,
    });
  });

  it("renders a read-only recorded decision", () => {
    render(
      <GapCard
        gaps={{
          ...gaps,
          decision: {
            decidedAt: "2026-11-19T08:00:00.000Z",
            selectedSuggestionIds: ["gap-competitors"],
            webSkipped: false,
          },
        }}
        pending={false}
        onConfirm={() => undefined}
      />,
    );
    expect(screen.getByText("Gap plan recorded")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm gaps" })).not.toBeInTheDocument();
  });
});
