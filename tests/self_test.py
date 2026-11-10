"""בדיקות שפיות למנוע. הרצה: python tests/self_test.py"""
import math
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mpm.atmosphere import AtmosphereProfile
from mpm.engine import FireParams, simulate
from mpm.fire_control import solve, solve_mv, calibrate  # solve_mv נוסף ב-Stage 2 (FR-D-234)
from mpm.geodesy import inverse, direct
from mpm.projectile import load_projectile
from mpm.units import mils_to_rad

P = load_projectile()
A = AtmosphereProfile.standard(0)
FP = FireParams(qe=mils_to_rad(500), azimuth=0.0, mv=684, latitude=math.radians(32))
results = []


def check(name, cond, info=""):
    results.append(cond)
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")


r1 = simulate(P, A, replace(FP, dt=0.005), record=False).ground_range
r2 = simulate(P, A, replace(FP, dt=0.05), record=False).ground_range
check("התכנסות צעד האינטגרציה", abs(r1 - r2) < 0.5, f"({r1:.2f} / {r2:.2f} מ')")

r = simulate(P, A, replace(FP, coriolis=False), record=False)
check("סחיפה ימינה בפיתול ימני", r.impact["drift_z_m"] > 0, f"({r.impact['drift_z_m']:.1f} מ')")

north = simulate(P, A, replace(FP, azimuth=0.0, lift_factor=0, magnus_factor=0), record=False)
check("קוריוליס מסיט ימינה בחצי הכדור הצפוני", north.impact["drift_z_m"] > 0, f"({north.impact['drift_z_m']:.1f} מ')")
east = simulate(P, A, replace(FP, azimuth=math.pi / 2), record=False).ground_range
west = simulate(P, A, replace(FP, azimuth=3 * math.pi / 2), record=False).ground_range
check("אפקט אטווש: ירי מזרחה ארוך מירי מערבה", east > west, f"({east - west:.1f} מ')")

s = solve(P, A, FP, 14000.0, mils_to_rad(800), 0.0, "low")
check("פתרון ירי מתכנס", s["ok"] and abs(s["residual_range_error_m"]) < 1.0,
      f"(שארית {s.get('residual_range_error_m')} מ')")

pts = []
for q in (300, 700):
    rr = simulate(P, A, replace(FP, qe=mils_to_rad(q), drag_factor=1.06, lift_factor=1.25), record=False)
    pts.append({"qe": mils_to_rad(q), "range_m": rr.ground_range, "drift_mils": rr.impact["deviation"]["mils"]})
c = calibrate(P, A, FP, pts)
check("כיול משחזר מקדמים ידועים", abs(c["drag_factor"] - 1.06) < 2e-3 and abs(c["lift_factor"] - 1.25) < 0.02,
      f"(fD={c['drag_factor']}, fL={c['lift_factor']})")

d, az = inverse(31.25, 34.79, 31.36, 34.89)
la, lo = direct(31.25, 34.79, az, d)
check("גאודזיה: הלוך-חזור", abs(la - 31.36) < 1e-7 and abs(lo - 34.89) < 1e-7, f"({d:.2f} מ', {az:.3f}°)")

# --- Stage 2 (FR-D-234): solve_mv — קובעים mv ידוע בהגבהה קבועה, מחשבים את הטווח שהוא מניב,
# ואז בודקים ש-solve_mv (עם חיפוש בתחום [600,750]) משחזר את ה-mv הזה בתוך 1 מ'/ש'
known_mv, known_qe = 700.0, mils_to_rad(500)
known_az = 0.0
known_range = simulate(P, A, replace(FP, mv=known_mv, qe=known_qe, azimuth=known_az), record=False).ground_range
smv = solve_mv(P, A, FP, known_range, known_az, known_qe, 600.0, 750.0)
check("solve_mv משחזר מהירות-לוע ידועה",
      smv["ok"] and abs(smv["muzzle_velocity_mps"] - known_mv) < 1.0,
      f"(mv={smv.get('muzzle_velocity_mps')}, ידוע={known_mv})")

# --- Stage 2 (FR-D-234): תחום-הגבהות מותר (qe_min/qe_max) ב-solve — פתרון בתוך תחום מצומצם-בכוונה
# שעדיין מכיל את הזווית האמיתית (500 מיל) חייב להתכנס; תחום שבכוונה לא מכיל אותה (עד 400 מיל בלבד,
# בענף 'low') חייב להיכשל בבירור עם טווח-קרוב-ביותר ולא להתכנס בשקט לתוצאה שגויה
rng_known = simulate(P, A, FP, record=False).ground_range  # FP כבר qe=500mils, azimuth=0
s_in = solve(P, A, FP, rng_known, 0.0, 0.0, "low", qe_min=mils_to_rad(300), qe_max=mils_to_rad(700))
check("פתרון בתוך תחום-הגבהות מותר (300-700 מיל) מתכנס", s_in["ok"] and abs(s_in["residual_range_error_m"]) < 1.0,
      f"(qe={s_in.get('qe')})")
s_out = solve(P, A, FP, rng_known, 0.0, 0.0, "low", qe_min=mils_to_rad(5), qe_max=mils_to_rad(400))
check("פתרון מחוץ לתחום-הגבהות מותר (עד 400 מיל) נכשל עם הודעה ברורה",
      not s_out["ok"] and "closest_achievable_range_m" in s_out, f"({s_out.get('error')})")

print("\nכל הבדיקות עברו" if all(results) else "\nיש בדיקות שנכשלו")
sys.exit(0 if all(results) else 1)
