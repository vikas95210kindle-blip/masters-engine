#!/usr/bin/env python3
"""Daily run — SPEC §18, §34, §35, §48, §54.

    python3 run_daily.py              # full run: load, score, report, dashboard
    python3 run_daily.py --weekly     # also write the weekly strategic report
    python3 run_daily.py --top 25     # change the size of the headline table
    python3 run_daily.py --no-report  # score only

Stdlib only. Safe to run repeatedly; loading is idempotent and change
detection compares against what is already stored.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import dashboard, db, jobmarket, load, report, scoring

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(ROOT, "reports")


def previous_scores(conn, run_id):
    """Latest score per programme from any earlier run (§34.3)."""
    rows = db.fetch_all(conn, """
        SELECT ps.programme_id, ps.overall, ps.run_id
        FROM programme_scores ps
        WHERE ps.run_id != ?
        ORDER BY ps.computed_at DESC
    """, (run_id,))
    out = {}
    for r in rows:
        out.setdefault(r["programme_id"], r["overall"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--kind", default="daily")
    args = ap.parse_args()

    conn = db.init(db.connect())
    run_id = db.new_run_id(args.kind)
    conn.execute("INSERT INTO runs (run_id, started_at, kind) VALUES (?,?,?)",
                 (run_id, db.now(), args.kind))

    print("run %s" % run_id)

    # ---- load -------------------------------------------------------------
    known_before = {r["id"] for r in db.fetch_all(conn, "SELECT id FROM programmes")}
    loaded = load.load_all(conn, run_id)
    profile = loaded["profile"]
    careers_cfg = loaded["careers"]
    weights = load.load_json("weights.json")
    print("loaded %d programmes, %d countries, %d careers"
          % (loaded["programme_count"], len(loaded["countries"]),
             len(careers_cfg["careers"])))

    programmes = db.fetch_all(conn, "SELECT * FROM programmes WHERE active = 1")
    new_programmes = [p["name"] for p in programmes if p["id"] not in known_before]

    countries = {c["code"]: c for c in db.fetch_all(conn, "SELECT * FROM countries")}
    unis = {u["id"]: u for u in db.fetch_all(conn, "SELECT * FROM universities")}

    # ---- job market (§31) -------------------------------------------------
    jm = jobmarket.run(conn, careers_cfg, run_id)
    print("job market: %d postings analysed" % jm["postings_loaded"])

    careers_by_id = {}
    careers_ranked = []
    for c in careers_cfg["careers"]:
        ev = jm["by_id"].get(c["id"], {})
        enriched = jobmarket.apply_overrides(c, ev)
        cs, cbreak = scoring.career_score(enriched, weights)
        money, purpose, balanced, _ = scoring.money_purpose(enriched, weights, profile)
        enriched["career_score"] = cs
        careers_by_id[c["id"]] = enriched
        careers_ranked.append({
            "career_id": c["id"], "career_name": c["name"], "career_score": cs,
            "money_score": money, "purpose_score": purpose, "balanced_score": balanced,
            "rationale": c.get("rationale", ""), "dimensions": enriched["dimensions"],
            "provenance": enriched["_provenance"],
        })
        db.upsert(conn, "career_scores", {
            "career_id": c["id"], "run_id": run_id, "career_score": cs,
            "money_score": money, "purpose_score": purpose, "balanced_score": balanced,
            "measured": db.js(enriched["_provenance"]),
            "posting_count": ev.get("posting_count", 0),
            "evidence": db.js(ev), "computed_at": db.now(),
        }, ("career_id", "run_id"))
    careers_ranked.sort(key=lambda x: -x["career_score"])

    # ---- country scores (§13) --------------------------------------------
    countries_ranked = []
    for code, c in countries.items():
        cs, _ = scoring.country_score(c, weights)
        conn.execute("UPDATE countries SET country_score = ? WHERE code = ?", (cs, code))
        c["country_score"] = cs
        countries_ranked.append(c)
    countries_ranked.sort(key=lambda x: -x["country_score"])

    # ---- score programmes -------------------------------------------------
    prev = previous_scores(conn, run_id)
    ranked = []
    for p in programmes:
        targets = db.uj(p.get("target_careers"), []) or []
        career = None
        for t in targets:
            cand = careers_by_id.get(t)
            if cand and (career is None or cand["career_score"] > career["career_score"]):
                career = cand
        country = countries.get(p["country_code"])
        uni = unis.get(p["university_id"])

        s = scoring.score_programme(p, profile, career, country, uni, weights)
        why = report.why_for_you(p, profile, s, career)
        gaps = report.gap_analysis(p, profile, career)
        outcomes = report.career_outcomes(p, career, jm["by_id"])

        db.upsert(conn, "programme_scores", {
            "programme_id": p["id"], "run_id": run_id,
            "overall": s["overall"], "career_value": s["career_value"],
            "personal_fit": s["personal_fit"], "admission_band": s["admission_band"],
            "admission_points": s["admission_points"],
            "admission_reason": s["admission_reason"],
            "salary_potential": s["salary_potential"], "job_security": s["job_security"],
            "ai_resilience": s["ai_resilience"], "country_score": s["country_score"],
            "roi_score": s["roi_score"], "roi_ratio": s["roi_ratio"],
            "university_quality": s["university_quality"],
            "money_score": s["money_score"], "purpose_score": s["purpose_score"],
            "balanced_score": s["balanced_score"], "priority_score": s["priority_score"],
            "penalties": db.js(s["penalties"]), "recommendation": s["recommendation"],
            "why_for_you": why, "risks": p.get("notes"), "gaps": db.js(gaps),
            "breakdown": db.js(s["breakdown"]), "computed_at": db.now(),
        }, ("programme_id", "run_id"))

        ranked.append({"programme": p, "scored": s, "career": career,
                       "country": country, "university": uni, "why": why,
                       "gaps": gaps, "outcomes": outcomes,
                       "salary": report.salary_projection(country, career, s),
                       "should_apply": report.should_i_apply(s, p)})

    ranked.sort(key=lambda r: -r["scored"]["overall"])

    score_changes = []
    for r in ranked:
        pid = r["programme"]["id"]
        if pid in prev and abs(prev[pid] - r["scored"]["overall"]) >= 0.1:
            score_changes.append({"name": r["programme"]["name"],
                                  "old": prev[pid], "new": r["scored"]["overall"]})

    # ---- deadline alerts (§24) -------------------------------------------
    for r in ranked:
        s = r["scored"]
        if s["deadline_days"] is not None and 0 <= s["deadline_days"] <= 30 \
                and not s["recommendation"].startswith(("REJECT", "DO NOT")):
            db.add_alert(conn, run_id,
                         "CRITICAL" if s["deadline_days"] <= 7 else "URGENT",
                         "DEADLINE", r["programme"]["id"],
                         "%s closes in %d days (%s)"
                         % (r["programme"]["name"], s["deadline_days"], s["recommendation"]))

    # ---- §33 challenges, §32 arbitrage ------------------------------------
    challenges = jobmarket.challenge(careers_cfg, jm["by_id"], careers_ranked)
    arb = jobmarket.arbitrage(careers_cfg, jm["by_id"], profile)

    # ---- §34.9 today's three actions --------------------------------------
    applyable = [r for r in ranked
                 if r["scored"]["recommendation"] in ("APPLY NOW", "STRONG APPLY")]
    by_priority = sorted(applyable, key=lambda r: -r["scored"]["priority_score"])
    actions = []
    if by_priority:
        top = by_priority[0]
        actions.append("Start the application for **%s** (%s) — priority score %.1f, %s."
                       % (top["programme"]["name"],
                          (top["university"] or {}).get("name", ""),
                          top["scored"]["priority_score"],
                          top["scored"]["deadline_status"]))
    unverified = [r for r in ranked[:8] if r["programme"].get("tuition_eur") is None]
    if unverified:
        actions.append("Verify tuition for **%s** — it is in the top 8 but its ROI "
                       "cannot be computed without a fee figure."
                       % unverified[0]["programme"]["name"])
    actions.append("Book the IAPP AIGP exam for February 2027 — it has no prerequisites "
                   "and is the cheapest credential that closes the largest gap.")
    actions = actions[:3]

    top5 = by_priority[:5] or ranked[:5]

    ctx = {
        "run_id": run_id, "ranked": ranked, "profile": profile,
        "jobmarket": jm, "careers_ranked": careers_ranked,
        "countries_ranked": countries_ranked, "challenges": challenges,
        "arbitrage": arb, "actions": actions, "top5": top5,
        "new_programmes": new_programmes, "score_changes": score_changes,
        "changes": loaded["changes"], "weights": weights, "top_n": args.top,
    }

    conn.execute("UPDATE runs SET finished_at = ?, programmes_scored = ? WHERE run_id = ?",
                 (db.now(), len(ranked), run_id))
    conn.commit()

    if not args.no_report:
        os.makedirs(REPORTS, exist_ok=True)
        md = report.daily_report(ctx)
        daily_path = os.path.join(REPORTS, "daily-%s.md" % db.today())
        with open(daily_path, "w", encoding="utf-8") as fh:
            fh.write(md)
        with open(os.path.join(ROOT, "LATEST-REPORT.md"), "w", encoding="utf-8") as fh:
            fh.write(md)
        db.upsert(conn, "reports", {"run_id": run_id, "kind": "daily",
                                    "path": daily_path, "generated_at": db.now()},
                  ("run_id", "kind"))
        print("wrote %s" % daily_path)

        if args.weekly:
            wk = report.weekly_report(ctx)
            wpath = os.path.join(REPORTS, "weekly-%s.md" % db.today())
            with open(wpath, "w", encoding="utf-8") as fh:
                fh.write(wk)
            db.upsert(conn, "reports", {"run_id": run_id, "kind": "weekly",
                                        "path": wpath, "generated_at": db.now()},
                      ("run_id", "kind"))
            print("wrote %s" % wpath)

        dashboard.build(ctx, os.path.join(ROOT, "site"))
        print("wrote site/index.html")

    conn.commit()

    # ---- console summary --------------------------------------------------
    print("")
    print("%-3s %-46s %-4s %7s %7s %-13s %s" %
          ("#", "PROGRAMME", "CC", "OVERALL", "FIT", "ADMISSION", "RECOMMENDATION"))
    for i, r in enumerate(ranked[:args.top], 1):
        s = r["scored"]
        print("%-3d %-46s %-4s %7.1f %7.1f %-13s %s"
              % (i, r["programme"]["name"][:46], r["programme"]["country_code"],
                 s["overall"], s["personal_fit"], s["admission_band"], s["recommendation"]))
    print("")
    for f in challenges:
        print("[%s] %s" % (f["severity"], f["headline"]))
    conn.close()


if __name__ == "__main__":
    main()
