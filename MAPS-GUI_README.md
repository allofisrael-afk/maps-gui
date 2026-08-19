# מפה אינטראקטיבית — תיעוד מלא
**תאריך עדכון:** 16/08/2026 | **פרויקט:** maps-gui | **מיקום:** `d:\PY-IS\maps-gui`

---

## תוכן עניינים
1. [סקירת הפרויקט](#1-סקירת-הפרויקט)
2. [מבנה תיקיות](#2-מבנה-תיקיות)
3. [אפליקציית Desktop — Python/PyQt5](#3-אפליקציית-desktop--pythonpyqt5)
4. [אפליקציית Android — Flutter](#4-אפליקציית-android--flutter)
5. [שרתי Flask (Backend)](#5-שרתי-flask-backend)
6. [ממשקי API חיצוניים](#6-ממשקי-api-חיצוניים)
7. [מפתחות ואישורים](#7-מפתחות-ואישורים)
8. [Build — ייצור APK](#8-build--ייצור-apk)
9. [הגבלות ואילוצים ידועים](#9-הגבלות-ואילוצים-ידועים)
10. [הנחיות עבודה עם Claude](#10-הנחיות-עבודה-עם-claude)
11. [היסטוריית שינויים עיקריים](#11-היסטוריית-שינויים-עיקריים)

---

## 1. סקירת הפרויקט

אפליקציה גיאוגרפית-מטאורולוגית דו-פלטפורמית, עם דגש נוסף על מודעות מרחב אווירי לכטב"ם (רחפנים):
- **Desktop (Windows):** PyQt5 + QWebEngineView + Leaflet.js, כולל דשבורד מעקב תהליכים ודשבורד בדיקות אבטחה נפרדים.
- **Android:** Flutter עם flutter_map.

הפרויקט **כן** נמצא ב-git (`origin` → GitHub, branch `main`).

### פיצ'רים עיקריים
| פיצ'ר | Desktop | Android |
|--------|---------|---------|
| מפה אינטראקטיבית | Leaflet.js (WebView) | flutter_map |
| שכבת גבהים (heat/grid/dots) | Open-Meteo דרך שרת מקומי | Open-Meteo ישיר |
| שכבת טמפרטורות (heat/grid/dots) | Open-Meteo דרך שרת מקומי | Open-Meteo ישיר |
| מזג אוויר לנקודה/עיר | OpenWeather + Google Geocoding | Open-Meteo + Nominatim |
| מסלולי טיסות | FlightRadar24 (שרת מקומי) | שרת מקומי → OpenSky → FR24 (fallback chain) |
| כלי מדידת מרחק (Ruler) | כן | כן |
| קו ראייה (LOS) | מחושב בשרת (`/los`), פאנל פרופיל גובה | מחושב **on-device** |
| רדיוס ראייה רדיאלי (Viewshed מכומת) | כן — job+polling+ביטול (`/los_radial/*`) | כן — on-device, ביטול לקוח |
| תצפית מכ"ם דופלר (רעיוני/חינוכי) | כן — job+polling+ביטול (`/radar_doppler/*`) | לא (טרם הותקן) |
| שכבת NOTAM — אזורי פעילות טיסה (7 קטגוריות) | כן, מקרא ניתן לצמצום | כן, מקרא ניתן לצמצום |
| שכבת "אזורי תיאום כטב״ם" (סטטית) | כן, מקרא ניתן לצמצום | כן, מקרא ניתן לצמצום |
| שכבת גבולות CTR שדות תעופה (סטטית, ממקור AIP רשמי) | כן, מקרא ניתן לצמצום | כן, מקרא ניתן לצמצום |
| הודעת כלל טיסת VLOS | כן — Control ניתן להרחבה על המפה | כן — כפתור מידע ייעודי |
| דשבורד מעקב תהליכים (3 שרתי Flask) | כן — סטטוס/PID/CPU/RAM/מטריקות | — |
| דשבורד בדיקות אבטחה (חשיפה + CIS L1/L2) | כן | — |
| GPS / מיקום עצמי | — | geolocator — ממלא גם את שדות LAT/LON הידניים |
| איפוס מפה מלא | כן — כפתור בפאנל, ללא דיאלוג אישור | כן — כפתור בסרגל העליון, עם דיאלוג אישור |
| תמיכת RTL עברית | מלאה | מלאה (`Locale('he','IL')` כפוי) |
| ערכת צבעים | כהה (Catppuccin Mocha) | Material 3, `ThemeMode.dark` כפוי |

---

## 2. מבנה תיקיות

```
d:\PY-IS\maps-gui\
├── main.py                    ← Desktop GUI ראשי (PyQt5) — כולל ProcessDashboard + SecurityCheckWorker
├── MAP.py                     ← גנרטור map.html (Leaflet, f-string אחד ~1750 שורות — ר' §9 לאזהרת עריכה)
├── ports.py                   ← GEO_PORT/WEATHER_PORT/FLIGHT_PORT — מקור אמת יחיד לפורטים
├── server_common.py           ← create_app(name) — Flask app אחיד (env/logging/CORS/metrics) לשלושת השרתים
├── metrics.py                 ← register_metrics(app) — נקודת קצה GET /metrics משותפת
├── geo_server.py              ← Flask :5003 — Google Geocoding + שכבת NOTAM כטב"ם
├── weather_server.py          ← Flask :5002 — OpenWeather, /elevation, /temp_grid, /los, /los_radial/*, /heatmap_data
├── flight_server.py           ← Flask :5004 — FlightRadar24
├── notam_categories.py        ← 7 קטגוריות סיווג NOTAM — מקור אמת גם ל-MAP.py וגם לתפריט ב-main.py
├── notam_drones.py            ← שליפה/פרסור/cache של NOTAM כטב"ם מ-brin.iaa.gov.il
├── uas_coordination_zones.py  ← נתוני "אזורי תיאום כטב״ם" הסטטיים
├── airport_ctr_zones.py       ← נתוני גבולות CTR שדות תעופה הסטטיים, ממקור AIP רשמי
├── icao_glossary.py           ← גלוסר עברי גס למונחי ICAO בטקסט NOTAM
├── security_checks.py         ← בדיקות חשיפה/סודות/CORS/CVEs/APK, נצרך ע"י דשבורד האבטחה
├── security_types.py          ← SecurityFinding (dataclass) בלבד — פותר circular import עם cis_checks.py
├── cis_checks.py              ← 25 בדיקות הקשחת Windows (CIS Level 1/2) דרך registry/PowerShell
├── test_requests.py           ← health checks לשלושת השרתים + בדיקות עומס, נצרך גם ע"י הדשבורדים
├── requirements.txt           ← dependencies Python
├── .env                       ← מפתחות API (לא לגיט!)
├── .env.example               ← תבנית משתני סביבה
├── map.html                   ← מפה Leaflet שנוצרת מחדש בכל create_map() — אין לערוך ידנית, נדרס
├── maps-gui-android-src\      ← ⚠️ מקור האמת לקוד Flutter — כאן עורכים תמיד
│   └── lib\
│       ├── main.dart
│       ├── screens\map_screen.dart      ← מסך יחיד: FlutterMap + סרגל עליון צף + BottomAppBar
│       ├── services\api_service.dart    ← כל קריאות ה-HTTP (כולל fallback chain לטיסות, LOS on-device)
│       ├── state\map_state.dart         ← MapState (ChangeNotifier, Provider) — 6 תחומים
│       ├── widgets\controls_panel.dart  ← LayersPanel/LocationPanel/FlightPanel (bottom sheets)
│       ├── models\*.dart                ← grid_point, los_session, city_result, uas_notam_zone, uas_coordination_zone
│       ├── data\*.dart                  ← notam_categories, uas_coordination_zones, icao_glossary (נתונים סטטיים)
│       └── utils\heat_image.dart        ← רינדור heat-image (PNG) בצד הלקוח
├── maps-gui-android\          ← ⚠️ פרויקט ה-BUILD בלבד — נוצר/נדרס ע"י build_apk.ps1, אין לערוך כאן ישירות
├── maps-gui-secure\           ← עותק נפרד עם חיזוקי אבטחה חלקיים — לא מתוחזק יחד עם הפרויקט הראשי
└── build_apk.ps1              ← סקריפט הבנייה היחיד ל-Android — ר' §8
```

**קבצים שנמחקו (קוד מת מאומת, לא קיימים יותר):** `apipyqt.py`, `weather_tool.py`, `heatmap_layer.py` — אם תראה אזכור שלהם במקום אחר (כולל תיעוד ישן), זה מיושן.

---

## 3. אפליקציית Desktop — Python/PyQt5

### קבצים עיקריים
- **`main.py`** — חלון ראשי, `QWebEngineView` לטעינת `map.html`, ניהול 3 שרתי Flask כ-subprocess, `ProcessDashboard` (מעקב תהליכים חי) ו-`SecurityCheckWorker`/`HealthCheckWorker`/`MetricsWorker` (כל אחד ב-thread נפרד למניעת הקפאת ה-GUI), `WeatherFetchWorker`/`FlightFetchWorker` (קריאות רשת חוסמות הועברו ל-thread נפרד).
- **`MAP.py`** — יוצר `map.html` דינמי: heatmap, שכבות גבהים/טמפרטורה (heat/grid/dots + עריכת אזור בגרירה), מסלולי טיסה, כלי מדידה (Ruler), קו ראייה (LOS) עם פאנל פרופיל גובה, 7 קטגוריות NOTAM עם מקרא ניתן לצמצום, אזורי תיאום כטב"ם עם מקרא ניתן לצמצום.

### שרתים שמופעלים מה-Desktop
```
port 5002 → weather_server.py
port 5003 → geo_server.py
port 5004 → flight_server.py
```
כל שרת נוצר דרך `server_common.create_app(name)` המשותף (env/logging/CORS/`/metrics`), הפורטים נגזרים מ-`ports.py`. לוגים ל-`app_combined.log`, מנגנון kill zombie processes בהפעלה.

### התקנה וריצה
```powershell
pip install -r requirements.txt
python main.py
```

### requirements.txt
```
requests, PyQt5, PyQtWebEngine, python-dotenv, Flask, flask-cors, FlightRadar24, psutil
```
(`pandas`/`folium`/`tqdm` הוסרו — היו נחוצים רק לכלים המתים `weather_tool.py`/`heatmap_layer.py` שנמחקו.)

### דשבורד מעקב תהליכים
כפתור `📊 דשבורד תהליכים` — חלון נפרד (לא-מודלי): סטטוס/PID/uptime/CPU/RAM לכל אחד מ-3 השרתים (`psutil`, כולל תת-תהליכים), מטריקות קריאות API (`/metrics`), יומן חי. כל הפעולות החוסמות רצות ב-`MetricsWorker` על thread נפרד.

### דשבורד בדיקות אבטחה
כפתור `🔒 בדיקת אבטחה` — מריץ `security_checks.run_security_checks()`: חשיפת debug console, סריקת סודות בתגובות שרת, מדיניות CORS, סריקת CVEs (`pip-audit`), סודות קשיחים ב-APK, וכן 25 בדיקות הקשחת Windows (`cis_checks.py`, CIS Level 1/2 דרך registry/PowerShell).

---

## 4. אפליקציית Android — Flutter

### ⚠️ מקור האמת הוא `maps-gui-android-src\` — לא `maps-gui-android\`!
הפרויקט הבר-בנייה (`maps-gui-android\`) הוא scaffold שנוצר/נדרס ע"י `build_apk.ps1`, שמעתיק אליו `lib/`, `pubspec.yaml` ו-`AndroidManifest.xml` מתוך `maps-gui-android-src\` בכל build. **תמיד לערוך ב-`-src`, אף פעם לא ישירות ב-`maps-gui-android\`.**

### Dependencies (pubspec.yaml)
```yaml
flutter_map: ^7.0.2         # מפה
latlong2: ^0.9.1            # קואורדינטות
http: ^1.2.1                # HTTP
provider: ^6.1.2            # State management
geolocator: ^13.0.4         # GPS
material_symbols_icons: ^4.2719.3
shared_preferences: ^2.2.2  # היסטוריית ערים/טיסות
```

### ארכיטקטורה
```
main.dart
  └── ChangeNotifierProvider(MapState)
        └── MapScreen (StatefulWidget)
              ├── FlutterMap (flutter_map)
              ├── סרגל עליון צף + BottomAppBar (3 כפתורים → bottom sheets)
              ├── LayersPanel / LocationPanel / FlightPanel (widgets/controls_panel.dart)
              └── כרטיסים/מקראות צפים: גובה, מזג אוויר, מדידה, NOTAM, אזורי תיאום, VLOS
```

**אין Drawer בפועל** — הניווט הוא `BottomAppBar` עם 3 כפתורים שפותחים modal bottom sheets (שכבות/מיקום/טיסות).

### State Management — `map_state.dart`
מחלקת `MapState` (ChangeNotifier) יחידה, 460 שורות, 6 תחומים: חיפוש עיר, בחירת נקודות חום ידנית, כלי מדידה, LOS, NOTAM (7 קטגוריות), אזורי תיאום כטב"ם. `context.watch<MapState>()` נקרא מ-4 מקומות (`map_screen.dart` + 3× `controls_panel.dart`) — כל שינוי מרנדר מחדש את כולם (לא פוצל ל-state נפרדים בכוונה, ר' §11 בתוכנית השיפור).

### מקראות שכבות (NOTAM / אזורי תיאום)
שני המקראות (`_UasNotamLegend`, `_UasCoordLegend`) בנויים על גבי `_CollapsibleLegend` משותף — **מצומצמים לסמל עגול קטן כברירת מחדל** (לא חוסמים את המפה), לחיצה פותחת את התוכן המלא, כפתור X מצמצם בחזרה.

### סרגל עליון צף — כפתורי מצב (מפעיל)
5 כפתורים, מימין לשמאל: **בחר אזור** (`crop_free`, לגבהים/טמפרטורה), **מדד מרחק** (`straighten`), **קו ראייה/LOS** (`visibility`), **חום ידני** (`local_fire_department`), **איפוס מפה** (`restart_alt`, חדש — ר' למטה).

**איפוס מפה:** מציג דיאלוג אישור, ואז מנקה בבת אחת: בחירת אזור, שכבות גבהים/טמפרטורה, חום ידני, כרטיסי גובה/מזג-אוויר פתוחים, כלי מדידה, כל סשני ה-LOS, סימון קטגוריות NOTAM (המטמון עצמו נשאר), שכבת אזורי תיאום, מסלול טיסה, סיכות, תוצאת חיפוש עיר — ומחזיר את המצלמה למרכז ברירת המחדל (`MapState.resetMap()`). **לא** מאפס היסטוריית חיפוש (ערים/טיסות).

**מיקום עצמי (GPS), פאנל "מיקום":** בהצלחה, מוסיף סיכה על המפה **וגם ממלא** את שדות הקלט הידניים LAT/LON בפאנל עם הקואורדינטה שאותרה (6 ספרות עשרוניות) — כדי שאפשר יהיה, למשל, להעתיק/לערוך את הערך שהתקבל בלי להקליד מחדש.

**סמן נקודת מזג אוויר:** לחיצה על המפה (כשאין מצב אחר פעיל) מציגה כרטיס מזג אוויר **וגם** סמן צהוב (`Icons.location_on`) על המפה בנקודת הלחיצה עצמה.

### AndroidManifest.xml — הרשאות
```xml
INTERNET, ACCESS_NETWORK_STATE
ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION
android:usesCleartextTraffic="true"   ← חובה לחיבור לשרת desktop
```

### Build Config (app/build.gradle.kts)
- `namespace`/`applicationId` = `com.mapsapp.maps_gui_android`
- Java 17, Kotlin JVM target 17
- `signingConfig = signingConfigs.getByName("debug")` ← חתימה בדebug key (לא ייצור אמיתי, ר' §9)

---

## 5. שרתי Flask (Backend)

### geo_server.py — port 5003
- `GET /geo_data?location=<city>` — Google Geocoding API, מחזיר `{address, latitude, longitude}`
- `GET /uas_notams` — שכבת NOTAM לרחפנים (מסונן UAS/UAV מתוך NOTAM ארצי, cache 20 דק', `?force=1` לעקיפה)
- `GET /metrics` — מטריקות (משותף, דרך `server_common.py`)

### weather_server.py — port 5002
- `GET /weather?region=<name>` או `?lat=&lon=` — OpenWeather
- `GET /heatmap_data` — נתוני heatmap קבועים/מקובץ CSV
- `POST /elevation` — Open-Meteo Elevation (עד 100 נקודות, retry עם backoff)
- `POST /temp_grid` — Open-Meteo Forecast (עד 500 נקודות, batches של 30 + השהיה)
- `GET /los?lat1=&lon1=&lat2=&lon2=` — חישוב קו ראייה (עקמומיות + רפרקציה)
- `GET /metrics`

### flight_server.py — port 5004
- `GET /flight_route?flight=<callsign>` — FlightRadar24API, מיפוי IATA→ICAO
- `GET /flight_search?q=` — autocomplete (קיים, לא בשימוש בפועל מה-UI כרגע)
- `GET /metrics`

---

## 6. ממשקי API חיצוניים

### Android — api_service.dart
| API | שימוש | URL |
|-----|-------|-----|
| open-meteo elevation | גבהים (grid) + LOS on-device | `api.open-meteo.com/v1/elevation` |
| open-meteo forecast | טמפרטורות (grid) + מזג אוויר לנקודה | `api.open-meteo.com/v1/forecast` |
| Nominatim | חיפוש עיר + גבולות | `nominatim.openstreetmap.org/search` |
| OpenSky Network | מסלולי טיסה (Tier 2) | `opensky-network.org/api/states/all` |
| FlightRadar24 Gold | מסלולי טיסה (Tier 3, אחרון) | `data.flightradar24.com` |
| שרת desktop (WiFi) | מסלולי טיסה (Tier 1) — **אין דרך להגדיר `flightServerHost` מה-UI, לא פעיל בפועל** | `http://{flightServerHost}:5004` |

### Desktop — שרתי Python
| API | מפתח | קובץ |
|-----|-------|------|
| OpenWeather | `OPENWEATHER_API_KEY` | weather_server.py |
| Google Geocoding | `GOOGLE_API_KEY` | geo_server.py |
| FlightRadar24 | `FR24_USER`+`FR24_PASS`+`FR24_TOKEN` | flight_server.py |
| Open-Meteo | ללא מפתח | weather_server.py |
| brin.iaa.gov.il (NOTAM) | ללא מפתח | notam_drones.py |

---

## 7. מפתחות ואישורים

**קובץ `.env` ב-`d:\PY-IS\maps-gui\`** — לא לשתף, לא לגיט!

```env
OPENWEATHER_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
GOOGLE_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_USER=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_PASS=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_TOKEN=<REDACTED — ראה .env המקומי, לא בגיט>
```

**Token FR24 מוטמע גם ב-api_service.dart** (ייחשף בפירוק כל APK מבוזר — ר' §9).

---

## 8. Build — ייצור APK

**הדרך הנכונה היחידה: `build_apk.ps1` משורש הפרויקט** — הוא מטפל בהכל: מתקין Flutter/Java/Android SDK אם חסר, מעתיק את `-src` לפרויקט הבר-בנייה, `pub get`, `build apk --release`.
```powershell
cd d:\PY-IS\maps-gui
powershell -ExecutionPolicy Bypass -File build_apk.ps1
# APK נמצא ב: maps-gui-android\build\app\outputs\flutter-apk\app-release.apk
```
**אל תבנה APK מבלי שהמשתמש ביקש זאת מפורשות בכל פעם** — גם אם בוצע שינוי לאנדרואיד.

**אם ה-build נכשל עם `OutOfMemoryError: Metaspace`** — להגדיל `org.gradle.jvmargs` ב-`maps-gui-android\android\gradle.properties` (כרגע `-Xmx2g -XX:MaxMetaspaceSize=512m`).

### App ID
`com.mapsapp.maps_gui_android`

---

## 9. הגבלות ואילוצים ידועים

### אנדרואיד
- **FlightRadar24 Cloudflare:** fallback chain: שרת desktop (לא פעיל בפועל, ר' למעלה) → OpenSky → FR24 Gold token
- **HTTP cleartext:** `usesCleartextTraffic="true"` דרוש לחיבור לשרת desktop
- **GPS:** דורש הרשאת `ACCESS_FINE_LOCATION` — נשאל runtime
- **גבהים:** open-meteo מקסימום 100 נקודות (chunks של 50)
- **טמפרטורות:** open-meteo מגביל 30 נקודות, chunks של 20 עם delay 200ms

### Desktop
- **`MAP.py` הוא f-string אחד ענק (~1750 שורות)** — שגיאת escaping (למשל `\n` במקום `\\n`) שוברת את כל תג ה-`<script>` ביחד. כל שינוי דורש רגנרציה (`python -c "import MAP; MAP.create_map()"`) ובדיקה.
- **Port conflicts:** שרתי Flask הורגים zombie processes על 5002/5003/5004 בכל הפעלה
- **שרתים רצים עם `debug=True`** — כל שרת הוא בפועל שרשרת של 2-4 תהליכי OS (launcher stub של virtualenv + reloader של Werkzeug) — לעצור/למדוד תמיד עם `psutil` על כל העץ, לא רק ה-PID השמור
- **`.venv/`** נוצר עם `virtualenv` — לא stdlib `venv`

### כללי
- **גיט:** הפרויקט **כן** ב-git. Remote `origin` → GitHub, branch `main`. אל תדחוף (`push`) בלי אישור מפורש בכל פעם, ואל תעשה force-push.
- **חיבור WiFi:** לשימוש בשרת desktop מהאנדרואיד — חובה אותה רשת (בפועל לא מנוצל כרגע, ר' §6)

---

## 10. הנחיות עבודה עם Claude

### כללי עבודה מרכזיים
1. **אל תשבור פעולות קיימות** — בכל שינוי יש לוודא שלא נפגע שום תהליך או פיצ'ר קיים
2. **שפת UI — עברית בלבד** — כל טקסט למשתמש בעברית, כולל error messages
3. **RTL** — כל ממשק בכיוון RTL, שימוש ב-`Directionality(textDirection: TextDirection.rtl)`
4. **ערכת צבעים כהה** — Dark theme, `ThemeMode.dark`/Catppuccin Mocha
5. **אל תוסיף פיצ'רים שלא התבקשו** — פחות זה יותר
6. **כל שורה שמתקנים או מוסיפים — חייבת הערה שמסבירה מה היא עושה** (לא רק WHY לא-ברור — גם WHAT; חלק מתהליך הלמידה של המשתמש. דורס את ברירת המחדל הרגילה של "בלי הערות").
7. **Flutter בלבד לאנדרואיד** — לא Buildozer, לא Kivy
8. **אל תבנה APK בלי בקשה מפורשת בכל פעם** — גם אחרי שינוי ב-Android, לא אוטומטי
9. **הפרויקט ב-git** — אל תדחוף בלי אישור מפורש בכל פעם, ואל תעשה force-push
10. **עדכן תמיד את `MAPS-GUI_README.md` ו-`MAPS-GUI_SRS.md`** — על כל שינוי בקוד, לפני שנחשב "הושלם" (ר' §11 למטה)

### הנחיות טכניות
- **State management:** Provider pattern בלבד (ChangeNotifier) — לא Bloc, לא Riverpod
- **API calls:** `http` package בלבד — לא dio
- **מפות:** `flutter_map` בלבד — לא google_maps_flutter
- **Gradle:** Kotlin DSL (`.kts`) — לא Groovy
- **Java:** גרסה 17

### Build process
- תמיד לרוץ מ-`d:\PY-IS\maps-gui\` דרך `build_apk.ps1` (לא ידנית מתוך `maps-gui-android\`)

---

## 11. היסטוריית שינויים עיקריים

### תוכנית שיפור קוד רב-שלבית (16/08/2026)
- **שלב 1 (באגים):** ריפוד ניווט Android חסר (2 מקומות), איפוס ruler שלא התאפס, הזרקת HTML לא-מאובטחת בפופאפ מזג אוויר, timeouts חסרים (5 מקומות).
- **שלב 2 (async):** `WeatherFetchWorker`/`FlightFetchWorker` — קריאות רשת הועברו מה-UI thread ל-QThread.
- **שלב 3 (dedup):** `_getJson` משותף (Dart), נירמול נקודת מסלול טיסה (תיקן drift אמיתי), `server_common.py`, dispatch table ל-`_on_title_changed`, `_toggle_layer` helper, איחוד קנבס/ידיות עריכה בין גבהים/טמפרטורה + תיקון באג בגרירת אזור גבהים.
- **שלב 4 (תשתית + ניקוי):** `ports.py`, `security_types.py` (פתר circular import), מחיקת `weather_tool.py`/`heatmap_layer.py`/`apipyqt.py` + מחלקת `ControlsPanel` המתה.
- **שלב 5 (פיצול קבצים גדולים) — דולג במפורש לפי בקשה.** אל תציע לפצל את `MAP.py`/`map_screen.dart`/`map_state.dart` בלי לשאול קודם.
- **שלבים 6-8** (ביצועים/UX/כיסוי בדיקות) — טרם בוצעו.
- **מקראות ניתנות לצמצום** (NOTAM + אזורי תיאום, שתי הפלטפורמות) + תיקון כפתור סגירת תפריט השכבות ב-Android (ידית הגרירה הייתה בתוך אזור הגלילה).
- **Android:** תוקן סמן חסר בלחיצה למזג אוויר; נוסף כפתור "איפוס מפה" (סרגל עליון, עם דיאלוג אישור — מנקה את כל השכבות/הכלים ומחזיר למרכז ברירת המחדל); "מיקום עצמי" (GPS) ממלא כעת גם את שדות LAT/LON הידניים בפאנל המיקום; תוקנה תצוגת הסרגל העליון הצף (רקע שחור בולט → `cs.surfaceContainerHigh` רך, כותרת קטנה יותר עם שורה אחת קבועה, 5 הכפתורים צומצמו כדי להיכנס בשורה בלי לדחוק); נוסף רדיוס מינימלי חזותי (תלוי-זום) למעגלי NOTAM/אזורי-תיאום קטנים — בלי זה אזורים אמיתיים בני כמה מאות מטרים (כמו NOTAM על מנוף בנייה) לא נראו כלל בזום ארצי, רק הסמן שמעליהם.
- **Desktop:** אותו תיקון רדיוס מינימלי חזותי גם ב-`MAP.py` (`_minVisibleRadiusM`/`_metersPerPixel`, מתעדכן ב-`zoomend`) — עקבי עם Android.
- **פרסור NOTAM (שני הצדדים):** תוקנה תבנית הקואורדינטות ב-`notam_drones.py`/`api_service.dart` לתמיכה גם בפורמט "אות-כיוון-ואז-ספרות" (`N314945E0345822`, בנוסף לפורמט הרגיל "ספרות-ואז-אות") וגם בשניות עשרוניות (`315907.32N`). לפני התיקון, NOTAM-ים בפורמט ההפוך נפלו ל"טקסט בלבד" ולא הוצגו כלל — כולל **שני פוליגונים אמיתיים** (LATRUN, OR-AKIVA) שעכשיו מוצגים כשכבת שטח, לא רק כסמן. בנוסף, `_RADIUS_RE`/`_radiusRe` תומכים עכשיו גם ביחידות **KM ו-M** לרדיוס (לא רק NM). יחד: `text_only_count` החי ירד מ-15 ל-**9** (12→**18** אזורים מוצגים). הנותרים (9) דורשים הפניה לאזור בשם (בלי קואורדינטות בטקסט) או שהם NOTAM מנהלתי טהור בלי גיאומטריה — לא נפתר, ר' SRS ממצא #17.
- **תוקן — Desktop:** באג אמיתי ב-`MAP.py`, `_redrawNotamLayer()` יצר `L.layerGroup(shapes)` וקרא ל-`.getBounds()` עליו — אבל ל-`LayerGroup` הרגיל ב-Leaflet **אין** `.getBounds()` (זו תוספת של `FeatureGroup` בלבד). כל הפעלה של שכבת NOTAM זרקה `TypeError` בפועל (אומת ב-render אמיתי, `L.LayerGroup.prototype.getBounds === undefined` בזמן ריצה) — הצורות כן צוירו על המפה, אבל השגיאה נתפסה כ"כישלון" והשאירה את מצב תיבות הסימון לא-עקבי. תוקן ע"י שימוש ב-`L.featureGroup(shapes)` במקום (התנהגות זהה לכל השאר, כולל `.getBounds()`).
- **שדרוג משמעותי — `notam_drones.py` (Desktop בלבד):** התגלה שהתצוגה המכווצת של NOTAM ב-brin.iaa.gov.il **חותכת** חלק מהטקסט (כולל קואורדינטות פוליגון!) — הטקסט המלא זמין רק דרך מנגנון "הרחבה" (postback אסינכרוני של ASP.NET UpdatePanel, מדמה לחיצה על "+"). נוסף `_fetch_more_info()` ששולף את ההרחבה לכל רשומה רלוונטית (session+cookies+ViewState משותפים, השהיה של 0.3ש' בין רשומות), וגם `_geometry_from_q_line()` — רשת ביטחון שמחלצת מעגל גס משורת ה-Q הסטנדרטית-חובה (ICAO) כשגם הטקסט המלא לא נותן גיאומטריה. **תוצאה: `text_only_count` ירד ל-0 (מ-15 במקור, 27/27 אזורים רלוונטיים כעת מוצגים)**, מאומת חי מול `/uas_notams`. עלות: רענון cache (כל 20 דק') לוקח כ-22 שניות במקום שניות בודדות (בקשת POST נוספת לכל רשומה) — **לא הוטמע ב-Android** (`api_service.dart` עדיין מבוסס רק על הטקסט הרגיל + KM/M/פורמט-קואורדינטות הפוכות, ר' SRS ממצא #17 המעודכן).
- **תוקן — Desktop (חשוב):** ה-22 שניות שהתווספו חשפו שלושת שרתי ה-Flask רצים ללא `threaded=True` — שרת הפיתוח של Werkzeug מטפל בבקשה **אחת** בכל רגע, אז במהלך שליפת ה-NOTAM הארוכה כל בקשה אחרת לאותו שרת (כולל `/metrics` שהדשבורד סורק כל 1.5 שניות) נחסמה מאחוריה — נראה כאילו כל האפליקציה נתקעה, לא רק שכבת ה-NOTAM. נוסף `threaded=True` לשלושת השרתים; אומת מול שרת אמיתי (לא test client) — `/metrics` ענה תוך 0.01-0.03ש' באופן עקבי גם באמצע שליפת NOTAM של 24 שניות. בנוסף, ל-`_fetch_more_info` (בקשות ה"הרחבה") הוגדר timeout נפרד וקצר יותר (8ש' במקום 20ש') כדי להגביל את זמן ה-worst-case אם ה-WAF מתחיל להאט בקשות בודדות בתוך רצף ארוך.
- **תוקן — Desktop:** 6 מתוך 27 אזורי NOTAM (בעיקר רצועות גבול לבנון/סוריה ואזורים מנהלתיים רחבים) מקורם ב"רשת הביטחון" משורת ה-Q (`_geometry_from_q_line`) ולא בתיאור מדויק — הוצגו כמעגלים "בטוחים בעצמם" למרות שהצורה האמיתית שונה (למשל רצועה, לא מעגל). נוסף שדה `geometry.source` (`"text"`/`"q_line_approx"`) שמועבר עד ל-JS; מעגלי קירוב מוצגים עכשיו עם **מסגרת מקווקוות + מילוי חלש יותר**, ובפופאפ מתווספת אזהרה מפורשת שהצורה קירוב גס בלבד. אומת עם render אמיתי דרך QWebEngineView (0 שגיאות קונסולה, 27/27 אזורים נטענו).

### שכבת גבולות CTR שדות תעופה (17/08/2026)
- המשתמש שם לב שנתב"ג לא מסומן במפה כלל, גם כששכבת NOTAM "אזורי פיקוח שדות תעופה" (`airport_control`) פעילה — כי הקטגוריה הזו מסתמכת רק על אזכורים אד-הוק בטקסט הודעות NOTAM (למשל עגורן בנייה ליד השדה), לא על גבול המרחב המבוקר הקבוע של השדה.
- נמצא מקור רשמי: ה-eAIP הישראלי (e-aip.azurefd.net), סעיף AD 2.17 ("ATS Airspace") לכל שדה — נבדק ואומת ידנית מול 2-3 מחזורי AIRAC שונים (נוב' 2022/אוק' 2024/אוק' 2025) לכל שדה, קואורדינטות זהות בכולם. שלושה שדות בלבד מפרסמים סעיף AD-2 מלא: בן-גוריון (LLBG), חיפה (LLHA), אילת/רמון (LLER, שני מגזרים — צפון ודרום).
- נוסף `airport_ctr_zones.py`/`airport_ctr_zones.dart` (+`airport_ctr_zone.dart` מודל) — קובץ נתונים סטטי חדש, באותו דפוס כמו `uas_coordination_zones.py` הקיים: 4 רשומות, כל אחת עם שם/ICAO/פוליגון/טווח גבהים/הערות. קואורדינטות ה-DDMMSS הומרו לעשרוני בסקריפט ייעודי (לא חושבו ידנית) כדי למנוע טעות על נתון בטיחותי.
- שכבה חדשה, נפרדת מ-NOTAM, בשני הצדדים: כפתור/מקרא ייעודי (🛫, צבע מג'נטה `#f72585`). אומת ב-Desktop עם render אמיתי (0 שגיאות קונסולה). אומת ב-Android עם `flutter build apk --release` מוצלח.
- תוך כדי: הרצפה החזותית המינימלית לפוליגונים (`_scaleUpSmallPolygon`, הייתה Desktop-בלבד) הורחבה גם ל-Android — כעת חלה על שלוש השכבות (NOTAM, אזורי תיאום, CTR) בשני הצדדים.

### רדיוס ראייה רדיאלי (Viewshed מכומת) — כלי חדש (18/08/2026, Desktop + Android)
- כלי חדש (📡), נפרד מ-LOS הנקודה-לנקודה הקיים: משקיף אחד + טווח + צעד זווית → פוליגון גבול-ראייה יחיד (קודקוד אחד לכל אזימוט, במרחק הראייה הרצוף המרבי). תוכנן במשותף עם המשתמש על פני עשרות סבבי הבהרה במצב תכנון (plan mode).
- **Backend** (`weather_server.py`): `_destination_point` (יעד ממקור+אזימוט+מרחק, חדש) + `_horizon_ratchet` (אלגוריתם ה-ratchet חולץ מ-`/los` לפונקציה משותפת — לא שני עותקים, `/los` נבדק ונשאר תואם). ארכיטקטורת **job ברקע + polling + ביטול** (`/los_radial/start`/`/status`/`/cancel`, `threading.Thread`+`Lock`) במקום בקשה חוסמת אחת — כי זמן חישוב טיפוסי בטווח ארוך (200-300 ק"מ) הוא כ-2-4 דקות (עד 4,000 נקודות גובה ב-batches).
- **פרמטרים**: טווח עד 300 ק"מ, מגזר זוויתי חלקי (אזימוט התחלה/סוף, כולל "עטיפה" מעל 360°/0°), מרווח רכס (0-10°, שולי ביטחון מעל הרכס הגבוה ביותר), טווח מינימלי/"אזור עיוור" (ברירת מחדל 5 ק"מ — בלעדיו, שדה-ראייה אנכי צר תמיד נחסם מיד ליד משקיף נמוך מסיבה גיאומטרית טהורה, לא תוכנית — נמצא ותוקן בבדיקה חיה), שדה-ראייה אנכי — מרכז+רוחב (ברירת מחדל 0°/4°=±2°).
- **Frontend** (`MAP.py`): לחיצה על המפה ממקמת משקיף ומציגה תצוגה מקדימה בלבד (קווים+ידיות גרירה) — לא מחשבת. גרירת ידית קובעת זווית (עצמאית) וטווח (משותף לשתי הידיות). חישוב מופעל רק בלחיצה מפורשת על "הפעל חישוב". תוצאה: לכל אזימוט מצויר קו ירוק מתחילת הדגימה (`min_range_km`) עד המרחק שעדיין רואים, וממשיך אדום עד סוף הטווח המבוקש אם נחסם לפני כן — כמו LOS הרגיל, לא נעצר בנקודת החסימה.
- **תיקון אחרי בדיקה חיה של המשתמש (18/08/2026)**: שדה-הראייה האנכי היה בהתחלה **קבוע בקוד, בלתי-נראה בממשק** — גרם לתוצאות "חסומות" בכל הכיוונים בלי שום הסבר גלוי (כי גובה יעד גבוה לא עוזר אם הזווית הנדרשת חורגת מהאלומה הצרה). הוצג כשני שדות ניתנים-לשינוי ("מרכז אלומה אנכי"/"רוחב אלומה אנכי") כדי שהמשתמש יראה וישלוט בפרמטר שממילא משפיע דרמטית על התוצאה.
- נבדק: backend מול Open-Meteo אמיתי (כולל regression check ל-`/los`), frontend ב-render חי (QWebEngineView, 0 שגיאות קונסולה) — תצוגה מקדימה, גרירה, איפוס, וציור פוליגון+חישורים דו-צבעוניים עם נתונים מדומים (לא בזבוז API).
- **בדיקה חיה נוספת (18/08/2026, ערב)**: משקיף מעל ים פתוח עם `tgt_h` גדול+אלומה צרה החזיר "חסום בכל הכיוונים" למרות קטע ראייה אמיתי באמצע הטווח — אובחן: הלולאה עצרה בכישלון הדגימה **הראשונה** ולא המשיכה הלאה, כי עצם בגובה קבוע "נראה" בזווית קטנה יותר ככל שמתרחקים ממנו (לא כמו רכס טופוגרפי אמיתי). מתוך 4 אפשרויות שהוצגו, המשתמש בחר: **לדווח את המרחק הרחוק ביותר שעדיין גלוי לאורך הקרן**, לא רק רצף-מהקרוב — שינה את קודקוד הפוליגון בהתאם (`weather_server.py`), אומת מול התרחיש המדויק שדווח.

**Android (הושלם באותו יום, 18/08/2026)**: מומש **on-device** לגמרי, ללא שרת/job — `weather_server.py`'s `_horizon_ratchet` הועבר ל-Dart (`api_service.dart::_horizonRatchet`, כולל שני התיקונים למעלה) ואומת מול Python ב-3 מקרי בדיקה זהים (סקריפט עצמאי). `fetchRadialLos` מבצע את שליפת הגבהים ב-batches (30, השהיה 0.5 שנ') עם `RadialLosCancelToken` לביטול לקוח במקום ביטול-שרת (`onProgress` callback במקום polling). ה-UI (`map_screen.dart`) עוקב אחרי אותה זרימה כמו Desktop (לחיצה=מיקום משקיף בלבד, תצוגה מקדימה+ידיות גרירה מבוססות `latlong2.Distance`, "הפעל חישוב" מפורש) אך מוצג ככפתור-אייקון עצמאי צף (📡, `_RadialLosPanel`) ולא בסרגל הכלים העליון — 5 הכפתורים שם כבר במקסימום. פאנל הפרמטרים (10 שדות) נפתח רק בלחיצה על האייקון. אומת ב-`flutter analyze` נקי (רק אזהרות קדם-קיימות לא קשורות).

### תצפית מכ"ם דופלר (רעיוני/חינוכי) — כלי שלישי, נפרד (19-20/08/2026, Desktop בלבד)
- כלי חדש (🎯), שלישי בנפרד מ-LOS ומרדיוס-הראייה: אותו רעיון בסיסי (משקיף+כל האזימוטים+פוליגון גבול יחיד), עם 3 שכבות פיזיקה חדשות מעל חסימת שטח — **משוואת מכ"ם** (טווח גילוי לפי הספק/רווח/RCS/תדר/רגישות מקלט), **דופלר** (מהירויות עיוורות ו-MDV, תלוי-אזימוט), ו**תפוצה** (multipath/lobing מהשתקפות קרקע, תלוי-נקודה). **רעיוני/חינוכי במפורש** — לא מבוסס מערכת מכ"ם אמיתית ספציפית, הוחלט מראש עם המשתמש (אחרי דיון מושגי דומה שעלה בזמן תכנון רדיוס-הראייה).
- **Backend** (`weather_server.py`): `_radar_max_range_m` (משוואת המכ"ם הסטנדרטית `R=[(Pt·G²·λ²·σ)/((4π)³·Pmin·L)]^(1/4)`), `_lobing_factor` (מודל two-ray מפושט מעל משטח שטוח), `_doppler_detectable`+`_max_unambiguous_range_m` (מהירויות עיוורות/MDV/PRF). אותו דפוס job+polling+ביטול בדיוק כמו רדיוס-הראייה (`/radar_doppler/start`/`/status`/`/cancel`, `_radar_jobs` נפרד לגמרי), ואותם קבועי דגימה גנריים (`_RADIAL_BASE_BUDGET` וכו') — לא כפולים. ברירות מחדל שונות: טווח 50 ק"מ, שדה-ראייה אנכי 10°, טווח מינימלי 1 ק"מ.
- **19 פרמטרים** ב-4 קבוצות (גיאומטריה/משוואת מכ"ם/דופלר/תפוצה) בפאנל אחד — כולל dropdowns "סוג מטרה" (RCS) ו"פס תדרים" במקום קלט מספרי גולמי לפרמטרים האלה.
- **סטייה מודעת מהתוכנית**: התוכנית המקורית הציעה "מהירות רדיאלית משוערת" כשדה יחיד לפישוט; הוחלף במימוש במהירות+כיוון תנועה אמיתיים של המטרה, כי מהירות רדיאלית תלויה בזווית בין כיוון התנועה לאזימוט הקרן הנבדקת — בלי זה כל הקרניים היו מקבלות אותה תוצאת-דופלר בדיוק (לא מדגים אזור-עיוורון תלוי-כיוון, שזו בדיוק הסיבה לבנות כלי "דופלר" נפרד מכלי טווח-גילוי גנרי).
- **Frontend** (`MAP.py`): אותה זרימה בדיוק כמו רדיוס-הראייה (לחיצה=משקיף+תצוגה מקדימה, ידיות גרירה, "הפעל חישוב" מפורש), בצבע ציאן ייחודי (`#22d3ee`) שלא חופף לצהוב של רדיוס-הראייה. תוצאה **תלת-צבעונית** (לא דו-צבעונית כמו הכלי הקודם): ירוק=מזוהה, כתום=כל הכיוון חסום דופלר (גם אם השטח/טווח המכ"ם היו מאפשרים גילוי), אדום=נחסם שטח או מעבר לטווח המכ"ם.
- נבדק: `py_compile` על כל קובץ ששונה, רגנרציית `map.html`+render חי (QWebEngineView) — 0 שגיאות קונסולה, gating לפי `_mapReady`, סימולציית לחיצה+תצוגה מקדימה. הרצת job אמיתית מול Open-Meteo (טווח קטן, quota-conscious) הניבה תוצאה תואמת חישוב ידני: טווח מכ"ם 39.87 ק"מ, טווח לא-חד-משמעי 149.9 ק"מ, ודפוס חסימת-דופלר "פרפר" ניצב לכיוון תנועת המטרה (מטרה טסה צפונה → בדיוק האזימוטים מזרח/מערב, הניצבים לכיוון התנועה, חסומי-דופלר) — שלושתם תואמים בדיוק לפיזיקה. **Android טרם קיבל את הכלי** — לא כלול בסבב הזה, לפי אותו כלל שחל על רדיוס-הראייה (לא מתחילים פורט בזמן שכלי חדש עדיין לא נבדק חי ע"י המשתמש עצמו בממשק בפועל).

### קודם לכן
- הוספת שכבת NOTAM (7 קטגוריות סיווג) + שכבת "אזורי תיאום כטב״ם" + הודעת כלל VLOS
- קו ראייה (LOS) עם sessions מרובים, פאנל פרופיל גובה, ידיות גרירה/גובה
- דשבורד מעקב תהליכים + דשבורד בדיקות אבטחה (כולל CIS L1/L2) ב-Desktop
- כלי מדידת מרחק (Ruler), שכבת רקע Dropdown, GPS/מיקום עצמי (Android)
- 3 מקורות data למסלולי טיסה ב-Android (שרת מקומי → OpenSky → FR24 Gold)

---

*מסמך זה עודכן לאחרונה ב-20/08/2026 ע"י Claude Code, מבוסס על קריאת קוד המקור בפועל.*
