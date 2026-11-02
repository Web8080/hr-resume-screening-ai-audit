"""Builds the audit report (docx, pdf, md), figures and the vendor questionnaire from data/audit_stats.json."""
import json, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from grc_kit import render_report, render_questionnaire
R = json.load(open("data/audit_stats.json"))
pf = lambda p: "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
S = {c: {x["group"]: x for x in R["single"][c]} for c in R["single"]}
EO = {c: {x["group"]: x for x in R["equal_opportunity"][c]} for c in R["equal_opportunity"]}
age, fem = S["age_band"]["40 plus"], S["gender"]["Female"]; hisp = S["ethnicity"]["Hispanic"]
inter = {x["group"]: x for x in R["intersectional"]}; worst_i = min(R["intersectional"], key=lambda x: x["ratio"])
ab = {a["variant"]: a for a in R["ablation"]}
cur, noage, nogap, skill = ab["Current model (all components)"], ab["Remove age"], ab["Remove career gap"], ab["Skill only (job-relevant signal)"]

# ---- figures
fig, ax = plt.subplots(figsize=(8, 3.6)); items = [(f"{c.replace('_band','')}: {g}", x["ratio"], x.get("ci95")) for c in S for g, x in S[c].items()]
cols = ["#c0392b" if r < 0.8 else "#1a7f4b" for _, r, _ in items]
ax.barh([i[0] for i in items], [i[1] for i in items], color=cols)
for y, (_, r, ci) in enumerate(items):
    if ci: ax.plot(ci, [y, y], color="#333", lw=1.4)
ax.axvline(0.8, color="#333", ls="--"); ax.text(0.8, len(items) - 0.4, " four-fifths line", fontsize=8); ax.set_xlim(0, 1.25); ax.invert_yaxis(); ax.set_xlabel("Impact ratio (95% bootstrap CI)")
plt.tight_layout(); plt.savefig("docs/figures/impact_ratios.png", dpi=150); plt.close()
fig, ax = plt.subplots(figsize=(8, 3.4)); names = [a["variant"].replace(" (all components)", "").replace(" (job-relevant signal)", "") for a in R["ablation"]]
x = range(len(names)); ax.bar([i - 0.2 for i in x], [a["age_ratio"] for a in R["ablation"]], 0.4, label="Age (40 plus)", color="#2b6cb0"); ax.bar([i + 0.2 for i in x], [a["gender_ratio"] for a in R["ablation"]], 0.4, label="Gender", color="#b7791f")
ax.axhline(0.8, color="#333", ls="--"); ax.set_xticks(list(x)); ax.set_xticklabels(names, fontsize=7, rotation=10); ax.set_ylabel("Impact ratio"); ax.legend(fontsize=8); plt.tight_layout(); plt.savefig("docs/figures/ablation.png", dpi=150); plt.close()

