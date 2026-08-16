#!/usr/bin/env python3
"""SPEC §56 test suite. Run: python3 tests/test_engine.py

These tests exist to protect the one constraint that cannot be allowed to fail
quietly: the non-coding filter. If a programming-heavy MSc ever reaches a
shortlist, the whole system has actively wasted the applicant's money.
"""

import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import db, eligibility, jobmarket, load, scoring

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROFILE = load.load_json("profile.json")
WEIGHTS = load.load_json("weights.json")
CAREERS = load.load_json("careers.json")
COUNTRIES = {c["code"]: c for c in load.load_json("countries.json")["countries"]}


def as_row(country):
    """Config dicts use nested objects; DB rows use JSON strings. Tests run
    against the DB shape so they exercise the same code path as production."""
    c = dict(country)
    c["scores"] = db.js(c.get("scores"))
    c["visa"] = db.js(c.get("visa"))
    c["scores_conf"] = c.get("scores_confidence")
    return c


def career(cid):
    return next(c for c in CAREERS["careers"] if c["id"] == cid)


BASE = {
    "id": "test", "name": "MSc Test", "country_code": "IE", "city": "Dublin",
    "degree": "MSc", "duration_months": 12, "study_mode": "full-time on-campus",
    "tuition_eur": 20000, "living_cost_eur": 14000,
    "application_deadline": None, "deadline_type": "ROLLING",
    "ielts": "6.5", "gre_required": 0, "gmat_required": 0,
    "academic_prereq": "Honours degree in any discipline",
    "programming_prereq": 0, "math_prereq": 0, "cs_prereq": 0,
    "work_exp_requirement": "preferred", "intl_eligible": 1,
    "post_study_work_months": 24, "ranking": "200",
    "ai_relevance": 6, "governance_relevance": 9, "cyber_relevance": 5,
    "risk_relevance": 9, "finserv_relevance": 7,
    "coding_intensity": None, "curriculum": db.js([]),
    "grad_outcomes": "risk manager, compliance officer, governance specialist",
    "confidence": db.js({}), "target_careers": db.js(["cyber_grc"]),
}


def prog(**over):
    p = copy.deepcopy(BASE)
    for k, v in over.items():
        p[k] = db.js(v) if isinstance(v, (list, dict)) else v
    return p


def score(p, cid="cyber_grc", cc="IE", weights=None):
    return scoring.score_programme(
        p, PROFILE, career(cid), as_row(COUNTRIES[cc]), None, weights or WEIGHTS)


def no_rank_filter():
    """Weights with the prestige gate off, for testing merit in isolation."""
    w = copy.deepcopy(WEIGHTS)
    w.setdefault("filters", {})["enforce_rank_filter"] = False
    return w


# --------------------------------------------------------------------------

class TestCodingFilter(unittest.TestCase):
    """SPEC §56 'Coding' + §10."""

    def test_programming_heavy_msc_is_rejected(self):
        p = prog(name="MSc Software Engineering",
                 curriculum=["Programming in Python", "Algorithms and Data Structures",
                             "Machine Learning", "Software Engineering", "Compilers"],
                 grad_outcomes="software engineer, machine learning engineer, data scientist")
        band, ev = eligibility.coding_intensity(p)
        self.assertGreaterEqual(band, 4, "programming-heavy MSc must band >= 4; got %d (%s)"
                                % (band, ev))
        reject, _, _ = eligibility.coding_verdict(p, PROFILE)
        self.assertTrue(reject)
        s = score(p)
        self.assertEqual(s["recommendation"], "REJECT - CODING")

    def test_cs_degree_prerequisite_is_hard_reject(self):
        p = prog(name="MSc Cybersecurity", cs_prereq=1, programming_prereq=1)
        reject, band, ev = eligibility.coding_verdict(p, PROFILE)
        self.assertTrue(reject)
        self.assertEqual(band, 5)
        self.assertIn("CS degree", ev["reject_cause"])

    def test_governance_programme_with_optional_coding_survives(self):
        """SPEC §10: a programme may contain Python and still qualify if it is
        minor/optional and the programme is governance-oriented."""
        p = prog(name="MSc Cybersecurity Risk Management",
                 curriculum=["Cybersecurity Risk Management", "Information Systems Management",
                             "Philosophy of Information and Information Ethics",
                             "Strategic Management",
                             "Advanced Programming for Business Analytics (OPTIONAL)"],
                 grad_outcomes="risk analyst, compliance officer, governance specialist")
        band, ev = eligibility.coding_intensity(p)
        self.assertLessEqual(band, 3, "governance programme wrongly banded %d: %s" % (band, ev))
        reject, _, _ = eligibility.coding_verdict(p, PROFILE)
        self.assertFalse(reject)

    def test_verified_manual_band_overrides_rubric(self):
        p = prog(name="MSc Governance", coding_intensity=1,
                 confidence={"coding_intensity": "VERIFIED"},
                 curriculum=["Programming", "Machine Learning", "Algorithms"])
        band, ev = eligibility.coding_intensity(p)
        self.assertEqual(band, 1)
        self.assertIn("disagreement", ev)

    def test_engineering_outcomes_dominate(self):
        """A programme whose graduates become engineers is an engineering
        programme, whatever its title says."""
        p = prog(name="MSc Technology Governance",
                 grad_outcomes="software engineer, data engineer, ML engineer")
        band, _ = eligibility.coding_intensity(p)
        self.assertGreaterEqual(band, 4)


