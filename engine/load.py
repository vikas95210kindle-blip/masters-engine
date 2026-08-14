"""Load config + seed data into SQLite, with change detection (§41).

Loading is idempotent. On every run each programme's material fields are
compared against what is already stored; differences are written to `changes`
and raised as alerts, which is what feeds §34.3 "ranking changes" and the
CHANGE DETECTED banner.
"""

import json
import os

from . import db

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config")
DATA = os.path.join(ROOT, "data")

# Fields whose change is materially interesting to the applicant (§41).
WATCHED = ["tuition_eur", "application_deadline", "deadline_type", "ielts",
           "academic_prereq", "duration_months", "coding_intensity",
           "next_intake", "scholarship_available", "post_study_work_months",
           "study_mode", "official_url"]

PROGRAMME_COLUMNS = None  # filled lazily from the table definition


def load_json(name, folder=CONFIG):
    with open(os.path.join(folder, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def load_profile(conn):
    p = load_json("profile.json")
    db.upsert(conn, "profiles", {
        "profile_id": p["profile_id"],
        "version": p.get("profile_version", 1),
        "payload": db.js(p),
        "loaded_at": db.now(),
    }, "profile_id")
    conn.commit()
    return p


def load_countries(conn):
    cfg = load_json("countries.json")
    for c in cfg["countries"]:
        db.upsert(conn, "countries", {
            "code": c["code"], "name": c["name"], "tier": c.get("tier"),
            "currency": c.get("currency"),
            "scores": db.js(c.get("scores")),
            "scores_conf": c.get("scores_confidence"),
            "rationale": c.get("scores_rationale"),
            "visa": db.js(c.get("visa")),
            "updated_at": db.now(),
        }, "code")
    conn.commit()
    return {c["code"]: c for c in cfg["countries"]}


def load_careers(conn):
    cfg = load_json("careers.json")
    for c in cfg["careers"]:
        db.upsert(conn, "career_paths", {
            "id": c["id"], "name": c["name"], "tier": c.get("tier"),
            "seed_rank": c.get("seed_rank"),
            "keywords": db.js(c.get("keywords")),
            "context_keywords": db.js(c.get("context_keywords")),
            "banking_adjacency": c.get("banking_adjacency"),
            "coding_expected": c.get("coding_expected"),
            "dimensions": db.js(c.get("dimensions")),
            "purpose_dims": db.js(c.get("purpose_dimensions")),
            "confidence": c.get("confidence"),
            "rationale": c.get("rationale"),
            "risks": db.js(c.get("risks")),
            "updated_at": db.now(),
        }, "id")
    conn.commit()
    return cfg


def load_programmes(conn, run_id):
    """Insert/update programmes. Returns (count, changes_detected)."""
    seed = load_json("programmes.seed.json", DATA)
    cols = set(_columns(conn, "programmes"))
    changed = []

    for u in seed.get("universities", []):
        db.upsert(conn, "universities", {
            "id": u["id"], "name": u["name"], "country_code": u.get("country_code"),
            "city": u.get("city"), "qs_rank": u.get("qs_rank"),
            "sources": db.js({"note": u.get("source")}),
            "updated_at": db.now(),
        }, "id")

    for p in seed["programmes"]:
        existing = db.fetch_one(
            conn, "SELECT * FROM programmes WHERE id = ?", (p["id"],))

        row = {}
        for k, v in p.items():
            if k not in cols:
                continue
            if isinstance(v, (list, dict)):
                row[k] = db.js(v)
            else:
                row[k] = v
        row["id"] = p["id"]
        row["last_checked"] = db.now()
        row["active"] = 1

        if existing:
            diffs = []
            for f in WATCHED:
                old, new = existing.get(f), row.get(f)
                if old != new and new is not None:
                    diffs.append((f, old, new))
            if diffs:
                row["last_changed"] = db.now()
                for f, old, new in diffs:
                    db.log_change(conn, run_id, "programme", p["id"], f, old, new)
                    changed.append({"programme": p["name"], "field": f,
                                    "old": old, "new": new})
                    db.add_alert(conn, run_id, "INFO", "CHANGE DETECTED", p["id"],
                                 "%s: %s changed from %s to %s"
                                 % (p["name"], f, old, new))
            else:
                row["last_changed"] = existing.get("last_changed")
        else:
            row["last_changed"] = db.now()

        db.upsert(conn, "programmes", row, "id")

        for url in (p.get("evidence_urls") or []):
            db.upsert(conn, "sources", {
                "url": url, "source_type": "official university",
                "tier": 1, "title": p["name"],
                "first_seen": db.now(), "last_checked": db.now(),
            }, "url")

    conn.commit()
    return len(seed["programmes"]), changed


def load_all(conn, run_id):
    profile = load_profile(conn)
    countries = load_countries(conn)
    careers = load_careers(conn)
    n, changes = load_programmes(conn, run_id)
    return {"profile": profile, "countries": countries, "careers": careers,
            "programme_count": n, "changes": changes}
