# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
radar_android — מתאם כלי בדיקת מעקב המכ"ם לאנדרואיד (שלב ג', SRS FR-D-282). רץ בתוך ה-APK דרך Chaquopy:
mpm_api.dispatch_json מנתב לכאן כל פעולה שמתחילה ב-"radar_" או ב-"rocket_".

ה-Kotlin קורא ל-Python על ה-thread הראשי של הממשק — לכן כל פעולה כבדה מתחילה כאן **עבודת רקע** (thread)
ומחזירה job_id מיד, וה-Dart שואל על המצב כל שנייה (radar_job_status), בדיוק כמו בדסקטופ.
הצינורות עצמם — radar_service.py, אותו קוד כמו בשרת. כאן רק: שליפת גבהים מ-Open-Meteo דרך urllib (בלי
requests), עם מטמון בזיכרון לפי תא-רשת וקצב מבוקר — Open-Meteo סופר כל נקודה כקריאה (600/דקה, 5000/שעה).
stdlib בלבד.
"""

import json as _json  # פענוח/קידוד מול ה-Dart
import threading  # עבודות רקע ונעילות
import time  # קצב והמתנות
import urllib.error as _urlerror  # שגיאות HTTP/רשת
import urllib.parse as _urlparse  # בניית ה-URL
import urllib.request as _urlrequest  # הבקשה עצמה
import uuid  # מזהה job

import radar_placement as rpl  # מגבלות המועמדים
import radar_service as rs  # הצינורות המשותפים
import elev_cache  # T23 (F-055): מטמון גבהים קבוע — אותו מודול כמו בשרת של ה-Desktop

BATCH = 100  # נקודות לבקשה — המקסימום ש-Open-Meteo מקבל
LOCS_PER_MIN = 500  # קצב יעד — מתחת ל-600 לדקה
RATE_RETRIES = 2  # המתנות של דקה על חסימה דקתית
JOB_TTL_S = 600  # עבודות שהסתיימו נמחקות אחרי 10 דקות
NET_ERROR_MSG = "אין חיבור לשירות הגבהים (Open-Meteo) — בדוק את חיבור האינטרנט ונסה שוב"  # T16 (F-048): זהה לשרת של הדסקטופ
_STORE = elev_cache.ElevCache()  # T23: זיכרון + קובץ SQLite בתיקיית הקבצים הפרטית של האפליקציה (HOME); שורד סגירה ופתיחה
_JOBS = {}  # job_id -> מצב
_JOBS_LOCK = threading.Lock()  # מגן על העבודות


class _RateLimited(Exception):
    """Open-Meteo החזיר 429 — message = הנוסח שלו (דקתי/שעתי/יומי)."""


def _http_elevations(cells):  # גבהים: קודם SRTM מקומי (משבצות במכשיר), ואת החסרים מ-Open-Meteo — המכסה לא עוצרת חישובים
    """אותו ממשק: רשימת גבהים מקבילה; 429 -> _RateLimited; רשת -> OSError (רק אם צריך את Open-Meteo בכלל)."""
    import srtm_dem  # ייבוא מקומי — המודול ארוז ב-APK (build_apk.ps1)
    return srtm_dem.merge([(c[0], c[1]) for c in cells], _http_elevations_remote)  # מקומי + השלמה


def _http_elevations_remote(cells):
    """בקשה אחת ל-Open-Meteo (עד 100 תאים). מחזיר רשימת גבהים מקבילה; 429 -> _RateLimited; רשת -> OSError."""
    url = "https://api.open-meteo.com/v1/elevation?" + _urlparse.urlencode({
        "latitude": ",".join(str(c[0]) for c in cells), "longitude": ",".join(str(c[1]) for c in cells)})  # ה-URL
    if not url.startswith("https://"):  # הגנה לעומק (כמו F-016 ב-mpm_api) — רק https
        raise ValueError("scheme לא-מאובטח ב-URL")  # לא אמור לקרות
    try:  # הבקשה
        with _urlrequest.urlopen(url, timeout=30) as r:  # nosec B310 — ה-scheme אומת למעלה
            elevs = _json.loads(r.read().decode("utf-8")).get("elevation", [])  # הגבהים
    except _urlerror.HTTPError as e:  # שגיאת HTTP
        if e.code == 429:  # מכסה
            try:  # Open-Meteo מחזיר JSON עם reason
                reason = _json.loads(e.read().decode("utf-8")).get("reason", "")  # הנוסח
            except (ValueError, OSError):  # גוף לא קריא
                reason = ""  # בלי נוסח
            raise _RateLimited(reason or "Open-Meteo: מכסת בקשות")  # לקורא
        raise  # שגיאת HTTP אחרת
    return [elevs[i] if i < len(elevs) else None for i in range(len(cells))]  # רשימה מקבילה


def _set(job_id, **kw):
    """עדכון שדות של job (בטוח לשרשורים)."""
    with _JOBS_LOCK:  # נעילה
        if job_id in _JOBS:  # עדיין קיים
            _JOBS[job_id].update(kw)  # העדכון


def _is_cancelled(job_id):
    """האם המשתמש ביטל."""
    with _JOBS_LOCK:  # נעילה
        return _JOBS.get(job_id, {}).get("cancelled", True)  # job שנמחק = מבוטל


def _sleep(job_id, seconds):
    """המתנה שמכבדת ביטול. False אם בוטל."""
    end = time.time() + seconds  # הסוף
    while time.time() < end:  # עד הסוף
        if _is_cancelled(job_id):  # בוטל
            return False  # עצירה
        time.sleep(min(0.5, max(0.0, end - time.time())))  # חצי שנייה
    return True  # הושלם


def _job_fetch(job_id):
    """fetch_cells לשירות: מטמון -> בקשות של 100 בקצב מבוקר -> המתנה וניסיון חוזר על חסימה דקתית.
    ביטול/מכסה -> rs.Aborted (הסטטוס נקבע כאן)."""
    def fetch(cells):  # הפונקציה שמוזרקת
        vals = [None] * len(cells)  # התוצאה
        todo = []  # מה שלא במטמון
        cached = _STORE.get_many(cells)  # T23: מהמטמון הקבוע
        for i, c in enumerate(cells):  # כל תא
            if c in cached:  # קיים
                vals[i] = cached[c]  # מהמטמון
            else:  # חסר
                todo.append(i)  # לשליפה
        if todo:  # SRTM מקומי לפני החלוקה לבקשות — ההשהיות חלות רק על מה שנשלח ל-Open-Meteo
            import srtm_dem  # ייבוא מקומי
            local = srtm_dem.lookup([cells[i] for i in todo])  # מקומי
            for i, v in zip(list(todo), local):  # מילוי
                if v is not None:  # יש ערך
                    vals[i] = v  # לתוצאה
            todo = [i for i, v in zip(todo, local) if v is None]  # נשארו החסרים
        total = (len(todo) + BATCH - 1) // BATCH  # מספר הבקשות
        sec_per_batch = BATCH * 60.0 / LOCS_PER_MIN + 1.5  # T23 (F-055): השהיית הקצב + זמן הבקשה
        _set(job_id, batches_total=total, batches_done=0, cached_cells=len(cells) - len(todo), eta_s=round(total * sec_per_batch))  # התקדמות + הערכת זמן
        for b in range(total):  # בקשה אחר בקשה
            idxs = todo[b * BATCH:(b + 1) * BATCH]  # התאים שלה
            attempt, net_errors = 0, 0  # מונים
            while True:  # ניסיון, וחזרה אם צריך
                if _is_cancelled(job_id):  # בוטל
                    _set(job_id, status="cancelled")  # מסמנים
                    raise rs.Aborted()  # עצירה
                try:  # הבקשה
                    got = _http_elevations([cells[i] for i in idxs])  # הגבהים
                    break  # הצליח
                except _RateLimited as e:  # מכסה
                    if "inutely" in str(e) and attempt < RATE_RETRIES:  # דקתית — עוברת תוך דקה
                        attempt += 1  # עוד המתנה
                        _set(job_id, note="ממתין דקה למכסת Open-Meteo…")  # לממשק
                        if not _sleep(job_id, 61):  # דקה ושנייה
                            _set(job_id, status="cancelled")  # בוטל בהמתנה
                            raise rs.Aborted()  # עצירה
                        _set(job_id, note=None)  # ממשיכים
                        continue  # ניסיון חוזר
                    _set(job_id, status="error", error="מכסת Open-Meteo נוצלה: " + str(e))  # שעתית/יומית
                    raise rs.Aborted()  # עצירה
                except (OSError, ValueError) as e:  # רשת (URLError הוא OSError) / תשובה לא קריאה
                    net_errors += 1  # עוד כשל
                    if net_errors >= 3:  # שלושה ברצף
                        msg = NET_ERROR_MSG if isinstance(e, OSError) else "שירות הגבהים (Open-Meteo) החזיר תשובה לא תקינה — נסה שוב בעוד רגע"  # T16 (F-048): הודעה אחידה, בלי "[Errno 11001] getaddrinfo failed"
                        _set(job_id, status="error", error=msg)  # שגיאה ברורה בעברית
                        raise rs.Aborted()  # עצירה
                    time.sleep(0.5 * net_errors)  # המתנה קצרה וחזרה
            for i, e in zip(idxs, got):  # כל תא
                vals[i] = e  # לתוצאה
            _STORE.put_many({cells[i]: e for i, e in zip(idxs, got)})  # T23: לשמירה קבועה (None לא נשמר)
            _set(job_id, batches_done=b + 1, eta_s=round((total - b - 1) * sec_per_batch))  # התקדמות + עדכון הערכת הזמן (T23)
            if b < total - 1 and not _sleep(job_id, len(idxs) * 60.0 / LOCS_PER_MIN):  # קצב מבוקר בין בקשות
                _set(job_id, status="cancelled")  # בוטל
                raise rs.Aborted()  # עצירה
        return vals  # הגבהים
    return fetch  # להזרקה


def _cleanup():
    """מוחק עבודות ישנות שהסתיימו."""
    now = time.time()  # עכשיו
    with _JOBS_LOCK:  # נעילה
        for k in [k for k, v in _JOBS.items() if v["status"] != "running" and now - v.get("finished", v["created"]) > v.get("ttl", JOB_TTL_S)]:  # ישנות (A6: תוצאת מאזור לאזור נשמרת שעות, מרגע הסיום)
            del _JOBS[k]  # מחיקה


def _start(work, ttl=JOB_TTL_S):
    """מתחיל job: work(job_id, fetch) מחזיר תוצאה (dict). מחזיר את מזהה ה-job. ttl: כמה זמן לשמור אחרי הסיום (A6)."""
    _cleanup()  # ניקוי
    job_id = uuid.uuid4().hex  # מזהה
    with _JOBS_LOCK:  # רישום
        _JOBS[job_id] = {"status": "running", "note": None, "batches_done": 0, "batches_total": None,
                         "result": None, "error": None, "cancelled": False, "created": time.time(), "cached_cells": 0,
                         "ttl": ttl, "eta_s": None}  # מצב התחלתי (A6: ttl; T23: הערכת זמן)

    def run():  # רץ ב-thread
        try:  # רשת ביטחון
            result = work(job_id, _job_fetch(job_id))  # העבודה
            _set(job_id, status="done", result=result, note=None, finished=time.time(), eta_s=None)  # הסתיים (A6: זמן סיום לניקוי)
        except rs.Aborted:  # בוטל/מכסה — הסטטוס נקבע; ביטול בין מועמדים עוד לא סומן
            with _JOBS_LOCK:  # בדיקה
                j = _JOBS.get(job_id)  # ה-job
                if j and j["status"] == "running":  # לא סומן
                    j["status"] = "cancelled"  # מסמנים
        except ValueError as e:  # שגיאה צפויה עם הסבר
            _set(job_id, status="error", error=str(e))  # לממשק
        except Exception as e:  # noqa: BLE001 — גבול thread: כל כשל חוזר כשגיאת job, לא נבלע ולא מפיל את התהליך
            _set(job_id, status="error", error="שגיאה בצד Python: " + str(e))  # לממשק

    threading.Thread(target=run, daemon=True).start()  # ברקע
    return job_id  # למעקב


# ═══════════════════════════ הפעולות ═══════════════════════════

def _check(params):
    """בדיקת מעקב (שלבים א1-א5) — אותו קלט כמו POST /radar_track/start בשרת."""
    lat, lon = float(params["lat"]), float(params["lon"])  # המכ"ם
    traj = params.get("trajectory")  # המסלול
    if not isinstance(traj, list) or len(traj) < 2 or len(traj) > rs.MAX_TRACK_POINTS:  # בדיקת גודל
        raise ValueError("מסלול חסר, קצר או ארוך מדי")  # הסבר
    p, track_cfg, alt_ref = rs.parse_all(params)  # כל הפרמטרים
    if alt_ref == "agl" and len(traj) > rs.MAX_AGL_POINTS:  # כל קודקוד דורש שליפה
        raise ValueError(f"גובה 'מעל הקרקע' נתמך עד {rs.MAX_AGL_POINTS} נקודות")  # הסבר

    def work(job_id, fetch):  # העבודה
        result = rs.run_check(lat, lon, p, traj, track_cfg, alt_ref, fetch)  # הצינור
        with _JOBS_LOCK:  # כמה מהמטמון
            result["terrain"]["cached"] = _JOBS[job_id].get("cached_cells", 0)  # השליפה האחרונה = השטח
        return result  # התוצאה
    return {"job_id": _start(work)}  # מזהה


def _profile(params):
    """פרופיל שטח לנקודה (שלב א3)."""
    lat, lon = float(params["lat"]), float(params["lon"])  # המכ"ם
    pt = params["point"]  # הנקודה
    point = {"lat": float(pt["lat"]), "lon": float(pt["lon"]), "alt": float(pt["alt"])}  # מיקום וגובה
    p = rs.rph._parse_radar_common_params(params)  # גובה אנטנה ומרווח רכס
    return {"job_id": _start(lambda job_id, fetch: rs.ray_profile(lat, lon, p, point, fetch))}  # job


def _placement(params):
    """הצעת מיקום (שלב ב')."""
    lat, lon = float(params["lat"]), float(params["lon"])  # מרכז החיפוש
    traj = params.get("trajectory")  # המסלול
    if not isinstance(traj, list) or len(traj) < 2 or len(traj) > rs.MAX_TRACK_POINTS:  # בדיקת גודל
        raise ValueError("מסלול חסר, קצר או ארוך מדי")  # הסבר
    radius_m = min(max(float(params.get("radius_km", 3.0)), 0.2), 30.0) * 1000.0  # רדיוס
    step_m = min(max(float(params.get("step_m", 500.0)), 50.0), 10000.0)  # מרווח
    n = len(rpl.candidate_grid(lat, lon, radius_m, step_m))  # כמה מועמדים
    if n > rpl.MAX_CANDIDATES:  # יותר מדי
        raise ValueError(f"יותר מדי מיקומים ({n}). הגדל את המרווח או הקטן את הרדיוס (עד {rpl.MAX_CANDIDATES}).")  # הסבר
    metric = "coverage" if params.get("metric") == "coverage" else "warning"  # הציון
    p, track_cfg, alt_ref = rs.parse_all(params)  # הפרמטרים

    def work(job_id, fetch):  # העבודה
        result = rs.run_placement(lat, lon, radius_m, step_m, metric, p, traj, track_cfg, alt_ref, fetch,
                                  lambda text: _set(job_id, note=text), lambda: _is_cancelled(job_id))  # הצינור
        with _JOBS_LOCK:  # כמה מהמטמון
            result["dem"]["cached"] = _JOBS[job_id].get("cached_cells", 0)  # צמתי הרשת
        return result  # התוצאה
    return {"job_id": _start(work), "candidates": n}  # מזהה + מספר מועמדים


def _rocket(params):
    """מסלול רקטה (שלב א6) — כמו POST /ballistics/rocket בשרת; המטאו ("live") נפתר כמו בכלי הבליסטי."""
    import mpm_api  # ייבוא מקומי — mpm_api מנתב לכאן, אז לא בראש הקובץ (מונע import מעגלי)
    import rocket_model  # המודל
    from mpm.geodesy import direct as _vincenty_direct  # אותה גיאודזיה כמו ה-MPM

    def work(_job_id, _fetch):  # העבודה (בלי שליפת גבהים)
        resolved, err = mpm_api._resolve_met_for_android(dict(params))  # מטאו חי -> שכבות
        if err:  # כשל במטאו
            raise ValueError(err.get("error", "שגיאת מטאו"))  # הסבר
        gun = resolved["gun"]  # המשגר
        atmo, met_meta = mpm_api._build_atmosphere(resolved.get("met"), float(gun["alt_m"]))  # האטמוספרה
        out = rocket_model.simulate(gun, float(resolved["elev_deg"]), float(resolved["azimuth_deg"]), resolved["rocket"], atmo,
                                    impact_alt=resolved.get("target_alt"), geo_direct=_vincenty_direct)  # הסימולציה
        out["met_used"] = met_meta  # שקיפות
        return out  # התוצאה
    return {"job_id": _start(work)}  # job


def _status(params):
    """מצב job — אותו מבנה כמו /radar_doppler/status בשרת."""
    with _JOBS_LOCK:  # קריאה
        j = _JOBS.get(params.get("job_id"))  # ה-job
        if j is None:  # לא קיים
            return {"status": "error", "error": "job לא נמצא"}  # שגיאה
        out = {k: j[k] for k in ("status", "note", "batches_done", "batches_total", "result", "error")}  # המצב
        out["eta_s"] = j.get("eta_s")  # T23 (F-055): הערכת זמן שנותר — בלי זה ההערכה לא מגיעה לממשק
        return out  # המצב


def _cancel(params):
    """ביטול job."""
    _set(params.get("job_id"), cancelled=True)  # הדגל — העבודה עוצרת בין בקשות/מועמדים
    return {"ok": True}  # אישור


def _profiles_library(_params):
    """ספריית הפרופילים המובנית (FR-D-286) — אותה פונקציה כמו GET /radar_profiles/library בשרת. קריאה סינכרונית:
    11 קבצים קטנים, בלי רשת — מהיר מספיק לריצה על ה-thread של הממשק. התיקייה ארוזה ב-APK (build_apk.ps1)."""
    import radar_service as _rs  # ייבוא מקומי — כמו שאר הפעולות כאן
    return {"profiles": _rs.load_profile_library()}  # [{name, file, params, notes}]


# ═══════════════════════════ ירי מאזור לאזור (A6) ═══════════════════════════
AREA_TTL_S = 6 * 3600  # A6: תוצאה נשמרת 6 שעות מהסיום, כמו בשרת


def _area_estimate(params):
    """הערכה לפני הרצה — סינכרונית (בלי רשת): נקודות, זוגות, תאים חסרים וזמן. כמו POST /ballistics/area/estimate."""
    import area_fire  # ייבוא מקומי
    import srtm_dem  # גבהים מקומיים — נחשבים "זמינים" בהערכה אם המשבצת כבר במכשיר
    def avail(cells):  # מטמון + SRTM שכבר הורד
        hit = set(_STORE.get_many(cells).keys())  # במטמון
        rest = [c for c in cells if c not in hit]  # השאר
        return hit | {c for c, v in zip(rest, srtm_dem.lookup(rest, allow_download=False)) if v is not None}  # הסט
    return area_fire.estimate(params, cached_fn=avail, workers=1)  # אנדרואיד: חישוב סדרתי


def _area_start(params):
    """חישוב מאזור לאזור כ-job — אותו מנוע ואותה תוצאה כמו בשרת. המטאו החי נשלף כמו בכלי הבליסטי."""
    import area_fire  # ייבוא מקומי
    import mpm_api  # מטאו חי לאנדרואיד
    area_fire.parse_request(params)  # אימות מוקדם — שגיאה ברורה מיד

    def work(job_id, fetch):  # העבודה
        def progress(d):  # התקדמות → שדות ה-job
            _set(job_id, note=d.get("note"))  # הודעת השלב
        return area_fire.run(params, fetch, met_fetch=mpm_api._default_fetch_met_live, progress=progress,  # המנוע
                             cancelled=lambda: _is_cancelled(job_id))  # ביטול
    return {"job_id": _start(work, ttl=AREA_TTL_S)}  # מזהה


def _area_result(job_id):
    """תוצאה של job מאזור לאזור שהסתיים, או None."""
    with _JOBS_LOCK:  # קריאה
        j = _JOBS.get(job_id)  # ה-job
        return j["result"] if j and j["status"] == "done" and isinstance(j["result"], dict) and "rows" in j["result"] else None  # רק תוצאת חישוב


def _area_visibility(params):
    """צביעת ירוק/אדום כ-job. המכ"מים המוצבים מגיעים מה-Dart (sites, באותו פורמט radar_sites), כי באנדרואיד הם שמורים באפליקציה."""
    import area_fire  # ייבוא מקומי
    res = _area_result(params.get("job_id"))  # תוצאת החישוב
    if res is None:  # אין
        raise ValueError("אין תוצאת חישוב מאזור לאזור (אולי נוקתה) — הרץ שוב")  # הסבר
    radars = area_fire.radar_list(params.get("sites") or [])  # המכ"מים

    def work(job_id, fetch):  # העבודה
        return area_fire.visibility(res["rows"], radars, fetch, progress=lambda d: _set(job_id, note=d.get("note")),  # המנוע
                                    cancelled=lambda: _is_cancelled(job_id))  # ביטול
    return {"job_id": _start(work, ttl=AREA_TTL_S), "radars": [r["name"] for r in radars]}  # מזהה + אילו מכ"מים


def _area_csv(params):
    """CSV של המסלולים (כולל נראות אם חושבה) — אותן עמודות כמו בשרת; ה-Dart משתף אותו כקובץ."""
    import csv  # ייצוא
    import io  # באפר
    res = _area_result(params.get("job_id"))  # תוצאת החישוב
    if res is None:  # אין
        raise ValueError("אין תוצאה לייצוא")  # הסבר
    vis = None  # צביעה
    with _JOBS_LOCK:  # קריאה
        vj = _JOBS.get(params.get("vis_job") or "")  # job הצביעה
        if vj and vj["status"] == "done" and isinstance(vj["result"], dict) and "masks" in vj["result"]:  # תקין
            vis = vj["result"]  # הצביעה
    def safe(v):  # הגנה מהזרקת נוסחה (CWE-1236)
        s = "" if v is None else str(v)  # מחרוזת
        return "'" + s if s[:1] in ("=", "+", "-", "@") else s  # גרש לפני תו מסוכן
    out = io.StringIO()  # באפר
    w = csv.writer(out)  # כותב
    w.writerow(["launch_area", "launch_lat", "launch_lon", "launch_alt_m", "target_area", "target_lat", "target_lon", "target_alt_m",  # כותרות
                "branch", "range_m", "qe_mils", "qe_deg", "fire_az_mils", "fire_az_deg", "tof_s", "apex_msl_m", "min_terrain_margin_m",
                "seen_fraction", "seen_by"])  # נראות
    names = [r["name"] for r in (vis or {}).get("radars", [])]  # שמות המכ"מים לפי ביט
    for i, r in enumerate(res["rows"]):  # כל מסלול
        frac, by = "", ""  # נראות
        if vis:  # יש צביעה
            m = vis["masks"][i]  # המסיכה
            frac = round(sum(1 for x in m if x) / len(m), 3)  # חלק נצפה
            bits = 0  # איחוד
            for x in m:  # כל נקודה
                bits |= x  # OR
            by = ";".join(n for b, n in enumerate(names) if bits & (1 << b))  # מי ראה
        w.writerow([safe(res["areas"]["launch"][r["la"]]), *r["launch"], safe(res["areas"]["target"][r["ta"]]), *r["target"],  # קצוות
                    "נמוך" if r["group"] == "low" else "גבוה", r["range_m"], r["qe"]["mils"], r["qe"]["deg"],  # פתרון
                    r["fire_azimuth"]["mils"], r["fire_azimuth"]["deg"], r["tof_s"], r["apex_msl_m"], r["min_terrain_margin_m"], frac, safe(by)])  # מדדים + נראות
    return {"csv": "\ufeff" + out.getvalue()}  # BOM ל-Excel


_ACTIONS = {"radar_check_start": _check, "radar_profile_start": _profile, "radar_placement_start": _placement,
            "rocket_start": _rocket, "radar_job_status": _status, "radar_job_cancel": _cancel,
            "radar_profiles_library": _profiles_library,  # טבלת הפעולות (+ספריית הפרופילים, FR-D-286)
            "radar_area_estimate": _area_estimate, "radar_area_start": _area_start,  # A6: מאזור לאזור (הקידומת radar_ מנותבת לכאן)
            "radar_area_visibility": _area_visibility, "radar_area_csv": _area_csv}  # A6: צביעה ו-CSV


def dispatch_json(action, params_json):
    """נקודת הכניסה מ-mpm_api.dispatch_json: מחרוזת JSON נכנסת, מחרוזת JSON יוצאת. כל פעולה חוזרת מיד."""
    try:  # גבול API ל-Kotlin
        fn = _ACTIONS.get(action)  # הפעולה
        if fn is None:  # לא מוכרת
            return _json.dumps({"ok": False, "error": f"פעולה לא מוכרת: {action}"})  # שגיאה
        out = fn(_json.loads(params_json))  # הרצה (מהירה — העבודה הכבדה ב-thread)
        out.setdefault("ok", True)  # הצלחה
        return _json.dumps(out)  # ל-Dart
    except (KeyError, TypeError, ValueError) as e:  # קלט לא תקין
        return _json.dumps({"ok": False, "error": f"קלט לא תקין: {e}"})  # שגיאה ברורה
    except Exception as e:  # noqa: BLE001 — גבול API ל-Kotlin: כל חריגה חייבת לחזור כ-JSON תקין, לא לקרוס את ה-bridge
        return _json.dumps({"ok": False, "error": f"שגיאה בצד Python: {e}"})  # שגיאה
