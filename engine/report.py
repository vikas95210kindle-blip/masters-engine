"""Explanation and reporting — §20, §21, §22, §27, §34, §35, §49, §54.

Everything user-facing is generated from the scored record, never hand-written
per programme, so the text cannot drift out of sync with the numbers.
"""

import datetime

from . import db
from . import scoring

TODAY = datetime.date.today()


# --------------------------------------------------------------------------
# §20 "why this is for you"
# --------------------------------------------------------------------------

def why_for_you(prog, profile, scored, career):
    """Dynamically connect this programme to his actual CV."""
    exp = (profile.get("experience") or [{}])[0]
    years = exp.get("years", 10)
    bits = []

    matched = scored["breakdown"]["personal_fit"].get("matched_skills") or []
    domain = scored["eligibility"]["work_exp_detail"].get("domain_terms_matched") or []

    lead = ("You already have roughly %d years of banking experience covering "
            "KYC/AML, payments, compliance and process digitisation." % years)
    bits.append(lead)

    if domain:
        bits.append("This programme's own material uses the same vocabulary you "
                    "work in (%s), so your experience reads as directly relevant "
                    "rather than as a career detour." % ", ".join(sorted(set(domain))[:5]))

    band = scored["eligibility"]["coding_band"]
    if band <= 2:
        bits.append("It adds governance and risk expertise at coding intensity %d/5 "
                    "(%s), so it does not require you to become a programmer."
                    % (band, scoring.eligibility.CODING_BANDS[band]))
    else:
        bits.append("WARNING: coding intensity is %d/5 (%s), which sits at the edge "
                    "of your stated constraint."
                    % (band, scoring.eligibility.CODING_BANDS[band]))

    if career:
        bits.append("It feeds the '%s' track, where your banking background scores "
                    "%d/10 on domain adjacency." % (career["name"],
                                                     career.get("banking_adjacency", 5)))

    req = (prog.get("work_exp_requirement") or "").lower()
    if req in ("mandatory", "preferred"):
        bits.append("Work experience is %s here, which turns your 10 years from a "
                    "gap-explaining problem into your strongest admission asset." % req)

    psw = prog.get("post_study_work_months")
    if psw:
        bits.append("It carries a %d-month post-study work route, which is the "
                    "actual mechanism by which this becomes a European job rather "
                    "than a European qualification." % psw)
    elif prog.get("study_mode", "").startswith(("online", "part-time")):
        bits.append("NOTE: delivery mode means this carries NO post-study work route. "
                    "It builds the credential but does not move you to Europe.")

    bits.append("The combination that results — %d years of regulated banking plus a "
                "governance qualification — is rare. Most people in AI governance have "
                "one or the other." % years)
    return " ".join(bits)


# --------------------------------------------------------------------------
# §21 career outcome engine
# --------------------------------------------------------------------------

PROGRESSION = {
    "0-2": "entry / first European or pivot role",
    "3-5": "established specialist, managing a domain",
    "5-10": "senior manager to head-of-function",
}


def career_outcomes(prog, career, evidence):
    """What jobs can he realistically target, and when."""
    targets = db.uj(prog.get("target_careers"), []) or []
    out = {"immediate_titles": [], "0-2": [], "3-5": [], "5-10": [], "evidence": {}}

    grad = prog.get("grad_outcomes")
    if grad:
        out["immediate_titles"] = [t.strip() for t in grad.split(",")[:8] if t.strip()]

    if career:
        name = career["name"]
        out["0-2"] = ["%s — analyst / specialist level" % name.split(" - ")[0],
                      "Technology Risk Analyst", "Compliance Officer (technology)"]
        out["3-5"] = ["%s — manager level" % name.split(" - ")[0],
                      "Senior Technology Risk Manager", "Model Governance Lead"]
        out["5-10"] = ["Head of AI Governance", "Technology Risk Director",
                       "Director, Financial Crime & AI", "GRC leadership"]

    for cid in targets:
        ev = evidence.get(cid)
        if ev:
            out["evidence"][cid] = {
                "postings": ev["posting_count"],
                "coding_required_pct": ev["coding_required_pct"],
                "masters_required_pct": ev["masters_required_pct"],
                "top_employers": ev["top_employers"][:5],
            }
    return out


