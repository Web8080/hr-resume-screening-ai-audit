"""grc_kit: turn a structured assurance spec into (a) an audit-style report in .docx, .pdf and .md and
(b) a separate due-diligence questionnaire workbook (.xlsx) with dropdowns, evidence columns and scoring formulas.
Report structure follows common internal-audit practice (IIA / ISACA): opinion, objective, scope, criteria,
approach, results, findings as condition / criteria / cause / effect / recommendation, action plan, management response."""
import os, subprocess, html, textwrap

RATING_COL = {"Critical": "C0392B", "High": "E67E22", "Medium": "F1C40F", "Low": "27AE60", "Informational": "5DADE2",
              "Unsatisfactory": "C0392B", "Needs improvement": "E67E22", "Satisfactory": "27AE60", "Effective": "27AE60",
              "Partially effective": "F1C40F", "Ineffective": "C0392B", "FAIL": "C0392B", "PARTIAL": "F1C40F", "PASS": "27AE60", "NOT TESTED": "BDC3C7"}

def risk_score(l, i): return l * i
def risk_band(s): return "Critical" if s >= 20 else "High" if s >= 12 else "Medium" if s >= 6 else "Low"

# ---------------------------------------------------------------- blocks
def build_blocks(s):
    B = []; h = lambda lvl, t: B.append(("h", lvl, t)); p = lambda t: B.append(("p", t))
    B.append(("title", s["title"], s["subtitle"]))
    h(1, "1. Document control")
    B.append(("table", ["Field", "Detail"], [[k, v] for k, v in s["doc_control"].items()]))
    h(1, "2. Executive summary")
    o = s["opinion"]
    B.append(("callout", f"Overall opinion: {o['rating']}", o["rationale"], o["rating"]))
    for para in s["exec_summary"]: p(para)
    if s.get("key_metrics"): B.append(("table", ["Key measure", "Result", "Benchmark / criterion"], s["key_metrics"]))
    h(2, "Decision requested"); B.append(("bullets", s["decisions"]))
    h(1, "3. Objective and scope")
    p(s["objective"])
    B.append(("table", ["In scope", "Out of scope"], [[a, b] for a, b in zip(s["scope_in"] + [""] * 9, s["scope_out"] + [""] * 9)][:max(len(s["scope_in"]), len(s["scope_out"]))]))
    h(1, "4. Methodology and criteria")
    for para in s["methodology"]: p(para)
    B.append(("table", ["Criteria source", "How it was used"], s["criteria"]))
    h(2, "Assurance rating scale")
    B.append(("table", ["Rating", "Meaning"], [[a, b] for a, b in s["rating_scale"]]))
    h(2, "Limitations and assumptions"); B.append(("bullets", s["limitations"]))
    h(1, "5. Results of control testing")
    p(s.get("control_intro", "Each control objective was tested against the stated criteria. Results are PASS, PARTIAL or FAIL, with the test performed and the evidence relied on."))
    B.append(("table", ["Ref", "Control objective", "Test performed", "Result", "Evidence / finding"], s["control_tests"]))
    for fig in s.get("figures", []): B.append(("img", fig[0], fig[1]))
    h(1, "6. Detailed findings")
    for f in s["findings"]:
        h(2, f"{f['id']}  {f['title']}  [{f['rating']}]")
        B.append(("finding", f))
    h(1, "7. Risk assessment")
    p(s.get("risk_intro", "Risks are scored on a 5 by 5 likelihood and impact matrix. Inherent risk assumes no controls. Residual risk assumes the controls currently in place. Bands: 20 to 25 Critical, 12 to 19 High, 6 to 11 Medium, 1 to 5 Low."))
    rr = []
    for r in s["risks"]:
        i, res = risk_score(r["il"], r["ii"]), risk_score(r["rl"], r["ri"])
        rr.append([r["id"], r["risk"], f"{r['il']}x{r['ii']}={i} ({risk_band(i)})", r["controls"], f"{r['rl']}x{r['ri']}={res} ({risk_band(res)})", r["owner"], r["treatment"]])
    B.append(("table", ["ID", "Risk", "Inherent", "Existing controls", "Residual", "Owner", "Treatment"], rr))
    h(1, "8. Recommendations and action plan")
    B.append(("table", ["#", "Action", "Addresses", "Priority", "Owner", "Target date"], s["actions"]))
    h(1, "9. Management response")
    p("Responses below are drafted for the accountable owner to confirm, amend or reject. An accepted risk requires a named executive signature and an expiry date.")
    B.append(("table", ["Finding", "Proposed response", "Accept / Amend / Reject", "Owner sign-off"], [[f["id"], f["mgmt_response"], "Pending", "Pending"] for f in s["findings"]]))
    h(1, "10. Appendices")
    for t, body in s.get("appendices", []):
        h(2, t)
        if isinstance(body, tuple): B.append(("table", body[0], body[1]))
        else: p(body)
    return B

