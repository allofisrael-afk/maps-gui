# פרומט לשיחה חדשה עם Claude — פרויקט maps-gui
*העתק את הטקסט הבא והדבק אותו בתחילת כל שיחה חדשה*

---

## ════════════════════════════════════════
## הדבק בשיחה חדשה:
## ════════════════════════════════════════

אתה עוזר לי בפרויקט **מפה אינטראקטיבית** — אפליקציית גיאוגרפיה/מטאורולוגיה דו-פלטפורמית.

---

### 📁 מיקום הפרויקט
```
d:\PY-IS\maps-gui\
```

### 🏗️ ארכיטקטורה
הפרויקט מורכב משני חלקים:

**1. Desktop (Python/PyQt5)**
- `main.py` — GUI ראשי, QWebEngineView + Leaflet.js
- `MAP.py` — גנרטור map.html
- `apipyqt.py` — wrapper ל-API calls
- שרתי Flask: `geo_server.py` (port 5003), `weather_server.py` (port 5002), `flight_server.py` (port 5004)

**2. Android (Flutter) ← הגרסה הפעילה לפיתוח**
```
d:\PY-IS\maps-gui\maps-gui-android\
├── lib/main.dart                    ← entry point
├── lib/screens/map_screen.dart      ← מסך המפה
├── lib/services/api_service.dart    ← כל ה-API calls
├── lib/state/map_state.dart         ← ChangeNotifier (Provider)
├── lib/models/grid_point.dart
├── lib/utils/heat_image.dart
└── lib/widgets/controls_panel.dart  ← Drawer ימני
```

### 📦 Dependencies Flutter
```yaml
flutter_map: ^7.0.2    # מפה
latlong2: ^0.9.1       # קואורדינטות
http: ^1.2.1           # HTTP
provider: ^6.1.2       # State management
geolocator: ^13.0.4    # GPS
material_symbols_icons: ^4.2719.3
```

### 🌐 APIs (Android)
- **גבהים:** `open-meteo.com/v1/elevation` — חינמי, ללא key
- **טמפרטורות:** `open-meteo.com/v1/forecast` — חינמי, ללא key
- **טיסות (3 שלבים):**
  1. שרת desktop מקומי `http://{host}:5004/flight_route?flight=` (אם WiFi זמין)
  2. OpenSky Network (חינמי, ללא Cloudflare)
  3. FlightRadar24 Gold token (fallback אחרון)

### 🔑 APIs (Desktop — קובץ .env)
```
OPENWEATHER_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
GOOGLE_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_TOKEN=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_USER=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_PASS=<REDACTED — ראה .env המקומי, לא בגיט>
```

### 🛠️ Build APK
```powershell
cd d:\PY-IS\maps-gui\maps-gui-android
flutter clean
flutter pub get
flutter build apk --release
# APK נמצא ב: build\app\outputs\flutter-apk\app-release.apk
```

### App ID
`com.mapsapp.maps_gui_android`

---

### ⚠️ כללים ואילוצים — חובה לשמור!

1. **אל תשבור פיצ'רים קיימים** — כל שינוי חייב לשמור על כל הפעולות הקיימות
2. **עברית בלבד** בממשק המשתמש (כולל error messages)
3. **RTL** — `Directionality(textDirection: TextDirection.rtl)` בכל מקום רלוונטי
4. **Dark theme** — `ThemeMode.dark`, Material 3, ColorScheme.fromSeed (seedColor: Color(0xFF1565C0))
5. **Provider בלבד** — לא Bloc/Riverpod
6. **flutter_map בלבד** — לא google_maps_flutter
7. **http package בלבד** — לא dio
8. **Java 17** — `JavaVersion.VERSION_17` ב-build.gradle.kts
9. **אל תוסיף פיצ'רים שלא ביקשתי**
10. **אל תוסיף הערות לקוד** אלא אם ה-WHY אינו ברור כלל
11. **אחרי כל שינוי לאנדרואיד** — ייצר APK חדש
12. **לא גיט** — הפרויקט לא ב-git repository

### ⚡ אילוצים טכניים ידועים
- FlightRadar24 חוסם Cloudflare — לכן יש 3 שלבי fallback
- open-meteo: max 100 נקודות לגבהים, max 20 לטמפרטורות עם delay 200ms
- `usesCleartextTraffic="true"` ב-AndroidManifest — חובה לחיבור HTTP לשרת desktop
- NDK ב: `C:\dev\android-sdk\ndk`

---

### 📍 מצב נוכחי (19/05/2026)
הפיצ'רים הפעילים ב-Android:
- [x] מפה (OSM / ESRI Satellite / CartoDB Dark) — Dropdown selector
- [x] שכבת גבהים — heat / grid / dots
- [x] שכבת טמפרטורות — heat / grid / dots
- [x] בחירת אזור בגרירה + ידיות עריכה
- [x] מסלולי טיסה (3 מקורות data)
- [x] GPS מיקום עצמי
- [x] דיקור נקודה ידנית (LAT/LON)
- [x] כלי מדידת מרחק (ק"מ + NM)
- [x] כרטיס גובה בלחיצה
- [x] כרטיס מזג אוויר בלחיצה
- [x] scale bar דינמי
- [x] Drawer RTL עם כל הכלים

---

*כעת תאר מה אתה רוצה לעשות/לשנות/לתקן בפרויקט.*

## ════════════════════════════════════════
