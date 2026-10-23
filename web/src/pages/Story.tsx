import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Curve } from "../components/Curve";
import { Loading, Section } from "../components/Shell";
import { Stamp, Verdict } from "../components/Verdict";
import { Slider } from "@/components/ui/slider";
import type { Case, Core, CurvePoint } from "../data";
import { useCases, useCore } from "../data";
import { day, int, month, pct, pctSmart, REASON_LABEL, tidy, TYPE_LABEL, usd, usdCompact } from "../format";

export function Story() {
  const { data, error } = useCore();
  if (!data) return <Loading error={error} />;
  return <StoryBody data={data} />;
}

function controls(p: CurvePoint): string[] {
  const out = ["Block cash, money transfers and motor fuel by merchant category."];
  if (p.split_threshold_usd !== null)
    out.push(
      `Decline when one card's spend at one merchant passes ${usd(p.split_threshold_usd)} within ${
        p.split_window_days + 1
      } calendar days.`,
    );
  if (p.anomaly_multiple !== null)
    out.push(`Decline a purchase over ${+p.anomaly_multiple.toFixed(1)}× the card's largest purchase so far.`);
  if (p.consumer_guard)
    out.push("Decline a card's first-ever purchase in a consumer category, such as a bar or a sporting-goods store.");
  if (p.duplicate_window_days !== null)
    out.push(
      p.duplicate_window_days === 0
        ? "Decline an identical charge from the same merchant on the same day."
        : `Decline an identical charge from the same merchant within ${p.duplicate_window_days} days.`,
    );
  return out;
}

/** Figure 1, the signature: one ruled strictness scale. Above the rule, the share of planted misuse each
 *  setting stops (red); below it, the legitimate spend it declines (ink), against the 1% budget rule. The
 *  flag is the slider. Bar heights only scale numbers the pipeline wrote. */
