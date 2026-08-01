import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# טעינת משתני סביבה
load_dotenv()

# הגדרת לוגינג
logging.basicConfig(filename='app_combined.log', level=logging.INFO,  # נשמור הכל בקובץ אחד
                    format='%(asctime)s - %(message)s')

# יצירת מופע Flask
app = Flask(__name__)
CORS(app)

# קבלת המפתחות ל-OpenWeather ו-Google API
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_city_boundary(region):
    """פונקציה לקבלת גבולות העיר מ-Google Geocoding API"""
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": region, "key": GOOGLE_API_KEY}

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if response.status_code == 200 and "results" in data and len(data["results"]) > 0:
            geometry = data["results"][0]["geometry"]
            bounds = geometry.get("bounds")
            if bounds:
                return {
                    "northeast": bounds["northeast"],
                    "southwest": bounds["southwest"]
                }
        return None
    except Exception as e:
        logging.error(f"שגיאה בקבלת גבולות העיר: {e}")
        return None

@app.route("/weather", methods=["GET"])
def get_weather():
    region = request.args.get("region")
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    # תיעוד בקשה שהתקבלה
    logging.info(f"תקבלה בקשה: Region={region}, Lat={lat}, Lon={lon}")

    # אם חסרים פרמטרים (לא נשלחו גם region וגם קואורדינטות)
    if not region and (not lat or not lon):
        error_message = "חסר 'region' או קואורדינטות"
        logging.error(error_message)  # רישום שגיאה
        return jsonify({"error": error_message}), 400

    # הגדרת פרמטרים לבקשה
    if region:
        params = {
            "q": region,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "he"
        }
    elif lat and lon:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "he"
        }
    else:
        error_message = "חסר 'region' או קואורדינטות"
        logging.error(error_message)
        return jsonify({"error": error_message}), 400

    # בקשה ל-OpenWeatherMap
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather"
        response = requests.get(url, params=params)
        data = response.json()

        # בקשה לגבולות העיר מ-Google Geocoding
        boundary = get_city_boundary(region) if region else None

        # תיעוד התגובה שהתקבלה
        if response.status_code == 200:
            logging.info(f"נתוני מזג האוויר התקבלו בהצלחה: {data}")
            return jsonify({
                "region": region if region else f"Latitude: {lat}, Longitude: {lon}",
                "weather": data["weather"][0]["description"],
                "temperature": data["main"]["temp"],
                "latitude": data["coord"]["lat"],
                "longitude": data["coord"]["lon"],
                "boundary": boundary  # הוספת גבולות העיר
            })
        else:
            logging.error(f"שגיאה בקבלת נתוני מזג האוויר: {data.get('message', 'שגיאה לא ידועה')}")
            return jsonify({"error": data.get("message", "Error fetching weather data")}), response.status_code

    except Exception as e:
        error_message = f"שגיאה בשרת: {e}"
        logging.error(error_message)  # רישום שגיאה
        return jsonify({"error": error_message}), 500

@app.route("/heatmap_data", methods=["GET"])
def get_heatmap_data():
    """
    API להחזרת נתוני שכבת חום.
    """
    # יצירת נתונים לדוגמה
    data = [
        {"latitude": 32.0853, "longitude": 34.7818, "temperature": 28},  # תל אביב
        {"latitude": 31.7683, "longitude": 35.2137, "temperature": 30},  # ירושלים
        {"latitude": 29.5581, "longitude": 34.9482, "temperature": 25},  # אילת
    ]

    # החזרת הנתונים בפורמט JSON
    return jsonify(data)


if __name__ == "__main__":
    app.run(port=5002, debug=True)