"""
שכבת "אזורי פעילות טיסה (NOTAM)" — שולף ומפרש NOTAMs מ-brin.iaa.gov.il (רשות שדות
התעופה), מסונן ל-7 קטגוריות (ר' notam_categories.py — בהשראת מסך השכבות של DronesIL
הרשמית), ומחלץ גיאומטריה (מעגל/פוליגון) וגובה מהטקסט החופשי. NOTAM בודד עשוי להתאים
ליותר מקטגוריה אחת (למשל "UAS PROHIBITED" מתאים גם ל-uas וגם ל-prohibited).

חשוב — סמנטיקה: רשומת "UAS/UAV ACT WILL TAKE PLACE... CLSD FM GND UP TO Xft" מתארת
פעילות רחפנים *מאושרת של מפעיל אחר* שהמרחב האווירי סביבה סגור לתעבורה אחרת עד לגובה
מסוים — זה *לא* "מותר לך לטוס כאן". השכבה מוצגת ככלי הימנעות/מודעות, לא כ"אזור מותר".
נבדק ידנית מול העמוד ב-2026-08-09: brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam

חשוב (עודכן 17/08/2026): בניגוד למה שהונח בעבר, ה-GET הראשוני **לא** תמיד מחזיר את
הטקסט המלא — לחלק מהרשומות יש עוד שורות (כולל קואורדינטות פוליגון!) שחתוכות בתצוגה
המכווצת וזמינות רק דרך מנגנון "הרחבה" (postback אסינכרוני של ASP.NET UpdatePanel,
מדמה לחיצה על כפתור "+"). לכן, לכל רשומה שעברה סינון קטגוריה, שולפים גם את ה"הרחבה"
שלה (ר' _fetch_more_info) — כולל שורת Q) הסטנדרטית (חובה בכל NOTAM לפי ICAO) שמשמשת
כרשת ביטחון אחרונה (מרכז+רדיוס גס) גם כשל-E) עצמו אין קואורדינטות (ר' _geometry_from_q_line).

האתר מוגן ב-WAF (עוגיות __uzm*/F5 ASM) — cache עם TTL מונע סריקה תכופה מדי שעלולה
להיחסם, ובמקביל נותן תמונת מצב "עדכנית מספיק" (NOTAM לא משתנה כל שנייה). מנגנון
ה"הרחבה" מוסיף עד כ-26 בקשות POST נוספות לרענון cache אחד — לכן יש השהיה קטנה בין
בקשה לבקשה (_MORE_INFO_DELAY_SEC) כדי לא להציף את ה-WAF, וכל כישלון בקשה בודדת
נופל בחזרה לטקסט המקוצר של ה-GET הראשוני במקום להפיל את הרענון כולו.
"""
import re  # פרסינג HTML/טקסט חופשי בלי תלות חיצונית — הדף עצמו לא מספק JSON
import time  # מדידת גיל ה-cache

import requests  # שליפת דף ה-NOTAM מרשות שדות התעופה

from icao_glossary import render_hebrew_gloss  # תרגום גס לעברית — ר' icao_glossary.py לאזהרת הבטיחות
from notam_categories import classify_notam  # סיווג NOTAM ל-7 קטגוריות — ר' notam_categories.py

_NOTAM_URL = "https://brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam"  # דף NOTAM ציבורי — לא דורש מפתח API
_REQUEST_TIMEOUT = 20  # שניות — לבקשת ה-GET הראשונית בלבד; היא לבדה, אין סיכון הצטברות
_CACHE_TTL_SEC = 20 * 60  # 20 דקות — מספיק "חי" לתמונת מצב, לא מציף את השרת המוגן
# timeout קצר יותר מ-_REQUEST_TIMEOUT ייעודית לבקשות "הרחבה" (_fetch_more_info) — יש עד 27
# כאלה ברצף אחד; timeout מלא (20ש') לכל אחת בנפרד היה יכול להצטבר לדקות אם ה-WAF מתחיל
# להאט חלק מהבקשות, ויש כבר נפילה-חזרה טובה (הטקסט המקוצר) שלא מצדיקה חכייה ארוכה
_MORE_INFO_TIMEOUT = 8

