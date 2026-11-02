"""Statistical bias audit. Reads data/applicants.csv (written by analysis.py).
Adds what a defensible audit needs beyond a four-fifths table: significance tests, confidence intervals,
intersectional cuts, feature ablation (what drives the disparity), proxy tests and a criterion-validity check."""
import json, numpy as np, pandas as pd
from scipy import stats
rng = np.random.default_rng(42)
df = pd.read_csv("data/applicants.csv")
TOP = 0.25
def s_cur(d): return d.skill + 0.45 * (3 - d.school_tier) - 0.5 * d.gap_years - 0.036 * np.maximum(0, d.age - 35)
def select(score):
    cut = np.sort(score.values)[::-1][int(len(df) * TOP)]; return (score >= cut).astype(int)
df["sel"] = select(s_cur(df)); df["qualified"] = (df.skill > 0.5).astype(int)
res = json.load(open("data/audit_results.json"))
# integrity check: this script must reproduce the first-stage results
chk = df.groupby("age_band").sel.mean().mul(100).round(1).to_dict()
assert chk == res["current"]["age"]["selection_rate"], "audit.py has drifted from analysis.py"

def ratio_table(d, col, sel="sel"):
    rates = d.groupby(col)[sel].agg(["sum", "count"]); rates["rate"] = rates["sum"] / rates["count"]
    ref = rates.rate.idxmax(); out = []
    for g, r in rates.iterrows():
        tbl = [[r["sum"], r["count"] - r["sum"]], [rates.loc[ref, "sum"], rates.loc[ref, "count"] - rates.loc[ref, "sum"]]]
        p = 1.0 if g == ref else stats.fisher_exact(tbl)[1]
        out.append(dict(group=g, n=int(r["count"]), selected=int(r["sum"]), rate=round(100 * r.rate, 1), ratio=round(r.rate / rates.rate.max(), 3), p=float(p), reference=(g == ref)))
    return out
def boot_ratio(d, col, group, ref, B=2000):
    g = d[d[col] == group].sel.values; r = d[d[col] == ref].sel.values; v = []
    for _ in range(B):
        a = rng.choice(g, len(g)).mean(); b = rng.choice(r, len(r)).mean(); v.append(a / b if b else np.nan)
    return [round(float(x), 3) for x in np.nanpercentile(v, [2.5, 97.5])]
R = {"n": len(df), "top_share": TOP, "single": {}, "ci": {}, "intersectional": [], "ablation": [], "proxy": {}, "validity": {}, "equal_opportunity": {}}
for col in ("gender", "ethnicity", "age_band"):
    R["single"][col] = ratio_table(df, col)
    ref = [x["group"] for x in R["single"][col] if x["reference"]][0]
    for x in R["single"][col]:
        if not x["reference"]: x["ci95"] = boot_ratio(df, col, x["group"], ref)
# intersectional (gender x age) as required by NYC LL144 style audits
df["gender_age"] = df.gender + " / " + df.age_band
R["intersectional"] = ratio_table(df, "gender_age")
# equal opportunity among truly qualified
q = df[df.qualified == 1]
R["equal_opportunity"] = {c: ratio_table(q, c) for c in ("gender", "ethnicity", "age_band")}
# ablation: remove one score component at a time, re-select, see which component drives the age and gender gaps
terms = {"school tier": lambda d: 0.45 * (3 - d.school_tier), "career gap": lambda d: -0.5 * d.gap_years, "age": lambda d: -0.036 * np.maximum(0, d.age - 35)}
variants = [("Current model (all components)", s_cur(df))] + [(f"Remove {k}", s_cur(df) - f(df)) for k, f in terms.items()] + [("Skill only (job-relevant signal)", df.skill)]
for name, sc in variants:
    d2 = df.copy(); d2["sel"] = select(sc)
    ar = {c: min(x["ratio"] for x in ratio_table(d2, c)) for c in ("age_band", "gender", "ethnicity")}
    R["ablation"].append(dict(variant=name, age_ratio=ar["age_band"], gender_ratio=ar["gender"], ethnicity_ratio=ar["ethnicity"],
                              precision_qualified=round(float(d2[d2.sel == 1].qualified.mean()) * 100, 1)))
# proxy tests
f, m = df[df.gender == "Female"].gap_years, df[df.gender == "Male"].gap_years
R["proxy"]["gap_by_gender"] = dict(female=round(f.mean(), 2), male=round(m.mean(), 2), mann_whitney_p=float(stats.mannwhitneyu(f, m).pvalue))
ct = pd.crosstab(df.ethnicity, df.school_tier); chi = stats.chi2_contingency(ct)
R["proxy"]["tier_by_ethnicity"] = dict(chi2=round(float(chi[0]), 1), p=float(chi[1]), cramers_v=round(float(np.sqrt(chi[0] / (len(df) * (min(ct.shape) - 1)))), 3))
R["proxy"]["age_in_score"] = "direct: age is an input to the score formula (age penalty)"
# criterion validity: does the score track true job-relevant skill?
sc = s_cur(df); R["validity"] = dict(spearman_score_vs_skill=round(float(stats.spearmanr(sc, df.skill)[0]), 3),
    precision_current=R["ablation"][0]["precision_qualified"], precision_skill_only=R["ablation"][-1]["precision_qualified"])
json.dump(R, open("data/audit_stats.json", "w"), indent=1, default=float)
print(json.dumps({k: R[k] for k in ("validity", "proxy")}, indent=1, default=float))
for a in R["ablation"]: print(a)
for c in R["single"]:
    for x in R["single"][c]: print(c, x)
for x in R["intersectional"]: print(x["group"], x["rate"], x["ratio"], round(x["p"], 4))
print({c: [(x["group"], x["rate"], x["ratio"], round(x["p"], 4)) for x in v] for c, v in R["equal_opportunity"].items()})
