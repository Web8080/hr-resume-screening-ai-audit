"""Bias audit of a (synthetic) AI resume-screening tool. Pure standard library, seeded, reproducible."""
import csv, json, random, collections
random.seed(42)
N = 4000
GROUPS = {"gender": ["Female", "Male"], "ethnicity": ["White", "Black", "Hispanic", "Asian"], "age": ["Under 40", "40 plus"]}

def make():
    rows = []
    for i in range(N):
        g = random.choice(["Female", "Male"])
        e = random.choices(["White", "Black", "Hispanic", "Asian"], [0.55, 0.15, 0.18, 0.12])[0]
        age = random.choices([27, 34, 45, 55], [0.35, 0.30, 0.22, 0.13])[0] + random.randint(0, 4)
        skill = random.gauss(0, 1)                       # true job-relevant ability, same distribution for everyone
        gap = max(0, round(random.gauss(0.5 if g == "Female" else 0.1, 0.8)))  # career-gap years (caregiving skews female)
        tier = random.choices([1, 2, 3], [0.2, 0.35, 0.45] if e == "White" else [0.1, 0.3, 0.6])[0]  # 1 = elite school
        rows.append(dict(id=i, gender=g, ethnicity=e, age=age, age_band="Under 40" if age < 40 else "40 plus",
                         skill=round(skill, 3), gap_years=gap, school_tier=tier))
    return rows

def score_biased(r):   # what the vendor model effectively learned from historical hiring
    return r["skill"] + 0.45 * (3 - r["school_tier"]) - 0.5 * r["gap_years"] - 0.036 * max(0, r["age"] - 35)

def score_fixed(r):    # job-relevant signal only
    return r["skill"]

def select(rows, fn, top=0.25):
    cut = sorted((fn(r) for r in rows), reverse=True)[int(len(rows) * top)]
    return {r["id"] for r in rows if fn(r) >= cut}

def rates(rows, sel, attr, only_qualified=False):
    out = {}
    for grp in sorted({r[attr] for r in rows}):
        pool = [r for r in rows if r[attr] == grp and (not only_qualified or r["skill"] > 0.5)]
        out[grp] = round(100 * sum(r["id"] in sel for r in pool) / len(pool), 1)
    return out

def air(rt):
    best = max(rt.values())
    return {k: round(v / best, 2) for k, v in rt.items()}

rows = make()
with open("data/applicants.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

sel_b, sel_f = select(rows, score_biased), select(rows, score_fixed)
report = {"n": N}
for name, sel in (("current", sel_b), ("remediated", sel_f)):
    report[name] = {}
    for attr, col in (("gender", "gender"), ("ethnicity", "ethnicity"), ("age", "age_band")):
        rt = rates(rows, sel, col)
        report[name][attr] = {"selection_rate": rt, "impact_ratio": air(rt),
                              "qualified_selection_rate": rates(rows, sel, col, True)}
# proxy check: how strongly do "neutral" features track protected attributes?
fem_gap = sum(r["gap_years"] for r in rows if r["gender"] == "Female") / sum(r["gender"] == "Female" for r in rows)
male_gap = sum(r["gap_years"] for r in rows if r["gender"] == "Male") / sum(r["gender"] == "Male" for r in rows)
report["proxy"] = {"mean_gap_years_female": round(fem_gap, 2), "mean_gap_years_male": round(male_gap, 2)}
json.dump(report, open("data/audit_results.json", "w"), indent=2)

def worst(sec):
    return min((v, f"{a}:{k}") for a in sec for k, v in sec[a]["impact_ratio"].items())
print("worst impact ratio, current   :", worst(report["current"]))
print("worst impact ratio, remediated:", worst(report["remediated"]))

# dashboard spec
def items(attr, key="selection_rate", sec="current"):
    ir = report[sec][attr]["impact_ratio"]
    return [{"label": k, "value": v, "status": "good" if ir[k] >= 0.8 else "bad"} for k, v in report[sec][attr][key].items()]
cur = report["current"]
rowsT = []
for a in ("gender", "ethnicity", "age"):
    for k, v in cur[a]["impact_ratio"].items():
        rowsT.append([a.title(), k, cur[a]["selection_rate"][k], v, report["remediated"][a]["impact_ratio"][k], "PASS" if v >= 0.8 else "FAIL"])
wv, wl = worst(cur); rv, _ = worst(report["remediated"])
spec = {"title": "AI Resume Screening Review: Bias Audit", "subtitle": f"{N:,} synthetic applicants, top 25% advance. Four-fifths rule (impact ratio >= 0.80).",
        "kpis": [{"label": "Worst impact ratio (current)", "value": wv, "status": "bad", "note": wl},
                 {"label": "Worst impact ratio (job-relevant only)", "value": rv, "status": "good", "note": "after removing proxy signals"},
                 {"label": "Groups failing 4/5 rule", "value": sum(r[5] == "FAIL" for r in rowsT), "status": "bad", "note": f"of {len(rowsT)} groups tested"},
                 {"label": "Female vs male mean career gap", "value": f'{fem_gap:.2f} vs {male_gap:.2f}', "status": "warn", "note": "years; gap is a gender proxy"}],
        "verdict": {"status": "bad", "label": "Recommendation: do not deploy as-is.", "text": "Older applicants fail the four-fifths rule outright. Gender and ethnicity pass but gender sits close to the line and rides on a career-gap proxy. Require vendor remediation and human review before any use."},
        "charts": [{"title": "Selection rate by gender (%)", "unit": "%", "max": 40, "items": items("gender")},
                   {"title": "Selection rate by ethnicity (%)", "unit": "%", "max": 40, "items": items("ethnicity")},
                   {"title": "Selection rate by age band (%)", "unit": "%", "max": 40, "items": items("age")},
                   {"title": "Equal opportunity: selection rate among truly qualified, by gender (%)", "unit": "%", "max": 100, "items": items("gender", "qualified_selection_rate")}],
        "tables": [{"title": "Impact ratio by group", "columns": ["Attribute", "Group", "Selection rate %", "Impact ratio", "After remediation", "4/5 rule"], "rows": rowsT}]}
json.dump(spec, open("data/dashboard_spec.json", "w"), indent=1)
