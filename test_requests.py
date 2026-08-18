"""
בדיקות תקינות (health checks) לשלושת שרתי ה-Flask של הפרויקט: GeoServer (5003),
WeatherServer (5002), FlightServer (5004).

ריצה כ-CLI:  python test_requests.py  — מדפיס תוצאה לכל בדיקה ואחוז תקינות כולל.
ריצה כמודול: from test_requests import run_health_checks, summarize — נצרך ע"י
             ProcessDashboard ב-main.py להצגת אחוז תקינות ותקלות פר-שרת בדשבורד.
"""
import concurrent.futures  # threads מקבילים לבדיקות עומס
import sys  # קידוד stdout ב-CLI
import time  # מדידת elapsed_ms
from dataclasses import dataclass  # מבני TestCase/TestResult/LoadTestCase
from typing import Callable, Optional  # טיפוסי type hints לשדות אופציונליים ולפונקציית validate

import requests  # ירי הבקשות בפועל לשרתים

from ports import GEO_PORT, WEATHER_PORT, FLIGHT_PORT

DEFAULT_HOST = "127.0.0.1"  # לא "localhost" — Windows מנסה IPv6 (::1) קודם ונופל חזרה ל-IPv4 רק אחרי delay של ~2 שניות לכל קריאה


@dataclass
class TestCase:
    server: str  # תווית שרת — תואמת ל-ProcessDashboard.SERVERS ב-main.py
    port: int
    name: str
    method: str
    path: str
    params: Optional[dict] = None
    json_body: Optional[dict] = None
    timeout: float = 10.0
    validate: Optional[Callable] = None  # (response) -> (ok: bool, message: str); ברירת מחדל: סטטוס < 500


@dataclass
class TestResult:
    server: str
    name: str
    ok: bool
    status: Optional[int]
    message: str
    elapsed_ms: float
    body: str = ""  # גוף התגובה (חתוך) — לא מוצג בטבלה, נצרך ע"י security_checks.py לסריקת דליפת סודות
    category: str = "health"  # "health" | "load" — נצרך ע"י רשת השעונים 3×3 בדשבורד (main.py) לחלוקה לעמודות


def _default_validate(response):
    """ ולידציה כללית לבדיקות בלי validate מפורש — רק מוודאת שהשרת לא קרס (5xx). """
    if response.status_code >= 500:
        return False, f"סטטוס {response.status_code}"
    return True, f"סטטוס {response.status_code}"


def _validate_json_keys(*keys):
    """ מחזיר פונקציית ולידציה שבודקת שכל keys קיימים בגוף ה-JSON — משמש ל-endpoints שמחזירים מבנה קבוע. """
    def _v(response):
        if response.status_code >= 500:
            return False, f"סטטוס {response.status_code}"
        if response.status_code >= 400:
            return True, f"סטטוס {response.status_code} (תגובת שגיאה תקינה)"  # 4xx נחשב תקין כאן — הבדיקה בודקת שהשרת לא קרס, לא שהבקשה הצליחה עסקית
        try:
            data = response.json()
        except ValueError:
            return False, "תגובה אינה JSON תקין"
        missing = [k for k in keys if k not in data]
        if missing:
            return False, f"חסרים שדות: {', '.join(missing)}"
        return True, f"סטטוס {response.status_code}, שדות תקינים"
    return _v


def _validate_list(response):
    """ מוודא שהתגובה היא JSON array — משמש ל-endpoints שמחזירים רשימת תוצאות (חיפוש, heatmap וכו'). """
    if response.status_code >= 500:
        return False, f"סטטוס {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return False, "תגובה אינה JSON תקין"
    if not isinstance(data, list):
        return False, "תגובה אינה רשימה"
    return True, f"סטטוס {response.status_code}, {len(data)} תוצאות"


