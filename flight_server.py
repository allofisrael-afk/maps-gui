import logging  # רישום אירועים לקובץ לוג (ה-basicConfig עצמו הוגדר ב-server_common.create_app)
import os        # קריאת משתני סביבה לפרטי התחברות
import re        # חילוץ קידומת ICAO מה-callsign לחיפוש ממוקד
from flask import jsonify, request  # פענוח פרמטרים — Flask() עצמו נוצר ב-server_common.create_app
from FlightRadar24 import FlightRadar24API  # ספריית Python לשליפת נתוני FR24

from server_common import create_app  # תשתית משותפת לשלושת השרתים — .env/logging/Flask/CORS/metrics
# create_app כבר קורא ל-load_dotenv() — טוען גם את FR24_USER/FR24_PASS/FR24_TOKEN בהמשך הקובץ

# מיפוי קוד IATA (2 תווים) → קוד ICAO (3 תווים) לחברות נפוצות.
# ה-API של FR24 מקבל רק ICAO בפרמטר airline — IATA מחזיר 0 תוצאות.
_IATA_TO_ICAO = {
    'LY': 'ELY', 'IZ': 'AIZ', 'IS': 'ISF',          # ישראל
    'AA': 'AAL', 'UA': 'UAL', 'DL': 'DAL', 'WN': 'SWA', 'B6': 'JBU', 'AS': 'ASA', 'F9': 'FFT', 'NK': 'NKS',
    'BA': 'BAW', 'LH': 'DLH', 'AF': 'AFR', 'KL': 'KLM', 'IB': 'IBE', 'SK': 'SAS', 'AY': 'FIN',
    'OS': 'AUA', 'SN': 'BEL', 'LX': 'SWR', 'EI': 'EIN', 'TP': 'TAP', 'AZ': 'AZA', 'VS': 'VIR',
    'FR': 'RYR', 'U2': 'EZY', 'W6': 'WZZ', 'VY': 'VLG', 'EW': 'EWG', 'DY': 'NAX', 'BT': 'BTI',
    'EK': 'UAE', 'QR': 'QTR', 'TK': 'THY', 'SV': 'SVA', 'GF': 'GFA', 'WY': 'OMA', 'FZ': 'FDB', 'G9': 'ABY',
    'SU': 'AFL', 'S7': 'SBI',
    'SQ': 'SIA', 'CX': 'CPA', 'JL': 'JAL', 'NH': 'ANA', 'CI': 'CAL', 'CA': 'CCA', 'MU': 'CES',
    'OZ': 'AAR', 'KE': 'KAL', 'MH': 'MAS', 'TG': 'THA', 'AI': 'AIC', '9W': 'JAI',
    'AC': 'ACA', 'WS': 'WJA', 'QF': 'QFA', 'NZ': 'ANZ',
    'ET': 'ETH', 'KQ': 'KQA', 'SA': 'SAA', 'MS': 'MSR',
    'LA': 'LAN', 'AV': 'AVA', 'AM': 'AMX', 'CM': 'CMP', 'G3': 'GLO',
}


def _resolve_icao(prefix: str) -> str:
    """ממיר קידומת IATA (2 תווים) ל-ICAO (3 תווים) אם קיים מיפוי; אחרת מחזיר כפי שהוא."""
    if len(prefix) == 2:
        return _IATA_TO_ICAO.get(prefix, prefix)
    return prefix


def _normalize_flight_num(fn: str) -> str:
    """מסיר אפסים מובילים מחלק המספר: LY001 → LY1, ELY006 → ELY6."""
    m = re.match(r'^([A-Z]+)0*(\d+)$', fn)
    return (m.group(1) + m.group(2)) if m else fn


