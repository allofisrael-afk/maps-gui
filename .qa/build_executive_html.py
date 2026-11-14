# -*- coding: utf-8 -*-
"""בונה את .qa/executive-summary.html - גרסה מקומית, קריאה-בלבד, של סיכום-המנהלים (מקביל ל-.docx,
לא תחליף לו - שני הקבצים קיימים). self-contained: הגרף מוטמע כ-base64 כדי שהקובץ יהיה נייד.
הרצה: .venv/Scripts/python.exe .qa/build_executive_html.py (stdlib בלבד, לא דורש .qa/.venv)"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings_data import FINDINGS, SEVERITY_COLORS, SEVERITY_ORDER, OPEN_QUESTIONS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CHART_PATH = os.path.join(HERE, "severity_chart.png")
OUT = os.path.join(HERE, "executive-summary.html")

# סבב 4 (12/11/2026): הנגזרות למטה הן data-driven (לא רשימות-F-ID קשיחות) בדיוק כדי שהקובץ הזה
# לא יתיישן שוב בכל סבב עתידי - "פתוח" / "סגור" / "התייתר" נקבעים ישירות משדה status, לא משוכפלים כאן.
def _is_resolved(status):
    return status.startswith("תוקן") or status.startswith("עבר")

def _is_moot(status):
    return "לא-רלוונטי בפועל" in status

open_findings = [f for f in FINDINGS if not _is_resolved(f["status"]) and not _is_moot(f["status"])]
resolved_findings = [f for f in FINDINGS if _is_resolved(f["status"])]
moot_findings = [f for f in FINDINGS if _is_moot(f["status"])]

sev_counts = {"קריטי": 0, "גבוה": 0, "בינוני": 0, "נמוך": 0}
for f in FINDINGS:
    sev_counts[f["severity"]] += 1
legal_findings = [f for f in FINDINGS if f["legal"]]
open_legal_findings = [f for f in open_findings if f["legal"]]
top5 = sorted(open_findings, key=lambda f: (SEVERITY_ORDER[f["severity"]], not f["legal"]))[:5]

chart_b64 = ""
if os.path.exists(CHART_PATH):
    with open(CHART_PATH, "rb") as f:
        chart_b64 = base64.b64encode(f.read()).decode("ascii")

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

warn_items = [(f["id"], f["desc"]) for f in open_legal_findings]

quality_rows = [
    ("ממצאים קריטיים פתוחים", "0", f"0 — עבר" if not any(f["severity"] == "קריטי" for f in open_findings) else "נמצאו — לא עבר", "pass" if not any(f["severity"] == "קריטי" for f in open_findings) else "fail"),
    ("רגרסיה קיימת (self_test+ballistics_api)", "100%", "2/2 — עבר", "pass"),
    ("4 בדיקות-שחזור Stage 6 (F-011/012/013/014)", "100%", "4/4 CLOSED — עבר", "pass"),
    ("mock-layer ל-test_requests.py (F-022)", "100%", "37/37 — עבר, 0 קריאות-רשת אמיתיות", "pass"),
    ("CVE בתלויות (Desktop+Web)", "0", "0/0 — עבר (אומת מחדש בסבב 4)", "pass"),
    ("ASVS 5.0 L1 פורמלי (Desktop)", "0 פערים", "30/30 דרישות נבדקו, 0 פתוחות — עבר", "pass"),
    ("Statement/Branch coverage פורמלי", "נמדד", "לא נמדד — לא עבר", "fail"),
    ("Mutation score", "נמדד", "לא בוצע — לא עבר", "fail"),
]

target_lines = [
    "אבטחה (Desktop, ASVS 5.0 L1): יעד הורחב ל-L1 פורמלי מלא (בקשת המשתמש) — **הושג**. 30 דרישות-L1 נבדקו מול המקור הרשמי, 0 פערים פתוחים (ר' .qa/asvs_l1_desktop_compliance.md).",
    "אבטחה (Web, ASVS): יעד התייתר — map.yechielalaluf.com ירד לגמרי ולא יוחזר (אישור המשתמש). F-004/005/006/007 סומנו לא-רלוונטיים.",
    "אבטחה (Android, MASVS): יעד L1+P — חלקי, ללא שינוי בסבב זה. טוקן FR24 קשיח (F-001, הושאר כמו-שהוא באישור מפורש) ו-SharedPreferences לא-מוצפן (F-010, accepted-risk) חוסמים L1 מלא.",
    "נגישות (WCAG): F-005 (יעד-WCAG) התייתר עם Web. F-026/F-027 (touch-targets/ARIA) חלק-Android נשאר פתוח בעדיפות-נמוכה, לא טופל בסבב זה.",
]
not_tested_lines = [
    "גישה ל-Vercel dashboard/logs (F-007) — התייתרה: Web ירד לגמרי, אין יותר תשתית-חיה לבדוק.",
    "הרצה על מכשיר/אמולטור Android אמיתי — עדיין לא זמינה בסביבה.",
    "Mutation Testing / Fuzzing (F-023) — נדחה-מפורש בסבב זה (Q-4).",
    "SBOM פורמלי (F-024) — נדחה-מפורש בסבב זה (Q-5), אין דרישה רגולטורית פעילה.",
    "בדיקת-נגישות אוטומטית (axe-core/Lighthouse) — דורש Node/npm, לא הותקן.",
]

HTML = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>סיכום מנהלים — maps-gui QA</title>
<style>
  :root {{ --accent:#1F4E79; --accent2:#2E74B5; --ink:#1a1a1a; --muted:#6b7280; --line:#e2e6ea;
          --crit:#d32f2f; --high:#ed7d31; --med:#c99a00; --low:#808080; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: Arial, "Segoe UI", sans-serif; background:#f4f6f8; color:var(--ink); }}
  .page {{ max-width: 860px; margin: 0 auto; padding: 28px 22px 60px; }}
  .masthead {{ background:var(--accent); color:#fff; border-radius:10px; padding:20px 26px; margin-bottom:22px; }}
  .masthead h1 {{ margin:0 0 4px; font-size:22px; }}
  .masthead .sub {{ font-size:14px; color:#cfe0ef; margin-bottom:8px; }}
  .masthead .meta {{ font-size:12px; color:#bcd4ea; }}
  section {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:18px 22px; margin-bottom:18px; }}
  h2 {{ font-size:16px; color:var(--accent); margin:0 0 12px; border-bottom:2px solid var(--accent); padding-bottom:6px; }}
  .bottom-line {{ font-size:14px; line-height:1.8; }}
  .warn {{ border-right:4px solid #c00000; background:#fdecec; border-radius:6px; padding:8px 12px; margin-bottom:8px; font-size:13px; }}
  .warn b {{ color:#c00000; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ border:1px solid var(--line); padding:7px 10px; text-align:right; }}
  th {{ background:var(--accent); color:#fff; }}
  .sev-badge {{ display:inline-block; padding:2px 10px; border-radius:10px; color:#fff; font-weight:bold; }}
  .chart {{ text-align:center; margin-top:14px; }}
  .chart img {{ max-width:100%; }}
  .finding {{ margin-bottom:14px; padding-bottom:12px; border-bottom:1px dashed var(--line); }}
  .finding:last-child {{ border-bottom:none; margin-bottom:0; padding-bottom:0; }}
  .finding .fid {{ font-weight:bold; color:var(--accent); }}
  .finding .rec {{ color:var(--accent2); }}
  ul.plain {{ margin:0; padding-right:20px; font-size:13.5px; line-height:1.9; }}
  .status-pass {{ color:#2e7d32; font-weight:bold; }}
  .status-fail {{ color:#c00000; font-weight:bold; }}
  .status-warn {{ color:#b26a00; font-weight:bold; }}
  .nextstep {{ background:#eef6ee; border-right:4px solid #4caf50; border-radius:6px; padding:12px 16px; font-size:13.5px; }}
  .print-note {{ text-align:center; font-size:11px; color:var(--muted); margin-top:20px; }}
  @media print {{ body {{ background:#fff; }} section {{ box-shadow:none; }} }}
</style>
</head>
<body>
<div class="page">

  <div class="masthead">
    <h1>דוח QA/אבטחה — maps-gui</h1>
    <div class="sub">סיכום מנהלים (גרסה מקומית לקריאה — ר' גם executive-summary.docx)</div>
    <div class="meta">תאריך: 12/11/2026 &nbsp;|&nbsp; סבב 4 (ריצה רביעית) &nbsp;|&nbsp; נקודת ייחוס: working tree נוכחי, לא commit מסוים</div>
  </div>

  <section>
    <h2>שורה תחתונה</h2>
    <div class="bottom-line">
      מתוך 30 הממצאים (28 מהמחזור המקורי + 2 שנמצאו בסבב-האימות הזה), <b>{n_resolved} תוקנו/נסגרו</b>,
      <b>{n_moot} התייתרו</b> (map.yechielalaluf.com ירד לגמרי ולא יוחזר — אישור מפורש של המשתמש),
      ונותרו <b>{n_open} פתוחים</b> — מהם {n_open_legal} בעלי חשיפה משפטית/רישוי (⚠️).
      Stage 6 (תיקון) בוצע ואומת: רגרסיה 2/2, 4/4 בדיקות-שחזור, 37/37 בדיקות-mock, 0 CVE,
      וביקורת ASVS 5.0 L1 פורמלית ל-Desktop (30/30 דרישות, 0 פערים פתוחים). סבב-האימות הזה (round 4)
      אישר שכל תיקוני-Stage-6 עומדים בפועל ומצא 2 ממצאים חדשים — שניהם בכלי-הבדיקה של ה-QA עצמו,
      לא בקוד ה-production.
    </div>
  </section>

  <section>
    <h2>⚠️ התראות</h2>
    {warnings_html}
  </section>

  <section>
    <h2>ממצאים לפי חומרה</h2>
    <table>
      <tr><th>חומרה</th><th>מספר</th><th>מהם ⚠️</th></tr>
      {severity_rows_html}
    </table>
    <div class="chart">{chart_html}</div>
  </section>

  <section>
    <h2>הממצאים הפתוחים החשובים (מתוך {n_open} שנותרו)</h2>
    {top5_html}
  </section>

  <section>
    <h2>מדדי איכות מול קריטריוני יציאה</h2>
    <table>
      <tr><th>מדד</th><th>קריטריון</th><th>סטטוס</th></tr>
      {quality_rows_html}
    </table>
  </section>

  <section>
    <h2>רמות יעד מול מצב בפועל</h2>
    <ul class="plain">{target_html}</ul>
  </section>

  <section>
    <h2>מה לא נבדק ולמה, ומה חסום</h2>
    <ul class="plain">{not_tested_html}</ul>
  </section>

  <section>
    <h2>השוואה לסבבים הקודמים</h2>
    <div class="bottom-line">
      זהו הסבב הרביעי של המחזור. המשתמש מילא וסימן את 28 הממצאים המקוריים ב-<b>findings_form.html</b>;
      ההחלטות בוצעו ב-<b>Stage 6</b> (תיקוני-קוד F-011/012/014/015/016/019, תיקון-בדיקה ל-F-013 שהתגלה
      כ-false-positive, ביקורת ASVS-L1 פורמלית חדשה, ו-mock-layer ל-F-022). סבב 4 הזה היה סבב-<b>אימות</b>
      (לא מיפוי-מחדש — אין פיצ'רים חדשים/משטח-תקיפה חדש מאז Stage 6): אימת כל תיקון מול git diff בפועל,
      הריץ ניתוח-סטטי מלא והשווה מדויק מול בייסליין-הסבב-הקודם, ובדק flakiness על הרגרסיה (8+ ריצות).
      מצא 2 ממצאים חדשים (F-029/F-030, ר' למטה) — שניהם בכלי-הבדיקה, לא בקוד production.
    </div>
  </section>

  <section>
    <h2>הצעד הבא</h2>
    <div class="nextstep">
      נותרו <b>{n_open} ממצאים פתוחים בלבד</b> ({open_ids_str}) — כולם accepted-risk/נדחה-מפורש/חלקי-באישור,
      לא ממצאים שלא טופלו מחדל. ניתן למלא עדכון ב-<b>findings_form.html</b> (שומר JSON) או ב-<b>findings.xlsx</b>
      אם יש החלטה חדשה על מי מהם — אחרת, אין פעולה נדרשת כרגע.
    </div>
  </section>

  <div class="print-note">נוצר אוטומטית מתוך findings_data.py — ר' .qa/STAGE5_FINAL_REPORT.md לדוח המלא.</div>
</div>
</body>
</html>
"""

warnings_html = "\n".join(
    f'<div class="warn"><b>⚠️ {esc(fid)}:</b> {esc(text)}</div>' for fid, text in warn_items
)

sev_rows = []
for sev in ["קריטי", "גבוה", "בינוני", "נמוך"]:
    ids = ", ".join(f["id"] for f in legal_findings if f["severity"] == sev) or "—"
    color = SEVERITY_COLORS[sev]
    text_color = "#fff" if sev != "נמוך" else "#000"
    sev_rows.append(
        f'<tr><td><span class="sev-badge" style="background:#{color};color:{text_color}">{esc(sev)}</span></td>'
        f'<td>{sev_counts[sev]}</td><td>{esc(ids)}</td></tr>'
    )
severity_rows_html = "\n".join(sev_rows)

chart_html = f'<img src="data:image/png;base64,{chart_b64}" alt="גרף ממצאים לפי חומרה">' if chart_b64 else "<em>גרף לא נמצא (severity_chart.png חסר)</em>"

top5_parts = []
for f in top5:
    legal_mark = " ⚠️" if f["legal"] else ""
    top5_parts.append(
        f'<div class="finding"><div><span class="fid">{esc(f["id"])} ({esc(f["severity"])}{legal_mark})</span> — {esc(f["process"])}</div>'
        f'<div>הבעיה: {esc(f["desc"])}</div>'
        f'<div class="rec">המלצה: {esc(f["recommended"])}</div></div>'
    )
top5_html = "\n".join(top5_parts)

quality_rows_html = "\n".join(
    f'<tr><td>{esc(name)}</td><td>{esc(crit)}</td><td class="status-{cls}">{esc(status)}</td></tr>'
    for name, crit, status, cls in quality_rows
)

target_html = "\n".join(f"<li>{esc(line)}</li>" for line in target_lines)
not_tested_html = "\n".join(f"<li>{esc(line)}</li>" for line in not_tested_lines)

open_ids_str = ", ".join(f["id"] for f in open_findings) if open_findings else "—"
final_html = HTML.format(
    warnings_html=warnings_html,
    severity_rows_html=severity_rows_html,
    chart_html=chart_html,
    top5_html=top5_html,
    quality_rows_html=quality_rows_html,
    target_html=target_html,
    not_tested_html=not_tested_html,
    nq=len(OPEN_QUESTIONS),
    n_resolved=len(resolved_findings),
    n_moot=len(moot_findings),
    n_open=len(open_findings),
    n_open_legal=len(open_legal_findings),
    open_ids_str=open_ids_str,
)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(final_html)
print(f"נכתב: {OUT}")