# ---- findings
F = [
 dict(id="F1", title="Applicants aged 40 and over are screened out at roughly half the rate of younger applicants", rating="Critical",
  condition=f"40 plus applicants advance at {age['rate']}% versus 30.1% for under 40: impact ratio {age['ratio']} (95% CI {age['ci95'][0]} to {age['ci95'][1]}, {pf(age['p'])}). The intersection of women aged 40 and over is worst at {inter['Female / 40 plus']['ratio']}. Removing the age component from the score restores the ratio to {noage['age_ratio']}.",
  criteria="Impact ratio of at least 0.80 (EEOC Uniform Guidelines, 29 CFR 1607.4D) and no statistically significant disparity. Age Discrimination in Employment Act protects applicants 40 and over. NYC Local Law 144 requires impact ratios to be published for the tool.",
  cause="The scoring function applies an explicit age-linked penalty (in real tools this typically appears as graduation year, years of experience caps or recency weighting). Ablation shows age is the single driver: school tier and career gap leave the ratio at 0.52 to 0.53.",
  effect="Disparate-impact liability under the ADEA and equivalent laws; loss of experienced talent; regulatory and reputational exposure; EU AI Act high-risk non-conformity if used in the EU.",
  recommendation="Suspend production use for age-sensitive roles immediately. Require vendor to remove age-linked features and any proxies (graduation year, experience ceilings), re-run this audit and provide evidence before reinstatement.",
  refs="NIST AI RMF MEASURE 2.11; ISO/IEC 23894 6.4; EU AI Act Art. 10(2)(f) and Art. 15; EEOC UGESP", owner="Head of Talent Acquisition / 2026-11-16",
  mgmt_response="Agree. Production use suspended pending vendor remediation; Legal to assess exposure for candidates already screened."),
 dict(id="F2", title="Qualified women advance less often than equally qualified men, and the headline test hides it", rating="High",
  condition=f"Overall gender impact ratio is {fem['ratio']} ({pf(fem['p'])}), which passes the four-fifths screen and is not statistically significant. Among applicants who are truly qualified, women advance at {EO['gender']['Female']['rate']}% versus {EO['gender']['Male']['rate']}% for men: ratio {EO['gender']['Female']['ratio']} ({pf(EO['gender']['Female']['p'])}).",
  criteria="Equal opportunity: qualified candidates should have equal chance of progressing regardless of sex. Adverse-impact analysis should not rely on a single aggregate screen (EEOC guidance; NIST AI RMF MEASURE 2.11).",
  cause=f"Career-gap years are penalised in the score. Women average {R['proxy']['gap_by_gender']['female']} gap years versus {R['proxy']['gap_by_gender']['male']} for men ({pf(R['proxy']['gap_by_gender']['mann_whitney_p'])}). Removing the gap penalty lifts the gender ratio to {nogap['gender_ratio']}.",
  effect="Indirect sex discrimination (including caregiving-related gaps); the vendor's aggregate fairness statistic would give false assurance.",
  recommendation="Remove career-gap and similar proxy features; adopt equal-opportunity difference as a mandatory reporting metric alongside impact ratio; add it to the release criteria.",
  refs="NIST AI RMF MAP 2.3, MEASURE 2.11; EU AI Act Art. 10(2)(f); Title VII; Equality Act 2010 s.19", owner="Vendor / People Analytics / 2026-12-15",
  mgmt_response="Agree. Add equal-opportunity difference to the audit standard and the vendor contract."),
 dict(id="F3", title="Proxy variables are not identified or governed", rating="High",
  condition=f"Career-gap years differ by gender ({pf(R['proxy']['gap_by_gender']['mann_whitney_p'])}); school tier is associated with ethnicity (chi-square {R['proxy']['tier_by_ethnicity']['chi2']}, {pf(R['proxy']['tier_by_ethnicity']['p'])}, Cramer's V {R['proxy']['tier_by_ethnicity']['cramers_v']}). Hispanic applicants sit at an impact ratio of {hisp['ratio']} (95% CI {hisp['ci95'][0]} to {hisp['ci95'][1]}, {pf(hisp['p'])}), below 0.90 but not statistically significant.",
  criteria="A documented feature review that tests every model input for association with protected characteristics, with a rationale for retaining any associated feature (ISO/IEC 23894; EU AI Act Art. 10(2)(f) and (g)).",
  cause="No feature-level fairness review process was evidenced; fairness is checked, if at all, only on outputs.",
  effect="Discrimination can re-enter through innocuous-looking features even when protected attributes are never used; borderline groups may breach thresholds after any model update.",
  recommendation="Vendor to provide the feature list and association tests; employer to monitor the Hispanic and Asian cells monthly with sample-size-aware tests; set an alert at ratio 0.85.",
  refs="NIST AI RMF MAP 2.3, MEASURE 2.11; ISO/IEC 23894", owner="Vendor / Privacy / 2026-12-15",
  mgmt_response="Agree. Request feature list as a condition of continued engagement."),
 dict(id="F4", title="No evidence that the score is job-related (criterion validity)", rating="Medium",
  condition=f"The score correlates with true skill at Spearman {R['validity']['spearman_score_vs_skill']}, and {cur['precision_qualified']}% of the people it advances are truly qualified, versus {skill['precision_qualified']}% for a skill-only ranking. (In this synthetic data the skill-only result is a by-construction ceiling; real validity must come from the vendor's studies.) No vendor validation study was provided.",
  criteria="Where adverse impact exists, the selection procedure must be validated as job-related and consistent with business necessity (UGESP 29 CFR 1607.5). EU AI Act Art. 15 requires appropriate accuracy.",
  cause="Vendor claims accuracy but supplies no job-relatedness evidence.",
  effect="Employer cannot defend the tool's use if challenged; a biased and not-very-predictive tool has no business case.",
  recommendation="Obtain vendor validation studies; run a local validation against hire and performance outcomes before any scaled use.",
  refs="EEOC UGESP; NIST AI RMF MEASURE 2.1, 2.5; EU AI Act Art. 15", owner="People Analytics / 2027-01-31",
  mgmt_response="Agree. Validation study scoped for Q1."),
 dict(id="F5", title="Governance, transparency and oversight controls could not be tested", rating="High",
  condition="Eight of 14 control objectives (C-07 to C-14) could not be tested because the vendor has not answered the due-diligence questionnaire (issued with this report). They cover independent audit, candidate notice, human oversight, logging, data use, change control, accessibility and kill switch.",
  criteria="NYC Local Law 144 (annual independent audit, candidate notice); EU AI Act Arts 12, 13, 14 and 26; GDPR Art. 22 and 35.",
  cause="No pre-contract AI due-diligence step existed; the tool was piloted on a business request.",
  effect="Unknown exposure. Absence of evidence is treated as non-compliance until the questionnaire is answered and evidence reviewed.",
  recommendation="Vendor to return the questionnaire (workbook provided) with evidence within 15 working days. Reviewers to score and update this report. No production use until closed.",
  refs="NIST AI RMF GOVERN 1.x, 2.x; ISO/IEC 42001 8.x", owner="Procurement / Legal / 2026-11-23",
  mgmt_response="Agree. Questionnaire issued; response deadline set."),
]
CT = [
 ["C-01", "Selection-rate impact ratio >= 0.80 for every protected group", "Computed on 4,000 applicants; compared with four-fifths line", "FAIL", f"40 plus ratio {age['ratio']}"],
 ["C-02", "Disparities tested for statistical significance with confidence intervals", "Fisher exact test; 2,000-sample bootstrap CI", "FAIL", f"Age {pf(age['p'])}; gender and ethnicity not significant overall"],
 ["C-03", "Intersectional impact tested", "Gender by age cells", "FAIL", f"Women 40 plus {inter['Female / 40 plus']['ratio']}"],
 ["C-04", "Equal opportunity among truly qualified applicants", "Selection rate among skill > 0.5", "FAIL", f"Women {EO['gender']['Female']['ratio']} of men ({pf(EO['gender']['Female']['p'])})"],
 ["C-05", "Proxy and feature review performed", "Association tests and feature ablation", "FAIL", "Gap and school tier act as proxies; age used directly"],
 ["C-06", "Job-relatedness / criterion validity evidenced", "Correlation of score with true skill; precision of advanced set", "PARTIAL", f"Spearman {R['validity']['spearman_score_vs_skill']}; no vendor study (F4)"],
] + [[f"C-{n}", o, "Questionnaire section " + sec, "NOT TESTED", "Awaiting vendor response (F5)"] for n, o, sec in [
 ("07", "Independent bias audit within 12 months published", "2"), ("08", "Candidate notice and alternative process", "5"), ("09", "Meaningful human oversight and override", "5"),
 ("10", "Logging and traceability of every score", "4"), ("11", "Candidate data use and retention; no training on our data", "3"), ("12", "Change control and re-audit on model update", "6"),
 ("13", "Accessibility and reasonable adjustments", "5"), ("14", "Monitoring, incident handling and kill switch", "6")]]