# קואורדינטת DMS דחוסה — נתמכים שני סדרי-טוקנים אמיתיים שנצפו ב-NOTAM: "ספרות-ואז-אות-כיוון"
# (315907.32N0345601.24E, הנפוץ) ו"אות-כיוון-ואז-ספרות" (N314945E0345822, נצפה בפוליגונים
# כמו LATRUN/OR-AKIVA — לפני התיקון הזה הם נפלו ל"טקסט בלבד" כי הפורמט הזה לא זוהה כלל).
# שניות עשרוניות (`.32`) נתמכות בשני הפורמטים — נצפו ב-NOTAM-ים אחרים (מנופי בנייה).
_COORD_PATTERN = (
    r"(?:\d{2}\d{2}\d{2}(?:\.\d+)?[NS]\d{3}\d{2}\d{2}(?:\.\d+)?[EW]"
    r"|[NS]\d{2}\d{2}\d{2}(?:\.\d+)?[EW]\d{3}\d{2}\d{2}(?:\.\d+)?)"
)
_COORD_RE = re.compile(_COORD_PATTERN)  # לאיתור כל הקואורדינטות בטקסט חופשי (לפוליגונים) — finditer
# פירוק בפועל לפי הפורמט הספציפי שהתקבל — נבדק ב-_coord_to_latlon אחרי שהתאמה נמצאה
_COORD_SUFFIX_RE = re.compile(r"(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([NS])(\d{3})(\d{2})(\d{2}(?:\.\d+)?)([EW])")
_COORD_PREFIX_RE = re.compile(r"([NS])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([EW])(\d{3})(\d{2})(\d{2}(?:\.\d+)?)")
# תבנית אזור מעגלי, למשל "0.3NM RADIUS CENTERED ON PSN 314643N0350539E" — נתמכות 3 יחידות
# מרחק אמיתיות שנצפו ב-NOTAM (NM/KM/M, ר' _UNIT_TO_METERS למטה); הקואורדינטה יכולה להיות
# בכל אחד משני הפורמטים הנתמכים (ר' _COORD_PATTERN למעלה). (?:\S+\s+){0,4}? מאפשר עד 4
# מילים בין RADIUS ל-CENTERED (למשל "RADIUS SEMI-CIRCLE TO EAST CENTERED", נצפה בפועל) —
# בלי זה, מעגל שהוא בעצם חצי-מעגל היה נופל ל"טקסט בלבד" למרות שיש לו קואורדינטת מרכז מלאה.
_RADIUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(NM|KM|M)\s+RADIUS\s+(?:\S+\s+){0,4}?CENTERED\s+ON\s+PSN\s+(" + _COORD_PATTERN + r")",
    re.IGNORECASE,
)
_UNIT_TO_METERS = {"NM": 1852.0, "KM": 1000.0, "M": 1.0}  # גורם המרה לכל יחידת רדיוס נתמכת
# משפט הגובה — מ"FM" (התחלה: GND או גובה) עד "UP TO ..." ועד לנקודה הבאה בטקסט
_ALT_SENTENCE_RE = re.compile(r"FM\s+(?:GND|[\d,]+\s*FT)\s+UP\s+TO[^.]*", re.IGNORECASE)
_BLOCK_SPLIT_RE = re.compile(r'(?=<div id="divMainInfo_)')  # כל רשומת NOTAM מתחילה ב-div כזה עם מזהה ייחודי
_MSG_NUM_RE = re.compile(r'divMainInfo_(\d+)"')  # המזהה המספרי הפנימי (למשל 2040525) — נדרש לבקשת ה"הרחבה"
_NOTAM_ID_RE = re.compile(r'class="NotamID">\s*([^<\n]+?)\s*</td>')  # תא הטבלה עם מספר ה-NOTAM (למשל C1711/26)
_LOCATION_RE = re.compile(r'class="Location">\s*([^<\n]+?)\s*</td>')  # תא הטבלה עם קוד ה-ICAO (למשל LLLL)
_MSGTEXT_RE = re.compile(r'class="MsgText">\s*([^<]*?)\s*</td>')  # שורת טקסט אחת מתוך כמה — המסר נחתך לכמה תאים

