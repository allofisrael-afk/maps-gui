# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""A4: בדיקות לנקודות הקצה של "מאזור לאזור" בשרת (Flask test client, in-process). בלי רשת: שטח שטוח סינתטי,
קובץ עמדות זמני ומטמון גבהים זמני — לא נוגע בנתוני המשתמש. בודק גם חישוב במקביל (ProcessPoolExecutor).
הרצה: .venv\\Scripts\\python.exe tests/test_area_fire_server.py"""
import csv  # פענוח ה-CSV
import io  # קריאת ה-CSV מהזיכרון
import json  # קובץ העמדות
import os  # נתיבים ומשתני סביבה
import sys  # sys.path וקוד יציאה
import tempfile  # קבצים זמניים
import time  # המתנה לסיום job


def main():  # הכול בתוך main — חובה עם ProcessPoolExecutor ב-Windows (spawn מייבא את הקובץ מחדש בכל תהליך)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
    sys.path.insert(0, root)  # ייבוא השרת
    tmp = tempfile.mkdtemp(prefix="area_srv_")  # תיקייה זמנית
    gun = (31.2008, 34.7510)  # מיקום מכ"ם הבדיקה (ליד אזור השיגור)
    with open(os.path.join(tmp, "s.json"), "w", encoding="utf-8") as f:  # קובץ עמדות זמני עם מכ"ם מוצב אחד
        json.dump({"radar_sites": [{"name": "R-test", "params": {"lat": gun[0], "lon": gun[1], "h_antenna": 5, "range_km": 100,
                                                                 "start_bearing_deg": 0, "end_bearing_deg": 360, "ridge_margin_deg": 0}}]}, f)  # המכ"ם
    os.environ["MAPS_GUI_STATIONS_FILE"] = os.path.join(tmp, "s.json")  # T24: השרת קורא את הקובץ הזמני
    os.environ["MAPS_GUI_ELEV_CACHE"] = os.path.join(tmp, "elev.sqlite")  # T23: מטמון זמני
    os.environ.pop("MAPS_GUI_APP_TOKEN", None)  # T5: בלי אכיפת טוקן ב-test client
    import weather_server as ws  # השרת

    ws._fetch_elevations = lambda locs: ([300.0] * len(locs), None)  # שטח שטוח 300 מ', בלי רשת
    ws._RADAR_TRACK_SEC_PER_BATCH = 0.0  # בלי השהיות קצב בבדיקה
    ws._radar_track_sleep = lambda job_id, s: True  # כנ"ל
    c = ws.app.test_client()  # לקוח בדיקה
    ok = [0, 0]  # מונים

    def check(name, cond, info=""):  # רישום תוצאה
        ok[0 if cond else 1] += 1  # עדכון
        print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט

    def wait(job_id, limit=300):  # המתנה לסיום job
        for _ in range(limit * 4):  # עד limit שניות
            st = c.get(f"/ballistics/area/status?job_id={job_id}").get_json()  # מצב
            if st.get("status") != "running":  # הסתיים
                return st  # התוצאה
            time.sleep(0.25)  # המתנה
        return st  # timeout

    req = {"launch_areas": [{"name": "שיגור א", "polygon": [[31.2000, 34.7500], [31.2000, 34.7520], [31.2015, 34.7520], [31.2015, 34.7500]]}],  # אזור שיגור (נקודה אחת)
           "target_areas": [{"name": "=מטרה", "polygon": [[31.3000, 34.8600], [31.3000, 34.8700], [31.3100, 34.8700], [31.3100, 34.8600]]}],  # שם שמתחיל ב-= (בדיקת CSV)
           "mv": 684, "met": {"source": "standard"}, "groups": ["low", "high"], "crest": True, "verify_frac": 0.2}  # בקשה
    est = c.post("/ballistics/area/estimate", json=req).get_json()  # הערכה
    check("estimate: 30 זוגות, 60 מסלולים מרביים, הערכת זמן", est.get("pairs") == 30 and est.get("trajectories_max") == 60 and isinstance(est.get("eta_s"), int), str(est))  # הערכה
    bad = c.post("/ballistics/area/start", json=dict(req, launch_areas=[{"polygon": [[31, 34]]}]))  # קלט שגוי
    check("start עם מצולע שגוי → 400 עם הודעה", bad.status_code == 400 and "מצולע" in bad.get_json().get("error", ""))  # ולידציה
    r = c.post("/ballistics/area/start", json=req).get_json()  # התחלה
    st = wait(r["job_id"])  # המתנה
    res = st.get("result") or {}  # התוצאה
    s = res.get("summary", {})  # הסיכום
    check("job הסתיים בהצלחה (במקביל על כמה תהליכים)", st.get("status") == "done", str(st.get("error")))  # הצלחה
    check("ספירות בתוצאה: 30 זוגות אפשריים, 60 מסלולים", s.get("pairs_feasible") == 30 and s.get("trajectories_feasible") == 60, str(s))  # ספירה
    check("אימות דיוק בתוצאה (החטאה ≤ 10 מ')", (res.get("verification") or {}).get("miss_max_m", 99) <= 10)  # דיוק
    v = c.post("/ballistics/area/visibility", json={"job_id": r["job_id"]}).get_json()  # צביעה
    check("visibility לקח את המכ\"ם המוצב מקובץ העמדות", v.get("radars") == ["R-test"], str(v))  # החלטה 14
    vs = wait(v["job_id"])  # המתנה
    vr = vs.get("result") or {}  # תוצאת הצביעה
    check("visibility: מסיכה לכל נקודה בכל מסלול, חלק נצפה", vs.get("status") == "done" and len(vr.get("masks", [])) == 60 and vr["summary"]["points_seen"] > 0, str(vr.get("summary")))  # צביעה
    csv_r = c.get(f"/ballistics/area/csv?job_id={r['job_id']}&vis_job={v['job_id']}")  # ייצוא
    text = csv_r.get_data(as_text=True).lstrip("﻿")  # בלי BOM
    rows = list(csv.reader(io.StringIO(text)))  # השורות
    check("CSV: כותרת + 60 שורות, עם נראות", csv_r.status_code == 200 and len(rows) == 61 and rows[0][-1] == "seen_by" and rows[1][-1] == "R-test", str(len(rows)))  # ייצוא
    check("CSV: שם שמתחיל ב-= מנוטרל (גרש) — הגנה מהזרקת נוסחה", rows[1][4].startswith("'="), rows[1][4])  # CWE-1236
    r2 = c.post("/ballistics/area/start", json=req).get_json()  # התחלה נוספת
    c.post(f"/ballistics/area/cancel?job_id={r2['job_id']}")  # ביטול מיידי
    st2 = wait(r2["job_id"])  # המתנה
    check("ביטול: ה-job מסתיים כ-cancelled או done (אם הספיק — הטבלה במטמון)", st2.get("status") in ("cancelled", "done"), str(st2.get("status")))  # ביטול
    check("status ל-job לא קיים → 404", c.get("/ballistics/area/status?job_id=nope").status_code == 404)  # שגיאה
    print(f"\n{ok[0]}/{ok[0] + ok[1]} passed")  # סיכום
    sys.exit(1 if ok[1] else 0)  # קוד יציאה


if __name__ == "__main__":  # שומר מפני הרצה חוזרת בתהליכי ה-spawn
    main()  # הרצה
