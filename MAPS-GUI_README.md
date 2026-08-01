# מפה אינטראקטיבית — תיעוד מלא
**תאריך עדכון:** 19/05/2026 | **פרויקט:** maps-gui | **מיקום:** `d:\PY-IS\maps-gui`

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

אפליקציה גיאוגרפית-מטאורולוגית דו-פלטפורמית:
- **Desktop (Windows):** PyQt5 + QWebEngineView + Leaflet.js
- **Android:** Flutter 3.19+ עם flutter_map

### פיצ'רים עיקריים
| פיצ'ר | Desktop | Android |
|--------|---------|---------|
| מפה אינטראקטיבית | Leaflet.js (WebView) | flutter_map |
| שכבת גבהים (heatmap) | leaflet.heat | open-meteo API |
| שכבת טמפרטורות | OpenWeather API | open-meteo API |
| מסלולי טיסות | FlightRadar24 API | FR24 + OpenSky + local server |
| GPS / מיקום עצמי | — | geolocator |
| כלי מדידת מרחק | — | Haversine בלב האפליקציה |
| תמיכת RTL עברית | מלאה | מלאה (Directionality.rtl) |
| ערכת צבעים | Catppuccin Mocha (כהה) | Material 3, ThemeMode.dark |

---

## 2. מבנה תיקיות

```
d:\PY-IS\maps-gui\
├── main.py                    ← Desktop GUI ראשי (PyQt5)
├── MAP.py                     ← גנרטור map.html (Leaflet)
├── apipyqt.py                 ← wrapper לקריאות API מה-GUI
├── geo_server.py              ← Flask port 5003 (Google Geocoding)
├── weather_server.py          ← Flask port 5002 (OpenWeather)
├── flight_server.py           ← Flask port 5004 (FlightRadar24)
├── weather_tool.py            ← כלי עזר מזג אוויר
├── heatmap_layer.py           ← כלי עזר heatmap
├── requirements.txt           ← dependencies Python
├── .env                       ← מפתחות API (לא לגיט!)
├── .env.example               ← תבנית משתני סביבה
├── map.html                   ← מפה Leaflet שנוצרת בריצה
├── heatmap.html               ← heatmap עצמאי
├── icons/                     ← bell_icon*.png
├── maps-gui-android/          ← FLUTTER APP ← זה הייצור
│   ├── pubspec.yaml
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/map_screen.dart
│   │   ├── services/api_service.dart
│   │   ├── state/map_state.dart
│   │   ├── models/grid_point.dart
│   │   ├── utils/heat_image.dart
│   │   └── widgets/controls_panel.dart
│   └── android/
│       ├── app/build.gradle.kts
│       ├── app/src/main/AndroidManifest.xml
│       └── local.properties
├── maps-gui-android-src/      ← גרסה חלופית/מקור (לא לייצור)
├── maps-gui-secure/           ← העתק לבדיקות
└── גירסה תקינה/               ← גיבוי גרסה יציבה
```

---

## 3. אפליקציית Desktop — Python/PyQt5

### קבצים עיקריים
- **`main.py`** — חלון ראשי, QWebEngineView לטעינת map.html, ניהול 3 שרתי Flask כ-subprocess, היסטוריית ערים, ספינרי קואורדינטות עם debounce, לוג צבעוני, מערכת התראות (bell icon), cache מזג אוויר עם timestamp
- **`MAP.py`** — יוצר map.html דינמי עם Leaflet.js, ערכת CartoDB Dark Matter, תמיכת RTL עברית, שכבת heatmap, מעקב טיסות, עמדות מזג אוויר
- **`apipyqt.py`** — `fetch_weather_data()`, `fetch_geo_data()`, גרסה async

### שרתים שמופעלים מה-Desktop
```
port 5002 → weather_server.py
port 5003 → geo_server.py
port 5004 → flight_server.py
```
כל שרת: Flask + CORS, לוגים ל-`app_combined.log`, מנגנון kill zombie processes בהפעלה

### התקנה וריצה
```powershell
# התקנת dependencies
pip install -r requirements.txt

# הרצה
python main.py
```

### requirements.txt
```
requests, PyQt5, PyQtWebEngine, python-dotenv, Flask, flask-cors, pandas, folium, tqdm, FlightRadar24
```

---

## 4. אפליקציית Android — Flutter

### מיקום: `d:\PY-IS\maps-gui\maps-gui-android\`

### Dependencies (pubspec.yaml)
```yaml
flutter_map: ^7.0.2       # מפה
latlong2: ^0.9.1          # קואורדינטות
http: ^1.2.1              # HTTP calls
provider: ^6.1.2          # State management
material_symbols_icons: ^4.2719.3
geolocator: ^13.0.4       # GPS
```

