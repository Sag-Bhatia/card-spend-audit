import { useState } from "react";
import type { Case } from "../data";
import { day, tidy, usd } from "../format";
import { useWidth } from "./useWidth";

const M = { top: 12, right: 16, bottom: 30, left: 56 };

const t = (iso: string) => Date.parse(`${iso}T00:00:00Z`);

/** A card's purchases in the 30 days either side of the flag. Log scale: amounts span $1 to $100K+. */
export function Timeline({ c }: { c: Case }) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useWidth<HTMLDivElement>();
  const H = W < 480 ? 190 : 220;
  const rows = c.timeline.filter((r) => r.amount > 0);
  if (!rows.length) return null;
  const t0 = Math.min(...rows.map((r) => t(r.date)));
  const t1 = Math.max(...rows.map((r) => t(r.date)), t0 + 86400000);
  const lo = Math.max(1, Math.min(...rows.map((r) => r.amount)));
  const hi = Math.max(...rows.map((r) => r.amount));
  const d0 = Math.floor(Math.log10(lo));
  const d1 = Math.ceil(Math.log10(hi)) || 1;
  const x = (iso: string) => M.left + ((t(iso) - t0) / (t1 - t0)) * (W - M.left - M.right);
  const y = (v: number) => M.top + (1 - (Math.log10(Math.max(v, 1)) - d0) / Math.max(d1 - d0, 1)) * (H - M.top - M.bottom);
  const ticks = Array.from({ length: d1 - d0 + 1 }, (_, i) => 10 ** (d0 + i));
  const ordered = [...rows.filter((r) => !r.flagged), ...rows.filter((r) => r.flagged)];
  // A double charge is two identical points; nudge repeats sideways so both stay visible.
  const seen = new Map<string, number>();
  const repeat = ordered.map((r) => {
    const k = `${r.date}|${r.amount}`;
    const n = seen.get(k) ?? 0;
    seen.set(k, n + 1);
    return n;
  });
  const hv = hover !== null ? ordered[hover] : null;

  return (
    <figure>
      <div className="flex flex-wrap gap-4 text-xs text-ink-2 mb-2" aria-hidden="true">
        <span className="inline-flex items-center gap-1.5">
          <svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="var(--series-1)" /></svg>
          Other purchases on this card
        </span>
        <span className="inline-flex items-center gap-1.5">
          <svg width="12" height="12"><circle cx="6" cy="6" r="5" fill="var(--series-2)" /></svg>
          {c.control ? "Spot-checked purchase" : "Flagged purchases"}
        </span>
      </div>
      <div className="relative" ref={box}>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`${c.card}'s purchases from ${day(rows[0].date)} to ${day(rows[rows.length - 1].date)}; flagged purchases highlighted.`}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke="var(--rule)" />
              <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end" fontSize="12" fill="var(--ink-3)">
                {v >= 1e6 ? `$${v / 1e6}M` : v >= 1000 ? `$${v / 1000}K` : `$${v}`}
              </text>
            </g>
          ))}
          <text x={M.left} y={H - 8} fontSize="12" fill="var(--ink-3)">
            {day(rows[0].date)}
          </text>
          <text x={W - M.right} y={H - 8} fontSize="12" fill="var(--ink-3)" textAnchor="end">
            {day(rows[rows.length - 1].date)}
          </text>
          {ordered.map((r, i) => (
            <circle
              key={r.txn_id}
              cx={x(r.date) + (repeat[i] ?? 0) * 9}
              cy={y(r.amount)}
              r={r.flagged ? 6 : 4}
              fill={r.flagged ? "var(--series-2)" : "var(--series-1)"}
              stroke="var(--surface)"
              strokeWidth="2"
              opacity={r.flagged ? 1 : 0.85}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              tabIndex={r.flagged ? 0 : -1}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              aria-label={r.flagged ? `${usd(r.amount, 2)} at ${tidy(r.merchant_norm)}, ${day(r.date)}` : undefined}
            />
          ))}
        </svg>
        {hv && (
          <div
            className="pointer-events-none absolute z-10 border-2 border-ink bg-surface px-3 py-2 text-xs whitespace-nowrap"
            style={{ left: `${(x(hv.date) / W) * 100}%`, top: `${(y(hv.amount) / H) * 100}%`, transform: "translate(-50%, calc(-100% - 12px))" }}
          >
            <div className="font-semibold">{usd(hv.amount, 2)}</div>
            <div className="text-ink-2">{tidy(hv.merchant_norm)}</div>
            <div className="text-ink-3">{day(hv.date)}</div>
          </div>
        )}
      </div>
    </figure>
  );
}