RK = [
 dict(id="R1", risk="Age discrimination claim or regulatory action", il=5, ii=5, controls="None", rl=5, ri=5, owner="Head of TA / Legal", treatment="Mitigate: suspend, remediate, re-audit"),
 dict(id="R2", risk="Sex discrimination via career-gap proxy", il=4, ii=4, controls="None", rl=4, ri=4, owner="Head of TA", treatment="Mitigate: remove proxy"),
 dict(id="R3", risk="Non-compliance with NYC LL144 / EU AI Act obligations", il=4, ii=4, controls="None evidenced", rl=4, ri=4, owner="Legal", treatment="Mitigate: close F5"),
 dict(id="R4", risk="Recruiters over-trust the ranking (automation bias)", il=4, ii=3, controls="None", rl=4, ri=3, owner="Head of TA", treatment="Mitigate: sample review of rejects"),
 dict(id="R5", risk="Candidate data used by vendor to train other models", il=3, ii=4, controls="Unknown", rl=3, ri=4, owner="Privacy", treatment="Mitigate: contract clause"),
 dict(id="R6", risk="Silent model change breaches thresholds", il=3, ii=4, controls="None", rl=3, ri=4, owner="Procurement", treatment="Mitigate: change notice and re-audit trigger"),
 dict(id="R7", risk="Tool is not predictive, so no business benefit", il=3, ii=3, controls="None", rl=3, ri=3, owner="People Analytics", treatment="Investigate: validation study"),
]
ACT = [["1", "Suspend production use for age-sensitive and all roles pending remediation", "F1, F2", "Immediate", "Head of Talent Acquisition", "2026-11-09"],
 ["2", "Issue due-diligence questionnaire; collect evidence", "F5", "High", "Procurement", "2026-11-23"],
 ["3", "Vendor removes age and career-gap features; re-submits audit stats incl. equal opportunity and intersectional cuts", "F1 F2 F3", "High", "Vendor / People Analytics", "2026-12-15"],
 ["4", "Independent third-party bias audit; publish summary (LL144)", "F1 F5", "High", "Legal", "2027-01-15"],
 ["5", "Local validation study against hire and performance outcomes", "F4", "Medium", "People Analytics", "2027-01-31"],
 ["6", "Supervised pilot with 10% random review of rejected applicants, monthly impact monitoring, automatic pause below 0.80", "R4", "Medium", "Head of Talent Acquisition", "2027-02-28"],
 ["7", "Add AI due-diligence gate to procurement; add contract clauses (no training, change notice, audit rights)", "F5 R5 R6", "Medium", "Procurement / Legal", "2027-03-31"]]
