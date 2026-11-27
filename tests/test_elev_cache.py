# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""T23 (F-055): בדיקות למטמון הגבהים הקבוע (elev_cache.py). בלי רשת, על קבצים זמניים בלבד.
הרצה: .venv\\Scripts\\python.exe tests/test_elev_cache.py"""
import os  # T23: נתיבים
import sys  # T23: sys.path וקוד יציאה
import tempfile  # T23: תיקייה זמנית לכל בדיקה

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # T23: פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # T23: שורש הפרויקט
sys.path.insert(0, ROOT)  # T23: ייבוא elev_cache
import elev_cache  # noqa: E402  # T23: המודול הנבדק

ok, fail = 0, 0  # T23: מונים


def check(name, cond, info=""):  # T23: רישום תוצאה
    global ok, fail  # T23: המונים
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)  # T23: עדכון
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # T23: פלט


tmp = tempfile.mkdtemp(prefix="elev_cache_test_")  # T23: תיקייה פרטית
path = os.path.join(tmp, "sub", "cache.sqlite")  # T23: גם תיקייה שעוד לא קיימת

c1 = elev_cache.ElevCache(path)  # T23: מטמון חדש
c1.put_many({(31.25, 34.79): 284.0, (31.36, 34.89): 310.5, (31.0, 35.0): None})  # T23: שני ערכים ו-None
check("קובץ נוצר בתיקייה חדשה", os.path.exists(path))  # T23: יצירת תיקייה וקובץ
check("None לא נשמר", c1.count() == 2, f"count={c1.count()}")  # T23: רק ערכים תקינים
c1._db.close()  # T23: סגירה — מדמה סגירת השרת

c2 = elev_cache.ElevCache(path)  # T23: "הפעלה מחדש" — מופע חדש על אותו קובץ
got = c2.get_many([(31.25, 34.79), (31.36, 34.89), (31.0, 35.0), (30.0, 34.0)])  # T23: שניים קיימים, שניים לא
check("שורד הפעלה מחדש", got.get((31.25, 34.79)) == 284.0 and got.get((31.36, 34.89)) == 310.5, str(got))  # T23: הערכים חזרו
check("תאים חסרים לא מוחזרים", (31.0, 35.0) not in got and (30.0, 34.0) not in got)  # T23: רק מה שנשמר
check("מפתח מעוגל: float קרוב מאוד = אותו תא", (31.2500000001, 34.79) in c2.get_many([(31.2500000001, 34.79)]))  # T23: עיגול 6 ספרות
c2.put_many({(31.25, 34.79): 285.0})  # T23: עדכון ערך
check("עדכון ערך קיים (INSERT OR REPLACE)", c2.get_many([(31.25, 34.79)])[(31.25, 34.79)] == 285.0 and c2.count() == 2)  # T23: בלי כפילות
c2._db.close()  # T23: סגירה

bad = os.path.join(tmp, "bad.sqlite")  # T23: קובץ פגום
with open(bad, "wb") as f:  # T23: תוכן שאינו SQLite
    f.write(b"this is not a sqlite database at all" * 50)  # T23: זבל
c3 = elev_cache.ElevCache(bad)  # T23: אמור לא לקרוס
c3.put_many({(1.0, 2.0): 3.0})  # T23: עובד אחרי שחזור
check("קובץ פגום: לא קורס, נוצר חדש ועובד", c3.get_many([(1.0, 2.0)]).get((1.0, 2.0)) == 3.0)  # T23: שחזור
check("קובץ פגום נשמר הצידה (.corrupt-*)", any(n.startswith("bad.sqlite.corrupt-") for n in os.listdir(tmp)))  # T23: לא נמחק
check("אחרי שחזור יש שוב קובץ (לא רק זיכרון)", c3._db is not None)  # T23: השחזור יצר קובץ חדש
if c3._db is not None:  # T23: סגירה רק אם נפתח
    c3._db.close()  # T23: סגירה

c4 = elev_cache.ElevCache(":memory:")  # T23: בלי קובץ
c4.put_many({(5.0, 6.0): 7.0})  # T23: שמירה
check("מצב זיכרון (:memory:) עובד", c4.get_many([(5.0, 6.0)]).get((5.0, 6.0)) == 7.0)  # T23: עובד

saved = elev_cache.sqlite3  # T23: מדמים סביבה בלי sqlite3
elev_cache.sqlite3 = None  # T23: אין sqlite3
c5 = elev_cache.ElevCache(os.path.join(tmp, "nosqlite.sqlite"))  # T23: אמור לעבוד בזיכרון
c5.put_many({(8.0, 9.0): 10.0})  # T23: שמירה
check("בלי sqlite3: זיכרון בלבד, בלי קריסה", c5._db is None and c5.get_many([(8.0, 9.0)]).get((8.0, 9.0)) == 10.0)  # T23: fallback
elev_cache.sqlite3 = saved  # T23: שחזור

os.environ["MAPS_GUI_ELEV_CACHE"] = os.path.join(tmp, "env.sqlite")  # T23: דריסה ממשתנה סביבה
check("default_path מכבד MAPS_GUI_ELEV_CACHE", elev_cache.default_path() == os.path.join(tmp, "env.sqlite"))  # T23: דריסה
del os.environ["MAPS_GUI_ELEV_CACHE"]  # T23: ניקוי
check("default_path מחוץ לריפו", not os.path.abspath(elev_cache.default_path()).startswith(ROOT))  # T23: לא נכנס ל-git

print(f"\n{ok}/{ok + fail} passed")  # T23: סיכום
sys.exit(1 if fail else 0)  # T23: קוד יציאה