class TestEligibility(unittest.TestCase):
    """SPEC §56 'Eligibility' + §9."""

    def test_cs_degree_requirement_rejected(self):
        p = prog(academic_prereq="Applicants must hold a degree in computer science "
                                 "or software engineering. Required.")
        s, reasons = eligibility.academic_eligibility(p, PROFILE)
        self.assertEqual(s, 0.0)
        elig = eligibility.evaluate(p, PROFILE)
        self.assertFalse(elig["eligible"])

    def test_any_discipline_is_fully_eligible(self):
        p = prog(academic_prereq="A 2:1 honours degree in any discipline. "
                                 "Professional experience also considered.")
        s, _ = eligibility.academic_eligibility(p, PROFILE)
        self.assertEqual(s, 1.0)

    def test_gre_requirement_blocks(self):
        p = prog(gre_required=1)
        elig = eligibility.evaluate(p, PROFILE)
        self.assertFalse(elig["eligible"])
        self.assertTrue(any("GRE" in b for b in elig["hard_blocks"]))

    def test_ten_years_banking_helps_when_experience_valued(self):
        valued = prog(work_exp_requirement="mandatory",
                      academic_prereq="business or compliance background; "
                                      "financial services experience required")
        ignored = prog(work_exp_requirement="irrelevant", academic_prereq="any discipline")
        a, _ = eligibility.work_experience_relevance(valued, PROFILE)
        b, _ = eligibility.work_experience_relevance(ignored, PROFILE)
        self.assertGreater(a, b)

    def test_non_international_is_rejected(self):
        p = prog(intl_eligible=0)
        elig = eligibility.evaluate(p, PROFILE)
        self.assertFalse(elig["eligible"])


class TestFit(unittest.TestCase):
    """SPEC §56 'Fit': a governance-focused AI programme should score highly."""

    def test_governance_ai_programme_scores_well(self):
        p = prog(name="MSc AI Governance and Risk",
                 governance_relevance=10, risk_relevance=9, ai_relevance=9,
                 finserv_relevance=8, work_exp_requirement="preferred",
                 curriculum=["AI governance", "Risk management", "Regulation and compliance",
                             "AI ethics", "Audit and assurance"],
                 grad_outcomes="AI governance manager, risk manager, compliance officer")
        # Merit is judged with the prestige gate off — a governance programme at
        # an unremarkable university must still score well on its own terms.
        s = score(p, "ai_gov_fs", weights=no_rank_filter())
        self.assertGreaterEqual(s["overall"], 60,
                                "governance programme scored only %.1f" % s["overall"])
        self.assertIn(s["recommendation"], ("APPLY NOW", "STRONG APPLY", "CONSIDER"))
        self.assertEqual(s["penalties"], [])

    def test_career_alignment_penalty_applies(self):
        """SPEC §56 'Career': a programme leading primarily to software
        engineering should be penalised."""
        p = prog(name="MSc Software Development",
                 governance_relevance=1, risk_relevance=1, ai_relevance=2,
                 finserv_relevance=1)
        s = score(p)
        rules = [x["rule"] for x in s["penalties"]]
        self.assertIn("poor_career_alignment", rules)


