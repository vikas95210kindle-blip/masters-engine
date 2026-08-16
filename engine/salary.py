"""Real salary evidence, parsed from real job postings.

This replaces guesswork. SPEC §22 forbids presenting estimates as facts, and
the previous approach could only offer the country's legal permit threshold as
a "floor proxy" — honest, but not a market salary.

164 of the collected postings state an actual figure. Parsing those gives
role-specific, country-specific, current market evidence for the exact jobs he
is targeting, with a sample size attached to every number.

Deliberate conservatism:
  - anything outside 20k-400k/yr is discarded as unparseable rather than
    guessed at (stipends, hourly rates, equity figures, typos)
  - monthly figures are detected and annualised only when the text says so
  - a median is only reported at n>=5; below that the raw observations are
    shown instead, because a "median" of two numbers is theatre
"""

import re
import statistics

# Conversion to EUR. These are ASSUMPTIONS, stated wherever a converted figure
# is displayed, and deliberately round — pretending to 4dp precision on an
# unsourced rate would be false confidence.
FX = {"EUR": 1.0, "GBP": 1.16, "USD": 0.92, "CHF": 1.05, "SEK": 0.088,
      "DKK": 0.134, "NOK": 0.086, "SGD": 0.69, "AUD": 0.61, "CAD": 0.68,
      "INR": 0.011, "AED": 0.25}

MARKET_CCY = {"Ireland": "EUR", "Netherlands": "EUR", "Germany": "EUR",
              "Belgium": "EUR", "Luxembourg": "EUR", "United Kingdom": "GBP",
              "India": "INR"}

MIN_ANNUAL = 20000
MAX_ANNUAL = 400000

_NUM = r"\d[\d,\. ]{2,}"
_PATTERNS = [
    # explicit currency symbol or code before the number
    re.compile(r"(?P<cur>[€£$]|EUR|GBP|USD)\s?(?P<a>" + _NUM + r")\s*(?:-|–|to)\s*(?P<cur2>[€£$]|EUR|GBP|USD)?\s?(?P<b>" + _NUM + r")", re.I),
    re.compile(r"(?P<cur>[€£$]|EUR|GBP|USD)\s?(?P<a>" + _NUM + r")", re.I),
    # number followed by a currency code
    re.compile(r"(?P<a>" + _NUM + r")\s*(?P<cur>EUR|GBP|USD)\b", re.I),
]

_MONTHLY = re.compile(r"per month|/month|monthly|p\.m\.|per maand", re.I)
_HOURLY = re.compile(r"per hour|/hour|hourly|per uur", re.I)

_CUR_MAP = {"€": "EUR", "£": "GBP", "$": "USD"}


