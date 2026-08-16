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
| שכבת NOTAM — אזורי פעילות טיסה (7 קטגוריות) | כן, מקרא ניתן לצמצום | כן, מקרא ניתן לצמצום |
| שכבת "אזורי תיאום כטב״ם" (סטטית) | כן, מקרא ניתן לצמצום | כן, מקרא ניתן לצמצום |
| הודעת כלל טיסת VLOS | — | כפתור מידע ייעודי |
| דשבורד מעקב תהליכים (3 שרתי Flask) | כן — סטטוס/PID/CPU/RAM/מטריקות | — |
| דשבורד בדיקות אבטחה (חשיפה + CIS L1/L2) | כן | — |
| GPS / מיקום עצמי | — | geolocator |
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
├── weather_server.py          ← Flask :5002 — OpenWeather, /elevation, /temp_grid, /los, /heatmap_data
├── flight_server.py           ← Flask :5004 — FlightRadar24
├── notam_categories.py        ← 7 קטגוריות סיווג NOTAM — מקור אמת גם ל-MAP.py וגם לתפריט ב-main.py
├── notam_drones.py            ← שליפה/פרסור/cache של NOTAM כטב"ם מ-brin.iaa.gov.il
├── uas_coordination_zones.py  ← נתוני "אזורי תיאום כטב״ם" הסטטיים
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
- **Android:** תוקן סמן חסר בלחיצה למזג אוויר; נוסף כפתור "איפוס מפה" (סרגל עליון, עם דיאלוג אישור — מנקה את כל השכבות/הכלים ומחזיר למרכז ברירת המחדל); "מיקום עצמי" (GPS) ממלא כעת גם את שדות LAT/LON הידניים בפאנל המיקום.

### קודם לכן
- הוספת שכבת NOTAM (7 קטגוריות סיווג) + שכבת "אזורי תיאום כטב״ם" + הודעת כלל VLOS
- קו ראייה (LOS) עם sessions מרובים, פאנל פרופיל גובה, ידיות גרירה/גובה
- דשבורד מעקב תהליכים + דשבורד בדיקות אבטחה (כולל CIS L1/L2) ב-Desktop
- כלי מדידת מרחק (Ruler), שכבת רקע Dropdown, GPS/מיקום עצמי (Android)
- 3 מקורות data למסלולי טיסה ב-Android (שרת מקומי → OpenSky → FR24 Gold)

---

*מסמך זה עודכן לאחרונה ב-16/08/2026 ע"י Claude Code, מבוסס על קריאת קוד המקור בפועל.*
