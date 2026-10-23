// Smoke test: every page renders from the real exported JSON in web/public/data.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Shell } from "../components/Shell";
import { Cases } from "./Cases";
import { Method } from "./Method";
import { Story } from "./Story";

const DATA = join(process.cwd(), "public/data"); // vitest runs from web/

beforeAll(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const name = url.split("/").pop()!;
      return { ok: true, status: 200, json: async () => JSON.parse(readFileSync(join(DATA, name), "utf8")) };
    }),
  );
  window.matchMedia ??= (() => ({ matches: false })) as unknown as typeof window.matchMedia;
});

function at(path: string) {
  const router = createMemoryRouter(
    [
      {
        element: <Shell />,
        children: [
          { path: "/", element: <Story /> },
          { path: "/cases", element: <Cases /> },
          { path: "/cases/:id", element: <Cases /> },
          { path: "/method", element: <Method /> },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

const summary = JSON.parse(readFileSync(join(DATA, "summary.json"), "utf8"));
const curve = JSON.parse(readFileSync(join(DATA, "curve.json"), "utf8"));

describe("pages", () => {
  it("story renders the instrument and moves with the slider", async () => {
    at("/");
    await screen.findByRole("heading", { level: 1 });
    const slider = screen.getByRole("slider", { name: "How strict should the cards be?" });
    const i = curve.findIndex((p: { s: number }) => p.s === summary.headline.replay_s);
    expect(Number(slider.getAttribute("aria-valuenow"))).toBe(i);
    fireEvent.keyDown(slider, { key: "End" });
    const last = curve[curve.length - 1];
    await waitFor(() =>
      expect(screen.getAllByText(`${Math.round(last.planted_incidents_stopped * 100)}%`).length).toBeGreaterThan(0),
    );
    expect(screen.getByText("What this doesn't show")).toBeInTheDocument();
  });

  it("case review lists every case and opens one", async () => {
    at("/cases/C01");
    await screen.findByRole("heading", { name: "Case review" });
    expect(screen.getByText(/C01,/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Escalate" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Escalate" }));
    expect(screen.getByRole("button", { name: "Escalated" })).toBeInTheDocument();
  });

  it("method renders its tables", async () => {
    at("/method");
    await screen.findByRole("heading", { name: "Planted misuse" });
    expect(screen.getByText("Prevention replay")).toBeInTheDocument();
  });
});
