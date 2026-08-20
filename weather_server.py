import json  # קריאה/כתיבה של קובץ "עמדות שמורות" (saved_stations.json)
import logging  # רישום אירועים לקובץ לוג משותף (ה-basicConfig עצמו הוגדר ב-server_common.create_app)
import math  # חישובי טריגונומטריה למרחקים/LOS/עקמומיות כדור הארץ
import time  # השהיות בין ניסיונות חוזרים ובין batches
from flask import jsonify, request  # פענוח בקשות — Flask() עצמו נוצר ב-server_common.create_app
import requests  # קריאות ל-OpenWeather/Open-Meteo/Google
import os  # קריאת מפתחות API ממשתני סביבה, בדיקת קיום קובץ CSV
import threading  # ריצת חישוב רדיוס-ראייה ברקע (job) כדי לא לחסום את הבקשה עצמה — מאפשר polling+ביטול
import uuid  # מזהה ייחודי לכל job של רדיוס-ראייה

from server_common import create_app  # תשתית משותפת לשלושת השרתים — .env/logging/Flask/CORS/metrics
from ports import WEATHER_PORT

# יצירת מופע Flask (טעינת .env, logging, CORS, ו-/metrics כבר מוכנים בתוך create_app)
app = create_app(__name__)

# מפתח ה-API ל-OpenWeather (מזג אוויר בפועל) — הגיאוקודינג (חיפוש עיר/אזור) עבר ל-Nominatim, חינמי וללא מפתח
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

def geocode_region_nominatim(region):
    """
    מחליף את Google Geocoding — משתמש ב-OSM/Nominatim (חינמי, ללא מפתח).
    חשוב: Google לא מזהה כלל מונחים כמו "שטח A"/"שטח B"/"שטח C" (בדוק ידנית —
    מחזיר ZERO_RESULTS או נופל לגבולות כל הגדה המערבית בלי הבחנה), בעוד Nominatim
    מזהה אותם נכון כפוליגוני גבול מנהליים אמיתיים (boundary/administrative ב-OSM).
    מחזיר (lat, lon, boundary) — boundary כולל גם bbox (northeast/southwest, לתאימות
    לאחור) וגם 'rings' (רשימת טבעות קואורדינטות אמיתיות, אם השירות החזיר geojson) —
    (lat, lon, None) אם המקום נמצא בלי boundingbox, או (None, None, None) אם לא נמצא כלל.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": region, "format": "json", "limit": 1, "polygon_geojson": 1}
    headers = {"User-Agent": "maps-gui-desktop/1.0"}  # נדרש ע"י מדיניות השימוש של Nominatim

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        results = response.json()
        if not results:
            return None, None, None
        r = results[0]
        lat = float(r["lat"])
        lon = float(r["lon"])

        boundary = None
        bbox = r.get("boundingbox")  # סדר Nominatim: [south, north, west, east], כל הערכים כ-strings
        if bbox and len(bbox) == 4:
            south, north, west, east = (float(v) for v in bbox)
            boundary = {
                "northeast": {"lat": north, "lng": east},
                "southwest": {"lat": south, "lng": west},
            }

        geojson = r.get("geojson")
        rings = _extract_boundary_rings(geojson) if geojson else []
        if rings:
            boundary = boundary or {}
            boundary["rings"] = rings

        return lat, lon, boundary
    except Exception as e:
        logging.error(f"שגיאה בגיאוקודינג דרך Nominatim: {e}")
        return None, None, None


def _extract_boundary_rings(geojson):
    """
    ממיר geojson['geometry'] מ-Nominatim (Polygon/MultiPolygon בלבד — טיפוסים אחרים
    כמו Point אין להם צורת שטח להציג) לרשימת טבעות [[lat, lon], ...] — מקביל בדיוק
    ל-_extractBoundaryRings ב-city_result.dart (גרסת האנדרואיד).
    """
    try:
        gtype = geojson.get("type")
        coords = geojson.get("coordinates")
        if gtype == "Polygon":
            return [[[pt[1], pt[0]] for pt in ring] for ring in coords]
        if gtype == "MultiPolygon":
            rings = []
            for polygon in coords:
                for ring in polygon:
                    rings.append([[pt[1], pt[0]] for pt in ring])
            return rings
    except Exception:
        pass
    return []

@app.route("/weather", methods=["GET"])
def get_weather():
    region = request.args.get("region")  # חיפוש לפי שם עיר, לדוגמה "תל אביב"
    lat = request.args.get("lat")  # לחלופין: קואורדינטות ישירות
    lon = request.args.get("lon")

    # תיעוד בקשה שהתקבלה
    logging.info(f"תקבלה בקשה: Region={region}, Lat={lat}, Lon={lon}")

    # אם חסרים פרמטרים (לא נשלחו גם region וגם קואורדינטות)
    if not region and (not lat or not lon):
        error_message = "חסר 'region' או קואורדינטות"
        logging.error(error_message)  # רישום שגיאה
        return jsonify({"error": error_message}), 400

    # אם חיפשו לפי שם — קודם מגאוקדים דרך Nominatim (מזהה גם "שטח A/B/C" ומחזיר גבול
    # אמיתי, מה ש-Google לא עשה — ר' geocode_region_nominatim). אם נמצא, ממשיכים עם
    # הקואורדינטות שהתקבלו (עובד גם לישויות שאינן "עיר" ב-OpenWeather, כמו אזור מנהלי).
    # אם לא נמצא, נופלים חזרה לחיפוש הישן של OpenWeather לפי שם — לא שוברים חיפושים קיימים.
    boundary = None
    if region:
        nomi_lat, nomi_lon, boundary = geocode_region_nominatim(region)
        if nomi_lat is not None:
            lat, lon = nomi_lat, nomi_lon

    # הגדרת פרמטרים לבקשה
    if lat and lon:  # OpenWeather API: lat/lon ישירים — גם למקור lat/lon מקורי, וגם לתוצאת גיאוקוד לפי שם
        params = {
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "he"
        }
    elif region:  # Nominatim לא מצא — נפילה חזרה לחיפוש OpenWeather הישן לפי שם עיר
        params = {
            "q": region,
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
        response = requests.get(url, params=params, timeout=15)  # היה חסר timeout — קריאה תקועה הייתה חוסמת את כל התהליך (dev server חד-thread)
        data = response.json()

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
    קורא מ-weather_data.csv אם קיים — אחרת מחזיר נתוני fallback סטטיים.
    """
    import csv as csv_module  # ייבוא מקומי — נדרש רק בפונקציה הזו, לא בשאר השרת

    csv_path = "weather_data.csv"
    if os.path.exists(csv_path):
        try:
            data = []
            with open(csv_path, encoding="utf-8") as f:
                reader = csv_module.DictReader(f)  # כל שורה הופכת ל-dict לפי כותרות העמודות
                for row in reader:
                    try:
                        data.append({
                            "latitude":    float(row["latitude"]),
                            "longitude":   float(row["longitude"]),
                            "temperature": float(row["temperature"])
                        })
                    except (KeyError, ValueError):
                        continue  # שורה פגומה — מדלג
            if data:
                logging.info(f"heatmap_data: נטענו {len(data)} נקודות מ-{csv_path}")
                return jsonify(data)
        except Exception as e:
            logging.error(f"שגיאה בקריאת {csv_path}: {e}")

    # fallback — נתונים סטטיים כשאין CSV
    logging.info("heatmap_data: CSV לא נמצא — מחזיר נתוני fallback")
    data = [
        {"latitude": 32.0853, "longitude": 34.7818, "temperature": 28},  # תל אביב
        {"latitude": 31.7683, "longitude": 35.2137, "temperature": 30},  # ירושלים
        {"latitude": 29.5581, "longitude": 34.9482, "temperature": 25},  # אילת
    ]
    return jsonify(data)