def _normalize_trail_point(point):
    """
    מנרמל נקודת מסלול בודדת ממבנה FR24 הלא-עקבי (lat/Lat, lng/Lng/lon/Lon,
    alt/Alt/altitude, spd/Spd/speed) למבנה אחיד {lat, lng, alt, spd}.
    מחזיר None אם אין קואורדינטות תקינות (הנקודה תידלג).
    מקור אמת יחיד — היו כאן שני עותקים כמעט-זהים (בנתיב הראשי ובנתיב search())
    שהתבררו כלא-זהים בפועל: אחד מהם לא בדק את המפתחות "altitude"/"speed".
    """
    pt_lat = point.get("lat") if point.get("lat") is not None else point.get("Lat")
    pt_lng = point.get("lng") if point.get("lng") is not None else (point.get("Lng") or point.get("lon") or point.get("Lon"))
    if pt_lat is None or pt_lng is None:
        return None
    return {
        "lat": pt_lat,
        "lng": pt_lng,
        "alt": point.get("alt") or point.get("Alt") or point.get("altitude") or 0,
        "spd": point.get("spd") or point.get("Spd") or point.get("speed") or 0,
    }

app = create_app(__name__)  # יצירת מופע Flask (טעינת .env, logging, CORS, ו-/metrics כבר מוכנים בתוך create_app)

fr_api = FlightRadar24API()  # יצירת מופע ה-API

# ── אימות FR24: קודם מנסה token ישיר (עוקף Cloudflare), אחר-כך login רגיל ──
_fr24_token = os.getenv("FR24_TOKEN", "").strip()  # ערך ה-cookie _frPl שנשמר ב-.env
_fr24_user  = os.getenv("FR24_USER", "")            # אימייל חשבון FR24 מ-.env
_fr24_pass  = os.getenv("FR24_PASS", "")            # סיסמת חשבון FR24 מ-.env

if _fr24_token:
    fr_api._FlightRadar24API__login_data = {        # הזרקת cookie ישירות — עוקף login שנחסם על-ידי Cloudflare
        "userData": {},                              # userData ריק — לא נדרש לשליפת trail
        "cookies":  {"_frPl": _fr24_token},         # ה-cookie שמאמת את הבקשות לנתוני פרטי טיסה
    }
    logging.info("FlightRadar24: אותחל עם FR24_TOKEN (cookie ישיר)")  # רישום אופן האימות
elif _fr24_user and _fr24_pass and not _fr24_user.startswith("your_"):
    try:
        fr_api.login(_fr24_user, _fr24_pass)  # login רגיל עם אימייל וסיסמה
        logging.info("FlightRadar24: login הצליח")
    except Exception as _e:
        logging.warning(f"FlightRadar24: login נכשל — {_e}. יפעל במצב בסיסי ללא trail.")  # Cloudflare עלול לחסום
else:
    logging.info("FlightRadar24: רץ ללא login — trail לא יהיה זמין")  # מצב בסיסי — מיקום נוכחי בלבד


