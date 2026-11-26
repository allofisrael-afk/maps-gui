# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות מודל הרקטה (rocket_model.py), שלב א6 — בלי רשת. העיקרית: שיגור אנכי בוואקום מול הפתרון האנליטי
(משוואת ציולקובסקי עם הפסד כובד), שמאמתת את האינטגרציה, את ירידת המסה ואת הדחף.
הרצה: python tests/test_rocket_model.py
"""
import math  # הפתרון האנליטי
import os  # נתיב שורש הפרויקט
import sys  # sys.path וקוד יציאה

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט

import rocket_model as rm  # המודול הנבדק
from mpm.atmosphere import AtmosphereProfile  # האטמוספרה של מנוע ה-MPM (סטנדרטית)
from mpm.geodesy import direct as geo_direct, inverse as geo_inverse  # הגיאודזיה של ה-MPM

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # עברית תקינה בקונסולה
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

results = []  # תוצאות


def check(name, cond, info=""):
    """רושם ומדפיס בדיקה."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # שורת פלט


class Vacuum:
    """אטמוספרה ריקה: צפיפות אפס, בלי רוח — כדי להשוות לפתרון אנליטי."""
    def at(self, h):  # אותו ממשק כמו AtmosphereProfile.at
        return 0.0, 340.0, 288.15, 0.0, 0.0, 0.0  # rho, a, T, P, we, wn


LAUNCH = {"lat": 31.25, "lon": 34.80, "alt_m": 100.0}  # משגר סינתטי
ROCKET = {"mass_kg": 100.0, "prop_kg": 40.0, "burn_s": 10.0, "thrust_n": 5000.0, "diam_m": 0.15, "cd": 0.4}  # רקטה רעיונית

# ── 1. שיגור אנכי בוואקום מול האנליטי ──
r = rm.simulate(LAUNCH, 90.0, 0.0, ROCKET, Vacuum(), geo_direct=geo_direct)
g, m0, m1, tb, T = rm.G0, 100.0, 60.0, 10.0, 5000.0  # קבועים
mdot = (m0 - m1) / tb  # קצב הדלק
ve = T / mdot  # מהירות הפליטה האפקטיבית
v_b = ve * math.log(m0 / m1) - g * tb  # מהירות בסוף הבעירה
h_b = ve * (tb - (m1 / mdot) * math.log(m0 / m1)) - g * tb * tb / 2.0  # גובה בסוף הבעירה
apex = h_b + v_b * v_b / (2.0 * g)  # שיא הגובה
check("וואקום אנכי: הסימולציה הצליחה", r["ok"], r.get("message", ""))
check("וואקום אנכי: מהירות סוף בעירה (סטייה < 0.5%)", abs(r["burnout"]["v_ms"] - v_b) / v_b < 0.005, f"{r['burnout']['v_ms']} מול {v_b:.1f}")
check("וואקום אנכי: גובה סוף בעירה (סטייה < 0.5%)", abs(r["burnout"]["alt_m"] - 100.0 - h_b) / h_b < 0.005, f"{r['burnout']['alt_m'] - 100:.1f} מול {h_b:.1f}")
check("וואקום אנכי: שיא הגובה (סטייה < 0.5%)", abs(r["apex"]["alt_m"] - 100.0 - apex) / apex < 0.005, f"{r['apex']['alt_m'] - 100:.0f} מול {apex:.0f}")
check("וואקום אנכי: נוחת בחזרה ליד המשגר", r["impact"]["range_m"] < 1.0, f"{r['impact']['range_m']} מ'")

# ── 2. שיגור ב-45° ──
vac = rm.simulate(LAUNCH, 45.0, 60.0, ROCKET, Vacuum(), geo_direct=geo_direct)
air = rm.simulate(LAUNCH, 45.0, 60.0, ROCKET, AtmosphereProfile.standard(surface_alt=100.0), geo_direct=geo_direct)
check("45°: שתי הסימולציות הצליחו", vac["ok"] and air["ok"])
check("45°: גרר מקצר את הטווח", air["impact"]["range_m"] < vac["impact"]["range_m"],
      f"אוויר {air['impact']['range_m'] / 1000:.1f} ק\"מ < ואקום {vac['impact']['range_m'] / 1000:.1f} ק\"מ")
