"""
שכבת "אזורי פעילות טיסה (NOTAM)" — שולף ומפרש NOTAMs מ-brin.iaa.gov.il (רשות שדות
התעופה), מסונן ל-7 קטגוריות (ר' notam_categories.py — בהשראת מסך השכבות של DronesIL
הרשמית), ומחלץ גיאומטריה (מעגל/פוליגון) וגובה מהטקסט החופשי. NOTAM בודד עשוי להתאים
ליותר מקטגוריה אחת (למשל "UAS PROHIBITED" מתאים גם ל-uas וגם ל-prohibited).

חשוב — סמנטיקה: רשומת "UAS/UAV ACT WILL TAKE PLACE... CLSD FM GND UP TO Xft" מתארת
פעילות רחפנים *מאושרת של מפעיל אחר* שהמרחב האווירי סביבה סגור לתעבורה אחרת עד לגובה
מסוים — זה *לא* "מותר לך לטוס כאן". השכבה מוצגת ככלי הימנעות/מודעות, לא כ"אזור מותר".
נבדק ידנית מול העמוד ב-2026-08-09: brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam
כבר מחזיר את כל הטקסט המלא ב-GET הראשוני (ללא צורך לדמות ASP.NET postback/ViewState).

האתר מוגן ב-WAF (עוגיות __uzm*/F5 ASM) — cache עם TTL מונע סריקה תכופה מדי שעלולה
להיחסם, ובמקביל נותן תמונת מצב "עדכנית מספיק" (NOTAM לא משתנה כל שנייה).
"""
import re  # פרסינג HTML/טקסט חופשי בלי תלות חיצונית — הדף עצמו לא מספק JSON
import time  # מדידת גיל ה-cache

import requests  # שליפת דף ה-NOTAM מרשות שדות התעופה

from icao_glossary import render_hebrew_gloss  # תרגום גס לעברית — ר' icao_glossary.py לאזהרת הבטיחות
from notam_categories import classify_notam  # סיווג NOTAM ל-7 קטגוריות — ר' notam_categories.py

_NOTAM_URL = "https://brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam"  # דף NOTAM ציבורי — לא דורש מפתח API
_REQUEST_TIMEOUT = 20  # שניות — האתר לפעמים איטי בגלל ה-WAF שמגן עליו
_CACHE_TTL_SEC = 20 * 60  # 20 דקות — מספיק "חי" לתמונת מצב, לא מציף את השרת המוגן

# קואורדינטת DMS דחוסה בפורמט NOTAM הסטנדרטי, למשל "305819N0345601E" — 2 ספרות מעלות/2 דקות/2 שניות לרוחב, 3 מעלות ללאורך
_COORD_RE = re.compile(r"(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])")
# תבנית אזור מעגלי, למשל "0.3NM RADIUS CENTERED ON PSN 314643N0350539E"
_RADIUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*NM\s+RADIUS\s+CENTERED\s+ON\s+PSN\s+(\d{6}[NS]\d{7}[EW])", re.IGNORECASE
)
# משפט הגובה — מ"FM" (התחלה: GND או גובה) עד "UP TO ..." ועד לנקודה הבאה בטקסט
_ALT_SENTENCE_RE = re.compile(r"FM\s+(?:GND|[\d,]+\s*FT)\s+UP\s+TO[^.]*", re.IGNORECASE)
_BLOCK_SPLIT_RE = re.compile(r'(?=<div id="divMainInfo_)')  # כל רשומת NOTAM מתחילה ב-div כזה עם מזהה ייחודי
_NOTAM_ID_RE = re.compile(r'class="NotamID">\s*([^<\n]+?)\s*</td>')  # תא הטבלה עם מספר ה-NOTAM (למשל C1711/26)
_LOCATION_RE = re.compile(r'class="Location">\s*([^<\n]+?)\s*</td>')  # תא הטבלה עם קוד ה-ICAO (למשל LLLL)
_MSGTEXT_RE = re.compile(r'class="MsgText">\s*([^<]*?)\s*</td>')  # שורת טקסט אחת מתוך כמה — המסר נחתך לכמה תאים

_cache = {"zones": [], "text_only_count": 0, "fetched_at": 0.0, "error": None}  # cache יחיד בזיכרון התהליך — משותף לכל הבקשות


def _coord_to_latlon(coord_str):
    """ ממיר קואורדינטת DMS דחוסה (למשל '305819N0345601E') לזוג (lat, lon) עשרוני. """
    m = _COORD_RE.fullmatch(coord_str)  # דורש התאמה מלאה — לא רק תת-מחרוזת
    if not m:
        return None  # לא בפורמט הצפוי — הקורא מסנן None בעצמו
    lat_d, lat_m, lat_s, ns, lon_d, lon_m, lon_s, ew = m.groups()  # פירוק מעלות/דקות/שניות + כיוון לכל ציר
    lat = int(lat_d) + int(lat_m) / 60 + int(lat_s) / 3600  # המרת DMS לעשרוני: מעלות + דקות/60 + שניות/3600
    lon = int(lon_d) + int(lon_m) / 60 + int(lon_s) / 3600
    if ns == "S":
        lat = -lat  # דרום = ערך שלילי
    if ew == "W":
        lon = -lon  # מערב = ערך שלילי
    return lat, lon