class TestRankFilter(unittest.TestCase):
    """User-requested top-50 prestige gate."""

    def test_top50_passes(self):
        s = score(prog(ranking='27'))
        self.assertTrue(s["rank_ok"])
        self.assertEqual(s["university_rank"], 27)
        self.assertNotEqual(s["recommendation"], "FILTERED - RANK")

    def test_outside_limit_is_filtered(self):
        limit = WEIGHTS["filters"]["min_university_rank"]
        s = score(prog(ranking=str(limit + 200)))
        self.assertFalse(s["rank_ok"])
        self.assertEqual(s["recommendation"], "FILTERED - RANK")
        self.assertIn("outside top %d" % limit, s["rank_note"])

    def test_inside_limit_passes(self):
        limit = WEIGHTS["filters"]["min_university_rank"]
        s = score(prog(ranking=str(max(1, limit - 5))))
        self.assertTrue(s["rank_ok"])

    def test_unranked_is_filtered(self):
        s = score(prog(ranking=None))
        self.assertFalse(s["rank_ok"])
        self.assertIsNone(s["university_rank"])

    def test_indian_check_blocks_cs_requirement(self):
        from engine import applicant
        p = prog(academic_prereq_families=['cs'])
        chk = applicant.indian_application_check(p, PROFILE, as_row(COUNTRIES['IE']))
        self.assertEqual(chk["verdict"], "CANNOT APPLY")
        self.assertTrue(any('Computer Science' in b for b in chk["blockers"]))

    def test_indian_check_passes_open_programme(self):
        from engine import applicant
        p = prog(academic_prereq_families=['any'], work_exp_requirement='preferred')
        chk = applicant.indian_application_check(p, PROFILE, as_row(COUNTRIES['IE']))
        self.assertIn(chk["verdict"], ("CAN APPLY", "CAN APPLY - WITH RISKS"))
        self.assertEqual(chk["blockers"], [])

    def test_online_programme_flagged_no_visa(self):
        from engine import applicant
        p = prog(post_study_work_months=0, study_mode='online part-time')
        chk = applicant.indian_application_check(p, PROFILE, as_row(COUNTRIES['IE']))
        self.assertTrue(any('no student visa' in w.lower() or 'NO student visa' in w
                            for w in chk["warnings"]))

    def test_gap_roadmap_ranks_measured_demand_first(self):
        from engine import applicant, jobmarket
        cfg = CAREERS
        ev = jobmarket.run(None, cfg, 'test')["by_id"] if jobmarket.load_postings() else {}
        gaps = applicant.international_gaps(PROFILE, ev, [c["id"] for c in cfg["careers"][:5]])
        self.assertTrue(gaps)
        self.assertEqual(gaps[0]["rank"], 1)
        self.assertIn(gaps[0]["band"], ("DO FIRST",))
        # every gap must carry a why and a time cost
        for g in gaps:
            self.assertTrue(g["why"])
            self.assertTrue(g["time"])

    def test_filter_does_not_destroy_underlying_score(self):
        """A filtered programme keeps its real merit score, so turning the
        filter off restores it rather than requiring a rescore."""
        p = prog(ranking='289')
        filtered = score(p)
        merit = score(p, weights=no_rank_filter())
        self.assertAlmostEqual(filtered["overall"], merit["overall"], places=1)
        self.assertNotEqual(merit["recommendation"], "FILTERED - RANK")

    def test_coding_reject_outranks_rank_filter(self):
        """A coding violation must stay visible as a coding reject, not be
        relabelled as a ranking problem."""
        s = score(prog(ranking='289', cs_prereq=1))
        self.assertEqual(s["recommendation"], "REJECT - CODING")


class TestDeadlines(unittest.TestCase):
    """SPEC §56 'Deadline'."""

    def test_urgency_ordering(self):
        vals = [scoring.deadline_urgency_points(d) for d in (3, 10, 25, 50, 85, 200)]
        self.assertEqual(vals, sorted(vals, reverse=True))

    def test_bucket_assignment(self):
        import datetime
        today = datetime.date(2026, 8, 14)
        p = prog(application_deadline="2026-08-18", deadline_type="FIXED")
        b, days, status = scoring.deadline_state(p, WEIGHTS, today)
        self.assertEqual(b, "DEADLINE IN 7 DAYS")
        self.assertEqual(days, 4)
        self.assertEqual(status, "OPEN NOW")

    def test_closed_deadline_detected(self):
        import datetime
        p = prog(application_deadline="2026-01-01", deadline_type="FIXED")
        b, days, status = scoring.deadline_state(p, WEIGHTS, datetime.date(2026, 8, 14))
        self.assertEqual(status, "CLOSED")

    def test_near_deadline_raises_priority(self):
        import datetime
        today = datetime.date(2026, 8, 14)
        soon = prog(application_deadline="2026-08-20", deadline_type="FIXED")
        far = prog(application_deadline="2027-08-20", deadline_type="FIXED")
        a = scoring.score_programme(soon, PROFILE, career("cyber_grc"),
                                    as_row(COUNTRIES["IE"]), None, WEIGHTS, today)
        b = scoring.score_programme(far, PROFILE, career("cyber_grc"),
                                    as_row(COUNTRIES["IE"]), None, WEIGHTS, today)
        self.assertGreater(a["priority_score"], b["priority_score"])


