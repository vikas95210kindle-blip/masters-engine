"""Eligibility (§9), coding filter (§10) and admission probability (§15).

The coding filter is the most consequential module here: it is the one that
enforces the applicant's single non-negotiable constraint. It is deliberately
EVIDENCE-DRIVEN rather than title-driven, because SPEC §57 forbids assuming a
programme is non-coding from its name alone. Every score carries the list of
strings that produced it, so a wrong call can be traced to its trigger.
"""

import re

from . import db

# --------------------------------------------------------------------------
# §10 coding-intensity signals
# --------------------------------------------------------------------------
# Tier weights are additive; the final 0-5 band is derived from the total.
# Patterns are matched against name + department + academic_prereq +
# curriculum + graduate outcomes, all lowercased.

HARD_CODE = [
    r"\bprogramming\b", r"\bpython\b", r"\bjava\b", r"\bc\+\+\b", r"\bscala\b",
    r"\balgorithms? and data structures?\b", r"\bsoftware (?:engineering|development|design)\b",
    r"\bcompilers?\b", r"\boperating systems\b", r"\bdata engineering\b",
    r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural networks?\b",
    r"\bcomputer vision\b", r"\bnatural language processing\b",
    r"\bstatistical (?:modelling|modeling|inference)\b", r"\beconometrics\b",
    r"\bstochastic\b", r"\blinear algebra\b", r"\bcalculus\b",
    r"\bdevops\b", r"\bcloud (?:engineering|architecture)\b",
    r"\bquantitative (?:finance|methods|modelling|modeling)\b",
    r"\bdata science\b", r"\bdata mining\b",
]

SOFT_CODE = [
    r"\bsql\b", r"\br programming\b", r"\bdata analytics\b", r"\bdata analysis\b",
    r"\bstatistics\b", r"\bmodel validation\b", r"\bpenetration testing\b",
    r"\bcryptography\b", r"\bnetwork security\b", r"\bsecure coding\b",
    r"\bscripting\b", r"\bdatabases?\b",
]

# Presence of these REDUCES the coding reading: they signal that technical
# vocabulary in the page is about oversight rather than implementation.
GOVERNANCE_CONTEXT = [
    r"\bgovernance\b", r"\bpolicy\b", r"\bregulation\b", r"\bcompliance\b",
    r"\baudit\b", r"\bassurance\b", r"\bethics\b", r"\brisk management\b",
    r"\blaw\b", r"\bmanagement\b", r"\boversight\b", r"\baccountability\b",
    r"\bstrategy\b", r"\bstewardship\b",
]

# Language that explicitly frames a technical module as optional or introductory.
SOFTENERS = [
    r"\bno (?:prior )?(?:programming|coding) (?:experience|knowledge|background)"
    r" (?:is )?(?:required|necessary|needed)\b",
    r"\bnon-technical\b", r"\bfor non-programmers\b", r"\bintroduction to\b",
    r"\bconceptual\b", r"\bwithout (?:writing )?code\b", r"\boptional module\b",
    r"\belective\b", r"\bawareness\b", r"\bliteracy\b",
]

# Graduate-outcome titles that mean the programme's centre of gravity is
# engineering, whatever the brochure says (§2, §10).
ENGINEERING_OUTCOMES = [
    r"\bsoftware engineer\b", r"\bdata scientist\b", r"\bml engineer\b",
    r"\bmachine learning engineer\b", r"\bdata engineer\b", r"\bdevops engineer\b",
    r"\bcloud engineer\b", r"\bquantitative analyst\b", r"\bquant\b",
    r"\bdeveloper\b", r"\bprogrammer\b", r"\bresearch scientist\b",
]

CODING_BANDS = {
    0: "no coding",
    1: "minimal technical literacy",
    2: "occasional technical coursework",
    3: "moderate programming",
    4: "programming-heavy",
    5: "engineering / programming core",
}


def _hits(text, patterns):
    found = []
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            found.append(m.group(0).strip())
    return found


def _programme_text(prog):
    """Concatenate every field that legitimately describes course content."""
    parts = [
        prog.get("name") or "",
        prog.get("department") or "",
        prog.get("degree") or "",
        prog.get("academic_prereq") or "",
        prog.get("grad_outcomes") or "",
        prog.get("career_outcomes") or "",
        prog.get("notes") or "",
    ]
    curriculum = db.uj(prog.get("curriculum"), []) or []
    if isinstance(curriculum, list):
        parts.extend(str(c) for c in curriculum)
    return " \n ".join(parts).lower()


