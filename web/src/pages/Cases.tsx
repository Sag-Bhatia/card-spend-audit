import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loading } from "../components/Shell";
import { Timeline } from "../components/Timeline";
import { Verdict, verdictLabel } from "../components/Verdict";
import type { Case, VerdictId } from "../data";
import { useData } from "../data";
import { day, pct, tidy, TYPE_LABEL, usd } from "../format";

type Decision = "dismissed" | "escalated";
const KEY = "case-decisions";

function readDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

function useDecisions() {
  const [d, setD] = useState<Record<string, Decision>>(readDecisions);
  const set = (id: string, v: Decision | null) => {
    const next = { ...d };
    if (v) next[id] = v;
    else delete next[id];
    setD(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* not remembered in private mode */
    }
  };
  return [d, set] as const;
}

const VERDICT_ORDER: VerdictId[] = ["likely_misuse", "needs_review", "likely_ok", "error", "pending"];

export function Cases() {
  const { data, error } = useData();
  const { id } = useParams();
  const navigate = useNavigate();
  const [rule, setRule] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [agency, setAgency] = useState("all");
  const [minDollars, setMinDollars] = useState(0);
  const [planted, setPlanted] = useState(true);
  const [decisions, decide] = useDecisions();

  const list = useMemo(() => {
    if (!data) return [];
    return data.cases
      .filter((c) => (rule === "all" || c.rule === rule) && (verdict === "all" || c.ai.verdict === verdict))
      .filter((c) => (agency === "all" || c.agency === agency) && c.dollars_at_stake >= minDollars)
      .filter((c) => planted || !c.planted)
      .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake);
  }, [data, rule, verdict, agency, minDollars, planted]);

  if (!data) return <Loading error={error} />;
  const current = data.cases.find((c) => c.case_id === id) ?? null;
  const rules = [...new Map(data.cases.map((c) => [c.rule, c.rule_label])).entries()];
  const verdicts = VERDICT_ORDER.filter((v) => data.cases.some((c) => c.ai.verdict === v));
  const agencies = [...new Set(data.cases.map((c) => c.agency))].sort();
  const plantedCount = data.cases.filter((c) => c.planted).length;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-10">
      <h1 className="text-3xl font-extrabold tracking-tight">Case review</h1>
      <p className="mt-2 text-ink-2 max-w-3xl">
        The {data.cases.length} flags the AI reviewer worked: the largest real flags under each rule, plus{" "}
        {plantedCount} planted cases it wasn't told about. Dismiss or escalate each one; your choices stay in this browser.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-4 text-sm">
        <label className="grid gap-1">
          <span className="text-ink-2">Rule</span>
          <select value={rule} onChange={(e) => setRule(e.target.value)} className="rounded-md border border-rule bg-surface px-2 py-1.5">
            <option value="all">All rules</option>
            {rules.map(([r, l]) => (
              <option key={r} value={r}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-ink-2">AI verdict</span>
          <select value={verdict} onChange={(e) => setVerdict(e.target.value)} className="rounded-md border border-rule bg-surface px-2 py-1.5">
            <option value="all">All verdicts</option>
            {verdicts.map((v) => (
              <option key={v} value={v}>
                {verdictLabel(v)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-ink-2">Agency</span>
          <select value={agency} onChange={(e) => setAgency(e.target.value)} className="rounded-md border border-rule bg-surface px-2 py-1.5 max-w-[16rem]">
            <option value="all">All agencies</option>
            {agencies.map((a) => (
              <option key={a} value={a}>
                {tidy(a)}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-ink-2">Flagged amount</span>
          <select value={minDollars} onChange={(e) => setMinDollars(Number(e.target.value))} className="rounded-md border border-rule bg-surface px-2 py-1.5">
            {[0, 1000, 10000, 50000].map((v) => (
              <option key={v} value={v}>
                {v ? `${usd(v)} or more` : "Any amount"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-1.5">
          <input type="checkbox" checked={planted} onChange={(e) => setPlanted(e.target.checked)} className="size-4 accent-[var(--series-1)]" />
          Show planted cases
        </label>
        <span className="pb-1.5 text-ink-3 ml-auto">{list.length} shown</span>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[22rem_1fr]">
        <ul className={`min-w-0 border-y border-rule divide-y divide-rule ${current ? "hidden lg:block" : ""} lg:max-h-[calc(100vh-10rem)] lg:overflow-y-auto`}>
          {list.length === 0 && <li className="py-6 text-ink-2">No cases match these filters. Clear a filter to see more.</li>}
          {list.map((c) => (
            <li key={c.case_id}>
              <button
                type="button"
                onClick={() => navigate(`/cases/${c.case_id}`)}
                aria-current={c.case_id === id ? "true" : undefined}
                className={`w-full text-left px-3 py-3 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 hover:bg-paper-2 ${
                  c.case_id === id ? "bg-paper-2 shadow-[inset_3px_0_0_var(--ink)]" : ""
                }`}
              >
                <span className="font-semibold truncate">{tidy(c.merchant)}</span>
                <span className="font-semibold text-right">{usd(c.dollars_at_stake)}</span>
                <span className="text-xs text-ink-2 truncate">
                  {c.rule_label}, {tidy(c.agency)}
                </span>
                <span className="text-right">
                  <Verdict verdict={c.ai.verdict} />
                </span>
                {(c.planted || decisions[c.case_id]) && (
                  <span className="col-span-2 flex gap-2 text-xs">
                    {c.planted && <span className="font-semibold text-s2">Planted</span>}
                    {decisions[c.case_id] && <span className="text-ink-3">You {decisions[c.case_id]} this</span>}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div className="min-w-0">
          {current ? (
            <Detail c={current} decision={decisions[current.case_id]} decide={(v) => decide(current.case_id, v)} />
          ) : (
            <div className="hidden lg:block rounded-xl border border-dashed border-rule-strong p-10 text-ink-2">
              Pick a case on the left to see the evidence and the reviewer's reasoning.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Detail({ c, decision, decide }: { c: Case; decision?: Decision; decide: (v: Decision | null) => void }) {
  const ai = c.ai;
  const cited = new Set(ai.evidence_txn_ids ?? []);
  return (
    <article className="rounded-xl border border-rule bg-surface p-5 sm:p-7">
      <Link to="/cases" className="lg:hidden text-sm font-semibold text-ink-2">
        Back to all cases
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-sm text-ink-2">
            {c.case_id}, {c.rule_label}
          </div>
          <h2 className="text-2xl font-bold tracking-tight">{tidy(c.merchant)}</h2>
          <div className="text-ink-2">
            {tidy(c.agency)}, {c.card}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold">{usd(c.dollars_at_stake, 2)}</div>
          <div className="text-xs text-ink-3">flagged</div>
        </div>
      </div>
      {c.planted && (
        <p className="mt-4 rounded-md bg-paper-2 px-3 py-2 text-sm">
          <span className="font-semibold text-s2">Planted test case:</span> {TYPE_LABEL[c.planted].toLowerCase()}, added
          to the data on purpose. The reviewer was not told.
        </p>
      )}

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">AI reviewer</h3>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Verdict verdict={ai.verdict} size="lg" />
          {ai.confidence !== undefined && <span className="text-sm text-ink-3">{pct(ai.confidence)} confident</span>}
        </div>
        {ai.explanation && <p className="mt-3 font-serif text-lg leading-relaxed max-w-[64ch]">{ai.explanation}</p>}
        {ai.innocent_explanation && (
          <p className="mt-3 text-sm text-ink-2 max-w-[64ch]">
            <span className="font-semibold text-ink">Innocent explanation: </span>
            {ai.innocent_explanation}
          </p>
        )}
        {ai.dollars_at_issue !== undefined && (
          <p className="mt-2 text-sm text-ink-2">
            <span className="font-semibold text-ink">Dollars it thinks are at issue: </span>
            {usd(ai.dollars_at_issue, 2)}
          </p>
        )}
        {ai.error && <p className="mt-2 text-sm text-bad">The reviewer gave no valid answer: {ai.error}</p>}
      </section>

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">Why the rule flagged it</h3>
        <p className="mt-1">{c.evidence}.</p>
        <p className="mt-1 text-sm text-ink-3">{c.clause}</p>
      </section>

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">This card, 30 days either side</h3>
        <div className="mt-2">
          <Timeline c={c} />
        </div>
      </section>

      <section className="mt-6 overflow-x-auto">
        <h3 className="text-sm font-semibold text-ink-2">Flagged purchases</h3>
        <table className="mt-2 w-full text-sm">
          <thead>
            <tr className="text-left text-ink-3 border-b border-rule">
              <th className="py-1.5 pr-3 font-semibold hidden sm:table-cell">Date</th>
              <th className="py-1.5 pr-3 font-semibold hidden sm:table-cell">Merchant</th>
              <th className="py-1.5 pr-3 font-semibold">Item description</th>
              <th className="py-1.5 font-semibold text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {c.txns.slice(0, 40).map((t) => (
              <tr key={t.txn_id} className="border-b border-rule align-top">
                <td className="py-1.5 pr-3 whitespace-nowrap hidden sm:table-cell">{day(t.date)}</td>
                <td className="py-1.5 pr-3 hidden sm:table-cell">
                  {t.merchant_raw}
                  {cited.has(t.txn_id) && <span className="ml-2 text-xs font-semibold text-s1">cited by AI</span>}
                </td>
                <td className="py-1.5 pr-3 text-ink-2">
                  {t.description}
                  <span className="sm:hidden block text-xs text-ink-3">
                    {day(t.date)}
                    {cited.has(t.txn_id) && <span className="ml-2 font-semibold text-s1">cited by AI</span>}
                  </span>
                </td>
                <td className="py-1.5 text-right whitespace-nowrap">{usd(t.amount, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {c.txn_count > 40 && (
          <p className="mt-2 text-sm text-ink-3">and {c.txn_count - 40} more in this flag</p>
        )}
      </section>

      <section className="mt-8 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => decide(decision === "escalated" ? null : "escalated")}
          aria-pressed={decision === "escalated"}
          className={`rounded-md px-4 py-2 font-semibold border-2 ${
            decision === "escalated" ? "bg-ink text-paper border-ink" : "border-ink hover:bg-paper-2"
          }`}
        >
          {decision === "escalated" ? "Escalated" : "Escalate"}
        </button>
        <button
          type="button"
          onClick={() => decide(decision === "dismissed" ? null : "dismissed")}
          aria-pressed={decision === "dismissed"}
          className={`rounded-md px-4 py-2 font-semibold border-2 ${
            decision === "dismissed" ? "bg-ink text-paper border-ink" : "border-rule-strong hover:bg-paper-2"
          }`}
        >
          {decision === "dismissed" ? "Dismissed" : "Dismiss"}
        </button>
        {ai.verdict !== "pending" && c.ai_meta.seconds !== null && (
          <span className="ml-auto text-xs text-ink-3">
            Reviewed by {c.ai_meta.model} in {c.ai_meta.seconds}s
            {c.ai_meta.cost_usd !== null ? `, ${usd(c.ai_meta.cost_usd, 3)} at API prices` : ""}
          </span>
        )}
      </section>
    </article>
  );
}