class TestROI(unittest.TestCase):
    """SPEC §56 'ROI' + §14."""

    def test_expensive_with_weak_outcome_is_penalised(self):
        p = prog(tuition_eur=60000, governance_relevance=2, risk_relevance=2,
                 ai_relevance=2, finserv_relevance=2)
        s = score(p)
        rules = [x["rule"] for x in s["penalties"]]
        self.assertIn("extreme_cost_weak_roi", rules)

    def test_cheaper_programme_beats_identical_expensive_one(self):
        cheap = score(prog(tuition_eur=12000))
        dear = score(prog(tuition_eur=45000))
        self.assertGreater(cheap["overall"], dear["overall"])

    def test_roi_reports_unavailable_rather_than_guessing(self):
        p = prog(tuition_eur=None)
        s = score(p)
        self.assertIsNone(s["roi_ratio"])
        self.assertIn("NOT CALCULABLE", s["roi_assumptions"]["result"])

    def test_salary_basis_is_never_invented(self):
        p = prog()
        s = score(p)
        basis = s["roi_assumptions"]["expected_salary_basis"]
        self.assertTrue("FLOOR PROXY" in str(basis) or "programme-reported" in str(basis)
                        or "DATA NOT VERIFIED" in str(basis),
                        "salary basis must always disclose its provenance: %r" % (basis,))


class TestCountry(unittest.TestCase):
    """SPEC §56 'Country': visa-unfriendly destinations score lower."""

    def test_visa_unfriendly_scores_lower(self):
        ie, _ = scoring.country_score(as_row(COUNTRIES["IE"]), WEIGHTS)
        ch, _ = scoring.country_score(as_row(COUNTRIES["CH"]), WEIGHTS)
        us, _ = scoring.country_score(as_row(COUNTRIES["US"]), WEIGHTS)
        self.assertGreater(ie, ch)
        self.assertGreater(ie, us)

    def test_red_flag_country_penalised(self):
        s = score(prog(country_code="US"), cc="US")
        rules = [x["rule"] for x in s["penalties"]]
        self.assertIn("poor_visa_situation", rules)

    def test_india_baseline_present(self):
        """The do-nothing baseline must exist, or every foreign option looks
        good by default."""
        self.assertIn("IN", COUNTRIES)


class TestRecommendationBands(unittest.TestCase):
    """SPEC §17: exactly one band, and rejects dominate."""

    def test_reject_beats_high_score(self):
        p = prog(name="MSc AI Engineering", cs_prereq=1,
                 governance_relevance=10, risk_relevance=10, ai_relevance=10,
                 finserv_relevance=10)
        s = score(p)
        self.assertTrue(s["recommendation"].startswith("REJECT"))

    def test_every_programme_gets_exactly_one_band(self):
        valid = {r[0] for r in scoring.RECOMMENDATIONS}
        for p in (prog(), prog(cs_prereq=1), prog(tuition_eur=None),
                  prog(governance_relevance=1, risk_relevance=1,
                       ai_relevance=1, finserv_relevance=1)):
            self.assertIn(score(p)["recommendation"], valid)


class TestJobMarket(unittest.TestCase):
    """SPEC §31: measured evidence, and honest about sample size."""

    def test_postings_load_and_match(self):
        postings = jobmarket.load_postings()
        if not postings:
            self.skipTest("no postings store available")
        block = jobmarket.analyse_career(career("cyber_grc"), postings, 12)
        self.assertGreater(block["posting_count"], 0)
        self.assertIn("measured", block)

    def test_small_sample_is_not_marked_measured(self):
        block = jobmarket.analyse_career(career("cyber_grc"), {}, 12)
        self.assertFalse(block["measured"])
        self.assertEqual(block["posting_count"], 0)


class TestScoreIntegrity(unittest.TestCase):
    def test_overall_weights_sum_to_one(self):
        total = sum(v for k, v in WEIGHTS["overall"].items() if not k.startswith("_"))
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_scores_stay_in_range(self):
        for p in (prog(), prog(cs_prereq=1), prog(tuition_eur=90000)):
            s = score(p)
            self.assertGreaterEqual(s["overall"], 0.0)
            self.assertLessEqual(s["overall"], 100.0)
            self.assertGreaterEqual(s["personal_fit"], 0.0)
            self.assertLessEqual(s["personal_fit"], 100.0)

    def test_seed_corpus_negative_controls_are_rejected(self):
        """The deliberate traps in the seed corpus must all be caught."""
        seed = load.load_json("programmes.seed.json", os.path.join(ROOT, "data"))
        by_id = {p["id"]: p for p in seed["programmes"]}
        for pid in ("ie-ucc-cybersecurity", "gb-edin-cyber-privacy-trust"):
            p = dict(by_id[pid])
            for k, v in list(p.items()):
                if isinstance(v, (list, dict)):
                    p[k] = db.js(v)
            s = scoring.score_programme(
                p, PROFILE, career("cyber_grc"),
                as_row(COUNTRIES[p["country_code"]]), None, WEIGHTS)
            self.assertTrue(s["recommendation"].startswith("REJECT"),
                            "%s should be rejected, got %s" % (pid, s["recommendation"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
