import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Curve } from "../components/Curve";
import { Loading, Section } from "../components/Shell";
import { Stamp, Verdict } from "../components/Verdict";
import type { Case, CurvePoint, Data } from "../data";
import { useData } from "../data";
import { day, int, month, pct, pctSmart, tidy, TYPE_LABEL, usd, usdCompact } from "../format";

export function Story() {
  const { data, error } = useData();
  if (!data) return <Loading error={error} />;
  return <StoryBody data={data} />;
}

function controls(p: CurvePoint, limit: number): string[] {
  const out = ["Block cash, money transfers and motor fuel by merchant category."];
  if (p.split_multiple !== null)
    out.push(
      `Decline when one card's spend at one merchant passes ${usd(limit * p.split_multiple)} within ${
        p.split_window_days + 1
      } calendar days.`,
    );
  if (p.anomaly_multiple !== null)
    out.push(`Decline a purchase over ${+p.anomaly_multiple.toFixed(1)}× the card's largest purchase so far.`);
  if (p.consumer_guard)
    out.push("Decline a card's first-ever purchase at a bar, clothing, jewelry or sporting-goods store.");
  if (p.duplicate_window_days !== null)
    out.push(
      p.duplicate_window_days === 0
        ? "Decline an identical charge from the same merchant on the same day."
        : `Decline an identical charge from the same merchant within ${p.duplicate_window_days} days.`,
    );
  return out;
}