# --------------------------------------------------------------------------
# §27 CV gap analysis
# --------------------------------------------------------------------------

GAP_LIBRARY = [
    {"gap": "EU AI Act (Annex III high-risk classification, Article 50 transparency)",
     "importance": "CRITICAL", "fix": "IAPP AIGP certification, or the free EU AI Act "
     "explorer plus a written case study on KYC as a high-risk use case",
     "time": "2-4 months"},
    {"gap": "DORA / ICT operational resilience",
     "importance": "HIGH", "fix": "Restate your payments-digitisation work in DORA "
     "vocabulary: ICT risk, third-party dependency, incident reporting",
     "time": "3-4 weeks, mostly writing"},
    {"gap": "NIS2", "importance": "MEDIUM",
     "fix": "Read the directive and one national transposition", "time": "2 weeks"},
    {"gap": "Recognised AI-risk framework (NIST AI RMF, ISO/IEC 42001)",
     "importance": "HIGH", "fix": "ISO 42001 foundation course, or NIST AI RMF "
     "self-study plus a mapping exercise against a Union Bank process",
     "time": "1-2 months"},
    {"gap": "Formal governance credential",
     "importance": "HIGH", "fix": "IAPP AIGP (no prerequisites). CIPP/E is the "
     "cheaper adjacent option and is well recognised in the EU",
     "time": "3-6 months"},
    {"gap": "Demonstrable AI-governance artefact",
     "importance": "CRITICAL", "fix": "Write 4 case studies mapping existing Union "
     "Bank work to AI-risk concepts. This is the single highest-leverage item — "
     "it converts 'banking person interested in AI' into 'AI governance person "
     "with banking depth'", "time": "6-8 weeks"},
    {"gap": "European labour-market presence / network",
     "importance": "CRITICAL", "fix": "This is precisely what an on-campus master's "
     "buys. It cannot be fixed remotely, which is the core argument for Track B",
     "time": "the duration of the degree"},
]


def gap_analysis(prog, profile, career):
    """§27. What he has, what he lacks, how important, how to fix."""
    have = []
    exp = (profile.get("experience") or [{}])[0]
    have.append("~%d years banking operations in a regulated environment" % exp.get("years", 10))
    have.extend(profile.get("skills", {}).get("strong", [])[:8])

    text = scoring.eligibility._programme_text(prog)
    gaps = []
    for g in GAP_LIBRARY:
        key = g["gap"].split("(")[0].strip().lower()
        covered = any(tok in text for tok in key.split("/")[0].split()[:2] if len(tok) > 4)
        entry = dict(g)
        entry["covered_by_programme"] = covered
        if covered:
            entry["note"] = "This programme addresses it directly."
        gaps.append(entry)

    return {"have": have, "gaps": gaps,
            "critical_count": sum(1 for g in gaps if g["importance"] == "CRITICAL"
                                  and not g["covered_by_programme"])}


# --------------------------------------------------------------------------
# §49 should I apply
# --------------------------------------------------------------------------

