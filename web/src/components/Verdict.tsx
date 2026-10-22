import type { VerdictId } from "../data";

const META: Record<VerdictId, { label: string; color: string; icon: string }> = {
  likely_misuse: { label: "Likely misuse", color: "var(--bad)", icon: "M8 2 15 14H1Z M8 6.5v3.5 M8 12v.01" },
  needs_review: { label: "Needs review", color: "var(--warn)", icon: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z M8 4.5V8l2.5 1.5" },
  likely_ok: { label: "Likely fine", color: "var(--good)", icon: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z M5 8.2l2 2 4-4.2" },
  error: { label: "No answer", color: "var(--ink-3)", icon: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z M5.5 5.5l5 5 M10.5 5.5l-5 5" },
  pending: { label: "Not reviewed", color: "var(--ink-3)", icon: "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z" },
};

export const verdictLabel = (v: VerdictId) => META[v].label;

/** Verdict = status: always icon + label, never color alone. */
export function Verdict({ verdict, size = "sm" }: { verdict: VerdictId; size?: "sm" | "lg" }) {
  const m = META[verdict];
  const px = size === "lg" ? 18 : 14;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold ${size === "lg" ? "text-base" : "text-xs"}`}
      style={{ color: m.color }}
    >
      <svg width={px} height={px} viewBox="0 0 16 16" aria-hidden="true">
        <path d={m.icon} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {m.label}
    </span>
  );
}

/** The rubber stamp for a swipe-time decision. */
export function Stamp({ declined }: { declined: boolean }) {
  return (
    <span className="stamp" style={{ color: declined ? "var(--series-2)" : "var(--good)" }}>
      {declined ? "Declined" : "Approved"}
    </span>
  );
}
