"""Job-market feedback loop — SPEC §31, §32, §33.

This module is what stops the engine from being a brochure aggregator. It reads
the real postings already collected by ../ai-governance-career/scan.py and
measures, per career track: how many openings exist, how often coding is
actually demanded, how often a master's is actually required, who is hiring,
where, and whether sponsorship is mentioned.

It measures ONLY what postings can support. Demand, coding rate, degree
requirement, sponsorship rate, geography and employers are MEASURED. Salary,
job security, AI resilience and career ceiling cannot be read off a posting
board, so they stay as seeded ESTIMATES and are labelled as such everywhere
they surface. Conflating the two would be exactly the kind of laundering that
SPEC §39 and §40 exist to prevent.
"""

import json
import os
import re
from collections import Counter

from . import db

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# Live store on the Mac, where scan.py keeps it fresh.
POSTINGS_LIVE = os.path.abspath(os.path.join(
    ROOT, "..", "ai-governance-career", "data", "postings.json"))
# Committed snapshot, so the engine still runs anywhere the sibling repo does
# not exist - a cloud sandbox, a clone on another machine, claude.ai/code.
POSTINGS_SNAPSHOT = os.path.join(ROOT, "data", "postings-snapshot.json")


def resolve_postings_path():
    """Prefer the live store; fall back to the committed snapshot."""
    if os.path.exists(POSTINGS_LIVE):
        return POSTINGS_LIVE, "live"
    if os.path.exists(POSTINGS_SNAPSHOT):
        return POSTINGS_SNAPSHOT, "snapshot"
    return POSTINGS_LIVE, "missing"


POSTINGS = resolve_postings_path()[0]

MARKET_TO_CODE = {
    "Ireland": "IE", "Netherlands": "NL", "United Kingdom": "GB",
    "Germany": "DE", "Luxembourg": "LU", "Belgium": "BE", "India": "IN",
}

MASTERS_PAT = re.compile(r"master'?s?\b|msc\b|m\.sc|postgraduate degree|mba\b", re.I)


def load_postings(path=POSTINGS):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def match_career(post, career):
    """Does this posting belong to this career track? Title carries most of
    the signal; description is corroboration. Context keywords (e.g. 'bank')
    are required only when the track is defined as sector-specific."""
    title = (post.get("title") or "").lower()
    desc = (post.get("description") or "").lower()
    hay = title + " \n " + desc

    kws = career.get("keywords") or []
    if not any(k in hay for k in kws):
        return False

    ctx = career.get("context_keywords") or []
    if ctx and not any(c in hay for c in ctx):
        return False

    # A title hit is a strong match; description-only is weak but counted.
    return True


def analyse_career(career, postings, min_measured):
    """Returns the §31 evidence block for one career track."""
    matched = [p for p in postings.values() if match_career(p, career)]
    n = len(matched)

    with_desc = [p for p in matched if p.get("description")]
    analysed = [p for p in matched if p.get("analysis")]

    coding_yes = 0
    coding_total = 0
    masters_required = 0
    degree_total = 0
    spons_pos = spons_neg = 0
    years = []
    certs = Counter()
    regs = Counter()
    companies = Counter()
    countries = Counter()
    seniority = Counter()

    for p in matched:
        countries[MARKET_TO_CODE.get(p.get("market"), p.get("market"))] += 1
        if p.get("company"):
            companies[p["company"]] += 1
        a = p.get("analysis") or {}
        if not a:
            continue
        if a.get("has_description"):
            coding_total += 1
            if (a.get("coding_signals") or 0) > 0:
                coding_yes += 1
            degs = a.get("degree") or []
            if degs:
                degree_total += 1
                if any(MASTERS_PAT.search(str(d)) for d in degs):
                    masters_required += 1
        s = a.get("sponsorship")
        if s == "positive":
            spons_pos += 1
        elif s == "negative":
            spons_neg += 1
        if a.get("years_required"):
            years.append(a["years_required"])
        for c in a.get("certs") or []:
            certs[c] += 1
        for r in a.get("regulations") or []:
            regs[r] += 1
        if a.get("seniority"):
            seniority[a["seniority"]] += 1

    def rate(num, den):
        return round(100.0 * num / den, 1) if den else None

    measured = n >= min_measured

    return {
        "career_id": career["id"],
        "career_name": career["name"],
        "posting_count": n,
        "with_description": len(with_desc),
        "analysed": len(analysed),
        "measured": measured,
        "min_for_measured": min_measured,
        "coding_required_pct": rate(coding_yes, coding_total),
        "coding_sample": coding_total,
        "masters_required_pct": rate(masters_required, degree_total),
        "masters_sample": degree_total,
        "sponsorship_positive": spons_pos,
        "sponsorship_negative": spons_neg,
        "median_years_required": (sorted(years)[len(years) // 2] if years else None),
        "top_certs": certs.most_common(6),
        "top_regulations": regs.most_common(6),
        "top_employers": companies.most_common(10),
        "country_distribution": countries.most_common(),
        "seniority_mix": seniority.most_common(),
    }


def demand_score(count, all_counts):
    """Convert a raw posting count into a 0-10 demand dimension, relative to
    the other tracks in this same scan. Relative, because absolute counts are
    an artefact of which queries scan.py happened to run."""
    if not all_counts or max(all_counts) == 0:
        return None
    top = max(all_counts)
    # sqrt compresses the long tail so one dominant track does not flatten the rest
    return round(min(10.0, 10.0 * (count / float(top)) ** 0.5), 1)


def run(conn, careers_cfg, run_id, path=None):
    """Measure every career track, write career_scores rows, return evidence."""
    if path is None:
        path, origin = resolve_postings_path()
    else:
        origin = "explicit"
    postings = load_postings(path)
    careers = careers_cfg["careers"]
    min_measured = careers_cfg.get("min_postings_for_measured", 12)

    blocks = [analyse_career(c, postings, min_measured) for c in careers]
    counts = [b["posting_count"] for b in blocks]

    by_id = {}
    for c, b in zip(careers, blocks):
        ds = demand_score(b["posting_count"], counts)
        overrides = {}
        if b["measured"] and ds is not None:
            overrides["job_demand"] = ds
        # Measured coding expectation replaces the seed when we have a sample.
        if b["coding_sample"] >= min_measured and b["coding_required_pct"] is not None:
            overrides["_measured_coding_pct"] = b["coding_required_pct"]
        b["overrides"] = overrides
        by_id[c["id"]] = b

    return {"postings_loaded": len(postings), "blocks": blocks, "by_id": by_id,
            "source": path, "source_origin": origin, "run_id": run_id}


def apply_overrides(career, evidence_block):
    """Return a copy of the career with measured dimensions substituted in,
    and a record of which dimensions are measured vs estimated (§40)."""
    c = json.loads(json.dumps(career))
    provenance = {k: "ESTIMATED" for k in c.get("dimensions", {})}
    for k, v in (evidence_block.get("overrides") or {}).items():
        if k.startswith("_"):
            continue
        c["dimensions"][k] = v
        provenance[k] = "MEASURED from %d real postings" % evidence_block["posting_count"]
    c["_provenance"] = provenance
    c["_evidence"] = evidence_block
    return c


# --------------------------------------------------------------------------
# §32 career arbitrage detector
# --------------------------------------------------------------------------

def arbitrage(careers_cfg, evidence_by_id, profile):
    """Rank the combinations where his existing CV is an unusual advantage.

    Rarity is a seeded editorial judgement. Demand and transferability are
    grounded in measured posting counts where available.
    """
    combos = careers_cfg.get("arbitrage_combinations", {}).get("combos", [])
    careers = {c["id"]: c for c in careers_cfg["careers"]}
    out = []
    for combo in combos:
        parts = [careers[i] for i in combo["components"] if i in careers]
        if not parts:
            continue
        ev = [evidence_by_id.get(i, {}) for i in combo["components"]]
        demand = sum(e.get("posting_count", 0) for e in ev)
        dims = [p.get("dimensions", {}) for p in parts]

        def avg(key):
            vals = [d.get(key) for d in dims if d.get(key) is not None]
            return sum(vals) / len(vals) if vals else 5.0

        score = (combo.get("rarity", 5) * 1.4
                 + combo.get("transferability", 5) * 1.4
                 + avg("salary_potential") * 1.2
                 + avg("ai_resilience") * 1.1
                 + avg("international_mobility") * 1.1
                 + min(10.0, demand / 12.0) * 1.3)
        maxs = (10 * 1.4 + 10 * 1.4 + 10 * 1.2 + 10 * 1.1 + 10 * 1.1 + 10 * 1.3)
        out.append({
            "id": combo["id"],
            "name": combo["name"],
            "score": round(100.0 * score / maxs, 1),
            "rarity": combo.get("rarity"),
            "transferability": combo.get("transferability"),
            "measured_postings": demand,
            "salary_potential": round(avg("salary_potential"), 1),
            "ai_resilience": round(avg("ai_resilience"), 1),
            "international_mobility": round(avg("international_mobility"), 1),
            "components": combo["components"],
        })
    out.sort(key=lambda x: -x["score"])
    return out


# --------------------------------------------------------------------------
# §33 challenge the hypothesis
# --------------------------------------------------------------------------

def challenge(careers_cfg, evidence_by_id, scored_careers):
    """Actively look for reasons the seed hypothesis is wrong.

    SPEC §33: the system's job is to maximise his outcome, not to confirm his
    assumptions. This returns warnings, not reassurance.
    """
    findings = []
    seed_primary = min(careers_cfg["careers"], key=lambda c: c.get("seed_rank", 99))
    ranked = sorted(scored_careers, key=lambda c: -c["career_score"])

    if ranked and ranked[0]["career_id"] != seed_primary["id"]:
        findings.append({
            "severity": "CHALLENGE",
            "headline": "Your seed #1 is not the top-scoring track this run",
            "detail": ("Seed #1 is '%s'. Highest scoring is '%s' (%.1f vs %.1f). "
                       "This is the §33 check firing - review it rather than "
                       "dismissing it."
                       % (seed_primary["name"], ranked[0]["career_name"],
                          ranked[0]["career_score"],
                          next((c["career_score"] for c in ranked
                                if c["career_id"] == seed_primary["id"]), 0.0))),
        })

    # Saturation proxy: lots of postings but high seniority skew means the
    # entry-level door is narrower than raw demand suggests.
    for cid, ev in evidence_by_id.items():
        if not ev.get("measured"):
            continue
        sm = dict(ev.get("seniority_mix") or [])
        total = sum(sm.values()) or 1
        exec_share = 100.0 * (sm.get("exec", 0) + sm.get("director", 0)) / total
        if exec_share >= 45:
            findings.append({
                "severity": "RISK",
                "headline": "%s is skewed to senior hiring" % ev["career_name"],
                "detail": ("%.0f%% of matched postings are director/exec level. "
                           "Demand exists, but not at the level he can enter at. "
                           "Raw posting counts overstate the opportunity here."
                           % exec_share),
            })

    # The coding constraint, measured rather than assumed.
    for cid, ev in evidence_by_id.items():
        if ev.get("coding_sample", 0) >= ev.get("min_for_measured", 12) \
                and (ev.get("coding_required_pct") or 0) >= 50:
            findings.append({
                "severity": "RISK",
                "headline": "%s demands coding more often than assumed" % ev["career_name"],
                "detail": ("%.0f%% of postings with a readable description show coding "
                           "signals (sample %d). The seed assumed this was a low-code "
                           "track. Treat programmes feeding only into it with caution."
                           % (ev["coding_required_pct"], ev["coding_sample"])),
            })

    # Is a master's actually required? The Jan 2027 decision input.
    agg_req = agg_total = 0
    for ev in evidence_by_id.values():
        if ev.get("masters_sample"):
            agg_req += ev["masters_required_pct"] * ev["masters_sample"] / 100.0
            agg_total += ev["masters_sample"]
    if agg_total >= 30:
        pct = 100.0 * agg_req / agg_total
        findings.append({
            "severity": "DECISION INPUT",
            "headline": "A master's is named in %.0f%% of postings that state a degree" % pct,
            "detail": ("Sample of %d postings. If this stays low, the master's is being "
                       "bought as an IMMIGRATION instrument (visa threshold + stay-back), "
                       "not as an employer requirement - which is a valid reason, but a "
                       "different one, and it should be judged on that basis."
                       % agg_total),
        })

    return findings
