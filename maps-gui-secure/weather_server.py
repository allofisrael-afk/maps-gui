import logging
import math
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(filename='app_combined.log', level=logging.INFO,
                    format='%(asctime)s - %(message)s')

app = Flask(__name__)
# תיקון: CORS מוגבל ל-localhost בלבד + null (לדפי file:// של QWebEngineView)
CORS(app,
     origins=["null", "http://localhost", "http://127.0.0.1"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type"])

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY")

_MAX_REGION_LEN = 200  # תיקון: מגבלת אורך לשם אזור


@app.before_request
def _handle_options():
    if request.method == 'OPTIONS':
        resp = app.make_response('')
        resp.headers['Access-Control-Allow-Origin']  = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp


def _validate_coordinates(lat_str, lon_str):
    """תיקון: וולידציה על קואורדינטות — טיפוס ותחום."""
    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except (ValueError, TypeError):
        return None, None, False
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None, None, False
    return lat, lon, True


def get_city_boundary(region):
    """פונקציה לקבלת גבולות העיר מ-Google Geocoding API."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": region, "key": GOOGLE_API_KEY}

    try:
        # תיקון: timeout מפורש שחסר במקור
        response = requests.get(url, params=params, timeout=5)
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
    region = request.args.get("region", "").strip() or None
    lat    = request.args.get("lat")
    lon    = request.args.get("lon")

    # תיקון: לא מתעדים את הקלט הגולמי של המשתמש
    logging.info("התקבלה בקשת מזג אוויר")

    if not region and (not lat or not lon):
        error_message = "חסר 'region' או קואורדינטות"
        logging.error(error_message)
        return jsonify({"error": error_message}), 400

    # תיקון: וולידציה על קואורדינטות
    if lat and lon:
        lat_f, lon_f, valid = _validate_coordinates(lat, lon)
        if not valid:
            logging.warning("קואורדינטות לא תקינות התקבלו")
            return jsonify({"error": "קואורדינטות לא תקינות"}), 400
        lat = str(lat_f)
        lon = str(lon_f)

    # תיקון: וולידציה על אורך שם האזור
    if region and len(region) > _MAX_REGION_LEN:
        logging.warning("שם אזור ארוך מדי")
        return jsonify({"error": "שם אזור ארוך מדי"}), 400

    if region:
        params = {
            "q":     region,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang":  "he"
        }
    else:
        params = {
            "lat":   lat,
            "lon":   lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang":  "he"
        }

    try:
        url = "http://api.openweathermap.org/data/2.5/weather"
        # תיקון: timeout מפורש שחסר במקור
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        boundary = get_city_boundary(region) if region else None

        if response.status_code == 200:
            # תיקון: לא מתעדים את התגובה המלאה של ה-API
            logging.info("נתוני מזג האוויר התקבלו בהצלחה")
            return jsonify({
                "region":      region if region else f"Latitude: {lat}, Longitude: {lon}",
                "weather":     data["weather"][0]["description"],
                "temperature": data["main"]["temp"],
                "latitude":    data["coord"]["lat"],
                "longitude":   data["coord"]["lon"],
                "boundary":    boundary
            })
        else:
            logging.error(f"שגיאה בקבלת נתוני מזג האוויר: {data.get('message', 'שגיאה לא ידועה')}")
            return jsonify({"error": data.get("message", "Error fetching weather data")}), response.status_code

    except Exception as e:
        logging.error(f"שגיאה בשרת מזג האוויר: {e}")
        # תיקון: הודעה גנרית ל-client, פרטים רק בלוג
        return jsonify({"error": "שגיאה פנימית בשרת"}), 500


@app.route("/heatmap_data", methods=["GET"])
def get_heatmap_data():
    data = [
        {"latitude": 32.0853, "longitude": 34.7818, "temperature": 28},
        {"latitude": 31.7683, "longitude": 35.2137, "temperature": 30},
        {"latitude": 29.5581, "longitude": 34.9482, "temperature": 25},
    ]
    return jsonify(data)


@app.route("/elevation", methods=["POST"])
def get_elevation():
    """
    מקבל רשימת נקודות [{latitude, longitude}] ומחזיר גובה לכל נקודה.
    משתמש ב-Open-Meteo Elevation API.
    """
    data = request.json
    locations = data.get("locations", []) if data else []

    if not locations:
        return jsonify({"error": "חסרות נקודות"}), 400

    locations = locations[:100]

    # תיקון: וולידציה על כל נקודה לפני שליחה לשרת חיצוני
    validated = []
    for p in locations:
        try:
            lat_v = float(p.get("latitude",  0))
            lon_v = float(p.get("longitude", 0))
            if (-90 <= lat_v <= 90) and (-180 <= lon_v <= 180):
                validated.append({"latitude": lat_v, "longitude": lon_v})
        except (ValueError, TypeError):
            continue

    if not validated:
        return jsonify({"error": "נקודות לא תקינות"}), 400

    lats = ",".join(str(p["latitude"])  for p in validated)
    lons = ",".join(str(p["longitude"]) for p in validated)

    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/elevation",
            params={"latitude": lats, "longitude": lons},
            timeout=15
        )
        r.raise_for_status()

        elevations = r.json().get("elevation", [])

        results = [
            {
                "latitude":  validated[i]["latitude"],
                "longitude": validated[i]["longitude"],
                "elevation": elevations[i]
            }
            for i in range(min(len(validated), len(elevations)))
        ]

        return jsonify({"results": results})

    except Exception as e:
        logging.error(f"שגיאה בשליפת גבהים: {e}")
        # תיקון: הודעה גנרית ל-client
        return jsonify({"error": "שגיאה פנימית בשרת"}), 500


# ── הגדרות עצמאיות לכל endpoint — שינוי באחד לא משפיע על השני ──

_ELEV_N_MAX      = 200    # מספר נקודות מטרה לרשת גבהים
_ELEV_MIN_STEP   = 0.2    # מרחק מינימלי בין נקודות (ק"מ)
_ELEV_BATCH      = 100    # נקודות לבקשה — מגבלת Open-Meteo Elevation API
_ELEV_BATCH_WAIT = 0.5    # השהיה בין batches (שניות)
_ELEV_TIMEOUT    = 20     # timeout לבקשת HTTP (שניות)
_ELEV_RETRY_WAIT = (65, 35)   # המתנה ב-retry עבור 429 (שניות: ניסיון 1, ניסיון 2)
_ELEV_CONN_WAIT  = 5      # המתנה ב-retry עבור ConnectionError (שניות)
_ELEV_HEADERS    = {
    "User-Agent": "Mozilla/5.0 (compatible; elevation-map-tool/1.0)",
    "Connection": "close",
    "Accept": "application/json",
}

_TEMP_N_MAX      = 200    # מספר נקודות מטרה לרשת טמפרטורות
_TEMP_MIN_STEP   = 0.5    # מרחק מינימלי בין נקודות (ק"מ)
_TEMP_BATCH      = 100    # נקודות לבקשה — מגבלת Open-Meteo Forecast API
_TEMP_BATCH_WAIT = 0.5    # השהיה בין batches (שניות)
_TEMP_TIMEOUT    = 30     # timeout לבקשת HTTP (שניות)
_TEMP_RETRY_WAIT = (65, 35)
_TEMP_CONN_WAIT  = 5
_TEMP_HEADERS    = {
    "User-Agent": "Mozilla/5.0 (compatible; temperature-map-tool/1.0)",
    "Connection": "close",
    "Accept": "application/json",
}


@app.route("/elevation_grid", methods=["POST"])
def get_elevation_grid():
    data = request.get_json()
    if not data:
        return jsonify({"error": "חסר גוף הבקשה"}), 400
    sw = data.get("southwest")
    ne = data.get("northeast")
    if not sw or not ne:
        return jsonify({"error": "חסרים southwest/northeast"}), 400

    mid_lat  = (sw["lat"] + ne["lat"]) / 2.0
    lat_km   = (ne["lat"] - sw["lat"]) * 111.0
    lon_km   = (ne["lng"] - sw["lng"]) * 111.0 * math.cos(math.radians(mid_lat))
    area_km2 = max(lat_km * lon_km, 0.01)
    step_km  = max(_ELEV_MIN_STEP, math.sqrt(area_km2 / _ELEV_N_MAX))
    lat_step = step_km / 111.0
    lon_step = step_km / (111.0 * math.cos(math.radians(mid_lat)))

    lats, lons = [], []
    lat = sw["lat"]
    while lat <= ne["lat"] + lat_step * 0.01:
        lon = sw["lng"]
        while lon <= ne["lng"] + lon_step * 0.01:
            lats.append(round(lat, 6))
            lons.append(round(lon, 6))
            lon += lon_step
        lat += lat_step

    if not lats:
        return jsonify({"error": "אזור קטן מדי"}), 400

    results = []
    for i in range(0, len(lats), _ELEV_BATCH):
        bl = lats[i:i + _ELEV_BATCH]
        bn = lons[i:i + _ELEV_BATCH]
        url = (f"https://api.open-meteo.com/v1/elevation"
               f"?latitude={','.join(map(str, bl))}"
               f"&longitude={','.join(map(str, bn))}")
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=_ELEV_TIMEOUT, headers=_ELEV_HEADERS)
                if r.status_code == 429:
                    wait = _ELEV_RETRY_WAIT[min(attempt, 1)]
                    logging.warning(f"elevation 429 — ממתין {wait}s (ניסיון {attempt+1}/3)")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                elevations = r.json().get("elevation", [])
                if not elevations:
                    logging.warning(f"elevation API returned empty: {r.text[:200]}")
                    return jsonify({"error": "API לא החזיר נתוני גובה"}), 502
                for j in range(min(len(bl), len(elevations))):
                    if elevations[j] is not None:
                        results.append({"lat": bl[j], "lng": bn[j], "elevation": elevations[j]})
                break
            except requests.exceptions.HTTPError as e:
                logging.error(f"elevation HTTP error: {r.status_code} | {r.text[:200]}")
                return jsonify({"error": f"שגיאת API: {r.status_code}"}), 502
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                logging.warning(f"elevation connection error (ניסיון {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(_ELEV_CONN_WAIT)
                    continue
                return jsonify({"error": "שגיאת חיבור ל-Open-Meteo"}), 502
            except Exception as e:
                logging.error(f"elevation unexpected error: {e}")
                return jsonify({"error": f"שגיאה פנימית: {str(e)}"}), 500
        else:
            return jsonify({"error": "חריגת מגבלת Open-Meteo — נסה שנית בעוד דקה"}), 429
        if i + _ELEV_BATCH < len(lats):
            time.sleep(_ELEV_BATCH_WAIT)

    if not results:
        return jsonify({"error": "לא נמצאו נקודות גובה תקינות"}), 404
    return jsonify(results)


@app.route("/temp_grid", methods=["POST"])
def get_temp_grid():
    data = request.get_json()
    if not data:
        return jsonify({"error": "חסר גוף הבקשה"}), 400
    sw = data.get("southwest")
    ne = data.get("northeast")
    if not sw or not ne:
        return jsonify({"error": "חסרים southwest/northeast"}), 400

    mid_lat  = (sw["lat"] + ne["lat"]) / 2.0
    lat_km   = (ne["lat"] - sw["lat"]) * 111.0
    lon_km   = (ne["lng"] - sw["lng"]) * 111.0 * math.cos(math.radians(mid_lat))
    area_km2 = max(lat_km * lon_km, 0.01)
    step_km  = max(_TEMP_MIN_STEP, math.sqrt(area_km2 / _TEMP_N_MAX))
    lat_step = step_km / 111.0
    lon_step = step_km / (111.0 * math.cos(math.radians(mid_lat)))

    lats, lons = [], []
    lat = sw["lat"]
    while lat <= ne["lat"] + lat_step * 0.01:
        lon = sw["lng"]
        while lon <= ne["lng"] + lon_step * 0.01:
            lats.append(round(lat, 6))
            lons.append(round(lon, 6))
            lon += lon_step
        lat += lat_step

    if not lats:
        return jsonify({"error": "אזור קטן מדי"}), 400

    results = []
    for i in range(0, len(lats), _TEMP_BATCH):
        bl = lats[i:i + _TEMP_BATCH]
        bn = lons[i:i + _TEMP_BATCH]
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={','.join(map(str, bl))}"
               f"&longitude={','.join(map(str, bn))}"
               f"&current=temperature_2m&timezone=auto")
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=_TEMP_TIMEOUT, headers=_TEMP_HEADERS)
                if r.status_code == 429:
                    wait = _TEMP_RETRY_WAIT[min(attempt, 1)]
                    logging.warning(f"temp_grid 429 — ממתין {wait}s (ניסיון {attempt+1}/3)")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                resp = r.json()
                if isinstance(resp, list):
                    for j, item in enumerate(resp):
                        temp = item.get("current", {}).get("temperature_2m")
                        if temp is not None:
                            results.append({"lat": bl[j], "lng": bn[j], "temperature": temp})
                else:
                    temp = resp.get("current", {}).get("temperature_2m")
                    if temp is not None:
                        results.append({"lat": bl[0], "lng": bn[0], "temperature": temp})
                break
            except requests.exceptions.HTTPError as e:
                logging.error(f"temp_grid HTTP error: {r.status_code} | {r.text[:200]}")
                return jsonify({"error": f"שגיאת API: {r.status_code}"}), 502
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                logging.warning(f"temp_grid connection error (ניסיון {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(_TEMP_CONN_WAIT)
                    continue
                return jsonify({"error": "שגיאת חיבור ל-Open-Meteo"}), 502
            except Exception as e:
                logging.error(f"temp_grid unexpected error: {e}")
                return jsonify({"error": f"שגיאה פנימית: {str(e)}"}), 500
        else:
            return jsonify({"error": "חריגת מגבלת Open-Meteo — נסה שנית בעוד דקה"}), 429
        if i + _TEMP_BATCH < len(lats):
            time.sleep(_TEMP_BATCH_WAIT)

    return jsonify(results)


if __name__ == "__main__":
    # תיקון: debug=False + קישור ל-127.0.0.1 בלבד
    app.run(host='127.0.0.1', port=5002, debug=False)
