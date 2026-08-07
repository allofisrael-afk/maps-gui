# פרומט לשיחה חדשה עם Claude — פרויקט maps-gui
*העתק את הטקסט הבא והדבק אותו בתחילת כל שיחה חדשה*

---

## ════════════════════════════════════════
## הדבק בשיחה חדשה:
## ════════════════════════════════════════

אתה עוזר לי בפרויקט **מפה אינטראקטיבית** — אפליקציית גיאוגרפיה/מטאורולוגיה דו-פלטפורמית.

**לפני שמתחילים — קרא את שני מסמכי התיעוד המלאים בשורש הפרויקט:**
- `MAPS-GUI_README.md` — מדריך טכני/תפעולי (מבנה, build, APIs, בעיות ידועות)
- `MAPS-GUI_SRS.md` — מפרט דרישות מלא (דרישות ממוספרות לכל פיצ'ר, כולל רשימת קוד מת/פערים/בעיות אבטחה שהתגלו בסריקה)

---

### 📁 מיקום הפרויקט
```
d:\PY-IS\maps-gui\
```

### 🗂️ Git
הפרויקט **כן** נמצא ב-git (בניגוד לתיעוד ישן שאמר אחרת). Remote: `origin` → `https://github.com/allofisrael-afk/maps-gui.git`, branch ראשי `main`. אל תדחוף (`push`) בלי אישור מפורש בכל פעם.

### 🏗️ ארכיטקטורה
הפרויקט מורכב משני חלקים עצמאיים (לא חולקים קוד ביניהם):

**1. Desktop (Python 3.14, PyQt5) — `d:\PY-IS\maps-gui\`**
- `main.py` — GUI ראשי, QWebEngineView + Leaflet.js, ניהול 3 תהליכי Flask כ-subprocess, ודשבורד מעקב תהליכים נפרד (`ProcessDashboard` + `MetricsWorker` — thread נפרד למניעת הקפאת ה-GUI)
- `MAP.py` — גנרטור `map.html`: heatmap, שכבות גבהים/טמפרטורה (heat/grid/dots + tooltip בהעברת עכבר), מסלולי טיסה, כלי מדידת מרחק (Ruler), קו ראייה (LOS) עם פאנל פרופיל גובה
- `apipyqt.py` — קוד legacy, **לא בשימוש בפועל** ע"י `main.py` (הוא עושה קריאות `requests` ישירות)
- `metrics.py` — מודול משותף שמוסיף `GET /metrics` לכל שרת Flask (ספירת קריאות/שגיאות/latency), נצרך ע"י הדשבורד
- שרתי Flask: `geo_server.py` (5003), `weather_server.py` (5002 — מכיל גם `/elevation`, `/temp_grid`, `/los`), `flight_server.py` (5004)
- **סביבה:** `.venv/` (Python 3.14, נוצר עם `virtualenv` — לא stdlib `venv`!). `.venv/Scripts/python.exe` הוא launcher stub שמבצע re-exec לתהליך האמיתי; Flask עם `debug=True` מוסיף עוד שכבת reloader — כל שרת הוא בפועל שרשרת של 2-4 תהליכי OS. **חובה** להשתמש ב-`sys.executable` (לא `"python"` גולמי) בכל `subprocess.Popen`, ולעצור/למדוד תהליכים דרך כל העץ (`psutil` + `children(recursive=True)`) ולא רק ה-PID השמור — אחרת תהליכים נשארים תקועים ותופסים פורטים אחרי "עצירה".

**2. Android (Flutter)**
**⚠️ מקור האמת הוא `maps-gui-android-src\` — לא `maps-gui-android\`!** הפרויקט הבר-בנייה (`maps-gui-android\`) הוא scaffold שנוצר ע"י `build_apk.ps1`, שמעתיק אליו `lib/`, `pubspec.yaml` ו-`AndroidManifest.xml` מתוך `maps-gui-android-src\` בכל build. **תמיד לערוך ב-`-src`, אף פעם לא ישירות ב-`maps-gui-android\`.**
```
d:\PY-IS\maps-gui\maps-gui-android-src\
├── lib/main.dart                    ← entry point, Locale('he','IL') + ThemeMode.dark כפויים
├── lib/screens/map_screen.dart      ← מסך יחיד: FlutterMap + סרגל עליון צף + BottomAppBar
├── lib/services/api_service.dart    ← כל ה-API calls (כולל fallback chain לטיסות, LOS on-device)
├── lib/state/map_state.dart         ← MapState (ChangeNotifier, Provider) — כל ה-state
├── lib/models/grid_point.dart       ← {lat, lon, value} לגבהים/טמפרטורות
├── lib/models/los_session.dart      ← session של קו ראייה (LosPoint, LosSession)
├── lib/models/city_result.dart      ← תוצאת חיפוש עיר (Nominatim)
├── lib/utils/heat_image.dart        ← רינדור heat-image (PNG) בצד הלקוח
└── lib/widgets/controls_panel.dart  ← LayersPanel/LocationPanel/FlightPanel (bottom sheets, לא Drawer)
```
**חשוב:** אין Drawer בפועל — הניווט הוא `BottomAppBar` עם 3 כפתורים שפותחים modal bottom sheets (שכבות/מיקום/טיסות).

### 📦 Dependencies Flutter
```yaml
flutter_map: ^7.0.2         # מפה
latlong2: ^0.9.1            # קואורדינטות
http: ^1.2.1                # HTTP
provider: ^6.1.2            # State management
geolocator: ^13.0.4         # GPS
material_symbols_icons: ^4.2719.3
shared_preferences: ^2.2.2  # היסטוריית ערים/טיסות (עד 10 כ"א)
```

### 🌐 APIs (Android)
- **גבהים:** `open-meteo.com/v1/elevation` — חינמי, ללא key (chunks של 50, עד 100 נק')
- **טמפרטורות:** `open-meteo.com/v1/forecast` — חינמי, ללא key (chunks של 20, delay 200ms, עד 30 נק')
- **חיפוש עיר:** `nominatim.openstreetmap.org/search` — חינמי, דורש header `User-Agent`
- **קו ראייה (LOS):** מחושב **כולו on-device** ב-`api_service.dart` (לא endpoint שרת) — גבהים מ-Open-Meteo, אלגוריתם עקמומיות+רפרקציה זהה עקרונית לזה שבצד Desktop (`weather_server.py` `/los`), אך מימוש Dart נפרד — **כל שינוי לנוסחה חייב להתעדכן בשני המקומות**
- **טיסות (3 שלבים, `fetchFlightTrack`):**
  1. שרת desktop מקומי `http://{flightServerHost}:5004/flight_route?flight=` — **שים לב: כרגע אין דרך להגדיר `flightServerHost` מה-UI, כך שהשלב הזה מת בפועל**
  2. OpenSky Network (חינמי, ללא Cloudflare)
  3. FlightRadar24 Gold token (fallback אחרון, token קשיח בקוד — ייחשף בפירוק APK)

### 🔑 APIs (Desktop — קובץ .env)
```
OPENWEATHER_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
GOOGLE_API_KEY=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_TOKEN=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_USER=<REDACTED — ראה .env המקומי, לא בגיט>
FR24_PASS=<REDACTED — ראה .env המקומי, לא בגיט>
```

### 🛠️ Build APK
הדרך הנכונה: להריץ `build_apk.ps1` משורש הפרויקט (הוא מטפל בהכל: מתקין Flutter/Java/Android SDK אם חסר, מעתיק את `-src` לפרויקט הבר-בנייה, `pub get`, `build apk --release`).
```powershell
cd d:\PY-IS\maps-gui
powershell -ExecutionPolicy Bypass -File build_apk.ps1
# APK נמצא ב: maps-gui-android\build\app\outputs\flutter-apk\app-release.apk
```
**אם ה-build נכשל עם `OutOfMemoryError: Metaspace`** — זה כבר קרה, הפתרון: להגדיל `org.gradle.jvmargs` ב-`maps-gui-android\android\gradle.properties` (כרגע `-Xmx2g -XX:MaxMetaspaceSize=512m`).

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
11. **אחרי כל שינוי לאנדרואיד** — ייצר APK חדש (ותמיד ערוך ב-`maps-gui-android-src\`, לא ב-`maps-gui-android\`)
12. **הפרויקט כן ב-git** — `origin/main` על GitHub. אל תדחוף בלי אישור מפורש בכל פעם, ואל תעשה force-push

### ⚡ אילוצים טכניים ידועים
- FlightRadar24 חוסם Cloudflare — לכן יש 3 שלבי fallback (Android) / אימות מדורג עם FR24_TOKEN קודם (Desktop)
- open-meteo: max 100 נקודות לגבהים, max 20-30 לטמפרטורות עם delay 200ms
- `usesCleartextTraffic="true"` ב-AndroidManifest — חובה לחיבור HTTP לשרת desktop
- NDK ב: `C:\dev\android-sdk\ndk`, Flutter מוצמד ל-3.41.9-stable, build-tools 35.0.0
- **שרתי Flask (Desktop) רצים עם `debug=True`** — הרנר של Werkzeug + ה-launcher stub של virtualenv יוצרים שרשרת תהליכים (ר' סעיף Desktop למעלה) — תמיד לעצור/למדוד עם `psutil` על כל העץ, לא רק ה-PID השמור
- אם `pip install` נכשל עם שגיאת רגיסטרי על `Common AppData` — זו בעיה ידועה בסביבה הזו (Windows חסר ערך רגיסטרי סטנדרטי), כבר תוקנה פעם אחת ב-HKCU

---

### 📍 מצב נוכחי (07/08/2026)
פיצ'רים פעילים ב-**Android**:
- [x] מפה (OSM / ESRI Satellite / CartoDB Dark) — Dropdown selector
- [x] שכבת גבהים — heat / grid / dots
- [x] שכבת טמפרטורות — heat / grid / dots
- [x] "חום ידני" — סימון נקודות ידני, ללא קריאת שרת (Gaussian kernel on-device)
- [x] בחירת אזור בגרירה / הקשה-הקשה / לחיצה-ארוכה + ידיות עריכה
- [x] מסלולי טיסה (3 מקורות data — שרת desktop לא פעיל בפועל כרגע, ר' למעלה)
- [x] GPS מיקום עצמי
- [x] דיקור נקודה ידנית (LAT/LON)
- [x] חיפוש עיר עם גבולות (Nominatim)
- [x] כלי מדידת מרחק (ק"מ + NM)
- [x] קו ראייה (LOS) — sessions מרובים בו-זמנית, פאנל פרופיל גובה
- [x] כרטיס גובה בלחיצה
- [x] כרטיס מזג אוויר בלחיצה
- [x] scale bar דינמי
- [x] BottomAppBar + 3 bottom sheets (שכבות/מיקום/טיסות)

פיצ'רים פעילים ב-**Desktop**:
- [x] כל הנ"ל (במימוש Leaflet.js/JS נפרד, ללא שיתוף קוד עם Android)
- [x] דשבורד מעקב תהליכים (`📊 דשבורד תהליכים`) — סטטוס/PID/uptime/CPU/RAM לכל שרת, מטריקות קריאות API, יומן חי

**מסמכים מלאים לפירוט נוסף:** `MAPS-GUI_README.md`, `MAPS-GUI_SRS.md` (כולל רשימת קוד מת/פערים ידועים).

---

*כעת תאר מה אתה רוצה לעשות/לשנות/לתקן בפרויקט.*

## ════════════════════════════════════════
