# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""בונה את .qa/executive-summary.docx (2-4 עמודים, RTL מלא) + גרף-עמודות (matplotlib) מוטמע.
כלים: python-docx, matplotlib, python-bidi - כולם ב-.qa/.venv (מבודד).
הרצה: .qa/.venv/Scripts/python.exe .qa/build_executive_docx.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings_data import FINDINGS, SEVERITY_COLORS, SEVERITY_ORDER, OPEN_QUESTIONS  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from bidi.algorithm import get_display  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt, Cm, RGBColor  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CHART_PATH = os.path.join(HERE, "severity_chart.png")
OUT = os.path.join(HERE, "executive-summary.docx")
FONT = "Arial"

# ======================== עזרי-RTL (python-docx לא חושף API ברמה-גבוהה לזה) ========================


def rtl_paragraph(doc_or_cell, text="", bold=False, size=11, color=None, align=WD_ALIGN_PARAGRAPH.RIGHT,
                   space_after=6, heading=None):
    p = doc_or_cell.add_paragraph(style=heading) if heading else doc_or_cell.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    pPr = p._p.get_or_add_pPr()
    bidi_el = OxmlElement("w:bidi")
    pPr.append(bidi_el)
    if text:
        add_run(p, text, bold=bold, size=size, color=color)
    return p


def add_run(paragraph, text, bold=False, size=11, color=None, italic=False):
    run = paragraph.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rFonts.set(qn(attr), FONT)
    rtl_el = OxmlElement("w:rtl")
    rPr.append(rtl_el)
    return run


def set_table_rtl(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    bidi_el = OxmlElement("w:bidiVisual")
    tblPr.append(bidi_el)


def cell_text(cell, text, bold=False, size=10, color=None, fill=None):
    cell.paragraphs[0].text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pPr = p._p.get_or_add_pPr()
    pPr.append(OxmlElement("w:bidi"))
    add_run(p, text, bold=bold, size=size, color=color)
    if fill:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)


# ======================== נתונים ========================

sev_counts = {"קריטי": 0, "גבוה": 0, "בינוני": 0, "נמוך": 0}
for f in FINDINGS:
    sev_counts[f["severity"]] += 1
legal_findings = [f for f in FINDINGS if f["legal"]]
top5 = sorted(FINDINGS, key=lambda f: (SEVERITY_ORDER[f["severity"]], not f["legal"]))[:5]
open_questions_count = len(OPEN_QUESTIONS)
pending_decision_count = len(FINDINGS)  # כולן ממתינות-להחלטה עד שיסומן findings.xlsx

# ======================== גרף (matplotlib + bidi) ========================

labels_he = ["קריטי", "גבוה", "בינוני", "נמוך"]
labels_display = [get_display(l) for l in labels_he]
values = [sev_counts[l] for l in labels_he]
colors = [f"#{SEVERITY_COLORS[l]}" for l in labels_he]

plt.rcParams["font.family"] = "Arial"
fig, ax = plt.subplots(figsize=(5.5, 2.6), dpi=200)
bars = ax.bar(labels_display, values, color=colors, edgecolor="#444444", linewidth=0.6)
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.3, str(v), ha="center", va="bottom", fontsize=10)
ax.set_title(get_display("ממצאים לפי חומרה"), fontsize=12)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(values) + 3)
plt.tight_layout()
plt.savefig(CHART_PATH)
plt.close(fig)

# ======================== מסמך ========================

doc = Document()
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(section, attr, Cm(2.0))

# כותרת
rtl_paragraph(doc, "דוח QA/אבטחה — maps-gui", bold=True, size=22, color="1F4E79", space_after=2)
rtl_paragraph(doc, "סיכום מנהלים", bold=True, size=14, color="2E74B5", space_after=10)
meta = rtl_paragraph(doc, "", space_after=14)
add_run(meta, "תאריך: 10/11/2026   |   מצב ריצה: מלא (full), אוטונומי   |   ", size=10, color="555555")
add_run(meta, "נקודת ייחוס: commit c1abf7a9 + FR-D-240 (תיקון מאושר-בנפרד)", size=10, color="555555")

# שורה תחתונה
rtl_paragraph(doc, "שורה תחתונה", bold=True, size=13, color="1F4E79", space_after=4)
bottom_line = (
    "הפרויקט פונקציונלי ויציב בבסיסו: מנוע החישוב הבליסטי עבר את כל בדיקות הרגרסיה הקיימות (20/20), "
    "ו-0 חולשות-אבטחה ידועות (CVE) נמצאו בתלויות. לצד זאת נמצאו 28 ממצאים הדורשים החלטה — "
    "4 מהם בעלי חשיפה משפטית/רישוי (⚠️, ר' להלן) ו-5 נוספים בחומרה גבוהה. "
    "האתר/האפליקציה אינם מוכנים להפצה רחבה/מסחרית ללא טיפול בטוקן FlightRadar24 החשוף ובסוגיית-הנגישות "
    "— מעבר לכך, מתאימים להמשך-שימוש אישי/מוגבל כפי שהם."
)
rtl_paragraph(doc, bottom_line, size=11, space_after=14)

# התראות
rtl_paragraph(doc, "⚠️ התראות", bold=True, size=13, color="C00000", space_after=4)
warn_lines = [
    ("F-001", "טוקן FlightRadar24 קשיח וחשוף בתוך ה-APK של Android — יש להעביר קריאות-FR24 דרך שרת-ביניים ולרוטט את הטוקן."),
    ("F-003", "רישוי PyQt5 (Desktop) תקין כרגע (לא בוצעה הפצה) — לבדוק רישיון מסחרי לפני כל הפצת-exe לצד ג׳."),
    ("F-005", "יעד-נגישות (WCAG) תלוי בסטטוס-משפטי של map.yechielalaluf.com שטרם הוכרע — יש לבדוק זאת לפני כל השקעה בתיקון."),
    ("F-013", "חסר ייחוס-OpenStreetMap גלוי במפה, כנדרש לפי רישיון ODbL — תיקון קטן ומהיר."),
]
for fid, text in warn_lines:
    p = rtl_paragraph(doc, "", space_after=4)
    add_run(p, f"⚠️ {fid}: ", bold=True, size=10.5, color="C00000")
    add_run(p, text, size=10.5)
doc.add_paragraph()