@app.route("/flight_route", methods=["GET"])
def get_flight_route():
    """
    מחזיר מסלול טיסה (trail) ופרטים לטיסה לפי callsign או מספר טיסה.
    פרמטר: flight — מספר הטיסה או callsign (למשל: LY001, ELY001)
    אם FR24 חוסם את ה-trail (403), מחזיר מיקום נוכחי בלבד ללא מסלול.
    """
    flight_number = request.args.get("flight", "").strip().upper()  # קריאת פרמטר הטיסה

    if not flight_number:
        logging.error("חסר פרמטר flight בבקשה")
        return jsonify({"error": "יש לספק מספר טיסה (פרמטר 'flight')"}), 400

    try:
        # ── חיפוש ממוקד לפי קידומת ICAO ──
        # get_flights() ללא פילטר מחזיר ~1500 טיסות בלבד מדגימה כלל-עולמית.
        # get_flights(airline="ELY") מחזיר את כל הטיסות הפעילות של אותה חברה — הרבה יותר אמין.
        # הבעיה: משתמש מקליד "LY001" (IATA), ה-API מצפה ל-ICAO ("ELY") → פתרון: _resolve_icao.
        prefix_match = re.match(r'^([A-Z]{2,4})', flight_number)
        raw_prefix   = prefix_match.group(1) if prefix_match else None
        icao_prefix  = _resolve_icao(raw_prefix) if raw_prefix else None  # LY → ELY

        all_flights = []
        if icao_prefix:
            try:
                all_flights = fr_api.get_flights(airline=icao_prefix)
                logging.info(f"get_flights(airline={icao_prefix}): {len(all_flights)} טיסות")
            except Exception as prefix_err:
                logging.warning(f"get_flights(airline={icao_prefix}) נכשל: {prefix_err}")

        # נרמול: LY001 → LY1 לצורך השוואה עם f.number (שמאוחסן בלי אפסים)
        normalized_input = _normalize_flight_num(flight_number)

        def _find_in_list(flights):
            """ מחפש התאמה ברשימת טיסות משני כיוונים: לפי callsign (הכלה חלקית) או לפי מספר טיסה מנורמל (שוויון מדויק). """
            return [
                f for f in flights
                if (f.callsign and flight_number   in f.callsign.upper())
                or (f.number  and normalized_input == f.number.upper())
            ]

        matching = _find_in_list(all_flights)

        # fallback גלובלי — תמיד מנסה, כי all_flights הממוקד עשוי להחזיר תוצאות חלקיות
        if not matching:
            try:
                global_flights = fr_api.get_flights()
                logging.info(f"get_flights() גלובלי: {len(global_flights)} טיסות")
                matching = _find_in_list(global_flights)
            except Exception as global_err:
                logging.warning(f"get_flights() גלובלי נכשל: {global_err}")

        # fallback search() — מאתר לפי callsign גם כשהטיסה לא מוצגת ב-get_flights
        if not matching:
            try:
                search_res = fr_api.search(flight_number)
                live = []
                if isinstance(search_res, dict):
                    live = search_res.get("live", search_res.get("flights", []))
                elif isinstance(search_res, list):
                    live = search_res
                logging.info(f"search({flight_number}): {len(live)} תוצאות")
                for item in live:
                    label = ""
                    fid   = ""
                    if isinstance(item, dict):
                        label = str(item.get("label", item.get("callsign", ""))).upper()
                        fid   = str(item.get("id", item.get("flight_id", "")))
                    if flight_number in label and fid:
                        logging.info(f"נמצא via search: id={fid}, label={label}")
                        details = fr_api.get_flight_details(fid)
                        trail = details.get("trail", [])
                        airports     = details.get("airport", {})
                        origin_iata  = airports.get("origin",      {}).get("code", {}).get("iata", "N/A")
                        origin_name  = airports.get("origin",      {}).get("name", "")
                        dest_iata    = airports.get("destination", {}).get("code", {}).get("iata", "N/A")
                        dest_name    = airports.get("destination", {}).get("name", "")
                        aircraft_mdl = details.get("aircraft", {}).get("model", {}).get("text", "לא ידוע")
                        airline_name = details.get("airline",  {}).get("name", "לא ידוע")
                        norm_trail = [p for p in (_normalize_trail_point(pt) for pt in trail) if p is not None]
                        if len(norm_trail) > 400:
                            norm_trail = norm_trail[-400:]
                        logging.info(f"נשלח מסלול via search עבור {flight_number}: {len(norm_trail)} נקודות")
                        return jsonify({
                            "callsign":    label,
                            "origin_iata": origin_iata, "origin_name": origin_name,
                            "dest_iata":   dest_iata,   "dest_name":   dest_name,
                            "aircraft":    aircraft_mdl, "airline":    airline_name,
                            "altitude": details.get("trail", [{}])[-1].get("alt", 0) if norm_trail else 0,
                            "speed":    details.get("trail", [{}])[-1].get("spd", 0) if norm_trail else 0,
                            "heading":  details.get("trail", [{}])[-1].get("hd",  0) if norm_trail else 0,
                            "lat": norm_trail[-1]["lat"] if norm_trail else None,
                            "lng": norm_trail[-1]["lng"] if norm_trail else None,
                            "trail": norm_trail
                        })
            except Exception as search_err:
                logging.warning(f"search() fallback נכשל עבור {flight_number}: {search_err}")

        if not matching:
            logging.warning(f"לא נמצאה טיסה: {flight_number}")
            return jsonify({"error": f"לא נמצאה טיסה פעילה עם מספר {flight_number}. ייתכן שהטיסה נחתה או טרם המריאה."}), 404

        flight = matching[0]  # הטיסה הראשונה שנמצאה

        # ── שליפת פרטים מלאים כולל trail ──
        trail        = []
        origin_iata  = "N/A"
        origin_name  = ""
        dest_iata    = "N/A"
        dest_name    = ""
        aircraft_model = "לא ידוע"
        airline_name   = "לא ידוע"

        try:
            details = fr_api.get_flight_details(flight)  # דורש login — יכשל ב-403 בלעדיו
            flight.set_flight_details(details)

            trail = details.get("trail", [])  # רשימת נקודות [{lat, lng, alt, spd, ts}]

            airports       = details.get("airport", {})
            origin_iata    = airports.get("origin",      {}).get("code", {}).get("iata", "N/A")
            origin_name    = airports.get("origin",      {}).get("name", "")
            dest_iata      = airports.get("destination", {}).get("code", {}).get("iata", "N/A")
            dest_name      = airports.get("destination", {}).get("name", "")
            aircraft_model = details.get("aircraft", {}).get("model", {}).get("text", "לא ידוע")
            airline_name   = details.get("airline",  {}).get("name", "לא ידוע")

        except Exception as detail_err:
            # 403 או כל שגיאת פרטים — חוזרים למיקום נוכחי בלבד מ-get_flights
            logging.warning(f"get_flight_details נכשל עבור {flight_number}: {detail_err}. מחזיר מיקום נוכחי בלבד.")

        # נרמול מפתחות trail — FR24 מחזיר לעיתים Lat/Lng (גדולות) ולא lat/lng
        trail = [p for p in (_normalize_trail_point(pt) for pt in trail) if p is not None]

        # שמירת המיקום הנוכחי לפני השינוי — ישמש כ-fallback
        current_lat = getattr(flight, "latitude",  None)  # getattr עם ברירת מחדל — שדות עשויים לא להתקיים אם FR24 שינה מבנה
        current_lng = getattr(flight, "longitude", None)

        # אם trail ריק — בונים נקודה בודדת מהמיקום הנוכחי של ה-flight
        if not trail and current_lat is not None and current_lng is not None:
            trail = [{"lat": current_lat, "lng": current_lng, "alt": getattr(flight, "altitude", 0), "spd": 0}]

        # הגבלה ל-400 נקודות אחרונות — מספיק לציור מסלול, מונע JSON כבד
        if len(trail) > 400:
            trail = trail[-400:]

        logging.info(f"נשלח מסלול עבור {flight_number}: {len(trail)} נקודות")

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
            "lat":         current_lat,   # מיקום נוכחי — fallback כשtrail ריק
            "lng":         current_lng,
            "trail":       trail
        })

    except Exception as e:
        logging.error(f"שגיאה בשליפת מסלול טיסה {flight_number}: {e}")
        return jsonify({"error": f"שגיאה פנימית: {str(e)}"}), 500


@app.route("/flight_search", methods=["GET"])
def search_flights():
    """
    מחזיר רשימת callsigns של טיסות שמתאימות לחיפוש.
    משמש לאוטוקומפליט בממשק.
    פרמטר: q — תחילית מספר הטיסה (מינימום 2 תווים)
    """
    query = request.args.get("q", "").strip().upper()  # שאילתת החיפוש

    if len(query) < 2:
        return jsonify([])  # מינימום 2 תווים — מונע שליפת כל הטיסות

    try:
        prefix_match = re.match(r'^([A-Z]{2,4})', query)
        raw_prefix    = prefix_match.group(1) if prefix_match else None
        airline_prefix = _resolve_icao(raw_prefix) if raw_prefix else None  # LY → ELY
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
        ][:20]  # מגבלה של 20 תוצאות לביצועים
        return jsonify(results)

    except Exception as e:
        logging.error(f"שגיאה בחיפוש טיסות: {e}")
        return jsonify([])  # רשימה ריקה בשגיאה — לא קורס את הממשק


if __name__ == "__main__":
    app.run(port=5004, debug=True)  # השרת רץ על פורט 5004 — נפרד משאר השרתים
