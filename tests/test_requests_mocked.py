"""
F-022 (QA engagement, Stage 6): גרסת-mock של test_requests.py.

test_requests.py המקורי יורה בקשות HTTP אמיתיות (ברשת) לשלושת שרתי ה-Flask של הפרויקט,
ששם קוד ה-route שלהם קורא עוד רשתית ל-API חיצוניים אמיתיים (Google Geocoding,
OpenWeatherMap, Nominatim, Open-Meteo, FlightRadar24) — זה מה שגרם לו להיות מסומן
"חסור" (blocked) ב-QA engagement, שאוסר בקשות-רשת אמיתיות ל-API חיצוניים בזמן ריצת-בדיקות.

הקובץ הזה סוגר את הפער בלי להפר את האילוץ: מייבא את TEST_CASES האמיתיים מ-test_requests.py
(לא משכפל אותם), ומריץ כל אחד מהם נגד קוד ה-route *האמיתי* של geo_server.py/weather_server.py/
flight_server.py — אבל נתב ב-process דרך app.test_client() של Flask (אין socket אמיתי בכלל),
עם כל קריאת-רשת חיצונית בתוך קוד ה-route עצמו ממוקה via unittest.mock.patch. שכבת-הגנה
נוספת (_block_real_sockets) חוסמת כל ניסיון חיבור-socket אמיתי במהלך כל הריצה — כך שאפילו
אם מוק כלשהו "התפספס", הבדיקה תיכשל בצורה רועשת במקום לשלוח בקשה אמיתית בפועל.

הרצה: python tests/test_requests_mocked.py  — מתוך שורש הפרויקט, עם ה-.venv הראשי
(לא .qa/.venv!) מופעל, כי צריך את התלויות האמיתיות של הפרויקט (flask, requests, FlightRadar24 וכו').

הערה: LOAD_TEST_CASES (בדיקות-עומס מקבילות) לא נכללות כאן בכוונה — הן בודקות concurrency
מול socket אמיתי על פורט מקומי, לא תלות ב-API חיצוני, ולכן שייכות לסוג-בדיקה אחר ולא
לפער ש-F-022 נועד לסגור.
"""
import json
import os
import socket
import sys
from unittest import mock

import requests

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)  # Q-6 (14/11/2026): tests/ -> שורש הפרויקט (רמה אחת, לא שתיים כמו ב-.qa/tests/ הישן)
sys.path.insert(0, _PROJECT_ROOT)  # כדי לייבא geo_server/weather_server/flight_server/test_requests/ports מהשורש


def _block_real_socket_connect(self, address):
    """מופעל כ-mock.patch על socket.socket.connect לכל אורך הריצה — שכבת-הגנה אחרונה: גם אם
    מוק כלשהו ברמת requests.get התפספס, כל ניסיון-חיבור-רשת אמיתי (TCP/IP בפועל) נחסם כאן
    ונכשל בצורה רועשת, במקום לצאת בשקט לרשת. test_client() של Flask לא עובר דרך socket
    אמיתי בכלל (WSGI in-process) — אז זה לא פוגע בדיספאץ' של הבדיקות עצמן."""
    raise RuntimeError(
        f"test_requests_mocked.py: נחסם ניסיון חיבור-רשת אמיתי (אסור ב-QA engagement, F-022): {address}"
    )


_socket_guard = mock.patch.object(socket.socket, "connect", _block_real_socket_connect)
_socket_guard.start()  # לא נעצר בכוונה — נשאר פעיל עד שה-process הזה עצמו מסתיים (ר' תיעוד המודול)

import test_requests  # noqa: E402 — TEST_CASES + validate helpers האמיתיים, לא משוכפלים (לאחר הפעלת ה-socket guard)
import geo_server  # noqa: E402
import weather_server  # noqa: E402
import flight_server  # noqa: E402
from ports import GEO_PORT, WEATHER_PORT, FLIGHT_PORT  # noqa: E402


