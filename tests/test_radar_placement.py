# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות שלב ב' — הצעת מיקום (radar_placement.py), בלי רשת: רשת המועמדים, רשת הגבהים (יישור למפתחות
המטמון, אינטרפולציה, תקציב), ותרחיש סינתטי שבו יש תשובה נכונה ידועה — רכס שמסתיר את המסלול רק
ממועמדים שמאחוריו.
הרצה: python tests/test_radar_placement.py
"""
import math  # חישובים
import os  # נתיב שורש
import sys  # sys.path וקוד יציאה

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט

import radar_placement as rp  # המודול הנבדק
import radar_track as rt  # המנוע של שלב א'

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # עברית בקונסולה
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

results = []  # תוצאות


def check(name, cond, info=""):
    """רושם ומדפיס בדיקה."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


C_LAT, C_LON = 31.25, 34.80  # מרכז האזור

# ── 1. רשת המועמדים ──
cands = rp.candidate_grid(C_LAT, C_LON, 1000.0, 500.0)  # רדיוס 1 ק"מ, מרווח 500 מ'
check("מועמדים: 13 נקודות במעגל 1 ק\"מ במרווח 500 מ'", len(cands) == 13, str(len(cands)))
far = max(cands, key=lambda c: math.hypot(c["dx_m"], c["dy_m"]))  # הרחוק ביותר
check("מועמדים: הרחוק ביותר במרחק 1 ק\"מ מהמרכז", abs(rt.haversine_m(C_LAT, C_LON, far["lat"], far["lon"]) - 1000.0) < 5.0,
      f"{rt.haversine_m(C_LAT, C_LON, far['lat'], far['lon']):.1f} מ'")

# ── 2. רשת הגבהים ──
dem = rp.DemGrid(31.20, 31.30, 34.75, 34.90, budget=1200)  # תיבה של ~11×14 ק"מ
nodes = dem.nodes()  # הצמתים
check("רשת גבהים: בתוך התקציב (עם עיגול)", len(nodes) <= 1200 * 1.3, f"{len(nodes)} צמתים, רזולוציה {dem.res_m:.0f} מ'")
check("רשת גבהים: הצמתים = מפתחות המטמון (snap_cell)", all(rt.snap_cell(lat, lon) == (lat, lon) for lat, lon in nodes[:200]))
check("רשת גבהים: מכסה את התיבה", nodes[0][0] <= 31.20 and nodes[-1][0] >= 31.30 and nodes[0][1] <= 34.75 and nodes[-1][1] >= 34.90)
dem.set_values([100.0 + 1000.0 * (lat - 31.2) + 500.0 * (lon - 34.75) for lat, lon in nodes])  # מישור משופע — הבילינארי מדויק עליו
check("רשת גבהים: אינטרפולציה מדויקת על מישור", abs(dem.at(31.2537, 34.8311) - (100.0 + 1000.0 * 0.0537 + 500.0 * 0.0811)) < 1e-6,
      f"{dem.at(31.2537, 34.8311):.4f}")
vals = list(dem.values)  # עותק
vals[0] = None  # פינה חסרה
dem.set_values(vals)  # מוצב
check("רשת גבהים: פינה חסרה לא מפילה", dem.at(nodes[0][0] + 0.0001, nodes[0][1] + 0.0001) is not None)

# ── 3. תרחיש עם תשובה ידועה: רכס צפון-דרום ב-34.83°, המסלול ממזרח לו ונמוך ──
RIDGE_LON = 34.83  # קו הרכס


def terrain(lat, lon):
    """רכס 700 מ' ברוחב ~400 מ' לאורך קו אורך 34.83, ושטח שטוח 100 מ' בכל מקום אחר."""
    d_m = abs(lon - RIDGE_LON) * rt.DEG_TO_M * math.cos(math.radians(lat))  # מרחק מקו הרכס
    return 700.0 if d_m < 200.0 else 100.0  # רכס או מישור


traj_raw = []  # מטרה ממזרח לרכס, נמוכה (200 מ'), נעה צפונה
for i in range(41):  # 40 שנ'
    lat, lon = 31.22 + i * 0.0015, 34.87  # צפונה לאורך 34.87
    traj_raw.append({"t": float(i), "lat": lat, "lon": lon, "alt_msl": 200.0})  # נמוכה — הרכס מסתיר אותה ממערב
