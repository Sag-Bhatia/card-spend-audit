import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams, type To } from "react-router-dom";
import { Flag, X } from "lucide-react";
import { Loading } from "../components/Shell";
import { Timeline } from "../components/Timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

function Filter({
  label,
  value,
  onChange,
  options,
  wide,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly (readonly [string, string])[];
  wide?: boolean;
  className?: string;
}) {
  return (
    <div className={`grid min-w-0 gap-1 ${className}`}>
      <Label className="text-sm font-normal text-ink-2">{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger aria-label={label} className={`h-11 w-full bg-surface ${wide ? "sm:w-[16rem]" : "sm:w-[11rem]"}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map(([v, l]) => (
            <SelectItem key={v} value={v}>
              {l}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

const VERDICT_ORDER: VerdictId[] = ["likely_misuse", "needs_review", "likely_ok", "error", "pending"];

const FILTER_DEFAULTS = { rule: "all", verdict: "all", agency: "all", min: "0", tests: "1" };
type FilterKey = keyof typeof FILTER_DEFAULTS;

export function Cases() {
  const { data, error } = useData();
  const { id } = useParams();
  const navigate = useNavigate();
  // Filters live in the URL so a filtered view survives reloads and can be shared.
  const [params, setParams] = useSearchParams();
  const get = (k: FilterKey) => params.get(k) ?? FILTER_DEFAULTS[k];
  const setFilter = (k: FilterKey, v: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v === FILTER_DEFAULTS[k]) next.delete(k);
        else next.set(k, v);
        return next;
      },
      { replace: true },
    );
  const [rule, verdict, agency, minDollars, planted] = [
    get("rule"),
    get("verdict"),
    get("agency"),
    Number(get("min")),
    get("tests") === "1",
  ];
  const filtered = (Object.keys(FILTER_DEFAULTS) as FilterKey[]).some((k) => params.has(k));
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [decisions, decide] = useDecisions();
  const listY = useRef(0);
  const article = useRef<HTMLDivElement>(null);
  const wide = () => window.matchMedia?.("(min-width: 1024px)").matches ?? true;

  const list = useMemo(() => {
    if (!data) return [];
    return data.cases
      .filter((c) => (rule === "all" || c.rule === rule) && (verdict === "all" || c.ai.verdict === verdict))
      .filter((c) => (agency === "all" || c.agency === agency) && c.dollars_at_stake >= minDollars)
      .filter((c) => planted || (!c.planted && !c.control))
      .sort((a, b) => b.dollars_at_stake - a.dollars_at_stake);
  }, [data, rule, verdict, agency, minDollars, planted]);

  const open = (caseId: string) => navigate({ pathname: `/cases/${caseId}`, search: params.toString() });
  const pos = list.findIndex((c) => c.case_id === id);
  const step = (d: number) => {
    const next = list[pos + d];
    if (next) open(next.case_id);
  };

  // Wide screens: open the top case instead of an empty pane.
  useEffect(() => {
    if (!id && list.length && wide()) navigate({ pathname: `/cases/${list[0].case_id}`, search: params.toString() }, { replace: true });
  }, [id, list, navigate, params]);

  // Phones show list or detail, not both: open a case at its top, and come back to the same place in the list.
  useEffect(() => {
    if (wide()) return;
    if (id) article.current?.scrollIntoView({ block: "start" });
    else window.scrollTo(0, listY.current);
  }, [id]);

  // j/k move between cases, e/d escalate or dismiss, unless typing or a menu is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (!id || e.metaKey || e.ctrlKey || e.altKey || t.closest("input, textarea, [role=listbox], [role=combobox]")) return;
      if (e.key === "j") step(1);
      else if (e.key === "k") step(-1);
      else if (e.key === "e") decide(id, decisions[id] === "escalated" ? null : "escalated");
      else if (e.key === "d") decide(id, decisions[id] === "dismissed" ? null : "dismissed");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!data) return <Loading error={error} />;
  const current = data.cases.find((c) => c.case_id === id) ?? null;
  const rules = [...new Map(data.cases.map((c) => [c.rule, c.rule_label])).entries()];
  const verdicts = VERDICT_ORDER.filter((v) => data.cases.some((c) => c.ai.verdict === v));
  const agencies = [...new Set(data.cases.map((c) => c.agency))].sort();
  const plantedCount = data.cases.filter((c) => c.planted).length;
  const controlCount = data.cases.filter((c) => c.control).length;
  const decided = data.cases.filter((c) => decisions[c.case_id]).length;
  const activeCount = (Object.keys(FILTER_DEFAULTS) as FilterKey[]).filter((k) => params.has(k)).length;
  const clear = () => setParams(new URLSearchParams(), { replace: true });

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 pt-8">
      <h1 className="heading text-[1.75rem] sm:text-[2rem]">Case review</h1>
      <p className="mt-1 text-ink-2 max-w-[72ch]">
        {data.cases.length} cases the AI reviewer worked, including {plantedCount} planted and {controlCount} clean
        controls it wasn't told about. Your decisions stay in this browser.
      </p>

      <Button
        variant="outline"
        className="mt-4 h-11 sm:hidden"
        onClick={() => setFiltersOpen((o) => !o)}
        aria-expanded={filtersOpen}
        aria-controls="case-filters"
      >
        {filtersOpen ? "Hide filters" : activeCount ? `Filters (${activeCount})` : "Filters"}
      </Button>
      <div
        id="case-filters"
        className={`mt-4 grid-cols-2 gap-3 text-sm sm:flex sm:flex-wrap sm:items-end sm:gap-4 ${filtersOpen ? "grid" : "hidden"}`}
      >
        <Filter label="Rule" value={rule} onChange={(v) => setFilter("rule", v)} options={[["all", "All rules"], ...rules]} />
        <Filter
          label="AI verdict"
          value={verdict}
          onChange={(v) => setFilter("verdict", v)}
          options={[["all", "All verdicts"], ...verdicts.map((v) => [v, verdictLabel(v)] as const)]}
        />
        <Filter
          label="Agency"
          value={agency}
          onChange={(v) => setFilter("agency", v)}
          options={[["all", "All agencies"], ...agencies.map((a) => [a, tidy(a)] as const)]}
          wide
          className="col-span-2 sm:col-span-1"
        />
        <Filter
          label="Flagged amount"
          value={String(minDollars)}
          onChange={(v) => setFilter("min", v)}
          options={[0, 1000, 5000, 10000, 25000, 50000].map((v) => [String(v), v ? `${usd(v)} or more` : "Any amount"] as const)}
        />
        <div className="flex items-center gap-2 h-11">
          <Checkbox id="test-cases" checked={planted} onCheckedChange={(v) => setFilter("tests", v === true ? "1" : "0")} />
          <Label htmlFor="test-cases" className="text-sm font-normal">
            Show test cases
          </Label>
        </div>
        {filtered && (
          <Button variant="ghost" className="h-11 text-ink-2" onClick={clear}>
            Clear filters
          </Button>
        )}
      </div>
      <p className="mt-3 text-sm text-ink-3" aria-live="polite">
        {list.length} shown, {decided} of {data.cases.length} decided
      </p>

      <div className="mt-3 grid gap-6 lg:grid-cols-[22rem_1fr]">
        <ul className={`min-w-0 border-y-2 border-ink divide-y divide-rule ${current ? "hidden lg:block" : ""} lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:sticky lg:top-4`}>
          {list.length === 0 && (
            <li className="py-6 text-ink-2">
              No cases match these filters.{" "}
              <Button variant="link" className="h-auto p-0 align-baseline" onClick={clear}>
                Clear filters
              </Button>
            </li>
          )}
          {list.map((c) => (
            <li key={c.case_id}>
              <button
                type="button"
                onClick={() => {
                  listY.current = window.scrollY;
                  open(c.case_id);
                }}
                aria-current={c.case_id === id ? "true" : undefined}
                className={`w-full text-left px-3 py-3 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 hover:bg-paper-2 ${
                  c.case_id === id ? "ring-2 ring-inset ring-ink" : ""
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
                {(c.planted || c.control || decisions[c.case_id]) && (
                  <span className="col-span-2 flex gap-2 text-xs">
                    {c.planted && <Badge variant="outline" className="border-ink text-ink">Planted</Badge>}
                    {c.control && <Badge variant="outline" className="border-dashed border-ink text-ink">Control</Badge>}
                    {decisions[c.case_id] && <span className="text-ink-3">You {decisions[c.case_id]} this</span>}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div className="min-w-0 scroll-mt-4" ref={article}>
          {current && (
            <Detail
              c={current}
              back={{ pathname: "/cases", search: params.toString() }}
              decision={decisions[current.case_id]}
              decide={(v) => decide(current.case_id, v)}
              next={pos >= 0 && pos < list.length - 1 ? () => step(1) : undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function Detail({
  c,
  back,
  decision,
  decide,
  next,
}: {
  c: Case;
  back: To;
  decision?: Decision;
  decide: (v: Decision | null) => void;
  next?: () => void;
}) {
  const ai = c.ai;
  const cited = new Set(ai.evidence_txn_ids ?? []);
  return (
    <article className="border-t-2 border-ink pt-5">
      <Link to={back} className="lg:hidden inline-flex h-11 items-center text-sm font-semibold text-ink-2">
        Back to all cases
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="heading text-[1.625rem]">{tidy(c.merchant)}</h2>
          <div className="text-ink-2">
            {tidy(c.agency)}, {c.card}
          </div>
          <div className="text-sm text-ink-2">
            {c.case_id}, {c.rule_label}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold">{usd(c.dollars_at_stake, 2)}</div>
          <div className="text-xs text-ink-3">{c.control ? "spot-checked" : "flagged"}</div>
        </div>
      </div>
      <section className="mt-5 flex flex-wrap items-center gap-3" aria-label="Your decision">
        <Button
          variant={decision === "escalated" ? "default" : "outline"}
          size="lg"
          className="h-11"
          onClick={() => decide(decision === "escalated" ? null : "escalated")}
          aria-pressed={decision === "escalated"}
        >
          <Flag aria-hidden="true" />
          {decision === "escalated" ? "Escalated" : "Escalate"}
        </Button>
        <Button
          variant={decision === "dismissed" ? "default" : "outline"}
          size="lg"
          className="h-11"
          onClick={() => decide(decision === "dismissed" ? null : "dismissed")}
          aria-pressed={decision === "dismissed"}
        >
          <X aria-hidden="true" />
          {decision === "dismissed" ? "Dismissed" : "Dismiss"}
        </Button>
        {next && (
          <Button variant="ghost" size="lg"
          className="h-11" onClick={next}>
            Next case
          </Button>
        )}
        <span className="hidden lg:inline ml-auto text-xs text-ink-3">j / k to move, e / d to decide</span>
      </section>
      {c.planted && (
        <p className="mt-4 border-y border-ink py-2 text-sm">
          <span className="font-semibold">Planted test case:</span> {TYPE_LABEL[c.planted].toLowerCase()}, added
          to the data on purpose. The reviewer was not told.
        </p>
      )}
      {c.control && (
        <p className="mt-4 border-y border-ink py-2 text-sm">
          <span className="font-semibold">Control case:</span> a real purchase no rule flagged, picked at random to
          check that the reviewer doesn't flag everything. The reviewer was not told.
        </p>
      )}

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">AI reviewer</h3>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Verdict verdict={ai.verdict} size="lg" />
          {ai.confidence !== undefined && <span className="text-sm text-ink-3">{pct(ai.confidence)} confident</span>}
        </div>
        {ai.explanation && <p className="mt-3 text-lg leading-relaxed max-w-[64ch]">{ai.explanation}</p>}
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
        {ai.verdict !== "pending" && c.ai_meta.seconds !== null && (
          <p className="mt-2 text-xs text-ink-3">
            Reviewed by Claude {c.ai_meta.model} in {c.ai_meta.seconds}s
            {c.ai_meta.cost_usd !== null ? `, ${usd(c.ai_meta.cost_usd, 3)} at API prices` : ""}
          </p>
        )}
      </section>

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">{c.control ? "Why it was picked" : "Why the rule flagged it"}</h3>
        <p className="mt-1">{c.evidence.replace(/\.$/, "")}.</p>
        <p className="mt-1 text-sm text-ink-3">{c.clause}</p>
      </section>

      <section className="mt-6">
        <h3 className="text-sm font-semibold text-ink-2">This card, 30 days either side</h3>
        <div className="mt-2">
          <Timeline c={c} />
        </div>
      </section>

      <section className="mt-6 overflow-x-auto">
        <h3 className="text-sm font-semibold text-ink-2">{c.control ? "The purchase" : "Flagged purchases"}</h3>
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

    </article>
  );
}
