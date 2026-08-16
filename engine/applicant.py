"""Indian-applicant eligibility, scholarship matching, and the international
competitiveness gap engine.

Three questions this module answers, in order of how much they matter:
  1. Can I, specifically, actually apply to this? (every requirement, walked)
  2. What money can I, specifically, actually win?
  3. What am I missing to compete internationally - ranked by EVIDENCE from
     real job postings, not by opinion.
"""

import re

from . import db


# --------------------------------------------------------------------------
# 1. Can an Indian national with this exact profile apply?
# --------------------------------------------------------------------------

def indian_application_check(prog, profile, country=None):
    """Walk every application requirement and return a verdict plus the
    per-requirement detail. Blockers are things that stop the application;
    warnings are things that weaken it."""
    checks = []
    blockers = []
    warnings = []

    def add(name, status, detail):
        checks.append({"requirement": name, "status": status, "detail": detail})
        if status == "BLOCKED":
            blockers.append("%s: %s" % (name, detail))
        elif status == "RISK":
            warnings.append("%s: %s" % (name, detail))

    edu = (profile.get("education") or [{}])[0]
    exp = (profile.get("experience") or [{}])[0]
    ident = profile.get("identity", {})
    conf = db.uj(prog.get("confidence"), {}) or {}

    # -- nationality / international eligibility ----------------------------
    if prog.get("intl_eligible") == 0:
        add("International eligibility", "BLOCKED",
            "Programme is not open to non-EU/international applicants.")
    elif prog.get("intl_eligible") is None:
        add("International eligibility", "UNKNOWN",
            "Not stated on the official page. Confirm before applying.")
    else:
        add("International eligibility", "OK",
            "Open to international applicants; Indian nationals may apply.")

    # -- degree recognition -------------------------------------------------
    yrs = edu.get("years", 4)
    if yrs >= 4:
        add("Degree recognition", "OK",
            "A 4-year Indian B.Tech is normally accepted as equivalent to a "
            "UK/EU bachelor's for master's entry (240 ECTS equivalent).")
    else:
        add("Degree recognition", "RISK",
            "A 3-year Indian bachelor's is sometimes judged short of the "
            "European 240-ECTS expectation.")

    # -- degree classification ---------------------------------------------
    cls = (edu.get("classification") or "").lower()
    prereq = (prog.get("academic_prereq") or "")
    wants21 = re.search(r"2:1|upper second|H2\.1|first[- ]class", prereq, re.I)
    if "first" in cls:
        add("Degree classification", "OK",
            "First Class maps to a UK 2:1 or better. Meets the stated bar%s."
            % (" (2:1 required)" if wants21 else ""))
    else:
        add("Degree classification", "UNKNOWN", "Classification not established.")

    # -- discipline match ---------------------------------------------------
    fams = db.uj(prog.get("academic_prereq_families"), None)
    if fams and "cs" in fams and len(fams) == 1:
        add("Discipline", "BLOCKED",
            "Requires a Computer Science degree; a B.Tech in Biotechnology "
            "does not qualify.")
    elif fams and "law" in fams and not any(f in fams for f in ("any", "any_with_experience", "stem", "engineering", "business")):
        add("Discipline", "BLOCKED",
            "Requires a law degree or law as a major component. His B.Tech has neither.")
    elif re.search(r"relevant discipline", prereq, re.I):
        add("Discipline", "RISK",
            "Asks for a 'relevant discipline' without defining it. Biotechnology "
            "is STEM but not obviously relevant - the application must argue "
            "relevance from 10 years of regulated banking and digitisation work, "
            "not from the degree subject.")
    elif fams and any(f in fams for f in ("any", "any_with_experience")):
        add("Discipline", "OK", "Explicitly open to any discipline.")
    elif fams and any(f in fams for f in ("stem", "engineering")):
        add("Discipline", "OK", "STEM/engineering accepted - a B.Tech qualifies.")
    else:
        add("Discipline", "UNKNOWN", "Accepted disciplines not clearly stated.")

    # -- English ------------------------------------------------------------
    eng = profile.get("english", {})
    ielts = prog.get("ielts")
    if not ielts:
        add("English requirement", "UNKNOWN",
            "Not stated. Assume a test is required and budget for it.")
    else:
        m = re.search(r"(\d\.\d|\d)", str(ielts))
        band = float(m.group(1)) if m else None
        if band and band >= 7.0:
            add("English requirement", "RISK",
                "%s. That is a demanding bar - 7.0 with 6.5 minimums fails a lot "
                "of otherwise strong applicants on one component. Budget "
                "preparation time, and note that an MOI letter will NOT be "
                "accepted at this level." % ielts)
        else:
            add("English requirement", "OK",
                "%s. Achievable. His degree was taught in English, so an MOI "
                "waiver may apply, but most institutions still require the test "
                "from Indian applicants - assume you must sit it." % ielts)

    # -- work experience ----------------------------------------------------
    req = (prog.get("work_exp_requirement") or "").lower()
    if req in ("mandatory", "preferred"):
        add("Work experience", "ADVANTAGE",
            "Experience is %s here. His 10 years is a differentiator rather than "
            "something to explain away." % req)
    elif req == "irrelevant":
        add("Work experience", "RISK",
            "The programme does not weight work experience, so his single "
            "biggest asset counts for nothing and he competes against recent "
            "graduates on academic record from 2015.")
    else:
        add("Work experience", "UNKNOWN", "Not stated.")

    # -- admissions tests ---------------------------------------------------
    t = profile.get("tests", {})
    if prog.get("gre_required") == 1 and not t.get("willing_to_take_gre"):
        add("Admissions test", "BLOCKED", "GRE required; applicant will not sit it.")
    elif prog.get("gmat_required") == 1 and not t.get("willing_to_take_gmat"):
        add("Admissions test", "BLOCKED", "GMAT required; applicant will not sit it.")
    else:
        add("Admissions test", "OK", "No GRE or GMAT required.")

    # -- age ----------------------------------------------------------------
    grad = edu.get("graduation_year")
    if prog.get("age_restrictions"):
        add("Age restrictions", "RISK", str(prog.get("age_restrictions")))
    elif grad and prog.get("country_code") == "AU":
        add("Age restrictions", "RISK",
            "Australia's post-study work visa (subclass 485) carries an upper "
            "age limit that has been tightened. Graduating in 2015 makes this a "
            "live risk - verify before spending anything.")
    else:
        add("Age restrictions", "OK", "None stated for the programme itself.")

    # -- visa ---------------------------------------------------------------
    visa = db.uj((country or {}).get("visa"), {}) or {}
    psw = prog.get("post_study_work_months")
    if psw == 0:
        add("Student visa", "RISK",
            "Delivery mode (%s) confers NO student visa and no post-study work "
            "route. Valid as a credential; useless as a migration route."
            % (prog.get("study_mode") or "unstated"))
    elif visa.get("flag") == "RED":
        add("Student visa", "RISK",
            "Destination flagged RED: %s" % visa.get("why_flag", ""))
    else:
        add("Student visa", "OK",
            "Route: %s. Indian nationals are eligible." % (prog.get("visa_route") or "standard student visa"))

    # -- money --------------------------------------------------------------
    tui = prog.get("tuition_eur")
    ceiling = ident.get("self_fund_ceiling_eur")
    if tui is None:
        add("Affordability", "UNKNOWN",
            "Tuition DATA NOT VERIFIED - cannot assess affordability or ROI.")
    else:
        living = (prog.get("living_cost_eur") or 0) * ((prog.get("duration_months") or 12) / 12)
        total = tui + living
        if ceiling and total > ceiling:
            add("Affordability", "RISK",
                "Approx EUR %,.0f all-in exceeds the stated self-funding ceiling "
                "of EUR %,.0f. A scholarship is not optional here, it is required."
                .replace(",", "") % (total, ceiling))
        else:
            add("Affordability", "OK",
                "Approx EUR %.0f all-in, within the stated self-funding ceiling." % total)

    # -- proof of funds (a real, commonly missed requirement) ---------------
    add("Proof of funds", "INFO",
        "Every student-visa route requires evidence of tuition plus living "
        "costs held in an account, usually for 28 consecutive days before "
        "applying. Plan the cash flow, not just the total.")

    if blockers:
        verdict, summary = "CANNOT APPLY", "%d blocking requirement%s" % (len(blockers), "" if len(blockers) == 1 else "s")
    elif len([c for c in checks if c["status"] == "UNKNOWN"]) >= 4:
        verdict, summary = "UNCLEAR", "Too many unverified requirements to judge"
    elif warnings:
        verdict, summary = "CAN APPLY - WITH RISKS", "%d risk%s to manage" % (len(warnings), "" if len(warnings) == 1 else "s")
    else:
        verdict, summary = "CAN APPLY", "All checked requirements satisfied"

    return {"verdict": verdict, "summary": summary, "checks": checks,
            "blockers": blockers, "warnings": warnings}


