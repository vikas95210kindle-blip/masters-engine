"""SQLite store — SPEC §8 (data model) and §36 (tables).

The spec asks for PostgreSQL. This machine has no Postgres and no drivers, so
the schema is written in portable SQL: no SERIAL, no JSONB, no arrays. JSON
lives in TEXT columns and is round-tripped through the helpers below. Porting
to Postgres means changing the connect() function and the three type names.
"""

import json
import os
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB_PATH = os.path.join(ROOT, "data", "masters.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- profile
CREATE TABLE IF NOT EXISTS profiles (
    profile_id      TEXT PRIMARY KEY,
    version         INTEGER NOT NULL,
    payload         TEXT NOT NULL,          -- full profile.json
    loaded_at       TEXT NOT NULL
);

-- ------------------------------------------------------------- reference
CREATE TABLE IF NOT EXISTS countries (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    tier            TEXT,
    currency        TEXT,
    scores          TEXT,                   -- json: 15 sub-scores
    scores_conf     TEXT,
    rationale       TEXT,
    visa            TEXT,                   -- json: §23 block
    country_score   REAL,                   -- computed §13
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS career_paths (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    tier            INTEGER,
    seed_rank       INTEGER,
    keywords        TEXT,
    context_keywords TEXT,
    banking_adjacency INTEGER,
    coding_expected INTEGER,
    dimensions      TEXT,                   -- json §11 inputs
    purpose_dims    TEXT,                   -- json §53 inputs
    confidence      TEXT,
    rationale       TEXT,
    risks           TEXT,
    updated_at      TEXT
);

-- Recomputed every run from measured job-market evidence (§31).
CREATE TABLE IF NOT EXISTS career_scores (
    career_id       TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    career_score    REAL,
    money_score     REAL,
    purpose_score   REAL,
    balanced_score  REAL,
    measured        TEXT,                   -- json: which dims came from real postings
    posting_count   INTEGER,
    evidence        TEXT,                   -- json §31 block
    computed_at     TEXT,
    PRIMARY KEY (career_id, run_id),
    FOREIGN KEY (career_id) REFERENCES career_paths(id)
);

CREATE TABLE IF NOT EXISTS universities (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country_code    TEXT,
    city            TEXT,
    qs_rank         INTEGER,
    the_rank        INTEGER,
    subject_rank    TEXT,
    reputation      TEXT,
    quality_score   REAL,
    sources         TEXT,
    updated_at      TEXT,
    FOREIGN KEY (country_code) REFERENCES countries(code)
);

-- ------------------------------------------------------------- programmes
CREATE TABLE IF NOT EXISTS programmes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    university_id   TEXT,
    country_code    TEXT,
    city            TEXT,
    degree          TEXT,
    department      TEXT,
    url             TEXT,
    official_url    TEXT,
    duration_months INTEGER,
    study_mode      TEXT,
    language        TEXT,
    tuition_amount  REAL,
    tuition_currency TEXT,
    tuition_eur     REAL,
    tuition_note    TEXT,
    living_cost_eur REAL,
    scholarship_available INTEGER,
    application_deadline TEXT,
    deadline_type   TEXT,                   -- ROLLING / FIXED / UNKNOWN
    next_intake     TEXT,
    application_fee TEXT,
    ielts           TEXT,
    toefl           TEXT,
    gre_required    INTEGER,
    gmat_required   INTEGER,
    academic_prereq TEXT,
    programming_prereq INTEGER,             -- 0/1/null
    math_prereq     INTEGER,
    cs_prereq       INTEGER,
    work_exp_requirement TEXT,              -- irrelevant/useful/preferred/mandatory
    age_restrictions TEXT,
    intl_eligible   INTEGER,
    visa_route      TEXT,
    post_study_work_months INTEGER,
    pr_pathway      TEXT,
    employment_rate TEXT,
    grad_outcomes   TEXT,
    median_salary   TEXT,
    career_outcomes TEXT,
    industry_links  TEXT,
    internship      TEXT,
    employer_links  TEXT,
    ranking         TEXT,
    subject_ranking TEXT,
    reputation      TEXT,
    ai_relevance    INTEGER,
    governance_relevance INTEGER,
    cyber_relevance INTEGER,
    risk_relevance  INTEGER,
    finserv_relevance INTEGER,
    coding_intensity INTEGER,               -- §10, 0-5
    coding_evidence TEXT,
    target_careers  TEXT,                   -- json list of career_path ids
    intl_org_pathway INTEGER,               -- §52
    curriculum      TEXT,                   -- json list of module names
    confidence      TEXT,                   -- json per-field confidence map §40
    evidence_urls   TEXT,                   -- json list
    last_verified   TEXT,
    source_hash     TEXT,
    last_checked    TEXT,
    last_changed    TEXT,
    notes           TEXT,
    active          INTEGER DEFAULT 1,
    FOREIGN KEY (university_id) REFERENCES universities(id),
    FOREIGN KEY (country_code) REFERENCES countries(code)
);

CREATE INDEX IF NOT EXISTS idx_prog_country ON programmes(country_code);
CREATE INDEX IF NOT EXISTS idx_prog_deadline ON programmes(application_deadline);

-- Score history: one row per programme per run, so §34.3 ranking changes work.
CREATE TABLE IF NOT EXISTS programme_scores (
    programme_id    TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    overall         REAL,
    career_value    REAL,
    personal_fit    REAL,
    admission_band  TEXT,
    admission_points REAL,
    admission_reason TEXT,
    salary_potential REAL,
    job_security    REAL,
    ai_resilience   REAL,
    country_score   REAL,
    roi_score       REAL,
    roi_ratio       REAL,
    university_quality REAL,
    money_score     REAL,
    purpose_score   REAL,
    balanced_score  REAL,
    priority_score  REAL,
    penalties       TEXT,                   -- json list of applied penalties
    recommendation  TEXT,                   -- §17 band
    why_for_you     TEXT,                   -- §20
    risks           TEXT,
    gaps            TEXT,                   -- §27
    breakdown       TEXT,                   -- json full component trace
    computed_at     TEXT,
    PRIMARY KEY (programme_id, run_id),
    FOREIGN KEY (programme_id) REFERENCES programmes(id)
);

CREATE TABLE IF NOT EXISTS scholarships (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    provider        TEXT,
    country_code    TEXT,
    programme_id    TEXT,
    eligibility     TEXT,
    amount          TEXT,
    deadline        TEXT,
    probability     TEXT,
    complexity      TEXT,
    url             TEXT,
    confidence      TEXT,
    last_verified   TEXT
);

-- ------------------------------------------------------- job market (§31)
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    title           TEXT,
    company         TEXT,
    location        TEXT,
    country_code    TEXT,
    posted          TEXT,
    url             TEXT,
    description     TEXT,
    career_ids      TEXT,                   -- json: matched career paths
    coding_required INTEGER,
    sponsorship     TEXT,
    degree_required TEXT,
    years_required  INTEGER,
    salary_raw      TEXT,
    source          TEXT,
    imported_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country_code);

