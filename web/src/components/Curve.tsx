import { useState } from "react";
import type { CurvePoint } from "../data";
import { pct, pctSmart } from "../format";
import { useWidth } from "./useWidth";

const M = { top: 16, right: 20, bottom: 52, left: 64 };

/** Trade-off curve: legit spend declined (x) vs planted misuse stopped (y), one dot per strictness.
 *  Single series, so no legend: the axis titles name it. */
export function Curve({
  points,
  index,
  onPick,
  budget,
}: {
  points: CurvePoint[];
  index: number;
  onPick: (i: number) => void;
  budget: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [box, W] = useWidth<HTMLDivElement>();
  const H = Math.round(Math.min(380, Math.max(260, W * 0.62)));
  const IW = W - M.left - M.right;
  const IH = H - M.top - M.bottom;
  const xMax = Math.ceil(Math.max(...points.map((p) => p.legit_dollars_declined_pct)) * 100) / 100;
  const x = (v: number) => M.left + (v / xMax) * IW;
  const y = (v: number) => M.top + (1 - v) * IH;
  const xTicks = Array.from({ length: Math.round(xMax * 100) + 1 }, (_, i) => i / 100).filter(
    (_, i, a) => a.length <= (W < 480 ? 5 : 9) || i % 2 === 0,
  );
  const path = points
    .map((p, i) => `${i ? "L" : "M"}${x(p.legit_dollars_declined_pct)},${y(p.planted_incidents_stopped)}`)
    .join(" ");
  const shown = hover ?? index;
  const sp = points[shown];

  const plateau = points.findIndex((p) => p.past_plateau) - 1; // the first setting at the top
  return (
    <div className="relative" ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-labelledby="curve-title curve-desc">
        <title id="curve-title">Misuse stopped versus legitimate spend declined</title>
        <desc id="curve-desc">
          As the controls get stricter, more planted misuse is stopped and more legitimate spend is declined. The
          current setting stops {pct(points[index].planted_incidents_stopped)} of planted incidents and declines{" "}
          {pctSmart(points[index].legit_dollars_declined_pct)} of legitimate spend.
        </desc>
        {plateau > 0 && (
          <g>
            <rect
              x={x(points[plateau].legit_dollars_declined_pct)}
              y={M.top}
              width={W - M.right - x(points[plateau].legit_dollars_declined_pct)}
              height={y(0) - M.top}
              fill="var(--paper-2)"
            />
            <text
              x={W - M.right - 6}
              y={y(0) - 10}
              textAnchor="end"
              fontSize="12"
              fill="var(--ink-2)"
            >
              No more misuse stopped
            </text>
          </g>
        )}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--rule)" strokeWidth="1" />
            <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="12" fill="var(--ink-3)">
              {pct(t)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={H - M.bottom + 20} textAnchor="middle" fontSize="12" fill="var(--ink-3)">
            {pct(t)}
          </text>
        ))}
        <line x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} stroke="var(--rule-strong)" />
        {budget <= xMax && (
          <g>
            <line x1={x(budget)} x2={x(budget)} y1={M.top} y2={y(0)} stroke="var(--ink-3)" strokeDasharray="4 4" />
            <text x={x(budget) + 6} y={M.top + 12} fontSize="12" fill="var(--ink-2)">
              {pct(budget)} of legitimate spend
            </text>
          </g>
        )}
        <text x={M.left + IW / 2} y={H - 8} textAnchor="middle" fontSize="13" fill="var(--ink-2)" fontWeight="600">
          Legitimate spend declined
        </text>
        <text
          transform={`translate(13 ${M.top + IH / 2}) rotate(-90)`}
          textAnchor="middle"
          fontSize="13"
          fill="var(--ink-2)"
          fontWeight="600"
        >
          Planted misuse stopped
        </text>
        <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" strokeLinejoin="round" />
        {points.map((p) => (
          <circle
            key={p.s}
            cx={x(p.legit_dollars_declined_pct)}
            cy={y(p.planted_incidents_stopped)}
            r={4}
            fill="var(--series-1)"
            stroke="var(--surface)"
            strokeWidth="2"
          />
        ))}
        <circle
          cx={x(points[index].legit_dollars_declined_pct)}
          cy={y(points[index].planted_incidents_stopped)}
          r={8}
          fill="var(--series-2)"
          stroke="var(--surface)"
          strokeWidth="2"
        />
        {points.map((p, i) => (
          <circle
            key={`hit-${p.s}`}
            cx={x(p.legit_dollars_declined_pct)}
            cy={y(p.planted_incidents_stopped)}
            r={12}
            fill="transparent"
            className="cursor-pointer"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            onClick={() => onPick(i)}
          />
        ))}
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-rule bg-surface px-3 py-2 text-xs shadow-sm"
          style={{
            left: `${(x(sp.legit_dollars_declined_pct) / W) * 100}%`,
            top: `${(y(sp.planted_incidents_stopped) / H) * 100}%`,
            transform: "translate(-50%, calc(-100% - 14px))",
          }}
        >
          <div className="font-semibold text-ink">Strictness {sp.s.toFixed(2)}</div>
          <div className="text-ink-2">{pct(sp.planted_incidents_stopped)} of planted misuse stopped</div>
          <div className="text-ink-2">{pctSmart(sp.legit_dollars_declined_pct)} of legitimate spend declined</div>
        </div>
      )}
    </div>
  );
}
