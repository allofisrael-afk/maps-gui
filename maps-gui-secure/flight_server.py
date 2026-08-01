import logging
import os
import re
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from FlightRadar24 import FlightRadar24API

load_dotenv()

logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')

app = Flask(__name__)
# תיקון: CORS מוגבל ל-localhost בלבד + null (לדפי file:// של QWebEngineView)
CORS(app, origins=["null", "http://localhost", "http://127.0.0.1"])

fr_api = FlightRadar24API()

_fr24_token = os.getenv("FR24_TOKEN", "").strip()
_fr24_user  = os.getenv("FR24_USER", "")
_fr24_pass  = os.getenv("FR24_PASS", "")

if _fr24_token:
    fr_api._FlightRadar24API__login_data = {
        "userData": {},
        "cookies":  {"_frPl": _fr24_token},
    }
    logging.info("FlightRadar24: אותחל עם token")  # תיקון: אין פרטי אימות בלוג
elif _fr24_user and _fr24_pass and not _fr24_user.startswith("your_"):
    try:
        fr_api.login(_fr24_user, _fr24_pass)
        logging.info("FlightRadar24: login הצליח")
    except Exception as _e:
        logging.warning(f"FlightRadar24: login נכשל. יפעל במצב בסיסי.")  # תיקון: אין חשיפת פרטי שגיאה
else:
    logging.info("FlightRadar24: רץ ללא login")


def _validate_flight_number(flight_number: str) -> bool:
    """תיקון: וולידציה על מספר הטיסה — מקסימום 10 תווים, אותיות ומספרים בלבד."""
    if not flight_number or len(flight_number) > 10:
        return False
    return bool(re.match(r'^[A-Z0-9]{2,10}$', flight_number))


