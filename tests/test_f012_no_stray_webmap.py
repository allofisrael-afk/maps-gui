"""F-012: web/map.html הוא שריד-build לא-בשימוש, tracked בגיט בטעות (ר' MAPS-GUI_SRS.md §3.28).
משחזר ע"י בדיקת-קובץ ישירה - 0 git/רשת."""
import os
import sys

_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')  # Q-6: tests/ - רמה אחת למעלה, לא שתיים
path = os.path.join(_PROJECT_ROOT, 'web', 'map.html')

if os.path.exists(path):
    print(f"[FAIL] F-012 משוחזר: {path} עדיין קיים (שריד-build מיותר, 4949 שורות, לא בשימוש ע\"י שום קוד).")
    sys.exit(1)
else:
    print("[OK] F-012: web/map.html אינו קיים - נוקה.")
    sys.exit(0)