@app.route("/elevation", methods=["POST"])  # נתיב POST — מקבל רשימת נקודות בגוף הבקשה
def get_elevation():
    """
    מקבל רשימת נקודות [{latitude, longitude}] ומחזיר גובה לכל נקודה.
    משתמש ב-Open-Meteo Elevation API (חינמי, ללא מפתח API, תומך עד 100 נקודות).
    מחזיר פורמט {"results": [{latitude, longitude, elevation}, ...]} לתאימות עם ה-JavaScript.
    """
    data = request.json  # פירוק גוף הבקשה מ-JSON לdict פייתון
    locations = data.get("locations", []) if data else []  # שליפת רשימת הנקודות — רשימה ריקה אם חסרה

    if not locations:  # אם לא נשלחו נקודות — מחזיר שגיאה 400
        return jsonify({"error": "חסרות נקודות"}), 400

    locations = locations[:100]  # Open-Meteo מגביל ל-100 נקודות בבקשה אחת

    # בניית פרמטרי ה-URL — Open-Meteo מצפה לרשימות lat ו-lon מופרדות בפסיק
    lats = ",".join(str(p["latitude"])  for p in locations)  # "31.77,32.08,..." — כל קו הרוחב
    lons = ",".join(str(p["longitude"]) for p in locations)  # "35.21,34.78,..." — כל קו האורך

    for attempt in range(3):
        try:
            r = requests.get(
                "https://api.open-meteo.com/v1/elevation",
                params={"latitude": lats, "longitude": lons},
                timeout=30
            )
            if r.status_code == 429:
                reason = r.json().get("reason", "מכסת בקשות Open-Meteo הגיעה למגבלה")
                logging.warning(f"Open-Meteo rate limit (429): {reason}")
                return jsonify({"error": reason, "rate_limited": True}), 429
            r.raise_for_status()

            elevations = r.json().get("elevation", [])
            results = [
                {
                    "latitude":  locations[i]["latitude"],
                    "longitude": locations[i]["longitude"],
                    "elevation": elevations[i]
                }
                for i in range(min(len(locations), len(elevations)))
            ]
            return jsonify({"results": results})

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logging.warning(f"שגיאת חיבור/timeout לגבהים (ניסיון {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
            else:
                logging.error(f"שגיאה בשליפת גבהים לאחר 3 ניסיונות: {e}")
                return jsonify({"error": str(e)}), 500
        except Exception as e:
            logging.error(f"שגיאה בשליפת גבהים: {e}")
            return jsonify({"error": str(e)}), 500


@app.route("/temp_grid", methods=["POST"])
def get_temp_grid():
    """
    מקבל {southwest: {lat,lng}, northeast: {lat,lng}} ומחזיר רשת טמפרטורות ברזולוציה של 5 ק"מ.
    משתמש ב-Open-Meteo Forecast API — חינמי, ללא מפתח, תומך עד 1000 נקודות לבקשה.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "חסר גוף הבקשה"}), 400

    sw = data.get("southwest")
    ne = data.get("northeast")
    if not sw or not ne:
        return jsonify({"error": "חסרים southwest/northeast"}), 400

    mid_lat = (sw["lat"] + ne["lat"]) / 2.0
    cos_lat = math.cos(math.radians(mid_lat))  # תיקון לכיווץ קווי האורך ככל שמתרחקים מקו המשווה (מעלת lng קצרה יותר ב-km)

    # Start at 5 km resolution; scale up so total points stay under 500
    base_km = 5.0
    MAX_POINTS = 500
    lat_range_km = (ne["lat"] - sw["lat"]) * 111.0  # מעלת רוחב ≈ 111 ק"מ בכל מקום על הכדור
    lng_range_km = (ne["lng"] - sw["lng"]) * 111.0 * cos_lat  # מעלת אורך מתכווצת לפי cos(רוחב)
    n_lat = max(1, lat_range_km / base_km)
    n_lng = max(1, lng_range_km / base_km)
    if n_lat * n_lng > MAX_POINTS:  # האזור שנבחר גדול מדי לרזולוציה של 5 ק"מ — מגדילים את המרחק בין נקודות
        scale = math.sqrt((n_lat * n_lng) / MAX_POINTS)
        base_km *= scale

    lat_step = base_km / 111.0
    lon_step = base_km / (111.0 * cos_lat)

    lats, lons = [], []
    lat = sw["lat"]
    while lat <= ne["lat"] + lat_step * 0.01:  # +1% סבילות למניעת דילוג על השורה/עמודה האחרונה מחוסר דיוק float
        lon = sw["lng"]
        while lon <= ne["lng"] + lon_step * 0.01:
            lats.append(round(lat, 6))
            lons.append(round(lon, 6))
            lon += lon_step
        lat += lat_step

    if not lats:
        return jsonify({"error": "אזור קטן מדי"}), 400

    # batch_size=30 keeps URLs shorter; 500ms inter-batch pause prevents open-meteo connection resets
    results = []
    batch_size = 30
    for i in range(0, len(lats), batch_size):
        if i > 0:
            time.sleep(0.5)  # 500ms pause between batches to avoid connection resets
        bl = lats[i:i + batch_size]
        bn = lons[i:i + batch_size]
        for attempt in range(3):
            try:
                r = requests.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude":  ",".join(map(str, bl)),
                        "longitude": ",".join(map(str, bn)),
                        "current":   "temperature_2m",
                        "timezone":  "auto"
                    },
                    timeout=30
                )
                if r.status_code == 429:
                    reason = r.json().get("reason", "מכסת בקשות Open-Meteo הגיעה למגבלה")
                    logging.warning(f"Open-Meteo rate limit (429): {reason}")
                    return jsonify({"error": reason, "rate_limited": True}), 429
                r.raise_for_status()
                resp = r.json()

                if isinstance(resp, list):  # יותר מנקודה אחת ב-batch — Open-Meteo מחזיר מערך של תוצאות
                    for j, item in enumerate(resp):
                        temp = item.get("current", {}).get("temperature_2m")
                        if temp is not None:
                            results.append({"lat": bl[j], "lng": bn[j], "temperature": temp})
                else:  # נקודה בודדת — Open-Meteo מחזיר object יחיד ולא מערך
                    temp = resp.get("current", {}).get("temperature_2m")
                    if temp is not None:
                        results.append({"lat": bl[0], "lng": bn[0], "temperature": temp})
                break  # success — no retry needed

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
                logging.warning(f"חיבור נכשל (ניסיון {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))  # 2s / 4s backoff
                else:
                    logging.error(f"שגיאה בשליפת רשת טמפרטורות לאחר 3 ניסיונות: {e}")
                    return jsonify({"error": str(e)}), 500
            except Exception as e:
                logging.error(f"שגיאה בשליפת רשת טמפרטורות: {e}")
                return jsonify({"error": str(e)}), 500

    return jsonify(results)


def _haversine_m(lat1, lon1, lat2, lon2):
    """מרחק Haversine בין שתי נקודות, במטרים."""
    r = math.pi / 180  # מקדם המרה ממעלות לרדיאנים
    R = 6371000.0  # רדיוס כדור הארץ הממוצע, במטרים
    phi1, phi2 = lat1 * r, lat2 * r
    dphi = (lat2 - lat1) * r
    dlam = (lon2 - lon1) * r
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2  # נוסחת Haversine הסטנדרטית
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _interpolate_gc(lat1, lon1, lat2, lon2, frac):
    """נקודה על גדול-המעגל בין שתי נקודות, frac ∈ [0,1]."""
    if frac <= 0: return lat1, lon1  # קצוות מטופלים ישירות — מונע בעיות דיוק ב-sin/asin קרוב ל-0/1
    if frac >= 1: return lat2, lon2
    r = math.pi / 180
    phi1, lam1 = lat1 * r, lon1 * r
    phi2, lam2 = lat2 * r, lon2 * r
    d = 2 * math.asin(math.sqrt(  # d = הזווית הכוללת (ברדיאנים) בין שתי הנקודות על פני הכדור
        math.sin((phi2 - phi1) / 2) ** 2 +
        math.cos(phi1) * math.cos(phi2) * math.sin((lam2 - lam1) / 2) ** 2
    ))
    if d < 1e-10:
        return lat1, lon1  # שתי הנקודות זהות בפועל — מונע חלוקה באפס בהמשך
    a = math.sin((1 - frac) * d) / math.sin(d)  # אינטרפולציית spherical-slerp — משקל הנקודה הראשונה
    b = math.sin(frac * d) / math.sin(d)  # משקל הנקודה השנייה
    x = a * math.cos(phi1) * math.cos(lam1) + b * math.cos(phi2) * math.cos(lam2)  # המרה לקואורדינטות קרטזיות תלת-ממדיות, שקלול, והמרה חזרה
    y = a * math.cos(phi1) * math.sin(lam1) + b * math.cos(phi2) * math.sin(lam2)
    z = a * math.sin(phi1) + b * math.sin(phi2)
    lat = math.atan2(z, math.sqrt(x * x + y * y)) / r
    lon = math.atan2(y, x) / r
    return lat, lon


def _destination_point(lat, lon, bearing_deg, distance_m):
    """נקודת יעד ממקור נתון, לפי אזימוט (0=צפון, בכיוון השעון) ומרחק — קירוב כדורי,
    עקבי עם _haversine_m/_interpolate_gc (אותו R). משמש לבניית נקודות הדגימה לאורך
    כל קרן ברדיוס-הראייה הרדיאלי (בשונה מ-_interpolate_gc, שדורש שתי נקודות קצה
    ידועות מראש — כאן יודעים רק את המקור, ומחשבים את היעד מכיוון+מרחק)."""
    if distance_m <= 0:
        return lat, lon  # מרחק אפס — נקודת היעד היא המקור עצמו
    r = math.pi / 180  # מקדם המרה ממעלות לרדיאנים
    R = 6371000.0  # רדיוס כדור הארץ הממוצע, במטרים — מקומי, כמו ב-_haversine_m/_interpolate_gc
    phi1, lam1 = lat * r, lon * r  # קו רוחב/אורך המקור, ברדיאנים
    theta = bearing_deg * r  # אזימוט, ברדיאנים
    delta = distance_m / R  # מרחק זוויתי (רדיאנים) לאורך פני הכדור
    phi2 = math.asin(  # קו רוחב היעד — נוסחת "direct geodetic problem" כדורית סטנדרטית
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lam2 = lam1 + math.atan2(  # קו אורך היעד
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2)
    )
    lon2 = (lam2 / r + 540) % 360 - 180  # נרמול ל-[-180,180] — נדרש עקרונית ליד קו התאריך, זול לכלול תמיד
    return phi2 / r, lon2


def _horizon_ratchet(dists_m, elevs, h_obs, h_offsets, margin_slope=0.0, min_angle_slope=None, max_angle_slope=None):
    """ליבת אלגוריתם "מנוע האופק" (horizon ratchet) — משותפת בין /los ורדיוס-הראייה
    הרדיאלי, כך ששינוי עתידי בנוסחה (עקמומיות/רפרקציה) יתבצע במקום אחד בלבד.
    dists_m/elevs/h_offsets: 3 רשימות מקבילות באותו אורך; dists_m עולה מונוטונית ומתחיל ב-0.
    h_obs: גובה עין הצופה (elevation בנקודת המוצא + obs_h) — מחושב ע"י הקורא.
    h_offsets[i]: גובה נוסף מעל הקרקע בנקודה i לצורך בדיקת הנראות שלה — /los שם 0 בכל
        הנקודות חוץ מהאחרונה (tgt_h מתווסף רק ליעד עצמו), רדיוס-הראייה הרדיאלי שם tgt_h
        באופן אחיד בכל נקודה (כל נקודה לאורך קרן היא "יעד" פוטנציאלי).
    margin_slope: שיפוע מרווח ביטחון נוסף שחייבים "לנצח" מעבר לרכס הגבוה ביותר שנצפה —
        0.0 = בקושי לעבור את הרכס (התנהגות /los המקורית) מספיק.
    min_angle_slope/max_angle_slope: הגבלת שדה-ראייה אנכי אופציונלית (כמו זווית עילוי
        מוגבלת של חיישן/אנטנה) — None = לא מוגבל (התנהגות /los המקורית).
    מחזיר רשימת dict מקבילה: [{'dist_m','elevation','los_h','visible'}, ...]."""
    R = 6371000.0  # רדיוס כדור הארץ, במטרים
    k = 0.13  # מקדם שבירה אטמוספרי
    max_angle = -float('inf')  # זווית "קו האופק" הגבוה ביותר שנצפה עד כה — **מהקרקע הגולמית בלבד** (h_offset=0),
    # לא כוללת את h_offsets[i] — אחרת, כש-h_offset מוחל על כמה נקודות ברצף (כמו ברדיוס-ראייה רדיאלי),
    # האופק "מזהם" את עצמו בבליטה של הנקודה הקודמת, וזווית הבדיקה (שיורדת עם המרחק לבליטה קבועה
    # על קרקע ישרה) לעולם לא מצליחה להדביק אותו — הכל נחסם בהדרגה גם בלי שום מכשול אמיתי (נמצא בבדיקה חיה).
    out = []
    for i, d in enumerate(dists_m):
        elev = elevs[i]  # גובה קרקע גולמי בנקודה הזו
        drop = d * d / (2 * R) * (1 - k)  # ירידת קו הראייה בגלל עקמומיות+רפרקציה
        if d == 0:
            visible, los_h = True, h_obs  # נקודת המוצא עצמה — תמיד גלויה, ללא עיגול (תואם להתנהגות /los הקיימת)
        else:
            bare_angle = (elev - drop - h_obs) / d  # זווית הקרקע הגולמית (בלי h_offset) — בונה את קו האופק
            test_angle = (elev + h_offsets[i] - drop - h_obs) / d  # זווית הנקודה הנבדקת בפועל (כולל h_offset שלה) — נבדקת מול האופק
            visible = test_angle >= max_angle + margin_slope  # חייב "לנצח" את קו האופק הגולמי + מרווח הביטחון
            if min_angle_slope is not None and test_angle < min_angle_slope:
                visible = False  # מתחת לתחתית שדה-הראייה האנכי המותר — לא גלוי, גם אם לא חסום ע"י שטח
            if max_angle_slope is not None and test_angle > max_angle_slope:
                visible = False  # מעל חלק שדה-הראייה האנכי המותר — לא גלוי, גם אם לא חסום ע"י שטח
            if bare_angle > max_angle:
                max_angle = bare_angle  # עדכון קו האופק — תמיד לפי הקרקע הגולמית, לא תלוי ב-h_offset/margin/visible
            los_h = round(h_obs + max_angle * d, 1)
        out.append({'dist_m': d, 'elevation': elev, 'los_h': los_h, 'visible': visible})
    return out


def _fetch_elevations(locations):
    """שולף גבהים לרשימת נקודות שרירותית [{'lat','lon'},...] (עד 100, מגבלת Open-Meteo),
    עם retry+backoff על timeout/ניתוק (כמו /elevation) — helper משותף לשליפת גובה
    המשקיף הבודד ולכל batch בסריקה הרדיאלית. מחזיר (רשימת גבהים מקבילה, שגיאה-או-None);
    ברשימת הגבהים None בכל אינדקס שנכשל בפועל (לא מפיל את כל הקריאה על כשל בודד)."""
    lats_str = ','.join(str(p['lat']) for p in locations)  # רשימת קווי רוחב, מופרדים בפסיק — פורמט Open-Meteo
    lons_str = ','.join(str(p['lon']) for p in locations)  # רשימת קווי אורך, מופרדים בפסיק
    for attempt in range(3):  # עד 3 ניסיונות, כמו /elevation
        try:
            r = requests.get(
                'https://api.open-meteo.com/v1/elevation',
                params={'latitude': lats_str, 'longitude': lons_str},
                timeout=30
            )
            if r.status_code == 429:  # מכסת בקשות — לא retry, מחזירים שגיאה מיידית (כמו /elevation)
                reason = r.json().get('reason', 'מכסת בקשות Open-Meteo הגיעה למגבלה')
                return None, {'error': reason, 'rate_limited': True}
            r.raise_for_status()
            elevs = r.json().get('elevation', [])
            # ממלא None בכל אינדקס חסר (תגובה קצרה מהמצופה) — לא זורק שגיאה, הקורא מטפל בערכי None
            return [elevs[i] if i < len(elevs) else None for i in range(len(locations))], None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))  # 0.5/1 שנ' — כמו /elevation
            else:
                return None, {'error': str(e)}
        except Exception as e:
            return None, {'error': str(e)}
    return None, {'error': 'נכשל אחרי 3 ניסיונות'}


@app.route("/los", methods=["GET"])
def line_of_sight():
    """
    חישוב קו ראייה בין שתי נקודות עם תיקון עקמומיות כדור הארץ.
    גובה מצפה: גובה קרקע + 11 מ'. דגימה כל 5 ק"מ עד 500 ק"מ.
    """
    try:
        lat1 = float(request.args.get('lat1'))
        lon1 = float(request.args.get('lon1'))
        lat2 = float(request.args.get('lat2'))
        lon2 = float(request.args.get('lon2'))
    except (TypeError, ValueError):
        return jsonify({"error": "פרמטרים חסרים"}), 400

    try:
        obs_h = float(request.args.get('obs_h', 11.0))  # גובה הצופה מעל הקרקע (מ') — ברירת מחדל 11
    except (TypeError, ValueError):
        obs_h = 11.0
    try:
        tgt_h = float(request.args.get('tgt_h', 0.0))  # גובה היעד מעל הקרקע (מ') — ברירת מחדל קרקע
    except (TypeError, ValueError):
        tgt_h = 0.0

    step_m = 5000.0     # דגימת גובה כל 5 ק"מ לאורך הקו
    max_m  = 500000.0   # תקרת מרחק — 500 ק"מ

    total_m = min(_haversine_m(lat1, lon1, lat2, lon2), max_m)  # חותך למקסימום גם אם המרחק בפועל גדול יותר
    n = max(2, int(total_m / step_m) + 1)  # מספר נקודות הדגימה — לפחות 2 (שתי הקצוות)
    n = min(n, 100)  # תקרה — Open-Meteo Elevation לא תומך ביותר מ-100 נקודות בבקשה

    pts = []
    for i in range(n):
        frac = i / (n - 1) if n > 1 else 0.0  # חלק יחסי לאורך הקו, 0..1
        lat, lon = _interpolate_gc(lat1, lon1, lat2, lon2, frac)
        pts.append({'lat': round(lat, 6), 'lon': round(lon, 6), 'dist_m': total_m * frac})

    lats_str = ','.join(str(p['lat']) for p in pts)
    lons_str = ','.join(str(p['lon']) for p in pts)
    try:
        r = requests.get(
            'https://api.open-meteo.com/v1/elevation',
            params={'latitude': lats_str, 'longitude': lons_str},
            timeout=30
        )
        r.raise_for_status()
        elevs = r.json().get('elevation', [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(elevs) < len(pts):
        return jsonify({'error': 'נתוני גובה חסרים'}), 500

    h_obs = elevs[0] + obs_h  # גובה עין המצפה = גובה קרקע בנקודת ההתחלה + גובה עמידה
    # גובה היעד מתווסף רק לנקודה האחרונה — נקודות ביניים נשארות גובה קרקע גולמי (מכשולים), לא "יעד"
    h_offsets = [0.0] * (n - 1) + [tgt_h]
    # קורא לליבת האלגוריתם המשותפת (_horizon_ratchet) — ללא margin/הגבלת זווית אנכית כאן,
    # כדי לשמר בדיוק את התנהגות /los המקורית (margin_slope=0, min/max_angle_slope=None)
    ratchet = _horizon_ratchet([p['dist_m'] for p in pts], elevs, h_obs, h_offsets)
    first_block_m = next((r['dist_m'] for r in ratchet if not r['visible']), None)  # המרחק הראשון החסום, None אם הכל גלוי

    result = [
        {
            'lat':       pts[i]['lat'],
            'lon':       pts[i]['lon'],
            'dist_km':   round(ratchet[i]['dist_m'] / 1000, 2),
            'elevation': ratchet[i]['elevation'],
            'los_h':     ratchet[i]['los_h'],
            'visible':   ratchet[i]['visible'],
        }
        for i in range(n)
    ]

    return jsonify({
        'points':         result,
        'total_km':       round(total_m / 1000, 2),
        'observer_elev':  elevs[0],
        'observer_h':     round(h_obs, 1),
        'target_elev':    elevs[-1],
        'target_h':       round(elevs[-1] + tgt_h, 1),
        'first_block_km': round(first_block_m / 1000, 2) if first_block_m is not None else None,
        'all_visible':    first_block_m is None
    })


# ── רדיוס-ראייה רדיאלי (Viewshed מכומת) — job ברקע + polling + ביטול ──
# בשונה מ-/los (בקשה חוסמת אחת), כאן זמן החישוב עלול להגיע לכמה דקות (עד אלפי נקודות
# גובה, ב-batches מרווחים) — לכן מריצים ב-thread נפרד ומאפשרים למשתמש לעקוב אחרי
# התקדמות ולבטל, בלי לחסום בקשות אחרות (weather_server.py כבר threaded=True).
_radial_jobs = {}  # job_id -> dict מצב (status/batches_done/batches_total/result/error/cancelled/created)
_radial_jobs_lock = threading.Lock()  # מגן על _radial_jobs מגישה בו-זמנית (worker threads + start/status/cancel)

_RADIAL_RANGE_KM_MIN, _RADIAL_RANGE_KM_MAX = 0.5, 300.0  # טווח מרחק מותר, ק"מ
_RADIAL_ANGLE_STEP_MIN, _RADIAL_ANGLE_STEP_MAX = 3.0, 45.0  # צעד זווית מותר, מעלות
_RADIAL_RIDGE_MARGIN_MIN, _RADIAL_RIDGE_MARGIN_MAX = 0.0, 10.0  # מרווח רכס מותר, מעלות
_RADIAL_BASE_BUDGET = 720  # תקציב נקודות ל"רזולוציה גבוהה בטווח קצר" (כמו התקרה שהייתה קבועה במקור)
_RADIAL_TARGET_SPACING_KM = 2.0  # מרווח יעד בין דגימות לאורך קרן, גובר בטווח ארוך
_RADIAL_SAMPLES_MIN, _RADIAL_SAMPLES_MAX = 8, 150  # רצפת/תקרת דגימות לקרן בודדת
_RADIAL_MAX_TOTAL_POINTS = 4000  # תקרת נקודות כוללת — גובלת את זמן התגובה המרבי
_RADIAL_BATCH_SIZE = 30  # נקודות לכל בקשת batch — כמו /temp_grid
_RADIAL_BATCH_PAUSE_SEC = 0.5  # השהיה בין batches — כמו /temp_grid, מונע חסימת Open-Meteo
_RADIAL_JOB_TTL_SEC = 600  # jobs שהסתיימו ולא נשאלו יותר מ-10 דק' מנוקים, כדי לא לדלוף זיכרון
_RADIAL_VERTICAL_CENTER_DEFAULT_DEG = 0.0  # ברירת מחדל למרכז שדה-הראייה האנכי (0°=אופקי) — ניתן לשינוי ע"י המשתמש
_RADIAL_VERTICAL_WIDTH_DEFAULT_DEG = 4.0  # ברירת מחדל לרוחב שדה-הראייה האנכי הכולל (±2° מהמרכז)
_RADIAL_VERTICAL_CENTER_MIN, _RADIAL_VERTICAL_CENTER_MAX = -45.0, 45.0  # טווח מותר למרכז האלומה, מעלות
_RADIAL_VERTICAL_WIDTH_MIN, _RADIAL_VERTICAL_WIDTH_MAX = 1.0, 90.0  # טווח מותר לרוחב האלומה, מעלות
_RADIAL_MIN_RANGE_KM_DEFAULT = 5.0  # טווח מינימלי ("אזור עיוור") כברירת מחדל — בלעדיו, אלומה צרה (4°)
# ממשקיף נמוך תמיד "נחסמת" מיד ליד המשקיף (זווית תלולה גיאומטרית מתחייבת מקרוב) — ר' תוכנית


def _cleanup_old_radial_jobs():
    """מוחק jobs שהסתיימו (הצליחו/נכשלו/בוטלו) ועברו מעל _RADIAL_JOB_TTL_SEC מאז יצירתם —
    נקרא בתחילת כל /los_radial/start כדי שרשימת ה-jobs לא תגדל ללא הגבלה בתהליך ארוך-חי.
    חייב להיקרא כשה-lock כבר תפוס (לא נועל בעצמו)."""
    now = time.time()  # זמן נוכחי — להשוואה מול 'created' של כל job
    stale = [
        jid for jid, job in _radial_jobs.items()
        if job['status'] in ('done', 'error', 'cancelled') and now - job['created'] > _RADIAL_JOB_TTL_SEC
    ]
    for jid in stale:
        del _radial_jobs[jid]  # מחיקה בפועל מהמילון המשותף


def _radial_worker(job_id, obs_lat, obs_lon, range_km, angle_step_deg, start_bearing_deg, end_bearing_deg,
                    obs_h, tgt_h, ridge_margin_deg, min_range_km, vertical_center_deg, vertical_width_deg):
    """רץ ב-thread נפרד (daemon) — כל החישוב הכבד של רדיוס-הראייה הרדיאלי, מעדכן את
    מצב ה-job תחת _radial_jobs_lock תוך כדי ריצה כדי שקריאות /status יראו התקדמות חיה."""
    try:
        range_m = range_km * 1000.0  # המרת הטווח מק"מ למטרים — יחידות _destination_point/_horizon_ratchet
        min_range_m = min_range_km * 1000.0  # המרת הטווח המינימלי מק"מ למטרים — תחילת הדגימה לאורך כל קרן

        # שלב 1: גובה המשקיף עצמו — בנפרד, לפני הכל, נכשל-מהר אם לא זמין (בלי טעם להמשיך בלעדיו)
        obs_elevs, err = _fetch_elevations([{'lat': obs_lat, 'lon': obs_lon}])
        if err or obs_elevs is None or obs_elevs[0] is None:
            with _radial_jobs_lock:
                _radial_jobs[job_id]['status'] = 'error'
                _radial_jobs[job_id]['error'] = (err or {}).get('error', 'לא ניתן לשלוף את גובה המשקיף')
            return
        observer_elev = obs_elevs[0]  # גובה קרקע גולמי בנקודת המשקיף
        h_obs = observer_elev + obs_h  # גובה עין המשקיף בפועל

        # שלב 2: בניית כיווני הסריקה (bearings) — תמיכה במגזר חלקי + "עטיפה" מעל 360°/0°
        span = (end_bearing_deg - start_bearing_deg) % 360  # רוחב המגזר במעלות, 0-360
        if span == 0:
            span = 360  # start==end פירושו "הכל" (מעגל מלא), לא מגזר ברוחב אפס
        n_bearings = max(1, round(span / angle_step_deg))  # מספר הכיוונים בפועל
        angle_step_deg = span / n_bearings  # שלב אפקטיבי — מחלק את המגזר בדיוק, בלי "תפר" בקצה
        bearings = [(start_bearing_deg + i * angle_step_deg) % 360 for i in range(n_bearings)]  # רשימת האזימוטים לבדיקה

        # שלב 3: צפיפות דגימה — מרבי בין "תקציב לפי מספר כיוונים" (טובה בטווח קצר) לבין
        # "מרווח יעד קבוע" (טובה בטווח ארוך), עם תקרת נקודות כוללת שגוברת בשילובים קיצוניים
        budget_based = min(20, max(_RADIAL_SAMPLES_MIN, _RADIAL_BASE_BUDGET // n_bearings))
        spacing_based = round((range_km - min_range_km) / _RADIAL_TARGET_SPACING_KM) + 1  # רק טווח הדגימה בפועל (לא כולל אזור עיוור)
        samples_per_ray = max(_RADIAL_SAMPLES_MIN, min(_RADIAL_SAMPLES_MAX, max(budget_based, spacing_based)))
        if n_bearings * samples_per_ray > _RADIAL_MAX_TOTAL_POINTS:  # שילוב קיצוני (טווח ארוך + צעד עדין) — מצמצם
            samples_per_ray = max(_RADIAL_SAMPLES_MIN, _RADIAL_MAX_TOTAL_POINTS // n_bearings)

        # שלב 4: בניית כל נקודות הדגימה מראש (כל כיוון × כל מרחק דגימה לאורכו) — רשימה שטוחה אחת
        all_points = []  # בסדר: קרן 0 (כל דגימותיה), קרן 1 (כל דגימותיה), ...
        for bearing in bearings:
            for j in range(samples_per_ray):
                # מרחק הדגימה ה-j לאורך הקרן — מתחיל ב-min_range_m (לא 0!) ומגיע עד range_m.
                # min_range_km=0 נותן dist=0 בדגימה הראשונה בדיוק כמו קודם (תאימות לאחור מלאה).
                frac = j / (samples_per_ray - 1) if samples_per_ray > 1 else 0.0
                dist = min_range_m + frac * (range_m - min_range_m)
                plat, plon = _destination_point(obs_lat, obs_lon, bearing, dist)  # נקודת הדגימה בפועל
                all_points.append({'lat': round(plat, 6), 'lon': round(plon, 6), 'dist_m': dist})

        # שלב 5: שליפת גבהים ב-batches, עם השהיה ביניהם — עדכון התקדמות אחרי כל batch
        total_batches = (len(all_points) + _RADIAL_BATCH_SIZE - 1) // _RADIAL_BATCH_SIZE  # ceiling division
        with _radial_jobs_lock:
            _radial_jobs[job_id]['batches_total'] = total_batches  # מאפשר ל-JS להציג "X מתוך Y"
        elevations = [None] * len(all_points)  # מקביל ל-all_points; None = נקודה שלא נשלף עבורה גובה
        for batch_idx in range(total_batches):
            with _radial_jobs_lock:
                if _radial_jobs[job_id]['cancelled']:  # בדיקת ביטול בין כל batch — תגובתיות סבירה לכפתור "בטל"
                    _radial_jobs[job_id]['status'] = 'cancelled'
                    return
            if batch_idx > 0:
                time.sleep(_RADIAL_BATCH_PAUSE_SEC)  # השהיה בין batches — לא לפני הראשון
            batch = all_points[batch_idx * _RADIAL_BATCH_SIZE:(batch_idx + 1) * _RADIAL_BATCH_SIZE]
            batch_elevs, err = _fetch_elevations(batch)
            if err and err.get('rate_limited'):  # 429 — עוצר את כל ה-job (כמו /elevation ו-/temp_grid)
                with _radial_jobs_lock:
                    _radial_jobs[job_id]['status'] = 'error'
                    _radial_jobs[job_id]['error'] = err.get('error')
                return
            if batch_elevs is not None:  # כשל חלקי (לא 429) — משאיר None בנקודות האלה וממשיך, לא מפיל את כל ה-job
                for k, elev in enumerate(batch_elevs):
                    elevations[batch_idx * _RADIAL_BATCH_SIZE + k] = elev
            with _radial_jobs_lock:
                _radial_jobs[job_id]['batches_done'] = batch_idx + 1  # עדכון התקדמות אחרי כל batch, הצלחה או כשל חלקי

        # שלב 6: פירוק בחזרה לפי קרן, הרצת ה-ratchet לכל קרן בנפרד (מקומית — בלי עוד קריאות רשת)
        margin_slope = math.tan(math.radians(ridge_margin_deg))  # המרת מרווח הרכס ממעלות לשיפוע
        v_half = vertical_width_deg / 2.0  # חצי רוחב שדה-הראייה האנכי, סביב המרכז שנבחר (ר' עדכון מ-18/08/2026 — הוצג כשדה ניתן-לשינוי)
        min_angle_slope = math.tan(math.radians(vertical_center_deg - v_half))  # גבול תחתון, כשיפוע
        max_angle_slope = math.tan(math.radians(vertical_center_deg + v_half))  # גבול עליון, כשיפוע
        rays = []  # תוצאה סופית — רשומה אחת לכל אזימוט
        clear_count = 0  # כמה קרניים הגיעו פנויות לגמרי עד הטווח המלא
        failed_rays = 0  # כמה קרניים חסרות נתונים חלקיים (batch שנכשל)
        for ray_idx, bearing in enumerate(bearings):
            ray_points = all_points[ray_idx * samples_per_ray:(ray_idx + 1) * samples_per_ray]  # נקודות הדגימה של הקרן הזו
            ray_elevs = elevations[ray_idx * samples_per_ray:(ray_idx + 1) * samples_per_ray]  # הגבהים המקבילים
            surviving = [(p, e) for p, e in zip(ray_points, ray_elevs) if e is not None]  # מסנן נקודות בלי גובה, שומר סדר
            samples_ok = len(surviving)
            if samples_ok < 2:  # אין מספיק נתונים בכלל לאורך הקרן הזו
                rays.append({'bearing_deg': round(bearing, 3), 'clear_dist_km': 0.0, 'lat': obs_lat, 'lon': obs_lon,
                             'blocked': True, 'ok': False, 'samples_ok': samples_ok})
                failed_rays += 1
                continue
            dists = [p['dist_m'] for p, _ in surviving]  # מרחקי הדגימות ששרדו, לפי סדר עולה
            elevs_only = [e for _, e in surviving]  # הגבהים המקבילים
            h_offsets = [tgt_h] * len(surviving)  # tgt_h מוחל על כל נקודה — כל נקודה היא "יעד" פוטנציאלי כאן, לא רק האחרונה
            ratchet = _horizon_ratchet(dists, elevs_only, h_obs, h_offsets, margin_slope, min_angle_slope, max_angle_slope)
            # קודקוד הקרן = הנקודה הגלויה **הרחוקה ביותר**, לא בהכרח רציפה מהקצה הקרוב (עודכן לפי
            # החלטת המשתמש אחרי בדיקה חיה, 18/08/2026 — ר' "תקלה שנמצאה" בתוכנית). לפני העדכון,
            # הליכה שנעצרה בכישלון הראשון פספסה קטע ראייה אמיתי באמצע הטווח (קורה בעיקר עם tgt_h
            # גדול+קבוע ביחד עם אלומה אנכית צרה, ששם הזווית הנדרשת *יורדת* עם המרחק — לא כמו רכס אמיתי).
            clear_dist_m, clear_lat, clear_lon = 0.0, obs_lat, obs_lon  # ברירת מחדל — אף נקודה לא נמצאה גלויה
            for i, rr in enumerate(ratchet):
                if rr['visible']:  # כל נקודה גלויה נבדקת בנפרד — לא עוצרים בראשונה הלא-גלויה
                    clear_dist_m = rr['dist_m']  # dists_m עולה מונוטונית, אז זו תמיד הגלויה-הרחוקה-ביותר-עד-כה
                    clear_lat, clear_lon = surviving[i][0]['lat'], surviving[i][0]['lon']
            blocked = not ratchet[-1]['visible']  # "פנוי לגמרי" רק אם הנקודה הרחוקה ביותר בקרן עצמה גלויה
            if not blocked:
                clear_count += 1
            rays.append({'bearing_deg': round(bearing, 3), 'clear_dist_km': round(clear_dist_m / 1000, 3),
                         'lat': clear_lat, 'lon': clear_lon, 'blocked': blocked,
                         'ok': samples_ok == samples_per_ray, 'samples_ok': samples_ok})
            if samples_ok != samples_per_ray:
                failed_rays += 1

        result = {  # תוצאת ה-job הסופית — נקראת ע"י /los_radial/status כש-status=='done'
            'observer_lat': obs_lat, 'observer_lon': obs_lon, 'observer_elev': observer_elev,
            'observer_h': round(h_obs, 1), 'obs_h': obs_h, 'tgt_h': tgt_h, 'ridge_margin_deg': ridge_margin_deg,
            'range_km': range_km, 'min_range_km': min_range_km, 'angle_step_deg': round(angle_step_deg, 3),
            'vertical_center_deg': vertical_center_deg, 'vertical_width_deg': vertical_width_deg,
            'start_bearing_deg': start_bearing_deg, 'end_bearing_deg': end_bearing_deg, 'span_deg': span,
            'n_bearings': n_bearings, 'samples_per_ray': samples_per_ray,
            'clear_count': clear_count, 'failed_rays': failed_rays, 'rays': rays,
        }
        with _radial_jobs_lock:
            _radial_jobs[job_id]['status'] = 'done'
            _radial_jobs[job_id]['result'] = result
    except Exception as e:  # רשת ביטחון — כשל בלתי-צפוי לא ישאיר את ה-job תקוע ב-'running' לנצח
        logging.error(f"שגיאה בחישוב רדיוס ראייה רדיאלי (job {job_id}): {e}")
        with _radial_jobs_lock:
            _radial_jobs[job_id]['status'] = 'error'
            _radial_jobs[job_id]['error'] = str(e)


@app.route("/los_radial/start", methods=["GET"])
def start_radial_los():
    """מתחיל job חדש של רדיוס-ראייה רדיאלי ברקע, מחזיר job_id מיידית (לא מחכה לתוצאה) —
    ר' /los_radial/status לבדיקת התקדמות ו-/los_radial/cancel לביטול."""
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "פרמטרים חסרים"}), 400

    try:
        range_km = float(request.args.get('range_km', 5.0))  # טווח מרחק, ק"מ — ברירת מחדל 5
    except (TypeError, ValueError):
        range_km = 5.0
    range_km = min(max(range_km, _RADIAL_RANGE_KM_MIN), _RADIAL_RANGE_KM_MAX)  # נצמד לטווח המותר, לא נדחה

    try:  # טווח מינימלי ("אזור עיוור") — בלעדיו, אלומה צרה תמיד תיחסם מיד ליד משקיף נמוך (ר' תוכנית)
        min_range_km = float(request.args.get('min_range_km', _RADIAL_MIN_RANGE_KM_DEFAULT))
    except (TypeError, ValueError):
        min_range_km = _RADIAL_MIN_RANGE_KM_DEFAULT
    min_range_km = min(max(min_range_km, 0.0), range_km)  # לא שלילי, ולא גדול מהטווח המקסימלי עצמו

    try:
        angle_step_deg = float(request.args.get('angle_step_deg', 10.0))  # צעד זווית, מעלות — ברירת מחדל 10
    except (TypeError, ValueError):
        angle_step_deg = 10.0
    angle_step_deg = min(max(angle_step_deg, _RADIAL_ANGLE_STEP_MIN), _RADIAL_ANGLE_STEP_MAX)

    try:
        ridge_margin_deg = float(request.args.get('ridge_margin_deg', 0.0))  # מרווח רכס, מעלות — ברירת מחדל 0
    except (TypeError, ValueError):
        ridge_margin_deg = 0.0
    ridge_margin_deg = min(max(ridge_margin_deg, _RADIAL_RIDGE_MARGIN_MIN), _RADIAL_RIDGE_MARGIN_MAX)

    try:  # אזימוט התחלה — לא נצמד לטווח קבוע, % 360 בהמשך כבר מנרמל כל ערך (גם שלילי/מעל 360)
        start_bearing_deg = float(request.args.get('start_bearing_deg', 0.0))
    except (TypeError, ValueError):
        start_bearing_deg = 0.0
    try:  # אזימוט סיום — ברירת מחדל 360 (יחד עם 0 למעלה = מעגל מלא כברירת מחדל)
        end_bearing_deg = float(request.args.get('end_bearing_deg', 360.0))
    except (TypeError, ValueError):
        end_bearing_deg = 360.0
    try:
        obs_h = float(request.args.get('obs_h', 11.0))  # גובה המשקיף, מ' — ברירת מחדל 11, כמו /los
    except (TypeError, ValueError):
        obs_h = 11.0
    try:
        tgt_h = float(request.args.get('tgt_h', 0.0))  # גובה היעד/מכשול, מ' — ברירת מחדל 0
    except (TypeError, ValueError):
        tgt_h = 0.0

    try:  # מרכז שדה-הראייה האנכי, מעלות — ברירת מחדל 0 (אופקי). נחשף כשדה בפאנל מ-18/08/2026
        vertical_center_deg = float(request.args.get('vertical_center_deg', _RADIAL_VERTICAL_CENTER_DEFAULT_DEG))
    except (TypeError, ValueError):
        vertical_center_deg = _RADIAL_VERTICAL_CENTER_DEFAULT_DEG
    vertical_center_deg = min(max(vertical_center_deg, _RADIAL_VERTICAL_CENTER_MIN), _RADIAL_VERTICAL_CENTER_MAX)

    try:  # רוחב שדה-הראייה האנכי הכולל, מעלות — ברירת מחדל 4° (±2°)
        vertical_width_deg = float(request.args.get('vertical_width_deg', _RADIAL_VERTICAL_WIDTH_DEFAULT_DEG))
    except (TypeError, ValueError):
        vertical_width_deg = _RADIAL_VERTICAL_WIDTH_DEFAULT_DEG
    vertical_width_deg = min(max(vertical_width_deg, _RADIAL_VERTICAL_WIDTH_MIN), _RADIAL_VERTICAL_WIDTH_MAX)

    job_id = str(uuid.uuid4())  # מזהה ייחודי ל-job הזה
    with _radial_jobs_lock:
        _cleanup_old_radial_jobs()  # ניקוי jobs ישנים לפני הוספת חדש — מונע דליפת זיכרון בתהליך ארוך-חי
        _radial_jobs[job_id] = {
            'status': 'running', 'batches_done': 0, 'batches_total': None,
            'result': None, 'error': None, 'cancelled': False, 'created': time.time(),
        }
    thread = threading.Thread(  # מריץ את כל החישוב ב-thread נפרד — הבקשה הזו חוזרת מיד, לא מחכה
        target=_radial_worker,
        args=(job_id, lat, lon, range_km, angle_step_deg, start_bearing_deg, end_bearing_deg, obs_h, tgt_h,
              ridge_margin_deg, min_range_km, vertical_center_deg, vertical_width_deg),
        daemon=True,  # daemon — לא מונע יציאה מהתהליך אם השרת נסגר תוך כדי ריצה
    )
    thread.start()
    return jsonify({'job_id': job_id})


