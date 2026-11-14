# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""מייצא את findings_data.py ל-JSON - נצרך ע"י findings_form.html (טופס-מילוי מקומי) ו-executive-summary.html.
הרצה: .qa/.venv/Scripts/python.exe .qa/export_data_json.py  (או כל python - אין תלות חיצונית כאן)"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings_data import FINDINGS, SEVERITY_COLORS, OPEN_QUESTIONS, RUN_DECISIONS, by_severity  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_data.json")

data = {
    "meta": {
        "date": "10/11/2026",
        "run_mode": "מלא (full), אוטונומי",
        "commit": "c1abf7a9 + FR-D-240 (תיקון production מאושר-בנפרד)",
    },
    "severity_colors": SEVERITY_COLORS,
    "findings": by_severity(),
    "open_questions": OPEN_QUESTIONS,
    "run_decisions": RUN_DECISIONS,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"נכתב: {OUT}")
print(f"ממצאים: {len(FINDINGS)}, שאלות-פתוחות: {len(OPEN_QUESTIONS)}, החלטות-ריצה: {len(RUN_DECISIONS)}")