def _validate_client_error(response):
    """ לבדיקות קלט חסר/שגוי: מוודא שהשרת דוחה אקטיבית עם 4xx — ולא קורס (5xx) או ממשיך בשקט עם 200. """
    if 400 <= response.status_code < 500:
        return True, f"סטטוס {response.status_code} (שגיאת קלט זוהתה כראוי)"
    if response.status_code >= 500:
        return False, f"סטטוס {response.status_code} — קרס במקום להחזיר שגיאת קלט"
    return False, f"סטטוס {response.status_code} — קלט חסר לא זוהה (חסרה ולידציה?)"


def _validate_empty_list(response):
    """ ל-query קצר מדי לחיפוש טיסות: מוודא שהשרת מחזיר [] במקום לנסות לחפש/לקרוס. """
    if response.status_code != 200:
        return False, f"סטטוס {response.status_code} (צפוי 200 עם רשימה ריקה)"
    try:
        data = response.json()
    except ValueError:
        return False, "תגובה אינה JSON תקין"
    if data != []:
        n = len(data) if isinstance(data, list) else "?"
        return False, f"צפויה רשימה ריקה, התקבלו {n} תוצאות"
    return True, "סטטוס 200, רשימה ריקה כצפוי"


def _validate_expected_status(expected):
    """ לבדיקות method-tampering: מוודא שה-status הוא בדיוק expected (בד"כ 405 Method Not Allowed). """
    def _v(response):
        if response.status_code == expected:
            return True, f"סטטוס {response.status_code} כצפוי"
        if response.status_code >= 500:
            return False, f"סטטוס {response.status_code} — קרס במקום להחזיר {expected}"
        return False, f"סטטוס {response.status_code}, צפוי {expected}"
    return _v


def _validate_elevation_truncated(response):
    """ ל-/elevation עם payload גדול מ-100 נקודות: מוודא שהשרת חותך ל-100 (per code) ולא מנסה לשלוח את כולן ל-Open-Meteo. """
    if response.status_code >= 500:
        return False, f"סטטוס {response.status_code}"
    if response.status_code != 200:
        return False, f"סטטוס {response.status_code} (צפוי 200 עם רשימה חתוכה)"
    try:
        data = response.json()
    except ValueError:
        return False, "תגובה אינה JSON תקין"
    results = data.get("results", [])
    if len(results) > 100:  # מגבלת ה-API החיצוני (Open-Meteo) לבקשה בודדת — השרת אמור לאכוף אותה
        return False, f"התקבלו {len(results)} תוצאות — אמור לחתוך ל-100 לכל היותר"
    return True, f"סטטוס 200, {len(results)} תוצאות (חתוך נכון)"