@app.route("/los_radial/status", methods=["GET"])
def radial_los_status():
    """מחזיר את מצב ה-job הנוכחי — status/batches_done/batches_total/result (result רק כש-status=='done')."""
    job_id = request.args.get('job_id')  # מזהה ה-job שהתקבל מ-/los_radial/start
    with _radial_jobs_lock:
        job = _radial_jobs.get(job_id)
        if job is None:  # job_id לא קיים — למשל נוקה כבר, או מזהה שגוי
            return jsonify({'error': 'job לא נמצא (אולי נוקה, או job_id שגוי)'}), 404
        return jsonify({
            'status': job['status'], 'batches_done': job['batches_done'],
            'batches_total': job['batches_total'], 'result': job['result'], 'error': job['error'],
        })


@app.route("/los_radial/cancel", methods=["POST"])
def cancel_radial_los():
    """מסמן job לביטול — ה-worker בודק את הדגל בין כל batch ועוצר בהתאם (ר' _radial_worker)."""
    job_id = request.args.get('job_id')  # מזהה ה-job לביטול
    with _radial_jobs_lock:
        if job_id in _radial_jobs:  # מתעלם בשקט אם ה-job כבר לא קיים (למשל הסתיים/נוקה) — אין מה לבטל
            _radial_jobs[job_id]['cancelled'] = True
    return jsonify({'ok': True})


