import logging  # רישום אירועים לקובץ לוג משותף
import os  # ייבוא מודול os לגישה למשתני סביבה
from dotenv import load_dotenv  # ייבוא load_dotenv לטעינת קובץ .env
from flask import Flask, jsonify, request  # שרת ה-Web ופענוח פרמטרים
from flask_cors import CORS  # מאפשר קריאות cross-origin מ-map.html שנטען מ-file://
import requests  # קריאה ל-Google Geocoding API

from metrics import register_metrics  # נתיב /metrics משותף לכל שרתי הפרויקט
from notam_drones import get_uas_notams  # שליפה/פרסור/cache של שכבת ה-NOTAM לרחפנים

# טעינת משתני סביבה מקובץ .env
load_dotenv()  # טעינת משתני הסביבה מקובץ .env לפני שימוש בהם

# הגדרת לוגינג
logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# יצירת מופע Flask
app = Flask(__name__)
CORS(app)
register_metrics(app)  # מוסיף נתיב GET /metrics למעקב הדשבורד

# מפתח ה-API נטען ממשתה סביבה ולא מוטמע בקוד מטעמי אבטחה
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # קריאת מפתח Google API מקובץ .env

@app.route("/geo_data", methods=["GET"])
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

@app.route("/uas_notams", methods=["GET"])
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
    # הפעלת השרת
    app.run(port=5003, debug=True)