# ── מנגנון "הרחבה" (postback אסינכרוני) — שליפת הטקסט המלא + שורת Q) לכל רשומה ──
_HIDDEN_FIELD_RE_TMPL = r'id="{name}"[^>]*value="([^"]*)"'  # תבנית כללית לשליפת ערך שדה hidden לפי id
# הקריאה f_buildMoreMsgInfo('<Msg ...>...</Msg>') מוטמעת בתגובת ה-postback (delta מסוג
# Microsoft AJAX) — הדרך הפשוטה והעמידה ביותר לשלוף אותה היא רג'קס ישיר, לא פענוח מלא
# של פורמט ה-delta (length|type|id|content|...) שאינו נחוץ לצורך הזה בלבד.
_MORE_INFO_RE = re.compile(r"f_buildMoreMsgInfo\('(<Msg .*?</Msg>)'\)", re.DOTALL)
_MORE_MSGTEXT_RE = re.compile(r"<MsgText>(.*?)</MsgText>", re.DOTALL)  # כל שורת טקסט בתוך ה-XML המוטמע
# שורת Q) הסטנדרטית (חובה בכל NOTAM לפי ICAO Doc 8126) — מרכז (מעלות+דקות, בלי שניות)
# ורדיוס (NM) בתור הסיומת: ".../000/014/3143N03450E002" — פורמט שונה/קומפקטי יותר
# מהקואורדינטות ב-E), ולכן רג'קס נפרד ולא הרחבה של _COORD_PATTERN
_Q_LINE_RE = re.compile(
    r"Q\)\s*\S+/\S+/\S+/\S*\s*/\S*\s*/\d+/\d+/(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})"
)
_MORE_INFO_DELAY_SEC = 0.3  # השהיה בין בקשות "הרחבה" עוקבות — קצב מתון, לא להציף את ה-WAF

_cache = {"zones": [], "text_only_count": 0, "fetched_at": 0.0, "error": None}  # cache יחיד בזיכרון התהליך — משותף לכל הבקשות


def _coord_to_latlon(coord_str):
    """ ממיר קואורדינטת DMS דחוסה (למשל '305819N0345601E' או 'N305819E0345601') לזוג
    (lat, lon) עשרוני. מנסה קודם את הפורמט הנפוץ (ספרות ואז אות-כיוון), ואם לא תואם —
    את הפורמט ההפוך (אות-כיוון ואז ספרות), שנצפה בפועל בכמה NOTAM-ים של פוליגונים. """
    m = _COORD_SUFFIX_RE.fullmatch(coord_str)  # פורמט 1: 315907N0345601E (הנפוץ)
    if m:
        lat_d, lat_m, lat_s, ns, lon_d, lon_m, lon_s, ew = m.groups()  # סדר: מעלות/דקות/שניות ואז כיוון, לכל ציר
    else:
        m = _COORD_PREFIX_RE.fullmatch(coord_str)  # פורמט 2: N315907E0345601 (הפוך)
        if not m:
            return None  # אף אחד משני הפורמטים לא תואם — הקורא מסנן None בעצמו
        ns, lat_d, lat_m, lat_s, ew, lon_d, lon_m, lon_s = m.groups()  # סדר: כיוון ואז מעלות/דקות/שניות, לכל ציר
    lat = float(lat_d) + float(lat_m) / 60 + float(lat_s) / 3600  # המרת DMS לעשרוני; float תומך גם בשניות עשרוניות
    lon = float(lon_d) + float(lon_m) / 60 + float(lon_s) / 3600
    if ns == "S":
        lat = -lat  # דרום = ערך שלילי
    if ew == "W":
        lon = -lon  # מערב = ערך שלילי
    return lat, lon


def _extract_geometry(text):
    """ מזהה מעגל ("X NM RADIUS CENTERED ON PSN ...") או פוליגון (3+ קואורדינטות בטקסט).
    מחזיר dict גיאומטריה או None אם לא נמצאה גיאומטריה ניתנת לזיהוי בטקסט. """
    # "source": "text" — הגיאומטריה חולצה מתיאור מפורש ב-E) עצמו (מעגל/פוליגון מדויקים
    # כפי שדווחו במקור), לא קירוב. נצרך ע"י הצד הלקוח כדי להבחין ויזואלית מ-_geometry_from_q_line.
    radius_match = _RADIUS_RE.search(text)  # קודם בודקים אם זה אזור מעגלי — יותר ספציפי מפוליגון
    if radius_match:
        center = _coord_to_latlon(radius_match.group(3))  # קבוצה 3 = הקואורדינטה של המרכז (1=מספר, 2=יחידה)
        if center:
            unit = radius_match.group(2).upper()
            return {"type": "circle", "center": [center[0], center[1]],
                     "radius_m": float(radius_match.group(1)) * _UNIT_TO_METERS[unit],  # המרה ליחידה שנתפסה בפועל
                     "source": "text"}

    coords = [_coord_to_latlon(m.group(0)) for m in _COORD_RE.finditer(text)]  # כל הקואורדינטות שמופיעות בטקסט לפי הסדר
    coords = [c for c in coords if c]  # סינון None (התאמות שנכשלו בהמרה)
    if len(coords) >= 3:  # מתחת ל-3 נקודות אין פוליגון תקין
        return {"type": "polygon", "points": [[lat, lon] for lat, lon in coords], "source": "text"}
    return None  # אין מספיק מידע גיאומטרי בטקסט — הרשומה תיספר כ-text_only


