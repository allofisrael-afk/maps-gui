# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — מפיק את .qa/findings.xlsx (5 גיליונות, RTL, רשימות נפתחות, עמודות למילוי בתכלת, השאר נעול בלי סיסמה)
ואת טבלאות הדוח (.qa/run5/_tables.md) מתוך findings_r5.py. אחר כך פותח את הקובץ מחדש ומאמת אותו.
הרצה: .qa\\.venv\\Scripts\\python.exe .qa/run5/build_r5.py"""
import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from findings_r5 import CARRYOVER, DECISIONS, FINDINGS, QUESTIONS, SEV_ORDER  # noqa: E402

OUT = os.path.join(HERE, "..", "findings.xlsx")
FINDINGS.sort(key=lambda f: (SEV_ORDER[f["sev"]], f["id"]))
SEV_FILL = {"קריטי": "F4B6B6", "גבוה": "F8CBA0", "בינוני": "FFF2A8", "נמוך": "DDDDDD"}
EDIT_FILL = PatternFill("solid", fgColor="BDE3F5")  # תכלת — עמודות למילוי
HEAD_FILL = PatternFill("solid", fgColor="2F3B52")
WRAP = Alignment(wrap_text=True, vertical="top", horizontal="right", readingOrder=2)


def sheet(wb, title, headers, widths, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.sheet_view.rightToLeft = True
    ws.append(headers)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
        c = ws.cell(1, i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center", readingOrder=2)
    ws.freeze_panes = "A2"
    return ws


def finish(ws, editable_cols, sev_col=None):
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
            c.protection = Protection(locked=c.column not in editable_cols)
            if c.column in editable_cols:
                c.fill = EDIT_FILL
        if sev_col:
            sev = row[sev_col - 1].value
            if sev in SEV_FILL:
                row[sev_col - 1].fill = PatternFill("solid", fgColor=SEV_FILL[sev])
    ws.auto_filter.ref = ws.dimensions
    ws.protection.sheet = True  # נעילה בלי סיסמה — רק עמודות התכלת ניתנות לעריכה
    ws.protection.autoFilter = False
    ws.protection.sort = False
    ws.protection.formatColumns = False


def dropdown(ws, col_letter, options, n_rows):
    dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{col_letter}2:{col_letter}{n_rows + 1}")


wb = Workbook()
# ── 1. סיכום ──
ws = sheet(wb, "סיכום", ["נושא", "ערך"], [38, 110], first=True)
counts = {s: sum(1 for f in FINDINGS if f["sev"] == s) for s in SEV_ORDER}
rows = [
    ("ריצה", "ריצת QA חמישית — מצב full, אוטונומי, 26/11/2026. נקודת ייחוס: HEAD bfdd312da + שינויים לא מחויבים (FR-D-286/287)."),
    ("היקף", "עומק מלא על ה-delta מאז Stage 7: כלי בדיקת מעקב המכ\"ם (6 מודולי Python, 9 נקודות קצה), ממשק המעקב בדסקטופ ובאנדרואיד, wa-status, ספריית הפרופילים, saved_stations ב-git."),
    ("ממצאים חדשים", f"{len(FINDINGS)} — קריטי {counts['קריטי']}, גבוה {counts['גבוה']}, בינוני {counts['בינוני']}, נמוך {counts['נמוך']}"),
    ("התראות ⚠️", "; ".join(f"{f['id']}: {f['desc'][:70]}…" for f in FINDINGS if f["legal"])),
    ("ממצאים פתוחים מריצות קודמות", "; ".join(f"{a} ({b}) {c} — {d}" for a, b, c, d in CARRYOVER)),
    ("בדיקות", "חבילת הפרויקט: 13/13 קבצים ירוקים (baseline). חדשות ב-.qa/run5/tests: 4 חבילות + fuzz + UI. Flaky: 0 מתוך 50 ריצות."),
    ("כיסוי", "ענפים בליבת המכ\"ם: 89% מהתרחיש המייצג לבדו, 90% עם החבילות הקיימות. Mutation score (radar_physics): 50%."),
    ("אבטחה", "יעד: שרת מקומי ASVS 5.0 L1 (התאמה), אנדרואיד MAS-L1+P. בפועל: לא עומד ב-L1 בגלל F-031/F-032/F-042/F-043."),
    ("נגישות", "יעד WCAG 2.x AA. בפועל: 0 רכיבים בלי שם נגיש; 15 מטרות קטנות (F-040); גרפים בלי חלופה (F-041). קורא מסך לא נבדק ידנית."),
    ("איך לסמן", "בגיליון 'ממצאים' — עמודות התכלת: 'החלטה' (חלופה א/ב/ג, לפי ההמלצה, לא לתקן, לדיון), 'עדיפות' (1/2/3), 'הערות שלי'. "
                 "גם בגיליונות 'שאלות פתוחות' ו'החלטות בריצה'. שאר העמודות נעולות (בלי סיסמה) כדי למנוע שינוי בטעות."),
]
for r in rows:
    ws.append(r)
finish(ws, set())

# ── 2. ממצאים ──
alt_h = []
for L in "אבג":
    alt_h += [f"חלופה {L} — תיאור", f"{L} — יתרונות", f"{L} — חסרונות", f"{L} — היקף", f"{L} — השפעה"]
H = ["מזהה", "חומרה", "⚠️", "קטגוריה", "תהליך", "תיאור", "צעדים לשחזור", "תוצאה צפויה", "תוצאה בפועל", "מיקום בקוד", "דרישה / CWE",
     "בדיקה משחזרת"] + alt_h + ["המלצה", "החלטה", "עדיפות", "הערות שלי"]
W = [8, 8, 4, 11, 22, 55, 35, 28, 32, 28, 28, 26] + [30, 18, 18, 8, 16] * 3 + [26, 16, 12, 30]
ws = sheet(wb, "ממצאים", H, W)
for f in FINDINGS:
    alts = []
    for i in range(3):
        a = f["alts"][i] if i < len(f["alts"]) else None
        alts += [a["desc"], a["pros"], a["cons"], a["scope"], a["impact"]] if a else ["", "", "", "", ""]
    ws.append([f["id"], f["sev"], "⚠️" if f["legal"] else "", f["cat"], f["process"], f["desc"], f["steps"], f["expected"], f["actual"],
               f["loc"], f["req"], f["test"]] + alts + [f["rec"], "", "", ""])
n = len(FINDINGS)
ncol = len(H)
dropdown(ws, ws.cell(1, ncol - 2).column_letter, ["חלופה א", "חלופה ב", "חלופה ג", "לפי ההמלצה", "לא לתקן", "לדיון"], n)
dropdown(ws, ws.cell(1, ncol - 1).column_letter, ["1 דחוף", "2 רגיל", "3 בהמשך"], n)
finish(ws, {ncol - 2, ncol - 1, ncol}, sev_col=2)

# ── 3. חלופות מורחב ──
ws = sheet(wb, "חלופות מורחב", ["מזהה ממצא", "חלופה", "תיאור מלא", "יתרונות", "חסרונות", "היקף", "השפעה על רכיבים אחרים", "מומלצת?"],
           [10, 8, 60, 30, 30, 10, 30, 10])
for f in FINDINGS:
    for i, a in enumerate(f["alts"]):
        letter = "אבג"[i]
        ws.append([f["id"], letter, a["desc"], a["pros"], a["cons"], a["scope"], a["impact"],
                   "כן" if (f"{letter}'" in f["rec"] or f"{letter} " in f["rec"][:3]) else ""])
finish(ws, set())

# ── 4. שאלות פתוחות ──
ws = sheet(wb, "שאלות פתוחות", ["מזהה", "נושא", "הסבר המונחים", "האפשרויות ומשמעותן", "המלצה", "התשובה שלי"], [9, 28, 50, 50, 40, 30])
for q in QUESTIONS:
    ws.append([q["id"], q["topic"], q["terms"], q["options"], q["rec"], ""])
dropdown(ws, "F", ["א", "ב", "ג", "לפי ההמלצה", "אחר — בהערה"], len(QUESTIONS))
finish(ws, {6})

# ── 5. החלטות בריצה ──
ws = sheet(wb, "החלטות בריצה", ["מזהה", "מה הוחלט", "הסבר המונחים", "החלופות", "הנימוק", "מה ישתנה אם תבחר אחרת", "לשנות?", "הערה"],
           [7, 45, 30, 30, 40, 30, 9, 30])
for d in DECISIONS:
    ws.append([d["id"], d["what"], d["terms"], d["alts"], d["why"], d["change"], "", ""])
dropdown(ws, "G", ["כן", "לא"], len(DECISIONS))
finish(ws, {7, 8})
wb.save(OUT)

# ── אימות: פתיחה מחדש ──
wb2 = load_workbook(OUT)
ws2 = wb2["ממצאים"]
ids_x = [ws2.cell(r, 1).value for r in range(2, ws2.max_row + 1)]
assert ids_x == [f["id"] for f in FINDINGS], "חסרים ממצאים ב-Excel"
assert all(wb2[s].sheet_view.rightToLeft for s in wb2.sheetnames), "RTL"
assert len(ws2.data_validations.dataValidation) == 2, "dropdowns"
assert ws2.protection.sheet and not ws2.cell(2, ncol).protection.locked and ws2.cell(2, 6).protection.locked, "נעילה"
assert "קריטי" in [ws2.cell(r, 2).value for r in range(2, ws2.max_row + 1)], "עברית"
print("xlsx OK:", OUT, "| sheets:", wb2.sheetnames, "| findings:", len(ids_x), "| dropdowns: findings=2, questions=1, decisions=1")

# ── טבלאות לדוח ──
md = ["| # | חומרה | ⚠️ | קטגוריה | תהליך | צעדים לשחזור | תוצאה צפויה | תוצאה בפועל | סטטוס | מיקום בקוד | דרישה / CWE |",
      "|---|---|---|---|---|---|---|---|---|---|---|"]
for f in FINDINGS:
    cells = [f["id"], f["sev"], "⚠️" if f["legal"] else "", f["cat"], f["process"], f["steps"], f["expected"], f["actual"], "נכשל",
             f["loc"], f["req"]]
    md.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |")
md += ["", "### חלופות לפתרון לכל ממצא", ""]
for f in FINDINGS:
    md.append(f"**{f['id']} ({f['sev']}{' ⚠️' if f['legal'] else ''}) — {f['process']}.** {f['desc']}")
    md.append("")
    for i, a in enumerate(f["alts"]):
        md.append(f"- **חלופה {'אבג'[i]}:** {a['desc']}. יתרונות: {a['pros'] or '—'}. חסרונות: {a['cons'] or '—'}. היקף: {a['scope']}. השפעה: {a['impact'] or '—'}.")
    md.append(f"- **המלצה:** {f['rec']}")
    md.append("")
md += ["### שאלות פתוחות לאישורך", ""]
for q in QUESTIONS:
    md += [f"**{q['id']} — {q['topic']}.** {q['terms']}", f"- אפשרויות: {q['options']}", f"- המלצה: {q['rec']}", ""]
md += ["### החלטות שהתקבלו בריצה", ""]
for d in DECISIONS:
    md += [f"**{d['id']}.** {d['what']}", f"- מונחים: {d['terms'] or '—'} · חלופות: {d['alts'] or '—'}", f"- נימוק: {d['why']}",
           f"- אם תבחר אחרת: {d['change'] or '—'}", ""]
with open(os.path.join(HERE, "_tables.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(md))
print("tables:", len(FINDINGS), "findings,", len(QUESTIONS), "questions,", len(DECISIONS), "decisions")
