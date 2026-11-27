# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
בדיקות FR-D-290: גובה בחינה של קווי ראייה — ייחוס AGL (מעל הקרקע, ברירת המחדל) או MSL (גובה קבוע מעל פני הים),
ב-/los וברדיוס הראייה (/los_radial). בלי רשת: Open-Meteo ממוקה. עיקר הבדיקה — AGL לא השתנה, ו-MSL שקול ל-AGL
כשהגובה זהה (שטח שטוח), ונקודה שבה הקרקע גבוהה מהיעד אינה גלויה.
הרצה: python tests/test_los_target_ref.py
"""
import os  # נתיב שורש
import sys  # sys.path וקוד יציאה
import time  # המתנה ל-job

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # שורש הפרויקט
os.environ.setdefault("MAPS_GUI_ELEV_CACHE", os.path.join(__import__("tempfile").mkdtemp(prefix="elevcache_test_"), "c.sqlite"))  # T23: הבדיקה מזריקה גבהים מזויפים — מטמון זמני, לעולם לא המטמון האמיתי של המשתמש
os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות

import weather_server as ws  # השרת  # noqa: E402

try:  # פלט UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

results = []  # תוצאות


def check(name, cond, info=""):
    results.append(bool(cond))  # לסיכום
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


GROUND = {"h": 100.0}  # גובה הקרקע בשטח הסינתטי (שטוח)


class _Resp:  # תשובה מזויפת של requests.get
    status_code = 200

    def __init__(self, n):
        self._n = n

    def raise_for_status(self):
        return None

    def json(self):
        return {"elevation": [GROUND["h"]] * self._n}  # שטח שטוח


def fake_get(url, params=None, timeout=None):
    n = len(str(params["latitude"]).split(","))  # כמה נקודות התבקשו
    return _Resp(n)


ws.requests.get = fake_get  # /los — בלי רשת
ws._fetch_elevations = lambda locs: ([GROUND["h"]] * len(locs), None)  # רדיוס הראייה — בלי רשת
client = ws.app.test_client()  # לקוח בדיקה
Q = "/los?lat1=31.25&lon1=34.80&lat2=31.70&lon2=34.80&obs_h=10"  # קו של ~50 ק"מ צפונה

# ── /los ──
a = client.get(Q + "&tgt_h=500").get_json()  # AGL (בלי tgt_ref — ברירת המחדל)
a2 = client.get(Q + "&tgt_h=500&tgt_ref=agl").get_json()  # AGL מפורש
check("/los AGL: ברירת המחדל זהה ל-tgt_ref=agl", a == a2)
check("/los AGL: גובה היעד = קרקע + 500", a["target_h"] == 600.0 and a.get("tgt_ref") == "agl", str(a["target_h"]))
m = client.get(Q + "&tgt_h=600&tgt_ref=msl").get_json()  # MSL 600 = קרקע 100 + 500
check("/los MSL שקול ל-AGL באותו גובה (שטח שטוח)", [p["visible"] for p in m["points"]] == [p["visible"] for p in a["points"]] and m["target_h"] == 600.0,
      f"msl={m['target_h']}")
hi = client.get(Q + "&tgt_h=9753.6&tgt_ref=msl").get_json()  # 32 א"ר
check("/los MSL 32 א\"ר: היעד גלוי, גובה היעד = 9753.6", hi["points"][-1]["visible"] is True and hi["target_h"] == 9753.6)
lo = client.get(Q + "&tgt_h=50&tgt_ref=msl").get_json()  # MSL מתחת לקרקע (100)
check("/los MSL מתחת לקרקע: היעד לא גלוי", lo["points"][-1]["visible"] is False and lo["all_visible"] is False)
z = client.get(Q + "&tgt_h=500&ridge_margin_deg=0").get_json()  # מרווח רכס 0 מפורש
check("/los מרווח רכס 0 = בדיוק כמו בלי הפרמטר", {k: v for k, v in z.items() if k != "ridge_margin_deg"} == {k: v for k, v in a.items() if k != "ridge_margin_deg"})
mg = client.get(Q + "&tgt_h=500&ridge_margin_deg=10").get_json()  # מרווח 10° — יעד של 500 מ' ב-50 ק"מ (~0.6°) לא עומד בו
check("/los מרווח רכס 10°: יעד נמוך ורחוק נחסם", mg["points"][-1]["visible"] is False and mg["ridge_margin_deg"] == 10.0)
cl = client.get(Q + "&tgt_h=500&ridge_margin_deg=99").get_json()  # מחוץ לטווח
check("/los מרווח רכס נצמד לטווח 0–10°", cl["ridge_margin_deg"] == 10.0)


# ── רדיוס הראייה ──
def radial(extra):
    j = client.get("/los_radial/start?lat=31.25&lon=34.80&range_km=20&min_range_km=0&angle_step_deg=30&start_bearing_deg=0&end_bearing_deg=90"
                   "&obs_h=10&vertical_center_deg=0&vertical_width_deg=90" + extra).get_json()["job_id"]
    for _ in range(200):
        st = client.get("/los_radial/status?job_id=" + j).get_json()
        if st["status"] != "running":
            return st
        time.sleep(0.05)
    return {"status": "timeout"}


ra = radial("&tgt_h=500")  # AGL (ברירת מחדל)
rm = radial("&tgt_h=600&tgt_ref=msl")  # MSL שקול
check("רדיוס AGL: הסתיים", ra["status"] == "done" and ra["result"]["tgt_ref"] == "agl")
check("רדיוס MSL שקול ל-AGL באותו גובה", rm["status"] == "done" and
      [r["clear_dist_km"] for r in rm["result"]["rays"]] == [r["clear_dist_km"] for r in ra["result"]["rays"]], str([r["clear_dist_km"] for r in rm["result"]["rays"]]))
rl = radial("&tgt_h=50&tgt_ref=msl")  # מתחת לקרקע
check("רדיוס MSL מתחת לקרקע: אף קרן לא גלויה", rl["status"] == "done" and all(r["clear_dist_km"] == 0.0 and r["blocked"] for r in rl["result"]["rays"]))
rn = radial("&tgt_h=nan&tgt_ref=msl")  # NaN
check("רדיוס: tgt_h=NaN לא תוקע (נצמד ל-0)", rn["status"] == "done")

passed = sum(results)
print(f"\n{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
