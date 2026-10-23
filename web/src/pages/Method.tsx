import { useState } from "react";
import { Loading, REPO } from "../components/Shell";
import type { Core } from "../data";
import { useCore } from "../data";
import { int, month, pct, pctSmart, signed, tidy, TYPE_LABEL, usd } from "../format";

function H({ children }: { children: React.ReactNode }) {
  return <h2 className="note-head heading mt-14 border-t-2 border-ink pt-3 text-[1.375rem]">{children}</h2>;
}

function Table({
  head,
  rows,
  align,
  wide,
  narrow,
}: {
  head: string[];
  rows: (string | number)[][];
  align?: ("l" | "r")[];
  wide?: number[]; // columns shown only from the sm breakpoint up
  narrow?: boolean; // a two-column key/value table: keep label and value within one eye span
}) {
  const hide = (i: number) => (wide?.includes(i) ? " hidden sm:table-cell" : "");
  return (
    <div className={`mt-4 overflow-x-auto ${narrow ? "lg:!max-w-[40rem]" : ""}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule-strong text-ink-2">
            {head.map((h, i) => (
              <th key={h} className={`py-2 pr-4 font-semibold ${align?.[i] === "r" ? "text-right" : "text-left"}${hide(i)}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, j) => (
            <tr key={j} className="border-b border-rule">
              {r.map((c, i) => (
                <td key={i} className={`py-2 pr-4 align-top ${align?.[i] === "r" ? "text-right" : ""}${hide(i)}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Method() {
  const { data, error } = useCore();
  if (!data) return <Loading error={error} />;
  const { summary: s, recall, rules, merchants, curve } = data;
  const p = s.profile;
  const ai = s.ai;
  const keyPoints = curve.filter((_, i) => i % 2 === 0);

  return (
    <div className="notes mx-auto max-w-6xl px-4 sm:px-6 pt-10 lg:[&>*]:ml-[calc((100%+1.5rem)/12)] lg:[&>*]:max-w-4xl lg:[&>p]:max-w-[62ch] lg:[&>ul]:max-w-[62ch]">
      <h1 className="display text-[clamp(2.25rem,5vw,3.5rem)]">Method</h1>
      <p className="mt-3 prose-read text-ink-2">
        Every number on this site is written by the pipeline and copied into{" "}
        <a href={`${REPO}/blob/main/REPORT.md`} className="underline decoration-2 underline-offset-4 hover:decoration-s2">
          REPORT.md
        </a>{" "}
        in the{" "}
        <a href={REPO} className="underline decoration-2 underline-offset-4 hover:decoration-s2">
          repository
        </a>
        . Nothing is typed by hand.
      </p>

      <H>The data</H>
      <Table
        head={["Measure", "Value"]}
        align={["l", "r"]}
        narrow
        rows={[
          ["Source", s.source],
          ["Statement months", `${month(`${p.first_month}-01`)} to ${month(`${p.last_month}-01`)} (${p.months})`],
          ["Transactions", int(p.rows)],
          ["Gross purchases", usd(p.dollars_positive)],
          ["Refunds and credits", int(p.refunds)],
          ["Agencies", int(p.agencies)],
          ["Cards (agency + surname + initial, hashed)", int(p.cards)],
          ["Merchant-category descriptions", int(p.mcc_categories)],
        ]}
      />
      <p className="mt-3 text-sm text-ink-2 max-w-[70ch]">
        The files carry the merchant category as text rather than a 4-digit code, and no card number. Cardholder names
        are hashed with a private salt the moment they're read and never stored.
      </p>

      <H>Cleaning merchant names</H>
      <p className="mt-3 text-ink-2">
        Card descriptors carry processor prefixes, store numbers and order codes, so {int(merchants.raw_descriptors)}{" "}
        raw strings collapse to {int(merchants.merchants)} merchants. The largest:
      </p>
      <MerchantTable top={merchants.top} />

      <H>Rule checks</H>
      <ul className="mt-3 list-disc pl-5 space-y-1.5 text-ink-2 max-w-[70ch]">
        <li>
          <b className="text-ink">Split purchase:</b> two or more purchases at one merchant within {s.policy.split_window_days + 1} calendar days,
          each under {usd(s.policy.limit)}, together over it. Utilities, professional services, interagency payments
          and State Use vendors have no limit and are skipped, as are travel, lodging and per-person fees.
        </li>
        <li>
          <b className="text-ink">Possible double charge:</b> exactly two identical charges (card, descriptor, amount)
          within {s.policy.duplicate_window_days} days with no matching refund. Three or more look like several items.
        </li>
        <li>
          <b className="text-ink">Prohibited category:</b>{" "}
          {s.policy.prohibited.map((x) => x.label.toLowerCase()).join("; ")}.
        </li>
        <li>
          <b className="text-ink">Unusual for this card:</b> over {s.policy.anomaly_multiple}× the card's largest earlier
          purchase, or its first purchase in a consumer category (such as bars, clothing or sporting goods), after at
          least {s.policy.anomaly_min_history} purchases.
        </li>
      </ul>
      <p className="mt-3 text-sm text-ink-2 max-w-[70ch]">
        {int(s.rules.total_flags)} flags in all, {s.rules.flags_per_10k.toFixed(1)} per 10,000 purchases.
      </p>
      <h3 className="mt-6 font-semibold">Flags by agency, largest spenders</h3>
      <Table
        head={["Agency", "Spend", "Flags", "Flags per $1M"]}
        align={["l", "r", "r", "r"]}
        rows={rules.agencies.slice(0, 12).map((a) => [tidy(a.agency), usd(a.spend), int(a.flags), a.flags_per_million.toFixed(1)])}
      />

      <H>Planted misuse</H>
      <p className="mt-3 text-ink-2">
        {recall.n_per_type} incidents of each kind per seed, seeds {recall.seeds.join(", ")}, on cards with at least 40
        purchases. Recall is the share of incidents with at least one planted purchase in a flag.
      </p>
      <Table
        head={["Kind", "Recall", "Lowest seed", "Highest seed", "Incidents"]}
        wide={[4]}
        align={["l", "r", "r", "r", "r"]}
        rows={[
          ...recall.by_type.map((r) => [TYPE_LABEL[r.type], pct(r.mean, 1), pct(r.min, 1), pct(r.max, 1), int(r.incidents)]),
          ["All kinds", pct(recall.overall_mean, 1), pct(recall.overall_min, 1), pct(recall.overall_max, 1), ""],
        ]}
      />

      <H>Prevention replay</H>
      <p className="mt-3 text-ink-2">
        {int(s.replay_rows)} transactions (real plus seed-0 plants), replayed in order in {s.replay_seconds}s. Each is
        approved or declined using only earlier transactions and what a card network sees at the swipe: amount,
        merchant and category, not the item description. That's why gift cards, which are found by description,
        can't be stopped at the swipe.
      </p>
      <Table
        head={["Strictness", "Legit spend declined", "Purchases declined", "Planted misuse stopped", "Flagged real $ blocked"]}
        wide={[2, 4]}
        align={["r", "r", "r", "r", "r"]}
        rows={keyPoints.map((q) => [
          q.s.toFixed(1),
          pctSmart(q.legit_dollars_declined_pct),
          pctSmart(q.legit_txns_declined_pct),
          pct(q.planted_incidents_stopped),
          q.flagged_dollars_blocked_pct === null ? "" : pct(q.flagged_dollars_blocked_pct),
        ])}
      />
      <p className="mt-3 text-sm text-ink-2 max-w-[70ch]">
        Headline: at most {pct(s.headline.replay_budget)} of legitimate spend declined stops{" "}
        {pct(s.headline.replay_stopped, 1)} of planted incidents (seeds {pct(s.headline.replay_stopped_range[0], 1)}–
        {pct(s.headline.replay_stopped_range[1], 1)}).
      </p>

      <H>AI reviewer</H>
      <Table
        head={["Measure", "Value"]}
        align={["l", "r"]}
        narrow
        rows={[
          ["Model", `Claude ${(ai.model ?? "").replace(/\b(haiku|sonnet|opus)\b/g, (m) => m[0].toUpperCase() + m.slice(1))}, headless Claude Code`],
          ["Final answer given by", Object.entries(ai.settled_by).map(([m, n]) => `${m} ${n}`).join(", ")],
          ["Cases", `${ai.cases} (${ai.real_cases} real, ${ai.planted_cases} planted, ${ai.control_cases} controls)`],
          ["Real cases: likely fine / needs review / likely misuse", `${ai.real_verdicts.likely_ok} / ${ai.real_verdicts.needs_review} / ${ai.real_verdicts.likely_misuse}`],
          ["Planted cases sent to review or called misuse", `${ai.planted_flagged_by_ai} of ${ai.planted_cases}`],
          ...Object.entries(ai.planted_by_type).map(([t, v]) => [`\u2003${TYPE_LABEL[t]}`, `${v.caught} of ${v.n} (${v.misuse} called misuse)`]),
          ["Controls wrongly sent to review or called misuse", `${ai.controls_flagged_by_ai} of ${ai.control_cases}`],
          ["Cost at API prices (paid by a Claude plan)", `${usd(ai.cost_usd, 2)} total, ${usd(ai.cost_per_case_usd ?? 0, 3)} per case`],
          ["Tokens", int(ai.tokens)],
          ["Average time per case", `${ai.seconds_mean}s`],
        ]}
      />
      <p className="mt-3 text-sm text-ink-2 max-w-[70ch]">
        The reviewer can only run four read-only lookups and must cite transaction ids that exist; an answer citing an
        unknown id is rejected and retried once. Controls are real purchases of $500 or more that no rule flagged, one
        per card, presented as random spot checks; without them, a reviewer that flags everything would look perfect.
      </p>

      <H>Tuning the reviewer, with a held-out test set</H>
      <p className="mt-3 text-sm text-ink-2 max-w-[70ch]">
        Dev is the {ai.planted_cases} planted cases and {ai.control_cases} controls above. Test is{" "}
        {s.ai_sets.test.planted} planted cases from another planting seed and {s.ai_sets.test.controls} controls drawn
        with another seed. Score = share of planted cases flagged minus share of controls flagged. A change ran on test
        only after it improved dev, and was kept only if the test score rose too (or held while cost fell by a quarter).
        The test failures were never read.
      </p>
      <Table
        head={["Change", "Dev", "Test", "$ per case", "Kept"]}
        align={["l", "r", "r", "r", "l"]}
        wide={[3]}
        rows={s.ai_tuning.map((r) => [
          r.label,
          r.dev_score === null ? "not run" : signed(r.dev_score),
          r.test_score === null ? "not run" : signed(r.test_score),
          r.test_cost_per_case_usd === null ? "" : usd(r.test_cost_per_case_usd, 3),
          r.kept ? "yes" : "no",
        ])}
      />

      <H>Limitations</H>
      <ul className="mt-3 list-disc pl-5 space-y-1.5 text-ink-2 max-w-[70ch]">
        <li>Recall only measures the kinds of misuse that were planted, and the rules were designed with them in mind.</li>
        <li>"Legitimate spend declined" treats every real purchase as legitimate, so it is an upper bound on the cost.</li>
        <li>
          The AI's verdicts on real cases are unverified. {ai.planted_cases} planted cases and {ai.control_cases} controls
          are small samples, and a control could itself be misuse no rule caught.
        </li>
        <li>
          One state, no card numbers, and purchases under statewide contracts (which have no limit) can't be told apart.
          University programs may set their own card limits.
        </li>
        <li>Every flag is a purchase worth reviewing, not an accusation against anyone.</li>
      </ul>
    </div>
  );
}

/** The merchant cleanup, ten rows first: it supports the method, it isn't the finding. */
function MerchantTable({ top }: { top: Core["merchants"]["top"] }) {
  const [all, setAll] = useState(false);
  return (
    <>
      <Table
        head={["Merchant", "Raw variants", "Purchases", "Spend", "Sample descriptors"]}
        wide={[1, 4]}
        align={["l", "r", "r", "r", "l"]}
        rows={(all ? top : top.slice(0, 10)).map((m) => [
          tidy(m.merchant_norm),
          int(m.raw_variants),
          int(m.txns),
          usd(m.dollars),
          m.samples.slice(0, 3).join(", "),
        ])}
      />
      {top.length > 10 && (
        <button
          type="button"
          onClick={() => setAll((a) => !a)}
          aria-expanded={all}
          className="mt-2 inline-flex min-h-11 items-center text-sm font-semibold underline decoration-2 underline-offset-4 hover:decoration-s2"
        >
          {all ? "Show the top 10" : `Show all ${top.length}`}
        </button>
      )}
    </>
  );
}
