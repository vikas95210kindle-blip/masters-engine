"""The guide. Not "which degree" — "what do I do, starting this week".

SPEC §27 covered CV gaps. This goes further, because a degree is roughly 10%
of what gets someone hired internationally. The other 90% is evidence, habits,
visibility and network, and none of it requires waiting for an intake.

Everything here is time-phased and checkable. A recommendation with no
deadline and no way to tell whether you did it is a wish, not a plan.
"""

from . import salary as salary_mod


# --------------------------------------------------------------------------
# The non-academic half — habits and visible work
# --------------------------------------------------------------------------

HABITS = [
    {"id": "write_weekly", "name": "Publish one short analysis a week",
     "cadence": "weekly", "effort": "60-90 min",
     "what": "One post on a live regulatory development — an AI Act implementing act, a DORA "
             "incident-reporting detail, an enforcement action. 300-500 words. Say what it means "
             "operationally, not what it says.",
     "why": "This is the single cheapest way to manufacture the thing you cannot otherwise get: "
            "a public record of governance judgement. After six months you have 25 pieces of "
            "evidence that you think like a governance professional. Recruiters searching "
            "'EU AI Act' plus 'banking' will find almost nobody — the space is that thin.",
     "measure": "26 posts in 6 months. Count them.",
     "tooling": "You already have ../linkedin-automation wired to publish."},

    {"id": "reg_reading", "name": "Thirty minutes of primary regulation, daily",
     "cadence": "daily", "effort": "30 min",
     "what": "Read the actual text — the AI Act, DORA RTS, NIS2 transposition, EBA guidelines. "
             "Not summaries, not LinkedIn takes. The source.",
     "why": "Almost everyone in this field works from secondary commentary. The people who have "
            "read the primary text are visibly different in an interview within ninety seconds, "
            "and it is the one advantage that compounds without costing money.",
     "measure": "One instrument fully read per month."},

    {"id": "translate", "name": "Translate one piece of your own work per week",
     "cadence": "weekly", "effort": "45 min",
     "what": "Take something you actually did at Union Bank and rewrite it in the vocabulary of "
             "the target market: ICT third-party risk, model inventory, control testing, "
             "high-risk use case classification.",
     "why": "Your ten years are invisible to a European recruiter because they are described in "
            "Indian retail-banking language. This is not embellishment — it is translation, and "
            "it is the difference between 'bank clerk' and 'regulated-environment risk "
            "practitioner' reading the same career.",
     "measure": "A bank of 20+ translated STAR stories before any interview."},

    {"id": "outreach", "name": "Two informational conversations a week",
     "cadence": "weekly", "effort": "45 min",
     "what": "Message two people doing the job you want in the country you want. Ask one specific "
             "question about their work. Do not ask for a job or a referral.",
     "why": "Most European governance roles are filled through networks before they are posted. "
            "Sponsorship-willing employers are usually found, not advertised. Ten months of this "
            "is roughly 80 conversations and is worth more than any certificate on this list.",
     "measure": "80 conversations before you need them, not after."},

    {"id": "english_daily", "name": "Speak English out loud, daily",
     "cadence": "daily", "effort": "15 min",
     "what": "Record yourself explaining a regulatory concept for two minutes. Listen back once.",
     "why": "IELTS speaking is where competent applicants lose the band that gates the "
            "application. It is also what a hiring panel actually judges. Reading fluency does "
            "not transfer to speaking fluency without production practice.",
     "measure": "IELTS 7.5+ so no programme's band requirement can gate you."},

    {"id": "keyboard", "name": "Fifteen minutes of typing and shortcut drilling",
     "cadence": "daily", "effort": "15 min",
     "what": "Deliberate practice, not incidental typing.",
     "why": "Compounding tool leverage. Governance work is document work — the throughput "
            "difference between 45 and 85 wpm with keyboard-first navigation is roughly an hour "
            "a day, permanently.",
     "measure": "80+ wpm at 97% accuracy.",
     "tooling": "../keyboard-academy"},
]

