// Shapes of the JSON written by `python -m spendaudit export` (spendaudit/export.py).
// The site only displays these numbers; it never computes a metric.
import { useEffect, useState } from "react";

export type RuleId = "split" | "duplicate" | "prohibited" | "unusual" | "spot_check";
export type VerdictId = "likely_misuse" | "needs_review" | "likely_ok" | "error" | "pending";
export type PlantType = "split" | "duplicate" | "prohibited" | "personal";

export interface Example {
  txn_id: string;
  date: string;
  amount: number;
  merchant_norm: string;
  mcc: string;
  agency: string;
  reason: string;
}

export interface CurvePoint {
  s: number;
  split_window_days: number;
  split_multiple: number | null;
  split_threshold_usd: number | null;
  duplicate_window_days: number | null;
  anomaly_multiple: number | null;
  consumer_guard: boolean;
  legit_dollars_declined_pct: number;
  legit_txns_declined_pct: number;
  flagged_dollars_blocked_pct: number | null;
  planted_dollars_blocked_pct: number;
  planted_incidents_stopped: number;
  planted_incidents_stopped_by_type: Record<PlantType, number>;
  by_reason: Record<string, number>;
  newly_declined: { txns: number; usd: number };
  past_plateau: boolean;
  examples: Example[];
}

export interface Headline {
  s: number;
  max_legit: number;
  legit_dollars_declined_pct: number;
  planted_incidents_stopped: number;
  planted_incidents_stopped_by_type: Record<PlantType, number>;
  seed_range?: [number, number];
}

export interface Summary {
  generated: string;
  source: string;
  profile: {
    rows: number;
    first_date: string;
    last_date: string;
    months: number;
    first_month: string;
    last_month: string;
    dollars: number;
    dollars_positive: number;
    refunds: number;
    agencies: number;
    cards: number;
    mcc_categories: number;
    rows_dropped: number;
  };
  policy: {
    limit: number;
    limit_clause: string;
    split_window_days: number;
    duplicate_window_days: number;
    anomaly_multiple: number;
    anomaly_min_history: number;
    sources: Record<string, string>;
    prohibited: { label: string; clause: string }[];
  };
  headline: {
    rules_recall: number;
    rules_recall_range: [number, number];
    replay_stopped: number;
    replay_stopped_range: [number, number];
    replay_legit_declined: number;
    replay_budget: number;
    replay_s: number;
    dollars_audited: number;
    txns_audited: number;
    ai_cost_usd: number;
    ai_cases: number;
  };
  replay_headlines: Record<string, Headline>;
  replay_seconds: number;
  replay_rows: number;
  rules: {
    by_rule: { rule: RuleId; label: string; flags: number; dollars: number; txns: number }[];
    total_flags: number;
    flags_per_10k: number;
    flagged_txns: number;
  };
  ai: {
    cases: number;
    investigated: number;
    real_cases: number;
    planted_cases: number;
    control_cases: number;
    real_verdicts: Record<VerdictId, number>;
    planted_verdicts: Record<VerdictId, number>;
    control_verdicts: Record<VerdictId, number>;
    planted_flagged_by_ai: number;
    controls_flagged_by_ai: number;
    planted_by_type: Record<PlantType, { n: number; caught: number; misuse: number }>;
    cost_usd: number;
    cost_per_case_usd: number | null;
    tokens: number;
    seconds_mean: number | null;
    model: string | null;
    per_rule: number;
  };
}

export interface Recall {
  by_type: { type: PlantType; mean: number; min: number; max: number; incidents: number }[];
  overall_mean: number;
  overall_min: number;
  overall_max: number;
  flags_per_10k_real: number;
  seeds: number[];
  n_per_type: number;
}

export interface Rules {
  agencies: {
    agency: string;
    spend: number;
    cards: number;
    flags: number;
    flagged: number;
    flags_per_million: number;
    flagged_share: number;
  }[];
}

export interface CaseTxn {
  txn_id: string;
  date: string;
  amount: number;
  merchant_raw: string;
  mcc: string;
  description: string | null;
}

export interface Case {
  case_id: string;
  rule: RuleId;
  rule_label: string;
  card: string;
  agency: string;
  merchant: string;
  dollars_at_stake: number;
  evidence: string;
  clause: string;
  txns: CaseTxn[];
  txn_count: number;
  timeline: { txn_id: string; date: string; amount: number; merchant_norm: string; flagged: boolean }[];
  planted: PlantType | null;
  control: boolean;
  ai: {
    verdict: VerdictId;
    confidence?: number;
    explanation?: string;
    evidence_txn_ids?: string[];
    policy_clause?: string;
    innocent_explanation?: string;
    dollars_at_issue?: number;
    error?: string;
  };
  ai_meta: { cost_usd: number | null; seconds: number | null; attempts: number | null; model: string | null };
}

export interface Merchants {
  raw_descriptors: number;
  merchants: number;
  top: { merchant_norm: string; dollars: number; txns: number; raw_variants: number; samples: string[] }[];
}

export interface Data {
  summary: Summary;
  curve: CurvePoint[];
  recall: Recall;
  rules: Rules;
  cases: Case[];
  merchants: Merchants;
}

const FILES = ["summary", "curve", "recall", "rules", "cases", "merchants"] as const;
let cache: Promise<Data> | null = null;

export function loadData(): Promise<Data> {
  cache ??= Promise.all(
    FILES.map((f) =>
      fetch(`${import.meta.env.BASE_URL}data/${f}.json`).then((r) => {
        if (!r.ok) throw new Error(`data/${f}.json returned ${r.status}`);
        return r.json();
      }),
    ),
  ).then(([summary, curve, recall, rules, cases, merchants]) => ({
    summary,
    curve,
    recall,
    rules,
    cases,
    merchants,
  }));
  return cache;
}

export function useData(): { data: Data | null; error: string | null } {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    loadData().then(setData, (e: Error) => setError(e.message));
  }, []);
  return { data, error };
}
