"""Render results.json into a static dashboard.html (no dependencies)."""
import json, sys, html

COL = {"good": "#1a7f4b", "warn": "#b7791f", "bad": "#c0392b", "info": "#2b6cb0"}

def bar_chart(c):
    rows = []
    mx = c.get("max") or max([i["value"] for i in c["items"]] + [c.get("threshold", {}).get("value", 0)]) * 1.1
    th = c.get("threshold")
    for i in c["items"]:
        w = max(1, min(100, i["value"] / mx * 100))
        col = COL[i.get("status", "info")]
        rows.append(
            f'<div class="row"><div class="lbl">{html.escape(i["label"])}</div>'
            f'<div class="track"><div class="fill" style="width:{w:.1f}%;background:{col}"></div>'
            + (f'<div class="th" style="left:{th["value"]/mx*100:.1f}%"></div>' if th else "")
            + f'</div><div class="val">{i["value"]:g}{c.get("unit","")}</div></div>')
    note = f'<div class="note">Dashed line: {html.escape(th["label"])}</div>' if th else ""
    return f'<section class="card"><h3>{html.escape(c["title"])}</h3>{"".join(rows)}{note}</section>'

def table(t):
    head = "".join(f"<th>{html.escape(h)}</th>" for h in t["columns"])
    body = ""
    for r in t["rows"]:
        tds = ""
        for v in r:
            s = str(v); cls = ""
            if s in ("FAIL", "High", "Critical", "Red", "Reject"): cls = "bad"
            elif s in ("WARN", "Medium", "Amber", "Conditional"): cls = "warn"
            elif s in ("PASS", "Low", "Green", "Approve"): cls = "good"
            tds += f'<td class="{cls}">{html.escape(s)}</td>'
        body += f"<tr>{tds}</tr>"
    return f'<section class="card wide"><h3>{html.escape(t["title"])}</h3><table><tr>{head}</tr>{body}</table></section>'

def render(d):
    k = "".join(
        f'<div class="kpi"><div class="kl">{html.escape(x["label"])}</div>'
        f'<div class="kv" style="color:{COL[x.get("status","info")]}">{html.escape(str(x["value"]))}</div>'
        f'<div class="kn">{html.escape(x.get("note",""))}</div></div>' for x in d["kpis"])
    charts = "".join(bar_chart(c) for c in d.get("charts", []))
    tbl = "".join(table(t) for t in d.get("tables", []))
    verdict = d.get("verdict")
    v = (f'<div class="verdict" style="border-color:{COL[verdict["status"]]}"><b>{html.escape(verdict["label"])}</b> '
         f'{html.escape(verdict["text"])}</div>') if verdict else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(d["title"])}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mut:#667085;--line:#e4e7ec}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif;padding:28px}}
h1{{margin:0 0 4px;font-size:22px}}.sub{{color:var(--mut);margin-bottom:18px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:14px}}
.kpi,.card,.verdict{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.kl{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}}.kv{{font-size:28px;font-weight:700;margin:2px 0}}.kn{{color:var(--mut);font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}}.wide{{grid-column:1/-1}}
h3{{margin:0 0 10px;font-size:15px}}.row{{display:grid;grid-template-columns:150px 1fr 64px;gap:10px;align-items:center;margin:7px 0}}
.lbl{{font-size:13px}}.track{{position:relative;height:16px;background:#eef0f3;border-radius:4px}}.fill{{height:100%;border-radius:4px}}
.th{{position:absolute;top:-3px;bottom:-3px;border-left:2px dashed #344054}}.val{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}}
.note{{color:var(--mut);font-size:12px;margin-top:6px}}table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}}td{{padding:6px 8px;border-bottom:1px solid var(--line)}}
td.bad{{color:#c0392b;font-weight:700}}td.warn{{color:#b7791f;font-weight:700}}td.good{{color:#1a7f4b;font-weight:700}}
.verdict{{border-left-width:5px;margin:14px 0}}.foot{{color:var(--mut);font-size:12px;margin-top:14px}}
</style></head><body><h1>{html.escape(d["title"])}</h1><div class="sub">{html.escape(d["subtitle"])}</div>
<div class="kpis">{k}</div>{v}<div class="grid">{charts}{tbl}</div>
<div class="foot">{html.escape(d.get("footer","Synthetic data for portfolio demonstration. Not a real audit."))}</div></body></html>"""

if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    open(out, "w").write(render(json.load(open(src))))
