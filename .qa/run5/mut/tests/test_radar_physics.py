# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות radar_physics.py — בעיקר תיקון המהירויות העיוורות (FR-D-280): חור ברוחב קבוע ±MDV סביב אפס וסביב
כל מהירות עיוורת n·λ·PRF/2. הבדיקה המרכזית: בכפולה גבוהה (n=20) מהירות באמצע בין שתי מהירויות עיוורות
*מתגלה* — בגרסה הקודמת (חור של 5% מהמהירות העיוורת) היא סומנה עיוורת.
הרצה: python tests/test_radar_physics.py
"""
import os  # נתיב שורש
import sys  # sys.path וקוד יציאה

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט

import radar_physics as rp  # המודול הנבדק
import weather_server as ws  # השרת — חייב להשתמש בדיוק באותן פונקציות

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # עברית בקונסולה
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

results = []  # תוצאות


def check(name, cond, info=""):
    """רושם ומדפיס בדיקה."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


WL = 0.1  # אורך גל 10 ס"מ (3 GHz)
PRF = 1000.0  # Hz
VB = WL * PRF / 2.0  # מהירות עיוורת בסיסית: 50 מ'/ש'
MDV = 5.0  # מ'/ש'

check("מתחת ל-MDV — עיוור (רקע נייח)", not rp._doppler_detectable(3.0, MDV, WL, PRF))
check("בדיוק על מהירות עיוורת (n=1) — עיוור", not rp._doppler_detectable(VB, MDV, WL, PRF))
check("בתוך ±MDV סביב n=1 — עיוור", not rp._doppler_detectable(VB + 4.0, MDV, WL, PRF))
check("מחוץ ל-±MDV סביב n=1 — מתגלה", rp._doppler_detectable(VB + 6.0, MDV, WL, PRF))
check("n=20: באמצע בין מהירויות עיוורות — מתגלה (התיקון)", rp._doppler_detectable(20.5 * VB, MDV, WL, PRF), f"v={20.5 * VB}")
check("n=20: בתוך ±MDV — עדיין עיוור", not rp._doppler_detectable(20 * VB + 3.0, MDV, WL, PRF))
old_tolerance_would_block = abs(20.5 * VB - 20 * VB) <= 0.05 * (20 * VB)  # הכלל הישן: 25 <= 50 -> עיוור
check("אימות: לפי הכלל הישן אותה מהירות סומנה עיוורת", old_tolerance_would_block)
check("MDV=0 — אין חורים בכלל", rp._doppler_detectable(VB, 0.0, WL, PRF) and rp._doppler_detectable(0.5, 0.0, WL, PRF))
frac = sum(1 for k in range(10000, 100000) if not rp._doppler_detectable(k / 100.0, MDV, WL, PRF)) / 90000.0  # חלק המהירויות העיוורות — דגימה כל 1 ס"מ/ש'
check("שבר המהירויות העיוורות ≈ 2·MDV/v_b (20%)", abs(frac - 2 * MDV / VB) < 0.02, f"{frac * 100:.1f}%")
check("השרת משתמש באותה פונקציה בדיוק (מקור אמת אחד)", ws._doppler_detectable is rp._doppler_detectable
      and ws._radar_max_range_m is rp._radar_max_range_m and ws._parse_radar_common_params is rp._parse_radar_common_params)
p = rp._parse_radar_common_params({"rcs_m2": "99999", "prf_hz": "x", "antenna_type": "bogus"})  # צמידה וברירות מחדל
check("קליטת פרמטרים: צמידה, ברירת מחדל לערך לא מספרי ולסוג לא מוכר",
      p["rcs_m2"] == rp._RADAR_RCS_M2_MAX and p["prf_hz"] == rp._RADAR_PRF_HZ_DEFAULT and p["antenna_type"] == "generic")

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה
