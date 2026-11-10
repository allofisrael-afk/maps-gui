"""
בדיקות שכבת ה-API (mpm_api.py) לכלי המסלול הבליסטי — Stage 2 (FR-D-234). בניגוד ל-self_test.py
(בודק רק את mpm/ הגולמי) — כאן נבדקות trajectory/solve/solve_mv/table/calibrate/terrain_check/
min_qe_for_crest כמו שweather_server.py קורא להן בפועל, כולל רכס-קרקע סינתטי ל-terrain_check
(לפי בקשת הפרומפט: "כיסוי שטח עם רכס סינתטי... collision במרחק הנכון... min_qe_for_crest מחזיר
זווית שעוברת מעל הרכס"). רץ בלי רשת ובלי שרת (elevation_fetcher מוזרק כפונקציה מזוייפת) —
הרצה: python tests/test_ballistics_api.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש-הפרויקט — ל-mpm_api/mpm.geodesy

import mpm_api
from mpm.geodesy import inverse as geo_inverse
from mpm.units import mils_to_rad

GUN = {"lat": 31.2520, "lon": 34.7915, "alt_m": 280.0}
TARGET = {"lat": 31.3600, "lon": 34.8900, "alt_m": 310.0}
MET_STD = {"source": "standard"}  # אטמוספרה סטנדרטית — אין תלות-רשת בבדיקה הזו
results = []


def check(name, cond, info=""):
    results.append(cond)
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")


def fetcher_flat(locs):
    """קרקע שטוחה בגובה 50 מ' — elevation_fetcher מזוייף (אין קריאת-רשת כלל) ל-terrain_check."""
    return [50.0 for _ in locs], None


def fetcher_ridge(locs):
    """רכס סינתטי: 3000 מ' בין 5-7 ק"מ מהתותח, 50 מ' בכל מקום אחר — elevation_fetcher מזוייף."""
    out = []
    for loc in locs:
        d, _az = geo_inverse(GUN["lat"], GUN["lon"], loc["lat"], loc["lon"])
        out.append(3000.0 if 5000.0 <= d <= 7000.0 else 50.0)
    return out, None


# --- trajectory/solve/solve_mv/table/calibrate — בדיקת-שפיות שכל הפעולות מחזירות dict תקין ---
tr = mpm_api.trajectory(GUN, qe=450, azimuth=600, mv=684, met=MET_STD, include_path=True, path_step=1)
check("trajectory מחזיר פגיעה תקינה", tr["ok"] and tr["impact"]["ground_range_m"] > 0,
      f"(range={tr.get('impact', {}).get('ground_range_m')})")

s = mpm_api.solve(GUN, TARGET, mv=684, met=MET_STD, group="low", include_path=False)
check("solve (low) מתכנס עם שארית קטנה", s["ok"] and abs(s["residual_range_error_m"]) < 1.0,
      f"(residual={s.get('residual_range_error_m')})")

s_out = mpm_api.solve(GUN, TARGET, mv=684, met=MET_STD, group="low", qe_min=5, qe_max=200, include_path=False)
check("solve מחוץ לתחום-הגבהות מותר נכשל בבירור", not s_out["ok"] and "error" in s_out, f"({s_out.get('error')})")

smv = mpm_api.solve_mv(GUN, TARGET, qe=450, mv_min=600, mv_max=750, met=MET_STD, include_path=False)
check("solve_mv מוצא V0 בתחום עם שארית קטנה", smv["ok"] and abs(smv["residual_range_error_m"]) < 1.0,
      f"(mv={smv.get('muzzle_velocity_mps')})")

tb = mpm_api.table(GUN, azimuth=0, qe_start=100, qe_end=1200, qe_step=100, mv=684, met=MET_STD)
check("table מחזיר שורות במספר הצפוי", tb["ok"] and len(tb["rows"]) == 12, f"(rows={len(tb.get('rows', []))})")

cal = mpm_api.calibrate(GUN, mv=684, met=MET_STD, points=[
    {"qe": 300, "azimuth": 1600, "range_m": 12316, "drift": 13.5},
    {"qe": 700, "azimuth": 1600, "range_m": 22000, "drift": 40.0},
])
check("calibrate מחזיר מקדמי-התאמה", "drag_factor" in cal and "lift_factor" in cal,
      f"(fD={cal.get('drag_factor')}, fL={cal.get('lift_factor')})")

# --- terrain_check: קרקע שטוחה — לא אמור לחסום ---
tc_flat = mpm_api.terrain_check(tr["path"], fetcher_flat, safety_margin_m=10.0)
check("terrain_check על קרקע שטוחה — עובר (clear)", tc_flat["ok"] and tc_flat["clear"])

# --- terrain_check: רכס סינתטי (3000 מ' ב-5-7 ק"מ) — אמור לחסום במרחק הנכון ---
tc_ridge = mpm_api.terrain_check(tr["path"], fetcher_ridge, safety_margin_m=10.0)
coll = tc_ridge.get("first_collision") or {}
check("terrain_check עם רכס סינתטי מזהה חסימה במרחק הנכון",
      tc_ridge["ok"] and not tc_ridge["clear"] and 5000.0 <= coll.get("ground_dist", -1) <= 7000.0,
      f"(collision at {coll.get('ground_dist')} מ')")

# --- min_qe_for_crest: מול אותו רכס — הזווית שמוחזרת חייבת לעבור אותו בפועל ---
mqc = mpm_api.min_qe_for_crest(GUN, {"range_m": 15000, "azimuth": 600}, mv=684, met=MET_STD,
                               elevation_fetcher=fetcher_ridge, safety_margin_m=10.0)
check("min_qe_for_crest מחזיר זווית שעוברת מעל הרכס",
      mqc["ok"] and mqc["terrain_check"]["clear"] and mqc["qe_min"]["mils"] > mils_to_rad(452.05) * 0,
      f"(qe_min={mqc.get('qe_min')})")
# אימות-נוסף: הזווית שהוחזרה גבוהה מהזווית ה'טבעית' (452 מיל) שמשמשת ל-solve באותה תצורה —
# כלומר הרכס בפועל *מחייב* הגבהה גבוהה יותר, לא מחזיר ערך-שרירותי
check("הגבהה-מינימלית-לכיסוי-שטח גבוהה מהזווית הרגילה לאותה מטרה (הרכס בפועל משפיע)",
      mqc["ok"] and mqc["qe_min"]["mils"] > 452.05, f"(qe_min={mqc['qe_min']['mils']} מיל > 452.05)")

print("\nכל בדיקות ה-API עברו" if all(results) else "\nיש בדיקות API שנכשלו")
sys.exit(0 if all(results) else 1)
