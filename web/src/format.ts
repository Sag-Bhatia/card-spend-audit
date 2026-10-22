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
    .replace(/\b(Ok|Okc|Llc|Inc|It|Us|Usa|Dhs|Dot|Ups|Shi|Mms|Bk|Cat|At&t)\b/gi, (w) => w.toUpperCase());

export const TYPE_LABEL: Record<string, string> = {
  split: "Split purchases",
  duplicate: "Double charges",
  prohibited: "Prohibited categories",
  personal: "Personal purchases",
};
