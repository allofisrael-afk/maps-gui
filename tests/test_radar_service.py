# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות radar_service.py (FR-D-281) — הצינורות המשותפים ל-Desktop ול-Android — וגם השרת עצמו אחרי שהועבר
אליהם: Flask test client מול /radar_track/start, /radar_track/profile ו-/radar_track/placement/start, עם שליפת
גבהים מזויפת (בלי רשת). מוודא שהמבנה שהממשק מצפה לו נשמר בדיוק.
הרצה: python tests/test_radar_service.py
"""
import math  # רכס סינתטי
import os  # נתיב שורש
import sys  # sys.path וקוד יציאה
import time  # המתנה ל-job

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט
os.environ.setdefault("MAPS_GUI_ELEV_CACHE", os.path.join(__import__("tempfile").mkdtemp(prefix="elevcache_test_"), "c.sqlite"))  # T23: הבדיקה מזריקה גבהים מזויפים — מטמון זמני, לעולם לא המטמון האמיתי של המשתמש
os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות

import radar_service as rs  # המודול הנבדק
import radar_track as rt  # המנוע
import weather_server as ws  # השרת — עובר דרך השירות

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # עברית בקונסולה
except (AttributeError, ValueError):  # סביבה בלי reconfigure
    pass  # לא קריטי

results = []  # תוצאות


def check(name, cond, info=""):
    """רושם ומדפיס בדיקה."""
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


R_LAT, R_LON = 31.25, 34.80  # מכ"ם


def ground(lat, lon):
    """שטח סינתטי: 100 מ', ורכס 600 מ' במרחק 5-6 ק"מ מזרחית למכ"ם."""
    d = rt.haversine_m(R_LAT, R_LON, lat, lon)  # מרחק
    b = rt.bearing_deg(R_LAT, R_LON, lat, lon)  # כיוון
    return 600.0 if (5000.0 <= d <= 6000.0 and 80.0 <= b <= 100.0) else 100.0  # רכס או מישור


def fake_fetch(cells):
    """fetch_cells מזויף — מחזיר גובה לכל תא לפי השטח הסינתטי."""
    return [ground(lat, lon) for lat, lon in cells]  # בלי רשת


traj = []  # קשת מזרחה 8-20 ק"מ, 40 שנ'
for i in range(81):  # נקודה כל חצי שנייה
    f = i / 80.0  # התקדמות
    lat, lon = rt.destination_point(R_LAT, R_LON, 90.0, (8 + 12 * f) * 1000.0)  # מיקום
    traj.append({"t": 40.0 * f, "lat": lat, "lon": lon, "alt": 150.0 + 2850.0 * 4 * f * (1 - f)})  # פרבולה
BODY = {"vertical_center_deg": 45, "vertical_width_deg": 90, "rcs_m2": 5, "power_kw": 500, "prf_hz": 5000, "mdv_kt": 5,
        "track_mode": "track", "scan_mode": "phased", "revisit_s": 0.5}  # מכ"ם חזק בלי מגבלות זווית

# ── 1. השירות ישירות ──
p, track_cfg, alt_ref = rs.parse_all(BODY)  # קליטה
check("parse_all: מצב מעקב, מערך-מופע, MSL", track_cfg[0] == "track" and track_cfg[1]["mode"] == "phased" and alt_ref == "msl")
res = rs.run_check(R_LAT, R_LON, p, traj, track_cfg, alt_ref, fake_fetch)  # בדיקה
seg = [s["reason"] for s in res["summary"]["segments"]]  # הקטעים
check("run_check: הרכס חוסם את ההתחלה והסוף", seg[0] == "terrain" and seg[-1] == "terrain", str(seg))
check("run_check: מבנה התוצאה מלא", all(k in res for k in ("radar", "points", "summary", "terrain", "beam", "env", "track", "scan")))
check("run_check: גובה המכ\"ם = קרקע + אנטנה", res["radar"]["h_msl"] == 100.0 + p["h_antenna"], str(res["radar"]))
check("run_check: נפתח מעקב", res["track"]["track_initiated"], str(res["track"]["first_track_t"]))
prof = rs.ray_profile(R_LAT, R_LON, p, {"lat": traj[0]["lat"], "lon": traj[0]["lon"], "alt": traj[0]["alt"]}, fake_fetch)  # פרופיל
check("ray_profile: הנקודה הראשונה חסומה ברכס (~5 ק\"מ)", not prof["visible"] and 4800 < prof["block_dist_m"] < 6100, str(prof["block_dist_m"]))
agl = [dict(q, alt=50.0) for q in traj[:5]]  # 5 קודקודים בגובה 50 מ' מעל הקרקע
pt = rs.prepare_trajectory(agl, "agl", fake_fetch)  # המרה
check("prepare_trajectory AGL: 50 מעל קרקע של 100 = 150", abs(pt[0]["alt"] - 150.0) < 1e-6, str(pt[0]["alt"]))


def aborting_fetch(cells):
    """שליפה שמבוטלת — הצינור חייב לעצור ב-Aborted."""
    raise rs.Aborted()  # ביטול


try:  # ביטול
    rs.run_check(R_LAT, R_LON, p, traj, track_cfg, alt_ref, aborting_fetch)  # חייב לזרוק
    check("ביטול: Aborted עובר הלאה", False)
except rs.Aborted:  # כצפוי
    check("ביטול: Aborted עובר הלאה", True)
try:  # מסלול ריק
    rs.run_check(R_LAT, R_LON, p, traj[:1], track_cfg, alt_ref, fake_fetch)  # חייב לזרוק
    check("מסלול של נקודה אחת: ValueError", False)
except ValueError:  # כצפוי
    check("מסלול של נקודה אחת: ValueError", True)
notes = []  # הודעות התקדמות
pl = rs.run_placement(R_LAT, R_LON, 1000.0, 500.0, "coverage", p, traj, ("detection", None, None), "msl", fake_fetch, notes.append)  # הצעת מיקום
check("run_placement: 13 מועמדים, הודעות התקדמות", len(pl["candidates"]) == 13 and any("מחשב מיקומים" in n for n in notes), f"{len(pl['candidates'])}")

# ── 2. השרת אחרי ההעברה — Flask test client, שליפה מזויפת ──
ws._fetch_elevations = lambda locs: ([ground(q["lat"], q["lon"]) for q in locs], None)  # בלי רשת
ws._RADAR_TRACK_LOCS_PER_MIN = 10 ** 9  # בלי השהיית קצב בבדיקה
client = ws.app.test_client()  # לקוח בדיקה


def wait(job_id):
    """ממתין לסיום job דרך נקודת הסטטוס הקיימת."""
    for _ in range(200):  # עד ~20 שנ'
        st = client.get("/radar_doppler/status?job_id=" + job_id).get_json()  # הסטטוס
        if st["status"] != "running":  # הסתיים
            return st  # התוצאה
        time.sleep(0.1)  # המתנה קצרה
    return {"status": "timeout"}  # לא הסתיים


r = client.post("/radar_track/start", json=dict(BODY, lat=R_LAT, lon=R_LON, trajectory=traj)).get_json()  # בדיקה דרך השרת
st = wait(r["job_id"])  # המתנה
check("שרת /radar_track/start: הסתיים בהצלחה", st["status"] == "done", st.get("error") or st["status"])
if st["status"] == "done":  # השוואה לשירות
    sres = st["result"]  # התוצאה מהשרת
    check("שרת: אותם קטעים כמו השירות ישירות", [x["reason"] for x in sres["summary"]["segments"]] == seg)
    check("שרת: terrain.cached מולא", isinstance(sres["terrain"]["cached"], int), str(sres["terrain"]["cached"]))
pr = client.post("/radar_track/profile", json=dict(BODY, lat=R_LAT, lon=R_LON, point={"lat": traj[0]["lat"], "lon": traj[0]["lon"], "alt": traj[0]["alt"]}))  # פרופיל
check("שרת /radar_track/profile: 200 וחסום", pr.status_code == 200 and pr.get_json()["visible"] is False, str(pr.status_code))
check("שרת /radar_track/profile: קלט חסר = 400", client.post("/radar_track/profile", json={}).status_code == 400)
r = client.post("/radar_track/placement/start", json=dict(BODY, lat=R_LAT, lon=R_LON, radius_km=1, step_m=500, metric="coverage", trajectory=traj)).get_json()  # הצעת מיקום
st = wait(r["job_id"])  # המתנה
check("שרת /radar_track/placement/start: הסתיים, 13 מועמדים", st["status"] == "done" and len(st["result"]["candidates"]) == 13,
      st.get("error") or st["status"])

# ── FR-D-286: ספריית הפרופילים המובנית ──
import json as _json  # כתיבת קבצים לתיקייה זמנית  # noqa: E402
import tempfile  # תיקייה זמנית  # noqa: E402

lib = rs.load_profile_library()  # הספרייה האמיתית (radar-profiles/)
n_files = len([f for f in os.listdir(rs.PROFILE_LIBRARY_DIR) if f.lower().endswith(".json")])  # כמה קבצים יש — לא מספר קשיח, הספרייה גדלה
check("ספרייה: כל הקבצים נטענו, ממוינים לפי שם", len(lib) == n_files >= 13 and [p["name"] for p in lib] == sorted((p["name"] for p in lib), key=str.lower),
      f"{len(lib)}/{n_files}")
check("ספרייה: לכל פרופיל שם, params עם רגישות ותדר, ומקורות", all(p["name"] and "sensitivity_dbm" in p["params"] and "freq_mhz" in p["params"]
                                                                and p["notes"].get("published") for p in lib))
check("ספרייה: כל פרופיל עובר את קליטת הפרמטרים של המנוע", all(rs.parse_all(dict(p["params"]))[0]["range_km"] > 0 for p in lib))
with tempfile.TemporaryDirectory() as td:  # קבצים פגומים לצד קובץ תקין
    with open(os.path.join(td, "ok.json"), "w", encoding="utf-8") as f:  # תקין, בלי שדה name
        _json.dump({"format": "maps-gui-radar-profile", "version": 1, "params": {"range_km": 5}}, f)
    with open(os.path.join(td, "bad.json"), "w", encoding="utf-8") as f:  # JSON שבור
        f.write("{not json")
    with open(os.path.join(td, "other.json"), "w", encoding="utf-8") as f:  # פורמט אחר
        _json.dump({"format": "something-else", "params": {}}, f)
    with open(os.path.join(td, "notes.txt"), "w", encoding="utf-8") as f:  # לא JSON בכלל
        f.write("x")
    t = rs.load_profile_library(td)  # הקריאה
    check("ספרייה: קובץ פגום/זר מדולג, שם ברירת מחדל = שם הקובץ", len(t) == 1 and t[0]["name"] == "ok", str(t))
check("ספרייה: תיקייה חסרה = רשימה ריקה", rs.load_profile_library(os.path.join(os.path.dirname(__file__), "no_such_dir")) == [])
lr = client.get("/radar_profiles/library")  # דרך השרת
check("שרת /radar_profiles/library: 200 ואותה רשימה", lr.status_code == 200 and [p["name"] for p in lr.get_json()["profiles"]] == [p["name"] for p in lib])

# ── FR-D-288: מכ"מים מוצבים — שמירה/קריאה/מחיקה דרך /stations עם המפתח radar_sites (קובץ זמני, לא האמיתי) ──
_real_st = ws._STATIONS_FILE  # הקובץ האמיתי — לא נוגעים בו
with tempfile.TemporaryDirectory() as td:
    ws._STATIONS_FILE = os.path.join(td, "saved_stations.json")  # קובץ זמני
    site = {"type_key": "lib:COBRA_public_data.json", "type_name": "COBRA (נתונים פומביים)", "lat": 31.25, "lon": 34.8,
            "boresight_deg": 30.0, "h_antenna": 4.0, "range_km": 40.0, "start_bearing_deg": 345.0, "end_bearing_deg": 75.0,
            "angle_step_deg": 10.0, "reflectivity": "land", "lobing_enabled": False, "ridge_margin_deg": 0.0}  # מכ"ם מוצב
    sv = client.post("/stations/save", json={"tool": "radar_sites", "name": "מכ\"ם צפון", "params": site})  # שמירה
    lst = client.get("/stations/list?tool=radar_sites").get_json()["stations"]  # קריאה
    check("radar_sites: נשמר ונקרא בדיוק (round-trip, כולל עברית)", sv.status_code == 200 and len(lst) == 1 and lst[0]["name"] == "מכ\"ם צפון"
          and lst[0]["params"] == site and lst[0].get("_schema_version") == 1, str(lst)[:120])
    check("radar_sites: סוג המכ\"ם מצביע על קובץ קיים בספרייה", any("lib:" + p["file"] == site["type_key"] for p in lib))
    client.post("/stations/delete", json={"tool": "radar_sites", "name": "מכ\"ם צפון"})  # מחיקה
    check("radar_sites: נמחק", client.get("/stations/list?tool=radar_sites").get_json()["stations"] == [])
    check("radar_sites: כלי לא מוכר עדיין נדחה (400)", client.post("/stations/save", json={"tool": "radar_sitez", "name": "x", "params": {}}).status_code == 400)
ws._STATIONS_FILE = _real_st  # שחזור

passed = sum(results)  # כמה עברו
print(f"\n{passed}/{len(results)} passed")  # סיכום
sys.exit(0 if passed == len(results) else 1)  # קוד יציאה
