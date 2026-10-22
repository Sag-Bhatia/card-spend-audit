"""Merchant descriptor cleanup (spec §3): raw card descriptor -> `merchant_norm`."""

import re

import polars as pl
from rapidfuzz import fuzz, process

# Processor / aggregator prefixes that sit in front of the real merchant name. The portal often
# drops the "*" ("SQ  CORNER COPY"), so most also match with whitespace alone.
PREFIXES = re.compile(
    r"^(SQ|TST|PAYPAL|PP|SP|PY|IN|I3P|FS|GOOGLE|EB|CKE|BT|WPY|ACT|DD|EIG|SMK|CLR|LS|SPO|ZSK)"
    r"\s*\*\s*"
    r"|^(SQ|TST|PAYPAL|PY|SP|CKE|LS|SPO|ZSK|EB|DD|BT|I3P)\s+(?=\S)"
    r"|^(IN|FS)\s{2,}"
    r"|^2(?=[A-Z])"
)
# Trailing locations: state codes and the largest Oklahoma cities.
# shortcut: a fixed city list, not a gazetteer; extend if other places show up in top clusters.
LOCATION = re.compile(
    r"\s+(OK|OKLA|TX|KS|AR|MO|CO|NM|OKLAHOMA CITY|OKC|TULSA|NORMAN|STILLWATER|LAWTON|EDMOND|"
    r"MOORE|BROKEN ARROW|ENID|MUSKOGEE|MIDWEST CITY|OWASSO|SHAWNEE|ARDMORE|PONCA CITY|"
    r"BARTLESVILLE|DURANT|YUKON|ALTUS|TAHLEQUAH|WEATHERFORD|ADA|DUNCAN|MCALESTER|"
    r"CLAREMORE|GUTHRIE|CHICKASHA|WOODWARD|ALVA|GOODWELL|IDABEL|GROVE)$"
)

# Big merchants whose descriptors vary too much for fuzzy matching (order codes, product lines).
ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p), name)
    for p, name in [
        (r"^(AMAZON|AMZN)\b|^AMAZON\.", "AMAZON"),
        (r"^(AT ?& ?T|ATT)\b", "AT&T"),
        (r"^WAL-?MART|^WM SUPERCENTER", "WALMART"),
        (r"^(THE )?HOME ?DEPOT", "HOME DEPOT"),
        (r"^LOWES\b", "LOWES"),
        (r"^STAPLES\b", "STAPLES"),
        (r"^SOUTHWES(\s+\d|T AIR)", "SOUTHWEST AIRLINES"),
        (r"^AMERICAN AI(R|\s+\d)", "AMERICAN AIRLINES"),
        (r"^UNITED AIR|^UNITED +\d{6,}", "UNITED AIRLINES"),
        (r"^DELTA AIR", "DELTA AIR LINES"),
        (r"^HOLIDAY INN", "HOLIDAY INN"),
        (r"^FEDEX", "FEDEX"),
        (r"^UPS\b", "UPS"),
        (r"^USPS\b", "USPS"),
        (r"^TARGET\b", "TARGET"),
        (r"^COSTCO\b", "COSTCO"),
        (r"^SAMS ?CLUB|^SAMSCLUB|^SAM S CLUB", "SAMS CLUB"),
        (r"^DOLLAR ?GENERAL|^DOLLAR-GENERAL", "DOLLAR GENERAL"),
        (r"^FASTENAL\b", "FASTENAL"),
        (r"^NAPA\b", "NAPA AUTO PARTS"),
        (r"^OPENAI\b", "OPENAI"),
        (r"^ZOOM\b", "ZOOM"),
        (r"^ADOBE\b", "ADOBE"),
        (r"^MICROSOFT\b|^MSFT\b", "MICROSOFT"),
        (r"^APPLE\.COM|^APPLE\b", "APPLE"),
        (r"^VERIZON", "VERIZON"),
        (r"^COX\b", "COX COMMUNICATIONS"),
        (r"^EXPEDIA\b", "EXPEDIA"),
        (r"^UBER\b", "UBER"),
        (r"^LYFT\b", "LYFT"),
    ]
]
SUFFIXES = re.compile(r"\b(INC|LLC|L L C|CORP|CORPORATION|CO|COMPANY|LP|LTD|PLLC)$")


