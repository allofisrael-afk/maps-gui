"""
build_web.py — שלב ה-build שVercel מריץ (ר' buildCommand ב-vercel.json) לפני כל deploy.
קורא ל-MAP.create_map(target='web') ומעתיק את הפלט ל-web/public/index.html — כלומר
map.html *לא* נוצר מחדש כאן, אותה פונקציית-יצירה בדיוק כמו בדסקטופ (MAP.py בשורש
הפרויקט, לא עותק נפרד) — מבטיח שינוי אחד משפיע על שתי הפלטפורמות בלי כפילות קוד.
"""
import os
import shutil
import sys

# מוסיף את שורש הפרויקט (תיקייה אחת מעל web/) ל-sys.path כדי לייבא את MAP.py עצמו —
# גם אם Vercel Root Directory מוגדר ל-web/, הקבצים בשורש עדיין קיימים על הדיסק בזמן ה-build
_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, _PROJECT_ROOT)

import MAP  # noqa: E402 — ייבוא אחרי שינוי sys.path, בכוונה

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')


def main():
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    # באג אמיתי שנמצא בפועל (10/11/2026): create_map(output_path=None) כותב לנתיב היחסי
    # "map.html" - שנפתר לפי ה-cwd של ה-process, לא לפי מיקום הקובץ הזה. ב-Vercel, vercel.json
    # יושב ב-web/ (= Root Directory של הפרויקט ב-Vercel), כך שה-cwd בזמן ה-build הוא web/ -
    # כלומר create_map('web') היה כותב בפועל ל-web/map.html, ואילו השורה למטה המשיכה להעתיק
    # את map.html של השורש (קובץ ישן-ומחויב-ב-git, גרסת-Desktop בלי אף control של web ובלי
    # serversRunning=true) - ה-deploy "הצליח" (לא קרס) אבל הגיש בפועל בניית-Desktop במקום Web.
    # תיקון ראשון (output_path מוחלט) *יצר* באג חדש וחמור יותר: הנתיב המוחלט שנבחר היה בדיוק
    # map.html של השורש - אותו קובץ ש-main.py (Desktop) טוען ישירות ב-startup (QUrl.fromLocalFile,
    # main.py:790) *בלי* לקרוא create_map() מראש. הרצת build_web.py (web) אחרי create_map()
    # (desktop) דרסה את הקובץ שהדסקטופ טוען - main.py שעולה בלי לחיצה על "load map" קיבל בפועל
    # גרסת-web עם fetch-ים יחסיים נגד file://, בלי שרת - כל הכלים נשברים בשקט. התיקון הנכון:
    # web/ קבלת קובץ-ביניים עצמאי משלה, שאינו חופף לשום קובץ ש-Desktop טוען בשום שלב.
    generated = os.path.join(_PROJECT_ROOT, 'web', '_generated_map.html')
    # target='web' מפעיל את ה-controls/CSS הנוספים ב-MAP.py (ר' create_map); api_base='' כי
    # כל קריאות ה-API הן same-origin יחסיות (vercel.json מנתב /weather וכו' לפונקציות המתאימות)
    MAP.create_map(target='web', api_base='', output_path=generated)
    dest = os.path.join(PUBLIC_DIR, 'index.html')
    shutil.copyfile(generated, dest)
    print(f"נבנה: {dest}")


if __name__ == "__main__":
    main()
