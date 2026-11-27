# חבילת רגרסיה — tests/

**(Q-6, 14/11/2026: הועבר מ-`.qa/tests/` המבודד — מעכשיו חלק קבוע מחבילת-הבדיקות הרגילה של הפרויקט, לא סילו-QA נפרד.)**

הרצה: `.venv/Scripts/python.exe tests/run_regression.py` (מהשורש, עם ה-`.venv` **הראשי** של הפרויקט — לא `.qa/.venv`, כי אלה בדיקות של קוד-הפרויקט עצמו, לא כלי-ניתוח).

## רגרסיה (חייבת לעבור)
`tests/self_test.py` (מנוע mpm/), `tests/test_ballistics_api.py` (שכבת ה-API). שתיהן self-contained, 0 קריאות-רשת-חיצוניות.

## חבילות שהועברו מריצת QA 5 (T0, 27/11/2026)
- `test_r5_radar_algorithmic.py` — תרחיש מייצג לכלי מעקב המכ"ם, בדיקות metamorphic ואנליטיות, ו-Golden Master מול `golden/radar_scenario_golden.json`. חלק מהרגרסיה. עדכון ייחוס רק באישור: `--update-golden`. דוח זמנים: `--update-perf`.
- `test_r5_server_security.py` — CORS, ולידציה, NaN, שמירה אטומית, גבולות ותקרת jobs, מול קובץ עמדות זמני. חלק מהרגרסיה. שורות `[REPRO-CONFIRMED]` מדווחות ממצאים פתוחים בלי להכשיל.
- `fuzz_r5_nan_params.py` — NaN/±Inf בכל פרמטר × 3 סוגי סריקה (261 צירופים, כמה דקות). רץ רק ב-`run_regression.py --full`, ויוצא 1 כל עוד F-032 פתוח.
- הדוחות שהן כותבות נשמרים ב-`.qa/run5/`.

## בדיקות-שחזור לממצאים (עברו — שלב א' של Stage 6 תיקן את כל ארבעתן)
- `test_f011_radar_cancel_return.py` — F-011, `/radar_doppler/cancel` (Web) מחזיר 500. משתמש ב-Flask `test_client()` (WSGI in-process, לא socket/רשת-אמיתית).
- `test_f012_no_stray_webmap.py` — F-012, `web/map.html` שריד-build tracked בגיט.
- `test_f013_osm_attribution.py` — F-013, חסר ייחוס-OpenStreetMap גלוי במפה (נמצא false-positive — הייחוס כבר היה תקין; הבדיקה עודכנה לבדוק את התנאי הנכון).
- `test_f014_secret_env_vars_coverage.py` — F-014, `ANOTHER_API_KEY` חסר מרשימת-הסריקה של `security_checks.py`.

כל ארבעתן עברו תיקון מאושר (Stage 6, שלב א') ועוברות כרגע (exit 0) — `run_regression.py` מדפיס לכל אחת "CLOSED - תוקן". אם אחת מהן תתחיל להיכשל מחדש, זו רגרסיה אמיתית.

## test_requests_mocked.py — F-022
גרסת-mock של `test_requests.py`: מייבא את אותם `TEST_CASES` (37 בדיקות-תקינות, לא משוכפלים) ומריץ כל אחד מהם נגד קוד ה-route האמיתי של `geo_server.py`/`weather_server.py`/`flight_server.py` דרך `test_client()` של Flask (אין socket אמיתי), עם כל קריאת-רשת חיצונית (Google Geocoding/Nominatim/OpenWeatherMap/Open-Meteo/FlightRadar24) ממוקה. שכבת-הגנה נוספת חוסמת כל `socket.socket.connect` אמיתי לכל אורך הריצה. תוצאה נוכחית: 37/37 עוברות, 0 קריאות-רשת-אמיתיות. הרצה: `.venv/Scripts/python.exe tests/test_requests_mocked.py` (מה-`.venv` הראשי — צריך flask/requests/FlightRadar24 אמיתיים).

## לא כלול
- `test_requests.py` עצמו (הגרסה המקורית, מול שרתים חיים אמיתיים) — **חסום** (ר' `.qa/progress.md`, ממצא F-022): רוב ה-TestCase שלו קוראים בפועל ל-APIs חיצוניים אמיתיים. כיסוי שווה-ערך הושג במקומו ב-`test_requests_mocked.py` לעיל.
- `LOAD_TEST_CASES` (בדיקות-עומס מקבילות, מתוך `test_requests.py`) — לא מכוסות ב-`test_requests_mocked.py`: בודקות concurrency מול socket אמיתי על פורט מקומי, לא תלות ב-API חיצוני, ולכן מחוץ לתחום של F-022.

## כלים
כלים סטטיים (bandit/pip-audit/mypy/ruff) + openpyxl/python-docx/matplotlib מותקנים ב-`.qa/.venv` (מבודד), **לא** ב-`.venv` הראשי — הרצה: `.qa/.venv/Scripts/python.exe -m bandit ...` וכו'.
