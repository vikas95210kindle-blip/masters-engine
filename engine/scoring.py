"""Scoring engine — SPEC §11-§17, §47, §53.

Every score returned here carries a `breakdown` so that §19/§44 can show *why*
a programme ranks where it does. Nothing in this module invents a fact: where
an input is missing it degrades to a documented neutral and records that it
did, rather than guessing a number that would then look authoritative.
"""

import datetime
import re

from . import db
from . import eligibility

TODAY = datetime.date.today()


def _norm(components, weights):
    """Weighted mean of 0-10 components -> 0-100, ignoring absent components."""
    num = den = 0.0
    used = {}
    for key, w in weights.items():
        if key.startswith("_"):
            continue
        v = components.get(key)
        if v is None:
            continue
        num += float(v) * float(w)
        den += 10.0 * float(w)
        used[key] = v
    if den == 0:
        return 0.0, used
    return round(100.0 * num / den, 1), used


# --------------------------------------------------------------------------
# §11 career score
# --------------------------------------------------------------------------

def career_score(career, weights):
    dims = career.get("dimensions") or {}
    score, used = _norm(dims, weights["career_score"])
    return score, {"components": used, "confidence": career.get("confidence", "ESTIMATED")}


# --------------------------------------------------------------------------
# §53 money / purpose / balanced
# --------------------------------------------------------------------------

def money_purpose(career, weights, profile):
    dims = career.get("dimensions") or {}
    pdims = career.get("purpose_dimensions") or {}
    money, m_used = _norm(dims, weights["money_vs_purpose"]["money"])
    purpose, p_used = _norm(pdims, weights["money_vs_purpose"]["purpose"])
    bal = profile.get("preferences", {}).get("balance", {})
    mw = float(bal.get("money_weight", 0.7))
    pw = float(bal.get("purpose_weight", 0.3))
    total = mw + pw or 1.0
    balanced = round((money * mw + purpose * pw) / total, 1)
    return money, purpose, balanced, {"money_components": m_used,
                                      "purpose_components": p_used,
                                      "money_weight": mw, "purpose_weight": pw}


# --------------------------------------------------------------------------
# §13 country score
# --------------------------------------------------------------------------

def country_score(country, weights):
    scores = db.uj(country.get("scores"), {}) or {}
    score, used = _norm(scores, weights["country_score"])
    return score, {"components": used,
                   "confidence": country.get("scores_conf", "ESTIMATED")}


# --------------------------------------------------------------------------
# §30 university quality
# --------------------------------------------------------------------------

def university_quality(prog, uni):
    """0-100. Deliberately compressed: SPEC §30 says career fit beats ranking,
    so a top-10 university earns ~85 and an unranked-but-specialist one ~55,
    not 100 vs 10. Ranking must not be able to dominate the overall score."""
    breakdown = {}
    rank = None
    for src in (uni or {}).get("qs_rank"), (uni or {}).get("the_rank"), prog.get("ranking"):
        if src:
            try:
                rank = int(re.sub(r"[^0-9]", "", str(src)))
                break
            except (TypeError, ValueError):
                continue

    if rank is None:
        base = 55.0
        breakdown["ranking"] = "unranked or DATA NOT VERIFIED - neutral 55 applied"
    elif rank <= 25:
        base = 88.0
    elif rank <= 50:
        base = 82.0
    elif rank <= 100:
        base = 76.0
    elif rank <= 200:
        base = 70.0
    elif rank <= 400:
        base = 63.0
    else:
        base = 57.0
    if rank is not None:
        breakdown["ranking"] = "rank %s -> base %.0f" % (rank, base)

    # Programme-specific quality can move it either way (§30: a lower-ranked
    # university with the right programme should be able to win).
    bump = 0.0
    if prog.get("industry_links"):
        bump += 4
        breakdown["industry_links"] = "+4"
    if prog.get("internship"):
        bump += 4
        breakdown["internship"] = "+4"
    if prog.get("employer_links"):
        bump += 3
        breakdown["employer_links"] = "+3"
    if (prog.get("finserv_relevance") or 0) >= 7:
        bump += 4
        breakdown["financial_services_links"] = "+4"

    return min(100.0, round(base + bump, 1)), breakdown


# --------------------------------------------------------------------------
# §12 personal fit
# --------------------------------------------------------------------------