def coding_intensity(prog):
    """SPEC §10. Return (band 0-5, evidence dict).

    The band is computed from evidence. If the record carries a VERIFIED
    manual value, that wins — a human who read the curriculum page beats a
    regex — but any disagreement is recorded so the rubric can be tuned.
    """
    text = _programme_text(prog)

    hard = _hits(text, HARD_CODE)
    soft = _hits(text, SOFT_CODE)
    gov = _hits(text, GOVERNANCE_CONTEXT)
    soften = _hits(text, SOFTENERS)
    outcomes = _hits(prog.get("grad_outcomes") or "", ENGINEERING_OUTCOMES)

    # Explicit structured prerequisites are the strongest signal available.
    prereq_points = 0
    prereq_reasons = []
    if prog.get("cs_prereq") == 1:
        prereq_points += 4
        prereq_reasons.append("CS degree required")
    if prog.get("programming_prereq") == 1:
        prereq_points += 3
        prereq_reasons.append("programming prerequisite")
    if prog.get("math_prereq") == 1:
        prereq_points += 2
        prereq_reasons.append("mathematics/statistics prerequisite")

    raw = prereq_points + 1.4 * len(hard) + 0.5 * len(soft)
    raw += 2.5 * len(outcomes)                 # dominant outcomes dominate
    raw -= 0.35 * min(len(gov), 8)             # governance framing pulls down
    raw -= 1.0 * min(len(soften), 3)           # explicit "no coding needed"
    raw = max(0.0, raw)

    if raw <= 0.4:
        band = 0
    elif raw <= 1.5:
        band = 1
    elif raw <= 3.0:
        band = 2
    elif raw <= 5.5:
        band = 3
    elif raw <= 8.5:
        band = 4
    else:
        band = 5

    # A required CS degree is categorically disqualifying regardless of tone.
    if prog.get("cs_prereq") == 1:
        band = max(band, 5)
    if prog.get("programming_prereq") == 1:
        band = max(band, 4)

    evidence = {
        "computed_band": band,
        "raw": round(raw, 2),
        "hard_signals": hard,
        "soft_signals": soft,
        "governance_context": gov,
        "softeners": soften,
        "engineering_outcomes": outcomes,
        "structured_prerequisites": prereq_reasons,
        "label": CODING_BANDS[band],
    }

    manual = prog.get("coding_intensity")
    conf = db.uj(prog.get("confidence"), {}) or {}
    manual_verified = str(conf.get("coding_intensity", "")).upper() == "VERIFIED"
    if manual is not None and manual_verified:
        evidence["manual_band"] = manual
        evidence["source"] = "VERIFIED manual reading of the curriculum page"
        if manual != band:
            evidence["disagreement"] = (
                "Rubric computed %d, verified reading says %d. Using %d."
                % (band, manual, manual))
        return int(manual), evidence

    if manual is not None:
        # An unverified manual reading acts as a FLOOR, never as a ceiling.
        # This is a hard constraint: when a human has looked at the page and
        # judged it more code-heavy than the regexes can see, the regexes must
        # not be allowed to argue it back down. The reverse direction (manual
        # lower than computed) still requires VERIFIED, handled above.
        evidence["manual_band_unverified"] = manual
        if manual > band:
            evidence["floor_applied"] = (
                "Rubric computed %d but an unverified manual reading says %d. "
                "Taking the higher value - the coding constraint fails safe."
                % (band, manual))
            band = int(manual)
    evidence["computed_band"] = band
    evidence["label"] = CODING_BANDS[band]
    evidence["source"] = "computed from programme text"
    return band, evidence


def coding_verdict(prog, profile):
    """Apply the profile's hard constraint. Returns (reject: bool, band, evidence)."""
    band, evidence = coding_intensity(prog)
    hc = profile.get("hard_constraints", {})
    threshold = hc.get("reject_if_coding_intensity_at_or_above",
                       hc.get("reject_coding_intensity_at_or_above", 4))
    reject = band >= threshold
    if prog.get("cs_prereq") == 1 and hc.get("reject_if_cs_degree_required", True):
        reject = True
        evidence["reject_cause"] = "CS degree is a mandatory prerequisite"
    elif reject:
        evidence["reject_cause"] = (
            "coding_intensity %d >= reject threshold %d (%s)"
            % (band, threshold, CODING_BANDS[band]))
    return reject, band, evidence


# --------------------------------------------------------------------------
# §9 eligibility engine
# --------------------------------------------------------------------------

WORK_EXP_VALUE = {
    "mandatory": 1.0,
    "preferred": 0.9,
    "useful": 0.7,
    "irrelevant": 0.3,
    None: 0.5,
    "": 0.5,
}