def _geometry_from_q_line(text):
    """ רשת ביטחון אחרונה: מחלץ מעגל גס (מרכז+רדיוס) משורת Q) הסטנדרטית-חובה של NOTAM,
    לשימוש רק כש-_extract_geometry לא מצא שום דבר ב-E) עצמו (למשל הפניה לאזור בשם בלי
    קואורדינטות מפורשות). דיוק נמוך יותר מ-E) (בלי שניות, ורדיוס לפעמים גס), אבל עדיף
    על "טקסט בלבד" בלי שום ייצוג גיאוגרפי — כך גם DronesIL כנראה מציג את המקרים האלה. """
    m = _Q_LINE_RE.search(text)
    if not m:
        return None
    lat_d, lat_m, ns, lon_d, lon_m, ew, radius_nm = m.groups()
    lat = float(lat_d) + float(lat_m) / 60  # שורת Q נותנת רק מעלות+דקות, בלי שניות
    lon = float(lon_d) + float(lon_m) / 60
    if ns == "S":
        lat = -lat
    if ew == "W":
        lon = -lon
    radius_m = float(radius_nm) * _UNIT_TO_METERS["NM"]  # הרדיוס בשורת Q תמיד ב-NM
    if radius_m <= 0:
        return None  # רדיוס 000 בשורת Q — לא נותן שטח משמעותי לצייר
    # "source": "q_line_approx" — קירוב גס, לא הצורה האמיתית של האזור (למשל רצועת גבול
    # מוצגת כמעגל) — הצד הלקוח מציג את זה אחרת (מסגרת מקווקוות + הבהרה בפופאפ), לא
    # באותה רמת ביטחון חזותית כמו גיאומטריה מדויקת מ-_extract_geometry
    return {"type": "circle", "center": [lat, lon], "radius_m": radius_m, "source": "q_line_approx"}


def _extract_altitude_text(text):
    """ מחזיר את משפט הגובה הגולמי מהטקסט (למשל "FM GND UP TO 250M AGL"), או מחרוזת ריקה אם לא נמצא. """
    m = _ALT_SENTENCE_RE.search(text)
    return m.group(0).strip() if m else ""


def _parse_notam_blocks(html):
    """ מפצל את ה-HTML לבלוקים לפי divMainInfo_ (רשומת NOTAM אחת לכל בלוק) ומחלץ
    מכל בלוק: מזהה NOTAM, מיקום ICAO, מזהה פנימי מספרי (לבקשת "הרחבה"), וטקסט ההודעה
    כפי שמופיע בתצוגה המכווצת (מחובר מכל שורות ה-MsgText — עשוי להיות חתוך, ר' _fetch_more_info). """
    notams = []
    for block in _BLOCK_SPLIT_RE.split(html)[1:]:  # הפריט הראשון הוא prefix ללא רשומה (לפני ה-div הראשון)
        id_match = _NOTAM_ID_RE.search(block)
        loc_match = _LOCATION_RE.search(block)
        msg_num_match = _MSG_NUM_RE.search(block)
        if not id_match or not loc_match or not msg_num_match:
            continue  # בלוק שלא בפורמט הצפוי — מדלגים במקום לזרוק שגיאה
        msg_parts = [m.group(1).strip() for m in _MSGTEXT_RE.finditer(block)]  # כל שורות הטקסט השייכות לרשומה הזו
        full_text = " ".join(p for p in msg_parts if p)  # חיבור לטקסט רציף אחד — עשוי עדיין להיות חתוך (ר' docstring המודול)
        notams.append({
            "id": id_match.group(1).strip(),
            "icao": loc_match.group(1).strip(),
            "msg_num": msg_num_match.group(1),
            "text": full_text,
        })
    return notams


def _extract_hidden_field(html, name):
    """ שולף ערך שדה hidden בודד מה-HTML הראשוני, לפי ה-id שלו (למשל __VIEWSTATE). """
    m = re.search(_HIDDEN_FIELD_RE_TMPL.format(name=re.escape(name)), html)
    return m.group(1) if m else ""