def personal_fit(prog, profile, elig, career, country, admission_points, weights):
    text = eligibility._programme_text(prog)
    strong = [s.lower() for s in profile.get("skills", {}).get("strong", [])]
    matched_skills = [s for s in strong if s in text]

    comp = {
        "academic_eligibility": 10.0 * elig["academic_score"],
        "work_experience_relevance": 10.0 * elig["work_exp_score"],
        "existing_skills": min(10.0, 2.0 * len(matched_skills)),
        "domain_advantage": float(career.get("banking_adjacency", 5)) if career else 5.0,
        "career_alignment": min(10.0, (
            (prog.get("governance_relevance") or 0) * 0.4
            + (prog.get("risk_relevance") or 0) * 0.3
            + (prog.get("ai_relevance") or 0) * 0.2
            + (prog.get("finserv_relevance") or 0) * 0.3)),
        "admission_probability": admission_points / 10.0,
        "non_coding_fit": max(0.0, 10.0 - 2.2 * elig["coding_band"]),
        "international_mobility": (db.uj(country.get("scores"), {}) or {}).get(
            "post_study_work", 5) if country else 5.0,
    }
    score, used = _norm(comp, weights["personal_fit"])
    return score, {"components": used, "matched_skills": matched_skills}


# --------------------------------------------------------------------------
# §14 ROI
# --------------------------------------------------------------------------

EMPLOYMENT_PROB = {"HIGH": 0.80, "MEDIUM-HIGH": 0.68, "MEDIUM": 0.55,
                   "LOW": 0.38, "VERY LOW": 0.20}


def expected_salary_eur(prog, country, career):
    """Return (value, basis, confidence). NEVER fabricates a market salary.

    Preference order:
      1. A verified median graduate salary on the programme record.
      2. The country's skilled-route salary threshold, used explicitly as a
         FLOOR PROXY — it is the legal minimum an employer must pay to sponsor
         him, which is a real sourced number, not a salary estimate.
      3. Nothing. Returns None and the ROI is reported as unavailable.
    """
    med = prog.get("median_salary")
    if med:
        try:
            val = float(re.sub(r"[^0-9.]", "", str(med).split("-")[0]))
            if val > 1000:
                return val, "programme-reported median graduate salary: %s" % med, "PROBABLY CORRECT"
        except (TypeError, ValueError):
            pass

    visa = db.uj((country or {}).get("visa"), {}) or {}
    thr = (visa.get("skilled_threshold_eur") or {}).get("value")
    if thr:
        return float(thr), (
            "FLOOR PROXY, not a salary estimate: the %s skilled-route salary "
            "threshold an employer must meet to sponsor him (%s)"
            % (country.get("name"), (visa.get("skilled_threshold_eur") or {}).get("condition", "")),
        ), "ESTIMATED"
    return None, "DATA NOT VERIFIED - no sourced salary figure available", "UNKNOWN"


