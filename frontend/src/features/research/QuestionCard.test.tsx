import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { QuestionDTO } from "@/api/types";
import { QuestionCard } from "./QuestionCard";

const question: QuestionDTO = {
  key: "audience",
  position: 1,
  prompt: "Who is this deck mainly for?",
  options: [
    { key: "prospects", label: "Prospects and partners" },
    { key: "investors", label: "Investors" },
  ],
  answer: null,
};

describe("QuestionCard", () => {
  it("records an answer when an option is chosen", () => {
    const onAnswer = vi.fn();
    render(
      <QuestionCard
        question={question}
        state="current"
        pending={false}
        onEdit={() => undefined}
        onCancelEdit={() => undefined}
        onAnswer={onAnswer}
      />,
    );
    fireEvent.click(screen.getByText("Investors"));
    expect(onAnswer).toHaveBeenCalledWith("investors");
  });

  it("collapses an answered question to Recorded with an Edit control", () => {
    const onEdit = vi.fn();
    render(
      <QuestionCard
        question={{
          ...question,
          answer: { optionKey: "prospects", revision: 1, answeredAt: "2026-11-19T08:00:00.000Z" },
        }}
        state="answered"
        pending={false}
        onEdit={onEdit}
        onCancelEdit={() => undefined}
        onAnswer={() => undefined}
      />,
    );
    expect(screen.getByText(/Recorded:/)).toBeInTheDocument();
    expect(screen.getByText("Prospects and partners")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalled();
  });

  it("locks a future question", () => {
    render(
      <QuestionCard
        question={question}
        state="locked"
        pending={false}
        onEdit={() => undefined}
        onCancelEdit={() => undefined}
        onAnswer={() => undefined}
      />,
    );
    expect(screen.getByText("Answer the previous question first.")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });
});