def _fetch_more_info(session, msg_num, headers, base_fields):
    """ מדמה לחיצה על כפתור ה"+" של רשומת NOTAM בודדת (postback אסינכרוני, ASP.NET
    UpdatePanel) ומחזירה את הטקסט המלא המשוחזר (כל MsgText מחוברים, כולל שורת Q)/A)/B)/C)
    שלא מוצגות בתצוגה הרגילה) — או None בכל כישלון (הקורא נופל חזרה לטקסט המקוצר).
    base_fields — שדות ה-ViewState/EventValidation שנשלפו פעם אחת מה-GET הראשוני. """
    data = dict(base_fields)
    data.update({
        "ScriptManager": "ScriptManager|btnMoreInfo",  # שם השדה הנדרש ע"י Microsoft AJAX PageRequestManager לזיהוי async postback
        "hidTblClientId": "", "hidMsgNum": msg_num, "hidCurOrHist": "Current",
        "hidMode": "more", "hidXYPos": "",
        "__ASYNCPOST": "true", "btnMoreInfo": "",
    })
    post_headers = dict(headers)
    post_headers.update({
        "X-MicrosoftAjax": "Delta=true",  # מסמן לשרת שמדובר בבקשת postback חלקית (delta), לא רינדור עמוד מלא
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": _NOTAM_URL,
    })
    resp = session.post(_NOTAM_URL, data=data, headers=post_headers, timeout=_MORE_INFO_TIMEOUT)
    resp.raise_for_status()
    m = _MORE_INFO_RE.search(resp.text)
    if not m:
        return None  # התגובה לא במבנה הצפוי (למשל שגיאת שרת) — הקורא נופל חזרה לטקסט המקוצר
    parts = [t.strip() for t in _MORE_MSGTEXT_RE.findall(m.group(1))]
    return " ".join(p for p in parts if p)


def _fetch_and_parse():
    """ מושך את דף ה-NOTAM ומחזיר (zones, text_only_count) — לא נגיש ישירות מבחוץ, רק דרך get_uas_notams עם ה-cache. """
    session = requests.Session()  # נדרש כדי לשמר עוגיות ה-WAF וה-ViewState בין ה-GET הראשוני לבקשות ה"הרחבה"
    headers = {"User-Agent": "Mozilla/5.0"}  # UA דפדפן — נדרש כדי לעבור את ה-WAF
    resp = session.get(_NOTAM_URL, headers=headers, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()  # זורק חריגה על קוד שגיאה HTTP — נתפס ב-get_uas_notams
    html = resp.text
    notams = _parse_notam_blocks(html)

    # שדות ה-ViewState/EventValidation נשלפים פעם אחת מה-GET הראשוני ומועברים לכל
    # קריאת _fetch_more_info — הם משותפים לכל הרשומות באותו רענון (לא משתנים בין רשומה לרשומה)
    base_fields = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        "__VIEWSTATE": _extract_hidden_field(html, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _extract_hidden_field(html, "__VIEWSTATEGENERATOR"),
        "__VIEWSTATEENCRYPTED": "",
        "__EVENTVALIDATION": _extract_hidden_field(html, "__EVENTVALIDATION"),
        "hiddenLocalUtcDiff": "3", "msgsType": "Notam",
    }

    zones = []
    text_only_count = 0
    for n in notams:
        categories = classify_notam(n["text"])  # התאמה ל-0 או יותר מ-7 הקטגוריות (ר' notam_categories.py) — על הטקסט המקוצר, מספיק לסיווג
        if not categories:
            continue  # לא תואם אף קטגוריה רלוונטית — לא נכלל בשכבה, גם לא בהרחבה (חוסך בקשות מיותרות)

        full_text = n["text"]
        try:
            expanded = _fetch_more_info(session, n["msg_num"], headers, base_fields)  # מנסה לקבל את הטקסט המלא/לא-חתוך
            if expanded:
                full_text = expanded
        except requests.exceptions.RequestException:
            pass  # בקשת ה"הרחבה" נכשלה — ממשיכים עם הטקסט המקוצר של ה-GET הראשוני כ-fallback, לא מפילים את כל הרענון
        finally:
            time.sleep(_MORE_INFO_DELAY_SEC)  # קצב מתון בין רשומות — לא להציף את ה-WAF, גם אם הבקשה נכשלה

        geometry = _extract_geometry(full_text)
        if geometry is None:
            geometry = _geometry_from_q_line(full_text)  # רשת ביטחון אחרונה — מעגל גס משורת Q)
        if geometry is None:
            text_only_count += 1  # רשומה רלוונטית, אבל בלי שום גיאומטריה ניתנת לחילוץ (גם לא משורת Q)
            continue
        altitude_text = _extract_altitude_text(full_text)
        zones.append({
            "id": n["id"],
            "icao": n["icao"],
            "text": full_text,
            "altitude_text": altitude_text,
            "geometry": geometry,
            "categories": categories,  # רשימת id-ים — שימוש בסינון/צביעה לפי קטגוריה בצד הלקוח
            "hebrew_gloss": render_hebrew_gloss(full_text),  # תרגום גס — תמיד לצד המקור האנגלי, לא במקומו
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
