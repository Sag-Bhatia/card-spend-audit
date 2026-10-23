export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

/** Percent with enough precision to stay readable for small values (0.74% not 1%). */
export const pctSmart = (x: number) => pct(x, x < 0.1 ? (x < 0.01 ? 2 : 1) : 0);

export const usd = (x: number, digits = 0) =>
  x.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const usdCompact = (x: number) =>
  x >= 1e6 ? `$${(x / 1e6).toFixed(1)}M` : x >= 1e3 ? `$${(x / 1e3).toFixed(x >= 1e4 ? 0 : 1)}K` : usd(x);

/** A score with its sign, e.g. +0.65 or −0.10. */
export const signed = (x: number) => `${x < 0 ? "−" : "+"}${Math.abs(x).toFixed(2)}`;

export const int = (x: number) => x.toLocaleString("en-US");

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const day = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
};

export const month = (iso: string) => {
  const [y, m] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
};

/** Title-case an all-caps source string ("DEPARTMENT OF HUMAN SERVICES" → "Department of Human Services"). */
export const tidy = (s: string) =>
  s
    .toLowerCase()
    .replace(/\b(\w)/g, (c) => c.toUpperCase())
    .replace(/\b(Of|And|The|For|In|On|At|To|By)\b/g, (w, _m, i: number) => (i === 0 ? w : w.toLowerCase()))
    .replace(/\b(Ok|Okc|Llc|Inc|It|Us|Usa|Dhs|Dot|Ups|Shi|Mms|Bk|Cat|At&t|Dmi|Csa|Osu|Ou)\b/gi, (w) => w.toUpperCase())
    // Runs of 3-4 letters with no vowel (or y) are initials in card descriptors (WGC, TFS), not words.
    .replace(/\b[b-df-hj-np-tv-xz]{3,4}\b/gi, (w) => w.toUpperCase());

/** Plain names for the replay's decline reasons, matching the controls listed beside the curve. */
export const REASON_LABEL: Record<string, string> = {
  "prohibited category": "banned category",
  "split guard": "split-purchase limit",
  "duplicate guard": "identical charge again",
  "first consumer purchase on card": "card's first consumer purchase",
  "unusual amount for card": "far above the card's largest purchase",
};

export const TYPE_LABEL: Record<string, string> = {
  split: "Split purchases",
  duplicate: "Double charges",
  prohibited: "Prohibited categories",
  personal: "Personal purchases",
};