def roi(prog, country, career, profile, admission_band, weights):
    """SPEC §14. Returns (score 0-100, ratio or None, assumptions dict)."""
    cfg = weights["roi"]
    a = {}

    tuition = prog.get("tuition_eur")
    living = prog.get("living_cost_eur")
    months = prog.get("duration_months") or 12
    years = months / 12.0

    if living is None and country:
        living = None
    a["duration_years"] = round(years, 2)
    a["tuition_eur"] = tuition if tuition is not None else "DATA NOT VERIFIED"
    a["living_cost_eur_total"] = (round(living * years) if living else "DATA NOT VERIFIED")
    opp = cfg["opportunity_cost_annual_eur"] * years
    a["opportunity_cost_eur"] = round(opp)
    a["opportunity_cost_source"] = cfg["opportunity_cost_source"]

    salary, basis, sal_conf = expected_salary_eur(prog, country, career)
    a["expected_salary_eur"] = salary if salary else "DATA NOT VERIFIED"
    a["expected_salary_basis"] = basis
    a["expected_salary_confidence"] = sal_conf

    if tuition is None or salary is None:
        a["result"] = ("ROI NOT CALCULABLE - missing %s. Reported as unavailable "
                       "rather than estimated." %
                       ("tuition" if tuition is None else "salary evidence"))
        return None, None, a

    cost = tuition + (living * years if living else 0.0) + opp
    a["total_cost_eur"] = round(cost)

    p_emp = EMPLOYMENT_PROB.get(admission_band, 0.5)
    a["employment_probability"] = p_emp
    a["employment_probability_basis"] = (
        "Derived from admission band as a stand-in for cohort strength. "
        "ASSUMPTION - not a programme-reported employment rate.")

    visa = db.uj((country or {}).get("visa"), {}) or {}
    psw = (visa.get("post_study_work_months") or {}).get("value")
    visa_adv = 1.0
    if psw is not None:
        visa_adv = 0.7 + min(psw, 36) / 36.0 * 0.6      # 0.7 .. 1.3
    a["visa_advantage"] = round(visa_adv, 2)
    a["visa_advantage_basis"] = "post-study work months = %s" % (psw if psw is not None else "unknown")

    dims = (career or {}).get("dimensions", {})
    growth = 0.8 + (dims.get("career_ceiling", 5) / 10.0) * 0.5
    mobility = 0.8 + (dims.get("international_mobility", 5) / 10.0) * 0.5
    a["career_growth_multiplier"] = round(growth, 2)
    a["international_mobility_multiplier"] = round(mobility, 2)

    horizon = cfg["horizon_years"]
    benefit = salary * p_emp * visa_adv * growth * mobility * horizon
    a["horizon_years"] = horizon
    a["gross_benefit_eur"] = round(benefit)

    ratio = benefit / cost if cost > 0 else None
    a["roi_ratio"] = round(ratio, 2) if ratio else None
    a["roi_formula"] = ("(salary x P(employment) x visa advantage x career growth "
                        "x mobility x %d years) / (tuition + living + opportunity cost)"
                        % horizon)

    # Map ratio to 0-100. 3x over 5 years is unremarkable; 8x is excellent.
    if ratio is None:
        return None, None, a
    score = max(0.0, min(100.0, (ratio - 1.0) / 7.0 * 100.0))
    return round(score, 1), round(ratio, 2), a


# --------------------------------------------------------------------------
# §24 deadlines
# --------------------------------------------------------------------------

def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def target_intake_year(profile):
    """The cycle he is actually applying for (§profile.preferences.earliest_intake)."""
    s = (profile or {}).get("preferences", {}).get("earliest_intake")
    try:
        return int(str(s).split("-")[0])
    except (TypeError, ValueError):
        return None


def deadline_state(prog, weights, today=None, profile=None):
    """Returns (bucket, days_remaining_or_None, status).

    A deadline that has passed is only CLOSED if it belongs to the cycle he is
    applying for. His profile targets a September 2027 intake, so a 2026
    deadline is a PAST CYCLE, not a lost opportunity - the same programme
    reopens on roughly the same date a year later. Reporting those as CLOSED
    would silently drop good programmes off the shortlist for no reason.
    """
    today = today or TODAY
    dtype = (prog.get("deadline_type") or "UNKNOWN").upper()
    d = parse_date(prog.get("application_deadline"))

    if dtype == "ROLLING":
        return "ROLLING", None, "ROLLING"
    if d is None:
        return "UNKNOWN", None, ("NOT YET OPEN" if dtype == "NOT_OPEN" else "UNKNOWN")

    days = (d - today).days

    if days < 0:
        target = target_intake_year(profile)
        if target and d.year < target:
            # Roll forward to the equivalent date in the target cycle and flag
            # it as PROJECTED - the real date must still be confirmed.
            try:
                projected = d.replace(year=target)
            except ValueError:                       # 29 Feb
                projected = d.replace(year=target, day=28)
            pdays = (projected - today).days
            return ("NEXT CYCLE (projected %s)" % projected.isoformat(),
                    pdays, "PAST CYCLE - REOPENS")
        return "CLOSED", days, "CLOSED"
    cfg = weights["deadline_urgency_days"]
    if days <= cfg["critical"]:
        b = "DEADLINE IN 7 DAYS"
    elif days <= cfg["urgent"]:
        b = "DEADLINE IN 14 DAYS"
    elif days <= cfg["soon"]:
        b = "DEADLINE IN 30 DAYS"
    elif days <= cfg["approaching"]:
        b = "DEADLINE IN 60 DAYS"
    elif days <= cfg["watch"]:
        b = "DEADLINE IN 90 DAYS"
    else:
        b = "BEYOND 90 DAYS"
    return b, days, "OPEN NOW"


