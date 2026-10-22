import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Stamp, Verdict } from "./Verdict";

describe("Verdict", () => {
  it("always shows a text label, never color alone", () => {
    render(
      <>
        <Verdict verdict="likely_misuse" />
        <Verdict verdict="needs_review" />
        <Verdict verdict="likely_ok" />
      </>,
    );
    expect(screen.getByText("Likely misuse")).toBeInTheDocument();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("Likely fine")).toBeInTheDocument();
  });

  it("stamps declines", () => {
    render(<Stamp declined />);
    expect(screen.getByText("Declined")).toBeInTheDocument();
  });
});
