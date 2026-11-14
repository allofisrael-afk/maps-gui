"""F-013 (תוקן ל-false-positive, 11/11/2026): הבדיקה המקורית חיפשה את המחרוזת המדויקת
'OpenStreetMap contributors' (בלי תג-HTML בין המילים) - אבל הטקסט האמיתי ב-MAP.py הוא
'OpenStreetMap</a> contributors' (יש קישור <a> שבור את הרצף). Leaflet מציג ייחוס-ODbL
תקין בפועל דרך בקרת-ה-attribution המובנית שלו (attributionControl לא מבוטל, וכל 3 שכבות
ה-tile מגדירות attribution תקין) - אומת ב-render חי (QWebEngineView): הבקרה מוצגת,
מכילה "OpenStreetMap" + "OpenTopoMap", ו-visible=true. בדיקה זו מוודאת שהמנגנון הזה
לא נשבר (לא שהמחרוזת-המדויקת-הלא-נכונה קיימת)."""
import os
import sys

_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')  # Q-6: tests/ - רמה אחת למעלה, לא שתיים
path = os.path.join(_PROJECT_ROOT, 'MAP.py')
content = open(path, encoding='utf-8').read()

# בודק שה-tile layers עדיין מגדירים attribution הכולל "OpenStreetMap" (עם או בלי תג-HTML
# ביניים), ושאין קוד שמבטל את בקרת-הייחוס המובנית של Leaflet (attributionControl: false).
has_osm_credit = "OpenStreetMap" in content and "attribution:" in content
attribution_disabled = "attributionControl" in content and "false" in content.split("attributionControl")[1][:30]

if has_osm_credit and not attribution_disabled:
    print("[OK] F-013: תבנית-הייחוס תקינה (tile layers מגדירים attribution, attributionControl לא מבוטל). "
          "false-positive מתוקן - אומת ב-render חי שהבקרה אכן מוצגת (ר' MAPS-GUI_SRS.md).")
    sys.exit(0)
else:
    print("[FAIL] F-013: תבנית-הייחוס נשברה - חסר 'OpenStreetMap' בהגדרת-tile, או attributionControl בוטל.")
    sys.exit(1)