def _extract_geometry(text):
    """ מזהה מעגל ("X NM RADIUS CENTERED ON PSN ...") או פוליגון (3+ קואורדינטות בטקסט).
    מחזיר dict גיאומטריה או None אם לא נמצאה גיאומטריה ניתנת לזיהוי בטקסט. """
    radius_match = _RADIUS_RE.search(text)  # קודם בודקים אם זה אזור מעגלי — יותר ספציפי מפוליגון
    if radius_match:
        center = _coord_to_latlon(radius_match.group(2))  # קבוצה 2 = הקואורדינטה של המרכז
        if center:
            return {"type": "circle", "center": [center[0], center[1]],
                     "radius_m": float(radius_match.group(1)) * 1852.0}  # המרת NM למטרים (1 NM = 1852 מ')

    coords = [_coord_to_latlon(m.group(0)) for m in _COORD_RE.finditer(text)]  # כל הקואורדינטות שמופיעות בטקסט לפי הסדר
    coords = [c for c in coords if c]  # סינון None (התאמות שנכשלו בהמרה)
    if len(coords) >= 3:  # מתחת ל-3 נקודות אין פוליגון תקין
        return {"type": "polygon", "points": [[lat, lon] for lat, lon in coords]}
    return None  # אין מספיק מידע גיאומטרי בטקסט — הרשומה תיספר כ-text_only


def _extract_altitude_text(text):
    """ מחזיר את משפט הגובה הגולמי מהטקסט (למשל "FM GND UP TO 250M AGL"), או מחרוזת ריקה אם לא נמצא. """
    m = _ALT_SENTENCE_RE.search(text)
    return m.group(0).strip() if m else ""


def _parse_notam_blocks(html):
    """ מפצל את ה-HTML לבלוקים לפי divMainInfo_ (רשומת NOTAM אחת לכל בלוק) ומחלץ
    מכל בלוק: מזהה NOTAM, מיקום ICAO, וטקסט ההודעה המלא (מחובר מכל שורות ה-MsgText). """
    notams = []
    for block in _BLOCK_SPLIT_RE.split(html)[1:]:  # הפריט הראשון הוא prefix ללא רשומה (לפני ה-div הראשון)
        id_match = _NOTAM_ID_RE.search(block)
        loc_match = _LOCATION_RE.search(block)
        if not id_match or not loc_match:
            continue  # בלוק שלא בפורמט הצפוי — מדלגים במקום לזרוק שגיאה
        msg_parts = [m.group(1).strip() for m in _MSGTEXT_RE.finditer(block)]  # כל שורות הטקסט השייכות לרשומה הזו
        full_text = " ".join(p for p in msg_parts if p)  # חיבור לטקסט רציף אחד — כולל הקואורדינטות שנחתכו על פני כמה שורות
        notams.append({"id": id_match.group(1).strip(), "icao": loc_match.group(1).strip(), "text": full_text})
    return notams


def _fetch_and_parse():
    """ מושך את דף ה-NOTAM ומחזיר (zones, text_only_count) — לא נגיש ישירות מבחוץ, רק דרך get_uas_notams עם ה-cache. """
    resp = requests.get(_NOTAM_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=_REQUEST_TIMEOUT)  # UA דפדפן — נדרש כדי לעבור את ה-WAF
    resp.raise_for_status()  # זורק חריגה על קוד שגיאה HTTP — נתפס ב-get_uas_notams
    notams = _parse_notam_blocks(resp.text)

    zones = []
    text_only_count = 0
    for n in notams:
        categories = classify_notam(n["text"])  # התאמה ל-0 או יותר מ-7 הקטגוריות (ר' notam_categories.py)
        if not categories:
            continue  # לא תואם אף קטגוריה רלוונטית — לא נכלל בשכבה (מרחיב את UAS/UAV-בלבד הקודם ל-7 הקטגוריות)
        geometry = _extract_geometry(n["text"])
        if geometry is None:
            text_only_count += 1  # רשומה רלוונטית, אבל בלי גיאומטריה ניתנת לחילוץ מהטקסט
            continue
        altitude_text = _extract_altitude_text(n["text"])
        zones.append({
            "id": n["id"],
            "icao": n["icao"],
            "text": n["text"],
            "altitude_text": altitude_text,
            "geometry": geometry,
            "categories": categories,  # רשימת id-ים — שימוש בסינון/צביעה לפי קטגוריה בצד הלקוח
            "hebrew_gloss": render_hebrew_gloss(n["text"]),  # תרגום גס — תמיד לצד המקור האנגלי, לא במקומו
            "altitude_gloss": render_hebrew_gloss(altitude_text),
        })
    return zones, text_only_count


def get_uas_notams(force_refresh=False):
    """ מחזיר (zones, text_only_count, fetched_at, error) — עם cache בזיכרון ל-_CACHE_TTL_SEC.
    בכשל רשת/פרסינג מחזיר את ה-cache הישן (אם יש) עם error מוגדר, ולא זורק חריגה — כדי
    שקריאה ל-endpoint לא תיפול סתם כי האתר הממשלתי המוגן זמנית לא זמין. """
    age = time.time() - _cache["fetched_at"]  # 0 בפעם הראשונה (fetched_at=0.0) — age יהיה עצום, אז נכשל לתנאי ה-cache ממילא
    if not force_refresh and _cache["fetched_at"] and age < _CACHE_TTL_SEC:  # יש cache תקף שעדיין לא פג
        return _cache["zones"], _cache["text_only_count"], _cache["fetched_at"], None

    try:
        zones, text_only_count = _fetch_and_parse()  # שליפה חיה — עלול לקחת כמה שניות בגלל ה-WAF
        _cache.update(zones=zones, text_only_count=text_only_count, fetched_at=time.time(), error=None)  # עדכון ה-cache לניסיון הבא
        return zones, text_only_count, _cache["fetched_at"], None
    except (requests.exceptions.RequestException, re.error) as e:
        _cache["error"] = str(e)  # נשמר לתצוגה, אבל לא מוחק את הנתונים הישנים ב-cache
        return _cache["zones"], _cache["text_only_count"], _cache["fetched_at"], str(e)  # מחזירים cache ישן + הודעת השגיאה