class _FakeExternalResponse:
    """מחקה את חלק-הממשק של requests.Response שקוד ה-route עצמו משתמש בו (status_code,
    json() כ-method, raise_for_status) — זה מה ש-requests.get הממוקה מחזיר במקום תגובה אמיתית."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} שגיאת HTTP (מדומה, F-022)")


class _FlaskResponseAdapter:
    """עוטף תגובת test_client() (werkzeug TestResponse) בממשק requests.Response המצומצם
    שפונקציות ה-validate המקוריות של test_requests.py מצפות לו: ב-werkzeug .json הוא
    property, לא method כמו ב-requests האמיתי — בלי העטיפה הזו case.validate(response)
    הקיים היה נכשל על `response.json()` (TypeError: 'dict' object is not callable)."""

    def __init__(self, flask_response):
        self.status_code = flask_response.status_code
        self.text = flask_response.get_data(as_text=True)

    def json(self):
        if not self.text:
            raise ValueError("גוף תגובה ריק — אינו JSON")
        return json.loads(self.text)


def _fake_requests_get(url, params=None, headers=None, timeout=None):
    """מדמה את כל ה-URLs החיצוניים שה-route-handlers קוראים להם בפועל (geo_server.py +
    weather_server.py) — אותרו ב-grep על requests.get בשני הקבצים: Google Geocoding
    (/geo_data), Nominatim (geocode_region_nominatim), OpenWeatherMap (/weather), Open-Meteo
    elevation (/elevation, /los, _fetch_elevations — /los_radial ו-/radar_doppler ברקע),
    Open-Meteo forecast (/temp_grid). מאותר לפי תת-מחרוזת ב-URL.
    חובה בפונקציה *אחת* משותפת: geo_server.py ו-weather_server.py שניהם עשו "import requests" —
    זה אותו אובייקט-מודול יחיד ב-sys.modules, כך ש-requests.get הוא attribute גלובלי אחד
    ומשותף; שני patch.object נפרדים (אחד per-מודול) היו דורסים זה את זה בפועל (נמצא בריצה
    חיה — ה-mock השני שהוחל "זכה" עבור שתי הקריאות, וה-route קיבל JSON בצורה הלא-נכונה
    וקרס ל-500 עם KeyError/.get ברירת-מחדל ריקה)."""
    params = params or {}

    if "maps.googleapis.com" in url:
        # geo_server.py: /geo_data — TEST_CASES בודק רק מיקום תקין (status=='OK') או שגיאת-קלט-לפני-רשת
        return _FakeExternalResponse(200, {
            "status": "OK",
            "results": [{
                "formatted_address": "Tel Aviv-Yafo, Israel (מדומה, F-022)",
                "geometry": {"location": {"lat": 32.0853, "lng": 34.7818}},
            }],
        })

    if "nominatim.openstreetmap.org" in url:
        # "לא נמצא" — הroute יודע לרדת בחזרה לחיפוש OpenWeather-by-name בלי להישבר (ר' get_weather)
        return _FakeExternalResponse(200, [])

    if "api.openweathermap.org" in url:
        lat, lon = params.get("lat"), params.get("lon")
        if lat is not None:
            try:
                float(lat)
                float(lon)
            except (TypeError, ValueError):
                # תואם את בדיקת ה-TEST_CASE "lat/lon לא מספריים" — OpenWeather האמיתי גם מחזיר 400 כאן
                return _FakeExternalResponse(400, {"cod": "400", "message": "lat/lon לא תקינים (מדומה, F-022)"})
        return _FakeExternalResponse(200, {
            "weather": [{"description": "שמיים בהירים (מדומה, F-022)"}],
            "main": {"temp": 25.0},
            "coord": {
                "lat": float(lat) if lat is not None else 32.08,
                "lon": float(lon) if lon is not None else 34.78,
            },
        })

    if "api.open-meteo.com/v1/elevation" in url:
        n = len([p for p in str(params.get("latitude", "")).split(",") if p])
        return _FakeExternalResponse(200, {"elevation": [100.0] * n})

    if "api.open-meteo.com/v1/forecast" in url:
        n = len([p for p in str(params.get("latitude", "")).split(",") if p])
        item = {"current": {"temperature_2m": 22.0}}
        return _FakeExternalResponse(200, item if n <= 1 else [item] * n)

    raise AssertionError(f"test_requests_mocked.py: URL לא מוכר למוק (F-022, נדרש עדכון המוק): {url}")


class _MockedDispatcher:
    """מתרגם TestCase בודד (מיובא מ-test_requests.py) לקריאת test_client() על ה-Flask app
    הנכון לפי case.port — בלי לפתוח socket אמיתי כלל, ובלי לגעת ב-test_requests.py עצמו."""

    def __init__(self):
        self._clients = {
            GEO_PORT: geo_server.app.test_client(),
            WEATHER_PORT: weather_server.app.test_client(),
            FLIGHT_PORT: flight_server.app.test_client(),
        }

    def run(self, case):
        client = self._clients[case.port]
        flask_resp = client.open(case.path, method=case.method, query_string=case.params, json=case.json_body)
        return _FlaskResponseAdapter(flask_resp)


def run_mocked_health_checks():
    """מריץ את כל test_requests.TEST_CASES (37 בדיקות-תקינות) נגד קוד ה-route האמיתי,
    עם כל קריאת-רשת חיצונית ממוקה. מחזיר רשימת (case, ok, message)."""
    dispatcher = _MockedDispatcher()
    out = []
    # geo_server.py ו-weather_server.py חולקים את אותו requests.get גלובלי (ר' תיעוד
    # _fake_requests_get) — patch *אחד* בלבד, לא אחד per-מודול. ה-with אחד גדול (לא per-case)
    # כדי שגם thread ברקע שנשאר תלוי (מ-/los_radial/start, /radar_doppler/start) ימשיך לפגוש
    # מוק פעיל כל עוד התהליך חי, ולא יצליח "לברוח" לרשת אמיתית בין בדיקה לבדיקה.
    with mock.patch.object(requests, "get", side_effect=_fake_requests_get), \
         mock.patch.object(flight_server.fr_api, "get_flights", return_value=[]), \
         mock.patch.object(flight_server.fr_api, "search", return_value=[]):
        for case in test_requests.TEST_CASES:
            try:
                resp = dispatcher.run(case)
                validate = case.validate or test_requests._default_validate
                ok, message = validate(resp)
            except Exception as e:  # לא מפיל את כל הריצה על כשל-מוק בבדיקה בודדת
                ok, message = False, f"שגיאה בדיספאץ'/מוק: {e}"
            out.append((case, ok, message))
    return out


def _print_report(results):
    print("=" * 70)
    print("test_requests_mocked.py — F-022: בדיקות-תקינות מול test_client() + מוק (אין רשת אמיתית)")
    print("=" * 70)
    current_server = None
    for case, ok, message in results:
        if case.server != current_server:
            current_server = case.server
            print(f"\n{current_server}:")
        icon = "✓" if ok else "✗"
        print(f"  {icon} {case.name:45s} {message}")

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "-" * 70)
    print(f'סה"כ: {passed}/{total} עברו')
    print("=" * 70)
    return passed, total


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    results = run_mocked_health_checks()
    passed, total = _print_report(results)
    sys.exit(0 if passed == total else 1)