# Degree families a governance/risk master's typically asks for.
PREREQ_FAMILIES = {
    "any": 1.0,
    "any_with_experience": 1.0,
    "business": 0.85,
    "social_science": 0.75,
    # A law-degree requirement is a MAJOR mismatch for a B.Tech holder, not a
    # mild one: he has neither a law degree nor law as a component of one.
    # Scored below the major_prerequisite_mismatch trigger deliberately.
    "law": 0.35,
    "economics": 0.6,
    "engineering": 1.0,
    "stem": 1.0,
    "cs": 0.0,
    "quantitative": 0.25,
}


def academic_eligibility(prog, profile):
    """§9A/§9C. Can a B.Tech Biotechnology graduate apply? 0-1 plus reasons."""
    reasons = []
    edu = (profile.get("education") or [{}])[0]
    family = edu.get("field_family", "engineering_life_sciences")

    accepts = db.uj(prog.get("academic_prereq_families"), None)
    if accepts is None:
        # Derive from the free-text prerequisite string.
        txt = (prog.get("academic_prereq") or "").lower()
        if not txt:
            return 0.5, ["Prerequisites DATA NOT VERIFIED - treated as neutral"]
        if re.search(r"computer science|informatics degree|software engineering degree", txt) \
                and re.search(r"required|must hold|only", txt):
            return 0.0, ["Requires a Computer Science degree - applicant does not hold one"]
        if re.search(r"\bany (?:discipline|background|subject|field)\b|"
                     r"all disciplines|regardless of (?:your )?background|"
                     r"open to (?:all|graduates of any)", txt):
            reasons.append("Explicitly open to any discipline")
            score = 1.0
        elif re.search(r"law degree|qualified lawyer|llb required", txt):
            reasons.append("Law degree expected - a B.Tech is a mismatch")
            score = 0.35
        elif re.search(r"quantitative|mathematics|statistics|econometrics", txt) \
                and re.search(r"strong|required|solid", txt):
            reasons.append("Strong quantitative background expected - partial mismatch")
            score = 0.35
        elif re.search(r"stem|engineering|technical|science", txt):
            reasons.append("STEM/engineering background accepted - B.Tech qualifies")
            score = 1.0
        elif re.search(r"business|management|social science|humanities", txt):
            reasons.append("Business/social-science oriented; a B.Tech is usually accepted "
                           "but is not the archetypal applicant")
            score = 0.8
        else:
            reasons.append("Prerequisites not clearly parseable - treated as neutral")
            score = 0.6
    else:
        score = max(PREREQ_FAMILIES.get(f, 0.5) for f in accepts)
        reasons.append("Accepts: %s" % ", ".join(accepts))

    if edu.get("years", 4) >= 4:
        reasons.append("4-year B.Tech normally satisfies the 240-ECTS expectation "
                       "for a 1-year taught master's")
    if family == "engineering_life_sciences" and score >= 0.8:
        reasons.append("Biotechnology is an accepted STEM discipline, not a disadvantage")

    return score, reasons


def english_eligibility(prog, profile):
    """§9D. Returns (status, note)."""
    eng = profile.get("english", {})
    ielts = prog.get("ielts")
    if not ielts:
        return "UNKNOWN", "IELTS/TOEFL requirement DATA NOT VERIFIED"
    if eng.get("medium_of_instruction_english") and eng.get("moi_certificate_obtainable"):
        return ("PROBABLY EXEMPT" if "moi" in str(ielts).lower() or "waiv" in str(ielts).lower()
                else "TEST LIKELY REQUIRED"), (
            "Requirement: %s. Degree was taught in English, so an MOI waiver may apply, "
            "but most EU universities still require IELTS from Indian applicants. "
            "Budget for the test unless the programme page says otherwise." % ielts)
    return "TEST REQUIRED", "Requirement: %s" % ielts


def work_experience_relevance(prog, profile):
    """§9E + §12. How much does 10 years of banking help here? 0-1."""
    req = (prog.get("work_exp_requirement") or "").lower().strip()
    base = WORK_EXP_VALUE.get(req, 0.5)

    text = _programme_text(prog)
    domain_bonus = 0.0
    matched = []
    for term, w in (("financial", 0.10), ("bank", 0.10), ("compliance", 0.08),
                    ("risk", 0.06), ("aml", 0.10), ("financial crime", 0.10),
                    ("regulat", 0.06), ("payments", 0.08), ("governance", 0.05)):
        if term in text:
            domain_bonus += w
            matched.append(term)
    score = min(1.0, base + domain_bonus)
    return score, {"requirement": req or "unstated", "base": base,
                   "domain_terms_matched": matched}


def international_eligibility(prog):
    """§9F."""
    if prog.get("intl_eligible") == 0:
        return False, "Not open to international / non-EU applicants"
    if prog.get("intl_eligible") is None:
        return True, "International eligibility DATA NOT VERIFIED - assumed open"
    return True, "Open to international applicants"