# נקודות הבדיקה תואמות לנתיבים בפועל ב-geo_server.py / weather_server.py / flight_server.py.
# בדיקות שתלויות ב-API חיצוני (Google/OpenWeather/FR24) מקבלות גם 4xx/5xx עסקי כתקין —
# המטרה היא לוודא שהשרת עצמו מגיב כראוי, לא לבדוק תקפות מפתחות API.
TEST_CASES = [
    # --- GeoServer (5003) ---
    TestCase("GeoServer", GEO_PORT, "GET /metrics", "GET", "/metrics",
             validate=_validate_json_keys("uptime_sec", "endpoints")),
    TestCase("GeoServer", GEO_PORT, "GET /geo_data (תל אביב)", "GET", "/geo_data",
             params={"location": "תל אביב"}),
    TestCase("GeoServer", GEO_PORT, "GET /geo_data (חסר location)", "GET", "/geo_data",
             validate=_validate_client_error),
    TestCase("GeoServer", GEO_PORT, "DELETE /geo_data (method tampering)", "DELETE", "/geo_data",
             validate=_validate_expected_status(405)),

    # --- WeatherServer (5002) ---
    TestCase("WeatherServer", WEATHER_PORT, "GET /metrics", "GET", "/metrics",
             validate=_validate_json_keys("uptime_sec", "endpoints")),
    TestCase("WeatherServer", WEATHER_PORT, "GET /weather (קואורדינטות)", "GET", "/weather",
             params={"lat": 32.0853, "lon": 34.7818}),
    TestCase("WeatherServer", WEATHER_PORT, "GET /weather (region)", "GET", "/weather",
             params={"region": "תל אביב"}),
    TestCase("WeatherServer", WEATHER_PORT, "GET /weather (חסרים פרמטרים)", "GET", "/weather",
             validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "GET /weather (lat/lon לא מספריים)", "GET", "/weather",
             params={"lat": "abc", "lon": "xyz"}),
    TestCase("WeatherServer", WEATHER_PORT, "DELETE /weather (method tampering)", "DELETE", "/weather",
             validate=_validate_expected_status(405)),
    TestCase("WeatherServer", WEATHER_PORT, "GET /heatmap_data", "GET", "/heatmap_data",
             validate=_validate_list),
    TestCase("WeatherServer", WEATHER_PORT, "POST /elevation", "POST", "/elevation",
             json_body={"locations": [{"latitude": 31.7683, "longitude": 35.2137}]},
             validate=_validate_json_keys("results"), timeout=15),
    TestCase("WeatherServer", WEATHER_PORT, "POST /elevation (חסרות נקודות)", "POST", "/elevation",
             json_body={}, validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "POST /elevation (500 נקודות — בדיקת חיתוך)", "POST", "/elevation",
             json_body={"locations": [{"latitude": 31.5 + i * 0.001, "longitude": 34.8 + i * 0.001} for i in range(500)]},
             validate=_validate_elevation_truncated, timeout=15),
    TestCase("WeatherServer", WEATHER_PORT, "GET /elevation (method tampering)", "GET", "/elevation",
             validate=_validate_expected_status(405)),
    TestCase("WeatherServer", WEATHER_PORT, "POST /temp_grid", "POST", "/temp_grid",
             json_body={"southwest": {"lat": 32.05, "lng": 34.75}, "northeast": {"lat": 32.10, "lng": 34.80}},
             validate=_validate_list, timeout=20),
    TestCase("WeatherServer", WEATHER_PORT, "POST /temp_grid (חסרים גבולות)", "POST", "/temp_grid",
             json_body={}, validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los", "GET", "/los",
             params={"lat1": 31.7683, "lon1": 35.2137, "lat2": 32.0853, "lon2": 34.7818},
             validate=_validate_json_keys("points", "total_km"), timeout=20),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los (חסרים פרמטרים)", "GET", "/los",
             validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los (קואורדינטות לא מספריות)", "GET", "/los",
             params={"lat1": "abc", "lon1": "abc", "lat2": "abc", "lon2": "abc"},
             validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los_radial/start", "GET", "/los_radial/start",
             # מגזר קטן/גס (30°, 4 כיוונים) — הבדיקה בודקת רק שה-job מתחיל כראוי, לא מחכה לתוצאה
             params={"lat": 31.7683, "lon": 35.2137, "range_km": 3, "angle_step_deg": 90},
             validate=_validate_json_keys("job_id")),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los_radial/start (חסרים פרמטרים)", "GET", "/los_radial/start",
             validate=_validate_client_error),
    TestCase("WeatherServer", WEATHER_PORT, "GET /los_radial/status (job_id לא קיים)", "GET", "/los_radial/status",
             params={"job_id": "00000000-0000-0000-0000-000000000000"},
             validate=_validate_client_error),

    # --- FlightServer (5004) ---
    TestCase("FlightServer", FLIGHT_PORT, "GET /metrics", "GET", "/metrics",
             validate=_validate_json_keys("uptime_sec", "endpoints")),
    TestCase("FlightServer", FLIGHT_PORT, "GET /flight_search", "GET", "/flight_search",
             params={"q": "LY"}, validate=_validate_list, timeout=20),
    TestCase("FlightServer", FLIGHT_PORT, "GET /flight_search (שאילתה קצרה מדי)", "GET", "/flight_search",
             params={"q": "L"}, validate=_validate_empty_list),
    TestCase("FlightServer", FLIGHT_PORT, "GET /flight_route (טיסה לא קיימת)", "GET", "/flight_route",
             params={"flight": "ZZ0000000"},
             validate=_validate_json_keys("error"), timeout=20),
    TestCase("FlightServer", FLIGHT_PORT, "GET /flight_route (חסר flight)", "GET", "/flight_route",
             validate=_validate_client_error),
    TestCase("FlightServer", FLIGHT_PORT, "GET /flight_route (תווי הזרקה/script)", "GET", "/flight_route",
             params={"flight": "<script>alert(1)</script>"}, timeout=20),
    TestCase("FlightServer", FLIGHT_PORT, "POST /flight_route (method tampering)", "POST", "/flight_route",
             validate=_validate_expected_status(405)),
]


