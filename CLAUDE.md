# masters-engine — working directory

Personalised master's + career intelligence engine. Read `README.md` first, then
`LATEST-REPORT.md`.

## The one rule

**Never invent a fact.** Not a tuition figure, not a deadline, not a salary, not a visa
rule, not an employment rate. If it is not on an official page, it is `null` and renders as
`DATA NOT VERIFIED`. A missing number is useful; a plausible wrong number costs real money
and a year of his life.

Corollary: never infer that a programme is non-coding from its title (§57). The coding
filter reads curriculum, prerequisites and graduate outcomes, and records the exact strings
that produced each band.

## The constraint that must never regress

The non-coding constraint is deliberate and is not up for re-litigation. `tests/test_engine.py`
protects it. Three negative controls (UCC Cybersecurity, Edinburgh Cyber Security Privacy &
Trust, Trinity Financial Risk Management) must always be rejected. Run the tests after any
change to `eligibility.py` or `scoring.py`.

An unverified manual `coding_intensity` is a **floor, not a ceiling** — the rubric may
raise it but never lower it. Do not "simplify" that away.

## Editing rules

- Profile changes go in `config/profile.json`. Never edit scoring code to fix a profile
  problem.
- Weights, penalties and thresholds go in `config/weights.json`. They are all configurable
  by design (§16) — tune there, not in `scoring.py`.
- New programmes go in `data/programmes.seed.json` with `evidence_urls`, `last_verified`
  and a per-field `confidence` map. A record without sources should not be added.
- Ordinal 0-10 scores are editorial judgements and must stay labelled ESTIMATED. Never
  promote one into the `visa` fact block.

## What the engine is for

He is buying a master's substantially as an **immigration instrument** — Ireland's Critical
Skills permit threshold is far lower with a relevant degree, and his B.Tech in Biotechnology
almost certainly does not count as relevant. Measured evidence supports this framing: a
master's is named in only ~7% of real postings that state a degree requirement.

So: score programmes on whether they deliver a **visa route plus labour-market presence**,
not only on curriculum. Online and part-time-executive programmes confer neither and take
the `poor_visa_situation` penalty, however good their content. That is why the IOB MSc in
Compliance has the highest personal fit in the corpus and still ranks 8th.

## Do not

- Do not chase coding-heavy programmes or careers when they surface — that constraint is
  the whole strategy.
- Do not let university ranking dominate. §30 is explicit: career fit beats ranking, and
  `university_quality` is compressed to 55-92 so it cannot swing the result.
- Do not present the §33 challenges as reassurance. Their job is to attack the seed
  hypothesis. Cyber GRC currently outscores AI Governance – FS; say so plainly.
- Do not pad the corpus to hit a target count.

## Related

`../ai-governance-career` — `scan.py` collects the postings this engine measures; its
`CLAUDE.md` holds the two-track strategy and the **January 2027** decision date.