def should_i_apply(scored, prog):
    rec = scored["recommendation"]
    if rec.startswith("REJECT"):
        verdict = "NO"
    elif rec in ("APPLY NOW", "STRONG APPLY"):
        verdict = "YES — APPLY"
    elif rec in ("CONSIDER", "BACKUP"):
        verdict = "MAYBE"
    else:
        verdict = "NO"

    bullets = []
    bullets.append("Overall %.1f/100, personal fit %.1f/100, admission probability %s."
                   % (scored["overall"], scored["personal_fit"], scored["admission_band"]))
    bullets.append("Coding intensity %d/5 — %s."
                   % (scored["eligibility"]["coding_band"],
                      "within your constraint" if scored["eligibility"]["coding_band"] <= 3
                      else "VIOLATES your constraint"))
    bullets.append("Tuition %s; ROI %s."
                   % (_fmt_money(prog.get("tuition_eur")),
                      ("%.2fx over 5 years" % scored["roi_ratio"]) if scored["roi_ratio"]
                      else "not calculable — missing verified inputs"))
    psw = prog.get("post_study_work_months")
    bullets.append("Post-study work: %s."
                   % ("%d months" % psw if psw else "NONE — no immigration value"))
    if scored["penalties"]:
        bullets.append("Penalties applied: %s."
                       % "; ".join("%s (%+d)" % (p["rule"], p["points"])
                                   for p in scored["penalties"]))
    else:
        bullets.append("No penalties applied.")
    return verdict, bullets[:5]


# --------------------------------------------------------------------------
# §22 salary projection
# --------------------------------------------------------------------------

INR_PER_EUR = 100.0  # ASSUMPTION, stated wherever used


def salary_projection(country, career, scored):
    """§22. Refuses to invent numbers. Returns rows with an explicit source."""
    visa = db.uj((country or {}).get("visa"), {}) or {}
    thr = (visa.get("skilled_threshold_eur") or {}).get("value")
    rows = []
    if not thr:
        return {"available": False,
                "note": "DATA NOT VERIFIED — no sourced salary anchor for %s. "
                        "No projection is shown rather than an invented one."
                        % (country or {}).get("name", "this country"),
                "rows": []}

    src = (visa.get("skilled_threshold_eur") or {})
    note = ("ANCHOR IS A LEGAL THRESHOLD, NOT A MARKET SALARY. The only sourced "
            "figure available is the %s skilled-route salary threshold (EUR %s, "
            "condition: %s). Multipliers below are ASSUMPTIONS about career "
            "progression, not observed data. Source note: %s"
            % ((country or {}).get("name"), thr, src.get("condition", "n/a"),
               src.get("source_type", "unstated")))

    for label, mult in (("Entry (0-2 yrs)", 1.0), ("3-5 yrs", 1.30),
                        ("7-10 yrs", 1.70), ("Senior leadership ceiling", 2.40)):
        eur = thr * mult
        rows.append({"stage": label, "eur": round(eur), "multiplier": mult,
                     "inr_equivalent": round(eur * INR_PER_EUR),
                     "confidence": "ESTIMATED"})
    return {"available": True, "note": note, "rows": rows,
            "inr_assumption": "INR conversion uses a flat %.0f INR/EUR ASSUMPTION."
                              % INR_PER_EUR}


# --------------------------------------------------------------------------
# §34 daily report
# --------------------------------------------------------------------------

def _fmt_money(v):
    return "EUR %s" % format(int(v), ",") if v else "DATA NOT VERIFIED"


def _fmt_deadline(s):
    if not s:
        return "—"
    return "%s (%s)" % (s["deadline_status"],
                        "%d days" % s["deadline_days"] if s["deadline_days"] is not None
                        else s["deadline_bucket"])


