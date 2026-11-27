# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ירי מאזור לאזור (docs/PLAN_BALLISTICS_AREA_FIRE.md, שלבים A1–A2) — מנוע משותף ל-Desktop ולאנדרואיד.

הזרימה:
1. רשת נקודות: שיגור כל 500 מ', מטרה כל 200 מ' (קבוע, החלטה 9), מרכזי תאים בתוך כל מצולע.
2. גובה קרקע לכל נקודה דרך fetch_cells שמוזרק מבחוץ (בשרת: המטמון הקבוע + הקצב המבוקר).
3. טבלת ירי לכל אזור שיגור (החלטה 1): לכל צומת של כיוון × הפרש גובה — סריקת הגבהות מהירה (מסלול אחד ≈ 0.035 שנ'),
   שממנה מתקבלים טווח, סחיפה, זמן מעוף ופרופיל גובה לכל הגבהה, בענף הנמוך ובענף הגבוה.
4. כל זוג (נקודת שיגור × נקודת מטרה): אינטרפולציה הפוכה מהטבלה (טווח → הגבהה) לכל ענף, ואז סינון:
   טווח/הגבהה, טווח מינימלי, זמן מעוף מרבי, ומעבר מעל השטח (רכס) מול רשת שטח לאורך קו הירי (החלטה 2).
5. אימות (החלטה 1): מדגם (ברירת מחדל 5%) מהמסלולים האפשריים מורץ כמסלול אמיתי מנקודת השיגור עצמה, עם הפתרון
   שחושב, ונמדדת ההחטאה במטרים ושגיאת ההגבהה המשוערת במילים.
6. תוצאה: ספירת זוגות ומסלולים (החלטה 10), פירוט פסילות, ספירה לכל נקודת שיגור ומטרה (מפות חום), ושורה לכל מסלול
   עם קו קומפקטי לציור (21 נקודות: lat, lon, גובה).
7. נראות מכ"ם (A3, visibility): לכל מכ"ם מוצב מפת אופק (קרניים כל 0.5°, דגימה כל 150 מ', אותה נוסחה כמו /los:
   עקמומיות + שבירה k=0.13, "ratchet" על השטח הגולמי, מרווח רכס), ולכל נקודה במסלול — אילו מכ"מים רואים אותה.

קירובים מתועדים: פרופיל המסלול נמדד לאורך קו ישר בין השיגור למטרה (הסחיפה הצידית, עד כמה מאות מטרים, לא נכללת
בבדיקת הרכס ובציור); בדיקה מדויקת על המסלול האמיתי זמינה למסלול שנבחר (הכלי הבודד הקיים).
"""
import bisect  # חיפוש בינארי בדגימות הקרן (מרווחים לא אחידים)
import dataclasses  # עותק של FireParams עם שדות אחרים
import math  # טריגונומטריה, המרות
import random  # מדגם האימות (עם seed קבוע — תוצאה ניתנת לשחזור)
import time  # מדידת זמנים להערכת ETA

import mpm_api  # שכבת ה-API הקיימת של המנוע הבליסטי (אטמוספרה, פרמטרי ירי, פגז ברירת מחדל)
from mpm.engine import simulate  # ליבת הפיזיקה — ללא שינוי
from mpm.geodesy import direct as geo_direct, inverse as geo_inverse  # Vincenty — ללא שינוי
from mpm.units import both, mils_to_rad  # המרות זווית

LAUNCH_RES_M = 500.0  # רזולוציית אזורי שיגור — קבועה (החלטה 9)
TARGET_RES_M = 200.0  # רזולוציית אזורי מטרה — קבועה (החלטה 9)
TERRAIN_RES_M = 150.0  # רזולוציית רשת השטח לבדיקת הרכס (תאים משותפים, כדי שהמטמון ישמש שוב ושוב)
CREST_SKIP_M = 300.0  # לא בודקים רכס ב-300 מ' הראשונים והאחרונים (הלוע על הקרקע, והפגז יורד אל המטרה)
QE_LO_MILS = 10.0  # הגבהה נמוכה ביותר בסריקה
QE_HI_MILS = 1500.0  # הגבהה גבוהה ביותר בסריקה (~84°)
QE_STEP_MILS = 8.0  # צעד הסריקה (האינטרפולציה בין דגימות; שגיאתה נמדדת באימות)
PROFILE_N = 41  # נקודות בפרופיל הגובה (כל 2.5% מהטווח)
DRAW_N = 21  # נקודות בקו הציור של כל מסלול (כל 5% מהטווח — גם הרזולוציה של צביעת ירוק/אדום)
MAX_POLY_VERTICES = 500  # תקרת קודקודים למצולע (הגנה מקלט חריג)
M_PER_DEG_LAT = 111320.0  # מטרים למעלת רוחב (קירוב מקומי)
R_EARTH = 6371000.0  # רדיוס כדור הארץ לתיקון עקמומיות בפרופיל


class Aborted(Exception):  # ביטול מבחוץ (המשתמש לחץ "בטל")
    pass


# ═══════════════════════ קלט ורשתות ═══════════════════════

def _finite(v, name):  # מספר סופי, אחרת שגיאה ברורה
    try:
        f = float(v)  # המרה
    except (TypeError, ValueError):  # לא מספר
        raise ValueError(f"{name}: ערך לא מספרי")  # הודעה
    if not math.isfinite(f):  # NaN/Inf
        raise ValueError(f"{name}: ערך לא סופי")  # הודעה
    return f  # תקין


def _polygon(raw, name):  # מאמת מצולע [[lat,lon],...] ומחזיר רשימת (lat,lon)
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:  # פחות מ-3 קודקודים
        raise ValueError(f"{name}: מצולע צריך לפחות 3 נקודות")  # הודעה
    if len(raw) > MAX_POLY_VERTICES:  # יותר מדי
        raise ValueError(f"{name}: יותר מ-{MAX_POLY_VERTICES} קודקודים")  # הודעה
    pts = []  # התוצאה
    for i, p in enumerate(raw):  # כל קודקוד
        lat, lon = _finite(p[0], f"{name}[{i}].lat"), _finite(p[1], f"{name}[{i}].lon")  # מספרים
        if not (-89.0 <= lat <= 89.0 and -180.0 <= lon <= 180.0):  # מחוץ לטווח
            raise ValueError(f"{name}[{i}]: קואורדינטה מחוץ לטווח")  # הודעה
        pts.append((lat, lon))  # נוסף
    return pts  # המצולע


def _local_xy(lat0, lon0):  # הטלה מקומית (מטרים) סביב נקודת ייחוס — מספיקה לאזורים של עשרות ק"מ
    kx = M_PER_DEG_LAT * math.cos(math.radians(lat0))  # מטרים למעלת אורך בקו הרוחב הזה
    to_xy = lambda lat, lon: ((lon - lon0) * kx, (lat - lat0) * M_PER_DEG_LAT)  # noqa: E731  # (lat,lon) → (x,y)
    to_ll = lambda x, y: (lat0 + y / M_PER_DEG_LAT, lon0 + x / kx)  # noqa: E731  # (x,y) → (lat,lon)
    return to_xy, to_ll  # שתי הפונקציות


def _inside(x, y, poly):  # ray casting — האם (x,y) בתוך המצולע
    inside = False  # מצב
    n = len(poly)  # קודקודים
    for i in range(n):  # כל צלע
        x1, y1 = poly[i]  # קצה א
        x2, y2 = poly[(i + 1) % n]  # קצה ב
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:  # הקרן חוצה את הצלע
            inside = not inside  # מתהפך
    return inside  # התוצאה


def grid_points(polygon, res_m):  # מרכזי תאים ברזולוציה res_m בתוך המצולע; לפחות נקודה אחת (המרכז) לאזור קטן
    lat0 = sum(p[0] for p in polygon) / len(polygon)  # מרכז משוער — ייחוס להטלה
    lon0 = sum(p[1] for p in polygon) / len(polygon)  # כנ"ל
    to_xy, to_ll = _local_xy(lat0, lon0)  # הטלה
    poly = [to_xy(*p) for p in polygon]  # המצולע במטרים
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]  # לתיבה החוסמת
    out = []  # התוצאה
    y = min(ys) + res_m / 2.0  # שורה ראשונה — מרכז תא
    while y < max(ys):  # כל השורות
        x = min(xs) + res_m / 2.0  # עמודה ראשונה
        while x < max(xs):  # כל העמודות
            if _inside(x, y, poly):  # בתוך המצולע
                lat, lon = to_ll(x, y)  # חזרה לקואורדינטות
                out.append((round(lat, 6), round(lon, 6)))  # נקודה
            x += res_m  # עמודה הבאה
        y += res_m  # שורה הבאה
    if not out:  # אזור קטן מתא אחד
        out.append((round(lat0, 6), round(lon0, 6)))  # המרכז מייצג אותו
    return out  # הנקודות


def parse_request(req):  # מאמת את בקשת החישוב ומחזיר מבנה נקי (שגיאה ברורה על קלט שגוי)
    if not isinstance(req, dict):  # לא אובייקט
        raise ValueError("בקשה לא תקינה")  # הודעה
    def areas(key):  # רשימת אזורים
        raw = req.get(key) or []  # מהבקשה
        if not raw:  # ריק
            raise ValueError("נדרש לפחות אזור שיגור אחד ואזור מטרה אחד")  # הודעה
        return [{"name": str(a.get("name") or f"{key}-{i + 1}")[:80], "polygon": _polygon(a.get("polygon"), f"{key}[{i}]")}  # שם + מצולע
                for i, a in enumerate(raw)]  # כל אזור
    groups = [g for g in (req.get("groups") or ["low", "high"]) if g in ("low", "high")]  # ענפים
    if not groups:  # אף ענף
        raise ValueError("נדרש לפחות ענף אחד (נמוך/גבוה)")  # הודעה
    unit = req.get("angle_unit") or "mils"  # יחידת זווית לגבולות
    def opt_angle(key):  # גבול הגבהה אופציונלי → מילים
        v = req.get(key)  # הערך
        if v in (None, ""):  # לא הוגדר
            return None  # בלי גבול
        f = _finite(v, key)  # מספר
        return f if unit == "mils" else f * 6400.0 / 360.0  # מעלות → מילים (NATO 6400)
    def opt_num(key, lo=0.0):  # מספר אופציונלי לא שלילי
        v = req.get(key)  # הערך
        if v in (None, ""):  # לא הוגדר
            return None  # בלי
        return max(lo, _finite(v, key))  # מוצמד
    mv = _finite(req.get("mv", 684), "mv")  # מהירות לוע
    if not (50.0 <= mv <= 2000.0):  # טווח סביר
        raise ValueError("mv: מחוץ לטווח 50–2000 מ'/ש'")  # הודעה
    return {  # המבנה הנקי
        "launch_areas": areas("launch_areas"), "target_areas": areas("target_areas"),  # האזורים
        "mv": mv, "fitting": req.get("fitting") or {}, "coriolis": bool(req.get("coriolis", True)),  # פרמטרי ירי
        "earth_curvature": bool(req.get("earth_curvature", True)), "dt": min(0.1, max(0.005, _finite(req.get("dt", 0.02), "dt"))),  # צעד אינטגרציה מוגבל
        "met": req.get("met") or {"source": "standard"}, "groups": groups,  # מטאו וענפים
        "qe_min_mils": opt_angle("qe_min"), "qe_max_mils": opt_angle("qe_max"),  # גבולות הגבהה
        "min_range_m": opt_num("min_range_m") or 0.0, "max_tof_s": opt_num("max_tof_s"),  # טווח מינימלי, זמן מעוף מרבי
        "crest": bool(req.get("crest", True)), "safety_margin_m": opt_num("safety_margin_m") or 0.0,  # בדיקת רכס ומרווח
        "verify_frac": min(1.0, max(0.0, _finite(req.get("verify_frac", 0.05), "verify_frac"))),  # חלק המדגם לאימות
        "seed": int(req.get("seed", 1)),  # seed למדגם (שחזור)
    }


# ═══════════════════════ טבלת ירי ═══════════════════════

def _sim(atmo, fp_base, qe_rad, az_rad, target_alt, gun):  # מסלול בודד → מדדים + פרופיל גובה (או None כשלא פוגע)
    fp = dataclasses.replace(fp_base, qe=qe_rad, azimuth=az_rad, target_alt=target_alt)  # עותק עם הגבהה, כיוון וגובה מטרה (FireParams לא משתנה במקום)
    res = simulate(mpm_api._DEFAULT_PROJECTILE, atmo, fp, record=True)  # הסימולציה
    if not res.ok:  # לא הגיע לגובה המטרה (מעל הקודקוד) או נכשל
        return None  # לא פוגע
    imp = res.impact  # מדדי הפגיעה
    gd = [math.hypot(x, z) for x, z in zip(res.x, res.z)]  # מרחק קרקעי לאורך המסלול
    alt = [gun["alt_m"] + y + (x * x + z * z) / (2.0 * R_EARTH) for x, y, z in zip(res.x, res.y, res.z)]  # גובה MSL (כמו _path_points)
    rng = imp["ground_range_m"]  # הטווח
    prof, j = [], 0  # פרופיל בשברי טווח
    for k in range(PROFILE_N):  # כל שבר
        d = rng * k / (PROFILE_N - 1)  # המרחק הקרקעי
        while j < len(gd) - 2 and gd[j + 1] < d:  # מתקדמים לקטע הנכון
            j += 1  # הבא
        span = (gd[j + 1] - gd[j]) or 1e-9  # אורך הקטע
        t = min(1.0, max(0.0, (d - gd[j]) / span))  # מיקום בקטע
        prof.append(alt[j] + t * (alt[j + 1] - alt[j]))  # גובה באינטרפולציה
    return {"range": rng, "drift": imp["drift_z_m"], "tof": imp["time_of_flight_s"],  # טווח, סחיפה, זמן מעוף
            "apex": imp["max_ordinate_msl_m"], "prof": prof}  # קודקוד, פרופיל


def _branches(samples):  # מפצל סריקה (לפי הגבהה עולה) לענף נמוך (טווח עולה) וענף גבוה (טווח יורד)
    ok = [s for s in samples if s["d"] is not None]  # רק הגבהות שפוגעות
    if len(ok) < 2:  # אין מספיק
        return {"low": [], "high": []}  # ריק
    imax = max(range(len(ok)), key=lambda i: ok[i]["d"]["range"])  # הגבהת הטווח המרבי
    low = [ok[0]]  # ענף נמוך — רק החלק המונוטוני העולה
    for s in ok[1:imax + 1]:  # עד המרבי
        if s["d"]["range"] > low[-1]["d"]["range"]:  # עולה
            low.append(s)  # נוסף
    high = [ok[imax]]  # ענף גבוה — מהמרבי, טווח יורד
    for s in ok[imax + 1:]:  # אחרי המרבי
        if s["d"]["range"] < high[-1]["d"]["range"]:  # יורד
            high.append(s)  # נוסף
    return {"low": low, "high": high}  # שני הענפים


def _invert(branch, rng):  # טווח → פתרון באינטרפולציה בתוך ענף; None אם הטווח מחוץ לענף
    if len(branch) < 2:  # ענף ריק
        return None  # אין
    r0, r1 = branch[0]["d"]["range"], branch[-1]["d"]["range"]  # קצות הענף
    lo_r, hi_r = min(r0, r1), max(r0, r1)  # תחום הטווחים
    if not (lo_r <= rng <= hi_r):  # מחוץ לתחום
        return None  # לא בר השגה בענף הזה
    lo, hi = 0, len(branch) - 1  # חיפוש בינארי על הטווח (מונוטוני)
    asc = r1 > r0  # כיוון המונוטוניות
    while hi - lo > 1:  # עד קטע אחד
        mid = (lo + hi) // 2  # אמצע
        if (branch[mid]["d"]["range"] <= rng) == asc:  # בצד הנכון
            lo = mid  # ימינה
        else:
            hi = mid  # שמאלה
    a, b = branch[lo], branch[hi]  # הדגימות הסמוכות
    span = (b["d"]["range"] - a["d"]["range"]) or 1e-9  # הפרש הטווחים
    t = (rng - a["d"]["range"]) / span  # מיקום יחסי
    lerp = lambda u, v: u + t * (v - u)  # noqa: E731  # אינטרפולציה לינארית (לפרופיל, ולענף של 2 דגימות)
    da, db = a["d"], b["d"]  # המדדים
    qe = lerp(a["qe"], b["qe"])  # הגבהה — ניחוש ראשון לינארי
    if len(branch) >= 3:  # יש שכן שלישי — אינטרפולציה ריבועית (Lagrange) לפי ההגבהה: מדויקת בהרבה בענף הגבוה, שבו הסחיפה משתנה מהר
        i0 = lo - 1 if lo > 0 else hi + 1 if hi + 1 < len(branch) else lo  # השכן השלישי (לפני, או אחרי בקצה)
        tri = sorted({i0, lo, hi})  # שלוש דגימות סמוכות
        if len(tri) == 3:  # באמת שלוש
            q = [branch[i]["qe"] for i in tri]  # ההגבהות
            def quad(vals, x):  # פולינום Lagrange ממעלה 2 דרך שלוש הנקודות
                return sum(vals[i] * math.prod((x - q[j]) / (q[i] - q[j]) for j in range(3) if j != i) for i in range(3))  # הנוסחה
            def dquad(vals, x):  # הנגזרת שלו
                tot = 0.0  # סכום
                for i in range(3):  # כל איבר
                    js = [j for j in range(3) if j != i]  # שני האחרים
                    tot += vals[i] * ((x - q[js[0]]) + (x - q[js[1]])) / ((q[i] - q[js[0]]) * (q[i] - q[js[1]]))  # נגזרת המכפלה
                return tot  # הנגזרת
            rv = [branch[i]["d"]["range"] for i in tri]  # טווחים
            for _ in range(3):  # ניוטון: range(qe) = rng — 3 צעדים מספיקים מהניחוש הלינארי
                dr = dquad(rv, qe)  # שיפוע
                if abs(dr) < 1e-9:  # שטוח (שיא הטווח) — עוצרים
                    break  # יציאה
                qe -= (quad(rv, qe) - rng) / dr  # צעד
            qe = min(max(qe, min(q)), max(q))  # נשארים בתוך שלוש הדגימות
            pick = lambda key: quad([branch[i]["d"][key] for i in tri], qe)  # noqa: E731  # ערך שדה בהגבהה הזו
            slope = dquad(rv, qe)  # dR/dqe מדויק יותר
            return {"qe": qe, "drift": pick("drift"), "tof": pick("tof"), "apex": pick("apex"),  # הגבהה, סחיפה, זמן, קודקוד
                    "prof": [lerp(p, r) for p, r in zip(da["prof"], db["prof"])], "slope": slope}  # פרופיל (לינארי מספיק לרכס) + שיפוע
    return {"qe": qe, "drift": lerp(da["drift"], db["drift"]), "tof": lerp(da["tof"], db["tof"]),  # הגבהה, סחיפה, זמן
            "apex": lerp(da["apex"], db["apex"]), "prof": [lerp(p, q2) for p, q2 in zip(da["prof"], db["prof"])],  # קודקוד, פרופיל
            "slope": (b["d"]["range"] - a["d"]["range"]) / ((b["qe"] - a["qe"]) or 1e-9)}  # dR/dqe (מ' למיל) — להערכת שגיאת הגבהה


_TABLE_CACHE = {}  # מטמון צמתי טבלה בתהליך: ריצה חוזרת עם אותם פרמטרים לא מחשבת מחדש
_TABLE_CACHE_MAX = 256  # תקרה (כל צומת ≈ כמה מאות דגימות)


def _node_key(spec):  # מפתח יציב לצומת — מעוגל כך שהבדלים זניחים לא יחשבו מחדש
    g = spec["gun"]  # תותח הייחוס
    return (round(g["lat"], 4), round(g["lon"], 4), round(g["alt_m"]), round(spec["az"], 2), round(spec["talt"]),  # מיקום, כיוון, גובה מטרה
            spec["mv"], repr(sorted((spec["fitting"] or {}).items())), spec["coriolis"], spec["curv"], spec["dt"],  # פרמטרי ירי
            repr(spec["met"]))  # המטאו (כולל ערכים)


def _cache_put(key, val):  # הוספה למטמון עם תקרה
    if len(_TABLE_CACHE) >= _TABLE_CACHE_MAX:  # מלא
        _TABLE_CACHE.clear()  # איפוס פשוט
    _TABLE_CACHE[key] = val  # הוספה


def sweep_node(spec):  # סריקת הגבהות לצומת אחד → שני ענפים. פונקציה ברמת המודול כדי שתעבוד גם ב-multiprocessing (Windows spawn)
    gun = spec["gun"]  # תותח הייחוס
    atmo = mpm_api._build_atmosphere(spec["met"], gun["alt_m"])[0]  # אטמוספרה
    fp = mpm_api._fire_params(gun, spec["mv"], spec["fitting"], spec["coriolis"], spec["curv"], spec["dt"])  # פרמטרי בסיס
    az = math.radians(spec["az"])  # כיוון
    qes = [QE_LO_MILS + i * QE_STEP_MILS for i in range(int((QE_HI_MILS - QE_LO_MILS) / QE_STEP_MILS) + 1)]  # הגבהות
    return _branches([{"qe": q, "d": _sim(atmo, fp, mils_to_rad(q), az, spec["talt"], gun)} for q in qes])  # הסריקה


def _nodes(lo, hi, step, min_span):  # צמתים לאורך ציר: 1 אם התחום צר, אחרת קצוות + ביניים בצעד ≤ step
    if hi - lo < min_span:  # תחום צר
        return [(lo + hi) / 2.0]  # צומת אחד באמצע
    n = max(2, int(math.ceil((hi - lo) / step)) + 1)  # מספר צמתים
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]  # מפוזרים שווה


def _bracket(nodes, v):  # שני צמתים סמוכים ומשקל — לאינטרפולציה לינארית בציר
    if len(nodes) == 1:  # צומת יחיד
        return [(0, 1.0)]  # רק הוא
    if v <= nodes[0]:  # מתחת לתחום
        return [(0, 1.0)]  # הקצה
    if v >= nodes[-1]:  # מעל התחום
        return [(len(nodes) - 1, 1.0)]  # הקצה
    for i in range(len(nodes) - 1):  # הקטע שמכיל את v
        if nodes[i] <= v <= nodes[i + 1]:  # נמצא
            t = (v - nodes[i]) / ((nodes[i + 1] - nodes[i]) or 1e-9)  # משקל
            return [(i, 1.0 - t), (i + 1, t)]  # שני הצמתים
    return [(len(nodes) - 1, 1.0)]  # לא אמור לקרות


def _ang_diff(a, b):  # הפרש זוויות במעלות בתחום [-180, 180)
    return (a - b + 180.0) % 360.0 - 180.0  # עטיפה


# ═══════════════════════ המנוע ═══════════════════════

def plan(req):  # רשתות וספירות בלי רשת ובלי חישוב בליסטי — להערכה לפני הרצה
    p = parse_request(req)  # אימות
    launch = [grid_points(a["polygon"], LAUNCH_RES_M) for a in p["launch_areas"]]  # נקודות שיגור לכל אזור
    target = [grid_points(a["polygon"], TARGET_RES_M) for a in p["target_areas"]]  # נקודות מטרה לכל אזור
    n_l, n_t = sum(map(len, launch)), sum(map(len, target))  # סכומים
    return {"parsed": p, "launch": launch, "target": target, "launch_points": n_l, "target_points": n_t,  # הרשתות
            "pairs": n_l * n_t, "trajectories_max": n_l * n_t * len(p["groups"])}  # זוגות ומסלולים מרביים


def _terrain_cell(lat, lon, lat_step, lon_step):  # הצמדה לתא ברשת השטח המשותפת
    return (round(round(lat / lat_step) * lat_step, 6), round(round(lon / lon_step) * lon_step, 6))  # מפתח יציב


def run(req, fetch_cells, met_fetch=None, progress=None, cancelled=None, map_fn=None):  # החישוב המלא; map_fn: למשל pool.map לחישוב צמתי הטבלה במקביל
    """fetch_cells(list[(lat,lon)]) -> list[elev|None]; met_fetch(lat, lon, alt) -> (met_inline, err) ל-met.source=live.
    progress(dict) נקרא בכל שלב; cancelled() → True עוצר ב-Aborted."""
    t_start = time.time()  # לזמני ריצה
    def tick(**kw):  # דיווח התקדמות + בדיקת ביטול
        if cancelled and cancelled():  # בוטל
            raise Aborted()  # עצירה
        if progress:  # יש מאזין
            progress(kw)  # דיווח
    pl = plan(req)  # רשתות
    p, launch, target = pl["parsed"], pl["launch"], pl["target"]  # קיצורים
    tick(stage="elevations", note="שולף גבהי קרקע לנקודות האזורים…")  # שלב 1
    all_pts = [pt for g in launch for pt in g] + [pt for g in target for pt in g]  # כל הנקודות
    elevs = fetch_cells(all_pts)  # גבהים (מטמון/רשת)
    elev = dict(zip(all_pts, elevs))  # נקודה → גובה
    missing = sum(1 for e in elevs if e is None)  # כמה חסרים
    if missing:  # חישוב בלי גובה = שגוי בשקט — לא ממשיכים (כמו F-053)
        raise ValueError(f"חסר גובה קרקע ל-{missing} נקודות — נסה שוב (ייתכן שמכסת Open-Meteo נוצלה)")  # הודעה
    tgt_flat = [(ai, pt) for ai, g in enumerate(target) for pt in g]  # כל נקודות המטרה עם האזור שלהן
    rows, per_launch, per_target = [], {}, {}  # התוצאות
    rejects = {"out_of_range": 0, "qe_limits": 0, "min_range": 0, "max_tof": 0, "terrain": 0}  # פירוט פסילות (למסלולים)
    pairs_ok = 0  # זוגות עם לפחות מסלול אחד
    lat_ref = sum(pt[0] for pt in all_pts) / len(all_pts)  # רוחב ייחוס לרשת השטח
    lat_step = TERRAIN_RES_M / M_PER_DEG_LAT  # צעד רוחב
    lon_step = TERRAIN_RES_M / (M_PER_DEG_LAT * math.cos(math.radians(lat_ref)))  # צעד אורך
    tables_meta = []  # תיאור הטבלאות (לשקיפות)
    for li, gpts in enumerate(launch):  # כל אזור שיגור
        ref_lat = sum(g[0] for g in gpts) / len(gpts)  # מרכז האזור
        ref_lon = sum(g[1] for g in gpts) / len(gpts)  # כנ"ל
        ref_alt = sum(elev[g] for g in gpts) / len(gpts)  # גובה ממוצע
        gun_ref = {"lat": ref_lat, "lon": ref_lon, "alt_m": ref_alt}  # תותח הייחוס של הטבלה
        met = p["met"]  # מטאו לאזור (החלטה 7: אחד לכל אזור שיגור)
        if (met.get("source") or "").lower() in ("live", "open-meteo", "openmeteo"):  # תחזית חיה
            if met_fetch is None:  # אין מי שישלוף
                raise ValueError("מטאו חי לא זמין כאן — בחר אטמוספרה תקנית")  # הודעה
            met, err = met_fetch(ref_lat, ref_lon, ref_alt)  # תחזית במרכז האזור
            if err:  # כשל
                raise ValueError("שליפת מטאו נכשלה: " + str(err.get("error", err)))  # הודעה
        met_meta = mpm_api._build_atmosphere(met, ref_alt)[1]  # תיאור המטאו לשקיפות (האטמוספרה עצמה נבנית בכל צומת, גם בתהליך נפרד)
        geo = []  # גאומטריה לכל זוג: (gi, ti, range, az, dh)
        for gi, g in enumerate(gpts):  # כל נקודת שיגור
            for ti, (_, t) in enumerate(tgt_flat):  # כל נקודת מטרה
                rng, az = geo_inverse(g[0], g[1], t[0], t[1])  # טווח ואזימוט (Vincenty)
                geo.append((gi, ti, rng, az, elev[t] - elev[g]))  # הפרש גובה מטרה-שיגור
        az_mean = math.degrees(math.atan2(sum(math.sin(math.radians(x[3])) for x in geo), sum(math.cos(math.radians(x[3])) for x in geo)))  # ממוצע מעגלי
        d_az = [_ang_diff(x[3], az_mean) for x in geo]  # סטיות מהממוצע
        az_nodes = [az_mean + d for d in _nodes(min(d_az), max(d_az), 20.0, 2.0)]  # צמתי כיוון (כל ≤20°)
        dh_nodes = _nodes(min(x[4] for x in geo), max(x[4] for x in geo), 150.0, 30.0)  # צמתי הפרש גובה (כל ≤150 מ')
        qes = [QE_LO_MILS + i * QE_STEP_MILS for i in range(int((QE_HI_MILS - QE_LO_MILS) / QE_STEP_MILS) + 1)]  # הגבהות הסריקה
        g_alts = [elev[g] for g in gpts]  # גובהי נקודות השיגור
        ga_nodes = _nodes(min(g_alts), max(g_alts), 150.0, 30.0)  # צמתי גובה שיגור (כל ≤150 מ') — צפיפות האוויר תלויה בגובה (נמדד: 160 מ' הפרש = ~60 מ' החטאה)
        table, n_nodes = {}, len(az_nodes) * len(dh_nodes) * len(ga_nodes)  # הטבלה: (ia, idh, ig) → ענפים
        specs = []  # צמתים שצריך לחשב (לא במטמון)
        for ia, azn in enumerate(az_nodes):  # כל צומת כיוון
            for idh, dhn in enumerate(dh_nodes):  # כל צומת הפרש גובה
                for ig, gan in enumerate(ga_nodes):  # כל צומת גובה שיגור
                    spec = {"gun": dict(gun_ref, alt_m=gan), "met": met, "mv": p["mv"], "fitting": p["fitting"], "coriolis": p["coriolis"],  # כל מה שקובע את הסריקה
                            "curv": p["earth_curvature"], "dt": p["dt"], "az": azn % 360.0, "talt": gan + dhn}  # כיוון, גובה שיגור וגובה מטרה
                    key = _node_key(spec)  # מפתח מטמון
                    if key in _TABLE_CACHE:  # כבר חושב (ריצה קודמת עם אותם פרמטרים, למשל שינוי סינון בלבד)
                        table[(ia, idh, ig)] = _TABLE_CACHE[key]  # מהמטמון
                    else:  # צריך לחשב
                        specs.append(((ia, idh, ig), key, spec))  # לרשימה
        tick(stage="table", area=li, node=n_nodes - len(specs), nodes=n_nodes, note=f"טבלת ירי לאזור שיגור {li + 1}: {len(specs)} צמתים לחישוב")  # התקדמות
        done_nodes = n_nodes - len(specs)  # מונה
        for (ij, key, spec), br in zip(specs, (map_fn or map)(sweep_node, [s for _, _, s in specs])):  # map_fn: במקביל בשרת, סדרתי כברירת מחדל
            table[ij] = br  # לטבלה
            _cache_put(key, br)  # למטמון
            done_nodes += 1  # עוד צומת
            tick(stage="table", area=li, node=done_nodes, nodes=n_nodes, note=f"טבלת ירי לאזור שיגור {li + 1}: צומת {done_nodes}/{n_nodes}")  # התקדמות
        tables_meta.append({"area": p["launch_areas"][li]["name"], "az_nodes": len(az_nodes), "dh_nodes": len(dh_nodes), "gun_alt_nodes": len(ga_nodes),  # תיאור
                            "trajectories": n_nodes * len(qes), "met": met_meta})  # כמה מסלולים נסרקו
        az_rel_nodes = [_ang_diff(a, az_mean) for a in az_nodes]  # צמתי הכיוון כסטייה (לאינטרפולציה)
        tick(stage="pairs", area=li, note=f"מחשב זוגות לאזור שיגור {li + 1}…")  # שלב הזוגות
        pending = []  # מסלולים שעברו את כל הסינונים חוץ מרכס
        for k, (gi, ti, rng, az, dh) in enumerate(geo):  # כל זוג
            if k % 2000 == 0:  # מדי פעם
                tick(stage="pairs", area=li, pair=k, pairs=len(geo), note=f"זוגות באזור שיגור {li + 1}: {k}/{len(geo)}")  # התקדמות
            wa = _bracket(az_rel_nodes, _ang_diff(az, az_mean))  # משקלי כיוון
            wd = _bracket(dh_nodes, dh)  # משקלי הפרש גובה
            g_alt = elev[gpts[gi]]  # גובה נקודת השיגור
            wg = _bracket(ga_nodes, g_alt)  # משקלי גובה שיגור
            pair_has = False  # האם לזוג יש מסלול
            for grp in p["groups"]:  # כל ענף
                acc, wsum, ok = None, 0.0, True  # צבירה משוקללת
                for ia, w1 in wa:  # צמתי כיוון
                    for idh, w2 in wd:  # צמתי הפרש גובה
                        for ig, w3 in wg:  # צמתי גובה שיגור
                            s = _invert(table[(ia, idh, ig)][grp], rng)  # פתרון בצומת
                            if s is None:  # לא בר השגה בצומת הזה
                                ok = False  # שמרני — הזוג נפסל
                                break  # יציאה
                            w = w1 * w2 * w3  # משקל
                            if acc is None:  # ראשון
                                acc = {"qe": 0.0, "drift": 0.0, "tof": 0.0, "apex": 0.0, "slope": 0.0, "prof": [0.0] * PROFILE_N}  # אפסים
                            for key in ("qe", "drift", "tof", "apex", "slope"):  # שדות סקלריים
                                acc[key] += w * s[key]  # צבירה
                            shift = g_alt - ga_nodes[ig]  # הפרופיל של הצומת מחושב מגובה הצומת — מזיזים לגובה השיגור האמיתי
                            acc["prof"] = [a + w * (b + shift) for a, b in zip(acc["prof"], s["prof"])]  # פרופיל
                            wsum += w  # סכום משקלים
                        if not ok:  # כבר נפסל
                            break  # יציאה
                    if not ok:  # כבר נפסל
                        break  # יציאה
                if not ok or acc is None:  # לא בר השגה
                    rejects["out_of_range"] += 1  # פסילה
                    continue  # הענף הבא
                sol = {key: (v / wsum if key != "prof" else [x / wsum for x in v]) for key, v in acc.items()}  # נרמול
                reason = None  # סיבת פסילה
                if p["qe_min_mils"] is not None and sol["qe"] < p["qe_min_mils"] or p["qe_max_mils"] is not None and sol["qe"] > p["qe_max_mils"]:  # גבולות הגבהה
                    reason = "qe_limits"  # מחוץ לגבולות
                elif rng < p["min_range_m"]:  # קרוב מדי
                    reason = "min_range"  # טווח מינימלי
                elif p["max_tof_s"] is not None and sol["tof"] > p["max_tof_s"]:  # זמן מעוף ארוך
                    reason = "max_tof"  # זמן מעוף
                if reason:  # נפסל
                    rejects[reason] += 1  # פירוט
                    continue  # הבא
                pending.append((gi, ti, grp, rng, az, sol))  # לבדיקת רכס
                pair_has = True  # יש מועמד
            if not p["crest"] and pair_has:  # בלי בדיקת רכס — הזוג כבר נספר
                pairs_ok += 1  # זוג אפשרי
        cells_for = []  # תאי שטח לכל מועמד (לרכס)
        if p["crest"] and pending:  # צריך רשת שטח
            uniq = {}  # תא → None (סט מסודר)
            for gi, ti, grp, rng, az, sol in pending:  # כל מועמד
                g, t = gpts[gi], tgt_flat[ti][1]  # הקצוות
                n = max(2, int(math.ceil(rng / TERRAIN_RES_M)))  # מספר דגימות
                cs = []  # התאים של המסלול הזה
                for kk in range(1, n):  # דגימות פנימיות
                    d = rng * kk / n  # מרחק
                    if d < CREST_SKIP_M or d > rng - CREST_SKIP_M:  # קרוב ללוע/למטרה
                        continue  # מדלגים
                    f = kk / n  # שבר
                    c = _terrain_cell(g[0] + f * (t[0] - g[0]), g[1] + f * (t[1] - g[1]), lat_step, lon_step)  # תא
                    cs.append((f, c))  # נשמר
                    uniq[c] = None  # לסט
                cells_for.append(cs)  # לפי סדר pending
            cell_list = list(uniq)  # התאים הייחודיים
            tick(stage="terrain", area=li, cells=len(cell_list), note=f"שולף שטח לבדיקת רכס: {len(cell_list)} תאים…")  # שלב השטח
            terr = dict(zip(cell_list, fetch_cells(cell_list)))  # גבהים (מטמון/רשת)
        pair_seen = set()  # זוגות שנספרו (לרכס)
        for idx, (gi, ti, grp, rng, az, sol) in enumerate(pending):  # בדיקת רכס + רישום
            min_margin = None  # מרווח מינימלי
            if p["crest"]:  # בדיקה
                for f, c in cells_for[idx]:  # כל דגימה
                    te = terr.get(c)  # גובה השטח
                    if te is None:  # חסר — לא מכריעים לפיו
                        continue  # הבא
                    pos = f * (PROFILE_N - 1)  # מיקום בפרופיל
                    j = min(PROFILE_N - 2, int(pos))  # אינדקס
                    h = sol["prof"][j] + (pos - j) * (sol["prof"][j + 1] - sol["prof"][j])  # גובה הפגז
                    m = h - p["safety_margin_m"] - te  # מרווח
                    if min_margin is None or m < min_margin:  # מינימום
                        min_margin = m  # עדכון
                if min_margin is not None and min_margin < 0:  # פוגע בשטח
                    rejects["terrain"] += 1  # פסילה
                    continue  # הבא
                if (gi, ti) not in pair_seen:  # זוג חדש
                    pair_seen.add((gi, ti))  # נרשם
                    pairs_ok += 1  # זוג אפשרי
            g, t = gpts[gi], tgt_flat[ti][1]  # הקצוות
            dev = math.atan2(sol["drift"], rng)  # סטייה צידית (ימינה חיובי) → תיקון כיוון
            fire_az = math.radians(az) - dev  # אזימוט ירי
            draw = []  # קו ציור קומפקטי
            for kk in range(DRAW_N):  # 11 נקודות
                f = kk / (DRAW_N - 1)  # שבר
                pos = f * (PROFILE_N - 1)  # מיקום בפרופיל
                j = min(PROFILE_N - 2, int(pos))  # אינדקס
                h = sol["prof"][j] + (pos - j) * (sol["prof"][j + 1] - sol["prof"][j])  # גובה
                draw.append([round(g[0] + f * (t[0] - g[0]), 6), round(g[1] + f * (t[1] - g[1]), 6), round(h, 1)])  # נקודה
            rows.append({"la": li, "lp": gi, "ta": tgt_flat[ti][0], "tp": ti, "group": grp,  # מזהים
                         "launch": [g[0], g[1], round(elev[g], 1)], "target": [t[0], t[1], round(elev[t], 1)],  # קצוות + גבהים
                         "range_m": round(rng, 1), "qe": both(mils_to_rad(sol["qe"])), "fire_azimuth": both(fire_az % (2 * math.pi)),  # פתרון
                         "target_azimuth": both(math.radians(az)), "tof_s": round(sol["tof"], 2), "apex_msl_m": round(sol["apex"], 1),  # מדדים
                         "min_terrain_margin_m": None if min_margin is None else round(min_margin, 1), "path": draw,  # רכס + ציור
                         "_slope": sol["slope"], "_gun_alt": elev[g]})  # לאימות (נמחקים בסוף)
            key_l = (li, gi)  # מפתח נקודת שיגור
            per_launch[key_l] = per_launch.get(key_l, 0) + 1  # ספירה
            per_target[ti] = per_target.get(ti, 0) + 1  # ספירה
    verify = _verify(rows, p, met_fetch, tick)  # אימות מדגמי
    for r in rows:  # ניקוי שדות פנימיים
        r.pop("_slope", None)  # שיפוע
        r.pop("_gun_alt", None)  # גובה
    heat_launch = [{"area": li, "lat": g[0], "lon": g[1], "count": per_launch.get((li, gi), 0)}  # מפת חום — שיגור
                   for li, gpts in enumerate(launch) for gi, g in enumerate(gpts)]  # כל נקודה
    heat_target = [{"area": ai, "lat": t[0], "lon": t[1], "count": per_target.get(ti, 0)}  # מפת חום — מטרה
                   for ti, (ai, t) in enumerate(tgt_flat)]  # כל נקודה
    return {  # התוצאה
        "summary": {"launch_points": pl["launch_points"], "target_points": pl["target_points"], "pairs": pl["pairs"],  # גדלים
                    "pairs_feasible": pairs_ok, "trajectories_feasible": len(rows), "trajectories_checked": pl["trajectories_max"],  # ספירות (החלטה 10)
                    "rejected": rejects, "groups": p["groups"], "elapsed_s": round(time.time() - t_start, 1),  # פסילות, זמן
                    "met": " · ".join(dict.fromkeys(m["met"].get("description") or "" for m in tables_meta if m["met"].get("description"))),  # FR-D-299: מקור המטאו (תחזית חיה: שעה, וגיל אם שמורה)
                    "met_stale": any("שמורה מלפני" in (m["met"].get("description") or "") for m in tables_meta)},  # FR-D-299: תחזית שמורה בגלל כשל שליפה — אזהרה בתצוגה
        "verification": verify, "tables": tables_meta,  # אימות וטבלאות
        "resolution_m": {"launch": LAUNCH_RES_M, "target": TARGET_RES_M, "terrain": TERRAIN_RES_M},  # רזולוציות
        "areas": {"launch": [a["name"] for a in p["launch_areas"]], "target": [a["name"] for a in p["target_areas"]]},  # שמות
        "heat": {"launch": heat_launch, "target": heat_target}, "rows": rows,  # מפות חום ושורות
    }


def _verify(rows, p, met_fetch, tick):  # אימות: מסלול אמיתי מהשיגור עם הפתרון המשוער → החטאה במטרים
    if not rows or p["verify_frac"] <= 0:  # אין מה לאמת
        return {"checked": 0}  # ריק
    rnd = random.Random(p["seed"])  # מדגם ניתן לשחזור
    n = max(1, min(len(rows), int(round(len(rows) * p["verify_frac"]))))  # גודל המדגם
    sample = rnd.sample(rows, n)  # המדגם
    misses, qe_errs, atmo_cache = [], [], {}  # תוצאות, ומטמון אטמוספרה לפי גובה מעוגל
    for k, r in enumerate(sample):  # כל מסלול במדגם
        if k % 50 == 0:  # מדי פעם
            tick(stage="verify", done=k, total=n, note=f"מאמת דיוק: {k}/{n}")  # התקדמות
        gun = {"lat": r["launch"][0], "lon": r["launch"][1], "alt_m": r["_gun_alt"]}  # התותח האמיתי
        met = p["met"]  # המטאו
        if (met.get("source") or "").lower() in ("live", "open-meteo", "openmeteo"):  # חי — האימות על אטמוספרה תקנית מאותה תחזית לא זמינה כאן
            met = {"source": "standard"}  # שמרני: האימות מודד את שגיאת האינטרפולציה, לא את המטאו
        akey = (round(gun["alt_m"] / 10.0), id(met))  # מפתח מטמון
        if akey not in atmo_cache:  # חדש
            atmo_cache[akey] = mpm_api._build_atmosphere(met, gun["alt_m"])[0]  # אטמוספרה לגובה הזה
        fp = mpm_api._fire_params(gun, p["mv"], p["fitting"], p["coriolis"], p["earth_curvature"], p["dt"])  # פרמטרים
        qe = mils_to_rad(r["qe"]["mils"])  # ההגבהה המשוערת
        d = _sim(atmo_cache[akey], fp, qe, mils_to_rad(r["fire_azimuth"]["mils"]), r["target"][2], gun)  # מסלול אמיתי
        if d is None:  # לא פגע כלל
            misses.append(float("inf"))  # החטאה מלאה
            continue  # הבא
        bearing = r["fire_azimuth"]["deg"] + math.degrees(math.atan2(d["drift"], d["range"]))  # כיוון נקודת הפגיעה
        lat, lon = geo_direct(gun["lat"], gun["lon"], bearing % 360.0, d["range"])  # נקודת הפגיעה (range כבר מרחק קרקעי כולל הסחיפה)
        miss, _ = geo_inverse(lat, lon, r["target"][0], r["target"][1])  # מרחק מהמטרה
        misses.append(miss)  # נרשם
        if r["_slope"]:  # יש שיפוע
            qe_errs.append(abs((d["range"] - r["range_m"]) / r["_slope"]))  # שגיאת הגבהה משוערת במילים
    finite = [m for m in misses if math.isfinite(m)]  # החטאות סופיות
    return {"checked": n, "no_impact": n - len(finite),  # כמה נבדקו / לא פגעו
            "miss_max_m": round(max(finite), 1) if finite else None,  # החטאה מרבית
            "miss_rms_m": round(math.sqrt(sum(m * m for m in finite) / len(finite)), 1) if finite else None,  # RMS
            "qe_err_max_mils": round(max(qe_errs), 2) if qe_errs else None,  # שגיאת הגבהה מרבית
            "qe_err_rms_mils": round(math.sqrt(sum(e * e for e in qe_errs) / len(qe_errs)), 2) if qe_errs else None}  # RMS


# ═══════════════════════ נראות מכ"ם (A3) ═══════════════════════

REFRACTION_K = 0.13  # מקדם שבירה — זהה ל-_horizon_ratchet ב-weather_server.py (קו ראייה, רדיוס ראייה)
AZ_BIN_DEG = 0.5  # רוחב קרן במפת האופק (ב-30 ק"מ ≈ 260 מ' רוחב)
RAY_STEP_FRAC = 0.005  # מרווח הדגימה לאורך קרן גדל עם המרחק (0.5% מהמרחק, לפחות 150 מ') — מכ"ם בטווח 300 ק"מ לא דורש אלפי תאים


def _haversine_az(lat1, lon1, lat2, lon2):  # מרחק (מ') ואזימוט (°) מהיר — מספיק לעשרות ק"מ (Vincenty איטי מדי למאות אלפי נקודות)
    p1, p2 = math.radians(lat1), math.radians(lat2)  # רוחב ברדיאנים
    dl = math.radians(lon2 - lon1)  # הפרש אורך
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2  # haversine
    d = 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))  # מרחק
    az = math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)))  # אזימוט התחלתי
    return d, az % 360.0  # מרחק, אזימוט


def _in_sector(az, start, end):  # האם האזימוט בגזרה (start→end עם כיוון השעון; 0..360 = הכול)
    if start is None or end is None:  # לא הוגדרה גזרה
        return True  # הכול
    s, e, a = float(start) % 360.0, float(end) % 360.0, az % 360.0  # נרמול
    if abs(s - e) < 1e-9:  # התחלה = סוף (למשל 0→360) — גזרה מלאה
        return True  # הכול
    return s <= a <= e if s <= e else (a >= s or a <= e)  # כולל עטיפה דרך צפון


def radar_list(sites):  # ממיר מכ"מים מוצבים (פורמט radar_sites השמור) לרשימת מכ"מים לנראות
    out = []  # התוצאה
    for s in sites or []:  # כל מכ"ם
        pr = s.get("params") or s  # הפרמטרים (פורמט שמור או שטוח)
        try:
            out.append({"name": str(s.get("name") or "מכ\"ם")[:80], "lat": _finite(pr["lat"], "lat"), "lon": _finite(pr["lon"], "lon"),  # שם ומיקום
                        "h_antenna": _finite(pr.get("h_antenna", 5), "h_antenna"), "range_km": _finite(pr.get("range_km", 50), "range_km"),  # אנטנה וטווח
                        "start": pr.get("start_bearing_deg"), "end": pr.get("end_bearing_deg"),  # גזרה
                        "margin_deg": _finite(pr.get("ridge_margin_deg", 0) or 0, "ridge_margin_deg")})  # מרווח רכס
        except (KeyError, ValueError):  # מכ"ם בלי מיקום — מדלגים
            continue  # הבא
    return out  # הרשימה


def visibility(rows, radars, fetch_cells, progress=None, cancelled=None):  # לכל נקודה בכל מסלול: מסיכת ביטים של המכ"מים שרואים אותה
    """rows: שורות מ-run() (עם path); radars: radar_list(...). מחזיר {"masks": [[int]*DRAW_N per row], "radars": [...], "summary": {...}}.
    בלי מכ"מים — כל המסיכות 0 (הכול אדום, החלטה 14). אותה נוסחה כמו /los."""
    def tick(**kw):  # התקדמות + ביטול
        if cancelled and cancelled():  # בוטל
            raise Aborted()  # עצירה
        if progress:  # מאזין
            progress(kw)  # דיווח
    masks = [[0] * len(r["path"]) for r in rows]  # ברירת מחדל: אף מכ"ם לא רואה
    stats = []  # סטטיסטיקה לכל מכ"ם
    if not radars or not rows:  # אין מכ"מים או מסלולים
        return {"masks": masks, "radars": [], "summary": {"radars": 0, "points": sum(map(len, masks)), "points_seen": 0}}  # הכול אדום
    lat_ref = sum(r["launch"][0] for r in rows) / len(rows)  # רוחב ייחוס לרשת השטח (כמו ב-run)
    lat_step = TERRAIN_RES_M / M_PER_DEG_LAT  # צעד רוחב
    lon_step = TERRAIN_RES_M / (M_PER_DEG_LAT * math.cos(math.radians(lat_ref)))  # צעד אורך
    grounds = fetch_cells([(round(rd["lat"], 6), round(rd["lon"], 6)) for rd in radars])  # גובה הקרקע בכל מכ"ם
    for bit, (rd, ground) in enumerate(zip(radars, grounds)):  # כל מכ"ם (ביט משלו, עד 30)
        if bit >= 30:  # מסיכה ב-int — תקרה מעשית
            break  # יציאה
        tick(stage="visibility", radar=bit, note=f"מפת אופק למכ\"ם {rd['name']}…")  # התקדמות
        if ground is None:  # אין גובה למכ"ם — לא מנחשים
            stats.append({"name": rd["name"], "error": "חסר גובה קרקע במיקום המכ\"ם", "points_seen": 0})  # מדווחים
            continue  # הבא
        h_obs = ground + rd["h_antenna"]  # גובה האנטנה MSL
        r_max = rd["range_km"] * 1000.0  # טווח מרבי במטרים
        margin = math.tan(math.radians(rd["margin_deg"]))  # מרווח רכס כשיפוע (כמו /los)
        cand = {}  # קרן → [(row, idx, dist, alt)]
        for ri, r in enumerate(rows):  # כל מסלול
            for k, (plat, plon, palt) in enumerate(r["path"]):  # כל נקודה
                d, az = _haversine_az(rd["lat"], rd["lon"], plat, plon)  # מרחק ואזימוט מהמכ"ם
                if d < 1.0 or d > r_max or not _in_sector(az, rd["start"], rd["end"]):  # מחוץ לטווח/לגזרה
                    continue  # לא נראה ע"י המכ"ם הזה
                b = int(round(az / AZ_BIN_DEG)) % int(360 / AZ_BIN_DEG)  # הקרן
                cand.setdefault(b, []).append((ri, k, d, palt))  # לרשימה
        rays = {}  # קרן → רשימת (מרחק, תא)
        uniq = {}  # תאים ייחודיים
        for b, pts in cand.items():  # כל קרן שיש בה נקודות
            far = max(p[2] for p in pts)  # הנקודה הרחוקה בקרן
            az = math.radians(b * AZ_BIN_DEG)  # כיוון הקרן
            samples = []  # הדגימות
            d = TERRAIN_RES_M  # הדגימה הראשונה
            while d <= far:  # עד הנקודה הרחוקה
                lat = rd["lat"] + d * math.cos(az) / M_PER_DEG_LAT  # מיקום (קירוב מקומי)
                lon = rd["lon"] + d * math.sin(az) / (M_PER_DEG_LAT * math.cos(math.radians(rd["lat"])))  # כנ"ל
                c = _terrain_cell(lat, lon, lat_step, lon_step)  # תא משותף (אותה רשת כמו בדיקת הרכס)
                samples.append((d, c))  # נשמר
                uniq[c] = None  # לסט
                d += max(TERRAIN_RES_M, d * RAY_STEP_FRAC)  # מרווח גדל עם המרחק: 150 מ' קרוב, ~0.5% מהמרחק רחוק (אותו דיוק זוויתי, פחות תאים)
            rays[b] = samples  # הקרן
        cells = list(uniq)  # התאים
        tick(stage="visibility", radar=bit, cells=len(cells), note=f"שולף שטח למפת האופק של {rd['name']}: {len(cells)} תאים…")  # התקדמות
        terr = dict(zip(cells, fetch_cells(cells))) if cells else {}  # גבהים (מטמון/רשת)
        seen = 0  # נקודות שהמכ"ם הזה רואה
        for b, pts in cand.items():  # כל קרן
            dists_b = [d for d, _ in rays[b]]  # מרחקי הדגימות (לחיפוש בינארי)
            horizon, hmax = [], -float("inf")  # אופק מצטבר (prefix max) לכל דגימה
            for d, c in rays[b]:  # הדגימות לפי סדר מרחק
                e = terr.get(c)  # גובה
                if e is not None:  # יש נתון
                    drop = d * d / (2 * R_EARTH) * (1 - REFRACTION_K)  # עקמומיות + שבירה
                    hmax = max(hmax, (e - drop - h_obs) / d)  # עדכון האופק (שטח גולמי בלבד)
                horizon.append(hmax)  # האופק עד המרחק הזה
            for ri, k, d, palt in pts:  # כל נקודה בקרן
                j = bisect.bisect_left(dists_b, d) - 1  # הדגימה האחרונה לפני הנקודה (מרווחים לא אחידים)
                hz = horizon[j] if 0 <= j < len(horizon) else -float("inf")  # האופק לפניה
                drop = d * d / (2 * R_EARTH) * (1 - REFRACTION_K)  # עקמומיות + שבירה
                if (palt - drop - h_obs) / d >= hz + margin:  # מעל האופק + מרווח
                    masks[ri][k] |= (1 << bit)  # המכ"ם הזה רואה
                    seen += 1  # ספירה
        stats.append({"name": rd["name"], "points_seen": seen, "cells": len(cells)})  # סיכום למכ"ם
    total = sum(map(len, masks))  # כל הנקודות
    any_seen = sum(1 for m in masks for x in m if x)  # נקודות שמכ"ם כלשהו רואה
    rows_any = sum(1 for m in masks if any(m))  # מסלולים שנצפים בחלקם
    rows_full = sum(1 for m in masks if all(m))  # מסלולים שנצפים במלואם
    return {"masks": masks, "radars": stats,  # המסיכות והסטטיסטיקה
            "summary": {"radars": len(stats), "points": total, "points_seen": any_seen,  # נקודות
                        "trajectories_seen_any": rows_any, "trajectories_seen_full": rows_full,  # מסלולים
                        "trajectories_unseen": len(rows) - rows_any}}  # לא נצפים כלל


# ═══════════════════════ הערכה לפני הרצה ═══════════════════════

SEC_PER_SIM = 0.09  # זמן ממוצע למסלול בסריקה (נמדד: 0.035 נמוך – 0.15 גבוה); מתעדכן בשרת לפי מדידה בפועל
SEC_PER_FETCH_BATCH = 13.5  # שליפת 100 תאים כולל השהיית הקצב של Open-Meteo


def estimate(req, cached_fn=None, workers=1, sec_per_sim=None):  # מספרים והערכת זמן — בלי רשת ובלי בליסטיקה
    """cached_fn(list[(lat,lon)]) -> set של התאים שכבר במטמון (אופציונלי). מחזיר dict עם ספירות, תאים חסרים וזמן משוער."""
    pl = plan(req)  # רשתות
    p, launch, target = pl["parsed"], pl["launch"], pl["target"]  # קיצורים
    tpts = [pt for g in target for pt in g]  # כל נקודות המטרה
    n_qe = int((QE_HI_MILS - QE_LO_MILS) / QE_STEP_MILS) + 1  # דגימות לצומת
    nodes = 0  # צמתים בכל הטבלאות
    for gpts in launch:  # כל אזור שיגור
        azs = [_haversine_az(g[0], g[1], t[0], t[1])[1] for g in (gpts[0], gpts[-1]) for t in (tpts[0], tpts[-1], tpts[len(tpts) // 2])]  # כיוונים מייצגים
        m = math.degrees(math.atan2(sum(math.sin(math.radians(a)) for a in azs), sum(math.cos(math.radians(a)) for a in azs)))  # ממוצע
        d = [_ang_diff(a, m) for a in azs]  # סטיות
        nodes += len(_nodes(min(d), max(d), 20.0, 2.0)) * 2  # צמתי כיוון × 2 (הנחה: הגבהים עוד לא ידועים; באזור הררי יש גם צמתי הפרש גובה וגובה שיגור נוספים)
    pts = [pt for g in launch for pt in g] + tpts  # נקודות האזורים
    cells = set()  # תאי שטח לרכס
    lat_ref = sum(pt[0] for pt in pts) / len(pts)  # רוחב ייחוס
    lat_step = TERRAIN_RES_M / M_PER_DEG_LAT  # צעד רוחב
    lon_step = TERRAIN_RES_M / (M_PER_DEG_LAT * math.cos(math.radians(lat_ref)))  # צעד אורך
    gl = [pt for g in launch for pt in g]  # נקודות השיגור
    if p["crest"]:  # צריך שטח לאורך הקווים
        stride = max(1, int(math.sqrt(len(gl) * len(tpts) / 4000.0)))  # דילול להערכה מהירה באזורים גדולים
        for g in gl[::stride]:  # נקודות שיגור (מדוללות)
            for t in tpts[::stride]:  # נקודות מטרה (מדוללות)
                rng = _haversine_az(g[0], g[1], t[0], t[1])[0]  # טווח
                n = max(2, int(math.ceil(rng / TERRAIN_RES_M)))  # דגימות
                for kk in range(1, n):  # לאורך הקו
                    f = kk / n  # שבר
                    cells.add(_terrain_cell(g[0] + f * (t[0] - g[0]), g[1] + f * (t[1] - g[1]), lat_step, lon_step))  # תא
    all_cells = list(set(pts) | cells)  # נקודות + שטח
    cached = cached_fn(all_cells) if cached_fn else set()  # מה כבר במטמון
    missing = len(all_cells) - len(cached)  # חסרים
    table_s = nodes * n_qe * (sec_per_sim or SEC_PER_SIM) / max(1, workers)  # זמן הטבלאות
    fetch_s = math.ceil(missing / 100.0) * SEC_PER_FETCH_BATCH  # זמן שליפת השטח
    pairs_s = pl["pairs"] * len(p["groups"]) * 0.0004  # זמן הזוגות (אינטרפולציה + רכס)
    return {"launch_points": pl["launch_points"], "target_points": pl["target_points"], "pairs": pl["pairs"],  # גדלים
            "trajectories_max": pl["trajectories_max"], "table_nodes": nodes, "cells": len(all_cells), "cells_missing": missing,  # עבודה
            "eta_s": round(table_s + fetch_s + pairs_s), "eta_parts_s": {"table": round(table_s), "terrain": round(fetch_s), "pairs": round(pairs_s)}}  # זמן
