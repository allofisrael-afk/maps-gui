"""
שכבת "אזורי פעילות רחפנים (NOTAM)" — שולף ומפרש NOTAMs מ-brin.iaa.gov.il (רשות שדות
התעופה), מסונן לרשומות UAS/UAV בלבד, ומחלץ גיאומטריה (מעגל/פוליגון) וגובה מהטקסט החופשי.

חשוב — סמנטיקה: רשומת "UAS/UAV ACT WILL TAKE PLACE... CLSD FM GND UP TO Xft" מתארת
פעילות רחפנים *מאושרת של מפעיל אחר* שהמרחב האווירי סביבה סגור לתעבורה אחרת עד לגובה
מסוים — זה *לא* "מותר לך לטוס כאן". השכבה מוצגת ככלי הימנעות/מודעות, לא כ"אזור מותר".
נבדק ידנית מול העמוד ב-2026-08-09: brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam
כבר מחזיר את כל הטקסט המלא ב-GET הראשוני (ללא צורך לדמות ASP.NET postback/ViewState).

האתר מוגן ב-WAF (עוגיות __uzm*/F5 ASM) — cache עם TTL מונע סריקה תכופה מדי שעלולה
להיחסם, ובמקביל נותן תמונת מצב "עדכנית מספיק" (NOTAM לא משתנה כל שנייה).
"""
import re
import time

import requests

_NOTAM_URL = "https://brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam"
_REQUEST_TIMEOUT = 20
_CACHE_TTL_SEC = 20 * 60  # 20 דקות — מספיק "חי" לתמונת מצב, לא מציף את השרת המוגן

_COORD_RE = re.compile(r"(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])")
_RADIUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*NM\s+RADIUS\s+CENTERED\s+ON\s+PSN\s+(\d{6}[NS]\d{7}[EW])", re.IGNORECASE
)
_ALT_SENTENCE_RE = re.compile(r"FM\s+(?:GND|[\d,]+\s*FT)\s+UP\s+TO[^.]*", re.IGNORECASE)
_BLOCK_SPLIT_RE = re.compile(r'(?=<div id="divMainInfo_)')
_NOTAM_ID_RE = re.compile(r'class="NotamID">\s*([^<\n]+?)\s*</td>')
_LOCATION_RE = re.compile(r'class="Location">\s*([^<\n]+?)\s*</td>')
_MSGTEXT_RE = re.compile(r'class="MsgText">\s*([^<]*?)\s*</td>')

_cache = {"zones": [], "text_only_count": 0, "fetched_at": 0.0, "error": None}


def _coord_to_latlon(coord_str):
    """ ממיר קואורדינטת DMS דחוסה (למשל '305819N0345601E') לזוג (lat, lon) עשרוני. """
    m = _COORD_RE.fullmatch(coord_str)
    if not m:
        return None
    lat_d, lat_m, lat_s, ns, lon_d, lon_m, lon_s, ew = m.groups()
    lat = int(lat_d) + int(lat_m) / 60 + int(lat_s) / 3600
    lon = int(lon_d) + int(lon_m) / 60 + int(lon_s) / 3600
    if ns == "S":
        lat = -lat
    if ew == "W":
        lon = -lon
    return lat, lon


def _extract_geometry(text):
    """ מזהה מעגל ("X NM RADIUS CENTERED ON PSN ...") או פוליגון (3+ קואורדינטות בטקסט).
    מחזיר dict גיאומטריה או None אם לא נמצאה גיאומטריה ניתנת לזיהוי בטקסט. """
    radius_match = _RADIUS_RE.search(text)
    if radius_match:
        center = _coord_to_latlon(radius_match.group(2))
        if center:
            return {"type": "circle", "center": [center[0], center[1]],
                     "radius_m": float(radius_match.group(1)) * 1852.0}

    coords = [_coord_to_latlon(m.group(0)) for m in _COORD_RE.finditer(text)]
    coords = [c for c in coords if c]
    if len(coords) >= 3:
        return {"type": "polygon", "points": [[lat, lon] for lat, lon in coords]}
    return None


def _extract_altitude_text(text):
    m = _ALT_SENTENCE_RE.search(text)
    return m.group(0).strip() if m else ""


def _parse_notam_blocks(html):
    """ מפצל את ה-HTML לבלוקים לפי divMainInfo_ (רשומת NOTAM אחת לכל בלוק) ומחלץ
    מכל בלוק: מזהה NOTAM, מיקום ICAO, וטקסט ההודעה המלא (מחובר מכל שורות ה-MsgText). """
    notams = []
    for block in _BLOCK_SPLIT_RE.split(html)[1:]:  # הפריט הראשון הוא prefix ללא רשומה
        id_match = _NOTAM_ID_RE.search(block)
        loc_match = _LOCATION_RE.search(block)
        if not id_match or not loc_match:
            continue
        msg_parts = [m.group(1).strip() for m in _MSGTEXT_RE.finditer(block)]
        full_text = " ".join(p for p in msg_parts if p)
        notams.append({"id": id_match.group(1).strip(), "icao": loc_match.group(1).strip(), "text": full_text})
    return notams


def _fetch_and_parse():
    resp = requests.get(_NOTAM_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    notams = _parse_notam_blocks(resp.text)

    zones = []
    text_only_count = 0
    for n in notams:
        if "UAS" not in n["text"] and "UAV" not in n["text"]:
            continue
        geometry = _extract_geometry(n["text"])
        if geometry is None:
            text_only_count += 1
            continue
        zones.append({
            "id": n["id"],
            "icao": n["icao"],
            "text": n["text"],
            "altitude_text": _extract_altitude_text(n["text"]),
            "geometry": geometry,
        })
    return zones, text_only_count


def get_uas_notams(force_refresh=False):
    """ מחזיר (zones, text_only_count, fetched_at, error) — עם cache בזיכרון ל-_CACHE_TTL_SEC.
    בכשל רשת/פרסינג מחזיר את ה-cache הישן (אם יש) עם error מוגדר, ולא זורק חריגה — כדי
    שקריאה ל-endpoint לא תיפול סתם כי האתר הממשלתי המוגן זמנית לא זמין. """
    age = time.time() - _cache["fetched_at"]
    if not force_refresh and _cache["fetched_at"] and age < _CACHE_TTL_SEC:
        return _cache["zones"], _cache["text_only_count"], _cache["fetched_at"], None

    try:
        zones, text_only_count = _fetch_and_parse()
        _cache.update(zones=zones, text_only_count=text_only_count, fetched_at=time.time(), error=None)
        return zones, text_only_count, _cache["fetched_at"], None
    except (requests.exceptions.RequestException, re.error) as e:
        _cache["error"] = str(e)
        return _cache["zones"], _cache["text_only_count"], _cache["fetched_at"], str(e)
