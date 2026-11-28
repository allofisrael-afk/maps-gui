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
    os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות
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
    # ── 28/11: רזולוציה, תקרת אימות, זמן שנותר, מדגם למפה ──
    import area_fire  # 28/11: המנוע (לבדיקות ישירות)
    est2 = c.post("/ballistics/area/estimate", json=dict(req, target_res_m=400)).get_json()  # 28/11: רזולוציית מטרה גסה פי 2
    check("רזולוציה: target_res_m=400 → פחות נקודות מטרה מברירת המחדל", 0 < est2.get("target_points", 0) < est["target_points"] and est2.get("resolution_m") == {"launch": 500.0, "target": 400.0}, str(est2.get("target_points")))  # 28/11: הרזולוציה משפיעה
    check("רזולוציה: ריק = ברירת מחדל (500/200)", est.get("resolution_m") == {"launch": 500.0, "target": 200.0}, str(est.get("resolution_m")))  # 28/11: ברירת מחדל
    bad_res = c.post("/ballistics/area/start", json=dict(req, launch_res_m=10))  # 28/11: מחוץ לטווח
    check("רזולוציה מחוץ לטווח (10 מ') → 400 עם הודעה", bad_res.status_code == 400 and "רזולוציה" in bad_res.get_json().get("error", ""))  # 28/11: ולידציה
    check("הערכה כוללת את זמן האימות", "verify" in (est.get("eta_parts_s") or {}), str(est.get("eta_parts_s")))  # 28/11: אימות בהערכה
    check("תקרת אימות: 5% ממיליון = 2,000 (לא 50,000)", area_fire._verify_n(1_000_000, 0.05) == 2000 and area_fire._verify_n(100, 0.05) == 5)  # 28/11: תקרה
    ticks = []  # 28/11: דיווחי ההתקדמות
    area_fire.run(req, lambda pts: [300.0] * len(pts), progress=ticks.append)  # 28/11: חישוב ישיר (סדרתי)
    stages = {t["stage"] for t in ticks if t.get("eta_total_s") is not None}  # 28/11: שלבים עם זמן שנותר
    check("זמן שנותר לכל החישוב מדווח בשלבי הטבלה/הזוגות/האימות", {"pairs", "verify"} <= stages, str(sorted(stages)))  # 28/11: הערכה מלאה
    ws.AREA_MAP_ROWS_MAX = 10  # 28/11: סף קטן — כדי לבדוק מדגם עם 60 מסלולים
    r3 = c.post("/ballistics/area/start", json=req).get_json()  # 28/11: חישוב חדש (המדגם נקבע לכל job)
    st3 = wait(r3["job_id"])  # 28/11: המתנה
    res3 = st3.get("result") or {}  # 28/11: התוצאה כפי שנשלחה למפה
    check("תוצאה גדולה: למפה נשלח מדגם (10 מתוך 60) עם rows_total", len(res3.get("rows", [])) == 10 and res3.get("rows_total") == 60 and res3.get("rows_sampled") is True and res3["summary"]["trajectories_feasible"] == 60, f"{len(res3.get('rows', []))} {res3.get('rows_total')}")  # 28/11: מדגם
    v3 = c.post("/ballistics/area/visibility", json={"job_id": r3["job_id"]}).get_json()  # 28/11: צביעה
    vs3 = wait(v3["job_id"])  # 28/11: המתנה
    check("צביעה של תוצאה גדולה: מסיכות רק למסלולים שבמפה (10), הסיכום מכולם", len((vs3.get("result") or {}).get("masks", [])) == 10 and vs3["result"]["summary"]["points"] == 60 * area_fire.DRAW_N, str(len((vs3.get("result") or {}).get("masks", []))))  # 28/11: מסיכות לפי המדגם
    rows3 = list(csv.reader(io.StringIO(c.get(f"/ballistics/area/csv?job_id={r3['job_id']}&vis_job={v3['job_id']}").get_data(as_text=True).lstrip("﻿"))))  # 28/11: CSV
    check("CSV של תוצאה גדולה: כל 60 המסלולים, עם נראות", len(rows3) == 61 and rows3[1][-1] == "R-test", str(len(rows3)))  # 28/11: CSV מלא
    # ── FR-D-302: בדיקת מעקב מלאה (דופלר + משוואת מכ"ם + מעקב) לכל המסלולים ──
    rb = {"lat": gun[0], "lon": gun[1], "h_antenna": 5, "range_km": 100, "rcs_m2": 5, "power_kw": 500, "mdv_kt": 5,  # מכ"ם חזק ליד אזור השיגור
          "vertical_center_deg": 45, "vertical_width_deg": 90, "track_mode": "track", "scan_mode": "phased", "revisit_s": 0.5}  # כמו בבדיקות radar_service
    vf = c.post("/ballistics/area/visibility", json={"job_id": r3["job_id"], "mode": "full", "radars": [{"name": "R-full", "body": rb}]}).get_json()  # בדיקה מלאה
    check("בדיקה מלאה: ה-job התחיל עם המכ\"ם שנשלח", vf.get("radars") == ["R-full"], str(vf))  # התחלה
    vfs = wait(vf["job_id"])  # המתנה
    vfr = vfs.get("result") or {}  # התוצאה (מדגם — AREA_MAP_ROWS_MAX עדיין 10)
    check("בדיקה מלאה: mode=full, מצבים לכל נקודה (מדגם 10), מדדי מסלול", vfs.get("status") == "done" and vfr.get("mode") == "full" and len(vfr.get("states", [])) == 10 and len(vfr["states"][0]) == area_fire.DRAW_N and len(vfr.get("rows", [])) == 10, str(vfs.get("error")))  # מבנה
    check("בדיקה מלאה: הסיכום מכל 60 המסלולים, חלק במעקב", vfr.get("summary", {}).get("trajectories") == 60 and vfr["summary"]["trajectories_tracked"] > 0, str(vfr.get("summary")))  # סיכום
    rows4 = list(csv.reader(io.StringIO(c.get(f"/ballistics/area/csv?job_id={r3['job_id']}&vis_job={vf['job_id']}").get_data(as_text=True).lstrip("﻿"))))  # CSV
    hdr = rows4[0]  # כותרת
    check("CSV של בדיקה מלאה: עמודות מעקב, 60 שורות, מי זיהה", len(rows4) == 61 and hdr[-5:] == ["tracked", "first_track_t_s", "warning_time_s", "seen_fraction", "seen_by"] and any(r_[-5] == "כן" for r_ in rows4[1:]) and any(r_[-1] == "R-full" for r_ in rows4[1:]), str(hdr[-5:]))  # CSV
    vl = c.post("/ballistics/area/visibility", json={"job_id": r3["job_id"]}).get_json()  # בלי mode — קו ראייה כמו קודם
    vls = wait(vl["job_id"])  # המתנה
    check("בלי mode — צביעת קו ראייה כמו קודם (masks)", "masks" in (vls.get("result") or {}) and (vls.get("result") or {}).get("mode") != "full")  # תאימות
    ws.AREA_MAP_ROWS_MAX = 20000  # 28/11: החזרה
    r2 = c.post("/ballistics/area/start", json=req).get_json()  # התחלה נוספת
    c.post(f"/ballistics/area/cancel?job_id={r2['job_id']}")  # ביטול מיידי
    st2 = wait(r2["job_id"])  # המתנה
    check("ביטול: ה-job מסתיים כ-cancelled או done (אם הספיק — הטבלה במטמון)", st2.get("status") in ("cancelled", "done"), str(st2.get("status")))  # ביטול
    check("status ל-job לא קיים → 404", c.get("/ballistics/area/status?job_id=nope").status_code == 404)  # שגיאה
    print(f"\n{ok[0]}/{ok[0] + ok[1]} passed")  # סיכום
    sys.exit(1 if ok[1] else 0)  # קוד יציאה


if __name__ == "__main__":  # שומר מפני הרצה חוזרת בתהליכי ה-spawn
    main()  # הרצה