# ---------------------------------------------------------------- markdown
def esc(x): return str(x).replace("|", "/").replace("\n", " ")
def render_md(B):
    out = []
    for b in B:
        k = b[0]
        if k == "title": out += [f"# {b[1]}", f"*{b[2]}*", ""]
        elif k == "h": out += ["", "#" * (b[1] + 1) + " " + b[2], ""]
        elif k == "p": out += [b[1], ""]
        elif k == "bullets": out += [f"- {x}" for x in b[1]] + [""]
        elif k == "callout": out += [f"> **{b[1]}**  ", f"> {b[2]}", ""]
        elif k == "table":
            out += ["| " + " | ".join(esc(c) for c in b[1]) + " |", "|" + "---|" * len(b[1])]
            out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in b[2]] + [""]
        elif k == "img": out += [f"![{b[2]}]({os.path.relpath(b[1], 'docs') if False else b[1]})", f"*{b[2]}*", ""]
        elif k == "finding":
            f = b[1]
            rows = [["Rating", f["rating"]], ["Condition (what we found)", f["condition"]], ["Criteria (what should be)", f["criteria"]],
                    ["Cause", f["cause"]], ["Effect (risk)", f["effect"]], ["Recommendation", f["recommendation"]],
                    ["Framework references", f["refs"]], ["Owner / target", f["owner"]]]
            out += ["| Field | Detail |", "|---|---|"] + [f"| **{a}** | {esc(c)} |" for a, c in rows] + [""]
    return "\n".join(out)