def daily_report(ctx):
    """§34. Returns markdown."""
    ranked = ctx["ranked"]
    L = []
    A = L.append

    A("# GLOBAL MASTER'S INTELLIGENCE REPORT")
    A("")
    A("**%s** · run `%s` · %d programmes scored · %d real job postings analysed"
      % (TODAY.isoformat(), ctx["run_id"], len(ranked), ctx["jobmarket"]["postings_loaded"]))
    A("")
    A("> Scores are computed from the profile, the verified programme records and "
      "measured job-market evidence. Fields marked DATA NOT VERIFIED were not "
      "found on an official page and were **not** estimated in their place.")
    A("")

    # 1. Top 10
    A("## 1. 🔥 TOP 10 PROGRAMMES TO APPLY TO")
    A("")
    A("| # | Programme | University | Rank | Country | Career | Overall | Fit | Admission | Tuition | Coding | Visa | Deadline | Recommendation |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(ranked[:10], 1):
        p, s = r["programme"], r["scored"]
        A("| %d | %s | %s | %s | %s | %s | **%.1f** | %.1f | %s | %s | %d/5 | %s | %s | %s %s |"
          % (i, p["name"][:44], (r.get("university") or {}).get("name", "—")[:26],
             ("#%d" % s["university_rank"]) if s.get("university_rank") else "unranked",
             p["country_code"], (r.get("career") or {}).get("name", "—").split(" - ")[0][:24],
             s["overall"], s["personal_fit"], s["admission_band"],
             _fmt_money(p.get("tuition_eur")), s["eligibility"]["coding_band"],
             (db.uj((r.get("country") or {}).get("visa"), {}) or {}).get("flag", "—"),
             _fmt_deadline(s), s["recommendation_emoji"], s["recommendation"]))
    A("")

    # Detailed top 3
    A("### Detailed reasoning — top 3")
    A("")
    for i, r in enumerate(ranked[:3], 1):
        p, s = r["programme"], r["scored"]
        A("#### %d. %s — %s" % (i, p["name"], (r.get("university") or {}).get("name", "")))
        A("")
        A("- **Overall %.1f** (career value %.1f · personal fit %.1f · admission %s · "
          "country %.1f · university %.1f)"
          % (s["overall"], s["career_value"], s["personal_fit"], s["admission_band"],
             s["country_score"], s["university_quality"]))
        A("- **Money score %.1f / Purpose score %.1f / Balanced %.1f** (§53)"
          % (s["money_score"], s["purpose_score"], s["balanced_score"]))
        A("- **Why you:** %s" % r["why"])
        A("- **Admission reasoning:** %s" % s["admission_reason"])
        if s["penalties"]:
            A("- **Penalties:** %s" % "; ".join("%s %+d — %s" % (x["rule"], x["points"], x["reason"])
                                                for x in s["penalties"]))
        A("- **Risks:** %s" % (p.get("notes") or "none recorded"))
        A("- **Source:** %s (verified %s)" % (p.get("official_url"), p.get("last_verified")))
        A("")

    # 2. New
    A("## 2. 🆕 NEW PROGRAMMES DISCOVERED")
    A("")
    if ctx["new_programmes"]:
        for n in ctx["new_programmes"]:
            A("- %s" % n)
    else:
        A("_None this run — the corpus is unchanged since the last load._")
    A("")

    # 3. Ranking changes
    A("## 3. 📈 RANKING CHANGES")
    A("")
    if ctx["score_changes"]:
        for c in ctx["score_changes"]:
            A("- **%s** — %.1f → %.1f (%+.1f)" % (c["name"], c["old"], c["new"],
                                                  c["new"] - c["old"]))
    else:
        A("_No previous run to compare against. Baseline established today._")
    A("")

    # 4. Deadlines
    A("## 4. ⏰ DEADLINES")
    A("")
    buckets = {}
    for r in ranked:
        b = r["scored"]["deadline_bucket"]
        buckets.setdefault(b, []).append(r)
    order = ["DEADLINE IN 7 DAYS", "DEADLINE IN 14 DAYS", "DEADLINE IN 30 DAYS",
             "DEADLINE IN 60 DAYS", "DEADLINE IN 90 DAYS", "BEYOND 90 DAYS",
             "ROLLING", "UNKNOWN", "CLOSED"]
    order += [b for b in buckets if b not in order]
    for b in order:
        if b not in buckets:
            continue
        A("**%s**" % b)
        for r in buckets[b][:8]:
            A("- %s — %s (%s)" % (r["programme"]["name"],
                                  r["programme"].get("application_deadline") or "no date on record",
                                  r["scored"]["recommendation"]))
        A("")

    # 5. Scholarships
    A("## 5. 💰 SCHOLARSHIPS")
    A("")
    found = [r for r in ranked if r["programme"].get("scholarship_available") == 1]
    if found:
        for r in found:
            A("- **%s** — %s" % (r["programme"]["name"], r["programme"].get("notes", "")[:220]))
    else:
        A("_No scholarship data verified in the current corpus._")
    A("")

    # 6. Country
    A("## 6. 🌍 COUNTRIES")
    A("")
    A("| Country | Score | Visa flag | Post-study work | Note |")
    A("|---|---|---|---|---|")
    for c in ctx["countries_ranked"][:10]:
        visa = db.uj(c.get("visa"), {}) or {}
        psw = (visa.get("post_study_work_months") or {}).get("value")
        A("| %s | %.1f | %s | %s | %s |"
          % (c["name"], c["country_score"], visa.get("flag", "—"),
             "%d mo" % psw if psw is not None else "DATA NOT VERIFIED",
             (visa.get("why_flag") or "")[:90]))
    A("")

    # 7. Job market
    A("## 7. 💼 JOB MARKET (measured, §31)")
    A("")
    A("| Career | Postings | Coding demanded | Master's demanded | Top employers |")
    A("|---|---|---|---|---|")
    for b in sorted(ctx["jobmarket"]["blocks"], key=lambda x: -x["posting_count"])[:12]:
        A("| %s | %d | %s | %s | %s |"
          % (b["career_name"][:38], b["posting_count"],
             "%.0f%%" % b["coding_required_pct"] if b["coding_required_pct"] is not None else "—",
             "%.0f%%" % b["masters_required_pct"] if b["masters_required_pct"] is not None else "—",
             ", ".join(e[0] for e in b["top_employers"][:3])[:44]))
    A("")

    # 8. Risks / challenges
    A("## 8. 🚨 RISKS AND CHALLENGES TO YOUR ASSUMPTIONS (§33)")
    A("")
    for f in ctx["challenges"]:
        A("**%s — %s**" % (f["severity"], f["headline"]))
        A("")
        A(f["detail"])
        A("")

    # Arbitrage
    A("## 9. 🎲 CAREER ARBITRAGE (§32)")
    A("")
    A("| Combination | Score | Rarity | Transferability | Measured postings |")
    A("|---|---|---|---|---|")
    for a in ctx["arbitrage"][:8]:
        A("| %s | %.1f | %s/10 | %s/10 | %d |" % (a["name"], a["score"], a["rarity"],
                                                  a["transferability"], a["measured_postings"]))
    A("")

    # 10. Today's actions
    A("## 10. 🎯 TODAY'S THREE ACTIONS")
    A("")
    for i, act in enumerate(ctx["actions"], 1):
        A("%d. %s" % (i, act))
    A("")

    # §54 final decision engine
    A("---")
    A("")
    A("## FINAL DECISION ENGINE (§54)")
    A("")
    A("### If you could apply to only 5 programmes today")
    A("")
    for i, r in enumerate(ctx["top5"], 1):
        p, s = r["programme"], r["scored"]
        A("**%d. %s — %s**" % (i, p["name"], (r.get("university") or {}).get("name", "")))
        A("")
        A("1. *Why:* %s" % r["why"][:400])
        A("2. *Expected career:* %s" % (r.get("career") or {}).get("name", "—"))
        A("3. *Admission probability:* %s — %s" % (s["admission_band"], s["admission_reason"][:180]))
        A("4. *Cost:* %s tuition" % _fmt_money(p.get("tuition_eur")))
        A("5. *Deadline:* %s" % (p.get("application_deadline") or s["deadline_bucket"]))
        A("6. *Biggest risk:* %s" % (p.get("notes") or "none recorded")[:300])
        A("")

    A("### If you could choose only 3 countries")
    A("")
    for i, c in enumerate(ctx["countries_ranked"][:3], 1):
        visa = db.uj(c.get("visa"), {}) or {}
        A("%d. **%s** (%.1f) — %s" % (i, c["name"], c["country_score"],
                                      visa.get("why_flag", "")))
    A("")

    A("### If you could choose only one career")
    A("")
    top_career = ctx["careers_ranked"][0]
    A("**%s** — career score %.1f." % (top_career["career_name"], top_career["career_score"]))
    A("")
    A(top_career.get("rationale", ""))
    A("")
    ev = ctx["jobmarket"]["by_id"].get(top_career["career_id"], {})
    if ev:
        A("Measured evidence: %d matched postings; coding demanded in %s of those with "
          "a readable description; a master's named in %s."
          % (ev.get("posting_count", 0),
             "%.0f%%" % ev["coding_required_pct"] if ev.get("coding_required_pct") is not None else "n/a",
             "%.0f%%" % ev["masters_required_pct"] if ev.get("masters_required_pct") is not None else "n/a"))
    A("")

    A("---")
    A("")
    A("### Data honesty note")
    A("")
    A("- Programme facts come from official university pages, checked on the dates shown.")
    A("- Country ordinal sub-scores are **editorial judgements**, labelled ESTIMATED.")
    A("- Visa thresholds carried over from prior research are labelled and were **not** "
      "re-verified in this run. Verify before acting on any of them.")
    A("- Salary projections are anchored on legal salary thresholds, not market data, "
      "and say so.")
    A("- Job-market percentages are measured from %d real postings collected by "
      "`../ai-governance-career/scan.py`." % ctx["jobmarket"]["postings_loaded"])
    return "\n".join(L)


# --------------------------------------------------------------------------
# §35 weekly strategic report
# --------------------------------------------------------------------------

def weekly_report(ctx):
    L = []
    A = L.append
    A("# WHERE SHOULD I BET MY NEXT 3 YEARS?")
    A("")
    A("**%s** · weekly strategic review · run `%s`" % (TODAY.isoformat(), ctx["run_id"]))
    A("")
    A("| Career | Score | Measured postings | Coding demanded | Master's demanded | Median yrs asked | AI resilience | Mobility |")
    A("|---|---|---|---|---|---|---|---|")
    for c in ctx["careers_ranked"]:
        ev = ctx["jobmarket"]["by_id"].get(c["career_id"], {})
        dims = c.get("dimensions", {})
        A("| %s | %.1f | %d | %s | %s | %s | %s/10 | %s/10 |"
          % (c["career_name"][:40], c["career_score"], ev.get("posting_count", 0),
             "%.0f%%" % ev["coding_required_pct"] if ev.get("coding_required_pct") is not None else "—",
             "%.0f%%" % ev["masters_required_pct"] if ev.get("masters_required_pct") is not None else "—",
             ev.get("median_years_required") or "—",
             dims.get("ai_resilience", "—"), dims.get("international_mobility", "—")))
    A("")

    ranked = ctx["careers_ranked"]
    A("## The bets")
    A("")
    A("**PRIMARY BET — %s** (%.1f)" % (ranked[0]["career_name"], ranked[0]["career_score"]))
    A("")
    A(ranked[0].get("rationale", ""))
    A("")
    A("**SECONDARY BET — %s** (%.1f)" % (ranked[1]["career_name"], ranked[1]["career_score"]))
    A("")
    A(ranked[1].get("rationale", ""))
    A("")
    A("**BACKUP BET — %s** (%.1f)" % (ranked[2]["career_name"], ranked[2]["career_score"]))
    A("")
    A(ranked[2].get("rationale", ""))
    A("")
    A("## Challenges to the current theory")
    A("")
    for f in ctx["challenges"]:
        A("- **%s** — %s: %s" % (f["severity"], f["headline"], f["detail"]))
    A("")
    return "\n".join(L)