tbl = lambda grp: [[("Reference" if x["reference"] else ""), x["group"], x["n"], x["rate"], x["ratio"], str(x.get("ci95", "")), pf(x["p"])] for x in grp]
S_DOC = dict(
 title="AI Resume-Screening Tool: Algorithmic Bias and Governance Audit", subtitle="Independent assurance report, second line of defence. Draft for management response.",
 doc_control={"Report reference": "AIG-2026-001", "Version": "1.0 DRAFT", "Date": "2 November 2026", "Prepared by": "AI Governance / GRC analyst", "Reviewed by": "Pending (Head of Risk)", "Distribution": "Chief People Officer, Head of Talent Acquisition, General Counsel, DPO",
  "Classification": "Confidential. Fictional engagement; synthetic data.", "Engagement type": "Pre-deployment assurance of a third-party AI tool", "Next review": "On receipt of vendor questionnaire, or 2026-12-15"},
 opinion=dict(rating="Unsatisfactory", rationale="The tool is not fit for deployment in its current form. Applicants aged 40 and over fail the four-fifths rule at high statistical confidence, and qualified women are disadvantaged in a way the headline metric hides. Eight further control objectives are untested."),
 exec_summary=[f"We tested the vendor's resume-screening tool on a synthetic population of {R['n']:,} applicants who have the same true skill distribution in every group. The tool advances the top {int(R['top_share']*100)}% to a recruiter. Because recruiters rarely open the remaining 75%, a low score functions as an automated rejection, so the tool was assessed as a consequential decision system rather than a recruiter aid.",
  f"Six quantitative control objectives were tested. Five failed and one partially passed. The principal results are: (1) applicants aged 40 and over advance at {age['ratio']} of the rate of younger applicants (CI {age['ci95'][0]} to {age['ci95'][1]}); (2) among equally qualified applicants women advance at {EO['gender']['Female']['ratio']} of the male rate ({pf(EO['gender']['Female']['p'])}), even though the aggregate gender test passes; (3) women aged 40 and over are worst affected at {inter['Female / 40 plus']['ratio']}.",
  f"Ablation testing shows the disparities are removable: removing the age component restores the age ratio to {noage['age_ratio']}, and removing the career-gap component restores the gender ratio to {nogap['gender_ratio']}. Neither removal reduces shortlist quality (share of advanced applicants who are qualified goes from {cur['precision_qualified']}% to {noage['precision_qualified']}% and {nogap['precision_qualified']}%). There is no business-necessity argument for keeping them.",
  "Governance, transparency and oversight controls could not be tested because the vendor has not responded to the due-diligence questionnaire that accompanies this report. They are treated as unevidenced until proven."],
 key_metrics=[["Impact ratio, age 40 plus", age["ratio"], ">= 0.80"], ["Impact ratio, women 40 plus", inter["Female / 40 plus"]["ratio"], ">= 0.80"], ["Equal-opportunity ratio, women", EO["gender"]["Female"]["ratio"], ">= 0.80 and not significant"],
  ["Overall gender impact ratio", fem["ratio"], ">= 0.80 (passes, p = %.2f)" % fem["p"]], ["Impact ratio, age after removing age term", noage["age_ratio"], ">= 0.80"], ["Controls tested / passing", "6 / 0 (1 partial)", "All tested controls pass"], ["Controls untested", "8 of 14", "0"]],
 decisions=["Approve immediate suspension of production use (Action 1).", "Approve issuing the vendor questionnaire with a 15 working day deadline (Action 2).", "Approve the conditions for any future supervised pilot (Action 6) and the procurement control (Action 7)."],
 objective="To provide independent assurance, before wider deployment, on whether the AI resume-screening tool treats applicants fairly, is job-related, and is governed in line with applicable law and recognised AI risk frameworks, and to recommend whether it should be used.",
 scope_in=["Selection outcomes by gender, ethnicity, age and gender by age", "Equal opportunity among qualified applicants", "Proxy variable and feature analysis", "Job-relatedness check", "Governance controls (via questionnaire)"],
 scope_out=["Other vendor products or modules", "Interview and offer stages", "Applicant-facing accessibility testing in person", "Penetration testing of the vendor platform", "Legal advice on specific claims"],
 methodology=["The engagement followed the NIST AI Risk Management Framework (GOVERN, MAP, MEASURE, MANAGE) for structure and ISO/IEC 23894 for the risk process (context, identification, analysis, evaluation, treatment, monitoring). Quantitative criteria come from the EEOC Uniform Guidelines and the NYC Local Law 144 bias-audit method. Legal and regulatory criteria were mapped to control objectives.",
  "Quantitative tests used the full synthetic population (no sampling). Group disparities were assessed with impact ratios, Fisher exact tests, 2,000-sample bootstrap confidence intervals and an equal-opportunity test among truly qualified applicants. Intersectional cuts were examined. Feature ablation (removing one score component at a time) was used to attribute the disparity to causes. Proxy analysis used Mann-Whitney and chi-square tests.",
  "Governance controls cannot be evidenced from outputs alone, so a separate due-diligence questionnaire (Excel workbook, 34 questions, weighted scoring, evidence requests) was prepared. Findings are written as condition, criteria, cause, effect and recommendation. This is a second-line assurance exercise and does not replace first-line ownership of controls or third-line audit."],
 criteria=[["EEOC Uniform Guidelines (29 CFR 1607)", "Four-fifths rule; validation requirement when adverse impact exists"], ["NYC Local Law 144 and DCWP rules", "Impact ratio method, independent annual audit, candidate notice"], ["ADEA, Title VII, ADA, Equality Act 2010", "Protected characteristics and indirect discrimination"],
  ["EU AI Act (Annex III(4), Arts 9 to 15, 26, 86)", "High-risk employment system obligations"], ["GDPR Arts 22 and 35", "Automated decisions, DPIA"], ["NIST AI RMF 1.0", "Structure of governance and measurement activities"], ["ISO/IEC 23894 and ISO/IEC 42001", "Risk process and management system expectations"]],
 rating_scale=[["Satisfactory", "Controls suitably designed and operating; no significant findings"], ["Needs improvement", "Some significant findings; remediation can proceed alongside use"], ["Unsatisfactory", "Critical or multiple high findings; use should stop until remediated"]],
 limitations=["Applicants and outcomes are synthetic; the scoring function is a stand-in for a vendor model whose real behaviour is unknown.", "Protected attributes are available to the tester only because the data is synthetic. In real engagements collecting them for testing needs a lawful basis and separate handling.", "The four-fifths rule is a screening heuristic, not a legal safe harbour. Small cells (for example Asian, Hispanic) need significance and sample-size judgement.", "The validity check is illustrative: in synthetic data the skill-only ceiling holds by construction.", "Governance controls C-07 to C-14 are untested pending vendor evidence."],
 control_tests=CT, figures=[("docs/figures/impact_ratios.png", "Figure 1. Impact ratio by group with 95% bootstrap confidence intervals"), ("docs/figures/ablation.png", "Figure 2. Ablation: which score component drives each disparity")],
 findings=F, risks=RK, actions=ACT,
 appendices=[("Appendix A. Selection outcomes by single attribute", (["Ref", "Group", "N", "Selection %", "Impact ratio", "95% CI", "Fisher p vs reference"], sum([tbl(R["single"][c]) for c in R["single"]], []))),
  ("Appendix B. Intersectional outcomes (gender by age)", (["Ref", "Group", "N", "Selection %", "Impact ratio", "95% CI", "Fisher p vs reference"], tbl(R["intersectional"]))),
  ("Appendix C. Ablation results", (["Variant", "Age ratio", "Gender ratio", "Ethnicity ratio (min)", "% of advanced who are qualified"], [[a["variant"], a["age_ratio"], a["gender_ratio"], a["ethnicity_ratio"], a["precision_qualified"]] for a in R["ablation"]])),
  ("Appendix D. Companion documents", "docs/hr_vendor_due_diligence_questionnaire.xlsx (issued to the vendor), data/applicants.csv, analysis.py and audit.py (reproducible tests), data/audit_stats.json (all statistics quoted above). The audit script asserts that it reproduces the first-stage results, to catch drift."),
  ("Appendix E. Glossary", "Impact ratio: a group's selection rate divided by the highest group's rate. Equal opportunity: equal selection chance among qualified candidates. Proxy: a feature that stands in for a protected characteristic. Ablation: removing one component to measure its effect.")])
