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


if __name__ == "__main__":
    # threaded=True — מונע ממטריקות/בקשות אחרות להיחסם בזמן קריאות ארוכות (רשת גבהים/טמפרטורה
    # מרובת-batches) — אותו טעם כמו ב-geo_server.py
    app.run(port=WEATHER_PORT, debug=True, threaded=True)