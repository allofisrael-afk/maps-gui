# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""FR-D-299: מטמון תחזית מזג האוויר החי (met_cache.py), בלי רשת. בודק: בחירת השעה הקרובה לעכשיו (ולא 00:00),
שימוש חוזר בלי רשת, תחזית שמורה כשהמכסה נגמרת (עם גיל), שגיאה עם הסבר כשאין תחזית שמורה — ישירות, דרך
weather_server._fetch_met_profile_live (Desktop), mpm_api._default_fetch_met_live (אנדרואיד), ובסיכום של מאזור לאזור.
הרצה: .venv\\Scripts\\python.exe tests/test_met_cache.py"""
import datetime  # בניית סדרת שעות סינתטית
import io  # תשובת urlopen מזויפת
import json  # קידוד התשובה המזויפת
import os  # משתני סביבה
import sys  # sys.path וקוד יציאה
import tempfile  # מטמון זמני
import time  # זמן נוכחי

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
TMP = tempfile.mkdtemp(prefix="met_cache_test_")  # תיקייה זמנית
os.environ["MAPS_GUI_MET_CACHE"] = os.path.join(TMP, "met.sqlite")  # מטמון תחזית זמני — לא נוגע בקובץ של המשתמש
os.environ["MAPS_GUI_ELEV_CACHE"] = os.path.join(TMP, "elev.sqlite")  # מטמון גבהים זמני
os.environ.setdefault("MAPS_GUI_DEM", "off")  # בלי הורדת משבצות SRTM
os.environ.pop("MAPS_GUI_APP_TOKEN", None)  # בלי אכיפת טוקן
import met_cache as mc  # noqa: E402  # המודול הנבדק

ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30]  # כמו בשני הקבצים


def fake_response(hours=168):  # תשובת Open-Meteo סינתטית: מתחילה ב-00:00 UTC של היום (כמו האמיתית); הטמפ' = מספר השעה
    day0 = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)  # 00:00 היום
    times = [(day0 + datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]  # הסדרה
    H = {"time": times, "temperature_2m": [float(h) for h in range(hours)], "surface_pressure": [1000.0] * hours,  # קרקע: טמפ' = שעה
         "wind_speed_10m": [3.0] * hours, "wind_direction_10m": [270.0] * hours}  # רוח קרקע
    for i, p in enumerate(LEVELS):  # שכבות
        H[f"temperature_{p}hPa"] = [10.0] * hours  # טמפ'
        H[f"wind_speed_{p}hPa"] = [5.0] * hours  # רוח
        H[f"wind_direction_{p}hPa"] = [250.0] * hours  # כיוון
        H[f"geopotential_height_{p}hPa"] = [100.0 + 600.0 * i] * hours  # גובה עולה
    return {"elevation": 0.0, "hourly": H}  # התשובה


now = time.time()  # עכשיו
now_hour = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)  # עכשיו UTC
now_hour = (now_hour + datetime.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)  # השעה הקרובה
want_idx = now_hour.hour + (24 if now_hour.date() > datetime.datetime.now(datetime.timezone.utc).date() else 0)  # האינדקס הצפוי בסדרה
resp = fake_response()  # תשובה
check("pick_index: השעה הקרובה לעכשיו, לא 00:00", mc.pick_index(resp["hourly"]["time"], now=now) == want_idx, str(want_idx))  # התיקון
check("pick_index: שעה מבוקשת במפורש", mc.pick_index(resp["hourly"]["time"], resp["hourly"]["time"][5]) == 5)  # when_iso
check("pick_index: שעה מחוץ לסדרה → None", mc.pick_index(resp["hourly"]["time"][:1], now=now + 3 * 86400) is None)  # ישנה

calls = []  # קריאות "רשת"
d, i, info, err = mc.fetch(31.22, 34.79, lambda: (calls.append(1) or (resp, None)), now=now)  # 1: רשת
check("fetch ראשון: מהרשת, נשמר", err is None and i == want_idx and info["cached"] is False and calls == [1])  # רשת
d, i, info, err = mc.fetch(31.24, 34.81, lambda: (calls.append(1) or (resp, None)), now=now + 600)  # 2: אותו אזור (0.1°), 10 דק' אחרי
check("fetch שני באותו אזור: מהמטמון, בלי רשת", err is None and info["cached"] is True and info["stale"] is False and calls == [1], str(info))  # בלי רשת
quota = lambda: (None, {"error": "Daily API request limit exceeded", "rate_limited": True})  # noqa: E731  # מכסה נגמרה
d, i, info, err = mc.fetch(31.22, 34.79, quota, now=now + 5 * 3600)  # 3: 5 שעות אחרי, מכסה נגמרה
check("מכסה נגמרה + תחזית שמורה: משתמשים בה, עם גיל", err is None and info["stale"] is True and info["age_min"] == 300 and d is not None, str(info))  # תחזית שמורה
check("תחזית שמורה: השעה הנבחרת = עכשיו (5 שעות אחרי השליפה)", i == mc.pick_index(resp["hourly"]["time"], now=now + 5 * 3600))  # השעה מתקדמת
check("describe: אזהרת תחזית שמורה", "שמורה מלפני 300" in mc.describe("T", info), mc.describe("T", info))  # טקסט
d, i, info, err = mc.fetch(31.22, 34.79, quota, now=now + 49 * 3600)  # 4: אחרי 49 שעות — ישנה מדי
check("תחזית ישנה מ-48 שעות לא משמשת → שגיאה", d is None and err is not None)  # תקרה
d, i, info, err = mc.fetch(29.55, 34.95, quota, now=now)  # 5: אזור אחר, אין שמורה
check("מכסה + אין תחזית שמורה → שגיאה עם הסבר (אטמוספרה תקנית)", d is None and "אטמוספרה תקנית" in err["error"] and "Daily API" in err["error"] and err.get("rate_limited"), err["error"])  # הסבר
d, i, info, err = mc.fetch(29.55, 34.95, lambda: (None, {"error": "timeout"}), now=now)  # 6: כשל רשת
check("כשל רשת + אין שמורה → הסבר על חיבור", "החיבור לרשת" in err["error"])  # הסבר רשת

import weather_server as ws  # noqa: E402  # Desktop


class FakeResp:  # תשובת requests מזויפת
    def __init__(self, code, body):  # קוד וגוף
        self.status_code, self._body = code, body  # שמירה

    def json(self):  # גוף
        return self._body  # כמו שהוא

    def raise_for_status(self):  # אין שגיאה בקודים שמשתמשים בהם כאן
        return None  # תקין


net = []  # קריאות
ws.requests.get = lambda url, params=None, timeout=None: (net.append(params) or FakeResp(200, resp))  # רשת מזויפת
surface, levels, meta = ws._fetch_met_profile_live(30.6, 34.8, 500.0)  # אזור חדש
check("Desktop: השעה הנבחרת = עכשיו (הטמפ' בסינתטי = מספר השעה)", meta["valid_time_utc"] == resp["hourly"]["time"][want_idx] and abs(surface["temp_c"] - (want_idx - 0.0065 * 500)) < 0.01, f"{meta['valid_time_utc']} {surface['temp_c']}")  # התיקון
check("Desktop: הבקשה לא מגבילה ל-start_hour (כל 7 הימים, לשימוש חוזר)", "start_hour" not in net[0])  # סדרה מלאה
ws.requests.get = lambda url, params=None, timeout=None: FakeResp(429, {"reason": "Daily API request limit exceeded"})  # מכסה
met, err = ws._resolve_ballistics_met({"source": "live"}, {"lat": 30.6, "lon": 34.8, "alt_m": 500})  # יש שמורה (טרייה) → בלי רשת בכלל
check("Desktop: תחזית טרייה במטמון → עובד גם כשהמכסה נגמרה", err is None and met["source"] == "inline" and "שמורה" in met["description"], met.get("description"))  # מטמון
met, err = ws._resolve_ballistics_met({"source": "live"}, {"lat": 33.0, "lon": 35.5, "alt_m": 300})  # אזור בלי שמורה
check("Desktop: מכסה + אין שמורה → הודעה עם מה לעשות", met is None and "אטמוספרה תקנית" in err["error"], err.get("error"))  # הסבר
c = ws.app.test_client()  # לקוח בדיקה
r = c.post("/ballistics/trajectory", json={"gun": {"lat": 30.6, "lon": 34.8, "alt_m": 500}, "qe": 400, "azimuth": 1600, "mv": 684, "met": {"source": "live"}})  # הכלי הבודד
mu = (r.get_json() or {}).get("met_used") or {}  # מה הוצג
check("הכלי הבודד: met_used.description מוצג (מקור + שעה)", r.status_code == 200 and "Open-Meteo" in (mu.get("description") or ""), str(mu))  # תצוגה

import urllib.request  # noqa: E402  # לזיוף urlopen
import mpm_api  # noqa: E402  # אנדרואיד

urllib.request.urlopen = lambda url, timeout=None: io.BytesIO(json.dumps(resp).encode("utf-8"))  # רשת מזויפת
mpm_api._urlrequest.urlopen = urllib.request.urlopen  # אותו אובייקט שהמודול משתמש בו
met, err = mpm_api._default_fetch_met_live(32.1, 35.1, None)  # אזור חדש
check("אנדרואיד: השעה הנבחרת = עכשיו", err is None and met["time_utc"] == resp["hourly"]["time"][want_idx], str(met and met["time_utc"]))  # התיקון


def _http429(url, timeout=None):  # מכסה באנדרואיד
    raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)  # כמו urllib


mpm_api._urlrequest.urlopen = _http429  # מכסה
met, err = mpm_api._default_fetch_met_live(32.1, 35.1, None)  # יש שמורה
check("אנדרואיד: מכסה + תחזית שמורה → עובד", err is None and met["source"] == "inline")  # מטמון
met, err = mpm_api._default_fetch_met_live(31.0, 35.3, None)  # אין שמורה
check("אנדרואיד: מכסה + אין שמורה → rate_limited והסבר", met is None and err.get("rate_limited") is True and "אטמוספרה תקנית" in err["error"], str(err))  # הסבר

import area_fire  # noqa: E402  # מאזור לאזור
stale_met = {"source": "inline", "surface": {"temp_c": 15.0, "pressure_hpa": 1000.0, "wind_speed_mps": 0.0, "wind_dir_deg": 0.0},  # מטאו מזויף
             "levels": [], "time_utc": "T", "description": mc.describe("2026-11-27T12:00", {"cached": True, "stale": True, "age_min": 90})}  # תחזית שמורה
req = {"launch_areas": [{"name": "L", "polygon": [[31.2000, 34.7500], [31.2000, 34.7520], [31.2015, 34.7520], [31.2015, 34.7500]]}],  # שיגור (נקודה אחת)
       "target_areas": [{"name": "T", "polygon": [[31.3000, 34.8600], [31.3000, 34.8620], [31.3015, 34.8620], [31.3015, 34.8600]]}],  # מטרה קטנה
       "mv": 684, "met": {"source": "live"}, "groups": ["low"], "crest": False, "verify_frac": 0.0}  # בקשה
res = area_fire.run(req, lambda pts: [300.0] * len(pts), met_fetch=lambda la, lo, al: (stale_met, None))  # שטח שטוח, מטאו שמור
s = res["summary"]  # הסיכום
check("מאזור לאזור: הסיכום מציין מטאו שמור (met_stale)", s.get("met_stale") is True and "שמורה מלפני 90" in s.get("met", ""), s.get("met"))  # אזהרה
try:  # מכסה בלי שמורה
    area_fire.run(req, lambda pts: [300.0] * len(pts), met_fetch=lambda la, lo, al: (None, {"error": "quota — " + mc.NO_CACHE_HINT}))  # כשל
    check("מאזור לאזור: כשל מטאו → שגיאה", False)  # לא אמור להגיע
except ValueError as e:  # צפוי
    check("מאזור לאזור: כשל מטאו → הודעה עם מה לעשות", "אטמוספרה תקנית" in str(e), str(e))  # הסבר
print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