# ── תצפית מכ"ם דופלר (רעיוני/חינוכי, לא מבוסס מערכת אמיתית ספציפית) — כלי שלישי, נפרד ──
# אותו רעיון כמו רדיוס-ראייה רדיאלי למעלה (משקיף, כל הכיוונים, "עד כמה רואים"), עם עוד
# 3 שכבות חישוב מעליו: משוואת מכ"ם (כמה רחוק המכ"ם חזק מספיק לראות), דופלר (האם המטרה
# זזה בצורה שמתגלה), ותפוצה (השתקפות קרקע). קבועי ברירת מחדל וגבולות לכל פרמטר:
_RADAR_RANGE_KM_DEFAULT = 50.0  # טווח בדיקה — שונה מרדיוס-הראייה (5) כי מכ"ם טיפוסי סורק רחוק יותר
_RADAR_H_ANTENNA_DEFAULT_M = 15.0  # גובה אנטנה ברירת מחדל
_RADAR_VBEAM_CENTER_DEFAULT_DEG = 0.0  # מרכז שדה-ראייה אנכי — אופקי כברירת מחדל
_RADAR_VBEAM_WIDTH_DEFAULT_DEG = 10.0  # רוחב שדה-ראייה אנכי — רחב יותר מרדיוס-הראייה (4°)
_RADAR_MIN_RANGE_KM_DEFAULT = 1.0  # "טווח מת" ברירת מחדל

