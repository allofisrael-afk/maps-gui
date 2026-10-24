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
    # target='web' מפעיל את ה-controls/CSS הנוספים ב-MAP.py (ר' create_map); api_base='' כי
    # כל קריאות ה-API הן same-origin יחסיות (vercel.json מנתב /weather וכו' לפונקציות המתאימות)
    MAP.create_map(target='web', api_base='')
    generated = os.path.join(_PROJECT_ROOT, 'map.html')  # create_map כותב תמיד לשם הזה בתיקיית העבודה
    dest = os.path.join(PUBLIC_DIR, 'index.html')
    shutil.copyfile(generated, dest)
    print(f"נבנה: {dest}")


if __name__ == "__main__":
    main()