render_report(S_DOC, "docs", "AI_Resume_Screening_Audit_Report")

# ---- vendor questionnaire
Q = lambda i, t, g, e, w, k, r: (i, t, g, e, w, k, r)
sections = [
 ("1 Governance and accountability", [
  Q("G01", "Name the executive accountable for AI risk in your company and describe the AI governance structure.", "Named role, reporting line, committee, meeting frequency.", "Org chart, AI policy", 2, "N", "NIST GOVERN 2.1; ISO 42001 5.3"),
  Q("G02", "Do you hold ISO/IEC 42001, ISO/IEC 27001 or SOC 2 Type II certification covering this product?", "Certificate, scope, issuing body, expiry.", "Certificates and scope statements", 2, "N", "ISO 42001; ISO 27001"),
  Q("G03", "Do you maintain an AI risk assessment for this product and review it at least annually?", "Risk register extract, review dates.", "Risk assessment", 2, "N", "NIST MAP 1.x; ISO 23894"),
  Q("G04", "List all sub-processors and third-party or foundation models used.", "Names, location, purpose, contract flow-down.", "Sub-processor list", 3, "N", "GDPR Art 28; EU AI Act Art 25"),
  Q("G05", "State the EU AI Act risk classification you assign to this product and your reasoning.", "Class, Annex reference, conformity route.", "Classification memo", 3, "N", "EU AI Act Annex III(4)")]),
 ("2 Fairness testing and bias audit", [
  Q("B01", "Has an independent auditor performed a bias audit of this tool within the last 12 months?", "Auditor name and independence statement, date, scope.", "Published audit summary", 3, "Y", "NYC LL144; NIST MEASURE 2.11"),
  Q("B02", "Provide selection rates and impact ratios by sex, race/ethnicity and their intersections, and by age band (40 plus).", "Tables with sample sizes, not only ratios.", "Audit tables", 3, "Y", "EEOC UGESP; LL144"),
  Q("B03", "Do you test equal opportunity (selection among qualified candidates), not only overall selection rate?", "Metric definition and results.", "Test report", 3, "N", "NIST MEASURE 2.11"),
  Q("B04", "Do you report statistical significance and confidence intervals, and how do you handle small groups?", "Method, thresholds.", "Method statement", 2, "N", "EEOC UGESP"),
  Q("B05", "List every model input feature and the result of testing each for association with protected characteristics.", "Full feature list, test method, outcomes.", "Feature review", 3, "Y", "EU AI Act Art 10(2)(f)"),
  Q("B06", "Are age-linked features (graduation year, years of experience caps, recency weighting) used? How are they controlled?", "Yes/No per feature and rationale.", "Feature list", 3, "Y", "ADEA"),
  Q("B07", "Describe your remediation process when bias is found, with timelines and customer notification.", "Procedure and past example.", "Procedure", 2, "N", "NIST MANAGE 2.x")]),
 ("3 Data governance and privacy", [
  Q("D01", "Is our applicant data excluded from training or tuning any model used for other customers?", "Contract and technical control.", "DPA clause", 3, "Y", "GDPR Art 5, 28"),
  Q("D02", "Describe training data sources, representativeness and the steps taken to detect and correct bias.", "Sources, dates, populations, labelling.", "Data sheet", 3, "N", "EU AI Act Art 10"),
  Q("D03", "What personal data does the tool process? Is special-category data inferred?", "Data inventory; inference controls.", "Data map", 2, "N", "GDPR Art 9"),
  Q("D04", "State retention periods and deletion procedure, including logs and derived data.", "Periods, method, certificate.", "Retention schedule", 2, "N", "GDPR Art 5(1)(e)"),
  Q("D05", "Is a DPIA completed and available to us? Where is data stored and transferred?", "DPIA, locations, transfer mechanism.", "DPIA, transfer assessment", 2, "N", "GDPR Art 35, 44")]),
 ("4 Transparency, explainability and logging", [
  Q("T01", "Can the tool provide a per-candidate explanation of the factors behind a score?", "Demo and sample output.", "Sample explanations", 3, "N", "EU AI Act Art 13, 86"),
  Q("T02", "Do you log inputs, outputs, model version and user overrides for every decision? For how long?", "Log schema, retention.", "Log sample", 3, "N", "EU AI Act Art 12"),
  Q("T03", "Provide a model card or equivalent covering intended use, limits and known failure modes.", "Document with limits stated.", "Model card", 2, "N", "NIST MAP 2.x"),
  Q("T04", "Provide instructions for use sufficient for us to meet our deployer obligations.", "Instructions, supervision guidance.", "Instructions for use", 2, "N", "EU AI Act Art 13, 26")]),
 ("5 Human oversight, candidate rights and accessibility", [
  Q("H01", "Can a recruiter see and override every automated rejection, and is each override logged?", "Workflow demo.", "Screenshots, log", 3, "Y", "EU AI Act Art 14; GDPR Art 22"),
  Q("H02", "Does the tool support candidate notice, an alternative non-automated process, and a request for human review?", "Features and templates.", "Notice templates", 3, "N", "NYC LL144; GDPR Art 22"),
  Q("H03", "Describe testing for candidates with disabilities and the reasonable-adjustment process.", "Tests, standards (WCAG), process.", "Accessibility report", 2, "N", "ADA; Equality Act"),
  Q("H04", "Do you provide training on limits of the tool and on automation bias for reviewers?", "Materials.", "Training pack", 1, "N", "EU AI Act Art 4, 14")]),
 ("6 Performance validation, change control and incidents", [
  Q("V01", "Provide validation evidence that scores predict job performance for roles like ours.", "Study design, sample, results.", "Validation study", 3, "N", "EEOC UGESP 1607.5; EU AI Act Art 15"),
  Q("V02", "How do you notify customers of model changes, and do you re-run fairness tests before release?", "Notice period, test gate.", "Change policy", 3, "Y", "ISO 42001 8.x"),
  Q("V03", "Do you monitor for drift and fairness degradation in production? Which thresholds trigger action?", "Metrics, thresholds, alerts.", "Monitoring plan", 2, "N", "NIST MEASURE 2.4"),
  Q("V04", "Describe your AI incident process, severity levels and customer notification time.", "Procedure; notice within 72 hours.", "Incident procedure", 2, "N", "EU AI Act Art 73"),
  Q("V05", "Can features or the whole tool be suspended quickly (kill switch)? How fast?", "Mechanism, time to effect.", "Technical description", 2, "N", "NIST MANAGE 2.4")]),
 ("7 Security and contractual", [
  Q("S01", "Do you test for AI-specific attacks (data poisoning, model extraction, adversarial resumes, prompt injection)?", "Test scope and recent results.", "Red-team summary", 2, "N", "OWASP LLM Top 10; NIST MEASURE 2.7"),
  Q("S02", "Will you grant audit rights and provide documentation and test data on request?", "Contract position.", "Contract draft", 3, "N", "EU AI Act Art 26"),
  Q("S03", "Will you indemnify us for claims arising from discriminatory outputs and IP in training data?", "Contract position.", "Contract draft", 2, "N", "Commercial risk"),
  Q("S04", "Will you warrant fairness thresholds (impact ratio, equal opportunity) with remedy and termination rights?", "Contract position.", "Contract draft", 2, "N", "Commercial risk")])]
render_questionnaire(dict(title="AI Hiring Tool: Vendor Due Diligence Questionnaire", purpose="To obtain the evidence needed to assess a third-party AI resume-screening tool against fairness, data protection, transparency, oversight and security expectations before any production use.",
 respondent="Vendor product, legal, security and data science leads. A single named accountable respondent must sign the final submission.",
 instructions=["1. Answer every question in column F using the drop-down. Unsupported claims score half credit.", "2. Put the reference of the evidence document, section and date in column H. Attach documents named in the Evidence request list.", "3. Do not leave answers blank. Use N/A only with an explanation in column G.", "4. Return the workbook within 15 working days of issue. Late or incomplete returns delay any approval.", "5. Statements will be verified; we reserve audit rights. Reviewers complete columns L to O only."],
 scoring=dict(rule="Approve: total score at least 75% and no section under 50% and no knockout answered No. Otherwise Conditional. Reject: any knockout answered No with total under 50%.", approve=75, domain_min=50), sections=sections),
 "docs/hr_vendor_due_diligence_questionnaire.xlsx")
print("done", sum(len(q) for _, q in sections), "questions")
