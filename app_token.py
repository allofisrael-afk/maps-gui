# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""T5 (F-031): טוקן לכל הפעלה לשרתים המקומיים (5002/5003/5004).

main.py יוצר טוקן אקראי בכל הפעלה ושם אותו במשתנה הסביבה MAPS_GUI_APP_TOKEN, ושלושת השרתים יורשים אותו.
כל בקשה לשרת חייבת לשאת את הטוקן בכותרת X-App-Token, אחרת היא נדחית ב-403.
- המפה (map.html) מקבלת את הטוקן בהזרקת סקריפט בזמן ריצה (QWebEngineScript), לא בקובץ על הדיסק.
- קריאות requests של main.py עצמו (דשבורד, מזג אוויר, בדיקות תקינות) מקבלות את הכותרת דרך install_requests_header().
- בלי משתנה הסביבה (שרת שהורץ ידנית, בדיקות, גרסת ה-web) אין אכיפה, וההתנהגות כמו קודם.
"""
import hmac  # T5: השוואת טוקנים בזמן קבוע (לא חושפת מידע דרך זמן תגובה)
import os  # T5: משתנה הסביבה שמעביר את הטוקן לתהליכי השרתים
import secrets  # T5: יצירת טוקן אקראי קריפטוגרפי
from urllib.parse import urlsplit  # T5: זיהוי בקשות לשרתים המקומיים בלבד

TOKEN_ENV = "MAPS_GUI_APP_TOKEN"  # T5: שם משתנה הסביבה
HEADER = "X-App-Token"  # T5: שם הכותרת בבקשות HTTP
_LOCAL_HOSTS = ("127.0.0.1", "localhost")  # T5: רק לשרתים המקומיים מוסיפים את הכותרת
_LOCAL_PORTS = (5002, 5003, 5004)  # T5: weather / geo / flight (ר' ports.py)


def ensure_token():  # T5: יוצר טוקן חדש להפעלה הזו (אם עוד אין) ומחזיר אותו
    token = os.environ.get(TOKEN_ENV)  # T5: אולי כבר נוצר בתהליך הזה
    if not token:  # T5: הפעלה חדשה — טוקן חדש
        token = secrets.token_urlsafe(32)  # T5: 256 ביט אקראיים
        os.environ[TOKEN_ENV] = token  # T5: תהליכי השרתים שיופעלו מכאן יורשים אותו
    return token  # T5: לשימוש בהזרקה למפה


def is_local_server_url(url):  # T5: True רק לכתובת של אחד משלושת השרתים המקומיים
    try:
        parts = urlsplit(str(url))  # T5: פירוק הכתובת
        return parts.hostname in _LOCAL_HOSTS and parts.port in _LOCAL_PORTS  # T5: מארח ופורט מקומיים
    except ValueError:  # T5: כתובת לא תקינה
        return False  # T5: לא מוסיפים כותרת


def install_requests_header():  # T5: כל קריאת requests בתהליך הזה לשרת מקומי תישא את הטוקן
    import requests  # T5: ייבוא מקומי — המודול נטען גם בשרתים שלא צריכים requests כאן
    if getattr(requests.Session.request, "_app_token_wrapped", False):  # T5: לא עוטפים פעמיים
        return  # T5: כבר הותקן
    original = requests.Session.request  # T5: הפונקציה המקורית

    def request(self, method, url, *args, **kwargs):  # T5: עטיפה דקה
        token = os.environ.get(TOKEN_ENV)  # T5: הטוקן הנוכחי
        if token and is_local_server_url(url):  # T5: רק לשרתים המקומיים, אף פעם לא לשירות חיצוני
            headers = dict(kwargs.get("headers") or {})  # T5: עותק, לא משנים את המילון של הקורא
            headers[HEADER] = token  # T5: הכותרת
            kwargs["headers"] = headers  # T5: מחזירים לקריאה
        return original(self, method, url, *args, **kwargs)  # T5: הקריאה המקורית

    request._app_token_wrapped = True  # T5: סימון נגד עטיפה כפולה
    requests.Session.request = request  # T5: requests.get/post עוברים דרך Session.request


def fetch_wrapper_js(token):  # T5: סקריפט שמוזרק למפה לפני כל קוד אחר — מוסיף את הכותרת לכל fetch לשרת מקומי
    return (
        "(function(){var T=" + repr(token).replace("'", '"') + ";var of=window.fetch;"  # T5: הטוקן כמחרוזת JS
        "window.fetch=function(u,o){try{var s=(u&&u.url)||String(u);"  # T5: הכתובת (מחרוזת או Request)
        "if(/^http:\\/\\/(localhost|127\\.0\\.0\\.1):500[234]\\//.test(s)){"  # T5: רק שרתים מקומיים
        "o=Object.assign({},o||{});var h=new Headers(o.headers||(u&&u.headers)||{});"  # T5: עותק כותרות
        "h.set('" + HEADER + "',T);o.headers=h;}}catch(e){}"  # T5: הוספת הטוקן
        "return of.call(this,u,o);};})();"  # T5: הקריאה המקורית
    )


def check_request(req):  # T5: לשימוש ב-before_request של השרת; מחזיר None (מותר) או הודעת שגיאה
    token = os.environ.get(TOKEN_ENV)  # T5: הטוקן שהשרת ירש מ-main.py
    if not token:  # T5: שרת בלי טוקן (ידני/בדיקות/web) — בלי אכיפה
        return None  # T5: מותר
    if req.method == "OPTIONS":  # T5: preflight של CORS לא נושא כותרות מותאמות — flask-cors מטפל בו
        return None  # T5: מותר
    sent = req.headers.get(HEADER, "")  # T5: הטוקן שנשלח
    if hmac.compare_digest(sent.encode("utf-8"), token.encode("utf-8")):  # T5: השוואה בזמן קבוע
        return None  # T5: מותר
    return "בקשה בלי טוקן הפעלה תקין"  # T5: נדחה
