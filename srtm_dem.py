# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""גבהים מקומיים מ-SRTM (משבצות "skadi" של AWS Terrain Tiles) — משותף ל-Desktop (weather_server) ולאנדרואיד (radar_android, mpm_api).

למה: מכסת Open-Meteo היומית (10,000 קריאות) נגמרה פעמיים ב-27/11/2026 ועצרה חישובים. משבצות SRTM נשמרות במחשב/במכשיר,
ומרגע שירדו — בלי רשת ובלי מכסה. Open-Meteo נשאר לנקודות בלי ערך ("חורים") ומחוץ לכיסוי SRTM.

מקור ורישיון (אומת 27/11/2026 ממקור ראשוני — ר' docs/DEPENDENCIES.md):
- AWS Registry of Open Data, "Terrain Tiles": https://registry.opendata.aws/terrain-tiles/ — גישה אנונימית, בלי חשבון.
- פורמט skadi: "SRTMGL1 format tiles ... compressed using gzip" (tilezen/joerd docs/formats.md) — int16 big-endian, שורות מצפון לדרום,
  ‎-32768 = חור. לאזורנו המקור הוא SRTM של USGS, נחלת הכלל; ייחוס נדרש: "SRTM data courtesy of the U.S. Geological Survey".
- כתובת משבצת: https://elevation-tiles-prod.s3.amazonaws.com/skadi/N31/N31E034.hgt.gz (‎~7MB דחוס, ‎~26MB פרוס).

שימוש: lookup([(lat, lon), ...]) -> [elev | None, ...]. None = אין ערך מקומי (חור, מחוץ לכיסוי, כשל הורדה) — הקורא פונה ל-Open-Meteo.
כיבוי: MAPS_GUI_DEM=off (הבדיקות האוטומטיות משתמשות בזה). תיקייה: MAPS_GUI_DEM_DIR, אחרת ליד מטמון הגבהים (מחוץ לריפו).
"""
import gzip  # פריסת המשבצת (ספריית התקן)
import logging  # רישום הורדות וכשלים
import math  # floor ובדיקת סופיות
import mmap  # קריאה אקראית מהקובץ בלי לטעון 26MB לזיכרון
import os  # נתיבים ומשתני סביבה
import threading  # נעילה — הורדה אחת לכל משבצת גם מכמה threads
import time  # זמן כשל אחרון (כדי לא להציף את השרת בניסיונות)
import urllib.error  # שגיאות HTTP/רשת
import urllib.request  # ההורדה (ספריית התקן — בלי תלות חדשה, עובד גם ב-Chaquopy)

BASE_URL = "https://elevation-tiles-prod.s3.amazonaws.com/skadi"  # דלי ה-AWS הציבורי (us-east-1)
LAT_MIN, LAT_MAX = -56.0, 60.0  # כיסוי SRTM — מחוץ לזה לא מבקשים בכלל
VOID = -32768  # ערך "חור" בפורמט HGT
RETRY_AFTER_S = 600  # אחרי כשל רשת — לא מנסים את אותה משבצת שוב לפני 10 דקות
_SIZES = {3601 * 3601 * 2: 3601, 1201 * 1201 * 2: 1201}  # גודל קובץ → מספר דגימות לצלע (1" או 3")

_lock = threading.Lock()  # מגן על המפות למטה
_tile_locks = {}  # נעילה לכל משבצת — שני threads לא מורידים את אותה משבצת במקביל
_open = {}  # משבצת → (mmap, N) פתוחים לקריאה
_failed = {}  # משבצת → זמן הכשל האחרון


def enabled():  # האם להשתמש בגבהים מקומיים (ברירת מחדל: כן)
    return os.environ.get("MAPS_GUI_DEM", "on").strip().lower() not in ("off", "0", "false", "no")  # כיבוי מפורש בלבד


def tiles_dir():  # תיקיית המשבצות — מחוץ לריפו
    env = os.environ.get("MAPS_GUI_DEM_DIR")  # דריסה מפורשת
    if env:  # הוגדרה
        return env  # כמו שהיא
    import elev_cache  # ייבוא מקומי — אותה תיקיית בסיס כמו מטמון הגבהים
    return os.path.join(os.path.dirname(elev_cache.default_path()) or ".", "srtm")  # %LOCALAPPDATA%\maps-gui\srtm או ~/.maps-gui/srtm


def tile_name(lat, lon):  # שם המשבצת לפי הפינה הדרום-מערבית, למשל N31E034
    la, lo = int(math.floor(lat)), int(math.floor(lon))  # הפינה
    return f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"  # הפורמט של SRTM


def _download(name, path):  # מוריד ופורס משבצת. True = יש קובץ, False = אין משבצת (ים/מחוץ לכיסוי), None = כשל רשת
    url = f"{BASE_URL}/{name[:3]}/{name}.hgt.gz"  # הכתובת
    if not url.startswith("https://"):  # הגנה לעומק (כמו F-016) — רק https
        raise ValueError("scheme לא מאובטח")  # לא אמור לקרות
    tmp = path + ".part"  # קובץ זמני — קובץ חלקי לא נראה כמשבצת תקינה
    try:
        with urllib.request.urlopen(url, timeout=60) as r:  # nosec B310 — ה-scheme אומת למעלה
            raw = r.read()  # ‎~7MB
        data = gzip.decompress(raw)  # ‎~26MB
        if len(data) not in _SIZES:  # גודל לא צפוי — לא שומרים
            logging.warning(f"SRTM {name}: גודל לא צפוי ({len(data)})")  # אבחון
            return None  # כשל
        os.makedirs(os.path.dirname(path), exist_ok=True)  # התיקייה
        with open(tmp, "wb") as f:  # כתיבה לזמני
            f.write(data)  # התוכן
        os.replace(tmp, path)  # החלפה אטומית
        logging.info(f"SRTM: ירדה משבצת {name} ({len(raw) // 1024}KB)")  # רישום
        return True  # יש קובץ
    except urllib.error.HTTPError as e:  # שגיאת HTTP
        if e.code in (403, 404):  # אין משבצת כזו (ים) — מסמנים כדי לא לבקש שוב
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)  # התיקייה
                open(path[:-4] + ".none", "w").close()  # סימון "אין משבצת"
            except OSError:  # לא הצליח לסמן — לא נורא
                pass  # ממשיכים
            return False  # אין משבצת
        logging.warning(f"SRTM {name}: HTTP {e.code}")  # אחר
        return None  # כשל
    except (urllib.error.URLError, OSError, EOFError, ValueError) as e:  # רשת / דחיסה פגומה / דיסק
        logging.warning(f"SRTM {name}: הורדה נכשלה: {e}")  # אבחון
        return None  # כשל
    finally:
        if os.path.exists(tmp):  # נשאר זמני
            try:
                os.remove(tmp)  # ניקוי
            except OSError:  # לא נורא
                pass  # ממשיכים


def _tile(name, allow_download=True):  # (mmap, N) למשבצת, או None אם אין
    with _lock:  # בדיקה מהירה
        if name in _open:  # כבר פתוחה
            return _open[name]  # היא
        if time.time() - _failed.get(name, 0) < RETRY_AFTER_S:  # נכשלה לאחרונה
            return None  # לא מנסים עכשיו
        tl = _tile_locks.setdefault(name, threading.Lock())  # נעילה למשבצת
    with tl:  # הורדה אחת לכל משבצת
        with _lock:  # אולי thread אחר כבר פתח בינתיים
            if name in _open:  # כן
                return _open[name]  # היא
        d = tiles_dir()  # התיקייה
        path = os.path.join(d, name + ".hgt")  # הקובץ הפרוס
        if os.path.exists(os.path.join(d, name + ".none")):  # ידוע שאין משבצת
            return None  # אין
        if not os.path.exists(path):  # צריך להוריד
            if not allow_download:  # הורדה לא מותרת
                return None  # אין
            ok = _download(name, path)  # ההורדה
            if ok is None:  # כשל רשת
                with _lock:  # רישום הכשל
                    _failed[name] = time.time()  # לא לנסות שוב מיד
                return None  # אין
            if ok is False:  # אין משבצת
                return None  # אין
        try:
            size = os.path.getsize(path)  # הגודל
            n = _SIZES.get(size)  # מספר הדגימות
            if n is None:  # קובץ פגום
                os.remove(path)  # מוחקים — יירד מחדש בפעם הבאה
                return None  # אין
            f = open(path, "rb")  # פתיחה לקריאה
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)  # מיפוי לזיכרון (קריאה בלבד)
            f.close()  # ה-mmap מחזיק את הקובץ בעצמו
        except (OSError, ValueError) as e:  # כשל קריאה
            logging.warning(f"SRTM {name}: קריאה נכשלה: {e}")  # אבחון
            return None  # אין
        with _lock:  # שמירה
            _open[name] = (mm, n)  # פתוחה
        return mm, n  # המשבצת


def _sample(mm, n, r, c):  # ערך דגימה בשורה r ועמודה c (או None לחור)
    i = 2 * (r * n + c)  # המיקום בבתים
    v = int.from_bytes(mm[i:i + 2], "big", signed=True)  # int16 big-endian
    return None if v == VOID else v  # חור = None


DEPRESSION_BOX = (30.8, 33.0, 35.25, 35.75)  # בקעת ים המלח, הירדן והכנרת (רוחב מ-עד, אורך מ-עד) — שם גובה שלילי הוא פני שטח אמיתיים
DEPRESSION_FLOOR = -440.0  # הנקודה הנמוכה ביבשה (חוף ים המלח, ‎~-430) — עמוק מזה זו בטימטריה


def _real_depression(lat, lon, v):  # האם ערך שלילי הוא פני שטח אמיתיים (ולא עומק ים)
    la0, la1, lo0, lo1 = DEPRESSION_BOX  # הגבולות
    return la0 <= lat <= la1 and lo0 <= lon <= lo1 and v >= DEPRESSION_FLOOR  # בתוך הבקעה ולא עמוק מהיבשה הנמוכה בעולם


def elevation(lat, lon, allow_download=True):  # גובה בנקודה (בילינארי), או None
    if not (math.isfinite(lat) and math.isfinite(lon)) or not (LAT_MIN <= lat < LAT_MAX) or not (-180.0 <= lon < 180.0):  # מחוץ לכיסוי
        return None  # אין
    t = _tile(tile_name(lat, lon), allow_download)  # המשבצת
    if t is None:  # אין
        return None  # אין
    mm, n = t  # המיפוי ומספר הדגימות
    la0, lo0 = math.floor(lat), math.floor(lon)  # הפינה הדרום-מערבית
    y = (la0 + 1 - lat) * (n - 1)  # שורה עשרונית (0 = צפון)
    x = (lon - lo0) * (n - 1)  # עמודה עשרונית (0 = מערב)
    r0, c0 = min(n - 2, int(y)), min(n - 2, int(x))  # התא
    fy, fx = y - r0, x - c0  # המיקום בתוך התא
    v00, v01 = _sample(mm, n, r0, c0), _sample(mm, n, r0, c0 + 1)  # שתי הפינות העליונות
    v10, v11 = _sample(mm, n, r0 + 1, c0), _sample(mm, n, r0 + 1, c0 + 1)  # שתי התחתונות
    if None in (v00, v01, v10, v11):  # חור באחת הפינות — לא מנחשים
        return None  # Open-Meteo ישלים
    if min(v00, v01, v10, v11) < 0 and not _real_depression(lat, lon, min(v00, v01, v10, v11)):  # ערך שלילי מחוץ לבקעה = עומק ים (skadi ממלא ים בבטימטריה), לא פני שטח
        return None  # Open-Meteo ישלים (פני הים = 0); אחרת הים "נעלם" ולא חוסם קווי ראייה
    top = v00 + fx * (v01 - v00)  # אינטרפולציה בשורה העליונה
    bot = v10 + fx * (v11 - v10)  # בשורה התחתונה
    return round(top + fy * (bot - top), 1)  # בין השורות, בעשירית מטר


def lookup(points, allow_download=True):  # [(lat, lon)] → [elev | None]; כבוי = כולם None
    if not enabled():  # כבוי (בדיקות / בחירת משתמש)
        return [None] * len(points)  # הכול ל-Open-Meteo
    out = []  # התוצאה
    for lat, lon in points:  # כל נקודה
        try:
            out.append(elevation(float(lat), float(lon), allow_download))  # הגובה
        except (TypeError, ValueError):  # נקודה לא מספרית
            out.append(None)  # אין
    return out  # הרשימה


def merge(points, fetch_missing):  # גבהים מקומיים, והשלמת החסרים דרך fetch_missing(list[(lat,lon)]) -> list[elev|None]
    local = lookup(points)  # מקומי
    missing = [i for i, v in enumerate(local) if v is None]  # מה חסר
    if not missing:  # הכול מקומי — בלי רשת ובלי מכסה
        return local  # התוצאה
    got = fetch_missing([points[i] for i in missing])  # השלמה (Open-Meteo)
    for i, v in zip(missing, got or []):  # מיזוג
        local[i] = v  # הערך
    return local  # התוצאה
