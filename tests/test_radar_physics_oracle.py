# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""T10 (F-051): בדיקות oracle מוחלטות ל-radar_physics.py — ערכים שמחושבים כאן באופן בלתי תלוי (משוואת המכ"ם בתחום dB,
יחסים מדויקים, ערכי קצה), כדי שמוטציה בנוסחה תיתפס (mutation testing, יעד ≥80%).
הרצה: .venv\\Scripts\\python.exe tests/test_radar_physics_oracle.py"""
import math  # חישובי הייחוס
import os  # נתיבים ומשתני סביבה
import sys  # sys.path וקוד יציאה

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
if os.environ.get("QA_MUT_ROOT"):  # mutation testing: העותק המוטנטי בארגז החול קודם לשורש
    sys.path.insert(0, os.environ["QA_MUT_ROOT"])  # קודם בתור
import radar_physics as rp  # noqa: E402  # המודול הנבדק

ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


def close(a, b, rel=1e-9):  # השוואה יחסית
    return abs(a - b) <= rel * max(1.0, abs(b))  # בתוך הסובלנות


# ── משוואת המכ"ם: ייחוס בתחום dB (מימוש שונה מהנבדק) ──
def ref_range(pkw, gdbi, fmhz, rcs, sdbm, ldb=6.0):  # R = [Pt G² λ² σ / ((4π)³ Pmin L)]^(1/4), בחישוב לוגריתמי
    lam = 299792458.0 / (fmhz * 1e6)  # אורך גל
    r4_db = (10 * math.log10(pkw * 1000.0) + 2 * gdbi + 20 * math.log10(lam) + 10 * math.log10(rcs)  # מונה ב-dB
             - 30 * math.log10(4 * math.pi) - (sdbm - 30) - ldb)  # מכנה ב-dB
    return 10 ** (r4_db / 40.0)  # שורש רביעי


base = rp._radar_max_range_m(100, 30, 3000, 2, -100)  # מקרה בסיס
check("משוואת המכ\"ם = ייחוס dB (ברירות מחדל)", close(base, ref_range(100, 30, 3000, 2, -100)), f"{base:.3f}")  # שוויון
for args in [(1, 20, 1000, 0.5, -90, 3), (500, 40, 9000, 10, -120, 8), (0.1, 0, 100, 0.001, -60, 0)]:  # מקרים נוספים
    check(f"משוואת המכ\"ם = ייחוס dB {args}", close(rp._radar_max_range_m(*args), ref_range(*args)))  # שוויון
check("הספק ×2 → טווח ×2^(1/4)", close(rp._radar_max_range_m(200, 30, 3000, 2, -100) / base, 2 ** 0.25))  # יחס מדויק
check("רווח +6dB → טווח ×10^(0.3)", close(rp._radar_max_range_m(100, 36, 3000, 2, -100) / base, 10 ** 0.3))  # R∝G^(1/2)
check("תדר ×2 → טווח ×2^(-1/2)", close(rp._radar_max_range_m(100, 30, 6000, 2, -100) / base, 2 ** -0.5))  # R∝λ^(1/2)
check("RCS ×16 → טווח ×2", close(rp._radar_max_range_m(100, 30, 3000, 32, -100) / base, 2.0))  # R∝σ^(1/4)
check("רגישות -10dB → טווח ×10^(1/4)", close(rp._radar_max_range_m(100, 30, 3000, 2, -110) / base, 10 ** 0.25))  # R∝Pmin^(-1/4)
check("הפסדים +4dB → טווח ×10^(-0.1)", close(rp._radar_max_range_m(100, 30, 3000, 2, -100, 10.0) / base, 10 ** -0.1))  # R∝L^(-1/4)
check("RCS 0 → טווח 0", rp._radar_max_range_m(100, 30, 3000, 0, -100) == 0.0)  # מונה אפס
check("הספק שלילי → טווח 0", rp._radar_max_range_m(-1, 30, 3000, 2, -100) == 0.0)  # מונה שלילי

# ── ריבוד (lobing) ──
lam = 0.1  # אורך גל 10 ס"מ
check("ריבוד בזווית 0 = 1+ρ", close(rp._lobing_factor(0.0, 15.0, lam, 0.5), 1.5))  # Δφ=0
th_pi = math.degrees(math.asin(lam / (4 * 15.0)))  # Δφ=π
check("ריבוד ב-Δφ=π = 1-ρ", close(rp._lobing_factor(th_pi, 15.0, lam, 0.5), 0.5, 1e-9))  # ביטול חלקי
th_half = math.degrees(math.asin(lam / (8 * 15.0)))  # Δφ=π/2
check("ריבוד ב-Δφ=π/2 = √(1+ρ²)", close(rp._lobing_factor(th_half, 15.0, lam, 0.9), math.sqrt(1 + 0.81)))  # ניצב
check("ריבוד ב-Δφ=2π = 1+ρ (מחזוריות)", close(rp._lobing_factor(math.degrees(math.asin(lam / (2 * 15.0))), 15.0, lam, 0.9), 1.9))  # מחזור מלא
check("ריבוד בלי השתקפות (ρ=0) = 1", close(rp._lobing_factor(3.0, 15.0, lam, 0.0), 1.0))  # בלי מכפלה

# ── דופלר (λ=0.1, PRF=1000 → מהירות עיוורת 50 מ'/ש'; MDV=5) ──
dd = lambda v: rp._doppler_detectable(v, 5.0, 0.1, 1000.0)  # noqa: E731  # קיצור
check("מתחת ל-MDV — לא מתגלה", dd(4.9) is False)  # חור סביב אפס
check("בדיוק MDV — מתגלה", dd(5.0) is True)  # גבול
check("3 מ'/ש' מהמהירות העיוורת — לא מתגלה", dd(47.0) is False and dd(53.0) is False)  # בתוך החור
check("בדיוק MDV מהמהירות העיוורת — מתגלה", dd(45.0) is True and dd(55.0) is True)  # גבול החור (לא כולל)
check("כפולה שנייה (100) — לא מתגלה", dd(100.0) is False and dd(98.0) is False)  # n=2
check("בין החורים (75) — מתגלה", dd(75.0) is True and dd(25.0) is True)  # באמצע
check("PRF אפס — אין מהירויות עיוורות", rp._doppler_detectable(50.0, 5.0, 0.1, 0.0) is True)  # מקרה קצה

# ── טווח חד-משמעי, הפרש זוויות, הפסד סריקה ──
check("טווח חד-משמעי ב-PRF 1000 = c/2000", close(rp._max_unambiguous_range_m(1000.0), 149896.229))  # 149,896 מ'
check("טווח חד-משמעי הפוך ל-PRF", close(rp._max_unambiguous_range_m(250.0), 4 * rp._max_unambiguous_range_m(1000.0)))  # יחס
for a, b, exp in [(350, 10, 20), (10, 350, 20), (0, 180, 180), (90, 90, 0), (-30, 30, 60), (720, 0, 0), (0, 181, 179)]:  # מקרים
    check(f"הפרש זוויות {a}↔{b} = {exp}", close(rp._angular_diff_deg(a, b), exp))  # הקצר ביותר
check("הפסד סריקה ב-0° = 1", close(rp._scan_loss_factor(0, 0, 60), 1.0))  # כיוון הפנים
check("הפסד סריקה ב-30° = √cos30", close(rp._scan_loss_factor(30, 0, 60), math.sqrt(math.cos(math.radians(30)))))  # שורש הקוסינוס
check("הפסד סריקה בדיוק בגבול (60°) עדיין מכוסה", close(rp._scan_loss_factor(60, 0, 60), math.sqrt(0.5)))  # גבול כולל
check("מעבר לזווית הסריקה — 0", rp._scan_loss_factor(61, 0, 60) == 0.0)  # מחוץ לתחום
check("הפסד סריקה דרך צפון (350 מול 10)", close(rp._scan_loss_factor(350, 10, 60), math.sqrt(math.cos(math.radians(20)))))  # עטיפה

# ── קליטת פרמטרים: צמידה, ברירות מחדל, NaN/Inf (T7) ──
P = rp._parse_radar_common_params  # קיצור
d0 = P({})  # ברירות מחדל
check("ברירות מחדל", d0["range_km"] == rp._RADAR_RANGE_KM_DEFAULT and d0["power_kw"] == rp._RADAR_POWER_KW_DEFAULT and d0["reflectivity_key"] == "land")  # ברירות
check("צמידה למעלה ולמטה", P({"power_kw": 1e9})["power_kw"] == rp._RADAR_POWER_KW_MAX and P({"power_kw": -5})["power_kw"] == rp._RADAR_POWER_KW_MIN)  # גבולות
check("טווח מינימלי לא עולה על הטווח", P({"range_km": 10, "min_range_km": 50})["min_range_km"] == P({"range_km": 10})["range_km"])  # תלות
check("כיוון מטרה ופנים מנורמלים ל-0..360", P({"target_heading_deg": -90})["target_heading_deg"] == 270 and P({"boresight_deg": 370})["boresight_deg"] == 10)  # נרמול
check("ערך לא מספרי → ברירת מחדל", P({"gain_dbi": "abc"})["gain_dbi"] == rp._RADAR_GAIN_DBI_DEFAULT)  # טקסט
check("NaN → ברירת מחדל (לא נכנס לחישוב)", P({"freq_mhz": float("nan")})["freq_mhz"] == rp._RADAR_FREQ_MHZ_DEFAULT)  # T7
check("Inf → ברירת מחדל", P({"h_antenna": float("inf")})["h_antenna"] == rp._RADAR_H_ANTENNA_DEFAULT_M and P({"prf_hz": float("-inf")})["prf_hz"] == rp._RADAR_PRF_HZ_DEFAULT)  # T7
check("השתקפות/אנטנה לא מוכרות → ברירת מחדל", P({"reflectivity": "lava", "antenna_type": "x"})["reflectivity_key"] == "land" and P({"antenna_type": "x"})["antenna_type"] == "generic")  # בחירה
check("lobing_enabled רק 'true'", P({"lobing_enabled": "true"})["lobing_enabled"] is True and P({"lobing_enabled": "yes"})["lobing_enabled"] is False)  # מתג

print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
