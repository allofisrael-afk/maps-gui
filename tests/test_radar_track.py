# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות ליבת כלי "בדיקת מעקב מכ"ם" (radar_track.py), שלב א1 — בלי רשת ובלי שרת.
השטח סינתטי (פונקציה במקום Open-Meteo) והפיזיקה של המכ"ם מוזרקת כפונקציות פשוטות, כך שכל
מקרה בודק סיבה אחת בדיוק: טווח, אזור-עיוור, שטח, שדה-ראייה אנכי, סקטור, תקרת מכ"ם ודופלר.
הרצה: python tests/test_radar_track.py
"""
import math  # חישובי בדיקה
import os  # נתיב שורש הפרויקט
import sys  # sys.path וקוד יציאה

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט — ל-radar_track

import radar_track as rt  # המודול הנבדק

try:  # פלט UTF-8 — קונסולת Windows ברירת-מחדל משבשת עברית
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # תווים שלא ניתנים להצגה מוחלפים
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

RADAR_LAT, RADAR_LON = 31.25, 34.80  # מיקום מכ"ם סינתטי
GROUND_M = 100.0  # גובה הקרקע השטוחה, מטרים
H_ANT = 15.0  # גובה אנטנה
RADAR = {"lat": RADAR_LAT, "lon": RADAR_LON, "h_msl": GROUND_M + H_ANT}  # המכ"ם כפי שהמנוע מקבל אותו
results = []  # תוצאות הבדיקות


def check(name, cond, info=""):
    """רושם ומדפיס תוצאת בדיקה בודדת."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # שורת פלט


def terrain_flat(lat, lon):
    """קרקע שטוחה בגובה 100 מ'."""
    return GROUND_M  # תמיד אותו גובה


def terrain_ridge(lat, lon):
    """רכס 600 מ' במרחק 5-6 ק"מ מזרחית למכ"ם (אזימוט 80°-100°), 100 מ' בכל מקום אחר."""
    d = rt.haversine_m(RADAR_LAT, RADAR_LON, lat, lon)  # מרחק מהמכ"ם
    b = rt.bearing_deg(RADAR_LAT, RADAR_LON, lat, lon)  # כיוון מהמכ"ם
    return 600.0 if (5000.0 <= d <= 6000.0 and 80.0 <= b <= 100.0) else GROUND_M  # רכס או מישור


def params(**over):
    """פרמטרי מכ"ם בסיסיים (כמו _parse_radar_common_params) עם דריסות לבדיקה מסוימת."""
    base = {"range_km": 50.0, "min_range_km": 1.0, "ridge_margin_deg": 0.0,
            "vertical_center_deg": 45.0, "vertical_width_deg": 90.0}  # שדה ראייה 0°-90° — לא מגביל כברירת מחדל
    base.update(over)  # דריסות
    return base  # הפרמטרים


def physics(ceiling_km=100.0, mdv=5.0, sector=None):
    """פיזיקה מזויפת: תקרה קבועה, בלי ריבוד, דופלר לפי סף MDV בלבד, וסקטור אופציונלי (מרכז, חצי-רוחב)."""
    def scan(b):  # הפסד-סריקה: 1 בתוך הסקטור, 0 מחוצה לו
        if sector is None:  # אנטנה גנרית
            return 1.0  # בלי הפסד
        diff = abs((b - sector[0] + 180.0) % 360.0 - 180.0)  # הפרש זוויתי מהמרכז
        return 1.0 if diff <= sector[1] else 0.0  # בפנים / בחוץ
    return {"ceiling_m": ceiling_km * 1000.0, "lobing": lambda e: 1.0,
            "scan_loss": scan, "doppler_ok": lambda v: v >= mdv}  # ה-dict שהמנוע מצפה לו


def run(traj_raw, prm, phys, terrain):
    """מריץ את כל צינור שלב א1: איחוד, תכנון דגימות, "שליפת" גבהים סינתטית, פרופילים, הערכה וסיכום."""
    traj = rt.normalize_trajectory(traj_raw)  # איחוד המסלול
    plan = rt.plan_terrain_samples(RADAR, traj, prm["range_km"] * 1000.0)  # תכנון דגימות
    elevs = [terrain(lat, lon) for (lat, lon) in plan["cells"]]  # במקום Open-Meteo — גובה לכל תא-רשת ייחודי
    prof = rt.build_horizon_profiles(plan, elevs, RADAR["h_msl"])  # פרופילי אופק
    res = rt.evaluate_points(traj, RADAR, prm, phys, plan, prof)  # הערכה
    return traj, plan, res, rt.summarize(res)  # הכל לבדיקה


def east_arc(d0_km, d1_km, apex_m, n=81, duration_s=40.0, bearing=90.0):
    """מסלול בצורת קשת: מתקדם בכיוון bearing ממרחק d0 ל-d1, גובה פרבולי מ-GROUND+50 עד apex."""
    pts = []  # הנקודות
    for i in range(n):  # n נקודות לאורך המסלול
        f = i / (n - 1)  # התקדמות 0..1
        d = (d0_km + (d1_km - d0_km) * f) * 1000.0  # מרחק מהמכ"ם
        lat, lon = rt.destination_point(RADAR_LAT, RADAR_LON, bearing, d)  # מיקום
        alt = GROUND_M + 50.0 + (apex_m - GROUND_M - 50.0) * 4.0 * f * (1.0 - f)  # פרבולה
        pts.append({"t": duration_s * f, "lat": lat, "lon": lon, "alt_msl": alt})  # נקודה
    return pts  # המסלול


# ── 1. איחוד מסלול: מהירות תלת-ממדית מחושבת נכון מנקודות בלבד ──
line = []  # קו ישר מזרחה 100 מ'/ש' ועולה 10 מ'/ש'
for i in range(11):  # 11 נקודות, שנייה ביניהן
    lat, lon = rt.destination_point(RADAR_LAT, RADAR_LON, 90.0, 20000.0 + 100.0 * i)  # 100 מ' כל שנייה מזרחה
    line.append({"t": float(i), "lat": lat, "lng": lon, "alt": 1000.0 + 10.0 * i})  # גם 'lng'/'alt' נתמכים
line.append({"t": 3.0, "lat": 0, "lon": 0, "alt_msl": 0})  # זמן כפול — חייב להיזרק
line.append({"t": "x", "lat": 1, "lon": 1, "alt_msl": 1})  # זמן לא מספרי — חייב להיזרק
nt = rt.normalize_trajectory(line)  # איחוד
mid = nt[5]  # נקודה באמצע (הפרש מרכזי)
check("normalize: נקודות לא תקינות/כפולות נזרקו", len(nt) == 11, f"n={len(nt)}")
check("normalize: מהירות מזרחית ~100", abs(mid["ve"] - 100.0) < 1.0, f"ve={mid['ve']:.2f}")
check("normalize: מהירות צפונית ~0", abs(mid["vn"]) < 1.0, f"vn={mid['vn']:.2f}")
check("normalize: מהירות אנכית 10", abs(mid["vu"] - 10.0) < 0.01, f"vu={mid['vu']:.2f}")

# ── 2. שטח שטוח, מסלול גבוה בטווח: הכל מזוהה, כיסוי 100% ──
_t, plan, res, summ = run(east_arc(8, 20, 3000), params(), physics(), terrain_flat)
check("שטוח: כל הנקודות מזוהות", summ["counts"].get("detected", 0) == len(res), str(summ["counts"]))
check("שטוח: כיסוי 100%", summ["coverage_pct"] == 100.0, f"{summ['coverage_pct']}%")
check("שטוח: גילוי ראשון בתחילת המסלול", summ["first_detection"] and summ["first_detection"]["t"] == 0.0)
check("תכנון: תאים ייחודיים בתוך התקציב", len(plan["cells"]) <= rt.MAX_TERRAIN_POINTS, f"cells={len(plan['cells'])} samples={len(plan['samples'])}")
check("תכנון: מרווח יחסי התחלתי כשיש תקציב", plan["spacing_frac"] == rt.SPACING_FRAC_START, f"frac={plan['spacing_frac']}")

