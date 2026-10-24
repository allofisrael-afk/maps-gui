# bootstrap נתיב-ייבוא — מוסיף את web/lib/ ל-sys.path כדי שהייבואים למטה ימצאו את המודולים
# שם בלי לשנות שמות ייבוא (קובץ זה כמעט-עותק-מדויק של flight_server.py — ר' MAPS-GUI_SRS.md §3.24)
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))

import logging  # רישום אירועים ללוג (stdout ב-web — ה-basicConfig מוגדר ב-server_common.create_app)
import re        # חילוץ קידומת ICAO מה-callsign לחיפוש ממוקד
from flask import jsonify, request  # פענוח פרמטרים — Flask() עצמו נוצר ב-server_common.create_app
from FlightRadar24 import FlightRadar24API  # ספריית Python לשליפת נתוני FR24
from FlightRadar24.core import Core  # קבועי URL/headers של הספרייה — משמשים ב-_fetch_flight_details_direct

from server_common import create_app  # תשתית משותפת — .env/logging/Flask/CORS (גרסת web, ללא /metrics)
# create_app כבר קורא ל-load_dotenv() — טוען גם את FR24_USER/FR24_PASS/FR24_TOKEN בהמשך הקובץ
# ports.FLIGHT_PORT לא נדרש כאן — Vercel מנתב לפי שם-קובץ, לא לפי פורט מקומי קבוע

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
    alt/Alt/altitude, spd/Spd/speed, hd/Hd/heading) למבנה אחיד {lat, lng, alt, spd, hd}.
    מחזיר None אם אין קואורדינטות תקינות (הנקודה תידלג).
    מקור אמת יחיד — היו כאן שני עותקים כמעט-זהים (בנתיב הראשי ובנתיב search())
    שהתבררו כלא-זהים בפועל: אחד מהם לא בדק את המפתחות "altitude"/"speed".
    hd (כיוון) נשמר כ-None אם חסר (לא 0) — 0 הוא כיוון-צפון תקף, אסור לבלבל בין "אין נתון"
    ל"טס צפונה". נדרש ע"י הערכת מסלול טיסה מול מכ"ם-דופלר (ר' weather_server.py).
    """
    pt_lat = point.get("lat") if point.get("lat") is not None else point.get("Lat")
    pt_lng = point.get("lng") if point.get("lng") is not None else (point.get("Lng") or point.get("lon") or point.get("Lon"))
    if pt_lat is None or pt_lng is None:
        return None
    hd = point.get("hd") if point.get("hd") is not None else (point.get("Hd") or point.get("heading"))
    return {
        "lat": pt_lat,
        "lng": pt_lng,
        "alt": point.get("alt") or point.get("Alt") or point.get("altitude") or 0,
        "spd": point.get("spd") or point.get("Spd") or point.get("speed") or 0,
        "hd": hd,
    }


def _fetch_flight_details_direct(flight_id):
    """
    שולף פרטי טיסה מלאים (כולל trail) ישירות מ-FR24 — עוקף את fr_api.get_flight_details()
    הרגיל, שנמצא ב-403 עקבי לכל טיסה (גם עם FR24_TOKEN רענן, וגם לטיסות שבוודאות באוויר).
    הסיבה שנמצאה: get_flight_details() בספרייה לא מצרף שום cookie/הזדהות לבקשה הזו כלל
    (בדוק במקור — FlightRadar24/api.py, שורה 429) — כלומר ה-403 הוא הגנת Cloudflare/זיהוי-בוטים
    לפי טביעת-אצבע HTTP/TLS של הבקשה עצמה, לא היעדר טוקן. curl_cffi (impersonate="chrome")
    מדמה טביעת-אצבע TLS של דפדפן אמיתי ועוקף את זה — אומת ידנית: 200 ו-trail מלא (994 נקודות)
    מול אותו URL בדיוק שהחזיר 403 עם requests/urllib הרגילים של הספרייה.
    Fallback לספרייה המקורית (fr_api.get_flight_details, דרך אותו URL/headers) אם curl_cffi
    לא מותקן או נכשל מסיבה אחרת — כדי שלא לשבור התקנות ישנות בלי התלות החדשה.
    """
    url = Core.flight_data_url.format(flight_id)
    try:
        from curl_cffi import requests as cffi_requests  # ייבוא עצל — נכשל בעדינות אם התלות חסרה
        r = cffi_requests.get(url, impersonate="chrome", headers=Core.json_headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.warning(f"curl_cffi נכשל עבור flight_id={flight_id}: {e}. נופל חזרה לבקשה הרגילה (ללא עקיפת חסימה).")
        from FlightRadar24.request import APIRequest  # ייבוא מקומי — נדרש רק בנתיב ה-fallback
        response = APIRequest(url, headers=Core.json_headers, timeout=15)
        return response.get_content()


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
                        details = _fetch_flight_details_direct(fid)  # אותה עקיפת-403 — גם fid כאן הוא מזהה מחרוזת, לא Flight, ולכן זה גם תיקן קריאה שגויה קודמת ל-fr_api.get_flight_details (שציפתה ל-Flight.id)
                        trail = details.get("trail", [])
                        airports     = details.get("airport", {})
                        origin_iata  = airports.get("origin",      {}).get("code", {}).get("iata", "N/A")
                        origin_name  = airports.get("origin",      {}).get("name", "")
                        dest_iata    = airports.get("destination", {}).get("code", {}).get("iata", "N/A")
                        dest_name    = airports.get("destination", {}).get("name", "")
                        aircraft_mdl  = details.get("aircraft", {}).get("model", {}).get("text", "לא ידוע")
                        aircraft_icao = details.get("aircraft", {}).get("model", {}).get("code")  # ר' הערה מקבילה בנתיב הראשי
                        airline_name  = details.get("airline",  {}).get("name", "לא ידוע")
                        norm_trail = [p for p in (_normalize_trail_point(pt) for pt in trail) if p is not None]
                        if len(norm_trail) > 400:
                            norm_trail = norm_trail[-400:]
                        logging.info(f"נשלח מסלול via search עבור {flight_number}: {len(norm_trail)} נקודות")
                        return jsonify({
                            "callsign":    label,
                            "origin_iata": origin_iata, "origin_name": origin_name,
                            "dest_iata":   dest_iata,   "dest_name":   dest_name,
                            "aircraft":    aircraft_mdl, "aircraft_icao": aircraft_icao, "airline": airline_name,
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
        aircraft_icao  = None  # קוד ICAO קצר (למשל "B77W") — נצרך ב-MAP.py לאמידת RCS אוטומטית, ר' _rcsForAircraftType
        airline_name   = "לא ידוע"

        try:
            details = _fetch_flight_details_direct(flight.id)  # עוקף 403 (ר' תיעוד הפונקציה — לא עניין של login/טוקן)
            flight.set_flight_details(details)

            trail = details.get("trail", [])  # רשימת נקודות [{lat, lng, alt, spd, ts}]

            airports       = details.get("airport", {})
            origin_iata    = airports.get("origin",      {}).get("code", {}).get("iata", "N/A")
            origin_name    = airports.get("origin",      {}).get("name", "")
            dest_iata      = airports.get("destination", {}).get("code", {}).get("iata", "N/A")
            dest_name      = airports.get("destination", {}).get("name", "")
            aircraft_model = details.get("aircraft", {}).get("model", {}).get("text", "לא ידוע")
            aircraft_icao  = details.get("aircraft", {}).get("model", {}).get("code")  # למשל "B77W", "A320" — עשוי להיות None
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
            "aircraft":      aircraft_model,
            "aircraft_icao": aircraft_icao,  # קוד ICAO קצר (או None) — לאמידת RCS אוטומטית ב-MAP.py, לא לתצוגה
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
    # הפעלה מקומית לבדיקה בלבד — ב-Vercel לא מגיעים לכאן בכלל (ר' הערה מקבילה ב-geo.py).
    # פורט 5014 — נפרד מ-FLIGHT_PORT (5004) של הדסקטופ, כדי לא להתנגש אם שתיהן רצות יחד.
    app.run(port=5014, debug=True, threaded=True)