_RADAR_POWER_KW_DEFAULT, _RADAR_POWER_KW_MIN, _RADAR_POWER_KW_MAX = 100.0, 0.1, 5000.0  # הספק שידור שיא, קילוואט
_RADAR_GAIN_DBI_DEFAULT, _RADAR_GAIN_DBI_MIN, _RADAR_GAIN_DBI_MAX = 30.0, 0.0, 50.0  # רווח אנטנה, dBi
_RADAR_FREQ_MHZ_DEFAULT, _RADAR_FREQ_MHZ_MIN, _RADAR_FREQ_MHZ_MAX = 3000.0, 100.0, 20000.0  # תדר עבודה, MHz — ברירת מחדל S-band
_RADAR_SENSITIVITY_DBM_DEFAULT, _RADAR_SENSITIVITY_DBM_MIN, _RADAR_SENSITIVITY_DBM_MAX = -100.0, -140.0, -60.0  # רגישות מקלט, dBm
_RADAR_SYSTEM_LOSSES_DB = 6.0  # הפסדי מערכת — קבוע, לא נחשף כשדה למשתמש
_RADAR_RCS_M2_DEFAULT, _RADAR_RCS_M2_MIN, _RADAR_RCS_M2_MAX = 2.0, 0.001, 1000.0  # שטח חתך רדארי, מ"ר — ברירת מחדל "מטוס קל"

_RADAR_PRF_HZ_DEFAULT, _RADAR_PRF_HZ_MIN, _RADAR_PRF_HZ_MAX = 1000.0, 50.0, 20000.0  # תדר חזרת פולסים, Hz
_RADAR_MDV_KT_DEFAULT, _RADAR_MDV_KT_MIN, _RADAR_MDV_KT_MAX = 20.0, 0.0, 200.0  # מהירות רדיאלית מינימלית לגילוי, קשר
_RADAR_TARGET_SPEED_KT_DEFAULT, _RADAR_TARGET_SPEED_KT_MIN, _RADAR_TARGET_SPEED_KT_MAX = 250.0, 0.0, 1500.0  # מהירות המטרה המשוערת, קשר
_RADAR_TARGET_HEADING_DEG_DEFAULT = 0.0  # כיוון תנועת המטרה המשוער — צפונה כברירת מחדל
_RADAR_BLIND_SPEED_TOLERANCE_FRAC = 0.05  # "קרוב מדי" למהירות עיוורת = בתוך 5% ממנה
_KT_TO_MS = 0.514444  # מקדם המרה קשר -> מטר/שנייה

_RADAR_REFLECTIVITY = {'land': 0.5, 'sea': 0.9}  # מקדם החזרה מפושט לפי סוג משטח — להדגמה בלבד, לא ערך פיזיקלי מדויק
_RADAR_REFLECTIVITY_DEFAULT = 'land'
_RADAR_JOB_TTL_SEC = 600  # ניקוי jobs ישנים אחרי 10 דק', כמו _RADIAL_JOB_TTL_SEC

# ── סוג אנטנה: גנרי (רווח קבוע לכל אזימוט) מול מערך-מופעים (phased array) — נבחר ע"י המשתמש בפאנל ──
# מכ"ם מערך-מופעים אמיתי מנווט את הקרן אלקטרונית מסביב לכיוון-פנים קבוע (boresight) — הרווח האפקטיבי
# יורד ככל שמסטים מכיוון הפנים (הפסד סריקה, "cosine loss"), ומעבר לזווית סריקה מקסימלית (טיפוסית ~60°)
# האנטנה כלל לא מכסה את הכיוון הזה. גנרי = בלי אף אחת מהתופעות האלה (רווח אחיד בכל הכיוונים).
_RADAR_ANTENNA_TYPES = ('generic', 'phased_array')
_RADAR_ANTENNA_TYPE_DEFAULT = 'generic'
_RADAR_BORESIGHT_DEG_DEFAULT = 0.0  # כיוון-פנים של המערך — צפונה כברירת מחדל
_RADAR_MAX_SCAN_DEG_DEFAULT, _RADAR_MAX_SCAN_DEG_MIN, _RADAR_MAX_SCAN_DEG_MAX = 60.0, 5.0, 180.0  # זווית סריקה מקסימלית מכיוון הפנים


def _radar_max_range_m(power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm, losses_db=_RADAR_SYSTEM_LOSSES_DB):
    """טווח גילוי מקסימלי לפי משוואת המכ"ם הסטנדרטית (monostatic):
    R_max = [(Pt·G²·λ²·σ) / ((4π)³·Pmin·L)]^(1/4).
    ככל שההספק/הרווח/שטח-החתך גדולים יותר — טווח הגילוי גדל; ככל שהתדר גבוה יותר
    (אורך גל קצר) — טווח הגילוי קטן. רעיוני/חינוכי, לא כולל רווחי עיבוד סיגנל מתקדמים."""
    Pt = power_kw * 1000.0  # קילוואט -> ואט
    G = 10 ** (gain_dbi / 10.0)  # dBi -> יחס ליניארי
    wavelength_m = 299792458.0 / (freq_mhz * 1e6)  # אורך גל = מהירות האור / תדר
    Pmin = 10 ** ((sensitivity_dbm - 30) / 10.0)  # dBm -> ואט (בסיס dBm הוא מיליוואט)
    L = 10 ** (losses_db / 10.0)  # dB -> יחס ליניארי
    numerator = Pt * (G ** 2) * (wavelength_m ** 2) * rcs_m2
    denominator = ((4 * math.pi) ** 3) * Pmin * L
    if numerator <= 0 or denominator <= 0:
        return 0.0
    return (numerator / denominator) ** 0.25