def _clean(n):
    """'150.000' and '150,000' both mean 150000 in this corpus."""
    s = n.strip().replace(" ", "")
    if re.search(r"[.,]\d{3}\b", s):
        s = re.sub(r"[.,](?=\d{3}\b)", "", s)
    s = s.replace(",", "").rstrip(".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_salaries(text, default_currency="EUR"):
    """Return a list of {low, high, currency, annual} observations."""
    if not text:
        return []
    out = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            window = text[max(0, m.start() - 60):m.end() + 60]
            if _HOURLY.search(window):
                continue
            cur = (m.groupdict().get("cur") or default_currency).upper()
            cur = _CUR_MAP.get(cur, cur)
            if cur not in FX:
                continue
            a = _clean(m.group("a"))
            b = _clean(m.groupdict().get("b")) if m.groupdict().get("b") else None
            if a is None:
                continue
            monthly = bool(_MONTHLY.search(window))
            vals = [v for v in (a, b) if v]
            if monthly:
                vals = [v * 12 for v in vals]
            vals = [v for v in vals if MIN_ANNUAL <= v <= MAX_ANNUAL]
            if not vals:
                continue
            out.append({"low": min(vals), "high": max(vals), "currency": cur,
                        "annualised_from_monthly": monthly})
        if out:
            break          # first pattern that matched is the most specific
    return out


def to_eur(value, currency):
    return value * FX.get(currency, 1.0)


def collect(postings, match_fn=None, market=None):
    """Gather salary observations across postings.

    match_fn(posting) -> bool lets the caller restrict to one career track.
    """
    obs = []
    for p in postings.values():
        if market and p.get("market") != market:
            continue
        if match_fn and not match_fn(p):
            continue
        desc = p.get("description")
        if not desc:
            continue
        default = MARKET_CCY.get(p.get("market"), "EUR")
        parsed = parse_salaries(desc, default)
        if not parsed:
            continue
        # ONE observation per posting. A job ad that repeats its range in three
        # places is one data point, not three - counting each occurrence
        # inflates n and lets a single big-tech range dominate a median.
        widest = max(parsed, key=lambda x: x["high"] - x["low"]) if len(parsed) > 1 else parsed[0]
        for s in [widest]:
            mid = (s["low"] + s["high"]) / 2
            obs.append({
                "eur": to_eur(mid, s["currency"]),
                "low_eur": to_eur(s["low"], s["currency"]),
                "high_eur": to_eur(s["high"], s["currency"]),
                "currency": s["currency"],
                "market": p.get("market"),
                "title": p.get("title"),
                "company": p.get("company"),
                "url": p.get("url"),
            })
    return obs


def summarise(obs, min_n=5):
    """Median and quartiles, or an explicit refusal when the sample is too thin."""
    if not obs:
        return {"available": False, "n": 0,
                "note": "No posting in this slice states a salary. DATA NOT VERIFIED — "
                        "no figure is shown rather than an invented one."}
    vals = sorted(o["eur"] for o in obs)
    n = len(vals)
    if n < min_n:
        return {"available": False, "n": n, "observations": vals,
                "note": "Only %d posting%s states a salary here — too few for a median. "
                        "The raw observations are shown instead: %s."
                        % (n, "" if n == 1 else "s",
                           ", ".join("EUR %s" % format(int(v), ",") for v in vals))}
    q = lambda p: vals[min(n - 1, int(n * p))]
    return {
        "available": True, "n": n,
        "median_eur": round(statistics.median(vals)),
        "p25_eur": round(q(0.25)),
        "p75_eur": round(q(0.75)),
        "min_eur": round(vals[0]),
        "max_eur": round(vals[-1]),
        "note": "Median of %d real postings that stated a figure. Non-EUR converted "
                "at assumed rates (GBP 1.16, USD 0.92) — the conversion is an "
                "assumption, the underlying figures are not." % n,
    }


def by_career(postings, careers_cfg, jobmarket_module, min_n=5):
    """Salary evidence per career track."""
    out = {}
    for c in careers_cfg["careers"]:
        obs = collect(postings, match_fn=lambda p, c=c: jobmarket_module.match_career(p, c))
        out[c["id"]] = {"name": c["name"], **summarise(obs, min_n),
                        "top": sorted(obs, key=lambda o: -o["eur"])[:4]}
    return out


def by_country(postings, min_n=5):
    """Salary evidence per market, regardless of role."""
    out = {}
    for m in set(p.get("market") for p in postings.values() if p.get("market")):
        obs = collect(postings, market=m)
        out[m] = summarise(obs, min_n)
    return out


def career_progression(median_eur):
    """SPEC §22 stages, anchored on a MEASURED median rather than a legal floor.

    Multipliers are assumptions about progression and are labelled as such —
    but the base is now real market data, which is the important change.
    """
    if not median_eur:
        return None
    return [
        {"stage": "Entry (0-2 yrs)", "eur": round(median_eur * 0.72), "basis": "ASSUMPTION: 0.72x the observed median"},
        {"stage": "3-5 yrs", "eur": round(median_eur), "basis": "the observed median itself"},
        {"stage": "7-10 yrs", "eur": round(median_eur * 1.38), "basis": "ASSUMPTION: 1.38x"},
        {"stage": "Senior leadership", "eur": round(median_eur * 1.95), "basis": "ASSUMPTION: 1.95x"},
    ]