@app.route("/flight_route", methods=["GET"])
def get_flight_route():
    """
    מחזיר מסלול טיסה (trail) ופרטים לטיסה לפי callsign או מספר טיסה.
    פרמטר: flight — מספר הטיסה או callsign (למשל: LY001, ELY001)
    """
    flight_number = request.args.get("flight", "").strip().upper()

    if not flight_number:
        return jsonify({"error": "יש לספק מספר טיסה (פרמטר 'flight')"}), 400

    # תיקון: וולידציה על קלט משתמש
    if not _validate_flight_number(flight_number):
        logging.warning(f"מספר טיסה לא תקין התקבל")  # תיקון: לא נרשם הערך עצמו
        return jsonify({"error": "מספר טיסה לא תקין"}), 400

    try:
        prefix_match = re.match(r'^([A-Z]{2,4})', flight_number)
        airline_prefix = prefix_match.group(1) if prefix_match else None

        all_flights = []
        if airline_prefix:
            try:
                all_flights = fr_api.get_flights(airline=airline_prefix)
                logging.info(f"get_flights(airline): {len(all_flights)} טיסות")
            except Exception as prefix_err:
                logging.warning(f"get_flights(airline) נכשל")

        if not all_flights:
            all_flights = fr_api.get_flights()
            logging.info(f"get_flights() גלובלי: {len(all_flights)} טיסות")

        matching = [
            f for f in all_flights
            if f.callsign and flight_number in f.callsign.upper()
        ]

        if not matching:
            logging.warning(f"לא נמצאה טיסה (נבדקו {len(all_flights)} טיסות)")
            return jsonify({"error": f"לא נמצאה טיסה פעילה עם מספר {flight_number}"}), 404

        flight = matching[0]

        trail        = []
        origin_iata  = "N/A"
        origin_name  = ""
        dest_iata    = "N/A"
        dest_name    = ""
        aircraft_model = "לא ידוע"
        airline_name   = "לא ידוע"

        try:
            details = fr_api.get_flight_details(flight)
            flight.set_flight_details(details)

            trail = details.get("trail", [])

            airports       = details.get("airport", {})
            origin_iata    = airports.get("origin",      {}).get("code", {}).get("iata", "N/A")
            origin_name    = airports.get("origin",      {}).get("name", "")
            dest_iata      = airports.get("destination", {}).get("code", {}).get("iata", "N/A")
            dest_name      = airports.get("destination", {}).get("name", "")
            aircraft_model = details.get("aircraft", {}).get("model", {}).get("text", "לא ידוע")
            airline_name   = details.get("airline",  {}).get("name", "לא ידוע")

        except Exception as detail_err:
            logging.warning(f"get_flight_details נכשל: {detail_err}. מחזיר מיקום נוכחי.")

        normalized_trail = []
        for point in trail:
            pt_lat = point.get("lat") if point.get("lat") is not None else point.get("Lat")
            pt_lng = point.get("lng") if point.get("lng") is not None else (point.get("Lng") or point.get("lon") or point.get("Lon"))
            if pt_lat is not None and pt_lng is not None:
                normalized_trail.append({
                    "lat": pt_lat,
                    "lng": pt_lng,
                    "alt": point.get("alt") or point.get("Alt") or point.get("altitude") or 0,
                    "spd": point.get("spd") or point.get("Spd") or point.get("speed") or 0,
                })
        trail = normalized_trail

        current_lat = getattr(flight, "latitude",  None)
        current_lng = getattr(flight, "longitude", None)

        if not trail and current_lat is not None and current_lng is not None:
            trail = [{"lat": current_lat, "lng": current_lng, "alt": getattr(flight, "altitude", 0), "spd": 0}]

        if len(trail) > 400:
            trail = trail[-400:]

        logging.info(f"נשלח מסלול: {len(trail)} נקודות")

        return jsonify({
            "callsign":    flight.callsign,
            "origin_iata": origin_iata,
            "origin_name": origin_name,
            "dest_iata":   dest_iata,
            "dest_name":   dest_name,
            "aircraft":    aircraft_model,
            "airline":     airline_name,
            "altitude":    getattr(flight, "altitude",     0),
            "speed":       getattr(flight, "ground_speed", 0),
            "heading":     getattr(flight, "heading",      0),
            "lat":         current_lat,
            "lng":         current_lng,
            "trail":       trail
        })

    except Exception as e:
        logging.error(f"שגיאה בשליפת מסלול טיסה: {e}")
        # תיקון: הודעה גנרית ל-client, פרטים רק בלוג
        return jsonify({"error": "שגיאה פנימית בשרת"}), 500


@app.route("/flight_search", methods=["GET"])
def search_flights():
    """
    מחזיר רשימת callsigns של טיסות שמתאימות לחיפוש.
    פרמטר: q — תחילית מספר הטיסה (מינימום 2 תווים)
    """
    query = request.args.get("q", "").strip().upper()

    if len(query) < 2:
        return jsonify([])

    # תיקון: וולידציה על שאילתת החיפוש
    if len(query) > 10 or not re.match(r'^[A-Z0-9]+$', query):
        return jsonify([])

    try:
        prefix_match = re.match(r'^([A-Z]{2,4})', query)
        airline_prefix = prefix_match.group(1) if prefix_match else None
        all_flights = []
        if airline_prefix:
            try:
                all_flights = fr_api.get_flights(airline=airline_prefix)
            except Exception:
                pass
        if not all_flights:
            all_flights = fr_api.get_flights()
        results = [
            {
                "callsign": f.callsign,
                "origin":   f.origin_airport_iata,
                "dest":     f.destination_airport_iata
            }
            for f in all_flights
            if f.callsign and query in f.callsign.upper()
        ][:20]
        return jsonify(results)

    except Exception as e:
        logging.error(f"שגיאה בחיפוש טיסות: {e}")
        return jsonify([])


if __name__ == "__main__":
    # תיקון: debug=False + קישור ל-127.0.0.1 בלבד
    app.run(host='127.0.0.1', port=5004, debug=False)
