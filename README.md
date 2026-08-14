# Global Master's Intelligence & Career Matching Engine

Personalised master's + career intelligence for a **banking → AI governance / technology
risk** pivot, **non-coding track**, Indian national, targeting a **September 2027** intake.

Start with **[LATEST-REPORT.md](LATEST-REPORT.md)**. Open `site/index.html` for the dashboard.

```bash
python3 run_daily.py                # load, score, write report + dashboard
python3 run_daily.py --weekly       # also write the weekly strategic report
python3 run_daily.py --top 25       # size of the headline table
python3 tests/test_engine.py        # 30 tests, §56
python3 serve.py                    # dashboard on http://127.0.0.1:8765
```

---

## What it actually does

It answers one question every day: *what is the highest-probability master's decision
available right now that maximises long-term income, security, international mobility and
career impact, without becoming a programmer?*

It is **not** a course search engine. Rankings are driven by the profile in
`config/profile.json`, by verified programme records, and by **1,438 real job postings**
measured from `../ai-governance-career/data/postings.json`.

---

## Stack deviation from the specification

The spec asked for PostgreSQL + Next.js + FastAPI. This Mac runs **Python 3.9.6 with no
third-party packages and no Node toolchain**, so that stack is not buildable here. Built
instead:

| Spec | Built | Why |
|---|---|---|
| PostgreSQL | SQLite (`data/masters.db`) | Portable SQL only — no SERIAL, no JSONB, no arrays. Porting means changing `db.connect()` and three type names. |
| Next.js + Tailwind | Generated self-contained HTML (`site/index.html`) | No build step, no CDN. Opens by double-click. |
| FastAPI | `run_daily.py` + `serve.py` (stdlib `http.server`) | Same module boundaries as §37. |

Module boundaries follow §37 exactly, so the port is a swap rather than a rewrite.

---

## Layout

```
config/profile.json      §1  the applicant — edit this, rankings change
config/weights.json      §16 every weight, penalty and threshold, tunable
config/careers.json      §4  18 career tracks + §32 arbitrage combinations
config/countries.json    §13 20 countries: ordinal scores + §23 visa facts
data/programmes.seed.json     verified programme corpus (§57)
engine/db.py             §8/§36 schema
engine/eligibility.py    §9 eligibility · §10 coding filter · §15 admission
engine/scoring.py        §11-§17, §47, §53
engine/jobmarket.py      §31 feedback loop · §32 arbitrage · §33 challenge
engine/report.py         §20-§22, §27, §34, §35, §49, §54
engine/dashboard.py      §19, §43-§46
tests/test_engine.py     §56
```

---

## The coding filter (§10) — the part that matters most

This enforces the single non-negotiable constraint, so it is deliberately
**evidence-driven, not title-driven** (§57 forbids judging by name).

Signals are matched against name, department, prerequisites, curriculum and graduate
outcomes. Governance framing pulls the score *down*; engineering graduate outcomes push it
*up* hard. Every band carries the exact strings that produced it — a wrong call is
traceable to its trigger.

Two rules make it fail safe:

- A **verified** manual reading beats the rubric in both directions.
- An **unverified** manual reading acts as a **floor only**. If a human judged a programme
  more code-heavy than the regexes can see, the regexes cannot argue it back down.

That second rule is what catches Trinity's MSc Financial Risk Management: the rubric reads
it as governance-adjacent, but "credit risk modelling" is quantitative work. It is rejected.

Three deliberate **negative controls** live in the corpus and are asserted in the tests:

| Programme | Must be rejected because |
|---|---|
| UCC MSc Cybersecurity | cryptography / network / hardware security, €28,000 |
| Edinburgh Cyber Security, Privacy and Trust | requires a CS-family degree he does not hold |
| Trinity MSc Financial Risk Management | quantitative risk modelling wearing a governance title |

If any of these ever reaches a shortlist, the filter is broken.

---

## Data honesty rules (§39, §40, §57)

The hardest constraint in this build is not the scoring — it is refusing to invent facts.

- Programme facts are read off **official university pages**, with `last_verified` dates.
- Fields not found are **null**, rendered `DATA NOT VERIFIED`. They are never estimated
  into place. Six programmes currently have unverified tuition; their ROI reports as *not
  calculable* rather than guessing.
- **ROI never invents a salary.** With no verified graduate salary it falls back to the
  country's skilled-route salary threshold, labelled explicitly as a **floor proxy** — a
  real sourced legal minimum, not a market estimate.
- **Salary projections are anchored on legal thresholds, not market data**, and say so in
  the output.
- Country ordinal sub-scores are **editorial judgements**, labelled ESTIMATED. Visa
  thresholds are facts and carry their own confidence; several were carried over from
  earlier research and are flagged as **not re-verified**.
- Job-market percentages are **measured** from real postings, with sample sizes shown. A
  track with too few postings is not marked measured.

---

## What the first run found

**Rankings** — University of Galway MSc Cybersecurity Risk Management (79.6), TU Dublin
MSc Cybersecurity Management (78.4), Ulster MSc Ethical and Responsible AI (75.5).

**The §33 challenge fired against the seed hypothesis.** Cybersecurity GRC outscores
AI Governance – Financial Services (81.7 vs 80.7) and shows **189 postings with coding
demanded in only 2.8%** — the cleanest non-coding demand measured. AI Governance – FS shows
29.3%.

**Model Risk Governance is a confirmed trap**: 57% of its postings demand coding. The
validation-vs-governance distinction is real and measurable.

**A master's is named in only 7% of postings that state a degree** (sample 269). This is
the January 2027 decision input: the degree is an **immigration instrument** — permit
threshold plus stay-back — not an employer requirement. That is a valid reason to buy one,
but a different one, and it must be judged on that basis.

**Online programmes carry zero immigration value.** The IOB/UCD MSc in Compliance has the
highest personal fit in the corpus (83.0) and the lowest cost (€14,060), but confers no
student visa and no Stamp 1G. It takes the `poor_visa_situation` penalty and ranks 8th. It
is a **Track A** credential, not a route to Europe.

---

## Known limits

- **14 programmes, not 25.** §58 asked for a top 25. Padding to 25 would have meant
  inventing records, so the corpus is 14 verified entries. Extend `programmes.seed.json`.
- **Discovery is not yet automated.** Programmes were found and verified by hand this run.
  Several official sites (Tilburg, Ulster, Maastricht) block automated fetching with HTTP
  403 — those records are explicit placeholders and are marked as such.
- **Visa figures need re-verification.** Ireland's €40,904/€68,911 split, the UK Graduate
  Route duration and the Dutch reduced graduate threshold are all decisive and all carried
  over rather than freshly checked.
- Change detection (§41) is wired and stores `source_hash`/`last_checked`, but nothing
  re-fetches pages yet, so it only fires on edits to the seed file.

---

## Related

`../ai-governance-career` — the job-market scanner this consumes, plus the two-track
strategy and the January 2027 decision point.
