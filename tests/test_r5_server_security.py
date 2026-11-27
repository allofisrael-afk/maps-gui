# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — בדיקות אבטחה וחוסן לשרת (weather_server) דרך Flask test client. בלי רשת: שליפת הגבהים מזויפת,
וקובץ העמדות מוחלף בקובץ זמני (saved_stations.json האמיתי לא נגעים בו).
שני סוגי בדיקות:
  [OK]/[FAIL]  — התנהגות צפויה שאמורה לעבור.
  [REPRO]      — בדיקת שחזור לממצא: "REPRO-CONFIRMED" = הממצא קיים כרגע (צפוי עד תיקון).
הרצה: .venv\\Scripts\\python.exe tests/test_r5_server_security.py
"""
import json
import math
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # T0: moved from .qa/run5/tests/ to tests/ - project root is now one level up
sys.path.insert(0, ROOT)
os.environ.setdefault("MAPS_GUI_ELEV_CACHE", os.path.join(__import__("tempfile").mkdtemp(prefix="elevcache_test_"), "c.sqlite"))  # T23: הבדיקה מזריקה גבהים מזויפים — מטמון זמני, לעולם לא המטמון האמיתי של המשתמש
os.environ.setdefault("MAPS_GUI_DEM", "off")  # SRTM מקומי כבוי: הבדיקה מזריקה שטח סינתטי ולא מורידה משבצות אמיתיות
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import weather_server as ws  # noqa: E402

ws._fetch_elevations = lambda locs: ([100.0 for _ in locs], None)  # בלי רשת
ws._RADAR_TRACK_LOCS_PER_MIN = 10 ** 9  # בלי השהיית קצב
TMP = tempfile.mkdtemp(prefix="qa_r5_")  # תיקייה זמנית
ws._STATIONS_FILE = os.path.join(TMP, "saved_stations.json")  # לא נוגעים בקובץ האמיתי
client = ws.app.test_client()
results = {"ok": 0, "fail": 0, "repro": []}


def check(name, cond, info=""):
    results["ok" if cond else "fail"] += 1
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")


def repro(fid, name, confirmed, info=""):
    results["repro"].append((fid, confirmed))
    print(f"[REPRO-{'CONFIRMED' if confirmed else 'NOT-REPRODUCED'}] {fid} {name} {info}")


def wait(job_id, limit=200):
    for _ in range(limit):
        st = client.get("/radar_doppler/status?job_id=" + job_id).get_json()
        if st.get("status") != "running":
            return st
        time.sleep(0.05)
    return {"status": "timeout"}


EVIL = "https://evil.example"
# ── 1. CORS — כל אתר שהמשתמש גולש אליו יכול לקרוא/לכתוב לשרת המקומי ──
client.post("/stations/save", json={"tool": "radar_doppler", "name": "סוד", "params": {"lat": 31.5, "lon": 34.9}})
r = client.get("/stations/list?tool=radar_doppler", headers={"Origin": EVIL})
acao = r.headers.get("Access-Control-Allow-Origin")
repro("R5-SEC-CORS", "GET /stations/list מאתר זר מחזיר Access-Control-Allow-Origin מתיר (קריאת קואורדינטות עמדות)",
      acao in ("*", EVIL), f"ACAO={acao!r}, body={r.get_json()}")
pf = client.open("/stations/delete", method="OPTIONS", headers={"Origin": EVIL, "Access-Control-Request-Method": "POST",
                                                                 "Access-Control-Request-Headers": "content-type"})
repro("R5-SEC-CORS", "preflight מאתר זר ל-POST /stations/delete מאושר (מחיקה/כתיבה מרחוק)",
      pf.headers.get("Access-Control-Allow-Origin") in ("*", EVIL), f"status={pf.status_code} ACAO={pf.headers.get('Access-Control-Allow-Origin')!r}")
lib = client.get("/radar_profiles/library", headers={"Origin": EVIL})
check("radar_profiles/library: 200 (קריאה בלבד, תוכן ציבורי)", lib.status_code == 200)

# ── 2. /stations/save — גבולות קלט ──
big = {"blob": "x" * 2_000_000}  # 2MB
r = client.post("/stations/save", json={"tool": "radar_doppler", "name": "גדול", "params": big})
size = os.path.getsize(ws._STATIONS_FILE)
repro("R5-DATA-SIZE", "params של 2MB נשמר בלי הגבלת גודל", r.status_code == 200 and size > 1_900_000, f"status={r.status_code} file={size}B")
r = client.post("/stations/save", json={"tool": "radar_doppler", "name": "n" * 50_000, "params": {}})
repro("R5-DATA-SIZE", "שם של 50,000 תווים נשמר בלי הגבלה", r.status_code == 200)
check("tool לא מוכר — 400", client.post("/stations/save", json={"tool": "../../etc", "name": "a", "params": {}}).status_code == 400)
check("גוף לא-JSON — לא 500", client.post("/stations/save", data="not json", content_type="text/plain").status_code in (400, 415))
check("שם עם תווי HTML נשמר כטקסט (הממשק מציג ב-textContent)", client.post("/stations/save", json={"tool": "los", "name": "<img src=x onerror=alert(1)>", "params": {}}).status_code == 200)

# ── 3. שמירה לא-אטומית — קריסה באמצע json.dump ──
client.post("/stations/save", json={"tool": "los", "name": "טובה", "params": {"a": 1}})
before = ws._load_stations()
orig_dump = json.dump


def crashing_dump(obj, fp, **kw):  # כותב חצי ואז "קורס"
    s = json.dumps(obj, **kw)
    fp.write(s[: len(s) // 2])
    raise OSError("simulated crash mid-write")


ws.json.dump = crashing_dump
try:
    client.post("/stations/save", json={"tool": "los", "name": "חדשה", "params": {"b": 2}})
except Exception as e:  # noqa: BLE001 — הבדיקה רוצה לראות את מצב הקובץ גם אם השרת זרק
    print("   (server raised:", type(e).__name__, ")")
ws.json.dump = orig_dump
after = ws._load_stations()
repro("R5-DATA-ATOMIC", "קריסה באמצע שמירה משאירה קובץ קטוע — כל העמדות אובדות בטעינה הבאה",
      bool(before) and after == {}, f"before_tools={list(before)} after={after}")

# ── 4. /radar_track/start — קלט חריג (Syntax/Boundary/Error-guessing) ──
traj = [{"t": i * 0.5, "lat": 31.30 + i * 0.001, "lon": 34.80, "alt": 500 + 10 * i} for i in range(40)]
base = {"lat": 31.25, "lon": 34.80, "trajectory": traj}
cases = {
    "trajectory חסר": {"lat": 31.25, "lon": 34.80},
    "trajectory לא רשימה": dict(base, trajectory="abc"),
    "נקודה אחת": dict(base, trajectory=traj[:1]),
    "6001 נקודות": dict(base, trajectory=[dict(traj[0], t=i * 0.01) for i in range(6001)]),
    "lat מכ\"ם 999": dict(base, lat=999),
    "lat מכ\"ם מחרוזת": dict(base, lat="abc"),
    "range_km מחרוזת": dict(base, range_km="abc"),
    "track_m=0, track_n=-5": dict(base, track_m=0, track_n=-5),
    "rcs_nose=-1": dict(base, rcs_mode="aspect", rcs_nose=-1),
    "rain_rate=1e9": dict(base, rain_rate_mmh=1e9),
}
for name, body in cases.items():
    r = client.post("/radar_track/start", json=body)
    code = r.status_code
    if code == 200:
        st = wait(r.get_json()["job_id"])
        check(f"radar_track/start [{name}]: לא 500, job מסתיים", st["status"] in ("done", "error"), f"http=200 job={st['status']} {st.get('error') or ''}"[:140])
    else:
        check(f"radar_track/start [{name}]: נדחה בבקשה ברורה", code == 400 and bool(r.get_json().get("error")), f"http={code} {r.get_json()}"[:140])

# NaN בפרמטר — json.loads של Python מקבל NaN (דפדפן לא שולח, אבל לקוח ישיר כן)
raw = json.dumps(dict(base, range_km=float("nan"), sensitivity_dbm=float("nan")))  # 'NaN' בטקסט
r = client.post("/radar_track/start", data=raw, content_type="application/json")
if r.status_code == 200:
    st = wait(r.get_json()["job_id"])
    res = st.get("result") or {}
    rk = res.get("range_km", (res.get("radar") or {}).get("range_km"))  # T7: הטווח נמצא ברמה העליונה של התוצאה (קודם חיפשנו תחת radar וקיבלנו None — חיובי שגוי)
    repro("R5-VAL-NAN", "NaN בפרמטר עובר את הצמידה (min/max) ונכנס לחישוב", st["status"] == "done" and (rk is None or not math.isfinite(rk) or "NaN" in json.dumps(res)[:100000]),
          f"job={st['status']} radar.range_km={rk!r}")
else:
    repro("R5-VAL-NAN", "NaN בפרמטר", False, f"http={r.status_code}")
lat_bad = [dict(q, lat=95.0 + i) for i, q in enumerate(traj)]
r = client.post("/radar_track/start", json=dict(base, trajectory=lat_bad))
st = wait(r.get_json()["job_id"]) if r.status_code == 200 else {"status": f"http{r.status_code}"}
repro("R5-VAL-RANGE", "קואורדינטות מסלול מחוץ לטווח (lat>90) מתקבלות ומחושבות", st["status"] == "done", f"job={st['status']}")

# ── 5. jobs במקביל — אין תקרה ──
# T9: worker איטי (2 שנ') — אחרת ה-jobs מסתיימים מיד והתקרה לא נבחנת בכלל
_orig_worker = ws._radar_track_worker  # המקורי
ws._radar_track_worker = lambda job_id, *a, **k: time.sleep(2) or ws._job_fail(job_id, "test")  # עבודה איטית
resps = [client.post("/radar_track/start", json=base) for _ in range(40)]  # 40 בקשות מהירות
ids = [r.get_json().get("job_id") for r in resps if r.status_code == 200]  # שהתקבלו
n429 = sum(1 for r in resps if r.status_code == 429)  # שנדחו
repro("R5-DOS-JOBS", "40 jobs במקביל התקבלו בלי תקרה (thread לכל אחד)", len(ids) == 40, f"accepted={len(ids)} rejected_429={n429}")
check("T9: תקרת jobs — לכל היותר 16 פעילים, השאר 429", len(ids) <= ws._JOB_MAX_ACTIVE and n429 == 40 - len(ids), f"accepted={len(ids)}")
time.sleep(0.5)  # שה-threads יתחילו
with ws._radar_jobs_lock:  # כמה רצים בפועל (לא ממתינים בתור)
    queued = sum(1 for i in ids if ws._radar_jobs.get(i, {}).get("note") == ws._QUEUED_NOTE)  # בתור
check("T9: עד 4 רצים במקביל, השאר מסומנים 'ממתין בתור'", queued >= len(ids) - ws._JOB_CONCURRENCY, f"queued={queued}")
for i in ids:  # ניקוי — ביטול כולם
    client.post("/radar_doppler/cancel?job_id=" + i)  # ביטול
ws._radar_track_worker = _orig_worker  # שחזור
for i in ids:
    if i:
        client.post("/radar_doppler/cancel?job_id=" + i)

# ── 6. /radar_track/placement/start — גבולות ──
r = client.post("/radar_track/placement/start", json=dict(base, radius_km=1000, step_m=1))
check("placement: רדיוס/צעד קיצוניים — נצמדים או נדחים, לא נתקע", r.status_code in (200, 400), f"http={r.status_code} {str(r.get_json())[:100]}")
if r.status_code == 200:
    cand = r.get_json().get("candidates")
    check("placement: מספר מועמדים חסום (<=400)", isinstance(cand, int) and cand <= 400, f"candidates={cand}")
    client.post("/radar_doppler/cancel?job_id=" + r.get_json()["job_id"])

print(f"\nOK={results['ok']} FAIL={results['fail']} REPRO-CONFIRMED={sum(1 for _, c in results['repro'] if c)}/{len(results['repro'])}")
with open(os.path.join(ROOT, ".qa", "run5", "server_security_results.json"), "w", encoding="utf-8") as f:  # T0: report stays under .qa/run5
    json.dump(results, f, ensure_ascii=False, indent=1)
sys.exit(1 if results["fail"] else 0)
