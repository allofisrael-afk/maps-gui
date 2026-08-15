# -*- coding: utf-8 -*-
"""
סיווג NOTAM ל-7 קטגוריות, בהשראת מסך השכבות של אפליקציית DronesIL הרשמית (רשות
התעופה האזרחית) — נבדק ידנית מול קובץ ה-APK שלה (חילוץ סטטי בלבד, ללא הרצה) ולא
נמצא בו מקור נתונים ייעודי לכל קטגוריה; הסיווג שם הוא כנראה client-side על גבי אותו
פיד NOTAM יחיד. המימוש כאן מאמץ את אותו רעיון: NOTAM בודד עשוי להתאים למספר
קטגוריות בו-זמנית (למשל "UAS PROHIBITED" מתאים גם ל-uas וגם ל-prohibited).

חשוב — סמנטיקה: זו עדיין שכבת הימנעות/מודעות, לא "מותר לטוס". הרחבת הסינון
מ"UAS/UAV בלבד" לכל 7 הקטגוריות אומרת ש-NOTAM-ים רלוונטיים נוספים (אזורים
מוגבלים/אסורים/מסוכנים/מסוקים/פיקוח, גם בלי אזכור כטב"ם) ייכללו כעת בשכבה.
"""

import re

# כל קטגוריה: (id פנימי, תווית עברית לתצוגה, צבע רווי ומובחן, רשימת מילות מפתח לחיפוש בטקסט ה-NOTAM)
# הסדר כאן קובע גם את סדר התצוגה בתפריט (מהחמור/הספציפי לכללי)
# הצבעים נבחרו פרושים על גלגל הגוונים (לא גוונים פסטליים קרובים) כדי שיהיו מובחנים בבירור
# זה מזה וגם בולטים על רקע המפה הכהה — תוקן בעקבות משוב שהצבעים הקודמים (Catppuccin
# פסטליים, כולם רוויה נמוכה) היו קשים להבחנה הן מהמפה והן זה מזה.
NOTAM_CATEGORIES = [
    {"id": "prohibited",       "label": "אזורים אסורים לטיסה",        "color": "#e63946", "keywords": ["PROHIBITED"]},
    {"id": "restricted",       "label": "אזורים מוגבלים לטיסה",       "color": "#f4a261", "keywords": ["RESTRICTED"]},
    {"id": "danger",           "label": "אזורים מסוכנים לטיסה",       "color": "#e9c46a", "keywords": ["DANGER"]},
    {"id": "uas",              "label": 'אזורי כלי טיס בלתי מאויש',   "color": "#9b5de5", "keywords": ["UAS", "UAV"]},
    {"id": "heliport_control", "label": "אזורי פיקוח מנחתים",         "color": "#00b4d8", "keywords": ["HELIPORT", "HELIPAD"]},
    {"id": "helicopter",       "label": "אזורי מסוקים",               "color": "#2a9d8f", "keywords": ["HELICOPTER"]},
    {"id": "airport_control",  "label": "אזורי פיקוח שדות תעופה",     "color": "#4361ee", "keywords": ["AERODROME", "AIRPORT", "CTR", "ATZ"]},
]

# מיפוי id -> רשומת הקטגוריה, לנוחות שליפה מהירה (למשל צבע לפי id בזמן ציור)
NOTAM_CATEGORY_BY_ID = {c["id"]: c for c in NOTAM_CATEGORIES}

# regex יחיד לכל קטגוריה, \b כדי שלא יתפוס תת-מחרוזת בתוך מילה אחרת (למשל "AIRPORT" בתוך "SEAPORT")
_CATEGORY_PATTERNS = {
    c["id"]: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in c["keywords"]) + r")\b", re.IGNORECASE)
    for c in NOTAM_CATEGORIES
}

# קטגוריות "משתמעות" — אם הטקסט תואם את המפתח, מוסיפים גם את הערך גם אם המילה עצמה
# לא מופיעה במפורש. כרגע: NOTAM שמזכיר CTR/ATZ/AERODROME (airport_control) הוא תמיד
# גם "מוגבל" (restricted) במובן הרגולטורי — טיסת כטב"ם במרחב מבוקר דורשת אישור נת"א,
# גם כשה-NOTAM הבודד לא כותב את המילה "RESTRICTED" במפורש (הוא רק מתאר אירוע נקודתי
# כמו עגורן/פעילות בתוך ה-CTR). לא "prohibited" — זו קטגוריה חמורה יותר (איסור מוחלט),
# ו-CTR/ATZ הם "דורש אישור", לא "אסור לחלוטין".
_IMPLIED_CATEGORIES = {
    "airport_control": ["restricted"],
}


def classify_notam(text):
    """ מחזיר רשימת id-ים של כל הקטגוריות שהטקסט תואם, כולל קטגוריות משתמעות (עשוי להיות יותר מאחת, או ריק). """
    matched = [cat_id for cat_id, pattern in _CATEGORY_PATTERNS.items() if pattern.search(text)]
    for cat_id in list(matched):
        for implied_id in _IMPLIED_CATEGORIES.get(cat_id, []):
            if implied_id not in matched:
                matched.append(implied_id)
    return matched