# ממצאים לפי חומרה - טבלה + גרף
rtl_paragraph(doc, "ממצאים לפי חומרה", bold=True, size=13, color="1F4E79", space_after=6)
table = doc.add_table(rows=1, cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
set_table_rtl(table)
table.style = "Table Grid"
hdr = table.rows[0].cells
for i, h in enumerate(["חומרה", "מספר", "מהם ⚠️"]):
    cell_text(hdr[i], h, bold=True, size=10, color="FFFFFF", fill="1F4E79")
legal_by_sev = {}
for f in legal_findings:
    legal_by_sev.setdefault(f["severity"], []).append(f["id"])
for sev in ["קריטי", "גבוה", "בינוני", "נמוך"]:
    row = table.add_row().cells
    cell_text(row[0], sev, bold=True, size=10, color="FFFFFF" if sev != "נמוך" else "000000", fill=SEVERITY_COLORS[sev])
    cell_text(row[1], str(sev_counts[sev]), size=10)
    cell_text(row[2], ", ".join(legal_by_sev.get(sev, [])) or "—", size=9)

doc.add_paragraph()
doc.add_picture(CHART_PATH, width=Cm(13))
last_pic_p = doc.paragraphs[-1]
last_pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_page_break()

# 5 הממצאים החשובים
rtl_paragraph(doc, "5 הממצאים החשובים", bold=True, size=13, color="1F4E79", space_after=6)
for f in top5:
    p = rtl_paragraph(doc, "", space_after=2)
    add_run(p, f"{f['id']} ({f['severity']}" + (" ⚠️" if f["legal"] else "") + f") — {f['process']}", bold=True, size=11, color="1F4E79")
    p2 = rtl_paragraph(doc, "", space_after=2)
    add_run(p2, "הבעיה: ", bold=True, size=10)
    add_run(p2, f["desc"], size=10)
    p3 = rtl_paragraph(doc, "", space_after=10)
    add_run(p3, "המלצה: ", bold=True, size=10, color="2E74B5")
    add_run(p3, f["recommended"], size=10)

# מדדי איכות
rtl_paragraph(doc, "מדדי איכות מול קריטריוני יציאה", bold=True, size=13, color="1F4E79", space_after=6)
qtable = doc.add_table(rows=1, cols=3)
set_table_rtl(qtable)
qtable.style = "Table Grid"
qhdr = qtable.rows[0].cells
for i, h in enumerate(["מדד", "קריטריון", "סטטוס"]):
    cell_text(qhdr[i], h, bold=True, size=10, color="FFFFFF", fill="1F4E79")
quality_rows = [
    ("ממצאים קריטיים פתוחים", "0", "0 — עבר", "2E7D32"),
    ("רגרסיה קיימת (self_test+ballistics_api)", "100%", "20/20 — עבר", "2E7D32"),
    ("CVE בתלויות (Desktop+Web)", "0", "0/0 — עבר", "2E7D32"),
    ("Statement/Branch coverage פורמלי", "נמדד", "לא נמדד — לא עבר (לא הותקן כלי)", "C00000"),
    ("Mutation score", "נמדד", "לא בוצע — לא עבר (לא אושר/לא הותקן)", "C00000"),
    ("בדיקות לא-יציבות (flaky)", "0", "לא נבדק (הורץ פעם אחת, לא 5×)", "ED7D31"),
    ("test_requests.py (38/42 TestCase)", "100%", "חסום — דורש mock-layer", "ED7D31"),
]
for name, crit, status, color in quality_rows:
    row = qtable.add_row().cells
    cell_text(row[0], name, size=9.5)
    cell_text(row[1], crit, size=9.5)
    cell_text(row[2], status, size=9.5, color=color, bold=True)

doc.add_paragraph()

# רמות יעד מול בפועל
rtl_paragraph(doc, "רמות יעד מול מצב בפועל", bold=True, size=13, color="1F4E79", space_after=6)
for line in [
    "אבטחה (Web, ASVS): יעד L1 — חלקי. חסר rate-limiting (F-004) ו-auth; שאר L1 בעיקר תקין.",
    "אבטחה (Android, MASVS): יעד L1+P — חלקי. טוקן קשיח (F-001) ו-SharedPreferences לא-מוצפן (F-010) חוסמים L1 מלא.",
    "אבטחה (Desktop): אימוץ-חלקי של ASVS + Microsoft SDL (לא תקן פורמלי) — תקין ברובו.",
    "נגישות (WCAG): יעד לא-הוכרע (F-005) — במצב הנוכחי רחוק מ-AA (touch-targets קטנים, 0 ARIA).",
]:
    p = rtl_paragraph(doc, "", space_after=4)
    add_run(p, "• ", size=11)
    add_run(p, line, size=10.5)

# מה לא נבדק
rtl_paragraph(doc, "מה לא נבדק ולמה, ומה חסום", bold=True, size=13, color="1F4E79", space_after=6)
for line in [
    "test_requests.py (F-022) — חסום: 38/42 בדיקות קוראות ל-APIs חיצוניים אמיתיים, אין mock בפרויקט.",
    "גישה ל-Vercel dashboard/logs (F-007) — לא זמינה לסוכן, נדרשת בדיקת-משתמש.",
    "הרצה על מכשיר/אמולטור Android אמיתי — לא זמין בסביבה.",
    "Mutation Testing / Fuzzing (F-023) — דורש כלים חדשים + זמן-ריצה, לא אושר/בוצע בסבב זה.",
    "בדיקת-נגישות אוטומטית (axe-core/Lighthouse) — דורש Node/npm, לא הותקן.",
]:
    p = rtl_paragraph(doc, "", space_after=4)
    add_run(p, "• ", size=11)
    add_run(p, line, size=10.5)

# השוואה לריצה קודמת
rtl_paragraph(doc, "השוואה לריצה הקודמת", bold=True, size=13, color="1F4E79", space_after=6)
rtl_paragraph(doc,
    "ריצה קודמת (אותו יום) בוצעה תחת נוסח-פרומפט פחות-מדויק והפרה שתי מגבלות-ריצה "
    "(כלי-ניתוח הותקנו מחוץ לסביבה מבודדת; test_requests.py רץ עם קריאות-רשת אמיתיות). "
    "הדוח ותוכנית-התיקונים מאותה ריצה נמחקו לבקשת המשתמש; הריצה הנוכחית תיקנה את שתי החריגות "
    "ומחליפה אותם במלואם. ממצאי Stage 0 (מיפוי-קוד) נשארו ללא שינוי — הקוד לא השתנה בין הריצות.",
    size=10.5, space_after=12)

# הצעד הבא
rtl_paragraph(doc, "הצעד הבא", bold=True, size=13, color="1F4E79", space_after=6)
p = rtl_paragraph(doc, "", space_after=4)
add_run(p, f"נא לסמן את הקובץ findings.xlsx: {pending_decision_count} ממצאים ממתינים להחלטה, "
           f"ו-{open_questions_count} שאלות פתוחות בגיליון 'שאלות פתוחות'. "
           "לאחר שהקובץ יוחזר מסומן, תיבנה תוכנית-עבודה לתיקון (Stage 6) להמתנה-לאישור נוסף.",
    size=10.5)

doc.save(OUT)
print(f"נכתב: {OUT}")
print(f"נכתב גרף: {CHART_PATH}")