### ארכיטקטורה
```
main.dart
  └── ChangeNotifierProvider(MapState)
        └── MapScreen (StatefulWidget)
              ├── FlutterMap (flutter_map)
              ├── ControlsPanel (Drawer RTL)
              └── Cards: Elevation, Weather, Ruler, Scale
```

### State Management — `map_state.dart`
מחלקת `MapState` (ChangeNotifier) מנהלת:
- בחירת אזור (selectionStart/End) + bounds
- שכבת גבהים (elevPoints, elevHeatBytes, elevMode)
- שכבת טמפרטורות (tempPoints, tempHeatBytes, tempMode)
- נתוני טיסה (FlightData: path, current, callsign, info)
- נקודות מסומנות (pinnedPoints)
- GPS (goToMyLocation)
- כלי מדידה (rulerMode, rulerPoints, Haversine)
- מזג אוויר לנקודה (weatherData, weatherPoint)
- שכבת רקע (tileUrl, tileAttribution)

### מצבי תצוגה (DisplayMode)
```dart
enum DisplayMode { heat, grid, dots }
enum LayerType { none, elevation, temperature }
```

### AndroidManifest.xml — הרשאות
```xml
INTERNET, ACCESS_NETWORK_STATE
ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION
android:usesCleartextTraffic="true"   ← חובה לחיבור לשרת desktop
```

### Build Config (app/build.gradle.kts)
- `namespace = "com.mapsapp.maps_gui_android"`
- `applicationId = "com.mapsapp.maps_gui_android"`
- Java 17, Kotlin JVM target 17
- `signingConfig = signingConfigs.getByName("debug")` ← חתימה בdebug key (לפיתוח)

---

## 5. שרתי Flask (Backend)

### geo_server.py — port 5003
- Route: `GET /geo_data?location=<city>`
- קורא Google Geocoding API
- מחזיר: `{lat, lng, formatted_address}`

### weather_server.py — port 5002
- Routes: `GET /weather?region=<name>` או `GET /weather?lat=<>&lon=<>`
- קורא OpenWeather API
- מחזיר: `{temp, conditions, wind_speed, ...}`

