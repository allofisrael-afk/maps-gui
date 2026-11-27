# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""T23 (F-055): מטמון גבהים קבוע — משותף ל-Desktop (weather_server) ולאנדרואיד (radar_android).

גובה קרקע לא משתנה, ולכן כל גובה שנשלף מ-Open-Meteo נשמר לצמיתות בקובץ SQLite מקומי (ספריית התקן של פייתון,
בלי תלות חדשה). הרצה חוזרת באותו אזור — גם אחרי הפעלה מחדש של השרת או האפליקציה — לא שולפת שוב, וכך נחסכת
המכסה היומית והמתנות של דקות.
- שכבה 1: מילון בזיכרון (מהיר). שכבה 2: הקובץ.
- קובץ פגום מועבר הצידה (‎.corrupt-<זמן>) ונוצר חדש — השרת לא נופל. אם אי אפשר לכתוב לדיסק, עובדים בזיכרון בלבד.
- כל רשומה נשמרת עם זמן השליפה (ts), לאבחון.
- מיקום ברירת המחדל: משתנה הסביבה MAPS_GUI_ELEV_CACHE; אחרת %LOCALAPPDATA%\\maps-gui\\ ב-Windows,
  או ‎~/.maps-gui/‎ (באנדרואיד HOME הוא תיקיית הקבצים הפרטית של האפליקציה). הקובץ מחוץ לריפו.