function Instrument({ data }: { data: Data }) {
  const { curve, summary } = data;
  const start = Math.max(
    0,
    curve.findIndex((p) => p.s === summary.headline.replay_s),
  );
  const [i, setI] = useState(start);
  const p = curve[i];
  const types = Object.entries(p.planted_incidents_stopped_by_type);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 mt-12">
      <div className="rounded-2xl border border-rule bg-surface p-4 sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[3fr_2fr]">
          <div>
            <Curve points={curve} index={i} onPick={setI} budget={summary.headline.replay_budget} />
            <label htmlFor="strictness" className="mt-4 block font-semibold">
              How strict should the cards be?
            </label>
            <input
              id="strictness"
              className="dial"
              type="range"
              min={0}
              max={curve.length - 1}
              step={1}
              value={i}
              onChange={(e) => setI(Number(e.target.value))}
              aria-valuetext={`Strictness ${p.s.toFixed(2)}: ${pct(p.planted_incidents_stopped)} of planted misuse stopped, ${pctSmart(
                p.legit_dollars_declined_pct,
              )} of legitimate spend declined`}
            />
            <div className="flex justify-between text-xs text-ink-3">
              <span>Banned categories only</span>
              <span>Strictest</span>
            </div>
          </div>
          <div aria-live="polite">
            <div className="grid grid-cols-2 gap-6 border-b border-rule pb-6">
              <div>
                <div className="text-4xl sm:text-5xl font-extrabold tracking-tight text-s2">
                  {pct(p.planted_incidents_stopped)}
                </div>
                <div className="mt-1 text-sm text-ink-2">of planted misuse stopped at the swipe</div>
              </div>
              <div>
                <div className="text-4xl sm:text-5xl font-extrabold tracking-tight">
                  {pctSmart(p.legit_dollars_declined_pct)}
                </div>
                <div className="mt-1 text-sm text-ink-2">
                  of legitimate spend declined ({pctSmart(p.legit_txns_declined_pct)} of purchases)
                </div>
              </div>
            </div>
            <h3 className="mt-6 text-sm font-semibold">Stopped, by kind of planted misuse</h3>
            <ul className="mt-3 space-y-2.5">
              {types.map(([t, v]) => (
                <li key={t} className="grid grid-cols-[9.5rem_1fr_3rem] items-center gap-3 text-sm">
                  <span className="text-ink-2">{TYPE_LABEL[t]}</span>
                  <span className="h-2.5 rounded bg-paper-2 overflow-hidden" aria-hidden="true">
                    <span
                      className="block h-full rounded bg-s1 transition-[width] duration-200"
                      style={{ width: `${v * 100}%` }}
                    />
                  </span>
                  <span className="text-right font-semibold">{pct(v)}</span>
                </li>
              ))}
            </ul>
            <h3 className="mt-6 text-sm font-semibold">Controls at this setting</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-ink-2 list-disc pl-5">
              {controls(p, summary.policy.limit).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
        <h3 className="mt-10 font-semibold">Real purchases this setting would have declined</h3>
        <p className="text-sm text-ink-2">The largest ones, with the control that stopped each.</p>
        <ul className="mt-4 divide-y divide-rule border-y border-rule">
          {p.examples.slice(0, 6).map((e) => (
            <li key={`${i}-${e.txn_id}`} className="py-3 grid grid-cols-[1fr_auto] sm:grid-cols-[7rem_1fr_auto_8rem] gap-x-4 gap-y-1 items-center text-sm">
              <span className="text-ink-3 hidden sm:block">{day(e.date)}</span>
              <span>
                <span className="font-semibold">{tidy(e.merchant_norm)}</span>
                <span className="block text-ink-2 text-xs">
                  {tidy(e.agency)}, {e.reason}
                </span>
              </span>
              <span className="font-semibold text-right">{usd(e.amount, 2)}</span>
              <span className="col-span-2 sm:col-span-1 sm:text-right">
                <span className="stamp-in inline-block">
                  <Stamp declined />
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function pickExamples(cases: Case[]): Case[] {
  const real = cases.filter((c) => !c.planted);
  const ok = real
    .filter((c) => c.ai.verdict === "likely_ok")
    .sort((a, b) => (b.ai.confidence ?? 0) - (a.ai.confidence ?? 0))[0];
  const review = real
    .filter((c) => c.ai.verdict === "needs_review" && c.rule !== "unusual")
    .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake)[0];
  const planted = cases
    .filter((c) => c.planted && c.ai.verdict !== "likely_ok" && c.ai.verdict !== "pending")
    .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake)[0];
  return [ok, review, planted].filter(Boolean);
}

function StoryBody({ data }: { data: Data }) {
  const { summary, recall } = data;
  const h = summary.headline;
  const pr = summary.profile;
  const ai = summary.ai;
  const examples = useMemo(() => pickExamples(data.cases), [data.cases]);
  const h2 = summary.replay_headlines["0.02"];

  return (
    <article>
      <header className="mx-auto max-w-6xl px-4 sm:px-6 pt-14 sm:pt-20">
        <h1 className="text-[2.25rem] sm:text-[3.4rem] leading-[1.05] font-extrabold tracking-[-0.02em] max-w-4xl">
          If Oklahoma's state cards could say no at the register, what would they stop?
        </h1>
        <div className="prose-serif mt-6 text-ink-2">
          <p>
            I replayed {int(pr.rows)} real purchase-card transactions, {usdCompact(pr.dollars_positive)} across{" "}
            {pr.agencies} state agencies from {month(`${pr.first_month}-01`)} to {month(`${pr.last_month}-01`)}, through card controls
            that decide at the moment of the swipe. Then I measured them against misuse I planted in the data myself.
            Drag the dial to choose how strict the cards are.
          </p>
        </div>
      </header>

      <Instrument data={data} />

      <div className="mx-auto max-w-6xl px-4 sm:px-6 mt-16 grid gap-10 md:grid-cols-3">
        <Finding figure={pct(h.rules_recall)} title="caught after the fact">
          Rule checks on the full history find {pct(h.rules_recall)} of planted misuse (seeds ranged{" "}
          {pct(h.rules_recall_range[0])}–{pct(h.rules_recall_range[1])}). Personal purchases are the hard case.
        </Finding>
        <Finding figure={pct(h.replay_stopped)} title="stopped before it happens">
          At the swipe, controls stop {pct(h.replay_stopped)} of planted incidents while declining{" "}
          {pctSmart(h.replay_legit_declined)} of legitimate spend. Allowing {pct(h2.max_legit)} raises that to{" "}
          {pct(h2.planted_incidents_stopped)}.
        </Finding>
        <Finding figure={usd(ai.cost_usd, 2)} title={`for ${ai.investigated} AI case reviews`}>
          An AI reviewer cleared {ai.real_verdicts.likely_ok} of {ai.real_cases} real flags with a stated reason
          and sent {ai.planted_flagged_by_ai} of {ai.planted_cases} hidden planted cases to a human.
        </Finding>
      </div>

      <Section title="Why controls at the swipe matter">
        <div className="prose-serif">
          <p>
            Most public-sector card programs catch problems after the money is gone: a monthly reconciliation, an
            annual audit. Corporate card platforms argue the opposite: put the policy on the card, so the bad
            purchase never clears. This project tests that claim on real data, with a cost attached. Every control
            that stops misuse also stops some purchases people needed to make.
          </p>
          <p>
            The policy is Oklahoma's own: a {usd(summary.policy.limit)} single-purchase limit set by statute,
            a ban on split purchases made to get under it, and banned categories including cash, gift cards and
            motor fuel.
          </p>
        </div>
      </Section>

      <Section title="What the rules flagged in two years of real spending">
        <div className="overflow-x-auto">
          <table className="w-full max-w-3xl text-sm">
            <thead>
              <tr className="text-left text-ink-2 border-b border-rule-strong">
                <th className="py-2 pr-4 font-semibold">Rule</th>
                <th className="py-2 pr-4 font-semibold text-right">Flags</th>
                <th className="py-2 pr-4 font-semibold text-right">Purchases</th>
                <th className="py-2 font-semibold text-right">Dollars involved</th>
              </tr>
            </thead>
            <tbody>
              {summary.rules.by_rule.map((r) => (
                <tr key={r.rule} className="border-b border-rule">
                  <td className="py-2.5 pr-4">{r.label}</td>
                  <td className="py-2.5 pr-4 text-right">{int(r.flags)}</td>
                  <td className="py-2.5 pr-4 text-right">{int(r.txns)}</td>
                  <td className="py-2.5 text-right">{usd(r.dollars)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="prose-serif mt-5 text-ink-2">
          That is {summary.rules.flags_per_10k.toFixed(0)} flags per 10,000 purchases. A flag means a purchase is
          worth a second look. It is not a finding of misuse, and nothing here says how many of these flags are
          real problems.
        </p>
      </Section>

      <Section title="What the AI reviewer concluded">
        <p className="prose-serif text-ink-2">
          Each flag went to Claude, running headless with read-only tools: the card's history, the merchant's
          other customers, the agency's spending and the policy text. Ten of the {ai.cases} cases were planted, and
          the reviewer was not told which.
        </p>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {examples.map((c) => (
            <Link
              key={c.case_id}
              to={`/cases/${c.case_id}`}
              className="block rounded-xl border border-rule bg-surface p-5 hover:border-rule-strong"
            >
              <Verdict verdict={c.ai.verdict} />
              <div className="mt-3 font-semibold">{tidy(c.merchant)}</div>
              <div className="text-sm text-ink-2">
                {tidy(c.agency)}, {c.rule_label}, {usd(c.dollars_at_stake)}
              </div>
              <p className="mt-3 font-serif text-[0.95rem] leading-relaxed">{c.ai.explanation}</p>
              {c.planted && (
                <p className="mt-3 text-sm font-semibold text-s2">
                  This case was planted ({TYPE_LABEL[c.planted].toLowerCase()}). The reviewer didn't know.
                </p>
              )}
            </Link>
          ))}
        </div>
        <p className="mt-6">
          <Link to="/cases" className="font-semibold underline underline-offset-4 decoration-2 decoration-s1">
            Review all {ai.cases} cases
          </Link>
        </p>
      </Section>

      <Section title="How I measured it">
        <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
          <div className="prose-serif">
            <p>
              Real data has no answer key: nobody has labeled which of these purchases were misuse. So I planted
              my own. For each of five random seeds I added {recall.n_per_type} incidents of each kind to the real
              data, using real cards, real merchants and real amounts: purchases split to dodge the{" "}
              {usd(summary.policy.limit)} limit, double charges, banned categories, and personal purchases out of
              character for the card.
            </p>
            <p>
              The rules and the replay never see which rows are planted. Recall is the share of planted incidents
              a method catches. The replay goes through every transaction in order and decides each one using only
              what came before it, the way a card network would.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold">Caught after the fact, by kind (range across seeds)</h3>
            <ul className="mt-4 space-y-4">
              {recall.by_type.map((r) => (
                <li key={r.type} className="text-sm">
                  <div className="flex justify-between">
                    <span className="text-ink-2">{TYPE_LABEL[r.type]}</span>
                    <span className="font-semibold">{pct(r.mean)}</span>
                  </div>
                  <div className="relative mt-1.5 h-2.5 rounded bg-paper-2" aria-hidden="true">
                    <div className="absolute inset-y-0 left-0 rounded bg-s1" style={{ width: `${r.mean * 100}%` }} />
                    <div
                      className="absolute -inset-y-1 border-x-2 border-ink"
                      style={{ left: `${r.min * 100}%`, width: `${Math.max((r.max - r.min) * 100, 0.6)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {pct(r.min)}–{pct(r.max)} across seeds
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section title="What this doesn't show">
        <ul className="prose-serif list-disc pl-6 space-y-2">
          <li>
            Recall only measures the kinds of misuse I planted, and the rules were designed with those kinds in
            mind. Real misuse can look different.
          </li>
          <li>
            "Legitimate spend declined" treats every real purchase as legitimate, so it overstates the cost of
            each control.
          </li>
          <li>The AI's verdicts on real cases are its judgment. No one has checked them.</li>
          <li>
            This is one state. The data has no card numbers, so a card is an agency plus a cardholder's surname and
            initial, and purchases under statewide contracts, which have no limit, can't be told apart.
          </li>
          <li>Every finding here is a purchase worth reviewing, not an accusation against anyone.</li>
        </ul>
      </Section>

      <Section title="What I'd build next">
        <ul className="prose-serif list-disc pl-6 space-y-2">
          <li>Replay published state audit reports: would these controls have caught what auditors found, and when?</li>
          <li>Run the same pipeline on a second state to see whether the trade-off curve travels.</li>
          <li>Publish the merchant-name cleanup as a labeled benchmark.</li>
          <li>Pit an agent that tries to evade the controls against the reviewer, round by round.</li>
        </ul>
      </Section>
    </article>
  );
}

function Finding({ figure, title, children }: { figure: string; title: string; children: React.ReactNode }) {
  return (
    <div className="border-t-2 border-ink pt-4">
      <div className="text-4xl font-extrabold tracking-tight">{figure}</div>
      <div className="font-semibold mt-1">{title}</div>
      <p className="mt-3 text-sm text-ink-2 leading-relaxed">{children}</p>
    </div>
  );
}
