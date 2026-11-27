# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""גבהים מקומיים מ-SRTM (srtm_dem.py): משבצות סינתטיות בתיקייה זמנית, בלי רשת. בודק קריאה ואינטרפולציה, חורים, ים מול בקעת
ים המלח, כיסוי, כיבוי, והשלמה מ-Open-Meteo רק לנקודות חסרות (גם דרך weather_server._fetch_elevations).
הרצה: .venv\\Scripts\\python.exe tests/test_srtm_dem.py"""
import os  # נתיבים ומשתני סביבה
import struct  # כתיבת משבצת HGT סינתטית (int16 big-endian)
import sys  # sys.path וקוד יציאה
import tempfile  # תיקייה זמנית

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא
TMP = tempfile.mkdtemp(prefix="srtm_test_")  # משבצות סינתטיות
os.environ["MAPS_GUI_DEM_DIR"] = TMP  # המודול קורא מכאן
os.environ["MAPS_GUI_DEM"] = "on"  # מופעל (הרגרסיה מכבה כברירת מחדל — כאן בודקים אותו עצמו)
os.environ["MAPS_GUI_ELEV_CACHE"] = os.path.join(TMP, "c.sqlite")  # מטמון זמני
import srtm_dem as d  # noqa: E402  # המודול הנבדק

d._download = lambda name, path: None  # בלי רשת: כל משבצת שאין בתיקייה = "כשל הורדה"
ok, fail = 0, 0  # מונים


def check(name, cond, info=""):  # רישום תוצאה
    global ok, fail  # המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


def write_tile(name, n, fn):  # כותב משבצת HGT: fn(row, col) -> int16
    with open(os.path.join(TMP, name + ".hgt"), "wb") as f:  # הקובץ
        for r in range(n):  # שורות (0 = צפון)
            f.write(struct.pack(f">{n}h", *[fn(r, c) for c in range(n)]))  # שורה שלמה, big-endian


N = 1201  # משבצת 3" (קטנה יותר לבדיקה)
write_tile("N31E034", N, lambda r, c: 1000 - r // 2 + c // 4)  # מדרון: יורד דרומה, עולה מזרחה
write_tile("N32E034", N, lambda r, c: -800 if c < 300 else (d.VOID if (r, c) == (600, 600) else 50))  # ים ממערב, חור אחד, יבשה
write_tile("N31E035", N, lambda r, c: -415)  # בקעת ים המלח (כולה שלילית)
open(os.path.join(TMP, "N33E034.none"), "w").close()  # "אין משבצת" (ים)

check("שם משבצת", d.tile_name(31.5, 34.7) == "N31E034" and d.tile_name(-0.5, -0.5) == "S01W001" and d.tile_name(29.99, 35.0) == "N29E035")  # פורמט SRTM
v = d.elevation(31.9999999, 34.0)  # פינה צפון-מערבית של N31E034 (שורה 0, עמודה 0). ‏32.0 בדיוק שייך כבר למשבצת N32 (floor, כמו SRTM)
check("פינת משבצת: ערך הדגימה (1000)", v == 1000.0, str(v))  # דגימה מדויקת
v = d.elevation(31.5, 34.5)  # מרכז: שורה 600, עמודה 600 → 1000 - 300 + 150
check("מרכז משבצת: 850", abs(v - 850.0) < 0.6, str(v))  # אינטרפולציה
lat = 31.0 + (N - 1 - 100.5) / (N - 1)  # בין שורה 100 ל-101
v = d.elevation(lat, 34.0)  # עמודה 0: 950 ו-950 (101//2 = 50) — בדיקת חצי תא
check("אינטרפולציה בילינארית בין שורות", abs(v - 950.0) < 0.6, str(v))  # 1000-50
check("ים (ערך שלילי מחוץ לבקעה) → None", d.elevation(32.5, 34.05) is None)  # בטימטריה לא נחשבת פני שטח
check("חור (‎-32768) באחת הפינות → None", d.elevation(32.0 + (N - 1 - 600) / (N - 1), 34.0 + 600 / (N - 1)) is None)  # חור
check("יבשה ליד החור → ערך", d.elevation(32.3, 34.8) == 50.0)  # יבשה
check("בקעת ים המלח: ‎-415 נשמר", d.elevation(31.5, 35.45) == -415.0)  # שלילי אמיתי
check("משבצת שמסומנת 'אין' → None, בלי הורדה", d.elevation(33.5, 34.5) is None)  # ים
check("משבצת חסרה + כשל הורדה → None", d.elevation(30.5, 34.5) is None)  # אין קובץ
check("מחוץ לכיסוי SRTM (‎>60°) → None", d.elevation(65.0, 20.0) is None)  # מחוץ לכיסוי
check("NaN → None", d.elevation(float("nan"), 34.5) is None)  # לא סופי

calls = []  # מה נשלח ל"Open-Meteo"
res = d.merge([(31.5, 34.5), (32.5, 34.05), (30.5, 34.5)], lambda pts: (calls.append(list(pts)) or [11.0] * len(pts)))  # מקומי + השלמה
check("merge: מקומי לנקודה המכוסה, השלמה רק לחסרות", abs(res[0] - 850.0) < 0.6 and res[1] == 11.0 and res[2] == 11.0 and calls == [[(32.5, 34.05), (30.5, 34.5)]], str(calls))  # רק 2 נשלחו
calls.clear()  # ניקוי
res = d.merge([(31.5, 34.5), (31.2, 34.2)], lambda pts: (calls.append(pts) or []))  # הכול מקומי
check("merge: הכול מקומי → בלי בקשה ל-Open-Meteo", calls == [] and None not in res)  # בלי רשת

os.environ["MAPS_GUI_DEM"] = "off"  # כיבוי
check("כבוי (MAPS_GUI_DEM=off) → הכול None", d.lookup([(31.5, 34.5)]) == [None])  # כבוי
os.environ["MAPS_GUI_DEM"] = "on"  # הפעלה מחדש

import weather_server as ws  # noqa: E402  # השרת — _fetch_elevations עם SRTM קודם

remote = []  # קריאות ל-Open-Meteo
ws._fetch_elevations_remote = lambda locs: (remote.append(len(locs)) or [7.0] * len(locs), None)  # Open-Meteo מזויף
got, err = ws._fetch_elevations([{"lat": 31.5, "lon": 34.5}, {"lat": 32.5, "lon": 34.05}])  # אחת מקומית, אחת ים
check("weather_server: SRTM קודם, Open-Meteo רק לנקודה החסרה", err is None and abs(got[0] - 850.0) < 0.6 and got[1] == 7.0 and remote == [1], f"{got} {remote}")  # נקודה אחת נשלחה
remote.clear()  # ניקוי
ws._fetch_elevations_remote = lambda locs: (None, {"error": "quota", "rate_limited": True})  # מכסה נגמרה
got, err = ws._fetch_elevations([{"lat": 31.5, "lon": 34.5}, {"lat": 31.2, "lon": 34.3}])  # הכול מקומי
check("weather_server: מכסה נגמרה אבל הכול מקומי → מצליח", err is None and None not in got)  # המכסה לא עוצרת
got, err = ws._fetch_elevations([{"lat": 32.5, "lon": 34.05}])  # ים — צריך את Open-Meteo
check("weather_server: נקודה שצריכה Open-Meteo + מכסה → אותה שגיאה כמו קודם", got is None and err.get("rate_limited") is True)  # התנהגות קודמת נשמרת
c = ws.app.test_client()  # לקוח בדיקה
r = c.post("/elevation", json={"locations": [{"latitude": 31.5, "longitude": 34.5}]})  # נקודה מקומית
check("/elevation: עונה מ-SRTM בלי Open-Meteo", r.status_code == 200 and r.get_json().get("source") == "srtm" and abs(r.get_json()["results"][0]["elevation"] - 850.0) < 0.6)  # מקומי
print(f"\n{ok}/{ok + fail} passed")  # סיכום
sys.exit(1 if fail else 0)  # קוד יציאה