# ---------------------------------------------------------------- docx
def render_docx(B, path):
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    d = Document()
    sec = d.sections[0]; sec.left_margin = sec.right_margin = Cm(2); sec.top_margin = sec.bottom_margin = Cm(2)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10)
    def shade(cell, hexcol):
        tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hexcol); tcPr.append(sh)
    def table(header, rows, widths=None):
        t = d.add_table(rows=1, cols=len(header)); t.style = "Table Grid"
        for i, c in enumerate(header):
            cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(str(c)); r.bold = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(255, 255, 255); shade(cell, "1F3A5F")
        for row in rows:
            cells = t.add_row().cells
            for i, c in enumerate(row):
                cells[i].text = ""; run = cells[i].paragraphs[0].add_run(str(c)); run.font.size = Pt(9)
                for key, col in RATING_COL.items():
                    if str(c).startswith(key) and len(str(c)) < 40 and key in ("Critical", "High", "Medium", "Low", "FAIL", "PARTIAL", "PASS", "NOT TESTED"):
                        shade(cells[i], col); run.bold = True; break
        d.add_paragraph()
    for b in B:
        k = b[0]
        if k == "title":
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.LEFT; r = p.add_run(b[1]); r.bold = True; r.font.size = Pt(24); r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
            p2 = d.add_paragraph(); r2 = p2.add_run(b[2]); r2.italic = True; r2.font.size = Pt(12)
        elif k == "h": d.add_heading(b[2], level=b[1])
        elif k == "p": d.add_paragraph(b[1])
        elif k == "bullets":
            for x in b[1]: d.add_paragraph(x, style="List Bullet")
        elif k == "callout":
            t = d.add_table(rows=1, cols=1); t.style = "Table Grid"; c = t.rows[0].cells[0]; shade(c, RATING_COL.get(b[3], "BDC3C7"))
            c.text = ""; r = c.paragraphs[0].add_run(b[1]); r.bold = True; r.font.size = Pt(12); c.add_paragraph(b[2]); d.add_paragraph()
        elif k == "table": table(b[1], b[2])
        elif k == "img":
            if os.path.exists(b[1]): d.add_picture(b[1], width=Cm(16)); cp = d.add_paragraph(b[2]); cp.runs[0].italic = True
        elif k == "finding":
            f = b[1]; t = d.add_table(rows=0, cols=2); t.style = "Table Grid"
            for a, c in [("Rating", f["rating"]), ("Condition", f["condition"]), ("Criteria", f["criteria"]), ("Cause", f["cause"]), ("Effect", f["effect"]),
                         ("Recommendation", f["recommendation"]), ("Framework references", f["refs"]), ("Owner / target", f["owner"])]:
                cells = t.add_row().cells; cells[0].text = ""; rr = cells[0].paragraphs[0].add_run(a); rr.bold = True; shade(cells[0], "E8EDF3")
                cells[1].text = str(c)
                if a == "Rating": shade(cells[1], RATING_COL.get(c, "BDC3C7"))
                cells[0].width = Cm(4); cells[1].width = Cm(13)
            d.add_paragraph()
    d.save(path)

# ---------------------------------------------------------------- pdf (markdown -> html -> chromium)
CSS = """body{font:11px/1.45 Calibri,Segoe UI,Arial,sans-serif;color:#1c2430;max-width:980px;margin:24px auto;padding:0 18px}
h1{color:#1F3A5F;font-size:22px;border-bottom:2px solid #1F3A5F;padding-bottom:4px;margin-top:26px}h2{color:#1F3A5F;font-size:15px;margin-top:20px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:10px}th{background:#1F3A5F;color:#fff;text-align:left;padding:5px}td{border:1px solid #cfd6df;padding:5px;vertical-align:top}
blockquote{border-left:5px solid #E67E22;background:#fdf3e7;margin:10px 0;padding:8px 12px}img{max-width:100%}tr{page-break-inside:avoid}h1,h2{page-break-after:avoid}"""
def render_pdf(md_text, path, tmp_html):
    import markdown
    body = markdown.markdown(md_text, extensions=["tables"])
    for key, col in (("PASS", "#d5f0df"), ("FAIL", "#f6d3cf"), ("PARTIAL", "#fbf0c4")):
        body = body.replace(f"<td>{key}</td>", f'<td style="background:{col};font-weight:700">{key}</td>')
    for key, col in (("Critical", "#f6d3cf"), ("High", "#fbe0c8"), ("Medium", "#fbf0c4"), ("Low", "#d5f0df")):
        body = body.replace(f"<td>{key}</td>", f'<td style="background:{col};font-weight:700">{key}</td>')
    open(tmp_html, "w").write(f"<!doctype html><meta charset=utf-8><style>{CSS}</style>{body}")
    js = f"const {{chromium}}=require('playwright');(async()=>{{const b=await chromium.launch();const p=await b.newPage();await p.goto('file://{os.path.abspath(tmp_html)}');await p.pdf({{path:'{os.path.abspath(path)}',format:'A4',margin:{{top:'14mm',bottom:'14mm',left:'12mm',right:'12mm'}},printBackground:true}});await b.close()}})()"
    subprocess.run(["node", "-e", js], check=True)