def _lobing_factor(elevation_angle_deg, h_antenna_m, wavelength_m, reflectivity):
    """גורם עוצמת 'ריבוד' (multipath lobing) — השתקפות מהקרקע יוצרת התאבכות עם הקרן
    הישירה, כך שבזוויות עילוי מסוימות הכיסוי מוגבר ובאחרות כמעט מבוטל (לא קונוס חלק).
    F=|1+ρ·e^(iΔφ)|, כאשר Δφ תלוי בגובה האנטנה, זווית העילוי ואורך הגל. מוכפל ישירות
    בטווח הגילוי (F נע בין 1-ρ ל-1+ρ). קירוב גס מעל משטח שטוח, רעיוני/חינוכי בלבד."""
    theta_rad = math.radians(elevation_angle_deg)
    delta_phi = (4 * math.pi * h_antenna_m * math.sin(theta_rad)) / wavelength_m
    real = 1 + reflectivity * math.cos(delta_phi)
    imag = reflectivity * math.sin(delta_phi)
    return math.sqrt(real * real + imag * imag)


def _doppler_detectable(radial_speed_ms, mdv_ms, wavelength_m, prf_hz, tolerance_frac=_RADAR_BLIND_SPEED_TOLERANCE_FRAC):
    """True אם מהירות רדיאלית נתונה תתגלה ע"י מכ"ם דופלר. שני תנאי כישלון:
    (1) איטי מדי (מתחת ל-MDV) — מסונן כרקע נייח (קרקע/עננים).
    (2) קרוב מדי ל'מהירות עיוורת' (v_blind=n·λ·PRF/2) — נדגם כאילו היה נייח, גם אם מהיר."""
    if radial_speed_ms < mdv_ms:
        return False
    v_blind_unit = wavelength_m * prf_hz / 2.0  # מהירות עיוורת בסיסית (n=1)
    if v_blind_unit <= 0:
        return True  # מקרה קצה — לא אמור לקרות עם PRF תקין
    n = round(radial_speed_ms / v_blind_unit)  # הכפולה הקרובה ביותר למהירות הנבדקת
    if n >= 1 and abs(radial_speed_ms - n * v_blind_unit) <= tolerance_frac * (n * v_blind_unit):
        return False
    return True


def _max_unambiguous_range_m(prf_hz):
    """טווח לא-חד-משמעי מקסימלי: R_unambig=c/(2·PRF) — מעבר לו, זמן החזרת פולס עלול
    להתבלבל עם הפולס הבא. תקרת טווח נוספת, לא קשורה ל-Doppler עצמו."""
    return 299792458.0 / (2.0 * prf_hz)