function Scale({
  curve,
  i,
  setI,
  reported,
  className = "",
}: {
  curve: CurvePoint[];
  i: number;
  setI: (v: number) => void;
  reported: number;
  className?: string;
}) {
  const p = curve[i];
  // Where tick k sits: the ticks run edge to edge inside 7px of padding, each 6px wide.
  const at = (k: number) => `calc(10px + ${k / (curve.length - 1)} * (100% - 20px))`;
  const UP = 72; // px for 100% of planted misuse stopped
  const PER_PCT = 14; // px per 1% of legitimate spend declined
  return (
    <figure className={`mt-10 border-t-2 border-ink pt-3 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <figcaption className="font-extrabold">
          Figure 1. <span id="strictness">How strict should the cards be?</span>
        </figcaption>
        <p className="flex flex-wrap items-baseline gap-x-4 text-sm tabular-nums">
          {/* Always laid out (hidden at the reported setting) so the scale never shifts under a finger. */}
          <button
            type="button"
            onClick={() => setI(reported)}
            className={`min-h-11 font-semibold underline decoration-2 underline-offset-4 hover:decoration-s2 ${
              i === reported ? "invisible" : ""
            }`}
          >
            Back to the reported setting
          </button>
          <span>
            Strictness <span className="font-extrabold">{p.s.toFixed(2)}</span> of 1
          </span>
        </p>
      </div>
      <div className="relative mt-7" aria-hidden="true">
        <span
          className="absolute -top-6 -translate-x-1/2 whitespace-nowrap text-xs font-bold leading-none"
          style={{ left: at(reported) }}
        >
          Reported
          <span className="mx-auto mt-0.5 block h-1.5 w-0.5 bg-ink" />
        </span>
        <div className="flex items-end justify-between px-[7px]" style={{ height: UP }}>
          {curve.map((q, k) => (
            <span
              key={q.s}
              className={k === i ? "bg-s2" : "bg-s2/55"}
              style={{ width: 6, height: Math.max(2, q.planted_incidents_stopped * UP) }}
            />
          ))}
        </div>
      </div>
      <Slider
        aria-labelledby="strictness"
        className="dial h-11 -my-[21px] relative z-10"
        min={0}
        max={curve.length - 1}
        step={1}
        value={[i]}
        onValueChange={([v]) => setI(v)}
        aria-valuetext={`Strictness ${p.s.toFixed(2)}: ${pct(p.planted_incidents_stopped)} of planted misuse stopped, ${pctSmart(
          p.legit_dollars_declined_pct,
        )} of legitimate spend declined`}
      />
      <div className="relative" aria-hidden="true">
        <div className="flex items-start justify-between px-[7px]" style={{ height: Math.ceil(curve[curve.length - 1].legit_dollars_declined_pct * 100 * PER_PCT) + 4 }}>
          {curve.map((q, k) => (
            <span
              key={q.s}
              className={k === i ? "bg-ink" : "bg-ink/50"}
              style={{ width: 6, height: Math.max(2, q.legit_dollars_declined_pct * 100 * PER_PCT) }}
            />
          ))}
        </div>
        <div className="absolute inset-x-0 border-t-4 border-ink" style={{ top: PER_PCT }}>
          <span className="absolute left-0 top-1 bg-paper pr-2 text-xs font-bold">1% of legitimate spend</span>
        </div>
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink-3">
        <span>Banned categories only</span>
        <span>Strictest</span>
      </div>
      <p className="mt-3 text-xs text-ink-3 max-w-[70ch]">
        Red above the line: planted misuse stopped. Below it: legitimate spend declined, against the 1% rule. Each tick is
        one setting; the headline figures follow the flag, and "Reported" marks the setting the summary quotes.
      </p>
    </figure>
  );
}

/** Figure 2: the trade-off curve, what the setting stops by kind, its controls, and what the notch costs. */
function Instrument({ data, i, setI }: { data: Core; i: number; setI: (v: number) => void }) {
  const { curve, summary } = data;
  const p = curve[i];
  const types = Object.entries(p.planted_incidents_stopped_by_type);
  const plateauFrom = curve.findIndex((q) => q.past_plateau) - 1;

  return (
    <section className="mx-auto max-w-6xl px-4 sm:px-6 mt-16">
      <h2 className="sr-only">Try the controls</h2>
      <div className="border-t-2 border-ink pt-3">
        <p className="font-extrabold">Figure 2. What each setting stops and what it costs</p>
        <div className="mt-6 grid gap-10 lg:grid-cols-12">
          <div className="min-w-0 lg:col-span-7">
            <Curve points={curve} index={i} onPick={setI} budget={summary.headline.replay_budget} />
          </div>
          <div className="min-w-0 lg:col-span-5">
            {p.past_plateau && (
              <p className="border-y-2 border-ink py-2 text-sm">
                Past {curve[plateauFrom].s.toFixed(2)}, stricter cards stop no more planted misuse. They only decline
                more legitimate spend.
              </p>
            )}
            <h3 className="mt-6 text-sm font-extrabold">Stopped, by kind of planted misuse</h3>
            <ul className="mt-3 space-y-2.5">
              {types.map(([t, v]) => (
                <li key={t} className="grid grid-cols-[minmax(0,9.5rem)_1fr_auto] items-center gap-3 text-sm">
                  <span>{TYPE_LABEL[t]}</span>
                  <span className="h-2 border-b border-rule" aria-hidden="true">
                    <span className="block h-full bg-s2" style={{ width: `${v * 100}%` }} />
                  </span>
                  <span className="text-right font-bold tabular-nums">{pct(v)}</span>
                </li>
              ))}
            </ul>
            <h3 className="mt-6 text-sm font-extrabold">Controls at this setting</h3>
            <ul className="mt-2 space-y-1.5 text-sm text-ink-2 list-disc pl-5">
              {controls(p).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
        <h3 className="mt-12 border-t-2 border-ink pt-3 text-lg font-extrabold">
          {i === 0 ? "The cost at the loosest setting" : "What this notch costs"}
        </h3>
        <p className="text-sm text-ink-2 max-w-[70ch]">
          {i === 0
            ? `${int(p.newly_declined.txns)} real purchases (${usd(p.newly_declined.usd)}) declined by banned categories alone.`
            : p.newly_declined.txns
              ? `${int(p.newly_declined.txns)} more real purchases (${usd(p.newly_declined.usd)}) declined than one notch looser.`
              : "No more real purchases declined than one notch looser."}{" "}
          Every real purchase counts as legitimate here, so these are the price of the misuse stopped. One per control
          first, then the largest.
        </p>
        <ul className="mt-4 divide-y divide-rule border-b-2 border-ink">
          {p.examples.slice(0, 5).map((e) => (
            <li key={`${i}-${e.txn_id}`} className="py-3 grid grid-cols-[1fr_auto] sm:grid-cols-[7rem_1fr_auto_8rem] gap-x-4 gap-y-1 items-center text-sm">
              <span className="text-ink-3 hidden sm:block">{day(e.date)}</span>
              <span>
                <span className="font-semibold">{tidy(e.merchant_norm)}</span>
                <span className="block text-ink-2 text-xs">
                  {tidy(e.agency)}, {REASON_LABEL[e.reason] ?? e.reason}
                </span>
              </span>
              <span className="font-semibold text-right">{usd(e.amount, 2)}</span>
              <span className="col-span-2 sm:col-span-1 sm:text-right">
                <Stamp declined cost />
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** One real "likely misuse" (or the largest real "needs review" if there is none), one real
 *  "likely fine", and one planted case the reviewer sent to a human. */
function pickExamples(cases: Case[]): Case[] {
  const real = cases.filter((c) => !c.planted && !c.control);
  const misuse = real
    .filter((c) => c.ai.verdict === "likely_misuse")
    .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake)[0];
  const ok = real
    .filter((c) => c.ai.verdict === "likely_ok")
    .sort((a, b) => (b.ai.confidence ?? 0) - (a.ai.confidence ?? 0))[0];
  const review = real
    .filter((c) => c.ai.verdict === "needs_review" && c.rule !== "unusual")
    .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake)[0];
  const planted = cases
    .filter((c) => c.planted && c.ai.verdict !== "likely_ok" && c.ai.verdict !== "pending")
    .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake)[0];
  return [misuse ?? review, ok, planted].filter(Boolean);
}

function StoryBody({ data }: { data: Core }) {
  const { summary, recall } = data;
  const h = summary.headline;
  const pr = summary.profile;
  const ai = summary.ai;
  const test = summary.ai_sets.test;
  const cases = useCases().data;
  const examples = useMemo(() => (cases ? pickExamples(cases) : []), [cases]);
  const h2 = summary.replay_headlines["0.02"];
  const reported = Math.max(
    0,
    data.curve.findIndex((q) => q.s === summary.headline.replay_s),
  );
  const [i, setI] = useState(reported);
  const p = data.curve[i];
  const over = p.legit_dollars_declined_pct > h.replay_budget;

  return (
    <article>
      <header className="mx-auto max-w-6xl px-4 sm:px-6 pt-10 sm:pt-14">
        <div className="grid grid-cols-12 sm:gap-x-6">
          <p className="hidden sm:block sm:col-span-1 text-sm font-extrabold text-s2 sm:pt-3" aria-hidden="true">
            1
          </p>
          <h1 className="display hyphens-auto break-words col-span-12 sm:col-span-11 lg:col-span-6 text-[clamp(2.25rem,4.3vw,3.6rem)]">
            <span className="sm:hidden mr-2 align-top text-sm text-s2" aria-hidden="true">
              1
            </span>
            If Oklahoma's state cards could say no at the register, what would they stop?
          </h1>
          <div className="col-span-12 lg:col-span-5 lg:col-start-8 mt-8 lg:mt-1 lg:row-span-2 grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] lg:grid-cols-1 content-start gap-6">
            <div>
              <div className="figure text-[min(clamp(3.25rem,9vw,8.25rem),14vw)] text-s2 tabular-nums">{pct(p.planted_incidents_stopped)}</div>
              <p className="mt-3 border-t-2 border-ink pt-2 text-sm font-semibold">of planted misuse stopped at the swipe</p>
            </div>
            <div>
              <div className="figure text-[min(clamp(3.25rem,9vw,8.25rem),14vw)] tabular-nums">{pctSmart(p.legit_dollars_declined_pct)}</div>
              <p className="mt-3 border-t-2 border-ink pt-2 text-sm font-semibold">
                of legitimate spend declined ({pctSmart(p.legit_txns_declined_pct)} of purchases)
                {/* Laid out even when hidden, so the scale below never moves. */}
                <span className={`block font-extrabold ${over ? "" : "invisible"}`} aria-hidden={!over}>
                  Over the {pct(h.replay_budget)} budget.
                </span>
              </p>
            </div>
          </div>
          <Scale
            curve={data.curve}
            i={i}
            setI={setI}
            reported={reported}
            className="col-span-12 lg:order-last"
          />
          <p className="col-span-12 sm:col-span-11 sm:col-start-2 lg:col-span-6 lg:col-start-2 mt-6 text-ink-2 max-w-[62ch]">
            I replayed {int(pr.rows)} real purchase-card transactions, {usdCompact(pr.dollars_positive)} across{" "}
            {pr.agencies} state agencies from {month(`${pr.first_month}-01`)} to {month(`${pr.last_month}-01`)}, through card
            controls that decide at the moment of the swipe. Then I measured them against misuse I planted in the data
            myself. Move the scale to choose how strict the cards are.
          </p>
          <p className="col-span-12 lg:col-span-5 lg:col-start-8 mt-6 border-t border-ink pt-2 text-sm text-ink-2">
            Answer key: {int(recall.n_per_type)} planted incidents of each of {recall.by_type.length} kinds, over{" "}
            {recall.seeds.length} random seeds. The replay sees only earlier purchases. Legitimate spend declined counts
            every real purchase as legitimate, so it is an upper bound.
          </p>
        </div>
      </header>

      <Instrument data={data} i={i} setI={setI} />

      <Section n={2} title="Summary of results">
        <table className="w-full text-sm max-sm:block">
          <tbody className="max-sm:block">
            <tr className="border-b border-rule align-top max-sm:grid max-sm:grid-cols-[1fr_auto] max-sm:gap-x-4">
              <th scope="row" className="py-3 pr-4 text-left font-semibold sm:w-[38%]">Caught after the fact</th>
              <td className="py-3 pr-4 figure text-[2rem] tabular-nums">{pct(h.rules_recall)}</td>
              <td className="py-3 text-ink-2 max-sm:col-span-2 max-sm:pt-0">
                Rule checks on the full history, seeds {pct(h.rules_recall_range[0])}–{pct(h.rules_recall_range[1])}.
                Personal purchases are the hard case.
              </td>
            </tr>
            <tr className="border-b border-rule align-top max-sm:grid max-sm:grid-cols-[1fr_auto] max-sm:gap-x-4">
              <th scope="row" className="py-3 pr-4 text-left font-semibold">Stopped at the swipe</th>
              <td className="py-3 pr-4 figure text-[2rem] text-s2 tabular-nums">{pct(h.replay_stopped)}</td>
              <td className="py-3 text-ink-2 max-sm:col-span-2 max-sm:pt-0">
                While declining {pctSmart(h.replay_legit_declined)} of legitimate spend. Allowing {pct(h2.max_legit)} raises
                that to {pct(h2.planted_incidents_stopped)}.
              </td>
            </tr>
            <tr className="border-b-2 border-ink align-top max-sm:grid max-sm:grid-cols-[1fr_auto] max-sm:gap-x-4">
              <th scope="row" className="py-3 pr-4 text-left font-semibold">AI case reviews</th>
              <td className="py-3 pr-4 figure text-[2rem] tabular-nums">{usd(ai.cost_usd, 2)}</td>
              <td className="py-3 text-ink-2 max-sm:col-span-2 max-sm:pt-0">
                For {ai.investigated} reviews. Of {test.planted} held-out planted cases it was never tuned on, it
                flagged {test.planted_caught} ({test.planted_misuse} as likely misuse) and wrongly flagged{" "}
                {test.controls_flagged} of {test.controls} clean spot checks.
              </td>
            </tr>
          </tbody>
        </table>
      </Section>

      <Section n={3} title="Why controls at the swipe matter">
        <div className="prose-read">
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

      <Section n={4} title="What the rules flagged in two years of real spending">
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
        <p className="prose-read mt-5 text-ink-2">
          That is {summary.rules.flags_per_10k.toFixed(0)} flags per 10,000 purchases. A flag means a purchase is
          worth a second look. It is not a finding of misuse, and nothing here says how many of these flags are
          real problems.
        </p>
      </Section>

      <Section n={5} title="What the AI reviewer concluded">
        <p className="prose-read text-ink-2">
          The {ai.per_rule} largest real flags under each rule ({ai.real_cases} in all), {ai.planted_cases} planted
          cases and {ai.control_cases} clean spot checks went to Claude, running headless with read-only tools: the
          card's history, the merchant's other customers, the agency's spending and the policy text. The reviewer was
          not told which cases were planted or which were controls.
        </p>
        {!cases && <p className="mt-8 text-ink-3">Loading the reviewed cases…</p>}
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {examples.map((c) => (
            // The merchant name is the link; its ::after covers the card, so the whole card opens the case
            // while screen readers still read the reasoning as text.
            <div key={c.case_id} className="group relative border-t-2 border-ink pt-4">
              <Verdict verdict={c.ai.verdict} />
              <Link
                to={`/cases/${c.case_id}`}
                className="mt-3 block font-semibold decoration-2 underline-offset-4 group-hover:underline after:absolute after:inset-0"
              >
                {tidy(c.merchant)}
              </Link>
              <div className="text-sm text-ink-2">
                {tidy(c.agency)}, {c.rule_label}, {usd(c.dollars_at_stake)}
              </div>
              <p className="mt-3 text-[0.95rem] leading-relaxed">{c.ai.explanation}</p>
              {c.planted && (
                <p className="mt-3 text-sm font-semibold">
                  This case was planted ({TYPE_LABEL[c.planted].toLowerCase()}). The reviewer didn't know.
                </p>
              )}
            </div>
          ))}
        </div>
        <p className="mt-6">
          <Link to="/cases" className="inline-flex min-h-11 items-center font-semibold underline underline-offset-4 decoration-2 decoration-s1">
            Review all {ai.cases} cases
          </Link>
        </p>
      </Section>

      <Section n={6} title="How I measured it">
        <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
          <div className="prose-read">
            <p>
              Real data has no answer key: nobody has labeled which of these purchases were misuse. So I planted
              my own. For each of {recall.seeds.length} random seeds I added {recall.n_per_type} incidents of each kind to the real
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
                  <div className="relative mt-1.5 h-2.5 border-b border-rule" aria-hidden="true">
                    <div className="absolute inset-y-0 left-0 bg-ink" style={{ width: `${r.mean * 100}%` }} />
                    {r.max > r.min && (
                      <div
                        className="absolute -inset-y-1 border-x-2 border-ink"
                        style={{ left: `${r.min * 100}%`, width: `${(r.max - r.min) * 100}%` }}
                      />
                    )}
                  </div>
                  <div className="mt-1 text-xs text-ink-3">
                    {r.max > r.min ? `${pct(r.min)}–${pct(r.max)} across seeds` : `${pct(r.min)} on every seed`}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section n={7} title="What this doesn't show">
        <ul className="prose-read list-disc pl-6 space-y-2">
          <li>
            Recall only measures the kinds of misuse I planted, and the rules were designed with those kinds in
            mind. Real misuse can look different.
          </li>
          <li>
            "Legitimate spend declined" treats every real purchase as legitimate, so it overstates the cost of
            each control.
          </li>
          <li>
            The AI's verdicts on real cases are its judgment. No one has checked them, and {ai.planted_cases} planted
            cases is a small sample.
          </li>
          <li>
            This is one state. The data has no card numbers, so a card is an agency plus a cardholder's surname and
            initial, and purchases under statewide contracts, which have no limit, can't be told apart.
          </li>
          <li>Every finding here is a purchase worth reviewing, not an accusation against anyone.</li>
        </ul>
      </Section>

      <Section n={8} title="What I'd build next">
        <ul className="prose-read list-disc pl-6 space-y-2">
          <li>Replay published state audit reports: would these controls have caught what auditors found, and when?</li>
          <li>Run the same pipeline on a second state to see whether the trade-off curve travels.</li>
          <li>Publish the merchant-name cleanup as a labeled benchmark.</li>
          <li>Pit an agent that tries to evade the controls against the reviewer, round by round.</li>
        </ul>
      </Section>
    </article>
  );
}