-- --------------------------------------------------- tracking + provenance
CREATE TABLE IF NOT EXISTS applications (
    programme_id    TEXT PRIMARY KEY,
    status          TEXT NOT NULL,          -- §25 status enum
    deadline        TEXT,
    application_fee TEXT,
    documents       TEXT,                   -- json checklist
    sop_status      TEXT,
    cv_status       TEXT,
    lor_status      TEXT,
    transcript_status TEXT,
    english_test    TEXT,
    scholarship     TEXT,
    visa            TEXT,
    decision        TEXT,
    notes           TEXT,
    updated_at      TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(id)
);

CREATE TABLE IF NOT EXISTS sources (
    url             TEXT PRIMARY KEY,
    source_type     TEXT,                   -- §39 tier
    tier            INTEGER,
    title           TEXT,
    first_seen      TEXT,
    last_checked    TEXT
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    url             TEXT NOT NULL,
    checked_at      TEXT NOT NULL,
    content_hash    TEXT,
    status          INTEGER,
    bytes           INTEGER,
    PRIMARY KEY (url, checked_at)
);

CREATE TABLE IF NOT EXISTS changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT,
    entity_type     TEXT,                   -- programme / country / career
    entity_id       TEXT,
    field           TEXT,
    old_value       TEXT,
    new_value       TEXT,
    detected_at     TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT,
    severity        TEXT,                   -- CRITICAL / URGENT / INFO
    kind            TEXT,
    entity_id       TEXT,
    message         TEXT,
    created_at      TEXT,
    acknowledged    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT,
    finished_at     TEXT,
    kind            TEXT,                   -- daily / weekly / manual
    programmes_scored INTEGER,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    run_id          TEXT NOT NULL,
    kind            TEXT NOT NULL,          -- daily / weekly
    path            TEXT,
    generated_at    TEXT,
    PRIMARY KEY (run_id, kind)
);
"""


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def today():
    return time.strftime("%Y-%m-%d")


def new_run_id(kind="daily"):
    return "%s-%s" % (kind, time.strftime("%Y%m%d-%H%M%S"))


# -- json column helpers ----------------------------------------------------

def js(value):
    """Serialise a Python value for a TEXT column."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def uj(text, default=None):
    """Deserialise a TEXT column, tolerating nulls and legacy plain strings."""
    if text is None or text == "":
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def upsert(conn, table, row, pk):
    """Insert or replace a dict row. Keys must be real columns."""
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    sql = "INSERT OR REPLACE INTO %s (%s) VALUES (%s)" % (
        table, ",".join(cols), placeholders)
    conn.execute(sql, [row[c] for c in cols])


def fetch_all(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fetch_one(conn, sql, params=()):
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def log_change(conn, run_id, entity_type, entity_id, field, old, new):
    conn.execute(
        "INSERT INTO changes (run_id, entity_type, entity_id, field, old_value,"
        " new_value, detected_at) VALUES (?,?,?,?,?,?,?)",
        (run_id, entity_type, entity_id, field, str(old), str(new), now()))


def add_alert(conn, run_id, severity, kind, entity_id, message):
    conn.execute(
        "INSERT INTO alerts (run_id, severity, kind, entity_id, message,"
        " created_at) VALUES (?,?,?,?,?,?)",
        (run_id, severity, kind, entity_id, message, now()))