def normalize(raw: str) -> str:
    """Strip processor prefixes, store numbers, order codes and legal suffixes. Deterministic."""
    s = raw.upper().strip()
    s = PREFIXES.sub("", s).strip()
    for pattern, name in ALIASES:
        if pattern.search(s):
            return name
    s = re.sub(r"\.(COM|ORG|NET|GOV|EDU|US)\b.*$", "", s)
    s = re.sub(r"/US\b", "", s)
    s = re.sub(r"#\s*\S*", " ", s)  # store numbers: "LOWES #00907"
    s = re.sub(r"(?<=[A-Z])\d{3,}\S*", " ", s)  # glued codes: "FEDEX57680723"
    s = re.sub(r"[^\w&' ]", " ", s)
    tokens = s.split()
    # Drop a leading store number ("126 BRAUMS STORE") and tokens holding digits after the first
    # (order codes, store ids, phone numbers).
    if len(tokens) > 1 and tokens[0].isdigit():
        tokens = tokens[1:]
    tokens = tokens[:1] + [t for t in tokens[1:] if not any(c.isdigit() for c in t)]
    s = " ".join(tokens)
    for _ in range(2):
        s = SUFFIXES.sub("", s).strip()
        cut = LOCATION.sub("", s).strip()
        if len(s.split()) > 2 and not cut.endswith(" OF"):  # keep "CITY OF STILLWATER"
            s = cut
    return s or raw.upper().strip()


def cluster(names: pl.DataFrame, cutoff: float = 92) -> dict[str, str]:
    """Map each normalized name to a canonical one. `names` has columns `name`, `n` (txn count).

    Within a block sharing the first token, names are visited by frequency; each joins the first
    canonical it matches (token_sort_ratio ≥ cutoff, or a ≥10-char prefix match because the
    source truncates merchant names at 25 chars), else becomes canonical itself."""
    mapping: dict[str, str] = {}
    ordered = names.sort(
        ["n", "name"], descending=[True, False]
    )  # ties broken by name: deterministic
    blocks: dict[str, list[str]] = {}
    for name in ordered["name"]:
        block = blocks.setdefault(name.split(" ", 1)[0], [])
        hit = None
        short = [c for c in block if (c.startswith(name) or name.startswith(c))]
        if short and min(len(name), len(short[0])) >= 10:
            hit = short[0]
        elif block:
            best = process.extractOne(
                name, block, scorer=fuzz.token_sort_ratio, score_cutoff=cutoff
            )
            hit = best[0] if best else None
        if hit is None:
            block.append(name)
            hit = name
        mapping[name] = hit
    return mapping


def add_merchant_norm(df: pl.DataFrame) -> pl.DataFrame:
    """Adds `merchant_norm` to a common-schema frame."""
    raw = df.select("merchant_raw").unique()
    raw = raw.with_columns(
        pl.col("merchant_raw").map_elements(normalize, return_dtype=pl.String).alias("name")
    )
    counts = df.select("merchant_raw").join(raw, on="merchant_raw").group_by("name").agg(n=pl.len())
    mapping = cluster(counts)
    raw = raw.with_columns(
        pl.col("name").replace_strict(mapping, return_dtype=pl.String).alias("merchant_norm")
    )
    return df.join(raw.select("merchant_raw", "merchant_norm"), on="merchant_raw", how="left")


def top_clusters(df: pl.DataFrame, k: int = 30) -> pl.DataFrame:
    """The k largest clusters by spend, with raw-descriptor counts and samples (Method page)."""
    return (
        df.group_by("merchant_norm")
        .agg(
            dollars=pl.col("amount").sum(),
            txns=pl.len(),
            raw_variants=pl.col("merchant_raw").n_unique(),
            samples=pl.col("merchant_raw").unique().sort().head(5),
        )
        .sort("dollars", descending=True)
        .head(k)
    )