@dataclass
class LoadTestCase:
    server: str
    port: int
    name: str
    method: str = "GET"
    path: str = "/metrics"
    params: Optional[dict] = None
    concurrency: int = 10
    total_requests: int = 30
    timeout: float = 10.0


# בדיקות עומס — רק על endpoints מקומיים/קלים (לא קוראים ל-API חיצוני) כדי לא לגרום
# ל-rate limiting אצל Open-Meteo/OpenWeather/FR24 מ-30 בקשות מקבילות.
LOAD_TEST_CASES = [
    LoadTestCase("GeoServer", GEO_PORT, "עומס: 30 בקשות מקבילות ל-/metrics", path="/metrics"),
    LoadTestCase("WeatherServer", WEATHER_PORT, "עומס: 30 בקשות מקבילות ל-/metrics", path="/metrics"),
    LoadTestCase("WeatherServer", WEATHER_PORT, "עומס: 30 בקשות מקבילות ל-/heatmap_data", path="/heatmap_data"),
    LoadTestCase("FlightServer", FLIGHT_PORT, "עומס: 30 בקשות מקבילות ל-/metrics", path="/metrics"),
]


def _run_single_case(case, host):
    """ מריץ TestCase בודד ומחזיר TestResult — תופס בנפרד connection refused/timeout/שגיאה כללית
    כדי שההודעה תהיה ברורה (לא רק "Exception") ושבדיקה אחת שנכשלת לא תפיל את כל הרצף. """
    url = f"http://{host}:{case.port}{case.path}"
    start = time.perf_counter()
    body = ""
    try:
        resp = requests.request(case.method, url, params=case.params, json=case.json_body, timeout=case.timeout)
        validate = case.validate or _default_validate  # ולידציה מותאמת אם הוגדרה, אחרת ברירת המחדל
        ok, message = validate(resp)
        status = resp.status_code
        body = resp.text[:50000]  # חתוך — נצרך רק לסריקת סודות ב-security_checks.py, לא מוצג
    except requests.exceptions.ConnectionError:
        ok, status, message = False, None, "השרת לא מגיב (Connection refused)"  # השרת כבוי/לא עלה עדיין
    except requests.exceptions.Timeout:
        ok, status, message = False, None, f"תם הזמן הקצוב ({case.timeout:.0f}s)"
    except Exception as e:
        ok, status, message = False, None, f"שגיאה: {e}"  # רשת נכשלה מסיבה אחרת — לא מפילים את שאר הבדיקות
    elapsed_ms = (time.perf_counter() - start) * 1000
    return TestResult(case.server, case.name, ok, status, message, elapsed_ms, body)