# ── 3. רכס 600 מ' ב-5-6 ק"מ: הקצוות הנמוכים חסומים בשטח, השיא מזוהה ──
_t, _p, res, summ = run(east_arc(8, 20, 3000), params(), physics(), terrain_ridge)
first, apex, last = res[0], res[len(res) // 2], res[-1]  # התחלה, שיא, סוף
check("רכס: תחילת המסלול (נמוכה) חסומה בשטח", first["reason"] == "terrain", first["reason"])
check("רכס: השיא (3000 מ') מזוהה", apex["status"] == "detected", apex["reason"])
check("רכס: סוף המסלול (נמוך) חסום בשטח", last["reason"] == "terrain", last["reason"])
check("רכס: קטעים — חסום, מזוהה, חסום", [s["reason"] for s in summ["segments"]] == ["terrain", "ok", "terrain"],
      str([s["reason"] for s in summ["segments"]]))
check("רכס: כיסוי חלקי (0<x<100)", 0.0 < summ["coverage_pct"] < 100.0, f"{summ['coverage_pct']}%")
# אימות עצמאי של נקודת החסימה: נקודה מוסתרת אם הזווית אליה נמוכה מזווית ראש הרכס
ridge_slope = (600.0 - rt.curvature_drop_m(5000.0) - RADAR["h_msl"]) / 5000.0  # שיפוע ראש הרכס (קצהו הקרוב חוסם הכי הרבה)
p0 = rt.normalize_trajectory(east_arc(8, 20, 3000))[0]  # הנקודה הראשונה
g0 = rt.point_geometry(RADAR, p0)  # הגיאומטריה שלה
check("רכס: אימות עצמאי — הנקודה הראשונה באמת מתחת לרכס", g0["dh_m"] / g0["dist_m"] < ridge_slope,
      f"{g0['dh_m'] / g0['dist_m']:.4f} < {ridge_slope:.4f}")

# ── 4. שדה-ראייה אנכי ±5°: פגז שעובר גבוה וקרוב יוצא מהאלומה (חרוט העיוורון) ──
_t, _p, res, _s = run(east_arc(3, 9, 3000), params(vertical_center_deg=0.0, vertical_width_deg=10.0), physics(), terrain_flat)
apex = res[len(res) // 2]  # השיא — 3000 מ' במרחק 6 ק"מ, עילוי ~26°
check("עילוי: השיא מחוץ לאלומה האנכית", apex["reason"] == "elevation", f"{apex['reason']} elev={apex['elev_deg']}")
check("עילוי: הנקודה הנמוכה בהתחלה בתוך האלומה", res[0]["status"] == "detected", f"{res[0]['reason']} elev={res[0]['elev_deg']}")

# ── 5. דופלר: תנועה במעגל סביב המכ"ם (משיקית) — מהירות רדיאלית ~0 ──
circ = []  # מעגל ברדיוס 10 ק"מ, 50 מ'/ש'
for i in range(37):  # 37 נקודות
    brg = i * 2.0  # מתקדם 2° בכל צעד
    lat, lon = rt.destination_point(RADAR_LAT, RADAR_LON, brg, 10000.0)  # על המעגל
    circ.append({"t": i * (10000.0 * math.radians(2.0) / 50.0), "lat": lat, "lon": lon, "alt_msl": 1500.0})  # זמן לפי 50 מ'/ש'
_t, _p, res, summ = run(circ, params(), physics(mdv=5.0), terrain_flat)
mid = res[18]  # באמצע הקשת
check("דופלר: תנועה משיקית = עיוור דופלר", mid["status"] == "doppler_blind", f"{mid['status']} vr={mid['radial_ms']}")
check("דופלר: המהירות עצמה ~50", abs(mid["speed_ms"] - 50.0) < 1.0, f"speed={mid['speed_ms']}")
plan_c = rt.plan_terrain_samples(RADAR, rt.normalize_trajectory(circ), 50000.0)  # מסלול שנפרש על הרבה כיוונים
check("תכנון: איחוד תאים — קרניים סמוכות חולקות תאים ליד המכ\"ם", len(plan_c["cells"]) < len(plan_c["samples"]),
      f"{len(plan_c['cells'])}<{len(plan_c['samples'])} bins={plan_c['n_bins']}")
# אותה מהירות, אבל בכיוון המכ"ם (רדיאלית) — מזוהה
radial_line = east_arc(20, 10, 1500 + 0.001)  # מתקרב מ-20 ל-10 ק"מ
_t, _p, res, _s = run(radial_line, params(), physics(mdv=5.0), terrain_flat)
check("דופלר: תנועה רדיאלית מזוהה", res[len(res) // 2]["status"] == "detected", res[len(res) // 2]["reason"])
# רכיב אנכי טהור (פגז צולל ישר למטה מעל נקודה רחוקה) נקלט ברדיאלי — בשונה מהערכת המסלול הקיימת
dive = [{"t": float(i), "lat": RADAR_LAT, "lon": rt.destination_point(RADAR_LAT, RADAR_LON, 90.0, 3000.0)[1],
         "alt_msl": 5000.0 - 200.0 * i} for i in range(10)]  # צלילה אנכית 200 מ'/ש' במרחק 3 ק"מ
_t, _p, res, _s = run(dive, params(), physics(mdv=5.0), terrain_flat)
check("דופלר: צלילה אנכית — רכיב רדיאלי משמעותי", res[2]["radial_ms"] > 100.0, f"vr={res[2]['radial_ms']}")

# ── 6. אזור-עיוור קרוב ──
near = [{"t": 0.0, "lat": RADAR_LAT, "lon": rt.destination_point(RADAR_LAT, RADAR_LON, 90.0, 500.0)[1], "alt_msl": 300.0},
        {"t": 1.0, "lat": RADAR_LAT, "lon": rt.destination_point(RADAR_LAT, RADAR_LON, 90.0, 600.0)[1], "alt_msl": 300.0}]
_t, _p, res, _s = run(near, params(min_range_km=1.0), physics(), terrain_flat)
check("אזור-עיוור: נקודה ב-500 מ' חסומה", res[0]["reason"] == "min_range", res[0]["reason"])

# ── 7. מעבר לטווח הבדיקה ──
_t, _p, res, _s = run(east_arc(55, 60, 3000), params(range_km=50.0), physics(), terrain_flat)
check("טווח: מעבר ל-50 ק\"מ = out_of_range", all(r["status"] == "out_of_range" for r in res), res[0]["status"])

# ── 8. סקטור של מערך-מופעים (צפונה ±60°) — מסלול במזרח (90°) מחוץ לו ──
_t, _p, res, _s = run(east_arc(8, 20, 3000), params(), physics(sector=(0.0, 60.0)), terrain_flat)
check("סקטור: מסלול ב-90° מחוץ לסקטור 0±60", res[len(res) // 2]["reason"] == "sector", res[len(res) // 2]["reason"])

# ── 9. תקרת מכ"ם 10 ק"מ — הטווח האלכסוני קובע ──
_t, _p, res, _s = run(east_arc(8, 20, 3000), params(), physics(ceiling_km=10.0), terrain_flat)
check("תקרה: תחילת המסלול (8 ק\"מ) מזוהה", res[0]["status"] == "detected", res[0]["reason"])
check("תקרה: סוף המסלול (20 ק\"מ) מעבר לתקרה", res[-1]["reason"] == "radar_range", res[-1]["reason"])

# ── 10. מרווח רכס: אותו רכס עם מרווח 2° חוסם יותר נקודות ──
_t, _p, r0, s0 = run(east_arc(8, 20, 3000), params(), physics(), terrain_ridge)
_t, _p, r2, s2 = run(east_arc(8, 20, 3000), params(ridge_margin_deg=2.0), physics(), terrain_ridge)
check("מרווח רכס: כיסוי יורד עם מרווח 2°", s2["coverage_pct"] < s0["coverage_pct"], f"{s0['coverage_pct']}% -> {s2['coverage_pct']}%")

# ── 11. מסלול ריק/פגום — לא קורס ──
_t, _p, res, summ = run([], params(), physics(), terrain_flat)
check("ריק: אין נקודות ואין קריסה", res == [] and summ["detected_any"] is False)

# ═══════════════ שלב א2: סריקה ומעקב ═══════════════

def scan_cfg(mode, **over):
    """תצורת סריקה בסיסית (כמו שהשרת מעביר) עם דריסות."""
    base = {"mode": mode, "rot_period_s": 4.0, "phase_deg": 0.0, "revisit_s": 0.5,
            "track_rate_hz": 10.0, "max_ang_rate_dps": 30.0, "cue_delay_s": 1.0}  # ברירות מחדל
    base.update(over)  # דריסות
    return base  # התצורה


def track_cfg(**over):
    """פרמטרי מעקב בסיסיים: 2 מתוך 3, דעיכה 8 שניות."""
    base = {"m": 2, "n": 3, "coast_s": 8.0}  # ברירות מחדל
    base.update(over)  # דריסות
    return base  # הפרמטרים


def track_run(res, scan, trk):
    """מריץ את לוגיקת המעקב + מצבים + סיכום."""
    out = rt.run_track_logic(res, scan, trk)  # לוגיקת המעקב
    states = rt.track_states(res, out["tracks"])  # מצב לכל נקודה
    return out, states, rt.summarize_track(res, out, states)  # הכל


_t, _p, res_flat, _s = run(east_arc(8, 20, 3000), params(), physics(), terrain_flat)  # 40 שנ', הכל מזוהה, אזימוט 90° קבוע

# ── 12. מערך-מופע, ביקור כל 0.5 שנ': מעקב נפתח בהזדמנות השנייה (2 מתוך 3) ──
o, st, sm = track_run(res_flat, scan_cfg("phased"), track_cfg())
check("מערך-מופע: מעקב נפתח בשנ' 0.5", sm["first_track_t"] == 0.5, str(sm["first_track_t"]))
check("מערך-מופע: זמן התרעה 39.5 שנ'", sm["warning_time_s"] == 39.5, str(sm["warning_time_s"]))
check("מערך-מופע: 81 הזדמנויות, כולן גילוי", o["opportunities"] == 81 and o["opp_detected"] == 81, f"{o['opportunities']}/{o['opp_detected']}")
check("מערך-מופע: מעקב אחד עד הסוף", len(o["tracks"]) == 1 and o["tracks"][0]["end_reason"] == "end", str(o["tracks"]))
check("מערך-מופע: הנקודה הראשונה 'גילוי בלי מעקב'", st[0] == rt.TRACK_DETECTED_ONLY and st[-1] == rt.TRACK_TRACKED, f"{st[0]} ... {st[-1]}")

# ── 13. אנטנה מסתובבת 4 שנ', מתחילה בצפון: המטרה ב-90° -> הזדמנויות ב-1, 5, 9... ──
opps = rt.scan_opportunities(res_flat, scan_cfg("rotating"))
check("מסתובבת: הזדמנויות כל 4 שנ' החל מ-1", len(opps) == 10 and abs(opps[0] - 1.0) < 0.01 and abs(opps[1] - 5.0) < 0.01,
      str([round(x, 2) for x in opps[:3]]))
o, st, sm = track_run(res_flat, scan_cfg("rotating"), track_cfg())
check("מסתובבת: מעקב נפתח בהזדמנות השנייה (שנ' 5)", sm["first_track_t"] is not None and abs(sm["first_track_t"] - 5.0) < 0.01, str(sm["first_track_t"]))
check("מסתובבת: בין סיבובים המעקב נשאר 'במעקב' (לא מהבהב לדעיכה)", rt.TRACK_COASTING not in st, str(set(st)))
o2, _st2, sm2 = track_run(res_flat, scan_cfg("rotating", phase_deg=80.0), track_cfg())  # פאזה שונה: האלומה מגיעה למטרה מוקדם יותר
check("מסתובבת: הפאזה משנה את זמן הפתיחה", sm2["first_track_t"] < sm["first_track_t"], f"{sm2['first_track_t']} < {sm['first_track_t']}")

# ── 14. סיבוב איטי + M גבוה: לא מספיק הזדמנויות לפתיחת מעקב ──
o, st, sm = track_run(res_flat, scan_cfg("rotating", rot_period_s=30.0), track_cfg(m=3, n=3))
check("סיבוב 30 שנ' ו-3 מתוך 3: אין מעקב", sm["track_initiated"] is False and o["opp_detected"] >= 1, f"opps={o['opportunities']}")
check("בלי מעקב: אין זמן התרעה, ויש 'גילוי בלי מעקב'", sm["warning_time_s"] is None and rt.TRACK_DETECTED_ONLY in st)

# ── 15. רכס: המעקב נשבר כשהמטרה יורדת מאחוריו, עם סיבה 'terrain' ודעיכה לפני השבירה ──
_t, _p, res_ridge, _s = run(east_arc(8, 20, 3000), params(), physics(), terrain_ridge)
o, st, sm = track_run(res_ridge, scan_cfg("phased"), track_cfg(coast_s=2.0))
check("רכס+מעקב: נפתח מעקב", sm["track_initiated"], str(sm["first_track_t"]))
check("רכס+מעקב: המעקב נשבר בגלל שטח", o["tracks"] and o["tracks"][-1]["end_reason"] == "terrain", str(o["tracks"]))
check("רכס+מעקב: יש 'דעיכה' לפני השבירה", rt.TRACK_COASTING in st, str(set(st)))
check("רכס+מעקב: זמן התרעה מפתיחת המעקב", sm["warning_time_s"] == round(40.0 - sm["first_track_t"], 2), str(sm["warning_time_s"]))

# ── 16. מכ"ם מעקב ייעודי: הכוונה + השהיה, ואז עדכונים ב-10 Hz ──
o, st, sm = track_run(res_flat, scan_cfg("tracker", cue_delay_s=1.0), track_cfg())
check("מעקב ייעודי: נפתח שנייה אחרי ההכוונה + עדכון שני", sm["first_track_t"] is not None and abs(sm["first_track_t"] - 1.1) < 0.01,
      str(sm["first_track_t"]))
# מטרה שחוצה קרוב למכ"ם במהירות — קצב זוויתי גבוה. אנטנה איטית (1°/שנ') לא עומדת בזה
fast = []  # חציה במרחק 2 ק"מ צפונית למכ"ם, 300 מ'/ש' מזרחה, 20 שנ'
north_lat, _lon0 = rt.destination_point(RADAR_LAT, RADAR_LON, 0.0, 2000.0)  # קו החציה
for i in range(41):  # כל חצי שנייה
    x = -3000.0 + 150.0 * i  # מערב->מזרח
    lat, lon = rt.destination_point(north_lat, RADAR_LON, 90.0 if x >= 0 else 270.0, abs(x))  # הנקודה
    fast.append({"t": i * 0.5, "lat": lat, "lon": lon, "alt_msl": 1500.0})  # בגובה קבוע
_t, _p, res_fast, _s = run(fast, params(min_range_km=0.0), physics(mdv=0.0), terrain_flat)  # בלי אזור עיוור ובלי סינון דופלר
rates = rt.angular_rates(res_fast)  # קצבים
check("קצב זוויתי: מקסימום בנקודת המעבר הקרובה (~7°/שנ')", 5.0 < max(rates) < 10.0, f"max={max(rates):.2f}")
o, _st, sm = track_run(res_fast, scan_cfg("tracker", max_ang_rate_dps=4.0), track_cfg(coast_s=1.0))  # 4°/שנ': נפתח בקצוות (~2.6°/שנ'), נופל במעבר הקרוב (~7°/שנ')
check("מעקב ייעודי 4°/שנ': נפתח, ונשבר בגלל קצב זוויתי", any(tr["end_reason"] == "angular_rate" for tr in o["tracks"]), str(o["tracks"]))
o, _st, sm = track_run(res_fast, scan_cfg("tracker", max_ang_rate_dps=30.0), track_cfg(coast_s=1.0))
check("מעקב ייעודי מהיר: מחזיק עד הסוף", len(o["tracks"]) == 1 and o["tracks"][0]["end_reason"] == "end", str(o["tracks"]))

# ── 17. ציר הזמן: מקטעים רציפים שמכסים את כל המסלול ──
_o, _st, sm = track_run(res_ridge, scan_cfg("phased"), track_cfg(coast_s=2.0))
tl = sm["timeline"]  # המקטעים
check("ציר זמן: מתחיל ב-0 ונגמר בסוף", tl[0]["t0"] == 0.0 and tl[-1]["t1"] == 40.0, f"{tl[0]['t0']}..{tl[-1]['t1']}")
check("ציר זמן: רציף בלי חורים", all(abs(tl[i]["t1"] - tl[i + 1]["t0"]) < 1e-9 for i in range(len(tl) - 1)), str(len(tl)))

# ═══════════════ שלב א4: ציפוף מסלול דליל ═══════════════
sparse = [{"t": 0.0, "lat": 31.0, "lon": 34.0, "alt_msl": 1000.0},
          {"t": 10.0, "lat": 31.1, "lon": 34.2, "alt_msl": 2000.0}]  # שתי נקודות, 10 שנ' ביניהן
dense = rt.densify_trajectory(sparse, max_step_s=1.0)  # צעד של שנייה
check("ציפוף: 11 נקודות לשנייה אחת", len(dense) == 11, str(len(dense)))
check("ציפוף: אמצע מאונטרפל נכון", abs(dense[5]["lat"] - 31.05) < 1e-9 and abs(dense[5]["alt_msl"] - 1500.0) < 1e-9, str(dense[5]))
check("ציפוף: הקצוות נשמרים", dense[0]["t"] == 0.0 and dense[-1]["t"] == 10.0 and dense[-1]["lon"] == 34.2)
long_route = [{"t": 0.0, "lat": 31.0, "lon": 34.0, "alt_msl": 1000.0}, {"t": 36000.0, "lat": 32.0, "lon": 35.0, "alt_msl": 1000.0}]  # 10 שעות
check("ציפוף: תקרת נקודות נשמרת במסלול ארוך", len(rt.densify_trajectory(long_route, 1.0, 5000)) <= 5001,
      str(len(rt.densify_trajectory(long_route, 1.0, 5000))))
check("ציפוף: נקודה בודדת לא קורסת", len(rt.densify_trajectory(sparse[:1])) == 1)

# ═══════════════ שלב א5: ITU-R P.838-3, גשם ו-RCS לפי זווית ═══════════════
# ערכי ייחוס מטבלה 5 של ITU-R P.838-3 עצמה (f, kH, αH, kV, αV) — אימות עצמאי של המקדמים שהועתקו
P838_TABLE5 = [(1, 0.0000259, 0.9691, 0.0000308, 0.8592), (3, 0.0001390, 1.2322, 0.0001942, 1.0688),
               (5, 0.0002162, 1.6969, 0.0002428, 1.5317), (10, 0.01217, 1.2571, 0.01129, 1.2156),
               (15, 0.04481, 1.1233, 0.05008, 1.0440)]  # מתוך ה-PDF הרשמי
worst = 0.0  # השגיאה היחסית הגדולה ביותר
for f, kh, ah, kv, av in P838_TABLE5:  # כל תדר בטבלה
    c = rt.p838_coefficients(f)  # החישוב שלנו
    for mine, ref in zip(c, (kh, ah, kv, av)):  # ארבעת המקדמים
        worst = max(worst, abs(mine - ref) / ref)  # שגיאה יחסית
check("ITU-R P.838-3: המקדמים תואמים לטבלה 5 (שגיאה < 0.5%)", worst < 0.005, f"worst={worst * 100:.3f}%")
g10h = rt.rain_specific_attenuation(10.0, 10.0, 0.0, 0.0)  # 10 GHz, 10 מ"מ/שעה, אופקי
check("גשם: γ = k·R^α ב-10 GHz/10 מ\"מ (אופקי)", abs(g10h - 0.01217 * 10 ** 1.2571) / g10h < 0.005, f"{g10h:.4f} dB/km")
check("גשם: אנכי < אופקי ב-10 GHz (כמו בטבלה)", rt.rain_specific_attenuation(10.0, 10.0, 0.0, 90.0) < g10h)
check("גשם: אין גשם = אין הנחתה", rt.rain_specific_attenuation(0.0, 10.0, 0.0, 0.0) == 0.0)
check("גשם: פס S (3 GHz) זניח מול פס X", rt.rain_specific_attenuation(10.0, 3.0, 0.0, 0.0) < g10h / 20.0)
check("מסלול בגשם: שני הקצוות מתחת לתקרה = כל הטווח", rt.rain_path_km(10000.0, 100.0, 1000.0, 3000.0) == 10.0)
check("מסלול בגשם: מטרה גבוהה — רק החלק שמתחת לתקרה", abs(rt.rain_path_km(10000.0, 0.0, 6000.0, 3000.0) - 5.0) < 1e-9)
check("מסלול בגשם: שני הקצוות מעל התקרה = 0", rt.rain_path_km(10000.0, 4000.0, 6000.0, 3000.0) == 0.0)


def physics_rain(rate, f_ghz=10.0, rain_top=3000.0, **kw):
    """פיזיקה מזויפת + גשם אמיתי לפי ITU — כמו שהשרת מזריק."""
    ph = physics(**kw)  # הבסיס
    ph["rain_db"] = lambda g, p: 2.0 * rt.rain_specific_attenuation(rate, f_ghz, g["elev_deg"], 0.0) * \
        rt.rain_path_km(g["slant_m"], RADAR["h_msl"], p["alt"], rain_top)  # הלוך-חזור
    return ph  # עם גשם


_t, _p, dry, _s = run(east_arc(8, 20, 1500), params(), physics(ceiling_km=22.0), terrain_flat)  # ביבש — הכל בתקרה
_t, _p, wet, _s = run(east_arc(8, 20, 1500), params(), physics_rain(25.0, ceiling_km=22.0), terrain_flat)  # גשם כבד, פס X
check("גשם: ביבש הסוף (20 ק\"מ) מזוהה", dry[-1]["status"] == "detected", dry[-1]["reason"])
check("גשם: בגשם כבד בפס X הסוף נחסם מסיבת 'rain'", wet[-1]["reason"] == "rain", f"{wet[-1]['reason']} {wet[-1].get('rain_db')} dB")
check("גשם: ההתחלה (8 ק\"מ) עדיין מזוהה", wet[0]["status"] == "detected", f"{wet[0]['reason']} {wet[0].get('rain_db')} dB")

# RCS לפי זווית: מטרה שמתקרבת ישר אל המכ"ם = חרטום (0°), מתרחקת = זנב (180°)
def level(d0_km, d1_km, alt=1500.0, n=41, duration_s=40.0):
    """מסלול אופקי ישר בגובה קבוע לאורך אזימוט 90° — בלי רכיב אנכי, כדי שזווית ההסתכלות תהיה נקייה."""
    out = []  # הנקודות
    for i in range(n):  # n נקודות
        f = i / (n - 1)  # התקדמות
        lat, lon = rt.destination_point(RADAR_LAT, RADAR_LON, 90.0, (d0_km + (d1_km - d0_km) * f) * 1000.0)  # מיקום
        out.append({"t": duration_s * f, "lat": lat, "lon": lon, "alt_msl": alt})  # נקודה
    return out  # המסלול


coming = level(20, 10)  # מתקרבת, אופקית
g_c = rt.point_geometry(RADAR, rt.normalize_trajectory(coming)[20])  # נקודה באמצע
check("זווית הסתכלות: מתקרבת = חרטום (~0°)", rt.aspect_angle_deg(g_c, rt.normalize_trajectory(coming)[20]) < 10.0)
going = level(10, 20)  # מתרחקת, אופקית
g_g = rt.point_geometry(RADAR, rt.normalize_trajectory(going)[20])  # נקודה באמצע
check("זווית הסתכלות: מתרחקת = זנב (~180°)", rt.aspect_angle_deg(g_g, rt.normalize_trajectory(going)[20]) > 170.0)
check("RCS: קצוות ואמצע", abs(rt.aspect_rcs(0, 0.01, 1.0, 0.1) - 0.01) < 1e-9 and abs(rt.aspect_rcs(90, 0.01, 1.0, 0.1) - 1.0) < 1e-9
      and abs(rt.aspect_rcs(45, 0.01, 1.0, 0.1) - 0.1) < 1e-9, "45° בין 0.01 ל-1 = 0.1 (ממוצע ב-dB)")


def physics_aspect(nose, side, tail, ref=1.0, **kw):
    """פיזיקה מזויפת + RCS לפי זווית, יחסית ל-RCS ייחוס."""
    ph = physics(**kw)  # הבסיס
    ph["rcs_factor"] = lambda a: ((rt.aspect_rcs(a, nose, side, tail) / ref) ** 0.25, rt.aspect_rcs(a, nose, side, tail))  # (גורם, RCS)
    return ph  # עם RCS לפי זווית


_t, _p, res_n, _s = run(coming, params(), physics_aspect(0.001, 1.0, 1.0, ceiling_km=15.0), terrain_flat)  # חרטום זעיר
check("RCS לפי זווית: חרטום קטן מקצר טווח — מתקרבת ב-18.5 ק\"מ חסומה", res_n[6]["reason"] == "radar_range" and res_n[6]["rcs_m2"] < 0.01,
      f"{res_n[6]['reason']} rcs={res_n[6].get('rcs_m2')} slant={res_n[6]['slant_km']}")

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה לרגרסיה
