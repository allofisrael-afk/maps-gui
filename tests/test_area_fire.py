# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""A1–A2: בדיקות למנוע "מאזור לאזור" (area_fire.py). בלי רשת — שטח סינתטי מוזרק כ-fetch_cells.
הרצה: .venv\\Scripts\\python.exe tests/test_area_fire.py"""
import math  # מרחקים
import os  # נתיבים
import sys  # sys.path וקוד יציאה

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא המנוע
import area_fire as af  # noqa: E402  # המודול הנבדק

ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


def raises(fn, exc):  # האם fn זורקת exc
    try:
        fn()  # ניסיון
    except exc:  # הצפוי
        return True  # כן
    except Exception:  # noqa: BLE001  # אחר
        return False  # לא הצפוי
    return False  # לא זרקה


FLAT = lambda cells: [300.0] * len(cells)  # noqa: E731  # שטח שטוח בגובה 300 מ'
GUN_PT = [[31.2000, 34.7500], [31.2000, 34.7520], [31.2015, 34.7520], [31.2015, 34.7500]]  # אזור שיגור קטן (נקודה אחת)
TGT = [[31.3000, 34.8600], [31.3000, 34.8700], [31.3100, 34.8700], [31.3100, 34.8600]]  # אזור מטרה ~1×1 ק"מ, ~15 ק"מ מצפון-מזרח
BASE = {"launch_areas": [{"name": "L", "polygon": GUN_PT}], "target_areas": [{"name": "T", "polygon": TGT}],  # בקשת בסיס
        "mv": 684, "met": {"source": "standard"}, "groups": ["low", "high"], "crest": False, "verify_frac": 0.3}  # בלי רכס

# ── רשתות ──
sq = [[31.0, 34.0], [31.0, 34.0 + 2000 / (af.M_PER_DEG_LAT * math.cos(math.radians(31.0)))], [31.0 + 2000 / af.M_PER_DEG_LAT, 34.0 + 2000 / (af.M_PER_DEG_LAT * math.cos(math.radians(31.0)))], [31.0 + 2000 / af.M_PER_DEG_LAT, 34.0]]  # ריבוע 2×2 ק"מ
check("רשת 500 מ' בריבוע 2×2 ק\"מ = 16 נקודות", len(af.grid_points(sq, 500.0)) == 16, str(len(af.grid_points(sq, 500.0))))  # 4×4
check("רשת 200 מ' בריבוע 2×2 ק\"מ = 100 נקודות", len(af.grid_points(sq, 200.0)) == 100)  # 10×10
tri = [[31.0, 34.0], [31.0, 34.02], [31.018, 34.0]]  # משולש — חצי מהריבוע בערך
n_tri = len(af.grid_points(tri, 200.0))  # נקודות במשולש
check("מצולע לא מלבני: רק נקודות בתוכו (כחצי ממלבן)", 0.35 < n_tri / max(1, len(af.grid_points([[31.0, 34.0], [31.0, 34.02], [31.018, 34.02], [31.018, 34.0]], 200.0))) < 0.65, str(n_tri))  # בערך חצי
check("אזור קטן מתא — נקודה אחת (המרכז)", len(af.grid_points(GUN_PT, 500.0)) == 1)  # מינימום נקודה

# ── קלט שגוי ──
check("מצולע של 2 נקודות נדחה", raises(lambda: af.parse_request(dict(BASE, launch_areas=[{"polygon": [[31, 34], [31.1, 34.1]]}])), ValueError))  # ולידציה
check("NaN בקואורדינטה נדחה", raises(lambda: af.parse_request(dict(BASE, target_areas=[{"polygon": [[float("nan"), 34], [31, 34.1], [31.1, 34]]}])), ValueError))  # ולידציה
check("mv מחוץ לטווח נדחה", raises(lambda: af.parse_request(dict(BASE, mv=5)), ValueError))  # ולידציה
check("בלי אזור מטרה נדחה", raises(lambda: af.parse_request(dict(BASE, target_areas=[])), ValueError))  # ולידציה
check("ביטול מיידי → Aborted", raises(lambda: af.run(BASE, FLAT, cancelled=lambda: True), af.Aborted))  # ביטול
check("גובה חסר → שגיאה ברורה, לא חישוב מגובה 0", raises(lambda: af.run(BASE, lambda c: [None] * len(c)), ValueError))  # כמו F-053

# ── ריצה בסיסית: ספירה ודיוק ──
res = af.run(BASE, FLAT)  # הריצה
s, v = res["summary"], res["verification"]  # קיצורים
print("   summary:", s, "\n   verification:", v)  # לפלט
check("ספירות: נקודה אחת × 30 מטרות = 30 זוגות", s["pairs"] == 30 and s["launch_points"] == 1, str(s["pairs"]))  # גדלים
check("כל הזוגות אפשריים (טווח ~15 ק\"מ, שטח שטוח)", s["pairs_feasible"] == 30 and s["trajectories_feasible"] == 60)  # שני ענפים
check("אימות: החטאה מרבית ≤ 10 מ'", v["miss_max_m"] is not None and v["miss_max_m"] <= 10.0, str(v["miss_max_m"]))  # דיוק האינטרפולציה
check("אימות: שגיאת הגבהה ≤ 0.3 מיל", v["qe_err_max_mils"] is not None and v["qe_err_max_mils"] <= 0.3, str(v["qe_err_max_mils"]))  # דיוק
low = [r for r in res["rows"] if r["group"] == "low"]  # ענף נמוך
high = [r for r in res["rows"] if r["group"] == "high"]  # ענף גבוה
check("ענף נמוך מתחת ל-800 מיל, גבוה מעליו", all(r["qe"]["mils"] < 800 for r in low) and all(r["qe"]["mils"] > 800 for r in high))  # הפרדת ענפים
check("קו ציור: DRAW_N נקודות, מתחיל בשיגור ומסתיים במטרה", all(len(r["path"]) == af.DRAW_N and abs(r["path"][0][2] - 300) < 5 and abs(r["path"][-1][2] - 300) < 5 for r in res["rows"]))  # ציור
check("מפת חום: נקודת השיגור מגיעה ל-60 מסלולים", res["heat"]["launch"][0]["count"] == 60)  # מפת חום
check("מפת חום מטרה: כל נקודה מקבלת 2 מסלולים", all(h["count"] == 2 for h in res["heat"]["target"]))  # מפת חום

# ── סינונים ──
res_f = af.run(dict(BASE, qe_max=800, verify_frac=0), FLAT)  # גבול הגבהה
check("qe_max=800: כל הענף הגבוה נפסל כ-qe_limits", res_f["summary"]["rejected"]["qe_limits"] == 30 and res_f["summary"]["trajectories_feasible"] == 30)  # סינון
res_m = af.run(dict(BASE, min_range_m=50000, verify_frac=0), FLAT)  # טווח מינימלי גדול
check("min_range 50 ק\"מ: הכול נפסל כ-min_range", res_m["summary"]["trajectories_feasible"] == 0 and res_m["summary"]["rejected"]["min_range"] == 60)  # סינון
far = [[p[0] + 0.30, p[1] + 0.30] for p in TGT]  # מטרה רחוקה (~45 ק"מ) — מעבר לטווח המרבי (~18 ק"מ)
res_o = af.run(dict(BASE, target_areas=[{"name": "far", "polygon": far}], verify_frac=0), FLAT)  # מחוץ לטווח
check("מטרה מעבר לטווח המרבי: out_of_range לכל המסלולים", res_o["summary"]["trajectories_feasible"] == 0 and res_o["summary"]["rejected"]["out_of_range"] == 60)  # סינון

# ── רכס סינתטי (A2): חוסם את הענף הנמוך בלבד ──
g0 = af.grid_points(GUN_PT, 500.0)[0]  # נקודת השיגור
i20 = round(0.2 * (af.DRAW_N - 1))  # אינדקס הנקודה ב-20% מהטווח
lo_h = low[0]["path"][i20][2]  # גובה הענף הנמוך ב-20% מהטווח
hi_h = high[0]["path"][i20][2]  # גובה הענף הגבוה באותה נקודה
ridge = (lo_h + hi_h) / 2.0  # רכס בגובה ביניים
d20 = low[0]["range_m"] * 0.2  # 20% מהטווח
def ridge_cells(cells):  # שטח: רצועה בגובה הרכס סביב 20% מהטווח, שטוח בשאר
    out = []  # התוצאה
    for lat, lon in cells:  # כל תא
        d = math.hypot((lat - g0[0]) * af.M_PER_DEG_LAT, (lon - g0[1]) * af.M_PER_DEG_LAT * math.cos(math.radians(g0[0])))  # מרחק מהשיגור
        out.append(ridge if abs(d - d20) < 400 else 300.0)  # רצועה ברוחב 800 מ'
    return out  # הגבהים
res_r = af.run(dict(BASE, crest=True, verify_frac=0), ridge_cells)  # עם רכס
rr = res_r["summary"]  # סיכום
check("רכס: כל הענף הנמוך נחסם (terrain)", rr["rejected"]["terrain"] == 30, str(rr["rejected"]))  # חסימה
check("רכס: הענף הגבוה עובר, וכל הזוגות עדיין אפשריים", rr["trajectories_feasible"] == 30 and rr["pairs_feasible"] == 30 and all(r["group"] == "high" for r in res_r["rows"]))  # עובר
check("רכס: מרווח השטח המינימלי חיובי במסלולים שעברו", all(r["min_terrain_margin_m"] is not None and r["min_terrain_margin_m"] > 0 for r in res_r["rows"]))  # מרווח
res_s = af.run(dict(BASE, crest=True, verify_frac=0), FLAT)  # שטוח עם רכס פעיל
check("שטח שטוח עם בדיקת רכס: אין פסילות שטח", res_s["summary"]["rejected"]["terrain"] == 0 and res_s["summary"]["trajectories_feasible"] == 60)  # בלי חסימה

# ── שיגור במדרון: צפיפות האוויר תלויה בגובה השיגור — הטבלה כוללת צמתי גובה שיגור ──
SLOPE_L = [[31.2000, 34.7500], [31.2000, 34.7618], [31.2100, 34.7618], [31.2100, 34.7500]]  # אזור שיגור ~1.1×1.1 ק"מ (2×2 נקודות ברשת 500 מ')


def slope(cells):  # מדרון: 300 מ' בדרום האזור, 500 מ' בצפונו; שטוח 300 בשאר
    return [300.0 + 200.0 * min(1.0, max(0.0, (lat - 31.2000) / 0.0100)) if lat < 31.215 else 300.0 for lat, lon in cells]  # גובה לפי רוחב (הפרש ~90 מ' בין שורות השיגור)


res_sl = af.run(dict(BASE, launch_areas=[{"name": "מדרון", "polygon": SLOPE_L}], groups=["low"], verify_frac=1.0), slope)  # אימות מלא
vsl = res_sl["verification"]  # האימות
check("שיגור במדרון (הפרש ~90 מ' בין נקודות שיגור): החטאה מרבית ≤ 10 מ'", vsl["miss_max_m"] is not None and vsl["miss_max_m"] <= 10.0, f"{vsl} nodes={res_sl['tables'][0].get('gun_alt_nodes')}")  # דיוק
check("שיגור במדרון: הטבלה כוללת יותר מצומת גובה שיגור אחד", res_sl["tables"][0].get("gun_alt_nodes", 1) >= 2)  # המימד החדש

# ── נראות מכ"ם (A3) ──
rows = res["rows"]  # המסלולים מהריצה הבסיסית (שטח שטוח 300 מ')
vis0 = af.visibility(rows, [], FLAT)  # בלי מכ"מים
check("בלי מכ\"ם: הכול אדום (כל המסיכות 0)", all(x == 0 for m in vis0["masks"] for x in m) and vis0["summary"]["points_seen"] == 0)  # החלטה 14
rad = {"name": "R1", "params": {"lat": g0[0], "lon": g0[1], "h_antenna": 5, "range_km": 100, "start_bearing_deg": 0, "end_bearing_deg": 360, "ridge_margin_deg": 0}}  # מכ"ם בנקודת השיגור
vis1 = af.visibility(rows, af.radar_list([rad]), FLAT)  # שטח שטוח
apex_k = [max(range(len(r["path"])), key=lambda k: r["path"][k][2]) for r in rows]  # נקודת הקודקוד בכל מסלול
check("מכ\"ם בשטח שטוח: הקודקוד של כל מסלול נראה", all(vis1["masks"][i][k] & 1 for i, k in enumerate(apex_k)))  # גבוה = נראה
check("מכ\"ם בשטח שטוח: נקודת הפגיעה (על הקרקע, 15 ק\"מ) מתחת לאופק בגלל העקמומיות", all(not (vis1["masks"][i][-1] & 1) for i in range(len(rows))))  # עקמומיות
vis_r = af.visibility(rows, af.radar_list([dict(rad, params=dict(rad["params"], range_km=5))]), FLAT)  # טווח 5 ק"מ
check("טווח 5 ק\"מ: רק נקודות עד 5 ק\"מ מהמכ\"ם נראות", all(not (vis_r["masks"][i][k] & 1) or rows[i]["range_m"] * k / (af.DRAW_N - 1) <= 5100 for i in range(len(rows)) for k in range(af.DRAW_N)) and vis_r["summary"]["points_seen"] > 0)  # טווח
vis_s = af.visibility(rows, af.radar_list([dict(rad, params=dict(rad["params"], start_bearing_deg=180, end_bearing_deg=270))]), FLAT)  # גזרה דרום-מערבית
check("גזרה 180–270 (המסלולים לכיוון 43°): אף נקודה לא נראית", vis_s["summary"]["points_seen"] == 0)  # גזרה
vis_w = af.visibility(rows, af.radar_list([dict(rad, params=dict(rad["params"], start_bearing_deg=295, end_bearing_deg=65))]), FLAT)  # גזרה דרך צפון
check("גזרה 295→65 דרך צפון: הנקודות נראות כמו בגזרה מלאה", vis_w["summary"]["points_seen"] == vis1["summary"]["points_seen"])  # עטיפה


def wall(cells):  # קיר שטח בגובה 2,000 מ' במרחק 2 ק"מ מהמכ"ם
    out = []  # התוצאה
    for lat, lon in cells:  # כל תא
        d = math.hypot((lat - g0[0]) * af.M_PER_DEG_LAT, (lon - g0[1]) * af.M_PER_DEG_LAT * math.cos(math.radians(g0[0])))  # מרחק
        out.append(2000.0 if 1800 < d < 2200 else 300.0)  # הקיר
    return out  # גבהים


vis_b = af.visibility(rows, af.radar_list([rad]), wall)  # עם קיר
lows = [i for i, r in enumerate(rows) if r["group"] == "low"]  # מסלולים נמוכים
check("קיר שטח: פחות נקודות נראות מאשר בשטח שטוח", vis_b["summary"]["points_seen"] < vis1["summary"]["points_seen"], f"{vis_b['summary']['points_seen']} < {vis1['summary']['points_seen']}")  # חסימה
check("קיר שטח: אמצע המסלול הנמוך (מאחורי הקיר) לא נראה", all(not (vis_b["masks"][i][af.DRAW_N // 2] & 1) for i in lows))  # חסום
rad2 = {"name": "R2", "params": {"lat": g0[0] + 1.0, "lon": g0[1], "h_antenna": 5, "range_km": 30}}  # מכ"ם רחוק (~110 ק"מ) — מחוץ לטווח
vis2 = af.visibility(rows, af.radar_list([rad, rad2]), FLAT)  # שני מכ"מים
check("שני מכ\"מים: ביט לכל מכ\"ם; הרחוק לא רואה כלום", all((x & 2) == 0 for m in vis2["masks"] for x in m) and vis2["summary"]["points_seen"] == vis1["summary"]["points_seen"] and len(vis2["radars"]) == 2)  # מסיכות
check("סיכום נראות: מסלולים נצפים/לא נצפים מסתכמים", vis1["summary"]["trajectories_seen_any"] + vis1["summary"]["trajectories_unseen"] == len(rows))  # עקביות

print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
