# bootstrap נתיב-ייבוא — מוסיף את web/lib/ ל-sys.path כדי שהייבואים למטה (server_common,
# notam_drones וכו') ימצאו את המודולים שם בלי לשנות את שמות הייבוא המקוריים בכלל (קובץ זה
# הוא כמעט-עותק-מדויק של geo_server.py המקורי — ר' MAPS-GUI_SRS.md §3.24).
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))

import logging  # רישום אירועים ללוג (stdout ב-web — ה-basicConfig עצמו מוגדר ב-server_common.create_app)
from flask import Blueprint, jsonify, request  # Blueprint — ר' הערה מטה למה לא Flask() נפרד
import requests  # קריאה ל-Google Geocoding API

from notam_drones import get_uas_notams  # שליפה/פרסור/cache של שכבת ה-NOTAM לרחפנים
# ports.GEO_PORT לא נדרש כאן — Vercel מנתב לפי שם-קובץ, לא לפי פורט מקומי קבוע

# Blueprint, לא Flask(__name__) משלו — Vercel's "Flask framework" preset מצפה ל-app יחיד
# בכל הפרויקט (נמצא בדיפלוי אמיתי: FLASK_ENTRYPOINT_NOT_FOUND כש-3 קבצים הגדירו app משלהם
# — ר' MAPS-GUI_SRS.md §3.26). web/app.py הוא נקודת-הכניסה היחידה, מרשם את כל ה-blueprints.
geo_bp = Blueprint('geo', __name__)

# מפתח ה-API נטען ממשתה סביבה ולא מוטמע בקוד מטעמי אבטחה
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # קריאת מפתח Google API מקובץ .env

@geo_bp.route("/geo_data", methods=["GET"])
def get_geo_data():
    """
    שליחת בקשה ל-API של Google Geocoding לקבלת נתונים גיאוגרפיים של מקום מסוים.
    :return: נתוני גיאוגרפיה עבור מקום אם נמצא, או הודעת שגיאה אם לא.
    """
    location = request.args.get("location")  # קבלת פרמטר 'location' מהבקשה

    if not location:
        logging.error("חסר פרמטר 'location'")  # רישום שגיאה אם אין מיקום
        return jsonify({"error": "יש לספק פרמטר 'location'"}), 400  # החזרת שגיאה אם הפרמטר חסר

    # URL של ה-API
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": GOOGLE_API_KEY}  # הכנת פרמטרים עם המפתח

    try:
        # שליחת בקשה ל-API
        response = requests.get(url, params=params, timeout=5)  # הגבלת זמן לתגובה של 5 שניות
        response.raise_for_status()  # העלאת שגיאה אם יש בעיית HTTP

        # המרת התשובה לפורמט JSON
        data = response.json()

        if data["status"] == "OK":
            # אם התקבל מענה תקין, מחזירים את המיקום ואת הקואורדינטות
            result = data["results"][0]  # בוחרים את התוצאה הראשונה מתוך הרשימה
            return jsonify({
                "address": result["formatted_address"],
                "latitude": result["geometry"]["location"]["lat"],
                "longitude": result["geometry"]["location"]["lng"]
            })
        else:
            logging.error(f"שגיאה במענה מ-Google API עבור מיקום: {location}")  # רישום שגיאה אם לא נמצא המיקום
            return jsonify({"error": "מיקום לא נמצא"}), 404

    except requests.exceptions.Timeout:
        logging.error("שגיאה: הזמן שהוקצב לחיבור פג")  # רישום שגיאה אם פג הזמן
        return jsonify({"error": "שגיאה: הזמן שהוקצב לחיבור פג"}), 408  # החזרת קוד שגיאה 408

    except requests.exceptions.RequestException as e:
        logging.error(f"שגיאה בחיבור ל-Google API: {str(e)}")  # רישום שגיאה אם יש בעיה בחיבור
        return jsonify({"error": f"שגיאה בחיבור ל-Google API: {str(e)}"}), 500  # החזרת קוד שגיאה 500 במקרה של שגיאה

@geo_bp.route("/uas_notams", methods=["GET"])
def get_uas_notams_route():
    """
    שכבת "אזורי פעילות רחפנים (NOTAM)" — מסונן ל-UAS/UAV בלבד מתוך NOTAM של רשות שדות
    התעופה, עם גיאומטריה (מעגל/פוליגון) שחולצה מהטקסט. חשוב: אלה אזורים של פעילות
    רחפנים *מאושרת של אחרים* — אזור להימנעות/מודעות, לא "מותר לך לטוס כאן".
    force=1 מדלג על ה-cache (20 דק') ומושך מחדש — לשימוש זהיר, לא לרענון אוטומטי תכוף.
    """
    force = request.args.get("force") == "1"  # "?force=1" בלבד מחשיב כ-True — כל ערך אחר מתעלם
    zones, text_only_count, fetched_at, error = get_uas_notams(force_refresh=force)  # לוגיקת ה-cache כולה נמצאת ב-notam_drones
    return jsonify({
        "zones": zones,
        "text_only_count": text_only_count,  # רשומות UAS/UAV שנמצאו אך בלי גיאומטריה ניתנת לזיהוי בטקסט
        "fetched_at": fetched_at,
        "error": error,  # None אם הצליח; אחרת הודעת השגיאה מהניסיון האחרון (וייתכן שהוחזר cache ישן)
    })


if __name__ == "__main__":
    # הפעלה מקומית לבדיקה בלבד (python web/api/geo.py) — ב-Vercel לא מגיעים לכאן בכלל, ושם
    # geo_bp נרשם על ה-app היחיד ב-web/app.py. כאן בונים app זמני רק בשביל הבדיקה המקומית.
    # פורט קבוע-לבדיקה שונה מה-GEO_PORT של הדסקטופ (5003), כדי שאפשר להריץ בו-זמנית.
    from server_common import create_app
    _app = create_app(__name__)
    _app.register_blueprint(geo_bp)
    _app.run(port=5013, debug=True, threaded=True)
