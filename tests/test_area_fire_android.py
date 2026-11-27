# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""A6: בדיקת שכבת ה-Python של האנדרואיד ל"מאזור לאזור" — דרך mpm_api.dispatch_json, בדיוק כמו ש-Kotlin/Dart קוראים לה.
בלי רשת: שליפת הגבהים מוחלפת בשטח שטוח; מטמון גבהים זמני. הרצה: .venv\\Scripts\\python.exe tests/test_area_fire_android.py"""
import json  # קידוד הבקשות והתשובות
import os  # נתיבים ומשתני סביבה
import sys  # sys.path וקוד יציאה
import tempfile  # מטמון זמני
import time  # המתנה לסיום job

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
os.environ["MAPS_GUI_ELEV_CACHE"] = os.path.join(tempfile.mkdtemp(prefix="af_android_"), "c.sqlite")  # T23: מטמון זמני
import mpm_api  # noqa: E402  # נקודת הכניסה של האנדרואיד
import radar_android as ra  # noqa: E402  # השכבה הנבדקת

ra._http_elevations = lambda cells: [300.0] * len(cells)  # שטח שטוח, בלי רשת
ra._sleep = lambda job_id, s: True  # בלי השהיות קצב
ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


def call(action, params):  # קריאה כמו מה-Dart: JSON פנימה, JSON החוצה
    return json.loads(mpm_api.dispatch_json(action, json.dumps(params)))  # התשובה


def wait(job_id, limit=300):  # המתנה לסיום job
    for _ in range(limit * 4):  # עד limit שניות
        st = call("radar_job_status", {"job_id": job_id})  # מצב
        if st.get("status") != "running":  # הסתיים
            return st  # התוצאה
        time.sleep(0.25)  # המתנה
    return st  # timeout


req = {"launch_areas": [{"name": "L", "polygon": [[31.2000, 34.7500], [31.2000, 34.7520], [31.2015, 34.7520], [31.2015, 34.7500]]}],  # שיגור (נקודה אחת)
       "target_areas": [{"name": "T", "polygon": [[31.3000, 34.8600], [31.3000, 34.8700], [31.3100, 34.8700], [31.3100, 34.8600]]}],  # מטרה (30 נקודות)
       "mv": 684, "met": {"source": "standard"}, "groups": ["low", "high"], "crest": True, "verify_frac": 0.2}  # בקשה
est = call("radar_area_estimate", req)  # הערכה
check("הערכה: 30 זוגות", est.get("pairs") == 30 and "eta_s" in est, str(est.get("pairs")))  # הערכה
bad = call("radar_area_start", dict(req, target_areas=[]))  # קלט שגוי
check("קלט שגוי → ok=false עם הודעה", bad.get("ok") is False and bool(bad.get("error")), str(bad))  # ולידציה
st = wait(call("radar_area_start", req)["job_id"])  # החישוב
res = st.get("result") or {}  # התוצאה
check("החישוב הסתיים: 60 מסלולים אפשריים", st.get("status") == "done" and res.get("summary", {}).get("trajectories_feasible") == 60, str(st.get("error")))  # הצלחה
check("סטטוס מחזיר eta_s (T23)", "eta_s" in st)  # הערכת זמן
job_id = None  # מזהה החישוב — לצביעה ול-CSV
with ra._JOBS_LOCK:  # מוצאים את ה-job שהסתיים
    job_id = [k for k, v in ra._JOBS.items() if isinstance(v.get("result"), dict) and "rows" in v["result"]][-1]  # האחרון
sites = [{"name": "R1", "params": {"lat": 31.2008, "lon": 34.7510, "h_antenna": 5, "range_km": 100}}]  # מכ"ם מוצב (פורמט radar_sites)
v = call("radar_area_visibility", {"job_id": job_id, "sites": sites})  # צביעה
vs = wait(v["job_id"])  # המתנה
check("צביעה: מסיכה ל-60 מסלולים, חלק נצפה", vs.get("status") == "done" and len(vs["result"]["masks"]) == 60 and vs["result"]["summary"]["points_seen"] > 0)  # צביעה
csv_out = call("radar_area_csv", {"job_id": job_id, "vis_job": v["job_id"]})  # CSV
lines = csv_out.get("csv", "").lstrip("﻿").strip().splitlines()  # שורות
check("CSV: כותרת + 60 שורות, עם נראות", len(lines) == 61 and lines[1].endswith("R1"), str(len(lines)))  # ייצוא
with ra._JOBS_LOCK:  # שמירה ארוכה
    check("תוצאת מאזור לאזור נשמרת שעות (ttl)", ra._JOBS[job_id]["ttl"] == ra.AREA_TTL_S and "finished" in ra._JOBS[job_id])  # A6
print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