# --------------------------------------------------------------------------
# 2. Which scholarships can he actually win?
# --------------------------------------------------------------------------

def scholarships_for(prog, cfg):
    """Scholarships open to an Indian national for this programme's country."""
    cc = prog.get("country_code")
    out = []
    for s in cfg.get("scholarships", []):
        if not s.get("indian_eligible"):
            continue
        countries = s.get("countries", [])
        if "*" in countries or cc in countries or (cc in ("IE", "NL", "DE", "BE") and "EU" in countries):
            out.append(s)
    order = {"STRONG": 0, "MEDIUM": 1, "LIKELY INELIGIBLE": 2}
    out.sort(key=lambda s: order.get(s.get("applicant_fit"), 3))
    return out


# --------------------------------------------------------------------------
# 3. What is missing to compete internationally (§27, evidence-ranked)
# --------------------------------------------------------------------------

# Static remediation knowledge. Priority is NOT hardcoded - it is computed from
# how often each item appears in the real postings the job-market engine read.
GAP_LIBRARY = [
    {"id": "iso27001", "gap": "ISO/IEC 27001 (information security management)",
     "kind": "certification", "match": ["27001"], "topic_match": ["information security management"],
     "cost": "Lead Implementer / Lead Auditor courses ~EUR 1,000-2,500",
     "time": "1-2 months", "prereq": "None",
     "why": "THE most-named credential in the entire posting corpus by a wide margin. It has no formal prerequisite, it is directly reachable, and it is the common language of every GRC function in Europe. If only one certification gets bought, the evidence says this is it."},
    {"id": "aigp", "gap": "IAPP AIGP (AI Governance Professional)",
     "kind": "certification", "match": ["aigp", "iapp"], "topic_match": ["ai governance", "responsible ai"],
     "cost": "USD 649 member / 799 non-member + USD 295 membership",
     "time": "3-6 months", "prereq": "None",
     "why": "The only entry-level AI governance credential with no prerequisites. BUT THE DATA IS SOBERING: it is named in just 13 of 1,438 postings. It is a BET on where the market goes once the AI Act's Annex III obligations land in Dec 2027 - not a response to demand that exists today. Buy it as positioning, with eyes open, not as the thing that gets you hired next year."},
    {"id": "cipp", "gap": "IAPP CIPP/E (privacy, EU)",
     "kind": "certification", "match": ["cipp"], "topic_match": ["gdpr", "privacy", "data protection"],
     "cost": "Similar to AIGP", "time": "3-4 months", "prereq": "None",
     "why": "Privacy is the most mature governance market in Europe and CIPP/E is its standard credential. Pairs naturally with AIGP."},
    {"id": "iso42001", "gap": "ISO/IEC 42001 (AI management system)",
     "kind": "certification", "match": ["42001", "iso 42001"], "topic_match": [],
     "cost": "Foundation courses ~EUR 500-1,500", "time": "1-2 months", "prereq": "None",
     "why": "The certifiable AI management standard. Auditors and consultancies are hiring specifically against it."},
    {"id": "crisc", "gap": "ISACA CRISC (risk and information systems control)",
     "kind": "certification", "match": ["crisc"],
     "cost": "~USD 575 exam", "time": "4-6 months", "prereq": "3 years experience (he qualifies)",
     "why": "The technology-risk credential most often named by banks. His banking risk experience counts toward the requirement."},
    {"id": "cisa", "gap": "ISACA CISA (information systems audit)",
     "kind": "certification", "match": ["cisa"],
     "cost": "~USD 575 exam", "time": "6 months", "prereq": "5 years audit/control experience",
     "why": "The Big-4 technology-audit entry credential and a prerequisite for ISACA's AAIA."},
    {"id": "cism", "gap": "ISACA CISM (security management)",
     "kind": "certification", "match": ["cism"],
     "cost": "~USD 575 exam", "time": "6 months", "prereq": "5 years security management",
     "why": "Gateway to security governance leadership and a prerequisite for AAISM. Note the experience bar is in SECURITY management specifically."},
    {"id": "cissp", "gap": "ISC2 CISSP",
     "kind": "certification", "match": ["cissp"],
     "cost": "~USD 749", "time": "6-12 months", "prereq": "5 years in 2 of 8 domains",
     "why": "The most-demanded security credential globally, but the experience prerequisite is genuinely hard to satisfy from a banking-operations background."},
    {"id": "euaiact", "gap": "EU AI Act working knowledge",
     "kind": "regulation", "match": ["eu ai act", "ai act"],
     "cost": "Free", "time": "3-4 weeks", "prereq": "None",
     "why": "Annex III high-risk obligations land in Dec 2027. Employers are hiring now for the people who will implement them."},
    {"id": "dora", "gap": "DORA / ICT operational resilience",
     "kind": "regulation", "match": ["dora"],
     "cost": "Free", "time": "3-4 weeks", "prereq": "None",
     "why": "Already in force since Jan 2025 - this is present-tense demand, not forecast. Restate his payments-digitisation work in DORA vocabulary: ICT risk, third-party dependency, incident reporting."},
    {"id": "nis2", "gap": "NIS2",
     "kind": "regulation", "match": ["nis2", "nis 2"],
     "cost": "Free", "time": "2 weeks", "prereq": "None",
     "why": "Drives the cyber-GRC hiring wave, which the posting data shows is the deepest non-coding market available to him."},
    {"id": "nist", "gap": "NIST AI Risk Management Framework",
     "kind": "framework", "match": ["nist ai", "nist rmf", "ai rmf"],
     "cost": "Free", "time": "2-3 weeks", "prereq": "None",
     "why": "The de facto vocabulary for AI risk work, and the one US-headquartered employers expect."},
    {"id": "mrm", "gap": "Model risk governance (SR 11-7 / RBI MRM)",
     "kind": "framework", "match": ["sr 11-7", "model risk", "mrm"],
     "cost": "Free", "time": "1 month", "prereq": "None",
     "why": "RBI's draft Model Risk Management guidance is the internal hook at Union Bank. CAUTION: stay on the GOVERNANCE side - the posting data shows 63% of model-risk roles demand coding."},
    {"id": "portfolio", "gap": "Demonstrable AI-governance artefacts",
     "kind": "evidence", "match": [],
     "cost": "Free", "time": "6-8 weeks", "prereq": "None",
     "why": "The highest-leverage item on this list and the only one nobody can buy. Four written case studies mapping real Union Bank work to AI-risk concepts: KYC onboarding as an Annex III high-risk use case; transaction monitoring and model validation thresholds; payments resilience in DORA vocabulary; customer-data lineage and minimisation. This is what makes a CV credible without a job title you do not yet hold."},
    {"id": "english", "gap": "IELTS Academic",
     "kind": "admission", "match": [],
     "cost": "~INR 17,000", "time": "1 month", "prereq": "None",
     "why": "Required by nearly every programme in the corpus, and 7.0 with 6.5 minimums (Edinburgh, likely Oxford/UCL) is a real bar. It gates the application itself, so it is urgent rather than important."},
    {"id": "network", "gap": "European professional network and market presence",
     "kind": "structural", "match": [],
     "cost": "The degree", "time": "Duration of the degree",
     "prereq": "On-campus study",
     "why": "Cannot be fixed remotely, which is the entire argument for an on-campus master's over an online one. No certification substitutes for being in the market."},
]


