# -*- coding: utf-8 -*-
"""בונה את .qa/findings.xlsx מתוך findings_data.py (מקור-אמת יחיד, ר' אותו קובץ).
הרצה: .qa/.venv/Scripts/python.exe .qa/build_findings_xlsx.py"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings_data import FINDINGS, SEVERITY_COLORS, by_severity, OPEN_QUESTIONS, RUN_DECISIONS  # noqa: E402

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.protection import SheetProtection

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "findings.xlsx")

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
EDITABLE_FILL = PatternFill("solid", fgColor="DDEBF7")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top", horizontal="right", readingOrder=2)
WRAP_CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center", readingOrder=2)

IMPACT_BY_SCOPE = {
    "קטן": "מינימלי - קובץ/שורה בודדים, לא צפוי להשפיע על רכיבים אחרים.",
    "בינוני": "מתון - ייתכן שיידרש לתאם עם רכיבים תלויים ולהריץ רגרסיה מלאה.",
    "גדול": "משמעותי - משפיע על ארכיטקטורה/ממשק; נדרש תכנון ובדיקה נרחבת.",
    "אין": "ללא השפעה - אין שינוי-קוד.",
}


def setup_sheet(ws, n_header_rows=1):
    ws.sheet_view.rightToLeft = True
    # בכוונה לא משתמשים ב-ws.cell(...).coordinate כאן: עצם הגישה ל-cell ביצירת-שורה חדשה
    # "נוגעת" בשורה (גם בלי לכתוב ערך) ומזיזה את כל ה-.append() הבאים שורה אחת קדימה -
    # נמצא בפועל (כל הגיליונות הודפסו עם 1-2 שורות ריקות לפני הנתונים האמיתיים).
    ws.freeze_panes = f"A{n_header_rows + 1}"


def style_header_row(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = WRAP_CENTER
        cell.border = BORDER


wb = Workbook()

# ============ גיליון 1: סיכום ============
ws1 = wb.active
ws1.title = "סיכום"
setup_sheet(ws1, 0)

sev_counts = {"קריטי": 0, "גבוה": 0, "בינוני": 0, "נמוך": 0}
for f in FINDINGS:
    sev_counts[f["severity"]] += 1
legal_findings = [f for f in FINDINGS if f["legal"]]

rows = [
    ["דוח QA/אבטחה — maps-gui — קובץ סימון ממצאים", ""],
    ["תאריך", "10/11/2026"],
    ["מצב ריצה", "מלא (full), אוטונומי"],
    ["נקודת ייחוס לקוד", "commit c1abf7a9 + FR-D-240 (תיקון מאושר-בנפרד)"],
    ["", ""],
    ["ספירת ממצאים לפי חומרה", ""],
    ["קריטי", sev_counts["קריטי"]],
    ["גבוה", sev_counts["גבוה"]],
    ["בינוני", sev_counts["בינוני"]],
    ["נמוך", sev_counts["נמוך"]],
    ["סה\"כ", len(FINDINGS)],
    ["", ""],
    ["⚠️ התראות (סיכון משפטי/חשיפה)", f"{len(legal_findings)} פריטים: " + ", ".join(f["id"] for f in legal_findings)],
    ["", ""],
    ["הוראות", "בגיליון 'ממצאים': מלא/י את העמודות הכחולות (החלטה, עדיפות, הערות שלי) לכל שורה."],
    ["", "בגיליון 'שאלות פתוחות': ענה/עני בעמודה 'התשובה שלי'."],
    ["", "בגיליון 'החלטות בריצה': אם ברצונך לשנות החלטה שהתקבלה אוטונומית, סמן/י 'כן' בעמודת 'לשנות?' והוסף/י הערה."],
    ["", "שאר הגיליונות/העמודות נעולים לעריכה (בלי סיסמה) כדי שלא ישתנו בטעות."],
]
for r in rows:
    ws1.append(r)
ws1.column_dimensions["A"].width = 38
ws1.column_dimensions["B"].width = 70
for row in ws1.iter_rows(min_row=1, max_row=len(rows)):
    for cell in row:
        cell.alignment = WRAP
ws1["A1"].font = Font(bold=True, size=14, color="1F4E79")
ws1["A6"].font = Font(bold=True)
ws1["A13"].font = Font(bold=True, color="C00000")
ws1["A15"].font = Font(bold=True)
sev_cell_map = {7: "קריטי", 8: "גבוה", 9: "בינוני", 10: "נמוך"}
for r, sev in sev_cell_map.items():
    ws1.cell(row=r, column=2).fill = PatternFill("solid", fgColor=SEVERITY_COLORS[sev])
    ws1.cell(row=r, column=2).font = Font(bold=True, color="FFFFFF" if sev != "נמוך" else "000000")

# ============ גיליון 2: ממצאים ============
ws2 = wb.create_sheet("ממצאים")
setup_sheet(ws2, 1)

BASE_COLS = ["מזהה", "חומרה", "⚠️", "קטגוריה", "תהליך", "תיאור", "צעדים לשחזור",
             "תוצאה צפויה", "תוצאה בפועל", "סטטוס", "מיקום בקוד", "דרישה / CWE", "בדיקה משחזרת"]
ALT_COLS = ["תיאור", "יתרונות", "חסרונות", "היקף שינוי", "השפעה על רכיבים אחרים"]
ALT_LABELS = ["חלופה א", "חלופה ב", "חלופה ג"]
EDIT_COLS = ["המלצה", "החלטה", "עדיפות", "הערות שלי"]

header = list(BASE_COLS)
for label in ALT_LABELS:
    header += [f"{label} - {c}" for c in ALT_COLS]
header += EDIT_COLS
ws2.append(header)
style_header_row(ws2, 1, len(header))

n_base = len(BASE_COLS)
n_alt_block = len(ALT_COLS)
editable_col_start = n_base + 3 * n_alt_block + 1  # 1-indexed col of "המלצה" (not editable itself, but decision/priority/notes after it are)
decision_col = editable_col_start + 1
priority_col = editable_col_start + 2
notes_col = editable_col_start + 3

for f in by_severity():
    row = [f["id"], f["severity"], "⚠️" if f["legal"] else "", f["category"], f["process"],
           f["desc"], f["repro"], f["expected"], f["actual"], f["status"], f["location"],
           f["requirement"], f["test"]]
    for i in range(3):
        if i < len(f["alts"]):
            a = f["alts"][i]
            row += [a["name"] + " - " + a["desc"], a["pros"], a["cons"], a["scope"], IMPACT_BY_SCOPE.get(a["scope"], "")]
        else:
            row += ["", "", "", "", ""]
    row += [f["recommended"], "", "", ""]  # המלצה + 3 editable
    ws2.append(row)

n_data_rows = len(FINDINGS)
last_row = n_data_rows + 1
ws2.auto_filter.ref = f"A1:{ws2.cell(row=1, column=len(header)).coordinate[:-1]}{last_row}"

widths = {1: 9, 2: 10, 3: 5, 4: 16, 5: 26, 6: 42, 7: 30, 8: 28, 9: 28, 10: 12, 11: 30, 12: 24, 13: 30}
for i in range(1, n_base + 1):
    col_letter = ws2.cell(row=1, column=i).column_letter
    ws2.column_dimensions[col_letter].width = widths.get(i, 20)
for i in range(n_base + 1, editable_col_start + 4):
    col_letter = ws2.cell(row=1, column=i).column_letter
    ws2.column_dimensions[col_letter].width = 26
ws2.column_dimensions[ws2.cell(row=1, column=decision_col).column_letter].width = 18
ws2.column_dimensions[ws2.cell(row=1, column=priority_col).column_letter].width = 14
ws2.column_dimensions[ws2.cell(row=1, column=notes_col).column_letter].width = 30

severity_col_letter = "B"
for r in range(2, last_row + 1):
    for c in range(1, len(header) + 1):
        cell = ws2.cell(row=r, column=c)
        cell.alignment = WRAP
        cell.border = BORDER
        cell.protection = cell.protection.copy(locked=True)
    sev = ws2.cell(row=r, column=2).value
    sev_cell = ws2.cell(row=r, column=2)
    sev_cell.fill = PatternFill("solid", fgColor=SEVERITY_COLORS[sev])
    sev_cell.font = Font(bold=True, color="FFFFFF" if sev != "נמוך" else "000000")
    for c in (decision_col, priority_col, notes_col):
        cell = ws2.cell(row=r, column=c)
        cell.fill = EDITABLE_FILL
        cell.protection = cell.protection.copy(locked=False)

dv_decision = DataValidation(type="list", formula1='"חלופה א,חלופה ב,חלופה ג,לפי ההמלצה,לא לתקן,לדיון"', allow_blank=True)
ws2.add_data_validation(dv_decision)
dv_decision.add(f"{ws2.cell(row=2, column=decision_col).column_letter}2:{ws2.cell(row=2, column=decision_col).column_letter}{last_row}")

dv_priority = DataValidation(type="list", formula1='"1 דחוף,2 רגיל,3 בהמשך"', allow_blank=True)
ws2.add_data_validation(dv_priority)
dv_priority.add(f"{ws2.cell(row=2, column=priority_col).column_letter}2:{ws2.cell(row=2, column=priority_col).column_letter}{last_row}")

ws2.protection = SheetProtection(sheet=True, password=None)
ws2.protection.formatCells = False
ws2.protection.sort = False
ws2.protection.autoFilter = False

# ============ גיליון 3: חלופות מורחב ============
ws3 = wb.create_sheet("חלופות מורחב")
setup_sheet(ws3, 1)
ws3.append(["מזהה ממצא", "חלופה", "תיאור מלא", "יתרונות", "חסרונות", "היקף שינוי", "השפעה על רכיבים אחרים"])
style_header_row(ws3, 1, 7)
EXPANDED_IDS = {"F-001", "F-004", "F-006", "F-010", "F-022"}
r = 2
for f in FINDINGS:
    if f["id"] not in EXPANDED_IDS:
        continue
    for a in f["alts"]:
        ws3.append([f["id"], a["name"], a["desc"], a["pros"], a["cons"], a["scope"], IMPACT_BY_SCOPE.get(a["scope"], "")])
        r += 1
for col, w in zip("ABCDEFG", [10, 26, 44, 34, 34, 14, 36]):
    ws3.column_dimensions[col].width = w
for row in ws3.iter_rows(min_row=2, max_row=ws3.max_row):
    for cell in row:
        cell.alignment = WRAP
        cell.border = BORDER
        cell.protection = cell.protection.copy(locked=True)
ws3.auto_filter.ref = f"A1:G{ws3.max_row}"
ws3.protection = SheetProtection(sheet=True, password=None)

# ============ גיליון 4: שאלות פתוחות ============
ws4 = wb.create_sheet("שאלות פתוחות")
setup_sheet(ws4, 1)
ws4.append(["מזהה", "נושא", "הסבר מונחים", "אפשרויות ומשמעותן", "המלצה", "התשובה שלי"])
style_header_row(ws4, 1, 6)

for q in OPEN_QUESTIONS:
    ws4.append([q["id"], q["topic"], q["terms"], q["options"], q["recommendation"], ""])
for col, w in zip("ABCDEF", [8, 24, 40, 50, 40, 30]):
    ws4.column_dimensions[col].width = w
for row in ws4.iter_rows(min_row=2, max_row=ws4.max_row):
    for i, cell in enumerate(row, start=1):
        cell.alignment = WRAP
        cell.border = BORDER
        cell.protection = cell.protection.copy(locked=(i != 6))
        if i == 6:
            cell.fill = EDITABLE_FILL
ws4.auto_filter.ref = f"A1:F{ws4.max_row}"
ws4.protection = SheetProtection(sheet=True, password=None)

# ============ גיליון 5: החלטות בריצה ============
ws5 = wb.create_sheet("החלטות בריצה")
setup_sheet(ws5, 1)
ws5.append(["#", "החלטה", "נימוק", "לשנות?", "הערה"])
style_header_row(ws5, 1, 5)
for d in RUN_DECISIONS:
    ws5.append([d["num"], d["decision"], d["rationale"], "", ""])
for col, w in zip("ABCDE", [5, 46, 50, 10, 30]):
    ws5.column_dimensions[col].width = w
for row in ws5.iter_rows(min_row=2, max_row=ws5.max_row):
    for i, cell in enumerate(row, start=1):
        cell.alignment = WRAP
        cell.border = BORDER
        cell.protection = cell.protection.copy(locked=(i < 4))
        if i >= 4:
            cell.fill = EDITABLE_FILL

dv_change = DataValidation(type="list", formula1='"כן,לא"', allow_blank=True)
ws5.add_data_validation(dv_change)
dv_change.add(f"D2:D{ws5.max_row}")
ws5.auto_filter.ref = f"A1:E{ws5.max_row}"
ws5.protection = SheetProtection(sheet=True, password=None)

wb.save(OUT)
print(f"נכתב: {OUT}")
print(f"ממצאים: {len(FINDINGS)}, שאלות-פתוחות: {len(OPEN_QUESTIONS)}, החלטות-ריצה: {len(RUN_DECISIONS)}")