def deadline_urgency_points(days):
    """0-100 urgency. A deadline 300 days out is not urgent; one in 5 days is."""
    if days is None:
        return 40.0
    if days < 0:
        return 0.0
    if days <= 7:
        return 100.0
    if days <= 14:
        return 90.0
    if days <= 30:
        return 78.0
    if days <= 60:
        return 62.0
    if days <= 90:
        return 50.0
    if days <= 180:
        return 35.0
    return 22.0


# --------------------------------------------------------------------------
# §16 overall score + penalties
# --------------------------------------------------------------------------

def apply_penalties(prog, elig, career, country, roi_ratio, tuition_eur, weights,
                    profile=None):
    """SPEC §16. Returns (total_penalty, list_of_applied)."""
    p = weights["penalties"]
    th = weights.get("penalty_thresholds", {})
    cost_trigger = th.get("extreme_cost_tuition_eur", 35000)
    roi_trigger = th.get("weak_roi_ratio", 4.0)
    align_trigger = th.get("poor_career_alignment_below", 10)
    applied = []
    total = 0.0

    if elig["coding_reject"]:
        total += p["hard_coding_violation"]
        applied.append({"rule": "hard_coding_violation", "points": p["hard_coding_violation"],
                        "reason": elig["coding_evidence"].get("reject_cause", "coding intensity too high")})

    if elig["academic_score"] <= 0.4 or elig["test_barriers"]:
        total += p["major_prerequisite_mismatch"]
        applied.append({"rule": "major_prerequisite_mismatch",
                        "points": p["major_prerequisite_mismatch"],
                        "reason": "; ".join(elig["academic_reasons"][:1] + elig["test_barriers"])})

    align = ((prog.get("governance_relevance") or 0) + (prog.get("risk_relevance") or 0)
             + (prog.get("ai_relevance") or 0) + (prog.get("finserv_relevance") or 0))
    if align < align_trigger:
        total += p["poor_career_alignment"]
        applied.append({"rule": "poor_career_alignment", "points": p["poor_career_alignment"],
                        "reason": "combined governance/risk/AI/finserv relevance is %d/40" % align})

    visa = db.uj((country or {}).get("visa"), {}) or {}
    psw = prog.get("post_study_work_months")
    needs_visa = (profile or {}).get("identity", {}).get("requires_student_visa", True)
    if needs_visa and psw == 0:
        # An online or part-time-executive programme confers no student visa and
        # no stay-back. Whatever its content, it cannot deliver the stated
        # objective of an internationally mobile career, so it takes the same
        # penalty as a RED-flagged destination. It remains a valid Track A
        # credential - that is what the report text is for, not the ranking.
        total += p["poor_visa_situation"]
        applied.append({"rule": "poor_visa_situation", "points": p["poor_visa_situation"],
                        "reason": "delivery mode confers NO student visa and NO post-study "
                                  "work route - zero immigration value (%s)"
                                  % (prog.get("study_mode") or "mode unstated")})
    elif visa.get("flag") == "RED":
        total += p["poor_visa_situation"]
        applied.append({"rule": "poor_visa_situation", "points": p["poor_visa_situation"],
                        "reason": visa.get("why_flag", "visa route flagged RED")})

    if tuition_eur and tuition_eur > cost_trigger \
            and (roi_ratio is not None and roi_ratio < roi_trigger):
        total += p["extreme_cost_weak_roi"]
        applied.append({"rule": "extreme_cost_weak_roi", "points": p["extreme_cost_weak_roi"],
                        "reason": "tuition EUR %.0f exceeds the EUR %.0f 'expensive' trigger "
                                  "while the 5-year gross ROI ratio is only %.2f (weak below %.1f)"
                                  % (tuition_eur, cost_trigger, roi_ratio, roi_trigger)})

    return total, applied


RECOMMENDATIONS = [
    ("APPLY NOW", "\U0001F7E2"),
    ("STRONG APPLY", "\U0001F7E2"),
    ("CONSIDER", "\U0001F7E1"),
    ("BACKUP", "\U0001F7E0"),
    ("DO NOT APPLY", "\U0001F534"),
    ("REJECT - CODING", "⛔"),
    ("REJECT - ELIGIBILITY", "⛔"),
]