def _angular_diff_deg(a, b):
    """הפרש הזוויות הקצר ביותר בין שתי מעלות (0-180) — למשל בין 350° ל-10° ההפרש הוא 20°, לא 340°."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _scan_loss_factor(bearing_deg, boresight_deg, max_scan_deg):
    """גורם הפסד-סריקה למכ"ם מערך-מופעים — הרווח האפקטיבי יורד ככל שמסטים את הקרן
    האלקטרונית הרחק מכיוון-הפנים (boresight), ומעבר לזווית הסריקה המקסימלית האנטנה
    כלל לא מכסה את הכיוון (מחזיר 0.0). R_max תלוי ב-G² בתוך שורש רביעי — כלומר R∝G^0.5 —
    ולכן ההפסד על הטווח (לא על הרווח עצמו) הוא שורש של הפסד ה-cosine הסטנדרטי."""
    scan_angle = _angular_diff_deg(bearing_deg, boresight_deg)
    if scan_angle > max_scan_deg:
        return 0.0  # מחוץ לתחום הסריקה של המערך — לא מכוסה כלל, לא רק מוחלש
    return math.sqrt(math.cos(math.radians(scan_angle)))


# job ברקע + polling + ביטול — אותו דפוס בדיוק כמו רדיוס-ראייה רדיאלי (_radial_jobs למעלה),
# אבל ב-dict נפרד לגמרי, כדי ששני סוגי החישובים יוכלו לרוץ בו-זמנית בלי להתנגש
_radar_jobs = {}  # job_id -> dict מצב (status/batches_done/batches_total/result/error/cancelled/created)
_radar_jobs_lock = threading.Lock()  # מגן על _radar_jobs מגישה בו-זמנית של כמה threads


def _cleanup_old_radar_jobs():
    """מוחק jobs ישנים שהסתיימו — אותו דפוס בדיוק כמו _cleanup_old_radial_jobs, על dict נפרד.
    חייב להיקרא כשה-lock כבר תפוס (לא נועל בעצמו)."""
    now = time.time()  # זמן נוכחי, להשוואה מול 'created' של כל job
    stale = [
        jid for jid, job in _radar_jobs.items()
        if job['status'] in ('done', 'error', 'cancelled') and now - job['created'] > _RADAR_JOB_TTL_SEC
    ]
    for jid in stale:
        del _radar_jobs[jid]  # מחיקה בפועל מהמילון המשותף


def _radar_worker(job_id, obs_lat, obs_lon, range_km, angle_step_deg, start_bearing_deg, end_bearing_deg,
                   h_antenna, ridge_margin_deg, min_range_km, vertical_center_deg, vertical_width_deg,
                   power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm,
                   prf_hz, mdv_kt, target_speed_kt, target_heading_deg,
                   lobing_enabled, reflectivity_key,
                   antenna_type, boresight_deg, max_scan_deg):
    """רץ ב-thread נפרד (daemon) — כל החישוב הכבד. מבנה זהה ל-_radial_worker (שלבים
    1-6: גובה משקיף, בניית כיוונים, צפיפות דגימה, בניית נקודות, שליפת גבהים ב-batches),
    ושלב 7 חדש: לכל קרן — בדיקת חסימת שטח (ratchet) + טווח מכ"ם/ריבוד (תלוי-נקודה) +
    דופלר (תלוי-אזימוט בלבד, קבוע לאורך כל הקרן)."""
    try:
        range_m = range_km * 1000.0  # המרה מק"מ למטרים
        min_range_m = min_range_km * 1000.0  # המרה מק"מ למטרים

        # שלב 1: גובה המשקיף/אנטנה — בנפרד, נכשל-מהר אם לא זמין (בלי טעם להמשיך בלעדיו)
        obs_elevs, err = _fetch_elevations([{'lat': obs_lat, 'lon': obs_lon}])
        if err or obs_elevs is None or obs_elevs[0] is None:
            with _radar_jobs_lock:
                _radar_jobs[job_id]['status'] = 'error'
                _radar_jobs[job_id]['error'] = (err or {}).get('error', 'לא ניתן לשלוף את גובה המשקיף')
            return
        observer_elev = obs_elevs[0]  # גובה קרקע גולמי בנקודת המשקיף
        h_obs = observer_elev + h_antenna  # גובה עין האנטנה בפועל

        # שלב 2: חישובי פיזיקה שלא תלויים בגיאומטריה הספציפית — פעם אחת, לא בכל נקודה
        wavelength_m = 299792458.0 / (freq_mhz * 1e6)  # אורך גל — נדרש למשוואת המכ"ם, ל-lobing, ולמהירויות עיוורות
        radar_clean_range_m = _radar_max_range_m(power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm)  # טווח לפי משוואת המכ"ם, בלי ריבוד
        unambig_range_m = _max_unambiguous_range_m(prf_hz)  # תקרת טווח נוספת מ-PRF
        radar_ceiling_m = min(radar_clean_range_m, unambig_range_m)  # התקרה בפועל, לפני ריבוד נקודתי
        mdv_ms = mdv_kt * _KT_TO_MS  # המרת MDV מקשר למטר/שנייה
        target_speed_ms = target_speed_kt * _KT_TO_MS  # המרת מהירות המטרה מקשר למטר/שנייה
        reflectivity = _RADAR_REFLECTIVITY.get(reflectivity_key, _RADAR_REFLECTIVITY[_RADAR_REFLECTIVITY_DEFAULT])  # מקדם החזרה לפי סוג המשטח

        # שלב 3: בניית כיווני הסריקה — זהה לרדיוס-ראייה רדיאלי (תמיכה במגזר חלקי+עטיפה מעל 360°/0°)
        span = (end_bearing_deg - start_bearing_deg) % 360  # רוחב המגזר במעלות
        if span == 0:
            span = 360  # start==end פירושו "הכל" (מעגל מלא), לא מגזר ברוחב אפס
        n_bearings = max(1, round(span / angle_step_deg))  # מספר הכיוונים בפועל
        angle_step_deg = span / n_bearings  # שלב אפקטיבי — מחלק את המגזר בדיוק
        bearings = [(start_bearing_deg + i * angle_step_deg) % 360 for i in range(n_bearings)]  # רשימת האזימוטים לבדיקה

        # שלב 4: צפיפות דגימה — אותה נוסחה בדיוק כמו רדיוס-ראייה רדיאלי (קבועים גנריים משותפים)
        budget_based = min(20, max(_RADIAL_SAMPLES_MIN, _RADIAL_BASE_BUDGET // n_bearings))
        spacing_based = round((range_km - min_range_km) / _RADIAL_TARGET_SPACING_KM) + 1
        samples_per_ray = max(_RADIAL_SAMPLES_MIN, min(_RADIAL_SAMPLES_MAX, max(budget_based, spacing_based)))
        if n_bearings * samples_per_ray > _RADIAL_MAX_TOTAL_POINTS:  # שילוב קיצוני — מצמצם כדי לא לחרוג מהתקרה הכוללת
            samples_per_ray = max(_RADIAL_SAMPLES_MIN, _RADIAL_MAX_TOTAL_POINTS // n_bearings)

        # שלב 5: בניית כל נקודות הדגימה מראש (כל כיוון × כל מרחק דגימה לאורכו) — זהה לרדיוס-ראייה רדיאלי
        all_points = []  # בסדר: קרן 0 (כל דגימותיה), קרן 1 (כל דגימותיה), ...
        for bearing in bearings:
            for j in range(samples_per_ray):
                frac = j / (samples_per_ray - 1) if samples_per_ray > 1 else 0.0
                dist = min_range_m + frac * (range_m - min_range_m)  # מרחק הדגימה — מתחיל ב-min_range_m, לא 0
                plat, plon = _destination_point(obs_lat, obs_lon, bearing, dist)  # נקודת הדגימה בפועל
                all_points.append({'lat': round(plat, 6), 'lon': round(plon, 6), 'dist_m': dist})

        # שלב 6: שליפת גבהים ב-batches, עם עדכון התקדמות ובדיקת ביטול ביניהם — זהה לרדיוס-ראייה רדיאלי
        total_batches = (len(all_points) + _RADIAL_BATCH_SIZE - 1) // _RADIAL_BATCH_SIZE  # ceiling division
        with _radar_jobs_lock:
            _radar_jobs[job_id]['batches_total'] = total_batches  # מאפשר ל-JS להציג "X מתוך Y"
        elevations = [None] * len(all_points)  # מקביל ל-all_points; None = נקודה שלא נשלף עבורה גובה
        for batch_idx in range(total_batches):
            with _radar_jobs_lock:
                if _radar_jobs[job_id]['cancelled']:  # בדיקת ביטול בין כל batch — תגובתיות לכפתור "בטל"
                    _radar_jobs[job_id]['status'] = 'cancelled'
                    return
            if batch_idx > 0:
                time.sleep(_RADIAL_BATCH_PAUSE_SEC)  # השהיה בין batches — לא לפני הראשון
            batch = all_points[batch_idx * _RADIAL_BATCH_SIZE:(batch_idx + 1) * _RADIAL_BATCH_SIZE]
            batch_elevs, err = _fetch_elevations(batch)
            if err and err.get('rate_limited'):  # 429 — עוצר את כל ה-job
                with _radar_jobs_lock:
                    _radar_jobs[job_id]['status'] = 'error'
                    _radar_jobs[job_id]['error'] = err.get('error')
                return
            if batch_elevs is not None:  # כשל חלקי (לא 429) — משאיר None בנקודות האלה וממשיך
                for k, elev in enumerate(batch_elevs):
                    elevations[batch_idx * _RADIAL_BATCH_SIZE + k] = elev
            with _radar_jobs_lock:
                _radar_jobs[job_id]['batches_done'] = batch_idx + 1  # עדכון התקדמות אחרי כל batch

        # שלב 7: פירוק לפי קרן — חסימת שטח (ratchet) + טווח מכ"ם/ריבוד (תלוי-נקודה) + דופלר (תלוי-אזימוט)
        margin_slope = math.tan(math.radians(ridge_margin_deg))  # מרווח רכס, כשיפוע
        v_half = vertical_width_deg / 2.0  # חצי רוחב שדה-הראייה האנכי
        min_angle_slope = math.tan(math.radians(vertical_center_deg - v_half))  # גבול תחתון, כשיפוע
        max_angle_slope = math.tan(math.radians(vertical_center_deg + v_half))  # גבול עליון, כשיפוע
        rays = []  # תוצאה סופית — רשומה אחת לכל אזימוט
        clear_count = 0  # קרניים שהגיעו מזוהות-לגמרי (ירוק) עד סוף הטווח המבוקש
        doppler_blocked_rays = 0  # קרניים שכל הקרן שלהן מוסתרת ע"י הדופלר (כתום בלבד, לא ירוק בכלל)
        failed_rays = 0  # קרניים חסרות נתונים חלקיים
        for ray_idx, bearing in enumerate(bearings):
            # מהירות רדיאלית משוערת של המטרה באזימוט הזה — תלויה רק בכיוון (קבועה לאורך כל הקרן),
            # לפי הזווית בין כיוון התנועה של המטרה לבין קו-הראייה מהמשקיף לאזימוט הזה
            radial_speed_ms = abs(target_speed_ms * math.cos(math.radians(target_heading_deg - bearing)))
            doppler_ok = _doppler_detectable(radial_speed_ms, mdv_ms, wavelength_m, prf_hz)
            # הפסד-סריקה של מערך-מופעים — קבוע לאורך כל הקרן (תלוי רק באזימוט מול כיוון-הפנים), כמו הדופלר;
            # 1.0 עבור אנטנה גנרית (בלי תופעת סריקה בכלל)
            ray_scan_loss = (_scan_loss_factor(bearing, boresight_deg, max_scan_deg)
                              if antenna_type == 'phased_array' else 1.0)

            ray_points = all_points[ray_idx * samples_per_ray:(ray_idx + 1) * samples_per_ray]  # נקודות הדגימה של הקרן הזו
            ray_elevs = elevations[ray_idx * samples_per_ray:(ray_idx + 1) * samples_per_ray]  # הגבהים המקבילים
            surviving = [(p, e) for p, e in zip(ray_points, ray_elevs) if e is not None]  # מסנן נקודות בלי גובה
            samples_ok = len(surviving)
            if samples_ok < 2:  # אין מספיק נתונים בכלל לאורך הקרן הזו
                rays.append({'bearing_deg': round(bearing, 3), 'radar_dist_km': 0.0, 'radar_lat': obs_lat,
                             'radar_lon': obs_lon, 'doppler_ok': doppler_ok, 'blocked': True, 'ok': False,
                             'samples_ok': samples_ok})
                failed_rays += 1
                continue
            dists = [p['dist_m'] for p, _ in surviving]  # מרחקי הדגימות ששרדו, לפי סדר עולה
            elevs_only = [e for _, e in surviving]  # הגבהים המקבילים
            h_offsets = [0.0] * len(surviving)  # אין "גובה יעד" נפרד כאן — הזיהוי נגזר ממשוואת המכ"ם/RCS, לא מגובה יעד ידני
            ratchet = _horizon_ratchet(dists, elevs_only, h_obs, h_offsets, margin_slope, min_angle_slope, max_angle_slope)

            # הנקודה הרחוקה ביותר שעדיין בטווח המכ"ם ולא חסומה שטח — נבדקות כל הנקודות, לא נעצר בכישלון הראשון
            radar_dist_m, radar_lat, radar_lon = 0.0, obs_lat, obs_lon
            for i, rr in enumerate(ratchet):
                if not rr['visible']:
                    continue  # חסום ע"י שטח/מחוץ לשדה-הראייה האנכי — לא נבדק מול טווח המכ"ם כלל
                d = dists[i]
                if lobing_enabled:
                    elev_angle_deg = math.degrees(math.atan2(elevs_only[i] - h_obs, d)) if d > 0 else 90.0  # זווית עילוי מהאנטנה לנקודה
                    ceiling = radar_ceiling_m * _lobing_factor(elev_angle_deg, h_antenna, wavelength_m, reflectivity)
                else:
                    ceiling = radar_ceiling_m  # ריבוד כבוי — התקרה הנקייה בלבד
                ceiling *= ray_scan_loss  # הפסד-סריקה של מערך-מופעים (1.0 אם גנרי/בתוך תחום הסריקה המלא)
                if d <= ceiling:
                    radar_dist_m = d
                    radar_lat, radar_lon = surviving[i][0]['lat'], surviving[i][0]['lon']

            blocked = radar_dist_m < dists[-1] - 1e-6  # לא הגיע לקצה הטווח המבוקש בפועל — יצטייר קטע אדום בהמשך
            if doppler_ok:
                if not blocked:
                    clear_count += 1
            else:
                doppler_blocked_rays += 1
            rays.append({
                'bearing_deg': round(bearing, 3),
                'radar_dist_km': round(radar_dist_m / 1000, 3),
                'radar_lat': radar_lat, 'radar_lon': radar_lon,
                'doppler_ok': doppler_ok, 'blocked': blocked,
                'ok': samples_ok == samples_per_ray, 'samples_ok': samples_ok,
            })
            if samples_ok != samples_per_ray:
                failed_rays += 1

        result = {  # תוצאת ה-job הסופית — נקראת ע"י /radar_doppler/status כש-status=='done'
            'observer_lat': obs_lat, 'observer_lon': obs_lon, 'observer_elev': observer_elev,
            'observer_h': round(h_obs, 1), 'h_antenna': h_antenna, 'ridge_margin_deg': ridge_margin_deg,
            'range_km': range_km, 'min_range_km': min_range_km, 'angle_step_deg': round(angle_step_deg, 3),
            'vertical_center_deg': vertical_center_deg, 'vertical_width_deg': vertical_width_deg,
            'start_bearing_deg': start_bearing_deg, 'end_bearing_deg': end_bearing_deg, 'span_deg': span,
            'n_bearings': n_bearings, 'samples_per_ray': samples_per_ray,
            'power_kw': power_kw, 'gain_dbi': gain_dbi, 'freq_mhz': freq_mhz, 'rcs_m2': rcs_m2,
            'sensitivity_dbm': sensitivity_dbm,
            'radar_clean_range_km': round(radar_clean_range_m / 1000, 2),
            'unambig_range_km': round(unambig_range_m / 1000, 2),
            'prf_hz': prf_hz, 'mdv_kt': mdv_kt, 'target_speed_kt': target_speed_kt,
            'target_heading_deg': target_heading_deg,
            'lobing_enabled': lobing_enabled, 'reflectivity_key': reflectivity_key,
            'antenna_type': antenna_type, 'boresight_deg': boresight_deg, 'max_scan_deg': max_scan_deg,
            'clear_count': clear_count, 'doppler_blocked_rays': doppler_blocked_rays,
            'failed_rays': failed_rays, 'rays': rays,
        }
        with _radar_jobs_lock:
            _radar_jobs[job_id]['status'] = 'done'
            _radar_jobs[job_id]['result'] = result
    except Exception as e:  # רשת ביטחון — כשל בלתי-צפוי לא ישאיר את ה-job תקוע ב-'running' לנצח
        logging.error(f"שגיאה בחישוב תצפית מכ\"ם דופלר (job {job_id}): {e}")
        with _radar_jobs_lock:
            _radar_jobs[job_id]['status'] = 'error'
            _radar_jobs[job_id]['error'] = str(e)


@app.route("/radar_doppler/start", methods=["GET"])
def start_radar_doppler():
    """מתחיל job חדש של תצפית מכ"ם דופלר ברקע, מחזיר job_id מיידית — אותו דפוס בדיוק
    כמו /los_radial/start. קולט את כל הפרמטרים, וכל אחד נצמד (clamp) לטווח מותר, לא נדחה."""
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "פרמטרים חסרים"}), 400

    try:
        range_km = float(request.args.get('range_km', _RADAR_RANGE_KM_DEFAULT))
    except (TypeError, ValueError):
        range_km = _RADAR_RANGE_KM_DEFAULT
    range_km = min(max(range_km, _RADIAL_RANGE_KM_MIN), _RADIAL_RANGE_KM_MAX)  # גבולות גנריים משותפים עם רדיוס-הראייה

    try:
        min_range_km = float(request.args.get('min_range_km', _RADAR_MIN_RANGE_KM_DEFAULT))
    except (TypeError, ValueError):
        min_range_km = _RADAR_MIN_RANGE_KM_DEFAULT
    min_range_km = min(max(min_range_km, 0.0), range_km)  # לא שלילי, ולא גדול מהטווח המקסימלי עצמו

    try:
        angle_step_deg = float(request.args.get('angle_step_deg', 10.0))
    except (TypeError, ValueError):
        angle_step_deg = 10.0
    angle_step_deg = min(max(angle_step_deg, _RADIAL_ANGLE_STEP_MIN), _RADIAL_ANGLE_STEP_MAX)

    try:
        ridge_margin_deg = float(request.args.get('ridge_margin_deg', 0.0))
    except (TypeError, ValueError):
        ridge_margin_deg = 0.0
    ridge_margin_deg = min(max(ridge_margin_deg, _RADIAL_RIDGE_MARGIN_MIN), _RADIAL_RIDGE_MARGIN_MAX)

    try:  # אזימוט התחלה — לא נצמד לטווח קבוע, % 360 בהמשך כבר מנרמל כל ערך
        start_bearing_deg = float(request.args.get('start_bearing_deg', 0.0))
    except (TypeError, ValueError):
        start_bearing_deg = 0.0
    try:  # אזימוט סיום — ברירת מחדל 360 (יחד עם 0 למעלה = מעגל מלא כברירת מחדל)
        end_bearing_deg = float(request.args.get('end_bearing_deg', 360.0))
    except (TypeError, ValueError):
        end_bearing_deg = 360.0

    try:
        h_antenna = float(request.args.get('h_antenna', _RADAR_H_ANTENNA_DEFAULT_M))
    except (TypeError, ValueError):
        h_antenna = _RADAR_H_ANTENNA_DEFAULT_M

    try:
        vertical_center_deg = float(request.args.get('vertical_center_deg', _RADAR_VBEAM_CENTER_DEFAULT_DEG))
    except (TypeError, ValueError):
        vertical_center_deg = _RADAR_VBEAM_CENTER_DEFAULT_DEG
    vertical_center_deg = min(max(vertical_center_deg, _RADIAL_VERTICAL_CENTER_MIN), _RADIAL_VERTICAL_CENTER_MAX)

    try:
        vertical_width_deg = float(request.args.get('vertical_width_deg', _RADAR_VBEAM_WIDTH_DEFAULT_DEG))
    except (TypeError, ValueError):
        vertical_width_deg = _RADAR_VBEAM_WIDTH_DEFAULT_DEG
    vertical_width_deg = min(max(vertical_width_deg, _RADIAL_VERTICAL_WIDTH_MIN), _RADIAL_VERTICAL_WIDTH_MAX)

    try:
        power_kw = float(request.args.get('power_kw', _RADAR_POWER_KW_DEFAULT))
    except (TypeError, ValueError):
        power_kw = _RADAR_POWER_KW_DEFAULT
    power_kw = min(max(power_kw, _RADAR_POWER_KW_MIN), _RADAR_POWER_KW_MAX)

    try:
        gain_dbi = float(request.args.get('gain_dbi', _RADAR_GAIN_DBI_DEFAULT))
    except (TypeError, ValueError):
        gain_dbi = _RADAR_GAIN_DBI_DEFAULT
    gain_dbi = min(max(gain_dbi, _RADAR_GAIN_DBI_MIN), _RADAR_GAIN_DBI_MAX)

    try:
        freq_mhz = float(request.args.get('freq_mhz', _RADAR_FREQ_MHZ_DEFAULT))
    except (TypeError, ValueError):
        freq_mhz = _RADAR_FREQ_MHZ_DEFAULT
    freq_mhz = min(max(freq_mhz, _RADAR_FREQ_MHZ_MIN), _RADAR_FREQ_MHZ_MAX)

    try:
        rcs_m2 = float(request.args.get('rcs_m2', _RADAR_RCS_M2_DEFAULT))
    except (TypeError, ValueError):
        rcs_m2 = _RADAR_RCS_M2_DEFAULT
    rcs_m2 = min(max(rcs_m2, _RADAR_RCS_M2_MIN), _RADAR_RCS_M2_MAX)

    try:
        sensitivity_dbm = float(request.args.get('sensitivity_dbm', _RADAR_SENSITIVITY_DBM_DEFAULT))
    except (TypeError, ValueError):
        sensitivity_dbm = _RADAR_SENSITIVITY_DBM_DEFAULT
    sensitivity_dbm = min(max(sensitivity_dbm, _RADAR_SENSITIVITY_DBM_MIN), _RADAR_SENSITIVITY_DBM_MAX)

    try:
        prf_hz = float(request.args.get('prf_hz', _RADAR_PRF_HZ_DEFAULT))
    except (TypeError, ValueError):
        prf_hz = _RADAR_PRF_HZ_DEFAULT
    prf_hz = min(max(prf_hz, _RADAR_PRF_HZ_MIN), _RADAR_PRF_HZ_MAX)

    try:
        mdv_kt = float(request.args.get('mdv_kt', _RADAR_MDV_KT_DEFAULT))
    except (TypeError, ValueError):
        mdv_kt = _RADAR_MDV_KT_DEFAULT
    mdv_kt = min(max(mdv_kt, _RADAR_MDV_KT_MIN), _RADAR_MDV_KT_MAX)

    try:
        target_speed_kt = float(request.args.get('target_speed_kt', _RADAR_TARGET_SPEED_KT_DEFAULT))
    except (TypeError, ValueError):
        target_speed_kt = _RADAR_TARGET_SPEED_KT_DEFAULT
    target_speed_kt = min(max(target_speed_kt, _RADAR_TARGET_SPEED_KT_MIN), _RADAR_TARGET_SPEED_KT_MAX)

    try:
        target_heading_deg = float(request.args.get('target_heading_deg', _RADAR_TARGET_HEADING_DEG_DEFAULT))
    except (TypeError, ValueError):
        target_heading_deg = _RADAR_TARGET_HEADING_DEG_DEFAULT
    target_heading_deg = target_heading_deg % 360  # מנרמל כל ערך (כולל שלילי) לטווח 0-360

    lobing_enabled = request.args.get('lobing_enabled', 'false').lower() == 'true'  # toggle — כבוי כברירת מחדל
    reflectivity_key = request.args.get('reflectivity', _RADAR_REFLECTIVITY_DEFAULT)
    if reflectivity_key not in _RADAR_REFLECTIVITY:
        reflectivity_key = _RADAR_REFLECTIVITY_DEFAULT  # ערך לא מוכר — נופל לברירת המחדל בשקט, לא שגיאה

    antenna_type = request.args.get('antenna_type', _RADAR_ANTENNA_TYPE_DEFAULT)
    if antenna_type not in _RADAR_ANTENNA_TYPES:
        antenna_type = _RADAR_ANTENNA_TYPE_DEFAULT  # ערך לא מוכר — נופל לברירת המחדל בשקט, לא שגיאה
    try:
        boresight_deg = float(request.args.get('boresight_deg', _RADAR_BORESIGHT_DEG_DEFAULT))
    except (TypeError, ValueError):
        boresight_deg = _RADAR_BORESIGHT_DEG_DEFAULT
    boresight_deg = boresight_deg % 360  # מנרמל כל ערך (כולל שלילי) לטווח 0-360
    try:
        max_scan_deg = float(request.args.get('max_scan_deg', _RADAR_MAX_SCAN_DEG_DEFAULT))
    except (TypeError, ValueError):
        max_scan_deg = _RADAR_MAX_SCAN_DEG_DEFAULT
    max_scan_deg = min(max(max_scan_deg, _RADAR_MAX_SCAN_DEG_MIN), _RADAR_MAX_SCAN_DEG_MAX)

    job_id = str(uuid.uuid4())  # מזהה ייחודי ל-job הזה
    with _radar_jobs_lock:
        _cleanup_old_radar_jobs()  # ניקוי jobs ישנים לפני הוספת חדש — מונע דליפת זיכרון
        _radar_jobs[job_id] = {
            'status': 'running', 'batches_done': 0, 'batches_total': None,
            'result': None, 'error': None, 'cancelled': False, 'created': time.time(),
        }
    thread = threading.Thread(  # מריץ את כל החישוב ב-thread נפרד — הבקשה הזו חוזרת מיד, לא מחכה
        target=_radar_worker,
        args=(job_id, lat, lon, range_km, angle_step_deg, start_bearing_deg, end_bearing_deg,
              h_antenna, ridge_margin_deg, min_range_km, vertical_center_deg, vertical_width_deg,
              power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm,
              prf_hz, mdv_kt, target_speed_kt, target_heading_deg,
              lobing_enabled, reflectivity_key,
              antenna_type, boresight_deg, max_scan_deg),
        daemon=True,  # daemon — לא מונע יציאה מהתהליך אם השרת נסגר תוך כדי ריצה
    )
    thread.start()
    return jsonify({'job_id': job_id})


@app.route("/radar_doppler/status", methods=["GET"])
def radar_doppler_status():
    """מחזיר את מצב ה-job הנוכחי — אותו מבנה בדיוק כמו /los_radial/status."""
    job_id = request.args.get('job_id')  # מזהה ה-job שהתקבל מ-/radar_doppler/start
    with _radar_jobs_lock:
        job = _radar_jobs.get(job_id)
        if job is None:  # job_id לא קיים — למשל נוקה כבר, או מזהה שגוי
            return jsonify({'error': 'job לא נמצא (אולי נוקה, או job_id שגוי)'}), 404
        return jsonify({
            'status': job['status'], 'batches_done': job['batches_done'],
            'batches_total': job['batches_total'], 'result': job['result'], 'error': job['error'],
        })


@app.route("/radar_doppler/cancel", methods=["POST"])
def cancel_radar_doppler():
    """מסמן job לביטול — ה-worker בודק את הדגל בין כל batch, אותו דפוס כמו /los_radial/cancel."""
    job_id = request.args.get('job_id')  # מזהה ה-job לביטול
    with _radar_jobs_lock:
        if job_id in _radar_jobs:  # מתעלם בשקט אם ה-job כבר לא קיים (למשל הסתיים/נוקה) — אין מה לבטל
            _radar_jobs[job_id]['cancelled'] = True
    return jsonify({'ok': True})


# ── "עמדות שמורות" — מיקום+פרמטרים ניתנים לשמירה תחת שם, לכל אחד משלושת כלי התצפית בנפרד ──
# משותף ל-LOS/רדיוס-ראייה/מכ"ם-דופלר — לא מחזיק ידע על צורת ה-params של כל כלי, רק שומר/מחזיר
# אותם כמו שהם (JS אחראי על התוכן). קובץ JSON שטוח פשוט (כמו weather_data.csv במקום אחר בפרויקט) —
# לא מסד נתונים, כי כמות הנתונים קטנה וזה שימוש מקומי-בלבד של משתמש יחיד.
_STATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_stations.json')  # תמיד לצד weather_server.py, לא תלוי-תיקיית-עבודה
_STATIONS_LOCK = threading.Lock()  # מגן על קריאה/כתיבה בו-זמנית לקובץ מכמה בקשות
_STATIONS_MAX_PER_TOOL = 20  # תקרת עמדות שמורות לכל כלי — מונע צמיחה בלתי מוגבלת של הקובץ
_STATIONS_VALID_TOOLS = ('los', 'radial_los', 'radar_doppler')  # מפתחות תקינים — שם JS מזהה כל כלי


def _load_stations():
    """קורא את קובץ העמדות השמורות — מחזיר dict ריק אם הקובץ לא קיים עדיין או פגום."""
    if not os.path.exists(_STATIONS_FILE):
        return {}
    try:
        with open(_STATIONS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logging.error(f"שגיאה בקריאת {_STATIONS_FILE}: {e}")
        return {}  # קובץ פגום — מתייחסים כאילו אין עמדות שמורות, לא קורסים


def _save_stations(data):
    """כותב את כל מבנה העמדות השמורות בחזרה לקובץ — קריאה מלאה+כתיבה מלאה (לא append), פשוט מספיק לכמות הנתונים הקטנה."""
    with open(_STATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/stations/list", methods=["GET"])
def list_stations():
    """מחזיר את כל העמדות השמורות לכלי מסוים — [{name, params}, ...], ריק אם אין עדיין."""
    tool = request.args.get('tool')
    if tool not in _STATIONS_VALID_TOOLS:
        return jsonify({'error': 'כלי לא מוכר'}), 400
    with _STATIONS_LOCK:
        data = _load_stations()
    return jsonify({'stations': data.get(tool, [])})


@app.route("/stations/save", methods=["POST"])
def save_station():
    """שומר/מעדכן עמדה תחת שם — אם כבר קיימת עמדה באותו שם לאותו כלי, מוחלפת (לא נוצרת כפולה)."""
    body = request.json or {}
    tool = body.get('tool')
    name = (body.get('name') or '').strip()
    params = body.get('params')
    if tool not in _STATIONS_VALID_TOOLS:
        return jsonify({'error': 'כלי לא מוכר'}), 400
    if not name:
        return jsonify({'error': 'חסר שם לעמדה'}), 400
    if not isinstance(params, dict):
        return jsonify({'error': 'חסרים פרמטרים'}), 400
    with _STATIONS_LOCK:
        data = _load_stations()
        tool_list = data.setdefault(tool, [])
        tool_list[:] = [s for s in tool_list if s.get('name') != name]  # מסיר עמדה קודמת באותו שם, אם קיימת — לא כפילות
        tool_list.append({'name': name, 'params': params})
        if len(tool_list) > _STATIONS_MAX_PER_TOOL:  # חרג מהתקרה — מוחק את הישנה ביותר (הראשונה ברשימה)
            del tool_list[0]
        _save_stations(data)
    return jsonify({'ok': True})


@app.route("/stations/delete", methods=["POST"])
def delete_station():
    """מוחק עמדה שמורה לפי שם — מתעלם בשקט אם השם/הכלי לא נמצאו."""
    body = request.json or {}
    tool = body.get('tool')
    name = body.get('name')
    if tool not in _STATIONS_VALID_TOOLS:
        return jsonify({'error': 'כלי לא מוכר'}), 400
    with _STATIONS_LOCK:
        data = _load_stations()
        tool_list = data.get(tool, [])
        tool_list[:] = [s for s in tool_list if s.get('name') != name]
        _save_stations(data)
    return jsonify({'ok': True})


if __name__ == "__main__":
    # threaded=True — מונע ממטריקות/בקשות אחרות להיחסם בזמן קריאות ארוכות (רשת גבהים/טמפרטורה
    # מרובת-batches) — אותו טעם כמו ב-geo_server.py
    app.run(port=WEATHER_PORT, debug=True, threaded=True)