def test_barriers(prog, profile):
    """GRE/GMAT walls the applicant has said he will not climb."""
    blocks = []
    t = profile.get("tests", {})
    if prog.get("gre_required") == 1 and not t.get("willing_to_take_gre"):
        blocks.append("GRE required and applicant is unwilling to sit it")
    if prog.get("gmat_required") == 1 and not t.get("willing_to_take_gmat"):
        blocks.append("GMAT required and applicant is unwilling to sit it")
    return blocks


def evaluate(prog, profile):
    """Full §9 pass. Returns a dict consumed by scoring and the report."""
    acad_score, acad_reasons = academic_eligibility(prog, profile)
    eng_status, eng_note = english_eligibility(prog, profile)
    we_score, we_detail = work_experience_relevance(prog, profile)
    intl_ok, intl_note = international_eligibility(prog)
    barriers = test_barriers(prog, profile)
    reject, band, coding_ev = coding_verdict(prog, profile)

    hard_blocks = []
    if reject:
        hard_blocks.append("CODING: " + coding_ev.get("reject_cause", "coding intensity too high"))
    if not intl_ok:
        hard_blocks.append("ELIGIBILITY: " + intl_note)
    if acad_score <= 0.0:
        hard_blocks.append("ELIGIBILITY: " + (acad_reasons[0] if acad_reasons else "academic mismatch"))
    hard_blocks.extend("ELIGIBILITY: " + b for b in barriers)

    return {
        "academic_score": acad_score,
        "academic_reasons": acad_reasons,
        "english_status": eng_status,
        "english_note": eng_note,
        "work_exp_score": we_score,
        "work_exp_detail": we_detail,
        "international_ok": intl_ok,
        "international_note": intl_note,
        "test_barriers": barriers,
        "coding_band": band,
        "coding_reject": reject,
        "coding_evidence": coding_ev,
        "hard_blocks": hard_blocks,
        "eligible": not hard_blocks,
    }


# --------------------------------------------------------------------------
# §15 admission probability
# --------------------------------------------------------------------------

BANDS = ["VERY LOW", "LOW", "MEDIUM", "MEDIUM-HIGH", "HIGH"]


def admission_probability(prog, profile, elig):
    """§15. Returns (band, reason). Explains itself in plain language."""
    if elig["hard_blocks"]:
        return "VERY LOW", "Does not meet prerequisites: " + "; ".join(elig["hard_blocks"])

    points = 0.0
    reasons = []

    points += 2.5 * elig["academic_score"]
    if elig["academic_score"] >= 0.9:
        reasons.append("academic background accepted")
    elif elig["academic_score"] < 0.6:
        reasons.append("academic background is a partial mismatch")

    points += 2.0 * elig["work_exp_score"]
    req = (prog.get("work_exp_requirement") or "").lower()
    if req in ("mandatory", "preferred"):
        reasons.append("10 years of relevant experience is an active advantage "
                       "(experience is %s here)" % req)
    elif req == "irrelevant":
        reasons.append("programme does not weight work experience, so his main "
                       "differentiator is neutralised")

    # Selectivity proxy: ranking. Famous universities reject more people.
    qs = prog.get("ranking")
    try:
        qs_rank = int(re.sub(r"[^0-9]", "", str(qs))) if qs else None
    except (TypeError, ValueError):
        qs_rank = None
    if qs_rank:
        if qs_rank <= 50:
            points -= 1.4
            reasons.append("top-50 university, competitive intake")
        elif qs_rank <= 150:
            points -= 0.7
            reasons.append("top-150 university, moderately competitive")
        else:
            points += 0.3
            reasons.append("outside the top 150, less selective")
    else:
        points += 0.1

    if prog.get("gre_required") == 1 or prog.get("gmat_required") == 1:
        points -= 1.0
        reasons.append("admissions test required")

    if elig["english_status"] == "TEST REQUIRED":
        points -= 0.2

    # A career changer applying 11 years after graduating is unusual; some
    # programmes love it, some quietly prefer recent graduates.
    grad_year = (profile.get("education") or [{}])[0].get("graduation_year")
    if grad_year and req in ("irrelevant", "", None):
        points -= 0.5
        reasons.append("graduated %s and the programme does not value experience, "
                       "which weakens the application" % grad_year)

    if prog.get("deadline_type") == "ROLLING":
        points += 0.3
        reasons.append("rolling admissions favour an early, well-prepared applicant")

    if points >= 4.2:
        band = "HIGH"
    elif points >= 3.3:
        band = "MEDIUM-HIGH"
    elif points >= 2.2:
        band = "MEDIUM"
    elif points >= 1.2:
        band = "LOW"
    else:
        band = "VERY LOW"

    return band, "; ".join(reasons) if reasons else "no distinguishing factors identified"
