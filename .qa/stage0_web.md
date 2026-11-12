# מיפוי Stage 0 — פלטפורמת Web (Flask serverless / Vercel), maps-gui

קריאה בלבד. בסיס: `MAPS-GUI_SRS.md` §3.24-3.28 + קריאה ישירה של `web/` וחלקי `target=='web'` ב-`MAP.py`.

---

## 0. ממצאים חדשים (לא היו ב-SRS — התגלו בריצה הזו)

**0.1 — קריטי, אומת עצמאית ע"י הקואורדינטור: `map.html` בשורש הפרויקט (שעליו Desktop טוען ישירות) מכיל כרגע בפועל את פלט ה-Web, לא את פלט ה-Desktop.**
- אימות: `var serversRunning = true` ×2, `WebNotamControl`/`WebGpsControl` ×4, `http://localhost:5002/5003` ×0 ב-`map.html` הנוכחי.
- מנגנון: `create_map()` מבצע בסוף `html_content.replace('http://localhost:5002', api_base).replace('http://localhost:5003', api_base)` (MAP.py:5015) — ל-Web זה מחליף ל-מחרוזת ריקה → כל הפניות הופכות ל-נתיבים יחסיים (`/weather?...`). `web/build_web.py` (אחרי התיקון ב-§3.28 חלק ב') כותב ל-`output_path=_PROJECT_ROOT/map.html` — **אותו קובץ בדיוק** ש-`main.py` (Desktop) טוען ישירות ב-`__init__` (`QUrl.fromLocalFile(os.path.abspath("map.html"))`, שורה 790) **בלי לקרוא `create_map()` מראש** — זה קורה רק בלחיצה מפורשת על "load_map_button" (`create_map_from_file`).
- תוצאה: מי שמריץ `python main.py` כרגע (בלי ללחוץ "load map" קודם) — כל ה-fetch-ים יחסיים נגד origin `file://`, בלי שרת מאזין בכלל. כל הכלים (מזג-אוויר/LOS/רדאר/בליסטי/NOTAM) ישברו, ו-`serversRunning=true` הקשיח מהתיקון הקודם **מסווה** את זה (הכפתורים נראים פעילים).
- נגרם בפועל ע"י סדר-הפעלה בסשן הזה: `create_map()` (desktop, cwd=שורש) ואז `build_web.py` (web, cwd=web/) שתיקונו (output_path מוחלט) כתב *אחרי* זה לאותו קובץ בדיוק — האחרון מנצח.
- **מצב**: נמצא, לא תוקן עדיין — מדווח למשתמש לפני תיקון, בהתאם לכלל "אין לשנות קוד ייצור בלי אישור מפורש".

**0.2 — דריפט/באג אמיתי ב-`/radar_doppler/cancel` ב-Web בלבד: חסר `return`.**
`web/api/weather.py:1308-1315` — `cancel_radar_doppler()` לא מחזיר שום דבר (Flask תזרוק "did not return a valid response" → 500). ה-sibling (`cancel_radial_los`) וה-Desktop-מקור (`weather_server.py:1287`) שניהם מחזירים `jsonify({'ok': True})`. נמצא ב-diff סמנטי בין שני הקבצים, לא תועד ב-SRS.

**0.3 (קל, היגיינת-repo)** — `web/map.html` (4949 שורות) tracked בגיט, שריד-ישיר מריצה עם cwd שגוי לפני תיקון §3.28. לא בשימוש ע"י שום קוד.

**0.4** — `ANOTHER_API_KEY` ב-`maps-gui-secure/.env.example` לא נצרך בשום `.py` בפרויקט — סוד-יתום.

---

## 1. טכנולוגיות (`web/requirements.txt`, כולן מוצמדות `==`)
Flask 3.1.3, flask-cors 6.0.2, requests 2.33.0, python-dotenv 1.2.2, FlightRadarAPI 1.4.0, beautifulsoup4 4.15.0 (תלות-אמת של FlightRadarAPI), curl_cffi 0.16.1 (lazy, try/except), upstash-redis 1.8.0 (**lazy-import**, רק אם job_store/stations_store נקראים).

Vercel: Root Directory=`web/`, `buildCommand: python build_web.py`, `outputDirectory: public`, `maxDuration: 35`. **Redis**: קורא `UPSTASH_REDIS_REST_URL/TOKEN` (או `KV_REST_API_*`) — **לא מוגדר ב-.env מקומי, לא אושר שהותקן בפרויקט Vercel בפועל** (SRS §3.25 עצמו אומר "טרם בוצע"). `/los_radial/*`,`/radar_doppler/*`,`/stations/*` עשויים להחזיר 503 בפרודקשן החי — **לא נבדק, אין גישה ל-dashboard**.

## 2. נקודות כניסה (26 routes)
`app.py`: `GET /`. `geo.py`: `/geo_data`,`/uas_notams`. `weather.py` (17): `/weather`,`/heatmap_data`,`/elevation`,`/temp_grid`,`/los`,`/los_radial/{start,status,cancel}`,`/radar_doppler/{start,status,cancel,profile}`,`/radar_doppler/evaluate_route/start`,`/stations/{list,save,delete}`. `flight.py`: `/flight_route`,`/flight_search`. `ballistics.py` (7/7): trajectory/solve/solve_mv/table/calibrate/terrain_check/min_qe_for_crest.

## 3. ארכיטקטורת serverless — בדיקת-קוד (לא תיעוד)
| מנגנון | מצב | תקין ב-Vercel? |
|---|---|---|
| `/los_radial/*`, `/radar_doppler/{start,status,cancel,profile}` | **הומר בפועל** ל-chunked-per-request+Redis (`job_store.py`), אומת שורה-שורה | ✅ (בתנאי Redis מוגדר בפרודקשן — לא מאומת) |
| `/radar_doppler/evaluate_route/start` | **נשאר** thread+dict בזיכרון (`_radar_jobs`), מתועד-בכוונה ב-FR-D-223 | ❌ **לא תקין ב-Vercel** — thread עשוי להיקטע, polling הבא עשוי לנחת על instance אחר → 404. כלי "הערכת-מסלול-טיסה מול רדאר" כנראה שבור ב-production |
| `/stations/*` | הומר ל-Redis (`stations_store.py`) | ✅ (בתנאי Redis) |
| NOTAM cache | Redis-אופציונלי + נפילה-חזרה שקטה ל-dict בזיכרון | ⚠️ עובד אך בלי cache-משותף אמיתי בלי Redis — scrape מלא בכל cold-start |
| `/ballistics/*` | סינכרוני מלא (לא chunked) — מהיר ל-5 מתוכן; `terrain_check`/`min_qe_for_crest` עם batching+sleep פנימי | ⚠️ סיכון timeout על maxDuration=35s למסלולים ארוכים — לא נבדק מול Vercel בפועל |
| `/heatmap_data` | קורא `weather_data.csv` יחסי — **לא קיים ב-Vercel** (fs read-only) | נופל ל-fallback סטטי (3 נק' קשיחות), לא קורס |

## 4. CORS/סודות
`CORS(app, origins=[ALLOWED_ORIGIN])` אם מוגדר, אחרת **פתוח-לכל (`*`) עם אזהרת-לוג בלבד**. משתני-סביבה נדרשים (אין `.env.example` ייעודי ל-`web/`): OPENWEATHER_API_KEY, GOOGLE_API_KEY, FR24_TOKEN/USER/PASS, ALLOWED_ORIGIN, UPSTASH_REDIS_REST_URL/TOKEN. **ASVS V4**: אין auth/API-key/rate-limit על אף endpoint — כל מי שמוצא את ה-URL יכול לצרוך בלי הגבלה מפתחות משולמים (Google/OpenWeather/FR24) ואת ה-scraping ל-brin.iaa.gov.il — חשיפת "denial-of-wallet", לא תועד קודם.

## 5. 6 הבקרות web-only
NOTAM toggles, מצב-היטמאפ גבהים/טמפרטורה, חיפוש-עיר, חיפוש-טיסה (אותו control), GPS (קליינט-בלבד, אין קריאת-שרת). כולן `max-width: calc(100vw-20px)`.

## 6. נגישות/מובייל
`_build_web_mobile_css()`: media-query בודד (`max-width:600px`) — אין breakpoints נוספים. Touch targets: GPS button 30×30px (**מתחת ל-44×44 WCAG**), NOTAM checkboxes font-size:10px בלי padding-מוגדל. **0 מופעי `aria-*`/`role`/`tabindex`** בכל MAP.py. מעולם לא נבדק על מכשיר-טאצ'/דפדפן-מובייל אמיתי (רק QWebEngineView דסקטופ) — פער מתועד-מראש, לא ממצא חדש.

## 7. מידע אישי
`navigator.geolocation` — קליינט-בלבד, לא נשלח ל-backend בשום קריאת-רשת שנמצאה.

## 8. דריפט Desktop↔Web
diff סמנטי מלא בין `weather_server.py` ל-`web/api/weather.py`: כל הפונקציות הפיזיקליות **זהות-קוד-מקור**. ההבדל הלא-מתועד היחיד: הבאג ב-0.2 (`cancel_radar_doppler` חסר return).

## 9. הרצה/בדיקות
אין test ייעודי ל-`web/api/*.py`. `test_requests.py` בודק רק את שרתי ה-Desktop.

## 10. לא נבדק
אין גישה ל-Vercel dashboard/Runtime Logs — לא אושר: deploy אחרון בפרודקשן, התקנת Upstash בפועל, הגדרת ALLOWED_ORIGIN/סודות ב-Vercel, geolocation/HTTPS/touch-targets במכשיר אמיתי. `maps-gui-secure/` לא נחקר (מחוץ ל-scope). `web/lib/{uas_coordination_zones,airport_ctr_zones,icao_glossary,notam_categories}.py` נסקרו שטחי (קבועים סטטיים, 0 I/O) בלי diff מלא מול Desktop. timeout בפועל של `terrain_check`/`min_qe_for_crest` מול Vercel לא נבדק.