ARTEFACTS = [
    {"id": "case_kyc", "name": "Case study: KYC onboarding as an AI Act high-risk use case",
     "time": "2 weeks",
     "what": "Classify a real onboarding flow against Annex III. Identify which obligations bite, "
             "what evidence a conformity assessment would need, and where the current process "
             "would fail one.",
     "why": "This is the single most valuable artefact you can produce, because it demonstrates "
            "the exact task an AI governance hire is paid to do, using a system you genuinely "
            "understand. Nobody can fake domain depth in KYC; you have it."},
    {"id": "case_tm", "name": "Case study: transaction monitoring and model governance",
     "time": "2 weeks",
     "what": "False-positive rates, threshold tuning, validation cadence, challenge process, and "
             "how RBI's draft MRM guidance would apply.",
     "why": "Shows you can hold the GOVERNANCE side of model risk without being a quant — which "
            "is exactly the distinction the posting data says 63% of model-risk roles blur."},
    {"id": "case_dora", "name": "Case study: payments digitisation restated in DORA terms",
     "time": "1 week",
     "what": "Your actual programme, rewritten as ICT risk management, third-party dependency, "
             "incident classification and reporting timelines.",
     "why": "DORA is present-tense hiring demand. This converts work you already did into "
            "evidence for a job you do not yet have."},
    {"id": "case_data", "name": "Case study: customer-data lineage and minimisation",
     "time": "1 week",
     "what": "Trace one data element through the account-opening interfaces you designed. Purpose "
             "limitation, retention, lineage, access.",
     "why": "Data governance is the most reachable adjacent track and this shows it concretely."},
    {"id": "framework_map", "name": "Mapping: one bank process against ISO 42001 and NIST AI RMF",
     "time": "1 week",
     "what": "A control-by-control gap map with owners and evidence.",
     "why": "ISO 27001 and ISO 42001 are the two most-named standards in the posting corpus. A "
            "worked mapping is what an employer actually needs done on day one."},
]

POSITIONING = [
    {"id": "linkedin_headline", "name": "Rewrite the LinkedIn headline",
     "time": "1 hour", "urgency": "this week",
     "what": "Lead with the destination, not the history. e.g. 'AI Governance & Technology Risk | "
             "10 yrs Banking: KYC/AML, Payments, Digitisation | EU AI Act · DORA · ISO 27001'",
     "why": "Recruiters search on keywords. Your current title does not contain any of the words "
            "they search for, so you are invisible regardless of merit."},
    {"id": "cv_restructure", "name": "Restructure the CV around risk and control language",
     "time": "1 day", "urgency": "this month",
     "what": "Every bullet becomes: what risk, what control, what evidence, what outcome. Drop "
             "process-administration language entirely.",
     "why": "The CV is currently a record of a banking-operations career. It needs to read as a "
            "record of working inside a regulated control environment — which is the same ten "
            "years, described in the vocabulary the target market screens on."},
    {"id": "internal_move", "name": "Get onto a risk or model-governance workstream at Union Bank",
     "time": "ongoing", "urgency": "this quarter",
     "what": "Ask explicitly to be assigned to the RBI Model Risk Management work.",
     "why": "The highest-leverage item on the entire list and it costs nothing. A single line of "
            "genuine in-role AI/model governance experience does more for employability than any "
            "certificate, and it is the only thing that fixes the real bottleneck: no European "
            "employer sponsors a visa for a CV with zero governance experience."},
]


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build_plan(profile, gap_roadmap, salary_by_career=None, top_career=None):
    """A time-phased plan. Ordered by leverage, not by comfort."""
    reachable = [g for g in gap_roadmap
                 if g.get("prereq", "None").startswith("None") or "qualifies" in g.get("prereq", "")]
    blocked = [g for g in gap_roadmap
               if not (g.get("prereq", "None").startswith("None") or "qualifies" in g.get("prereq", ""))]

    phases = [
        {
            "window": "Next 30 days",
            "theme": "Make yourself findable and start the compounding habits",
            "items": [
                {"kind": "positioning", "name": p["name"], "why": p["why"], "time": p["time"]}
                for p in POSITIONING if p["urgency"] in ("this week", "this month")
            ] + [
                {"kind": "habit", "name": h["name"], "why": h["why"], "time": h["effort"] + " / " + h["cadence"]}
                for h in HABITS if h["id"] in ("write_weekly", "reg_reading", "english_daily")
            ] + [
                {"kind": "certification", "name": g["gap"], "why": g["why"], "time": g["time"]}
                for g in reachable[:1]
            ],
        },
        {
            "window": "Months 2-3",
            "theme": "Build the evidence nobody can fake",
            "items": [
                {"kind": "artefact", "name": a["name"], "why": a["why"], "time": a["time"]}
                for a in ARTEFACTS[:3]
            ] + [
                {"kind": "positioning", "name": p["name"], "why": p["why"], "time": p["time"]}
                for p in POSITIONING if p["urgency"] == "this quarter"
            ] + [
                {"kind": "habit", "name": h["name"], "why": h["why"], "time": h["effort"] + " / " + h["cadence"]}
                for h in HABITS if h["id"] in ("translate", "outreach")
            ],
        },
        {
            "window": "Months 4-6",
            "theme": "Credential against measured demand, and sit the English test",
            "items": [
                {"kind": "certification", "name": g["gap"], "why": g["why"], "time": g["time"],
                 "demand": g.get("mentions")}
                for g in reachable[1:4]
            ] + [
                {"kind": "admission", "name": "Sit IELTS Academic", "time": "1 month",
                 "why": "Gates the application itself. Target 7.5+ so no programme's band "
                        "requirement can exclude you, and so it never becomes the reason a "
                        "deadline is missed."},
                {"kind": "artefact", "name": ARTEFACTS[3]["name"], "why": ARTEFACTS[3]["why"],
                 "time": ARTEFACTS[3]["time"]},
            ],
        },
        {
            "window": "Months 7-12",
            "theme": "Apply from strength, and decide the track",
            "items": [
                {"kind": "application", "name": "Submit master's applications",
                 "time": "2 months",
                 "why": "By this point the application is supported by published writing, four "
                        "case studies, a recognised standard credential and a translated CV — "
                        "not by a 2015 degree alone."},
                {"kind": "application", "name": "Apply for Chevening / Erasmus Mundus in the same cycle",
                 "time": "6 weeks",
                 "why": "Both have fixed annual windows. Missing one costs a full year, and "
                        "Chevening requires three UK offers in hand by its July deadline."},
                {"kind": "decision", "name": "Track A vs Track B decision point",
                 "time": "January 2027",
                 "why": "If an internal AI/model-governance role has landed by then, the master's "
                        "is optional. If it has not, it becomes the immigration instrument."},
                {"kind": "certification", "name": ARTEFACTS[4]["name"], "why": ARTEFACTS[4]["why"],
                 "time": ARTEFACTS[4]["time"]},
            ],
        },
    ]

    return {
        "phases": phases,
        "habits": HABITS,
        "artefacts": ARTEFACTS,
        "positioning": POSITIONING,
        "reachable_certs": reachable,
        "blocked_certs": blocked,
        "salary_target": salary_by_career.get(top_career) if (salary_by_career and top_career) else None,
    }