"""
import logging  # T23: רישום כשלים במטמון (לא מפילים את הקורא)
import os  # T23: נתיבים ומשתני סביבה
try:  # T23: sqlite3 הוא חלק מספריית התקן, אבל אם הוא חסר (בנייה מצומצמת של פייתון) — עובדים בזיכרון בלבד, לא קורסים
    import sqlite3  # T23: אחסון קבוע
except ImportError:  # T23: אין sqlite3
    sqlite3 = None  # T23: מסמן "זיכרון בלבד"
import threading  # T23: נעילה — כמה jobs במקביל
import time  # T23: זמן השליפה לכל רשומה

_CHUNK = 500  # T23: כמה מפתחות בשאילתת IN אחת (מתחת למגבלת המשתנים של SQLite)


def default_path():  # T23: מיקום קובץ המטמון לפי סביבה
    env = os.environ.get("MAPS_GUI_ELEV_CACHE")  # T23: דריסה מפורשת (בדיקות, התקנה מיוחדת)
    if env:  # T23: הוגדר
        return env  # T23: כמו שהוא (":memory:" = בלי קובץ)
    base = os.environ.get("LOCALAPPDATA")  # T23: Windows — תיקיית נתונים מקומית של המשתמש
    if base:  # T23: Windows
        return os.path.join(base, "maps-gui", "elev_cache.sqlite")  # T23: מחוץ לריפו
    return os.path.join(os.path.expanduser("~"), ".maps-gui", "elev_cache.sqlite")  # T23: אנדרואיד/לינוקס


def _key(cell):  # T23: מפתח יציב לתא (lat, lon) — עיגול ל-6 ספרות (~10 ס"מ), כדי ש-float זהה יתן אותו מפתח
    return f"{float(cell[0]):.6f},{float(cell[1]):.6f}"  # T23: מחרוזת


class ElevCache:  # T23: מטמון דו-שכבתי: זיכרון + SQLite
    def __init__(self, path=None, mem_max=200000):  # T23: path=None → default_path()
        self.path = default_path() if path is None else path  # T23: נתיב הקובץ
        self.mem_max = mem_max  # T23: תקרת המילון בזיכרון (מעבר לה הוא מתאפס; הקובץ נשאר)
        self._mem = {}  # T23: שכבה 1
        self._lock = threading.Lock()  # T23: גישה בטוחה מכמה threads
        self._db = None  # T23: חיבור SQLite (None = זיכרון בלבד)
        self._open()  # T23: פתיחה/יצירה

    def _connect(self):  # T23: פותח את הקובץ ומוודא את מבנה הטבלה
        if self.path != ":memory:":  # T23: קובץ אמיתי
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)  # T23: יצירת התיקייה
        con = sqlite3.connect(self.path, check_same_thread=False, timeout=10)  # T23: חיבור אחד, מוגן בנעילה שלנו
        try:
            con.execute("CREATE TABLE IF NOT EXISTS elev (k TEXT PRIMARY KEY, e REAL NOT NULL, ts INTEGER NOT NULL)")  # T23: מפתח, גובה, זמן
            con.execute("SELECT COUNT(*) FROM elev").fetchone()  # T23: בדיקת תקינות — קובץ פגום נכשל כאן
            con.commit()  # T23: שמירת יצירת הטבלה
        except sqlite3.Error:  # T23: קובץ פגום — סוגרים את החיבור, אחרת ב-Windows אי אפשר להעביר את הקובץ הצידה
            con.close()  # T23: משחרר את נעילת הקובץ
            raise  # T23: _open מטפל (העברה הצידה ויצירה מחדש)
        return con  # T23: מוכן

    def _open(self):  # T23: פתיחה עמידה — קובץ פגום מוחלף, דיסק לא זמין = זיכרון בלבד
        if sqlite3 is None:  # T23: אין sqlite3 בסביבה הזו
            return  # T23: self._db נשאר None — זיכרון בלבד
        try:
            self._db = self._connect()  # T23: ניסיון רגיל
        except sqlite3.DatabaseError as e:  # T23: הקובץ פגום
            logging.warning(f"מטמון הגבהים פגום ({e}) — מועבר הצידה ונוצר חדש")  # T23: אבחון
            try:
                os.replace(self.path, f"{self.path}.corrupt-{int(time.time())}")  # T23: שומרים את הפגום לבדיקה, לא מוחקים
                self._db = self._connect()  # T23: קובץ חדש
            except (OSError, sqlite3.DatabaseError) as e2:  # T23: גם זה נכשל
                logging.error(f"מטמון הגבהים לא זמין, עובדים בזיכרון בלבד: {e2}")  # T23: אבחון
                self._db = None  # T23: זיכרון בלבד
        except OSError as e:  # T23: אין הרשאה/דיסק
            logging.error(f"מטמון הגבהים לא זמין, עובדים בזיכרון בלבד: {e}")  # T23: אבחון
            self._db = None  # T23: זיכרון בלבד

    def get_many(self, cells):  # T23: מחזיר {cell: elev} לתאים שבמטמון (שכבה 1, ואז הקובץ)
        found, missing = {}, []  # T23: נמצאו / לחפש בקובץ
        with self._lock:  # T23: נעילה
            for c in cells:  # T23: כל תא
                k = _key(c)  # T23: המפתח
                if k in self._mem:  # T23: בזיכרון
                    found[c] = self._mem[k]  # T23: מהזיכרון
                else:  # T23: אולי בקובץ
                    missing.append((k, c))  # T23: לשאילתה
            if missing and self._db is not None:  # T23: יש קובץ
                try:
                    for s in range(0, len(missing), _CHUNK):  # T23: בחלקים
                        part = missing[s:s + _CHUNK]  # T23: החלק
                        by_key = {k: c for k, c in part}  # T23: מפתח → תא
                        q = "SELECT k, e FROM elev WHERE k IN (%s)" % ",".join("?" * len(part))  # T23: שאילתה עם פרמטרים (לא שרשור ערכים)
                        for k, e in self._db.execute(q, [k for k, _ in part]):  # T23: התוצאות
                            found[by_key[k]] = e  # T23: לתוצאה
                            self._mem[k] = e  # T23: לשכבה 1
                except sqlite3.Error as e:  # T23: כשל קריאה — ממשיכים בלי הקובץ
                    logging.error(f"קריאה ממטמון הגבהים נכשלה: {e}")  # T23: אבחון
        return found  # T23: מה שנמצא

    def put_many(self, mapping):  # T23: שומר {cell: elev}; ערכי None לא נשמרים
        rows = [(_key(c), float(e), int(time.time())) for c, e in mapping.items() if e is not None]  # T23: רק ערכים תקינים
        if not rows:  # T23: אין מה לשמור
            return  # T23: יציאה
        with self._lock:  # T23: נעילה
            if len(self._mem) > self.mem_max:  # T23: תקרת זיכרון
                self._mem.clear()  # T23: הקובץ עדיין מחזיק הכול
            for k, e, _ in rows:  # T23: שכבה 1
                self._mem[k] = e  # T23: עדכון
            if self._db is not None:  # T23: שכבה 2
                try:
                    self._db.executemany("INSERT OR REPLACE INTO elev (k, e, ts) VALUES (?, ?, ?)", rows)  # T23: הוספה/עדכון
                    self._db.commit()  # T23: נשמר לדיסק
                except sqlite3.Error as e:  # T23: כשל כתיבה — הזיכרון עדיין עובד
                    logging.error(f"כתיבה למטמון הגבהים נכשלה: {e}")  # T23: אבחון

    def count(self):  # T23: מספר הרשומות בקובץ (או בזיכרון אם אין קובץ) — לאבחון ולבדיקות
        with self._lock:  # T23: נעילה
            if self._db is None:  # T23: זיכרון בלבד
                return len(self._mem)  # T23: גודל המילון
            try:
                return self._db.execute("SELECT COUNT(*) FROM elev").fetchone()[0]  # T23: ספירה
            except sqlite3.Error:  # T23: כשל
                return len(self._mem)  # T23: הערכה
