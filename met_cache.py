# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""מטמון לתחזית מזג האוויר החי (FR-D-299) — משותף ל-Desktop (weather_server) ולאנדרואיד (mpm_api).

תחזית Open-Meteo מכילה 7 ימים של שעות (168), ולכן תשובה אחת מספיקה לשעות רבות קדימה. כל תשובה נשמרת לפי אזור
(עיגול ל-0.1°, ‏~11 ק"מ), ובכל שימוש נבחרת **השעה הקרובה לעכשיו** מתוך הסדרה (Open-Meteo מתחיל תמיד ב-00:00 של היום).
- טרייה (עד שעה): משתמשים בה בלי רשת — חוסך מכסה (בקשה אחת = ‏~8 קריאות, כי יש בה ‏~80 שדות).
- כשהשליפה נכשלת (מכסה/רשת): משתמשים בתחזית השמורה האחרונה לאזור, עד 48 שעות, ומדווחים את הגיל שלה.
- אין תחזית שמורה: שגיאה עם הסבר מה לעשות (אטמוספרה תקנית בהגדרות הכלי הבליסטי).
הקובץ: met_cache.sqlite ליד מטמון הגבהים (מחוץ לריפו). דריסה: MAPS_GUI_MET_CACHE. ספריית התקן בלבד.
"""
import datetime  # בחירת השעה הקרובה לעכשיו (UTC)
import json  # שמירת תשובת Open-Meteo כמו שהיא
import logging  # רישום כשלים (המטמון לא מפיל את הקורא)
import os  # נתיבים ומשתני סביבה
import threading  # נעילה — כמה jobs במקביל
import time  # זמן השליפה של כל רשומה
try:  # sqlite3 בספריית התקן; אם חסר — בלי מטמון, לא קורסים
    import sqlite3  # אחסון קבוע
except ImportError:  # בנייה מצומצמת של פייתון
    sqlite3 = None  # מסמן "בלי מטמון"

FRESH_S = 3600  # תחזית שנשלפה בשעה האחרונה משמשת בלי פנייה לרשת
STALE_MAX_S = 48 * 3600  # כשהשליפה נכשלת: תחזית שמורה עד 48 שעות (הגיל מוצג למשתמש)
NO_CACHE_HINT = "אין תחזית שמורה לאזור הזה. בחר 'אטמוספרה תקנית' בהגדרות הכלי הבליסטי, או נסה שוב מחר"  # הודעה במכסה
NET_HINT = "אין תחזית שמורה לאזור הזה. בדוק את החיבור לרשת, או בחר 'אטמוספרה תקנית' בהגדרות הכלי הבליסטי"  # הודעה בכשל רשת
_lock = threading.Lock()  # גישה בטוחה מכמה threads


def path():  # מיקום קובץ המטמון
    env = os.environ.get("MAPS_GUI_MET_CACHE")  # דריסה מפורשת
    if env:  # הוגדרה
        return env  # כמו שהיא (":memory:" = בלי קובץ קבוע)
    import elev_cache  # אותה תיקייה כמו מטמון הגבהים (כולל הדריסה שלו בבדיקות)
    base = elev_cache.default_path()  # נתיב מטמון הגבהים
    if base == ":memory:":  # מטמון גבהים בזיכרון → גם כאן
        return ":memory:"  # בלי קובץ
    return os.path.join(os.path.dirname(base) or ".", "met_cache.sqlite")  # ליד elev_cache.sqlite


def _key(lat, lon):  # מפתח אזור: עיגול ל-0.1° (רשת המודל של Open-Meteo היא כמה ק"מ — אותו אזור = אותה תחזית)
    return f"{round(float(lat), 1):.1f},{round(float(lon), 1):.1f}"  # מחרוזת יציבה


def _connect():  # חיבור לקובץ ויצירת הטבלה; None אם לא אפשרי
    if sqlite3 is None:  # אין sqlite3
        return None  # בלי מטמון
    p = path()  # הנתיב
    try:
        if p != ":memory:":  # קובץ אמיתי
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)  # יצירת התיקייה
        con = sqlite3.connect(p, timeout=10)  # חיבור קצר לכל פעולה (בלי מצב משותף בין threads)
        con.execute("CREATE TABLE IF NOT EXISTS met (k TEXT PRIMARY KEY, data TEXT NOT NULL, ts INTEGER NOT NULL)")  # אזור, תשובה, זמן שליפה
        return con  # מוכן
    except (OSError, sqlite3.Error) as e:  # דיסק/קובץ פגום
        logging.warning(f"מטמון התחזית לא זמין: {e}")  # אבחון — ממשיכים בלי מטמון
        return None  # בלי מטמון


def get(lat, lon, max_age_s, now=None):  # (data, ts) של התחזית השמורה לאזור, אם היא לא ישנה מ-max_age_s; אחרת (None, None)
    now = time.time() if now is None else now  # זמן נוכחי (ניתן להזרקה בבדיקות)
    with _lock:  # נעילה
        con = _connect()  # חיבור
        if con is None:  # בלי מטמון
            return None, None  # אין
        try:
            row = con.execute("SELECT data, ts FROM met WHERE k=?", (_key(lat, lon),)).fetchone()  # הרשומה
        except sqlite3.Error as e:  # קובץ פגום
            logging.warning(f"קריאת מטמון התחזית נכשלה: {e}")  # אבחון
            row = None  # כאילו אין
        finally:
            con.close()  # סגירה
    if not row or now - row[1] > max_age_s:  # אין, או ישנה מדי
        return None, None  # אין
    try:
        return json.loads(row[0]), row[1]  # התשובה וזמן השליפה
    except ValueError:  # JSON פגום
        return None, None  # כאילו אין


def put(lat, lon, data, now=None):  # שומר תשובה לאזור (מחליף את הקודמת) ומנקה רשומות ישנות מ-48 שעות
    now = int(time.time() if now is None else now)  # זמן השליפה
    with _lock:  # נעילה
        con = _connect()  # חיבור
        if con is None:  # בלי מטמון
            return  # לא שומרים
        try:
            con.execute("INSERT OR REPLACE INTO met (k, data, ts) VALUES (?, ?, ?)", (_key(lat, lon), json.dumps(data), now))  # שמירה
            con.execute("DELETE FROM met WHERE ts < ?", (now - STALE_MAX_S,))  # ניקוי — הקובץ לא גדל בלי סוף
            con.commit()  # כתיבה
        except sqlite3.Error as e:  # כשל כתיבה
            logging.warning(f"שמירת מטמון התחזית נכשלה: {e}")  # אבחון — לא מפילים
        finally:
            con.close()  # סגירה


def pick_index(times, when_iso=None, now=None):  # האינדקס של השעה המבוקשת בסדרה (ברירת מחדל: השעה הקרובה לעכשיו, UTC); None אם אינה בסדרה
    if when_iso:  # שעה מבוקשת במפורש
        target = str(when_iso)[:13]  # "YYYY-MM-DDTHH"
    else:  # עכשיו
        t = datetime.datetime.fromtimestamp(time.time() if now is None else now, datetime.timezone.utc)  # זמן UTC
        t = (t + datetime.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)  # עיגול לשעה הקרובה
        target = t.strftime("%Y-%m-%dT%H")  # אותו פורמט כמו ב-Open-Meteo (timezone=UTC)
    for i, s in enumerate(times or []):  # חיפוש בסדרה
        if str(s)[:13] == target:  # אותה שעה
            return i  # נמצא
    return None  # השעה לא בסדרה (למשל תחזית ישנה מדי)


def fetch(lat, lon, fetch_remote, when_iso=None, now=None):  # (data, index, info, err): מטמון טרי → רשת → מטמון ישן → שגיאה עם הסבר
    """fetch_remote() -> (data, err). data = תשובת Open-Meteo (dict עם hourly.time). info = {"cached", "stale", "age_min"}."""
    now = time.time() if now is None else now  # זמן נוכחי
    data, ts = get(lat, lon, FRESH_S, now)  # 1. טרייה
    if data is not None:  # יש
        idx = pick_index((data.get("hourly") or {}).get("time"), when_iso, now)  # השעה המבוקשת
        if idx is not None:  # השעה בסדרה
            return data, idx, {"cached": True, "stale": False, "age_min": int((now - ts) // 60)}, None  # בלי רשת
    data, err = fetch_remote()  # 2. רשת
    if data is not None:  # הצליח
        idx = pick_index((data.get("hourly") or {}).get("time"), when_iso, now)  # השעה המבוקשת
        if idx is None:  # השעה לא בתשובה — כמו קודם: השעה הראשונה שהוחזרה (למשל when_iso מחוץ לטווח)
            idx = 0  # התנהגות קודמת
        else:  # תשובה תקינה עם השעה
            put(lat, lon, data, now)  # שמירה לשימוש חוזר
        return data, idx, {"cached": False, "stale": False, "age_min": 0}, None  # טרי מהרשת
    old, ts = get(lat, lon, STALE_MAX_S, now)  # 3. תחזית שמורה ישנה יותר
    if old is not None:  # יש
        idx = pick_index((old.get("hourly") or {}).get("time"), when_iso, now)  # השעה המבוקשת מתוכה
        if idx is not None:  # השעה מכוסה
            logging.warning(f"שליפת התחזית נכשלה ({(err or {}).get('error')}) — משתמשים בתחזית שמורה")  # אבחון
            return old, idx, {"cached": True, "stale": True, "age_min": int((now - ts) // 60)}, None  # מהמטמון, עם הגיל
    err = dict(err or {"error": "שליפת התחזית נכשלה"})  # 4. אין חלופה — שגיאה עם הסבר
    hint = NO_CACHE_HINT if err.get("rate_limited") else NET_HINT  # מה לעשות
    err["error"] = f"{err.get('error')} — {hint}"  # ההודעה המלאה
    return None, None, None, err  # כשל


def describe(time_utc, info):  # תיאור המקור לתצוגה, כולל גיל תחזית שמורה
    base = f"Open-Meteo {time_utc} UTC"  # כמו קודם
    if info and info.get("stale"):  # תחזית שמורה בגלל כשל
        return f"{base} (תחזית שמורה מלפני {info['age_min']} דק' — שליפה חדשה נכשלה)"  # אזהרה
    if info and info.get("cached"):  # טרייה מהמטמון
        return f"{base} (שמורה, {info['age_min']} דק')"  # מידע
    return base  # טרייה מהרשת