last = air["path"][-1]  # נקודת הפגיעה
check("45°: הפגיעה בגובה המשגר (±1 מ' + עקמומיות)", abs(last["alt_msl"] - 100.0 - last["ground_dist"] ** 2 / (2 * rm.R_EARTH)) < 1.0, f"{last['alt_msl']}")
dist, brg = geo_inverse(LAUNCH["lat"], LAUNCH["lon"], last["lat"], last["lon"])  # מרחק וכיוון לפגיעה
check("45°: כיוון הפגיעה = אזימוט השיגור (60°)", abs(brg - 60.0) < 0.5, f"{brg:.2f}°")
check("45°: מרחק גאודטי = הטווח המדווח", abs(dist - air["impact"]["range_m"]) < 1.0, f"{dist:.1f} / {air['impact']['range_m']}")
ts = [p["t"] for p in air["path"]]  # זמני הנקודות
check("45°: זמנים עולים, מרווח 0.1 שנ'", all(b > a for a, b in zip(ts, ts[1:])) and abs(ts[1] - ts[0] - 0.1) < 1e-6, f"n={len(ts)}")
stronger = rm.simulate(LAUNCH, 45.0, 60.0, dict(ROCKET, thrust_n=6000.0), AtmosphereProfile.standard(surface_alt=100.0), geo_direct=geo_direct)
check("45°: דחף גדול יותר = טווח ארוך יותר", stronger["impact"]["range_m"] > air["impact"]["range_m"])

# ── 2א. יחס דחף-משקל גבוה בוואקום: הטווח תואם הערכה אנליטית מנקודת סוף הבעירה ──
hi = {"mass_kg": 60.0, "prop_kg": 25.0, "burn_s": 2.0, "thrust_n": 25000.0, "diam_m": 0.15, "cd": 0.4}  # T/W ≈ 42
rh = rm.simulate(LAUNCH, 45.0, 0.0, hi, Vacuum(), geo_direct=geo_direct)  # בוואקום
pb = min(rh["path"], key=lambda q: abs(q["t"] - rh["burnout"]["t"]))  # נקודת סוף הבעירה
i_b = rh["path"].index(pb)  # האינדקס שלה
qa, qb = rh["path"][i_b - 1], rh["path"][i_b]  # שתי נקודות סביבה — לזווית
ang = math.atan2(qb["alt_msl"] - qa["alt_msl"], qb["ground_dist"] - qa["ground_dist"])  # זווית המסלול
est = rh["burnout"]["v_ms"] ** 2 * math.sin(2 * ang) / rm.G0  # טווח בליסטי מנקודת סוף הבעירה (ארץ שטוחה)
check("T/W גבוה בוואקום: טווח תואם הערכה אנליטית (±5%)", abs(rh["impact"]["range_m"] - est) / est < 0.05,
      f"{rh['impact']['range_m'] / 1000:.1f} מול {est / 1000:.1f} ק\"מ")

# ── 3. קלט לא תקין ודחף חלש ──
check("קלט: דלק כבד מהרקטה נדחה", not rm.simulate(LAUNCH, 45.0, 0.0, dict(ROCKET, prop_kg=150.0), Vacuum(), geo_direct=geo_direct)["ok"])
check("קלט: זמן בעירה 0 נדחה", not rm.simulate(LAUNCH, 45.0, 0.0, dict(ROCKET, burn_s=0.0), Vacuum(), geo_direct=geo_direct)["ok"])
weak = rm.simulate(LAUNCH, 45.0, 0.0, dict(ROCKET, thrust_n=500.0), Vacuum(), geo_direct=geo_direct)
check("דחף קטן מהמשקל: הודעה ברורה", not weak["ok"] and "משקל" in weak["message"], weak["message"])

# ── 4. שילוב בכלי בדיקת המעקב: המסלול עובר את איחוד המסלול ──
import radar_track as rt  # noqa: E402 — הכלי שצורך את המסלול
nt = rt.normalize_trajectory(air["path"])  # איחוד
check("שילוב: radar_track מקבל את המסלול כמו שהוא", len(nt) == len(air["path"]) and nt[5]["speed"] > 0, f"n={len(nt)}")

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה
