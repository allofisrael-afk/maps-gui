# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""FR-D-302: בדיקת מעקב מלאה למאזור לאזור (area_track.py), בלי רשת (שטח שטוח סינתטי).
המקרה שהמשתמש דיווח: מסלול שמשיק למכ"ם (עובר לרוחבו) — המהירות הרדיאלית קרובה לאפס, מתחת לסף הדופלר (MDV), ולכן
המכ"ם לא מגלה אותו (כתום = עיוור לדופלר), גם כשקו הראייה פנוי. מסלול שמתקרב ישר אל המכ"ם — מזוהה.
בודק גם: התאמה לצינור של מסלול בודד (radar_service.run_check), הטוב מכל המכ"מים, מכ"ם בלי גובה, ביטול.
הרצה: .venv\\Scripts\\python.exe tests/test_area_track.py"""
import os  # משתני סביבה
import sys  # sys.path וקוד יציאה

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
os.environ.setdefault("MAPS_GUI_DEM", "off")  # בלי משבצות SRTM
import area_fire  # noqa: E402  # Aborted
import area_track as at  # noqa: E402  # המודול הנבדק
import radar_service as rs  # noqa: E402  # הצינור של מסלול בודד — להשוואה
import radar_track as rt  # noqa: E402  # גיאומטריה

ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


R_LAT, R_LON = 31.25, 34.79  # המכ"ם
flat = lambda cells: [100.0] * len(cells)  # noqa: E731  # שטח שטוח 100 מ'


def row(brg_start, brg_end, d_start, d_end, tof=40.0, apex=3000.0):  # מסלול סינתטי בפורמט area_fire: 21 נקודות [רוחב, אורך, גובה, זמן]
    a = rt.destination_point(R_LAT, R_LON, brg_start, d_start)  # תחילת המסלול
    b = rt.destination_point(R_LAT, R_LON, brg_end, d_end)  # סוף המסלול
    path = []  # הנקודות
    for k in range(21):  # כמו DRAW_N
        f = k / 20.0  # שבר
        path.append([a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), 150.0 + apex * 4 * f * (1 - f), tof * f])  # פרבולה
    return {"path": path}  # שורה


# משיק: עובר מצפון לדרום במרחק ~15 ק"מ מזרחית למכ"ם (קו ישר שהמכ"ם רואה מהצד) — המהירות הרדיאלית קרובה לאפס באמצע
tangent = row(60.0, 120.0, 17320.0, 17320.0)  # מ-60° ל-120°, אותו מרחק → חוצה את כיוון 90° בניצב לקו הראייה
radial = row(90.0, 90.0, 30000.0, 8000.0)  # מתקרב ישר אל המכ"ם מכיוון מזרח
body = {"lat": R_LAT, "lon": R_LON, "h_antenna": 10, "range_km": 60, "rcs_m2": 5, "power_kw": 500, "mdv_kt": 30, "prf_hz": 3000, "freq_mhz": 1300,  # סף דופלר 30 קשר; L-band + PRF 3000: טווח חד-ערכי 50 ק"מ ומהירות עיוורת ראשונה 346 מ'/ש — רחוק מ-~550 מ'/ש של המסלול הרדיאלי
        "vertical_center_deg": 45, "vertical_width_deg": 90, "track_mode": "detection"}  # בלי מגבלות זווית, מצב גילוי
radars = at.parse_radars([{"name": "R1", "body": body}])  # מכ"ם אחד
out = at.track_check([tangent, radial], radars, flat)  # הבדיקה
mid = out["states"][0][10]  # נקודת האמצע של המשיק
check("משיק למכ\"ם: באמצע המסלול — עיוור לדופלר (קוד 2), למרות קו ראייה פנוי", mid == 2, f"code={mid} ({at.CODES[mid]})")  # המקרה של המשתמש
check("מתקרב ישר אל המכ\"ם: רוב הנקודות מזוהות (קוד 3)", sum(1 for c in out["states"][1] if c == 3) >= 15, str(out["states"][1]))  # רדיאלי
check("סיכום: הנקודות לפי מצב כוללות עיוור לדופלר", out["summary"]["points_by_state"]["doppler_blind"] > 0, str(out["summary"]["points_by_state"]))  # סיכום

# אותה תוצאה כמו בצינור של מסלול בודד ("בדוק מעקב מכ"ם")
for name, r in (("משיק", tangent), ("רדיאלי", radial)):  # שני המסלולים
    traj = [{"t": q[3], "lat": q[0], "lon": q[1], "alt": q[2]} for q in r["path"]]  # המסלול
    ref = rs.run_check(R_LAT, R_LON, radars[0]["p"], traj, radars[0]["cfg"], "msl", flat)  # הצינור הקיים
    times = [p["t"] for p in ref["points"]]  # זמנים
    exp = [at.point_code(ref["points"][rt._nearest_index(times, q[3])]) for q in r["path"]]  # המצבים הצפויים
    got = out["states"][0 if name == "משיק" else 1]  # שהתקבלו
    check(f"{name}: זהה לבדיקת מסלול בודד בכל 21 הנקודות", exp == got, f"{exp} vs {got}")  # עקביות

# מצב מעקב: נפתח מעקב על הרדיאלי, זמן מעקב ראשון וזמן התרעה
bt = dict(body, track_mode="track", scan_mode="phased", revisit_s=0.5, mdv_kt=5)  # מעקב
out_t = at.track_check([radial], at.parse_radars([{"name": "R1", "body": bt}]), flat)  # הבדיקה
pr = out_t["rows"][0]  # מדדי המסלול
check("מצב מעקב: נפתח מעקב, זמן ראשון וזמן התרעה", pr["tk"] == 1 and pr["ft"] is not None and pr["ws"] is not None and 5 in out_t["states"][0], str(pr))  # מעקב

# הטוב מכל המכ"מים: מכ"ם שני שרואה את המשיק בצורה רדיאלית (מצפון) מתקן את הכתום
tan_mid = tangent["path"][10]  # נקודת האמצע של המשיק
north = rt.destination_point(tan_mid[0], tan_mid[1], 0.0, 15000.0)  # מכ"ם מצפון לאמצע — המסלול נע לכיוונו/ממנו
two = at.parse_radars([{"name": "R1", "body": body}, {"name": "R2", "body": dict(body, lat=north[0], lon=north[1])}])  # שני מכ"מים
out2 = at.track_check([tangent], two, flat)  # הבדיקה
check("שני מכ\"מים: באמצע המשיק — מזוהה (המכ\"ם השני), ושני הביטים ב-by", out2["states"][0][10] == 3 and out2["rows"][0]["by"] & 2, f"code={out2['states'][0][10]} by={out2['rows'][0]['by']}")  # הטוב מכולם

# מכ"ם בלי גובה קרקע (למשל בים) — מדווח, לא קורס
out3 = at.track_check([radial], radars, lambda cells: [None] * len(cells))  # אין גבהים
check("מכ\"ם בלי גובה: שגיאה מוסברת בסטטיסטיקה, הכול מחוץ לטווח", bool(out3["radars"][0]["error"]) and set(out3["states"][0]) == {0}, str(out3["radars"][0]))  # בלי קריסה

# ביטול
try:  # ביטול מיידי
    at.track_check([radial], radars, flat, cancelled=lambda: True)  # מבוטל
    check("ביטול → Aborted", False)  # לא אמור להגיע
except area_fire.Aborted:  # צפוי
    check("ביטול → Aborted", True)  # תקין
check("מכ\"ם בלי מיקום תקין — מדולג ב-parse_radars", at.parse_radars([{"name": "X", "body": {"lat": 999, "lon": 0}}, {"body": {}}]) == [])  # קלט שגוי
print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