def readiness(profile, gap_roadmap, S_runs=None):
    """A blunt score: how hireable is this profile internationally, today.

    Deliberately harsh. The point is to show movement over months, not to
    flatter. Everything here is something he controls.
    """
    held = set(c.lower() for c in (profile.get("certifications", {}).get("held") or []))
    dims = [
        {"name": "Domain depth (banking, KYC/AML, payments)", "score": 90,
         "note": "Genuinely strong and rare. This is the asset."},
        {"name": "Governance vocabulary and frameworks", "score": 25,
         "note": "Knows the domain, not yet the target market's language."},
        {"name": "Recognised credential", "score": 0 if not held else 60,
         "note": "None held. ISO 27001 is the highest-demand reachable one."},
        {"name": "Public evidence of judgement", "score": 10,
         "note": "Little published. The cheapest gap to close and the fastest to show."},
        {"name": "European network", "score": 5,
         "note": "Near zero. Only fixable by deliberate outreach or physical presence."},
        {"name": "In-role governance experience", "score": 15,
         "note": "The real bottleneck. The internal RBI-MRM workstream is the fix."},
        {"name": "English (assessed)", "score": 50,
         "note": "Fluent, but untested. An unassessed band gates applications."},
        {"name": "Immigration eligibility", "score": 35,
         "note": "No relevant degree yet, so the high permit threshold applies."},
    ]
    overall = round(sum(d["score"] for d in dims) / len(dims))
    return {"overall": overall, "dimensions": dims,
            "verdict": ("Not yet competitive internationally, and the gaps are specific rather "
                        "than vague. Six of the eight are closable without leaving your current "
                        "job.") if overall < 50 else "Competitive; keep compounding."}