def render_report(spec, outdir, base):
    os.makedirs(outdir, exist_ok=True)
    B = build_blocks(spec); md = render_md(B).replace(f"]({outdir}/", "](")
    # figures are referenced relative to the md file location
    open(f"{outdir}/{base}.md", "w").write(md)
    render_docx(B, f"{outdir}/{base}.docx")
    render_pdf(md.replace("](figures/", f"]({os.path.abspath(outdir)}/figures/"), f"{outdir}/{base}.pdf", f"/tmp/{base}.html")
    return md

# ---------------------------------------------------------------- questionnaire workbook
def render_questionnaire(q, path):
    """q: dict(title, purpose, respondent, instructions[], scoring{}, sections=[(name, [(id, question, guidance, evidence, weight, knockout, refs)])])"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule
    wb = Workbook(); H = PatternFill("solid", fgColor="1F3A5F"); HF = Font(bold=True, color="FFFFFF"); thin = Side(style="thin", color="BBBBBB"); BR = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws = wb.active; ws.title = "Instructions"; ws.column_dimensions["A"].width = 120
    rows = [q["title"], "", "Purpose", q["purpose"], "", "Who completes this", q["respondent"], "", "How to answer"] + q["instructions"] + ["", "Response scale (column F)", "Yes - evidenced = control exists AND you attach evidence (score 2)", "Partial / claimed = exists in part, or no evidence supplied (score 1)", "No / not in place = (score 0)", "N/A = not applicable, state why in Comments (excluded from score)", "", "Knockout questions (column D = Y): a 'No' blocks approval unless a named executive signs a documented exception."]
    for i, t in enumerate(rows, 1):
        c = ws.cell(i, 1, t); c.alignment = Alignment(wrap_text=True, vertical="top")
        if t in ("Purpose", "Who completes this", "How to answer", "Response scale (column F)"): c.font = Font(bold=True, size=12)
    ws["A1"].font = Font(bold=True, size=16, color="1F3A5F")
    wq = wb.create_sheet("Questionnaire"); heads = ["ID", "Section", "Question", "Knockout", "Weight", "Vendor response", "Vendor comments", "Evidence reference (document, section, date)", "Guidance (what a good answer contains)", "Evidence requested", "Framework refs", "Reviewer score (0-2)", "Weighted score", "Reviewer notes", "Follow-up required"]
    for i, hd in enumerate(heads, 1):
        c = wq.cell(1, i, hd); c.fill = H; c.font = HF; c.alignment = Alignment(wrap_text=True, vertical="center"); c.border = BR
    widths = [7, 22, 60, 9, 8, 18, 36, 30, 45, 30, 22, 12, 12, 30, 16]
    for i, w in enumerate(widths, 1): wq.column_dimensions[chr(64 + i)].width = w
    r = 2; first = r
    dv = DataValidation(type="list", formula1='"Yes - evidenced,Partial / claimed,No / not in place,N/A"', allow_blank=True); wq.add_data_validation(dv)
    dv2 = DataValidation(type="list", formula1='"Y,N"', allow_blank=True); wq.add_data_validation(dv2)
    dsc = DataValidation(type="whole", operator="between", formula1="0", formula2="2", allow_blank=True); wq.add_data_validation(dsc)
    for sname, qs in q["sections"]:
        for (qid, text, guide, ev, w, ko, refs) in qs:
            vals = [qid, sname, text, ko, w, "", "", "", guide, ev, refs, "", None, "", ""]
            for i, v in enumerate(vals, 1):
                c = wq.cell(r, i, v); c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = BR
            wq.cell(r, 13, f'=IF(OR(L{r}="",F{r}="N/A"),"",L{r}*E{r})')
            dv.add(wq.cell(r, 6)); dsc.add(wq.cell(r, 12)); dv2.add(wq.cell(r, 15))
            for col in (6, 7, 8): wq.cell(r, col).fill = PatternFill("solid", fgColor="FFF9E5")
            r += 1
    last = r - 1; wq.freeze_panes = "D2"; wq.auto_filter.ref = f"A1:O{last}"
    wq.conditional_formatting.add(f"F2:F{last}", CellIsRule(operator="equal", formula=['"No / not in place"'], fill=PatternFill("solid", bgColor="F6D3CF")))
    wq.conditional_formatting.add(f"F2:F{last}", CellIsRule(operator="equal", formula=['"Yes - evidenced"'], fill=PatternFill("solid", bgColor="D5F0DF")))
    wq.conditional_formatting.add(f"F2:F{last}", CellIsRule(operator="equal", formula=['"Partial / claimed"'], fill=PatternFill("solid", bgColor="FBF0C4")))
    sc = wb.create_sheet("Scoring"); sh = ["Section", "Max weighted score", "Scored", "Section score %", "Knockouts answered No"]
    for i, hd in enumerate(sh, 1):
        c = sc.cell(1, i, hd); c.fill = H; c.font = HF
    for n, (sname, qs) in enumerate(q["sections"], 2):
        sc.cell(n, 1, sname)
        sc.cell(n, 2, f'=SUMPRODUCT((Questionnaire!$B${first}:$B${last}=A{n})*(Questionnaire!$F${first}:$F${last}<>"N/A")*Questionnaire!$E${first}:$E${last})*2')
        sc.cell(n, 3, f'=SUMIFS(Questionnaire!$M${first}:$M${last},Questionnaire!$B${first}:$B${last},A{n})')
        sc.cell(n, 4, f'=IF(B{n}=0,"",ROUND(100*C{n}/B{n},0))')
        sc.cell(n, 5, f'=COUNTIFS(Questionnaire!$B${first}:$B${last},A{n},Questionnaire!$D${first}:$D${last},"Y",Questionnaire!$F${first}:$F${last},"No / not in place")')
    n = len(q["sections"]) + 2
    sc.cell(n, 1, "TOTAL").font = Font(bold=True); sc.cell(n, 2, f"=SUM(B2:B{n-1})"); sc.cell(n, 3, f"=SUM(C2:C{n-1})"); sc.cell(n, 4, f'=IF(B{n}=0,"",ROUND(100*C{n}/B{n},0))'); sc.cell(n, 5, f"=SUM(E2:E{n-1})")
    sc.cell(n + 2, 1, "Decision rule").font = Font(bold=True)
    sc.cell(n + 3, 1, q["scoring"]["rule"])
    sc.cell(n + 4, 1, "Recommended outcome (auto)").font = Font(bold=True)
    th = q["scoring"]["approve"]; mn = q["scoring"]["domain_min"]
    sc.cell(n + 4, 2, f'=IF(E{n}>0,IF(D{n}<50,"REJECT","CONDITIONAL"),IF(AND(D{n}>={th},MIN(D2:D{n-1})>={mn}),"APPROVE","CONDITIONAL"))')
    sc.cell(n + 4, 2).font = Font(bold=True)
    for col, w in zip("ABCDE", (46, 20, 12, 16, 22)): sc.column_dimensions[col].width = w
    ev = wb.create_sheet("Evidence request list"); 
    for i, hd in enumerate(["Ref", "Document requested", "Linked question", "Received (Y/N)", "Date", "Reviewer"], 1):
        c = ev.cell(1, i, hd); c.fill = H; c.font = HF
    k = 2
    for sname, qs in q["sections"]:
        for (qid, text, guide, evd, w, ko, refs) in qs:
            ev.cell(k, 1, f"E{k-1:03d}"); ev.cell(k, 2, evd); ev.cell(k, 3, qid); k += 1
    for col, w in zip("ABCDEF", (8, 60, 14, 14, 12, 16)): ev.column_dimensions[col].width = w
    wb.save(path)