def recommend(overall, elig, admission_band, personal_fit_score):
    """SPEC §17. Exactly one band per programme."""
    if elig["coding_reject"]:
        return "REJECT - CODING", "⛔"
    if elig["hard_blocks"]:
        return "REJECT - ELIGIBILITY", "⛔"

    if overall >= 72 and admission_band in ("HIGH", "MEDIUM-HIGH") and personal_fit_score >= 65:
        return "APPLY NOW", "\U0001F7E2"
    if overall >= 68 and admission_band in ("MEDIUM", "MEDIUM-HIGH", "HIGH"):
        return "STRONG APPLY", "\U0001F7E2"
    if overall >= 55:
        return "CONSIDER", "\U0001F7E1"
    if overall >= 42 and admission_band in ("HIGH", "MEDIUM-HIGH"):
        return "BACKUP", "\U0001F7E0"
    return "DO NOT APPLY", "\U0001F534"


def score_programme(prog, profile, career, country, uni, weights, today=None):
    """Full pipeline for one programme. Returns a dict ready for the DB."""
    today = today or TODAY
    elig = eligibility.evaluate(prog, profile)
    adm_band, adm_reason = eligibility.admission_probability(prog, profile, elig)
    adm_points = weights["admission_probability_points"][adm_band]

    cscore, cbreak = career_score(career, weights) if career else (50.0, {})
    ctry_score, ctry_break = country_score(country, weights) if country else (50.0, {})
    fit, fit_break = personal_fit(prog, profile, elig, career, country, adm_points, weights)
    uq, uq_break = university_quality(prog, uni)
    roi_score, roi_ratio, roi_assumptions = roi(
        prog, country, career, profile, adm_band, weights)
    money, purpose, balanced, mp_break = money_purpose(career, weights, profile) if career else (50.0, 50.0, 50.0, {})

    dims = (career or {}).get("dimensions", {})
    comps = {
        "career_value": cscore,
        "personal_fit": fit,
        "admission_probability": adm_points,
        "salary_potential": dims.get("salary_potential", 5) * 10.0,
        "job_security": dims.get("job_security", 5) * 10.0,
        "ai_resilience": dims.get("ai_resilience", 5) * 10.0,
        "country_immigration": ctry_score,
        "roi": roi_score if roi_score is not None else 50.0,
        "university_quality": uq,
    }
    if roi_score is None:
        comps["_roi_note"] = "ROI unavailable; neutral 50 used so a missing figure " \
                             "neither rewards nor punishes the programme."

    w = weights["overall"]
    base = sum(comps[k] * w[k] for k in w if not k.startswith("_"))
    penalty, applied = apply_penalties(
        prog, elig, career, country, roi_ratio, prog.get("tuition_eur"), weights,
        profile)
    overall = max(0.0, min(100.0, base + penalty))

    rec, emoji = recommend(overall, elig, adm_band, fit)

    bucket, days, status = deadline_state(prog, weights, today, profile)
    pw = weights["application_priority"]
    priority = (pw["programme_quality"] * uq + pw["personal_fit"] * fit
                + pw["admission_probability"] * adm_points
                + pw["career_value"] * cscore
                + pw["deadline_urgency"] * deadline_urgency_points(days))
    if elig["hard_blocks"]:
        priority = 0.0

    return {
        "overall": round(overall, 1),
        "base_before_penalties": round(base, 1),
        "career_value": cscore,
        "personal_fit": fit,
        "admission_band": adm_band,
        "admission_points": adm_points,
        "admission_reason": adm_reason,
        "salary_potential": comps["salary_potential"],
        "job_security": comps["job_security"],
        "ai_resilience": comps["ai_resilience"],
        "country_score": ctry_score,
        "roi_score": roi_score,
        "roi_ratio": roi_ratio,
        "roi_assumptions": roi_assumptions,
        "university_quality": uq,
        "money_score": money,
        "purpose_score": purpose,
        "balanced_score": balanced,
        "priority_score": round(priority, 1),
        "penalties": applied,
        "penalty_total": penalty,
        "recommendation": rec,
        "recommendation_emoji": emoji,
        "deadline_bucket": bucket,
        "deadline_days": days,
        "deadline_status": status,
        "eligibility": elig,
        "breakdown": {
            "overall_components": comps,
            "overall_weights": w,
            "career": cbreak,
            "country": ctry_break,
            "personal_fit": fit_break,
            "university": uq_break,
            "money_purpose": mp_break,
        },
    }