def _run_load_case(case, host):
    """ יורה total_requests בקשות ב-concurrency worker-threads מקבילים לאותו endpoint, ומוודא שכולן חוזרות 200 — חושף כשלים שרק מופיעים תחת עומס מקביל (למשל שרת Flask יחיד-thread שנתקע/מפיל בקשות). """
    url = f"http://{host}:{case.port}{case.path}"

    def _one():
        """ בקשה בודדת מתוך ה-batch המקביל — לא זורקת חריגה החוצה, מחזירה (status, ms) גם בכישלון. """
        req_start = time.perf_counter()
        try:
            resp = requests.request(case.method, url, params=case.params, timeout=case.timeout)
            return resp.status_code, (time.perf_counter() - req_start) * 1000
        except Exception:
            return None, (time.perf_counter() - req_start) * 1000  # status=None מסמן כישלון — נספר כ-fail בהמשך

    start_all = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=case.concurrency) as pool:
        outcomes = [f.result() for f in [pool.submit(_one) for _ in range(case.total_requests)]]  # יורה את כל הבקשות במקביל ומחכה לכולן
    total_elapsed_ms = (time.perf_counter() - start_all) * 1000

    ok_count = sum(1 for status, _ in outcomes if status == 200)
    fail_count = case.total_requests - ok_count
    durations = [ms for _, ms in outcomes]
    avg_ms = sum(durations) / len(durations) if durations else 0
    max_ms = max(durations) if durations else 0

    message = f'{ok_count}/{case.total_requests} הצליחו, ממוצע {avg_ms:.0f}ms, מקסימום {max_ms:.0f}ms, סה"כ {total_elapsed_ms:.0f}ms'
    if fail_count:
        message += f" — {fail_count} נכשלו/timeout"

    return TestResult(case.server, case.name, fail_count == 0, 200 if fail_count == 0 else None, message,
                       total_elapsed_ms, category="load")


def run_health_checks(host=DEFAULT_HOST, cases=None, load_cases=None, on_progress=None):
    """
    מריץ את כל בדיקות התקינות (כולל בדיקות עומס) ומחזיר רשימת TestResult.
    :param on_progress: callback אופציונלי(result) שנקרא אחרי כל בדיקה בודדת — לעדכון UI חי.
    """
    cases = TEST_CASES if cases is None else cases  # ניתן להזריק רשימת cases מותאמת (למשל security_checks עובר load_cases=[])
    load_cases = LOAD_TEST_CASES if load_cases is None else load_cases
    results = []
    for case in cases:
        result = _run_single_case(case, host)
        results.append(result)
        if on_progress:
            on_progress(result)  # מדווח מיד — הטבלה בדשבורד מתמלאת בהדרגה, לא בבת אחת בסוף
    for case in load_cases:
        result = _run_load_case(case, host)
        results.append(result)
        if on_progress:
            on_progress(result)
    return results


def summarize(results):
    """מחזיר (health_percent, per_server dict {server: (ok_count, total_count)})."""
    if not results:
        return 0.0, {}
    per_server = {}
    for r in results:
        ok_count, total = per_server.get(r.server, (0, 0))
        per_server[r.server] = (ok_count + (1 if r.ok else 0), total + 1)  # צבירת ok/total לכל שרת בנפרד
    total_ok = sum(1 for r in results if r.ok)
    health_percent = round(100.0 * total_ok / len(results), 1)
    return health_percent, per_server


def _print_report(results):
    """ דוח טקסטואלי לריצה כ-CLI (python test_requests.py) — main.py משתמש בתוצאות ישירות, לא בפונקציה הזו. """
    print("=" * 60)
    print("בדיקת תקינות שרתים — maps-gui")
    print("=" * 60)
    current_server = None
    for r in results:
        if r.server != current_server:  # מדפיס כותרת שרת חדשה רק כשעוברים לשרת אחר — התוצאות כבר מקובצות לפי סדר ה-cases
            current_server = r.server
            print(f"\n{current_server}:")
        icon = "✓" if r.ok else "✗"
        print(f"  {icon} {r.name:35s} {r.elapsed_ms:7.0f}ms  {r.message}")

    health_percent, per_server = summarize(results)
    print("\n" + "-" * 60)
    for server, (ok_count, total) in per_server.items():
        print(f"{server}: {ok_count}/{total} תקין")
    print(f"\nתקינות כוללת: {health_percent}%")
    print("=" * 60)


if __name__ == "__main__":
    # מסוף Windows בעברית עובד לפעמים עם cp1255 כברירת מחדל, שלא תומך בסימני ✓/✗ —
    # מכריחים UTF-8 כדי שהדוח יודפס תקין גם שם.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    _print_report(run_health_checks())
