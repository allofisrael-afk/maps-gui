# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות radar_android.py (FR-D-282) — בדיוק כמו שה-Kotlin קורא: mpm_api.dispatch_json(action, params_json) עם
מחרוזות JSON, ושאילת מצב עד הסיום. השליפה מ-Open-Meteo מוחלפת בפונקציה מזויפת (בלי רשת).
הרצה: python tests/test_radar_android.py
"""
import json  # מחרוזות JSON כמו מה-Dart
import os  # נתיב שורש
import sys  # sys.path וקוד יציאה
import time  # המתנה

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט
os.environ.setdefault("MAPS_GUI_ELEV_CACHE", os.path.join(__import__("tempfile").mkdtemp(prefix="elevcache_test_"), "c.sqlite"))  # T23: הבדיקה מזריקה גבהים מזויפים — מטמון זמני, לעולם לא המטמון האמיתי של המשתמש
os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות

import mpm_api  # נקודת הכניסה של ה-Kotlin
import radar_android as ra  # המתאם
import radar_track as rt  # גיאודזיה לבניית מסלול

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # עברית בקונסולה
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

results = []  # תוצאות


def check(name, cond, info=""):
    """רושם ומדפיס בדיקה."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


calls = []  # כמה בקשות "יצאו לרשת"
ra._http_elevations = lambda cells: (calls.append(len(cells)), [100.0 for _ in cells])[1]  # שטח שטוח, בלי רשת
ra.LOCS_PER_MIN = 10 ** 9  # בלי השהיית קצב בבדיקה


def call(action, params):
    """כמו MpmBridge.call ב-Dart."""
    return json.loads(mpm_api.dispatch_json(action, json.dumps(params)))  # JSON פנימה, JSON החוצה


def wait(job_id):
    """שואל מצב עד הסיום, כמו ה-polling ב-Dart."""
    for _ in range(300):  # עד ~30 שנ'
        st = call("radar_job_status", {"job_id": job_id})  # המצב
        if st["status"] != "running":  # הסתיים
            return st  # התוצאה
        time.sleep(0.1)  # המתנה
    return {"status": "timeout"}  # לא הסתיים


R_LAT, R_LON = 31.25, 34.80  # מכ"ם
traj = []  # קשת מזרחה
for i in range(41):  # 20 שנ'
    lat, lon = rt.destination_point(R_LAT, R_LON, 90.0, (6 + 0.2 * i) * 1000.0)  # מיקום
    traj.append({"t": i * 0.5, "lat": lat, "lon": lon, "alt": 500.0 + 40.0 * i})  # עולה
BASE = {"lat": R_LAT, "lon": R_LON, "trajectory": traj, "vertical_center_deg": 45, "vertical_width_deg": 90,
        "rcs_m2": 5, "power_kw": 500, "prf_hz": 5000, "mdv_kt": 5, "track_mode": "track", "scan_mode": "phased"}  # הבקשה

t0 = time.time()  # זמן ההתחלה
start = call("radar_check_start", BASE)  # התחלה
check("radar_check_start: חוזר מיד עם job_id", start.get("ok") and start.get("job_id") and time.time() - t0 < 1.0, str(start)[:80])
st = wait(start["job_id"])  # המתנה
check("בדיקה: הסתיימה בהצלחה", st["status"] == "done", st.get("error") or st["status"])
if st["status"] == "done":  # המבנה
    r = st["result"]  # התוצאה
    check("בדיקה: מבנה כמו בשרת (points/summary/track/beam/terrain)", all(k in r for k in ("points", "summary", "track", "beam", "terrain")))
    check("בדיקה: נפתח מעקב", r["track"]["track_initiated"], str(r["track"]["first_track_t"]))
n_calls = len(calls)  # בקשות עד כה
st2 = wait(call("radar_check_start", BASE)["job_id"])  # שוב — הכל מהמטמון
check("מטמון: הרצה חוזרת בלי בקשות חדשות", st2["status"] == "done" and len(calls) == n_calls, f"{len(calls) - n_calls} בקשות חדשות")
pr = wait(call("radar_profile_start", {"lat": R_LAT, "lon": R_LON, "point": {"lat": traj[0]["lat"], "lon": traj[0]["lon"], "alt": 500}})["job_id"])  # פרופיל
check("פרופיל: הסתיים, קו פנוי מעל שטח שטוח", pr["status"] == "done" and pr["result"]["visible"], pr.get("error") or "")
pl_start = call("radar_placement_start", dict(BASE, radius_km=1, step_m=500, metric="coverage"))  # הצעת מיקום
check("הצעת מיקום: 13 מועמדים מדווחים מיד", pl_start.get("candidates") == 13, str(pl_start)[:80])
pl = wait(pl_start["job_id"])  # המתנה
check("הצעת מיקום: הסתיימה", pl["status"] == "done" and len(pl["result"]["candidates"]) == 13, pl.get("error") or pl["status"])
rk = wait(call("rocket_start", {"gun": {"lat": R_LAT, "lon": R_LON, "alt_m": 100}, "elev_deg": 45, "azimuth_deg": 90,
                                "rocket": {"mass_kg": 40, "prop_kg": 12, "burn_s": 2, "thrust_n": 12000, "diam_m": 0.15, "cd": 0.4},
                                "met": {"source": "standard"}})["job_id"])  # רקטה
check("רקטה: הסתיימה עם מסלול ופגיעה", rk["status"] == "done" and rk["result"]["ok"] and rk["result"]["impact"]["range_m"] > 1000,
      rk.get("error") or str(rk["result"].get("impact")))
ra._http_elevations = lambda cells: (time.sleep(0.3), [100.0 for _ in cells])[1]  # שליפה איטית — כדי שיהיה זמן לבטל
ra._STORE = ra.elev_cache.ElevCache(":memory:")  # T23: מטמון ריק בזיכרון — כדי שהשליפה האיטית באמת תרוץ ויהיה זמן לבטל
cj = call("radar_check_start", BASE)["job_id"]  # התחלה
call("radar_job_cancel", {"job_id": cj})  # ביטול מיד
check("ביטול: העבודה נעצרת עם status=cancelled", wait(cj)["status"] == "cancelled")
check("פעולה לא מוכרת: שגיאה ברורה", call("radar_nope", {}).get("ok") is False)
lib = call("radar_profiles_library", {})  # FR-D-286: הספרייה המובנית — כמו שה-Kotlin קורא
import radar_service as _rs  # noqa: E402 — אותה ספרייה כמו בשרת, להשוואה
check("ספריית פרופילים: ok, אותה רשימה כמו בשרת, עם שם ופרמטרים", lib.get("ok") is True
      and [p["name"] for p in lib.get("profiles", [])] == [p["name"] for p in _rs.load_profile_library()]
      and len(lib["profiles"]) >= 13 and all(p["name"] and p["params"] for p in lib["profiles"]), str(len(lib.get("profiles", []))))
check("קלט שגוי (בלי מסלול): שגיאה ברורה, בלי קריסה", call("radar_check_start", {"lat": 31, "lon": 34}).get("ok") is False)
check("הכלי הבליסטי לא הושפע מהניתוב", json.loads(mpm_api.dispatch_json("nope_action", "{}"))["ok"] is False)

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה
