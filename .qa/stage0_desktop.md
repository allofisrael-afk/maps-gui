# דוח מיפוי Stage 0 — פלטפורמת Desktop (Python/PyQt5) + קוד משותף (mpm/, mpm_api.py)
**Root:** `D:\PY-IS\maps-gui` | **Commit ייחוס:** `c1abf7a9` ("balistic version") | VERSION=`1.0.2`

הערה מתודולוגית: קראתי את כל הקבצים שצוינו במשימה בשלמותם (main.py — 2376 שורות, MAP.py החלקים הרלוונטיים מתוך 5025 שורות, weather_server.py — 1929 שורות במלואו, geo_server.py, flight_server.py, server_common.py, ports.py, security_types.py, security_checks.py, metrics.py, test_requests.py, notam_categories.py, notam_drones.py, icao_glossary.py, uas_coordination_zones.py/airport_ctr_zones.py (ראשים), cis_checks.py (ראש), כל 6 קבצי mpm/, mpm_api.py במלואו, tests/*.py, data/, build_apk.ps1 (ראש)). **הרצתי בפועל** (קריאה-בלבד, ללא שינוי קבצים) את `tests/self_test.py` ו-`tests/test_ballistics_api.py` — שתיהן עברו במלואן. לא הרצתי את `main.py`/השרתים עצמם (GUI+subprocess+רשת חיצונית, לא מתאים לריצת-בדיקה סוכנית חד-כיוונית).

---

## 1. טכנולוגיות (מ-requirements.txt + imports בפועל)

| קטגוריה | פרט |
|---|---|
| שפה | Python (סביבת venv מקומית כאן: 3.14.6; קוד עצמו תואם 3.8+ לפי שם ה-wheel המצורף) |
| GUI | PyQt5==5.15.11 (QMainWindow/QDialog/QThread/QSettings...), PyQtWebEngine==5.15.7 (QWebEngineView/QWebEnginePage — מציג map.html) |
| שרתי Backend | Flask==3.1.3 + flask-cors==6.0.2 — 3 שרתים נפרדים (geo_server.py:5003, weather_server.py:5002, flight_server.py:5004), כל אחד תהליך עצמאי (`subprocess.Popen([sys.executable, "<file>.py"])`) |
| HTTP client | requests==2.33.0 (כל קריאות ה-API), curl_cffi==0.16.1 (עוקף Cloudflare ל-FlightRadar24, ר' סעיף 4) |
| טיסות | FlightRadar24API==1.4.0 (חבילת `FlightRadar24`) |
| ניטור תהליכים | psutil==7.2.2 (CPU/RAM לדשבורד, רשימת חיבורי רשת ל-security_checks) |
| סודות/קונפיג | python-dotenv==1.2.2 (.env) |
| מנוע בליסטי (mpm/) | **stdlib בלבד** — math, dataclasses, bisect, csv, json, os (מאומת: אין import חיצוני באף קובץ ב-mpm/) |
| בדיקות/כלים | pip-audit (אופציונלי, נקרא דרך subprocess ב-security_checks.py, לא ב-requirements.txt) |
| Build | build_apk.ps1 — **Android/Flutter בלבד** (מוריד Flutter SDK + Android cmdline-tools, בונה APK); אין חלק Desktop-ייעודי. יוצר `android_python/` (junctions ל-mpm//data/, hardlink ל-mpm_api.py) כדי ש-Chaquopy יסרוק תיקייה מבודדת — לא קבצים אמיתיים, לא ב-git (ר' `.gitignore`) |
| מפות/טיילים (חוץ, נצרך גם ב-Desktop) | Leaflet 1.9.4 מ-unpkg.com (CDN), OpenTopoMap (ברירת מחדל), OpenStreetMap standard tiles, Esri World Imagery (ArcGIS) — כל השלוש ללא מפתח API |

קבצי wheel/venv מצורפים לריפו: `PyQt5-5.15.11-cp38-abi3-win_amd64.whl`, `.venv/` (לא ב-git, ר' `.gitignore`).

---

## 2. נקודות כניסה

| נקודת כניסה | קובץ:שורה | פרטים |
|---|---|---|
| GUI entry | `main.py:2372` `if __name__=="__main__"` → `QApplication` + `MapApp()` | |
| GeoServer | `geo_server.py:78` `app.run(port=5003, debug=True, threaded=True)` | 2 routes: `GET /geo_data` (Google Geocoding), `GET /uas_notams` |
| WeatherServer | `weather_server.py:1927` `app.run(port=5002, debug=True, threaded=True)` | **21 routes** — ר' טבלה בסעיף 3 |
| FlightServer | `flight_server.py:330` `app.run(port=5004, debug=True, threaded=True)` | `GET /flight_route`, `GET /flight_search` |
| 7 ה-routes הבליסטיים (כולם ב-weather_server.py, כולם POST) | `/ballistics/trajectory` (1809), `/solve` (1827), `/solve_mv` (1845), `/table` (1863), `/calibrate` (1880), `/terrain_check` (1896), `/min_qe_for_crest` (1908) — כולן עטיפות HTTP דקות ל-`mpm_api.py` | |
| כפתורי UI מרכזיים | `main.py` (ר' מלאי מלא בסעיף 6) | |
| QThread workers | `MetricsWorker` (57), `HealthCheckWorker` (167), `SecurityCheckWorker` (185), `WeatherFetchWorker` (201), `FlightFetchWorker` (235) — כולם ב-`main.py` | כולם קיימים ומממשים את מה שהמשימה ציינה |

**/metrics** — נתיב נוסף (GET) שקיים בכל אחד משלושת השרתים דרך `metrics.py::register_metrics(app)` (נקרא מ-`server_common.create_app`) — נצרך ע"י `MetricsWorker`.

---

## 3. מפת תהליכים

| תהליך | טריגר | קלט | מסלול בקוד | פלט/תופעות-לוואי |
|---|---|---|---|---|
| הפעלת שרתים | כפתור "הפעל שרתים" | — | `main.py:toggle_servers→start_servers` (1645) → 3×`subprocess.Popen` | 3 תהליכי Python נפרדים; `_kill_zombie_servers` (807) מריץ `netstat`/`taskkill` לפני כן |
| כיבוי שרתים | כפתור "עצור שרתים" / `closeEvent` | — | `stop_servers` (1718) → `_terminate_process_tree` (1689, psutil) | סגירת פורטים, נורות סטטוס אפורות |
| חיפוש עיר | שדה עיר + "שלח" / Enter | `city_name` (טקסט חופשי) | `save_and_send_city`(1799)→`city_log.txt`→`WeatherFetchWorker`→`/weather?region=`→Nominatim→fallback OpenWeather by-name | מרקר+פוליגון גבול, QSettings history (10) |
| דקירת נ.צ | שדה LAT/LON + "שלח"/debounce 600ms | lat∈[-90,90], lon∈[-180,180] | `submit_coordinates`(2178)/`save_and_send`(1753)→`coordinates_log.txt`→`WeatherFetchWorker`→`/weather?lat&lon` | מרקר+popup (escaped), cache בזיכרון |
| חיפוש טיסה | שדה טיסה+"הצג מסלול"/Enter | `flight_number` | `fetch_and_draw_flight`(967)→`FlightFetchWorker`→`/flight_route`→FR24 (3 fallbacks) | קו מסלול (≤400 נק'), QSettings (15) |
| שכבת NOTAM | תפריט toolbox ✈️NOTAM, 7 checkboxes | בחירת קטגוריה | `toggle_notam_category`(2092)→JS→`/uas_notams`→`notam_drones.get_uas_notams`→scrape brin.iaa.gov.il | שכבת מעגלים/פוליגונים; cache 20 דק' |
| שכבת גבהים/טמפרטורה | כפתור+גרירת מלבן | bbox | JS→`/elevation`/`/temp_grid`→Open-Meteo | heat/grid/dots overlay |
| LOS | כלי 👁, 2 קליקים | lat1/lon1/lat2/lon2 | JS→`/los`→Open-Meteo Elevation | גרף פרופיל+קו חסימה |
| רדיוס-ראייה רדיאלי | כלי 📡 | lat/lon/range_km/... | `/los_radial/start`(job async thread+uuid)→`/status`(polling)→`/cancel` | פוליגון רואה/לא-רואה |
| מכ"ם-דופלר | כלי 🎯 (~20 פרמ') | lat/lon+power/gain/freq/rcs/... | `/radar_doppler/start`→thread→`/status`→`/cancel`; `/profile` סינכרוני; `/evaluate_route/start` | פוליגון כיסוי+הערכת-גילוי-מסלול |
| מסלול-מותאם | — | — | `saved_stations.json["custom_route"]` | — |
| עמדות שמורות | כפתור "שמור עמדה" | tool/name/params | `/stations/save`/`/list`/`/delete`→`saved_stations.json` | תקרה לכלי, מוחק ישן |
| Undo/Redo | Ctrl+Z/Y | — | JS בלבד→`__sync_layer_checkboxes__`→`main.py:_sync_layer_checkboxes`(2131) | Python מסתנכרן בלבד |
| דשבורד תהליכים | כפתור 📊 | — | `open_process_dashboard`(852)→`ProcessDashboard`(334) | 4 לשוניות (סקירה/שרתים/תקינות/אבטחה) |
| דשבורד אבטחה | כפתור 🔒 בדשבורד | — | `SecurityCheckWorker`→`security_checks.run_security_checks` | טבלת ממצאים+remediation |
| כלי מסלול בליסטי | כפתור 💥 | gun/target+qe/azimuth/mv/met/... | JS→`/ballistics/*`(7)→`mpm_api.py`→`mpm/engine.simulate`(RK4) | מסלול+פרופיל+טבלה+calibrate |

---

## 4. משטח תקיפה (Desktop)

| וקטור | מקור | פרטים/סיכון לתיעוד |
|---|---|---|
| קלט משתמש — שדות UI | lat_input/lon_input (QDoubleSpinBox) | סיכון נמוך — טיפוס נומרי מאולץ ע"י Qt |
| קלט משתמש — טקסט חופשי | city_name_input, flight_input | מועבר כפרמטר GET; `test_requests.py` מכיל test-case הזרקה (`<script>alert(1)</script>`) ל-flight — אין ולידציה אקטיבית בצד Flask, רק לא קורס |
| הזרקת JS ל-map_view | `display_weather_on_map` | escaping מפורש (`_js_str_escape`, 2217) — נראה תקין בעיון קוד, אך הגנה ידנית לא ספרייה — מיקוד מומלץ ל-ASVS |
| API חיצוניים (ללא מפתח) | Nominatim, Open-Meteo, brin.iaa.gov.il, unpkg/OpenTopoMap/OSM/ArcGIS tiles | תלות-רשת פעילה; אין אימות-תעודה מיוחד מעבר ל-requests/fetch ברירת-מחדל |
| API חיצוניים עם מפתח | Google Geocoding (HTTPS) · **OpenWeatherMap (`weather_server.py:137` — HTTP לא HTTPS! מפתח ב-GET ברשת לא-מוצפנת)** · FlightRadar24 (cookie/login) | ממצא: תעבורה לא-מוצפנת + API key בפרמטר |
| נכסים רגישים (.env) | OPENWEATHER_API_KEY, GOOGLE_API_KEY, ANOTHER_API_KEY (⚠️ **לא נסרק** ב-`security_checks._SECRET_ENV_VARS`), FR24_USER/PASS/TOKEN | פער-כיסוי בסריקת-סודות |
| קבצי נתונים נטענים | `data/projectiles/generic_155.json`+csv (אין sandboxing/size-limit), `saved_stations.json` | |
| subprocess | `Popen` קבוע (לא קלט-משתמש), `netstat`/`taskkill` (PID מ-parsing, לא חוץ), `security_checks`/`cis_checks`: pip-audit/powershell/secedit (קריאה-בלבד) | אין injection דרך קלט-משתמש |
| curl_cffi impersonation | `flight_server.py:_fetch_flight_details_direct` | מדמה TLS fingerprint של Chrome לעקיפת Cloudflare של FR24 — לתיעוד כ"עקיפת הגנת API צד-ג'" לדיון ToS/ASVS |
| CORS | `CORS(app)` ברירת-מחדל על כל 3 השרתים → `*` (מתועד גם ב-`security_checks` כ-"low" ביודעין, כי map.html נטען מ-file://) | |
| Debug server חשוף | כל 3 ה-Flask apps עם `debug=True` (Werkzeug debugger אינטראקטיבי), מאזינים כרגע ברירת-מחדל (127.0.0.1) | `security_checks._check_bind_exposure` בודק זאת |

---

## 5. דיוק נומרי — mpm/ (מנוע בליסטי)

| פרמטר | ערך/קובץ | הערות |
|---|---|---|
| טיפוסי מספרים | `float` בלבד — אין Decimal/numpy | |
| R_EARTH | `engine.py:27` = `6356766.0` מ' (רדיוס-מקורב) | שונה בכוונה מ-`geodesy.py` (WGS84 אמיתי: A=6378137.0, F=1/298.257223563, Vincenty) — engine.py לתיקון-עקמומיות מקומי, geodesy.py למרחק/אזימוט גלובלי |
| OMEGA_EARTH (קוריוליס) | `7.292115e-5` rad/s | |
| ALPHA_CAP | `radians(20.0)` — מעבר לזה "המודל לא תקף" (אזהרה, לא שגיאה) | |
| dt | ברירת מחדל `0.02`s (RK4); `self_test.py` מאשר התכנסות 0.005↔0.05 (הפרש<0.5מ' ב-~15.7ק"מ) | `min_qe_for_crest` משתמש ב-dt=**0.05** (גס יותר, לסריקה מהירה) |
| אטמוספרה ISA | R_AIR=287.05287, GAMMA=1.4, G0=9.80665, GRID_DZ=25.0מ', TOP_MSL=40000.0מ' | ICAO lapse rates |
| QE_MIN/MAX | mils_to_rad(5.0)/mils_to_rad(1350.0) | מעל ~76° "הקירוב קורס" |
| MILS_PER_CIRCLE | 6400.0 (נאט"ו) | |
| Vincenty tolerance | 1e-12 rad, 200 איטרציות, fallback ל-Haversine (R=6371008.8) | |
| random/seed | **לא נמצא שום שימוש** בכל הקוד (main.py, mpm/, mpm_api.py, שרתים) — אושר בחיפוש גלובלי | רלוונטי ל-determinism |
| אימות בפועל | `self_test.py`+`test_ballistics_api.py` — **הורצו, הכל עבר (OK)** | ר' פירוט בסעיף 10 |

---

## 6. מלאי רכיבי UI (main.py)

| רכיב | סוג Qt | שורה | handler |
|---|---|---|---|
| manage_servers_button | QPushButton | 1052 | `toggle_servers` |
| dashboard_button | QPushButton | 1070 | `open_process_dashboard` |
| geo/weather_status_dot | QLabel | 1059/1062 | — |
| load_map_button | QPushButton | 1086 | `create_map_from_file` |
| home_button | QPushButton | 1094 | `center_map_israel` |
| clear_markers_button | QPushButton | 1102 | `clear_map_markers` |
| Find_a_location | QPushButton | 1118 | `toggle_lat_lon_inputs` |
| input_tabs | QTabWidget | 1126 | — |
| lat/lon_input | QDoubleSpinBox | 1134/1140 | `valueChanged→_restart_debounce` |
| save_send_button/city | QPushButton | 1146/1163 | `save_and_send`/`save_and_send_city` |
| city_name_input/flight_input | QComboBox (editable, QSettings history) | 1158/1355 | Enter handlers |
| heatmap/elevation_button | QPushButton (checkable) | 1182/1244 | `toggle_heatmap`/`toggle_elevation_layer` |
| opacity_slider | QSlider | 1194 | `update_heatmap_opacity` |
| temp/elev_mode_* | QPushButton (checkable ×6) | 1206-1269 | `set_temp_mode`/`set_elev_mode` |
| heatmap_pick/clear_points | QPushButton | 1229/1235 | |
| notam_menu_button | QToolButton+QMenu+7×QCheckBox | 1283-1305 | `toggle_notam_category` |
| uas_coord/airport_ctr_button | QPushButton (checkable) | 1308/1317 | |
| ruler_button/clear | QPushButton | 1330/1338 | |
| show/clear_flight_button | QPushButton | 1366/1371 | |
| toggle_log_button | QPushButton+badge | 1384/1391 | |
| save/clear_log_button | QPushButton | 1396/1403 | |
| map_view | QWebEngineView+LoggingWebEnginePage | 788 | טוען map.html, `titleChanged`→Python |
| ProcessDashboard | QDialog 820×980, 4 לשוניות | 334 | run buttons |
| GaugeWidget | QWidget מותאם (paintEvent) | 263 | — |

---

## 7. מלאי צד-שלישי

**ספריות Python:** PyQt5, PyQtWebEngine, Flask, flask-cors, requests, python-dotenv, FlightRadar24API, curl_cffi, psutil.

**API חיצוניים:**
| API | שימוש | מפתח |
|---|---|---|
| Google Geocoding | `/geo_data` | GOOGLE_API_KEY |
| OpenWeatherMap | `/weather` fallback | OPENWEATHER_API_KEY, **HTTP לא HTTPS** |
| Nominatim | geocode_region | אין |
| Open-Meteo | elevation/forecast | אין |
| FlightRadar24 | flight_server.py | FR24_TOKEN/USER/PASS |
| brin.iaa.gov.il | notam_drones.py | אין (WAF) |

**Tiles:** unpkg.com, tile.opentopomap.org (ברירת-מחדל), tile.openstreetmap.org, server.arcgisonline.com (Esri).
*הערה: docstring של `create_map` מזכיר "CartoDB Dark Matter" אך שכבת-הבסיס בפועל היא topo — פער תיעוד/קוד.*

---

## 8. מלאי מידע אישי

- מיקום/חיפושים — `coordinates_log.txt`, `city_log.txt` (append-only)
- היסטוריה — `QSettings("MapApp","MapGUI")` (Windows Registry) — 10 ערים, 15 טיסות
- עמדות שמורות עם קואורדינטות — `saved_stations.json` (מידע מיקום אופרטיבי שהמשתמש שמר, JSON רגיל בלי הצפנה)
- לוגים — `app_combined.log` (משותף ל-4 תהליכים) עם lat/lon/weather/city בטקסט פשוט
- אין Analytics/Telemetry לשום שרת מרוחק

---

## 9. שמירה ופורמטים

| קובץ | כותב/קורא | פורמט | שדה-גרסה? |
|---|---|---|---|
| `saved_stations.json` | WeatherServer `/stations/*` | JSON `{tool:[{name,params}]}` | אין |
| `coordinates_log.txt` | main.py append | `{'lat':..,'lon':..}` (repr Python, **לא JSON תקני**) | אין |
| `city_log.txt` | main.py append utf-8 | `City: <name>` | אין |
| `app_combined.log` | main.py+3 שרתים (אותו logging.basicConfig) | `%(asctime)s - %(message)s` | אין |
| `weather_data.csv` | **לא נכתב בקוד הפעיל** (נקרא כ-fallback ב-`/heatmap_data` אם קיים; נכתב רק ע"י `maps-gui-secure/weather_tool.py` — legacy) | CSV | אין |
| `VERSION` | נקרא ע"י `main.py:_load_app_version` | טקסט `1.0.2` | זה עצמו שדה-הגרסה; מסונכרן ל-`version.dart` (אומת זהה) |
| `data/projectiles/*` | נקרא ע"י `mpm/projectile.py` | JSON+CSV | אין |
| `data/met_example.csv` | **לא נמצא קוד שקורא אותו** — יתום | CSV | — |

---

## 10. הרצה/בדיקות קיימות

**הרצה:** `python main.py` מהשורש. שרתים מופעלים מתוך ה-GUI.

**בדיקות:**
1. `tests/self_test.py` — **הורץ בפועל: 10/10 עברו** (התכנסות dt, סחיפת-ספין, קוריוליס, אפקט-אטווש, solve, calibrate, geodesy, solve_mv, qe bounds).
2. `tests/test_ballistics_api.py` — **הורץ בפועל: 10/10 עברו** (כל 7 פעולות API, כולל רכס-קרקע סינתטי).
3. `test_requests.py` — **לא הורץ** (דורש 3 שרתים חיים+רשת-חוץ, לא מתאים ל"קריאה-בלבד"). 38 TestCase+4 LoadTestCase, כולל injection/method-tampering/payload-גדול.
4. `security_checks.py`/`cis_checks.py` — **לא הורץ** (דורש שרתים חיים+pip-audit+הרשאות-מנהל).

**pytest:** לא בשימוש בפועל (`.pytest_cache/` שארית; הבדיקות הן plain-script עם `sys.exit`).

---

## 11. רכיבים שלא הורצו / הערות-גבול

- **לא הורצו**: `test_requests.py`, `security_checks.py`, `cis_checks.py`, `main.py` עצמו (GUI+subprocess+רשת).
- **הבנה-קוד בלי אימות-ריצה**: `notam_drones.py` (scraping תלוי-WAF בזמן אמת), FR24 403-bypass, `cis_checks.py` (חלק דורש הרשאות-מנהל).
- **ממצאים לתיעוד (Stage 0, לא תיקון)**:
  1. OpenWeatherMap נקרא על HTTP לא HTTPS.
  2. `ANOTHER_API_KEY` ב-.env לא נסרק ב-`security_checks._SECRET_ENV_VARS`.
  3. `coordinates_log.txt` בפורמט repr-Python לא JSON.
  4. `weather_data.csv`/`data/met_example.csv` — קבצים יתומים/legacy.
  5. docstring `create_map` ("CartoDB Dark Matter") לא תואם שכבת-הבסיס בפועל ("topo").
  6. `main.py`+3 שרתים כותבים ללוג-משותף אחד מ-4 תהליכים — לא נמצאה בעיה, ראוי ל-stress-test.
- **Web/Android** — לא נבדקו (סוכנים אחרים), למעט שימוש-משולב (`MAP.py target='desktop'`, `mpm_api.py` משותף).
- קיים `maps-gui-secure/` כגרסה ישנה/נפרדת מקבילה — לא ברור אם ייחוס פעיל או ארכיון; לא בהיקף המשימה, הוזכר רק כהסבר ל-`weather_data.csv`.