traj = rt.normalize_trajectory(traj_raw)  # איחוד
center_lat, center_lon = 31.25, 34.83  # מרכז החיפוש — על הרכס
cands = rp.candidate_grid(center_lat, center_lon, 2500.0, 500.0)  # מועמדים משני צדי הרכס
params = {"range_km": 30.0, "min_range_km": 0.0, "ridge_margin_deg": 0.0, "vertical_center_deg": 45.0,
          "vertical_width_deg": 90.0, "h_antenna": 10.0}  # מכ"ם בלי מגבלות מיוחדות
bbox = rp.region_bbox(cands, traj, params["range_km"] * 1000.0)  # התיבה
grid = rp.DemGrid(*bbox)  # רשת הגבהים
grid.set_values([terrain(lat, lon) for lat, lon in grid.nodes()])  # "שליפה" סינתטית


def physics_factory(_h):
    """פיזיקה בלי מגבלות: רק השטח משפיע."""
    return {"ceiling_m": 1e9, "lobing": lambda e: 1.0, "scan_loss": lambda b: 1.0, "doppler_ok": lambda v: True}  # הכל עובר


res = [rp.evaluate_candidate(c, traj, grid, params, physics_factory, ("detection", None, None), "coverage") for c in cands]  # כל המועמדים
west = [r for r in res if r["lon"] < RIDGE_LON - 0.004]  # מאחורי הרכס (מערבה לו, >~400 מ')
east = [r for r in res if r["lon"] > RIDGE_LON + 0.004]  # בצד של המטרה
check("תרחיש: כל המועמדים חושבו", all(r["score"] is not None for r in res), f"n={len(res)}")
check("תרחיש: מאחורי הרכס — המטרה מוסתרת (כיסוי 0)", max(r["score"] for r in west) == 0.0, f"max west={max(r['score'] for r in west)}")
check("תרחיש: בצד המטרה — כיסוי מלא", min(r["score"] for r in east) == 100.0, f"min east={min(r['score'] for r in east)}")
best = rp.best_candidates(res, 5)  # הטובים
check("תרחיש: חמשת הטובים כולם בצד המטרה", all(b["lon"] > RIDGE_LON for b in best), str([round(b["lon"], 4) for b in best]))
crest = [r for r in res if abs(r["lon"] - RIDGE_LON) < 0.001]  # במרכז רמת הרכס (400 מ' רוחב)
# ממרכז הרמה, שפתה המזרחית (200 מ', ~-2.9°) מסתירה מטרה נמוכה במרחק 4 ק"מ (~-7.3°) — כמו במציאות
check("תרחיש: ממרכז רמה שטוחה — שפת הרמה מסתירה מטרה נמוכה", crest and all(r["score"] == 0.0 for r in crest), str([r["score"] for r in crest]))

# ── 4. ציון "זמן התרעה" במצב גילוי, ומסלול שלא מתחיל ב-0 ──
traj_late = rt.normalize_trajectory([dict(p, t=p["t"] + 100.0) for p in traj_raw])  # אותו מסלול, מתחיל ב-100 שנ'
r_late = rp.evaluate_candidate(east[0], traj_late, grid, params, physics_factory, ("detection", None, None), "warning")  # צד המטרה
check("זמן התרעה: לא מניח שהזמן מתחיל ב-0", r_late["score"] == 40.0, str(r_late["score"]))
scan = {"mode": "phased", "revisit_s": 1.0, "rot_period_s": 4.0, "phase_deg": 0.0, "track_rate_hz": 10.0,
        "max_ang_rate_dps": 30.0, "cue_delay_s": 1.0}  # מערך-מופע, ביקור כל שנייה
r_trk = rp.evaluate_candidate(east[0], traj, grid, params, physics_factory, ("track", scan, {"m": 2, "n": 3, "coast_s": 5.0}), "warning")  # מצב מעקב
check("זמן התרעה במצב מעקב: מפתיחת המעקב (שנ' 1) עד הסוף", r_trk["score"] == 39.0 and r_trk["track_initiated"], str(r_trk["score"]))

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה
