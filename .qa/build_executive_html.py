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

sev_counts = {"קריטי": 0, "גבוה": 0, "בינוני": 0, "נמוך": 0}
for f in FINDINGS:
    sev_counts[f["severity"]] += 1
legal_findings = [f for f in FINDINGS if f["legal"]]
top5 = sorted(FINDINGS, key=lambda f: (SEVERITY_ORDER[f["severity"]], not f["legal"]))[:5]

chart_b64 = ""
if os.path.exists(CHART_PATH):
    with open(CHART_PATH, "rb") as f:
        chart_b64 = base64.b64encode(f.read()).decode("ascii")

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

warn_items = [
    ("F-001", "טוקן FlightRadar24 קשיח וחשוף בתוך ה-APK של Android — יש להעביר קריאות-FR24 דרך שרת-ביניים ולרוטט את הטוקן."),
    ("F-003", "רישוי PyQt5 (Desktop) תקין כרגע (לא בוצעה הפצה) — לבדוק רישיון מסחרי לפני כל הפצת-exe לצד ג׳."),
    ("F-005", "יעד-נגישות (WCAG) תלוי בסטטוס-משפטי של map.yechielalaluf.com שטרם הוכרע — יש לבדוק זאת לפני כל השקעה בתיקון."),
    ("F-013", "חסר ייחוס-OpenStreetMap גלוי במפה, כנדרש לפי רישיון ODbL — תיקון קטן ומהיר."),
]

quality_rows = [
    ("ממצאים קריטיים פתוחים", "0", "0 — עבר", "pass"),
    ("רגרסיה קיימת (self_test+ballistics_api)", "100%", "20/20 — עבר", "pass"),
    ("CVE בתלויות (Desktop+Web)", "0", "0/0 — עבר", "pass"),
    ("Statement/Branch coverage פורמלי", "נמדד", "לא נמדד — לא עבר", "fail"),
    ("Mutation score", "נמדד", "לא בוצע — לא עבר", "fail"),
    ("בדיקות לא-יציבות (flaky)", "0", "לא נבדק (הורץ פעם אחת)", "warn"),
    ("test_requests.py (38/42 TestCase)", "100%", "חסום — דורש mock-layer", "warn"),
]

target_lines = [
    "אבטחה (Web, ASVS): יעד L1 — חלקי. חסר rate-limiting (F-004) ו-auth; שאר L1 בעיקר תקין.",
    "אבטחה (Android, MASVS): יעד L1+P — חלקי. טוקן קשיח (F-001) ו-SharedPreferences לא-מוצפן (F-010) חוסמים L1 מלא.",
    "אבטחה (Desktop): אימוץ-חלקי של ASVS + Microsoft SDL (לא תקן פורמלי) — תקין ברובו.",
    "נגישות (WCAG): יעד לא-הוכרע (F-005) — במצב הנוכחי רחוק מ-AA (touch-targets קטנים, 0 ARIA).",
]
not_tested_lines = [
    "test_requests.py (F-022) — חסום: 38/42 בדיקות קוראות ל-APIs חיצוניים אמיתיים, אין mock בפרויקט.",
    "גישה ל-Vercel dashboard/logs (F-007) — לא זמינה לסוכן, נדרשת בדיקת-משתמש.",
    "הרצה על מכשיר/אמולטור Android אמיתי — לא זמין בסביבה.",
    "Mutation Testing / Fuzzing (F-023) — דורש כלים חדשים + זמן-ריצה, לא אושר/בוצע בסבב זה.",
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
    <div class="meta">תאריך: 10/11/2026 &nbsp;|&nbsp; מצב ריצה: מלא (full), אוטונומי &nbsp;|&nbsp; נקודת ייחוס: commit c1abf7a9 + FR-D-240</div>
  </div>

  <section>
    <h2>שורה תחתונה</h2>
    <div class="bottom-line">
      הפרויקט פונקציונלי ויציב בבסיסו: מנוע החישוב הבליסטי עבר את כל בדיקות הרגרסיה הקיימות (20/20),
      ו-0 חולשות-אבטחה ידועות (CVE) נמצאו בתלויות. לצד זאת נמצאו 28 ממצאים הדורשים החלטה —
      4 מהם בעלי חשיפה משפטית/רישוי (⚠️) ו-5 נוספים בחומרה גבוהה. האתר/האפליקציה אינם מוכנים
      להפצה רחבה/מסחרית ללא טיפול בטוקן FlightRadar24 החשוף ובסוגיית-הנגישות — מעבר לכך,
      מתאימים להמשך-שימוש אישי/מוגבל כפי שהם.
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
    <h2>5 הממצאים החשובים</h2>
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
    <h2>השוואה לריצה הקודמת</h2>
    <div class="bottom-line">
      ריצה קודמת (אותו יום) בוצעה תחת נוסח-פרומפט פחות-מדויק והפרה שתי מגבלות-ריצה
      (כלי-ניתוח הותקנו מחוץ לסביבה מבודדת; test_requests.py רץ עם קריאות-רשת אמיתיות).
      הדוח ותוכנית-התיקונים מאותה ריצה נמחקו לבקשת המשתמש; הריצה הנוכחית תיקנה את שתי החריגות
      ומחליפה אותם במלואם. ממצאי Stage 0 (מיפוי-קוד) נשארו ללא שינוי — הקוד לא השתנה בין הריצות.
    </div>
  </section>

  <section>
    <h2>הצעד הבא</h2>
    <div class="nextstep">
      נא לסמן את הקובץ <b>findings.xlsx</b> (או למלא את <b>findings_form.html</b> ולהוריד JSON) —
      28 ממצאים ממתינים להחלטה, ו-{nq} שאלות פתוחות. לאחר שהתשובות יוחזרו, תיבנה תוכנית-עבודה
      לתיקון (Stage 6) להמתנה-לאישור נוסף.
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

final_html = HTML.format(
    warnings_html=warnings_html,
    severity_rows_html=severity_rows_html,
    chart_html=chart_html,
    top5_html=top5_html,
    quality_rows_html=quality_rows_html,
    target_html=target_html,
    not_tested_html=not_tested_html,
    nq=len(OPEN_QUESTIONS),
)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(final_html)
print(f"נכתב: {OUT}")