def international_gaps(profile, jm_evidence=None, top_careers=None):
    """Rank the gaps by MEASURED employer demand where possible.

    `jm_evidence` is jobmarket.run()['by_id']. We count how often each cert and
    regulation is named across the postings matched to his target careers, and
    use that to order the roadmap. An item nobody asks for drops down the list
    regardless of how impressive it sounds.
    """
    held = {c.lower() for c in (profile.get("certifications", {}).get("held") or [])}
    demand = {}

    if jm_evidence:
        careers = top_careers or list(jm_evidence.keys())
        for cid in careers:
            ev = jm_evidence.get(cid) or {}
            for name, n in (ev.get("top_certs") or []):
                demand[str(name).lower()] = demand.get(str(name).lower(), 0) + n
            for name, n in (ev.get("top_regulations") or []):
                demand[str(name).lower()] = demand.get(str(name).lower(), 0) + n

    out = []
    for g in GAP_LIBRARY:
        if g["id"] in held:
            continue
        # A posting naming "GDPR" is evidence that PRIVACY KNOWLEDGE matters.
        # It is NOT evidence that the CIPP/E certificate is demanded. Conflating
        # the two ranked CIPP/E and CISSP top purely because their topic words
        # are common, which is a measurement error, not a finding. Counted apart.
        named = sum(n for key, n in demand.items()
                    if any(m in key for m in g.get("match", [])))
        topical = sum(n for key, n in demand.items()
                      if any(m in key for m in g.get("topic_match", [])))
        entry = dict(g)
        entry["mentions"] = named
        entry["topic_mentions"] = topical
        entry["measured"] = named > 0

        # Certification demand is scored on the certificate being NAMED.
        # Topic demand contributes at a heavy discount: it says the subject
        # matters, not that the badge does.
        base = {"evidence": 45, "structural": 40, "admission": 38}.get(g["kind"], 0)
        reachable = 0 if g.get("prereq", "None").startswith("None") else -8
        entry["priority"] = named * 2 + topical * 0.15 + base + reachable
        out.append(entry)

    out.sort(key=lambda g: -g["priority"])
    for i, g in enumerate(out, 1):
        g["rank"] = i
        g["band"] = "DO FIRST" if i <= 3 else "NEXT" if i <= 6 else "LATER"
    return out
