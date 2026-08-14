"""Static dashboard generator — SPEC §19, §43, §44, §45, §46.

Emits a single self-contained HTML file. No framework, no CDN, no build step:
this Mac has no Node toolchain, and a file you can open with a double click has
fewer ways to stop working than a dev server. `serve.py` exists for the cases
where a real origin is wanted.
"""

import html
import json
import os

from . import db


def esc(s):
    return html.escape(str(s if s is not None else ""))


def money(v):
    return "€" + format(int(v), ",") if v else '<span class="unv">DATA NOT VERIFIED</span>'


def conf_badge(conf, field):
    c = (conf or {}).get(field)
    if not c:
        return '<span class="b b-unk">UNKNOWN</span>'
    cls = {"VERIFIED": "b-ver", "PROBABLY CORRECT": "b-prob",
           "ESTIMATED": "b-est", "UNKNOWN": "b-unk"}.get(str(c).split(" -")[0], "b-est")
    return '<span class="b %s">%s</span>' % (cls, esc(str(c).split(" -")[0]))


CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:#0e1116;color:#e6edf3}
a{color:#6cb6ff}
header{padding:26px 30px;border-bottom:1px solid #21262d;background:#161b22}
h1{margin:0;font-size:21px;letter-spacing:-.2px}
.sub{color:#8b949e;font-size:13px;margin-top:6px}
nav{display:flex;gap:2px;padding:0 30px;background:#161b22;border-bottom:1px solid #21262d;
flex-wrap:wrap}
nav button{background:none;border:none;color:#8b949e;padding:12px 15px;cursor:pointer;
font-size:13px;border-bottom:2px solid transparent;font-family:inherit}
nav button:hover{color:#e6edf3}
nav button.on{color:#e6edf3;border-bottom-color:#f78166}
main{padding:26px 30px;max-width:1500px}
section{display:none}section.on{display:block}
h2{font-size:17px;margin:26px 0 12px;font-weight:600}
h3{font-size:15px;margin:20px 0 8px;color:#c9d1d9}
.wrap{overflow-x:auto;border:1px solid #21262d;border-radius:8px;margin-bottom:18px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:900px}
th{background:#161b22;text-align:left;padding:9px 11px;font-weight:600;color:#8b949e;
white-space:nowrap;border-bottom:1px solid #21262d;position:sticky;top:0}
td{padding:9px 11px;border-bottom:1px solid #1c2128;vertical-align:top}
tr:hover td{background:#161b22}
.score{font-weight:700}
.s-hi{color:#3fb950}.s-mid{color:#d29922}.s-lo{color:#f85149}
.b{font-size:10px;padding:2px 6px;border-radius:10px;font-weight:600;white-space:nowrap}
.b-ver{background:#132e1a;color:#3fb950}
.b-prob{background:#132b3d;color:#6cb6ff}
.b-est{background:#3a2d10;color:#d29922}
.b-unk{background:#2d2d2d;color:#8b949e}
.unv{color:#8b949e;font-style:italic;font-size:12px}
.card{border:1px solid #21262d;border-radius:8px;padding:18px;margin-bottom:14px;background:#12171e}
.card h3{margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:12px 0}
.kv{background:#161b22;border-radius:6px;padding:10px 12px}
.kv .k{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.4px}
.kv .v{font-size:16px;font-weight:600;margin-top:3px}
.pill{display:inline-block;padding:3px 9px;border-radius:12px;font-size:11px;font-weight:600}
.p-apply{background:#132e1a;color:#3fb950}
.p-consider{background:#3a2d10;color:#d29922}
.p-backup{background:#3d2a12;color:#e3853d}
.p-no{background:#3d1418;color:#f85149}
.p-reject{background:#2d2d2d;color:#8b949e}
.warn{background:#2b1d12;border-left:3px solid #d29922;padding:12px 15px;border-radius:5px;
margin:10px 0;font-size:13.5px}
.crit{background:#2b1416;border-left:3px solid #f85149;padding:12px 15px;border-radius:5px;
margin:10px 0;font-size:13.5px}
.ok{background:#11221a;border-left:3px solid #3fb950;padding:12px 15px;border-radius:5px;
margin:10px 0;font-size:13.5px}
.filters{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.filters select,.filters input{background:#0d1117;border:1px solid #30363d;color:#e6edf3;
padding:6px 9px;border-radius:6px;font-size:13px;font-family:inherit}
.mut{color:#8b949e;font-size:12.5px}
details{margin:8px 0}
summary{cursor:pointer;color:#8b949e;font-size:13px}
ul{margin:6px 0;padding-left:20px}li{margin:3px 0}
.bar{height:5px;background:#21262d;border-radius:3px;overflow:hidden;margin-top:4px}
.bar i{display:block;height:100%;background:#3fb950}
footer{padding:24px 30px;color:#8b949e;font-size:12px;border-top:1px solid #21262d;margin-top:34px}
"""

JS = """
function tab(id,btn){
  document.querySelectorAll('section').forEach(s=>s.classList.remove('on'));
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('on'));
  document.getElementById(id).classList.add('on');btn.classList.add('on');
}
function filt(){
  var c=document.getElementById('fc').value,r=document.getElementById('fr').value,
      code=document.getElementById('fcode').value,q=document.getElementById('fq').value.toLowerCase();
  document.querySelectorAll('#ptable tbody tr').forEach(function(tr){
    var ok=true;
    if(c&&tr.dataset.country!==c)ok=false;
    if(r&&tr.dataset.rec!==r)ok=false;
    if(code&&parseInt(tr.dataset.coding)>parseInt(code))ok=false;
    if(q&&tr.textContent.toLowerCase().indexOf(q)<0)ok=false;
    tr.style.display=ok?'':'none';
  });
}
"""


def _cls(v):
    return "s-hi" if v >= 68 else ("s-mid" if v >= 50 else "s-lo")


def _pill(rec):
    m = {"APPLY NOW": "p-apply", "STRONG APPLY": "p-apply", "CONSIDER": "p-consider",
         "BACKUP": "p-backup", "DO NOT APPLY": "p-no"}
    return m.get(rec, "p-reject")


def build(ctx, outdir):
    os.makedirs(outdir, exist_ok=True)
    ranked = ctx["ranked"]
    L = []
    A = L.append

    A("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    A("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    A("<title>Master's Intelligence — %s</title>" % db.today())
    A("<style>%s</style></head><body>" % CSS)

    A("<header><h1>Global Master's Intelligence &amp; Career Matching Engine</h1>")
    A("<div class='sub'>%s · run <code>%s</code> · %d programmes scored · "
      "%d real job postings analysed · profile v%s</div></header>"
      % (db.today(), esc(ctx["run_id"]), len(ranked),
         ctx["jobmarket"]["postings_loaded"],
         ctx["profile"].get("profile_version", 1)))

    tabs = [("dash", "Dashboard"), ("finder", "Master's Finder"), ("detail", "Programme Detail"),
            ("countries", "Countries"), ("careers", "Careers"), ("jobs", "Jobs"),
            ("deadlines", "Deadlines"), ("gaps", "Gap Analysis"), ("decision", "Decision")]
    A("<nav>")
    for i, (tid, label) in enumerate(tabs):
        A("<button class='%s' onclick=\"tab('%s',this)\">%s</button>"
          % ("on" if i == 0 else "", tid, label))
    A("</nav><main>")

    # ---------------------------------------------------------------- dash
    A("<section id='dash' class='on'>")
    A("<h2>Today's top opportunities</h2>")
    top = ranked[0] if ranked else None
    if top:
        s = top["scored"]
        A("<div class='grid'>")
        for k, v in (("Top programme", top["programme"]["name"][:34]),
                     ("Overall", "%.1f" % s["overall"]),
                     ("Personal fit", "%.1f" % s["personal_fit"]),
                     ("Admission", s["admission_band"]),
                     ("Coding", "%d/5" % s["eligibility"]["coding_band"])):
            A("<div class='kv'><div class='k'>%s</div><div class='v'>%s</div></div>" % (esc(k), esc(v)))
        A("</div>")

    for r in ranked[:5]:
        p, s = r["programme"], r["scored"]
        A("<div class='card'>")
        A("<h3>%s <span class='pill %s'>%s %s</span></h3>"
          % (esc(p["name"]), _pill(s["recommendation"]),
             s["recommendation_emoji"], esc(s["recommendation"])))
        A("<div class='mut'>%s · %s, %s</div>"
          % (esc((r.get("university") or {}).get("name", "")), esc(p.get("city")),
             esc(p["country_code"])))
        A("<div class='grid'>")
        for k, v in (("Overall", "%.1f/100" % s["overall"]),
                     ("Personal fit", "%.1f/100" % s["personal_fit"]),
                     ("Career value", "%.1f/100" % s["career_value"]),
                     ("Admission", s["admission_band"]),
                     ("Coding", "%d/5" % s["eligibility"]["coding_band"]),
                     ("Tuition", money(p.get("tuition_eur"))),
                     ("Duration", "%s months" % p.get("duration_months")),
                     ("Post-study work", "%s mo" % p.get("post_study_work_months")
                      if p.get("post_study_work_months") else "NONE")):
            A("<div class='kv'><div class='k'>%s</div><div class='v'>%s</div></div>" % (esc(k), v if "DATA NOT" in str(v) else esc(v)))
        A("</div>")
        A("<p><strong>Why you should apply:</strong> %s</p>" % esc(r["why"]))
        if p.get("notes"):
            A("<div class='warn'><strong>Risks:</strong> %s</div>" % esc(p["notes"]))
        verdict, bullets = r["should_apply"]
        A("<details><summary>Should I apply? — <strong>%s</strong></summary><ul>" % esc(verdict))
        for b in bullets:
            A("<li>%s</li>" % esc(b))
        A("</ul></details>")
        A("<div class='mut'>Source: <a href='%s'>%s</a> · verified %s</div>"
          % (esc(p.get("official_url")), esc((p.get("official_url") or "")[:70]),
             esc(p.get("last_verified"))))
        A("</div>")

    A("<h2>Challenges to your assumptions (§33)</h2>")
    for f in ctx["challenges"]:
        cls = "crit" if f["severity"] in ("RISK", "CHALLENGE") else "warn"
        A("<div class='%s'><strong>%s — %s</strong><br>%s</div>"
          % (cls, esc(f["severity"]), esc(f["headline"]), esc(f["detail"])))

    A("<h2>Today's three actions</h2><ol>")
    for a in ctx["actions"]:
        A("<li>%s</li>" % a.replace("**", ""))
    A("</ol></section>")

    # -------------------------------------------------------------- finder
    A("<section id='finder'><h2>Master's Finder</h2>")
    A("<div class='filters'>")
    A("<input id='fq' placeholder='search…' oninput='filt()'>")
    A("<select id='fc' onchange='filt()'><option value=''>All countries</option>")
    for c in sorted({r["programme"]["country_code"] for r in ranked}):
        A("<option>%s</option>" % esc(c))
    A("</select>")
    A("<select id='fr' onchange='filt()'><option value=''>All recommendations</option>")
    for rec in ["APPLY NOW", "STRONG APPLY", "CONSIDER", "BACKUP", "DO NOT APPLY",
                "REJECT - CODING", "REJECT - ELIGIBILITY"]:
        A("<option>%s</option>" % esc(rec))
    A("</select>")
    A("<select id='fcode' onchange='filt()'><option value=''>Any coding level</option>")
    for i in range(6):
        A("<option value='%d'>Coding ≤ %d</option>" % (i, i))
    A("</select></div>")

    A("<div class='wrap'><table id='ptable'><thead><tr>"
      "<th>#</th><th>Programme</th><th>University</th><th>Country</th><th>Career</th>"
      "<th>Overall</th><th>Fit</th><th>Admission</th><th>Tuition</th><th>Coding</th>"
      "<th>Visa</th><th>Deadline</th><th>Recommendation</th></tr></thead><tbody>")
    for i, r in enumerate(ranked, 1):
        p, s = r["programme"], r["scored"]
        visa = db.uj((r.get("country") or {}).get("visa"), {}) or {}
        A("<tr data-country='%s' data-rec='%s' data-coding='%d'>"
          % (esc(p["country_code"]), esc(s["recommendation"]), s["eligibility"]["coding_band"]))
        A("<td>%d</td><td><strong>%s</strong></td><td>%s</td><td>%s</td><td>%s</td>"
          % (i, esc(p["name"]), esc((r.get("university") or {}).get("name", "")),
             esc(p["country_code"]),
             esc((r.get("career") or {}).get("name", "—").split(" - ")[0])))
        A("<td class='score %s'>%.1f</td><td>%.1f</td><td>%s</td><td>%s</td>"
          % (_cls(s["overall"]), s["overall"], s["personal_fit"],
             esc(s["admission_band"]), money(p.get("tuition_eur"))))
        A("<td>%d/5</td><td>%s</td><td>%s</td><td><span class='pill %s'>%s</span></td></tr>"
          % (s["eligibility"]["coding_band"], esc(visa.get("flag", "—")),
             esc(p.get("application_deadline") or s["deadline_bucket"]),
             _pill(s["recommendation"]), esc(s["recommendation"])))
    A("</tbody></table></div></section>")

    # -------------------------------------------------------------- detail
    A("<section id='detail'><h2>Programme detail (§44)</h2>")
    for r in ranked:
        p, s = r["programme"], r["scored"]
        conf = db.uj(p.get("confidence"), {}) or {}
        A("<details><summary><strong>%s</strong> — %s · %.1f · %s</summary><div class='card'>"
          % (esc(p["name"]), esc((r.get("university") or {}).get("name", "")),
             s["overall"], esc(s["recommendation"])))

        A("<h3>Why it ranks here</h3><div class='grid'>")
        for k, v in s["breakdown"]["overall_components"].items():
            if k.startswith("_"):
                continue
            w = s["breakdown"]["overall_weights"].get(k, 0)
            A("<div class='kv'><div class='k'>%s (w %.0f%%)</div><div class='v'>%.1f</div>"
              "<div class='bar'><i style='width:%.0f%%'></i></div></div>"
              % (esc(k.replace("_", " ")), w * 100, v, min(100, v)))
        A("</div>")
        if s["penalties"]:
            for pen in s["penalties"]:
                A("<div class='crit'><strong>%s %+d</strong> — %s</div>"
                  % (esc(pen["rule"]), pen["points"], esc(pen["reason"])))

        A("<h3>My fit</h3><p>%s</p>" % esc(r["why"]))
        A("<h3>Admission probability</h3><p><strong>%s</strong> — %s</p>"
          % (esc(s["admission_band"]), esc(s["admission_reason"])))

        A("<h3>Coding intensity — %d/5 %s</h3>"
          % (s["eligibility"]["coding_band"], conf_badge(conf, "coding_intensity")))
        ce = s["eligibility"]["coding_evidence"]
        A("<p class='mut'>%s</p>" % esc(p.get("coding_evidence") or ce.get("label", "")))
        A("<details><summary>Signal trace</summary><pre class='mut' style='white-space:pre-wrap'>%s</pre></details>"
          % esc(json.dumps(ce, indent=1)[:1600]))

        A("<h3>Cost and ROI</h3><div class='grid'>")
        A("<div class='kv'><div class='k'>Tuition %s</div><div class='v'>%s</div></div>"
          % (conf_badge(conf, "tuition"), money(p.get("tuition_eur"))))
        A("<div class='kv'><div class='k'>Living (est.)</div><div class='v'>%s</div></div>"
          % money(p.get("living_cost_eur")))
        A("<div class='kv'><div class='k'>ROI ratio</div><div class='v'>%s</div></div>"
          % (("%.2fx" % s["roi_ratio"]) if s["roi_ratio"] else "<span class='unv'>not calculable</span>"))
        A("</div>")
        A("<details><summary>ROI assumptions (§14)</summary><pre class='mut' style='white-space:pre-wrap'>%s</pre></details>"
          % esc(json.dumps(s["roi_assumptions"], indent=1)))

        A("<h3>Salary projection (§22)</h3>")
        sal = r["salary"]
        if sal["available"]:
            A("<div class='warn'>%s</div>" % esc(sal["note"]))
            A("<div class='wrap'><table><thead><tr><th>Stage</th><th>EUR</th>"
              "<th>INR equivalent</th><th>Confidence</th></tr></thead><tbody>")
            for row in sal["rows"]:
                A("<tr><td>%s</td><td>€%s</td><td>₹%s</td><td>%s</td></tr>"
                  % (esc(row["stage"]), format(row["eur"], ","),
                     format(row["inr_equivalent"], ","), esc(row["confidence"])))
            A("</tbody></table></div><p class='mut'>%s</p>" % esc(sal["inr_assumption"]))
        else:
            A("<div class='warn'>%s</div>" % esc(sal["note"]))

        A("<h3>Visa</h3>")
        visa = db.uj((r.get("country") or {}).get("visa"), {}) or {}
        A("<p>%s · route: %s · post-study work: %s</p>"
          % (esc(visa.get("flag", "—")), esc(p.get("visa_route")),
             "%s months" % p.get("post_study_work_months")
             if p.get("post_study_work_months") else "<span class='unv'>NONE</span>"))
        A("<p class='mut'>%s</p>" % esc(visa.get("why_flag", "")))

        A("<h3>Requirements</h3><ul>")
        A("<li>Academic: %s %s</li>" % (esc(p.get("academic_prereq") or "DATA NOT VERIFIED"),
                                        conf_badge(conf, "academic_prereq")))
        A("<li>English: %s %s</li>" % (esc(p.get("ielts") or "DATA NOT VERIFIED"),
                                       conf_badge(conf, "ielts")))
        A("<li>Work experience: %s</li>" % esc(p.get("work_exp_requirement") or "unstated"))
        A("<li>Deadline: %s %s</li>" % (esc(p.get("application_deadline") or s["deadline_bucket"]),
                                        conf_badge(conf, "deadline")))
        A("</ul>")

        cur = db.uj(p.get("curriculum"), []) or []
        if cur:
            A("<h3>Curriculum %s</h3><ul>" % conf_badge(conf, "curriculum"))
            for m in cur:
                A("<li>%s</li>" % esc(m))
            A("</ul>")

        A("<h3>Career paths</h3><ul>")
        for k in ("0-2", "3-5", "5-10"):
            A("<li><strong>%s yrs:</strong> %s</li>"
              % (k, esc(", ".join(r["outcomes"].get(k, [])))))
        A("</ul>")

        if r["outcomes"]["evidence"]:
            A("<h3>Job-market evidence (§31)</h3><ul>")
            for cid, e in r["outcomes"]["evidence"].items():
                A("<li><strong>%s</strong>: %d postings · coding demanded %s · "
                  "master's demanded %s · employers: %s</li>"
                  % (esc(cid), e["postings"],
                     "%.0f%%" % e["coding_required_pct"] if e["coding_required_pct"] is not None else "n/a",
                     "%.0f%%" % e["masters_required_pct"] if e["masters_required_pct"] is not None else "n/a",
                     esc(", ".join(x[0] for x in e["top_employers"][:4]))))
            A("</ul>")

        A("<h3>Sources</h3><ul>")
        for u in (db.uj(p.get("evidence_urls"), []) or []):
            A("<li><a href='%s'>%s</a></li>" % (esc(u), esc(u)))
        A("</ul><p class='mut'>Last verified %s</p>" % esc(p.get("last_verified")))
        A("</div></details>")
    A("</section>")

    # ----------------------------------------------------------- countries
    A("<section id='countries'><h2>Countries (§29)</h2><div class='wrap'><table><thead><tr>"
      "<th>#</th><th>Country</th><th>Score</th><th>Visa</th><th>Post-study work</th>"
      "<th>Skilled threshold</th><th>Assessment</th></tr></thead><tbody>")
    for i, c in enumerate(ctx["countries_ranked"], 1):
        visa = db.uj(c.get("visa"), {}) or {}
        psw = (visa.get("post_study_work_months") or {})
        thr = (visa.get("skilled_threshold_eur") or {})
        A("<tr><td>%d</td><td><strong>%s</strong></td><td class='score %s'>%.1f</td>"
          "<td>%s</td><td>%s %s</td><td>%s</td><td class='mut'>%s</td></tr>"
          % (i, esc(c["name"]), _cls(c["country_score"]), c["country_score"],
             esc(visa.get("flag", "—")),
             "%s mo" % psw.get("value") if psw.get("value") is not None else "<span class='unv'>n/v</span>",
             conf_badge({"x": psw.get("confidence")}, "x"),
             money(thr.get("value")),
             esc(visa.get("why_flag", ""))))
    A("</tbody></table></div>")
    A("<div class='warn'>Ordinal country sub-scores are <strong>editorial judgements for this "
      "applicant</strong>, not measurements. Salary thresholds and stay-back durations are "
      "facts and carry their own confidence labels — several were carried over from earlier "
      "research and were <strong>not</strong> re-verified in this run.</div></section>")

    # ------------------------------------------------------------- careers
    A("<section id='careers'><h2>Careers (§35)</h2><div class='wrap'><table><thead><tr>"
      "<th>#</th><th>Career</th><th>Score</th><th>Money</th><th>Purpose</th><th>Balanced</th>"
      "<th>Postings</th><th>Demand source</th></tr></thead><tbody>")
    for i, c in enumerate(ctx["careers_ranked"], 1):
        ev = ctx["jobmarket"]["by_id"].get(c["career_id"], {})
        prov = c["provenance"].get("job_demand", "ESTIMATED")
        A("<tr><td>%d</td><td><strong>%s</strong></td><td class='score %s'>%.1f</td>"
          "<td>%.1f</td><td>%.1f</td><td>%.1f</td><td>%d</td><td class='mut'>%s</td></tr>"
          % (i, esc(c["career_name"]), _cls(c["career_score"]), c["career_score"],
             c["money_score"], c["purpose_score"], c["balanced_score"],
             ev.get("posting_count", 0), esc(prov)))
    A("</tbody></table></div>")

    A("<h2>Career arbitrage (§32)</h2><div class='wrap'><table><thead><tr>"
      "<th>Combination</th><th>Score</th><th>Rarity</th><th>Transferability</th>"
      "<th>Measured postings</th></tr></thead><tbody>")
    for a in ctx["arbitrage"]:
        A("<tr><td><strong>%s</strong></td><td class='score %s'>%.1f</td><td>%s/10</td>"
          "<td>%s/10</td><td>%d</td></tr>"
          % (esc(a["name"]), _cls(a["score"]), a["score"], a["rarity"],
             a["transferability"], a["measured_postings"]))
    A("</tbody></table></div></section>")

    # ---------------------------------------------------------------- jobs
    A("<section id='jobs'><h2>Job market (§31) — measured from %d real postings</h2>"
      % ctx["jobmarket"]["postings_loaded"])
    A("<div class='wrap'><table><thead><tr><th>Career</th><th>Postings</th>"
      "<th>Coding demanded</th><th>Master's demanded</th><th>Median yrs</th>"
      "<th>Sponsorship +/-</th><th>Top employers</th><th>Top regulations</th>"
      "</tr></thead><tbody>")
    for b in sorted(ctx["jobmarket"]["blocks"], key=lambda x: -x["posting_count"]):
        A("<tr><td><strong>%s</strong></td><td>%d</td><td>%s</td><td>%s</td><td>%s</td>"
          "<td>%d / %d</td><td class='mut'>%s</td><td class='mut'>%s</td></tr>"
          % (esc(b["career_name"]), b["posting_count"],
             "%.0f%% <span class='mut'>(n=%d)</span>" % (b["coding_required_pct"], b["coding_sample"])
             if b["coding_required_pct"] is not None else "—",
             "%.0f%% <span class='mut'>(n=%d)</span>" % (b["masters_required_pct"], b["masters_sample"])
             if b["masters_required_pct"] is not None else "—",
             b["median_years_required"] or "—",
             b["sponsorship_positive"], b["sponsorship_negative"],
             esc(", ".join(x[0] for x in b["top_employers"][:4])),
             esc(", ".join(x[0] for x in b["top_regulations"][:4]))))
    A("</tbody></table></div></section>")

    # ----------------------------------------------------------- deadlines
    A("<section id='deadlines'><h2>Deadlines (§24)</h2>")
    buckets = {}
    for r in ranked:
        buckets.setdefault(r["scored"]["deadline_bucket"], []).append(r)
    _order = ["DEADLINE IN 7 DAYS", "DEADLINE IN 14 DAYS", "DEADLINE IN 30 DAYS",
              "DEADLINE IN 60 DAYS", "DEADLINE IN 90 DAYS", "BEYOND 90 DAYS",
              "ROLLING", "UNKNOWN", "CLOSED"]
    _order += [b for b in buckets if b not in _order]
    for b in _order:
        if b not in buckets:
            continue
        A("<h3>%s</h3><div class='wrap'><table><thead><tr><th>Programme</th><th>Date</th>"
          "<th>Status</th><th>Recommendation</th></tr></thead><tbody>" % esc(b))
        for r in buckets[b]:
            A("<tr><td>%s</td><td>%s</td><td>%s</td><td><span class='pill %s'>%s</span></td></tr>"
              % (esc(r["programme"]["name"]),
                 esc(r["programme"].get("application_deadline") or "—"),
                 esc(r["scored"]["deadline_status"]),
                 _pill(r["scored"]["recommendation"]), esc(r["scored"]["recommendation"])))
        A("</tbody></table></div>")
    A("</section>")

    # ---------------------------------------------------------------- gaps
    A("<section id='gaps'><h2>CV gap analysis (§27)</h2>")
    if ranked:
        g = ranked[0]["gaps"]
        A("<div class='card'><h3>What you already have</h3><ul>")
        for h in g["have"]:
            A("<li>%s</li>" % esc(h))
        A("</ul></div>")
        A("<div class='wrap'><table><thead><tr><th>Gap</th><th>Importance</th>"
          "<th>Covered by top programme?</th><th>How to fix</th><th>Time</th>"
          "</tr></thead><tbody>")
        for gap in g["gaps"]:
            A("<tr><td><strong>%s</strong></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
              % (esc(gap["gap"]), esc(gap["importance"]),
                 "yes" if gap["covered_by_programme"] else "no",
                 esc(gap["fix"]), esc(gap["time"])))
        A("</tbody></table></div>")
    A("</section>")

    # ------------------------------------------------------------ decision
    A("<section id='decision'><h2>Final decision engine (§54)</h2>")
    A("<h3>If you could apply to only 5 programmes today</h3>")
    for i, r in enumerate(ctx["top5"], 1):
        p, s = r["programme"], r["scored"]
        A("<div class='card'><h3>%d. %s</h3>" % (i, esc(p["name"])))
        A("<ol><li><strong>Why:</strong> %s</li>" % esc(r["why"][:420]))
        A("<li><strong>Expected career:</strong> %s</li>"
          % esc((r.get("career") or {}).get("name", "—")))
        A("<li><strong>Admission probability:</strong> %s — %s</li>"
          % (esc(s["admission_band"]), esc(s["admission_reason"][:200])))
        A("<li><strong>Cost:</strong> %s</li>" % money(p.get("tuition_eur")))
        A("<li><strong>Deadline:</strong> %s</li>"
          % esc(p.get("application_deadline") or s["deadline_bucket"]))
        A("<li><strong>Biggest risk:</strong> %s</li></ol></div>"
          % esc((p.get("notes") or "none recorded")[:340]))

    A("<h3>If you could choose only 3 countries</h3><ol>")
    for c in ctx["countries_ranked"][:3]:
        visa = db.uj(c.get("visa"), {}) or {}
        A("<li><strong>%s</strong> (%.1f) — %s</li>"
          % (esc(c["name"]), c["country_score"], esc(visa.get("why_flag", ""))))
    A("</ol>")

    tc = ctx["careers_ranked"][0]
    A("<h3>If you could choose only one career</h3>")
    A("<div class='ok'><strong>%s</strong> — career score %.1f<br>%s</div>"
      % (esc(tc["career_name"]), tc["career_score"], esc(tc["rationale"])))
    A("</section>")

    A("</main><footer>")
    A("Generated by masters-engine · stdlib Python · SQLite. "
      "Programme facts verified against official university pages on the dates shown. "
      "Ordinal scores are editorial judgements labelled ESTIMATED. "
      "Fields shown as DATA NOT VERIFIED were not found on an official source and were "
      "deliberately left blank rather than estimated.")
    A("</footer><script>%s</script></body></html>" % JS)

    path = os.path.join(outdir, "index.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return path
