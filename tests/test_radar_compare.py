# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""T30: השוואת כל המכ"מים המוצבים על אותו מסלול (radar_service.compare_sites + POST /radar_track/compare).
בלי רשת: שטח שטוח סינתטי, קובץ עמדות ומטמון זמניים. הרצה: .venv\\Scripts\\python.exe tests/test_radar_compare.py"""
import json  # קובץ העמדות
import os  # נתיבים ומשתני סביבה
import sys  # sys.path וקוד יציאה
import tempfile  # קבצים זמניים
import time  # המתנה ל-job

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
TMP = tempfile.mkdtemp(prefix="radar_cmp_")  # תיקייה זמנית
os.environ.setdefault("MAPS_GUI_ELEV_CACHE", os.path.join(TMP, "c.sqlite"))  # T23: מטמון זמני (גבהים מזויפים)
os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות
os.environ["MAPS_GUI_STATIONS_FILE"] = os.path.join(TMP, "s.json")  # T24: קובץ עמדות זמני
os.environ.pop("MAPS_GUI_APP_TOKEN", None)  # T5: בלי אכיפת טוקן ב-test client
import radar_service as rs  # noqa: E402  # השירות

ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


lib = rs.load_profile_library()  # הספרייה המובנית
lib_file = next((x["file"] for x in lib if "2084" in x["file"]), lib[0]["file"])  # סוג מהספרייה
merged = rs.site_params({"name": "A", "params": {"type_key": "lib:" + lib_file, "lat": 31.2, "lon": 34.8, "range_km": 33}}, lib, {})  # מיזוג
check("site_params: פרמטרי הסוג + ההצבה (ההצבה גוברת)", merged.get("range_km") == 33 and "freq_mhz" in merged and "type_key" not in merged)  # מיזוג
mine = rs.site_params({"params": {"type_key": "my:שלי", "lat": 31, "lon": 34}}, lib, {"שלי": {"power_kw": 7}})  # פרופיל שלי
check("site_params: פרופיל 'שלי' לפי שם", mine.get("power_kw") == 7 and mine.get("lat") == 31)  # מיזוג

traj = [{"t": i * 1.0, "lat": 31.20 + i * 0.003, "lon": 34.80, "alt": 300 + 40 * i - 0.4 * i * i} for i in range(60)]  # מסלול בליסטי פשוט צפונה
sites = [{"name": "קרוב", "params": {"type_key": "lib:" + lib_file, "lat": 31.18, "lon": 34.78, "h_antenna": 5, "range_km": 50,  # קרוב — רואה
                                     "start_bearing_deg": 0, "end_bearing_deg": 360}},
         {"name": "רחוק", "params": {"type_key": "lib:" + lib_file, "lat": 32.5, "lon": 35.5, "h_antenna": 5, "range_km": 20}},  # ~150 ק"מ — לא רואה
         {"name": "שבור", "params": {"type_key": "lib:" + lib_file, "lat": 999, "lon": 34.8}}]  # מיקום לא תקין
with open(os.environ["MAPS_GUI_STATIONS_FILE"], "w", encoding="utf-8") as f:  # קובץ העמדות הזמני
    json.dump({"radar_sites": sites}, f, ensure_ascii=False)  # המכ"מים
import weather_server as ws  # noqa: E402  # השרת

ws._fetch_elevations = lambda locs: ([300.0] * len(locs), None)  # שטח שטוח, בלי רשת
ws._radar_track_sleep = lambda job_id, s: True  # בלי השהיות קצב
c = ws.app.test_client()  # לקוח בדיקה
r = c.post("/radar_track/compare", json={"trajectory": traj, "alt_ref": "msl"})  # ההשוואה
check("compare: התחיל עם 3 מכ\"מים", r.status_code == 200 and r.get_json().get("radars") == 3, str(r.get_json()))  # התחלה
jid = r.get_json()["job_id"]  # המזהה
for _ in range(600):  # המתנה
    st = c.get("/radar_doppler/status?job_id=" + jid).get_json()  # מצב
    if st["status"] != "running":  # הסתיים
        break  # יציאה
    time.sleep(0.1)  # המתנה
res = st.get("result") or {}  # התוצאה
rows = {x["name"]: x for x in res.get("rows", [])}  # לפי שם
check("compare: הסתיים עם שורה לכל מכ\"ם", st["status"] == "done" and len(rows) == 3, str(st.get("error")))  # הצלחה
check("compare: הקרוב רואה (גילוי ראשון ואחוז כיסוי)", rows.get("קרוב", {}).get("detected") is True and rows["קרוב"].get("first_detection_t") is not None, str(rows.get("קרוב")))  # רואה
check("compare: הרחוק לא רואה", rows.get("רחוק", {}).get("ok") is True and rows["רחוק"].get("detected") is False)  # לא רואה
check("compare: מיקום לא תקין — שורת שגיאה, והשאר ממשיכים", rows.get("שבור", {}).get("ok") is False and "מיקום" in rows["שבור"].get("error", ""))  # שגיאה מבודדת
check("compare: סיכום — 1 רואה, הראשון 'קרוב'", res.get("summary", {}).get("seeing") == 1 and res["summary"].get("first") == "קרוב")  # סיכום
with open(os.environ["MAPS_GUI_STATIONS_FILE"], "w", encoding="utf-8") as f:  # בלי מכ"מים
    json.dump({}, f)  # ריק
check("compare בלי מכ\"מים מוצבים → 400 עם הסבר", c.post("/radar_track/compare", json={"trajectory": traj}).status_code == 400)  # הסבר
print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