### flight_server.py — port 5004
- Route: `GET /flight_route?flight=<callsign>`
- קורא FlightRadar24API (Python library)
- ממפה IATA→ICAO (LY→ELY וכו')
- מחזיר: `{trail:[{lat,lng}], lat, lng, callsign, origin_iata, dest_iata, aircraft}`

---

## 6. ממשקי API חיצוניים

### Android — api_service.dart
| API | שימוש | URL |
|-----|-------|-----|
| open-meteo elevation | גבהים (grid) | `api.open-meteo.com/v1/elevation` |
| open-meteo forecast | טמפרטורות (grid) | `api.open-meteo.com/v1/forecast` |
| OpenSky Network | מסלולי טיסה (primary fallback) | `opensky-network.org/api/states/all` |
| FlightRadar24 Gold | מסלולי טיסה (last resort) | `data.flightradar24.com` |
| שרת desktop (WiFi) | מסלולי טיסה (עדיפות ראשונה) | `http://{flightServerHost}:5004` |

### סדר עדיפויות — fetchFlightTrack()
1. **Local flight server** (desktop, אותו WiFi) — port 5004
2. **OpenSky Network** — חינמי, ללא Cloudflare
3. **FlightRadar24 Gold API** — fallback אחרון עם token

### Desktop — שרתי Python
| API | מפתח | קובץ |
|-----|-------|------|
| OpenWeather | OPENWEATHER_API_KEY | weather_server.py |
| Google Geocoding | GOOGLE_API_KEY | geo_server.py |
| FlightRadar24 | FR24_USER + FR24_PASS + FR24_TOKEN | flight_server.py |

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

**Token FR24 מוטמע גם ב-api_service.dart:**
```dart
static const _fr24Token = '<REDACTED>';
```

---

## 8. Build — ייצור APK

### דרישות סביבה
- Flutter SDK 3.19+ (בדוק: `flutter --version`)
- Android SDK + NDK (ב-`C:\dev\android-sdk\ndk`)
- Java 17
- `local.properties` מוגדר עם `flutter.sdk=<path>`

### פקודות Build
```powershell
cd d:\PY-IS\maps-gui\maps-gui-android

# בדיקת סביבה
flutter doctor

# ניקוי cache (לפני build חדש)
flutter clean
flutter pub get

# APK debug
flutter build apk --debug

# APK release (חתום בdebug key)
flutter build apk --release

# APK מפוצל לפי ארכיטקטורה (קובץ קטן יותר)
flutter build apk --split-per-abi --release
```

### מיקום APK שנוצר
```
maps-gui-android\build\app\outputs\flutter-apk\
├── app-debug.apk
├── app-release.apk
└── app-arm64-v8a-release.apk  (אם split-per-abi)
```

### בעיות Build נפוצות
| בעיה | פתרון |
|------|-------|
| `flutter.sdk` לא מוגדר | בדוק `android/local.properties` |
| Kotlin version conflict | בדוק `build.gradle.kts` — kotlinVersion |
| NDK missing | הגדר `ndkVersion` ב-`build.gradle.kts` |
| Gradle sync fail | `flutter clean && flutter pub get` |

---

## 9. הגבלות ואילוצים ידועים

### אנדרואיד
- **FlightRadar24 Cloudflare:** FR24 חוסם לעיתים בקשות ישירות. הפתרון: שרת desktop כ-proxy (אותו WiFi) → OpenSky → FR24 Gold token
- **HTTP cleartext:** `usesCleartextTraffic="true"` דרוש לחיבור לשרת desktop על HTTP
- **GPS:** דורש הרשאת `ACCESS_FINE_LOCATION` — נשאל runtime
- **גבהים:** open-meteo מחזיר chunk של 100 נקודות מקסימום — מחולק אוטומטית
- **טמפרטורות:** open-meteo מגביל 20 נקודות בו-זמנית עם delay 200ms בין chunks
- **שרת Flight מרוחק:** `ApiService.flightServerHost` ריק כברירת מחדל — משתמש צריך להגדיר ב-settings

### Desktop
- **Port conflicts:** שרתי Flask הורגים zombie processes על פורטים 5002/5003/5004 בכל הפעלה
- **Python 3.14:** נדרשת גרסת Python תואמת לכל הpackages
- **API rate limits:** OpenWeather מגביל קריאות בתוכנית חינמית

### כללי
- **ללא אימות:** האפליקציה לא מבצעת login — מפתחות API מוטמעים בקוד/env
- **ללא גיט:** הפרויקט אינו ב-git repository
- **חיבור WiFi:** לשימוש בשרת desktop מהאנדרואיד — חובה אותה רשת WiFi

---

## 10. הנחיות עבודה עם Claude

### כללי עבודה מרכזיים
1. **אל תשבור פעולות קיימות** — בכל שינוי יש לוודא שלא נפגע שום תהליך או פיצ'ר קיים
2. **שפת UI — עברית בלבד** — כל טקסט למשתמש בעברית, כולל error messages
3. **RTL** — כל ממשק בכיוון RTL, שימוש ב-`Directionality(textDirection: TextDirection.rtl)`
4. **ערכת צבעים כהה** — Dark theme עם Material 3, `ThemeMode.dark`
5. **אל תוסיף פיצ'רים שלא התבקשו** — פחות זה יותר
6. **אל תוסיף הערות לקוד** — רק כשה-WHY לא ברור לחלוטין
7. **Flutter בלבד לאנדרואיד** — לא Buildozer, לא Kivy — Flutter + Dart
8. **לא לשכוח לייצר APK** — אחרי כל שינוי מבוקש ב-Android

### הנחיות טכניות
- **State management:** Provider pattern בלבד (ChangeNotifier) — לא Bloc, לא Riverpod
- **API calls:** `http` package בלבד — לא dio
- **מפות:** `flutter_map` בלבד — לא google_maps_flutter
- **Gradle:** Kotlin DSL (`.kts`) — לא Groovy
- **Java:** גרסה 17 — לא 11, לא 21

### Build process
- תמיד לרוץ מתוך `d:\PY-IS\maps-gui\maps-gui-android\`
- לפני build חדש: `flutter clean && flutter pub get`
- APK ב: `build\app\outputs\flutter-apk\`

### קבצים שחייבים להישאר בסינק
אחרי כל שינוי ל-`api_service.dart` — לוודא שגם `map_state.dart` תואם
אחרי שינוי ל-`map_state.dart` — לוודא שגם `map_screen.dart` ו-`controls_panel.dart` תואמים

---

## 11. היסטוריית שינויים עיקריים

### גרסה נוכחית (מאי 2026)
- הוספת OpenSky Network כ-fallback עבור נתוני טיסה (Android)
- תיקון FlightRadar24 Cloudflare blocking — שילוב 3 מקורות data
- כלי מדידת מרחק (Ruler) עם Haversine + תצוגת NM/ק"מ
- שכבת רקע הוחלפה לDropdown: OSM / ESRI Satellite / CartoDB Dark
- כרטיס גובה בלחיצה על שכבת elevation
- scale bar דינמי בפינה ימנית-תחתונה

### ארכיטקטורה Flight Tracking (Android)
```
fetchFlightTrack(callsign)
    ↓ 1. local flight server (WiFi)  → _parseFlightServerResponse()
    ↓ 2. OpenSky Network             → _fetchOpenSky()
    ↓ 3. FlightRadar24 Gold          → _fetchFR24()
```

---

*מסמך זה נוצר אוטומטית ב-19/05/2026 על ידי Claude Code*
