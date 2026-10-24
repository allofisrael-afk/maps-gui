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

*אפליקציה + generator:*
- `main.py` — GUI ראשי, QWebEngineView + Leaflet.js, ניהול 3 תהליכי Flask כ-subprocess, ודשבורד מעקב תהליכים נפרד (`ProcessDashboard` + `MetricsWorker`/`HealthCheckWorker`/`SecurityCheckWorker` — כל אחד ב-thread נפרד למניעת הקפאת ה-GUI). קריאות רשת חוסמות (מזג אוויר/טיסות) גם הן על thread נפרד — `WeatherFetchWorker`/`FlightFetchWorker`.
- `MAP.py` — גנרטור `map.html` (f-string אחד ענק, ~1750 שורות): heatmap, שכבות גבהים/טמפרטורה (heat/grid/dots + tooltip), מסלולי טיסה, ruler, LOS עם פאנל פרופיל גובה, 7 קטגוריות NOTAM, אזורי תיאום כטב"ם. **זהירות בעריכה:** שגיאת escaping יחידה (למשל `\n` במקום `\\n` בתוך f-string) שוברת את כל תג ה-`<script>` ביחד — כל שינוי דורש רגנרציה (`python -c "import MAP; MAP.create_map()"`) ובדיקה.

*תשתית משותפת:*
- `ports.py` — קבועי `GEO_PORT`/`WEATHER_PORT`/`FLIGHT_PORT` (מקור אמת יחיד, נצרך ע"י `main.py`, שלושת השרתים, `test_requests.py`, `security_checks.py`)
- `server_common.py` — `create_app(name)` — Flask app אחיד (.env/logging/CORS/`/metrics`) לשלושת השרתים
- `metrics.py` — `register_metrics(app)`, נצרך ע"י `server_common.py`
- `security_types.py` — `SecurityFinding` (dataclass) בלבד — קיים כדי ש-`security_checks.py` ו-`cis_checks.py` לא ייבאו זה מזה במעגל

*שרתי Flask:* `geo_server.py` (5003 — geocoding + NOTAM כטב"ם), `weather_server.py` (5002 — גם `/elevation`, `/temp_grid`, `/los`), `flight_server.py` (5004 — מסלולי טיסה דרך FlightRadar24)

*נתונים/עזר:* `notam_categories.py` (7 קטגוריות סיווג — מקור אמת גם ל-`MAP.py`), `notam_drones.py` (שליפה/פרסור/cache NOTAM כטב"ם מ-brin.iaa.gov.il), `uas_coordination_zones.py` (אזורי תיאום סטטיים), `icao_glossary.py` (גלוסר עברי גס ל-ICAO)

*בדיקות/אבטחה:* `test_requests.py` (health checks לשלושת השרתים + עומס), `security_checks.py` (debug console/סודות/CORS/CVEs/APK), `cis_checks.py` (25 בדיקות הקשחת Windows CIS L1/L2 דרך registry/PowerShell)

*הוסרו לגמרי (קוד מת מאומת — היה קיים בעבר, נמחק):* `apipyqt.py`, `weather_tool.py`, `heatmap_layer.py` — ואם אתה רואה אזכור שלהם במקום אחר, זה מיושן.

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
10. **כל שורה שאתה מתקן או מוסיף — חייבת הערה שמסבירה מה השורה עושה** (לא רק WHY לא-ברור — גם WHAT). זה חלק מתהליך הלמידה של המשתמש, וזה דורס את ברירת המחדל הרגילה של "בלי הערות"
11. **תמיד ערוך רק ב-`maps-gui-android-src\`, אף פעם ב-`maps-gui-android\`** — ובנה APK **רק** דרך `build_apk.ps1`. **אל תבנה APK אוטומטית אחרי שינוי** — רק כשהמשתמש מבקש זאת במפורש, בכל פעם מחדש (אישור קודם לא תקף לשינוי הבא)
12. **הפרויקט כן ב-git** — `origin/main` על GitHub. אל תדחוף בלי אישור מפורש בכל פעם, ואל תעשה force-push
13. **עדכן תמיד את `MAPS-GUI_README.md` ו-`MAPS-GUI_SRS.md`** — על כל שינוי בקוד (פיצ'ר/באג/ריפקטור/קובץ שנוסף-נמחק), לפני שהשינוי נחשב "הושלם" — לא רק כשמתבקש במפורש

### ⚡ אילוצים טכניים ידועים
- FlightRadar24 חוסם Cloudflare — לכן יש 3 שלבי fallback (Android) / אימות מדורג עם FR24_TOKEN קודם (Desktop)
- open-meteo: max 100 נקודות לגבהים, max 20-30 לטמפרטורות עם delay 200ms
- `usesCleartextTraffic="true"` ב-AndroidManifest — חובה לחיבור HTTP לשרת desktop
- NDK ב: `C:\dev\android-sdk\ndk`, Flutter מוצמד ל-3.41.9-stable, build-tools 35.0.0
- **שרתי Flask (Desktop) רצים עם `debug=True`** — הרנר של Werkzeug + ה-launcher stub של virtualenv יוצרים שרשרת תהליכים (ר' סעיף Desktop למעלה) — תמיד לעצור/למדוד עם `psutil` על כל העץ, לא רק ה-PID השמור
- אם `pip install` נכשל עם שגיאת רגיסטרי על `Common AppData` — זו בעיה ידועה בסביבה הזו (Windows חסר ערך רגיסטרי סטנדרטי), כבר תוקנה פעם אחת ב-HKCU

---

### 📍 מצב נוכחי (16/08/2026)
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

**תוכנית שיפור קוד רב-שלבית (בוצעה 16/08/2026):** שלבים 1-4 הושלמו — תיקוני באגים, קריאות רשת ל-thread נפרד, צמצום כפילות קוד (Python+Dart), תשתית משותפת (`ports.py`/`server_common.py`/`security_types.py`) + מחיקת קוד מת. **שלב 5** (פיצול קבצים גדולים — `MAP.py`/`map_screen.dart`/`map_state.dart`) **דולג במפורש לפי בקשה** — אל תציע לפצל את הקבצים האלה בלי לשאול קודם. שלבים 6-8 (ביצועים/UX/כיסוי בדיקות) עדיין לא בוצעו.

**שכבת גבולות CTR שדות תעופה (17/08/2026):** נוספה שכבה סטטית חדשה (`airport_ctr_zones.py`/`.dart`) — גבול CTR קבוע ממקור AIP רשמי (e-aip.azurefd.net, סעיף AD 2.17), לא NOTAM. מכסה LLBG/LLHA/LLER (שני מגזרים). ר' `MAPS-GUI_SRS.md` §3.16/§5.15. יושמה בשני הצדדים, כולל APK. תוך כדי: הרצפה החזותית המינימלית לפוליגונים (`_scaleUpSmallPolygon`) הורחבה גם ל-Android.

**מסמכים מלאים לפירוט נוסף:** `MAPS-GUI_README.md`, `MAPS-GUI_SRS.md` (כולל רשימת קוד מת/פערים ידועים).

---

### 🎯 רדיוס ראייה רדיאלי (Viewshed מכומת) — כלי חדש, מומש (18/08/2026, Desktop + Android)

**התוכנית/היסטוריית הפיתוח המלאה נמצאת ב-`C:\Users\allof\.claude\plans\compiled-gliding-wren.md`** (בקומפיוטר של המשתמש, מחוץ לריפו). זה כלי **חדש, מומש ופעיל**, נפרד מ-LOS הקיים (נקודה-לנקודה) — לא רק תוכנית. עבר תהליך תכנון+מימוש ארוך עם עשרות סבבי עדכון, ואחריו כמה סבבי **בדיקה חיה של המשתמש שחשפו וחייבו תיקוני אלגוריתם אמיתיים** (לא רק UI) — קרא את הסעיף "תקלות שנמצאו ותוקנו" למטה לפני שאתה נוגע בקוד הזה, כי חלק מהתיקונים לא אינטואיטיביים.

**מה זה**: משקיף אחד + טווח + רזולוציית זווית (מגזר מלא או חלקי) → פוליגון גבול-ראייה יחיד (קודקוד אחד לכל אזימוט = **הנקודה הגלויה הרחוקה ביותר על הקרן**, לא בהכרח רציפה מהקצה הקרוב — ר' תיקון #2 למטה).

**מצב נוכחי**: מומש ועובד **בשני הצדדים**. Desktop הושלם ראשון ועבר כמה סבבי בדיקה חיה (ר' "תקלות שנמצאו" למטה). המשתמש ביקש במפורש להמתין עם Android עד שהכלי "יבשיל" ("תמתין עם האנדרואיד כי אני רואה שהכלי עדיין לא בשל") — ההמתנה **הוסרה** באותו יום בהוראה מפורשת נוספת ("ממש את כלל התהליכים החדשים באנדרואיד"), והפורט הושלם (ר' תת-סעיף Android למטה). זה תקדים חשוב: לא להתחיל פורט חדש-לגמרי בזמן שהמשתמש עדיין בודק ידנית בפלטפורמה הראשונה, גם אם ההיגיון מתבקש — לחכות להוראה מפורשת.

**ארכיטקטורה (`weather_server.py`, פורט 5002 — לא geo_server.py)**:
- `GET /los_radial/start` / `GET /los_radial/status?job_id=` / `POST /los_radial/cancel?job_id=` — job ברקע (`threading.Thread`+`Lock`) כי חישוב בטווח ארוך לוקח 2-4 דקות.
- `_horizon_ratchet(dists_m, elevs, h_obs, h_offsets, margin_slope, min_angle_slope, max_angle_slope)` — משותפת עם `/los` הישן.
- `_destination_point` — יעד ממקור+אזימוט+מרחק (חדש).
- פרמטרים: `range_km` (עד 300), `min_range_km` (ברירת מחדל 5 — "אזור עיוור"), `angle_step_deg`, `start/end_bearing_deg` (מגזר חלקי, תומך עטיפה מעל 360°/0°), `obs_h`/`tgt_h`, `ridge_margin_deg` (0-10°), `vertical_center_deg`/`vertical_width_deg` (שדה-ראייה אנכי — ברירת מחדל 0°/4°=±2°, **ניתן לשינוי מהממשק**, לא קבוע).
- Frontend ב-`MAP.py`: `RadialLosControl` (`L.Control`, לא Qt), לחיצה על המפה = תצוגה מקדימה בלבד (2 קווים+ידיות גרירה — קובעות גם זווית וגם טווח משותף), חישוב אמיתי רק בלחיצה על "הפעל חישוב". תוצאה: לכל אזימוט קו ירוק (טווח גלוי) שממשיך אדום עד סוף הטווח המבוקש אם נחסם.
- `main.py`: רק 4 רשומות לוג (`__radial_los_loading__/_loaded__/_error__/_cancelled__`) — אין כפתור Qt.

**תקלות שנמצאו בבדיקה חיה ותוקנו — קרא לפני שנוגעים באלגוריתם**:
1. **"זיהום" האופק ע"י גובה היעד** — כש-`tgt_h` מוחל על כל נקודה (לא רק האחרונה, בשונה מ-`/los`), אסור שהוא ישפיע גם על בניית קו האופק (`max_angle`) — אחרת שטח ישר לגמרי (ים) נחסם בהדרגה עם המרחק בלי שום סיבה אמיתית. הפתרון: `_horizon_ratchet` מחשב `bare_angle` (בלי `h_offset`, לבניית האופק) בנפרד מ-`test_angle` (עם `h_offset`, לבדיקת הנקודה עצמה).
2. **"הליכה נעצרת בכישלון ראשון" מפספסת קטע ראייה אמצעי** — עם `tgt_h` גדול+קבוע ועם אלומה אנכית צרה, הזווית הנדרשת **יורדת** עם המרחק (לא כמו רכס אמיתי) — כך שהנקודה הקרובה יכולה להיכשל בעוד נקודה רחוקה יותר עוברת. המשתמש בחר (מתוך 4 אפשרויות שהוצגו): קודקוד הקרן = **הנקודה הגלויה הרחוקה ביותר בכל הקרן**, לא נעצר בכישלון הראשון. **תופעת לוואי ידועה, לא תוקנה**: הקו הירוק בממשק מצויר ברצף מהקצה הקרוב ועד לקודקוד הזה, גם אם יש קטע לא-גלוי באמצע — המשתמש מודע לזה ובחר להשאיר כך.
3. **אומת מול פיזיקה ידועה**: משקיף בים פתוח (שטח 0 בכל כיוון) עם `obs_h=20`/`tgt_h=10` נותן ראייה עד כ-28-31 ק"מ ואז חסימה — תואם בדיוק לנוסחת "אופק מכ"ם/ראייה" הידועה (`4.12×√גובה` ק"מ, עם תיקון שבירה). זו בדיקת-שפיות טובה לכל שינוי עתידי באלגוריתם.
4. **פתוח, לא נחקר**: בבדיקה האחרונה של המשתמש (מעגל מלא, 360°, ים פתוח) 2 מתוך ~360 כיוונים יצאו "פנויים לגמרי" (הגיעו לטווח המלא) בעוד השאר נחסמו בגבול האופק הצפוי — לא הוסבר עדיין למה דווקא אלה.

**Android (הושלם 18/08/2026, אותו יום)**: on-device לגמרי, ללא שרת/job/polling.
- `api_service.dart::_horizonRatchet` — פונקציה **נפרדת** מהלולאה הקיימת ב-`fetchLos` (LOS הנקודה-לנקודה) — לא שיתוף קוד בין השתיים, וגם לא עם Python (ר' ממצא #10 ב-`MAPS-GUI_SRS.md` — כעת 3 מימושים עצמאיים של אותו אלגוריתם ratchet). אומתה מול Python ב-3 מקרי בדיקה זהים (סקריפט Dart עצמאי) לפני שילוב.
- `fetchRadialLos` — שליפת גבהים ב-batches (30, השהיה 0.5 שנ', כמו Desktop), עם `RadialLosCancelToken` לביטול לקוח (נבדק בין batches) במקום `POST /los_radial/cancel` — אין שרת בכלל ב-Android, כמו LOS הרגיל.
- `map_state.dart` — כל השדות/המתודות המקבילות (`radialLosMode`, 10 פרמטרים, `toggleRadialLosMode`/`setRadialLosObserver`/`updateRadialLosStartFromDrag`/`EndFromDrag` מבוססי `latlong2.Distance.bearing()`/`.offset()`, `runRadialLos`/`cancelRadialLos`/`clearRadialLosResult`). נוספה גם `updateRadialLosParam(void Function() mutate)` — מתודה גנרית אחת לעדכון שדה מתוך ה-UI (כי `notifyListeners()` מוגן/`@protected` ולא ניתן לקריאה ישירה מבחוץ).
- `map_screen.dart` — הכלי מיוצג ע"י כפתור-אייקון עצמאי צף (`_RadialLosPanel`, 📡/`Icons.radar`), **לא** בסרגל הכלים העליון (שם כבר 5 כפתורים בשורה אחת ללא מקום). רק בלחיצה עליו נפתח פאנל 10 השדות + הבחירה על המפה — תואם לבקשת המשתמש המפורשת ("נתאים את הכלי... ייצג את הכלי על ידי אייקון לבחירה ורק לאחר בחירתו ייפתח חלון הפרמטרים"). ממוקם `top:150, right:12` (עצמאי — לא בעמודות התחתית הקיימות) כדי לא להתנגש עם מחוון הטעינה/שגיאת LOS (`top:100-110`) או האזור התחתון.
- אומת: `flutter analyze` נקי לכל הקבצים שנגעו בהם (רק אזהרות קדם-קיימות לא-קשורות, למשל `api_service.dart:320` בקוד מעקב טיסות). נמצא ותוקן תוך כדי: `StrokePattern.dashed(...)` לא ניתן כ-`const` (הבנאי ניגש ל-`segments.length`) — הוסר ה-`const`.
- **הושלם ואומת**: `flutter build apk --release` הצליח (65.1MB) — הכלי כלול ב-APK הנוכחי, לרבות ה-UI המלא (`_RadialLosPanel`).

**אם המשתמש מבקש להמשיך**: קרא את קובץ התוכנית המלא (כולל הסעיף "תקלה שנמצאה" בסופו) לפני שינוי כלשהו באלגוריתם — יש שם ניתוח מלא של כל תקלה + הנוסחאות המדויקות.

---

### 🎯 תצפית מכ"ם דופלר (רעיוני/חינוכי) — כלי שלישי, מומש (19-20/08/2026, Desktop בלבד)

זהו המימוש בפועל של הדיון המושגי "האם להגדיר את הצופה כמכ"ם דופלר" שעלה בזמן תכנון רדיוס-הראייה (למעלה) — המשתמש ביקש במפורש רשימת פרמטרים ("תן לי רשימת פרמטרים עיקריים הנדרשים לך ע"י המשתמש"), אושרה תוכנית ב-plan mode (מסגור רעיוני/חינוכי, היקף מלא כולל lobing, Desktop בלבד), ומומש באותה שיחה.

**מה זה**: אותו רעיון בסיסי כמו רדיוס-ראייה (משקיף אחד, כל האזימוטים, פוליגון גבול-ראייה יחיד), עם **3 שכבות פיזיקה חדשות** מעל חסימת שטח בלבד:
1. **משוואת מכ"ם** — קובעת טווח גילוי מקסימלי לפי הספק/רווח/RCS/תדר/רגישות מקלט, לא רק גיאומטריה.
2. **דופלר** — מהירויות עיוורות (`v_blind=n·λ·PRF/2`) ו-MDV; **תלוי-אזימוט בלבד** (קבוע לאורך כל קרן, לא תלוי-מרחק) — לפי המהירות הרדיאלית שנגזרת ממהירות+כיוון תנועה משוערים של המטרה בכל זווית.
3. **תפוצה (lobing)** — השתקפות מהקרקע יוצרת "חורים" בכיסוי לפי זווית עילוי, תלוי-נקודה (לא ערך גלובלי).

**ארכיטקטורה (`weather_server.py`, לא קובץ/שרת נפרד)**: אותו דפוס job+polling+ביטול בדיוק כמו רדיוס-הראייה — `/radar_doppler/start`/`/status`/`/cancel`, `_radar_jobs`/`_radar_jobs_lock` נפרד לגמרי מ-`_radial_jobs` (יכולים לרוץ בו-זמנית). משתמש חוזר מלא ב-`_horizon_ratchet`/`_destination_point`/`_fetch_elevations` ובקבועי הדגימה הגנריים (`_RADIAL_BASE_BUDGET`/`_RADIAL_SAMPLES_MIN/MAX`/`_RADIAL_BATCH_SIZE` וכו') — **לא כפולים**, רק ברירות מחדל שונות (טווח 50 ק"מ, שדה-ראייה אנכי 10°, טווח מינימלי 1 ק"מ).

**פונקציות פיזיקה חדשות**:
- `_radar_max_range_m(power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm)` — `R=[(Pt·G²·λ²·σ)/((4π)³·Pmin·L)]^(1/4)`, הפסדי מערכת קבועים ב-6dB.
- `_lobing_factor(elevation_angle_deg, h_antenna_m, wavelength_m, reflectivity)` — מודל two-ray, `F=|1+ρ·e^(iΔφ)|`, `Δφ=4π·h_antenna·sin(θ)/λ`. מוכפל ישירות בטווח (לא ב-F⁴, כי הספק דו-כיווני משפיע כ-F⁴ על R^4, ולכן F על R).
- `_doppler_detectable(radial_speed_ms, mdv_ms, wavelength_m, prf_hz)` — False אם מתחת ל-MDV, או קרוב מדי (5%) לכפולה של מהירות עיוורת.
- `_max_unambiguous_range_m(prf_hz)` — `c/(2·PRF)`, תקרת טווח נוספת מ-PRF (לא Doppler ambiguity).

**19 פרמטרים** ב-4 קבוצות בפאנל אחד (גיאומטריה/משוואת מכ"ם/דופלר/תפוצה) — כולל dropdowns "סוג מטרה" (RCS: רחפן/מל"ט/מטוס קל/מטוס תובלה) ו"פס תדרים" (L/S/X) במקום קלט גולמי.

**סטייה מודעת מהתוכנית המקורית — חשוב לדעת לפני נגיעה בקוד**: התוכנית הציעה "מהירות רדיאלית משוערת" כשדה יחיד לפישוט. **הוחלף בזמן המימוש** במהירות+כיוון תנועה אמיתיים של המטרה (`target_speed_kt`+`target_heading_deg`), כי מהירות רדיאלית תלויה בזווית בין כיוון התנועה לאזימוט הקרן הנבדקת (`radial_speed=|v·cos(heading-bearing)|`) — עם שדה יחיד, כל הקרניים היו מקבלות תוצאת-דופלר זהה, בלי להדגים בכלל את אזור-העיוורון התלוי-כיוון (שזו בדיוק הסיבה לבנות כלי "דופלר" נפרד מכלי טווח-גילוי גנרי). **אומת נגד פיזיקה אמיתית**: מטרה הטסה צפונה (heading=0) גרמה בדיוק לשני האזימוטים הניצבים (90°/270°, מזרח/מערב — ניצבים לכיוון התנועה) להיחסם ע"י דופלר, ושאר האזימוטים לא — תואם בדיוק ל"אזור עיוורון" תיאורטי סביב מהירות רדיאלית אפס.

**תצוגה תלת-צבעונית** (לא דו-צבעונית כמו רדיוס-הראייה): ירוק=מזוהה, **כתום=כל הכיוון חסום דופלר** (גם אם השטח/טווח המכ"ם היו מאפשרים גילוי — קרן שלמה, לא נקודה בודדת, כי הדופלר תלוי-אזימוט בלבד), אדום=נחסם שטח או מעבר לטווח המכ"ם. צבע זיהוי ייחודי: ציאן `#22d3ee` (לא צהוב כמו רדיוס-הראייה, לא מג'נטה כמו CTR).

**Frontend/UI**: אותה זרימה בדיוק כמו רדיוס-הראייה (לחיצה=משקיף+תצוגה מקדימה, ידיות גרירה לזווית/טווח משותף, "הפעל חישוב" מפורש). כפתור 🎯 נפרד מ-📡, `main.py` מקבל 4 איתותי `document.title` ללוג בלבד (אין כפתור Qt).

**אומת**:
- `py_compile` על כל קובץ ששונה (`weather_server.py`/`MAP.py`/`main.py`/`test_requests.py`).
- רגנרציית `map.html`+render חי (QWebEngineView): 0 שגיאות קונסולה, gating נכון לפי `_mapReady`, סימולציית לחיצה+תצוגה מקדימה עובדת.
- הרצת job אמיתית מול Open-Meteo (טווח קטן, quota-conscious): טווח מכ"ם מחושב 39.87 ק"מ, טווח לא-חד-משמעי 149.9 ק"מ — שניהם תואמים חישוב ידני בדיוק. דפוס חסימת-הדופלר ("פרפר" ניצב לכיוון תנועת המטרה) תואם פיזיקה בדיוק (ר' למעלה).
- **תקלה בזמן הבדיקה (לא קשורה לקוד)**: הרצת שרת בדיקה נפרד ברקע תוך כדי שהמשתמש הריץ את `main.py`/`weather_server.py` שלו במקביל גרמה לתחרות משאבים ולבלבול — בנוסף, עריכת `weather_server.py` בזמן ש-session חי רץ (`debug=True`) גורמת ל-Werkzeug reloader להפיל ולהפעיל מחדש את השרת של המשתמש (תקלה מוכרת, מתועדת גם בתוכנית המקורית של הכלי). **לקח**: אל תריץ שרת בדיקה נפרד/תערוך שרתי Flask תוך כדי שהמשתמש עשוי להריץ session חי משלו — לוודא קודם.

**תוספות שבוצעו באותה שיחה, אחרי השאלה "כמה האלגוריתמיקה מתחשבת בPHASED ARRAY"**:
1. **סוג אנטנה — גנרי/מערך-מופעים**: dropdown חדש בפאנל; מערך-מופעים חושף כיוון-פנים (boresight)+זווית סריקה מקסימלית. `_scan_loss_factor`/`_angular_diff_deg` (`weather_server.py`) — מעבר לזווית הסריקה **אין כיסוי כלל** (0.0), בתוכה הפסד `√cos(זווית סטייה מ-boresight)` (שורש כי R∝G^0.5). קבוע לאורך כל קרן (כמו הדופלר). אומת חי: boresight=0/max_scan=60 חתך בדיוק ±60°.
2. **"עמדות שמורות"** (בעקבות בקשת המשתמש "לבחור אותו כיישות... לשמור מיקום לעמדה בכל אחד מהכלים... שאוכל לחזור אליה"): תשתית משותפת ל-3 הכלים (LOS/רדיוס-ראייה/מכ"ם-דופלר) — `/stations/list`/`save`/`delete` ב-`weather_server.py`, JSON שטוח (`saved_stations.json`), עד 20/כלי. Frontend: `_buildStationUI` אחת משותפת ב-`MAP.py` (לא 3 מימושים) — מקבלת `fieldMap` פר-כלי. **LOS שונה מבנית**: אין מיקום קבוע (זרימה מבוססת-קליק) — עמדה שומרת רק גבהי צופה/יעד. רדיוס-ראייה/מכ"ם-דופלר שומרים גם מיקום — טעינה קוראת ל-`_placeRadialLosObserver`/`_placeRadarObserver` (אותה פונקציה בדיוק שקליק על המפה קורא לה — מוצתה מהקוד הקיים, לא שוכפלה) + `map.panTo`. אומת קצה-לקצה בשלושת הכלים: לחיצה אמיתית על כפתור שמירה → אימות מול GET לשרת → ניקוי → לחיצה אמיתית על כפתור טעינה → שדות+מיקום משוחזרים.

**טרם נבדק**: לחיצה/הרצה בפועל ע"י המשתמש בממשק (רק render-test אוטומטי + endpoint tests, כולל render-test עם לחיצות DOM אמיתיות על כפתורי שמירה/טעינה — לא רק קריאת פונקציה). **Android טרם קיבל את הכלי (ואת שתי התוספות)** — המשתמש ביקש במפורש פורט מלא לאנדרואיד "עם הכלים החדשים לבדיקה" אחרי השלמת התוספות בדסקטופ; זה בניגוד לכלל הרגיל (לא מתחילים פורט לפני בשלות) אבל בבקשה מפורשת של המשתמש, כמו שקרה קודם עם רדיוס-הראייה.

**אם המשתמש מבקש להמשיך**: קרא את `MAPS-GUI_SRS.md` §3.11b וקבצי המקור (`weather_server.py` החל מ-`_radar_max_range_m`, `MAP.py` החל מ-`_radarMarkerIcon`) לפני שינוי כלשהו בפיזיקה.

---

---

### 🛩️ הערכת מסלול טיסה (FR24) מול מכ"ם-דופלר — כלי רביעי, מומש (24/08/2026, Desktop+Android) + עדכון גרסה ל-1.0.1

זהו חיבור בין כלי מעקב-הטיסות (FR24) לכלי מכ"ם-הדופלר (למעלה): במקום מטרה סינתטית עם מהירות/כיוון אחידים, **כל המסלול ההיסטורי של טיסה אמיתית** (עד 400 נקודות, גובה/מהירות/כיוון אמיתיים לכל נקודה) נבדק מול תצורת מכ"ם נתונה, נקודה-נקודה.

**Backend (`weather_server.py`)**: `POST /radar_doppler/evaluate_route/start` (POST כי ה-payload כולל מסלול שלם — לא query string) — reuse מלא של `/status`/`/cancel` הקיימים (`_radar_jobs` המשותף, לפי `job_id`). `_radar_route_eval_worker`: סינון-מוקדם `out_of_range` לפי מרחק בלבד, resample חמדני (יעד 2 ק"מ בין נקודות-הערכה, תקרה 100), `_horizon_ratchet` במצב יעד-יחיד (כמו `/los`, לא כמו סריקת-המגזר הרגילה), `_bearing_deg` חדש (לא היה קיים) לחישוב דופלר לפי כיוון תנועה אמיתי. 4 מצבים (לא 3): `detected`/`doppler_blind`/`blocked`/`out_of_range`. RCS נגזר אוטומטית מקוד ICAO של סוג כלי-הטיס (`_rcsForAircraftType`, טבלת קידומות) — **לא** מבוקש מהמשתמש. `flight_server.py::_normalize_trail_point` הורחב לשמר גם `hd` (כיוון, היה קיים בנתונים הגולמיים אך נזרק).

**Android**: פורט **on-device** מלא (`ApiService.fetchRouteEvaluation`, מקביל 1:1 ל-worker של Python, משתמש חוזר בכל הפיזיקה/batching הקיימים). `FlightData` הורחב עם `trail`+`aircraftIcao` **לצד** `path` הקיים. State עצמאי ב-`MapState` (`evaluateFlightRoute`/`routeEval*`). מקור OpenSky לא מספק מהירות/סוג-כלי-טיס פר-נקודה — RCS נופל לברירת מחדל.

**גרסה נסגרה ל-1.0.1** (`VERSION`+`kAppVersion`) בעקבות השלמת הפורט. ר' `MAPS-GUI_SRS.md` FR-D-115/116/195-206.

---

### 🐛 תיקוני באגים משמעותיים אחרי המעבר ל-1.0.1 (24-25/08/2026)

1. **FR24 403 Forbidden (Desktop, 24/08)**: `fr_api.get_flight_details()` נחסם ע"י Cloudflare/זיהוי-בוטים (**לא** בעיית טוקן — הפונקציה לא שולחת שום auth מלכתחילה, אומת בקוד המקור של הספרייה). תוקן: `_fetch_flight_details_direct()` חדש דרך `curl_cffi` (`impersonate="chrome"`), עם fallback לספרייה המקורית. תלות חדשה: `curl_cffi`.
2. **מיקום שגוי לגמרי בטיסות (Android, `_fetchOpenSky`, 24/08)**: OpenSky לא מסנן בפועל לפי `callsign` (מחזיר את כל טיסות העולם) — הסינון כולו בצד הלקוח, ותנאי ההתאמה `callsign.contains(cs)` היה `true` תמיד כש-`cs` ריק (~2.4% מהטיסות) → כלי-הטיס הראשון-ברשימה-בלי-callsign (מיקום אקראי) נבחר בטעות. תוקן: `if (cs.length < 3) continue;`. ר' FR-D-207.
3. **מכ"ם-דופלר לא השתמש במיקום עצמי שכבר אותר (Android, `MapState`, 25/08)**: לחיצה על "מיקום עצמי" (GPS) ואז הפעלת מכ"ם-דופלר גרמה לכלי להמתין ללחיצה חדשה, כי `lastPinnedPoint` (המשותף לכל הסיכות) נצרך/מתאפס מיד בפריים הבא (קפיצת מצלמה) — לפני שהמשתמש הגיע לפאנל הכלי. תוקן: שדה נפרד `lastSelfLocation` (לא נצרך אוטומטית) + `toggleRadarMode()` משתמש בו כמשקיף אוטומטית אם אין עדיין משקיף. מכוון למכ"ם-דופלר בלבד (לפי הדיווח הספציפי) — לא הורחב לרדיוס-ראייה/LOS. ר' FR-D-208.

כל השלושה אומתו (`py_compile`/`flutter analyze`/render/API חי לפי הרלוונטי) ותועדו ב-SRS+README. APK נבנה מחדש עם שני התיקונים האחרונים (2-3).

**קובץ נוסף שנוצר (25/08/2026)**: `מדריך-הפעלה-Android.md` — מדריך תפעולי למשתמש-קצה (לא טכני) לאפליקציית האנדרואיד, מחליף/מעדכן את ה-PDF הישן (`מדריך-הפעלה-Android.pdf`, מיושן מ-12/08). ה-PDF נשאר בריפו כארכיון היסטורי בלבד — **מקור האמת מעכשיו הוא ה-md**.

**"הגדרות שמורות" — פריסטים בלי מיקום (25/08/2026, Desktop+Android, רדיוס-ראייה+מכ"ם-דופלר בלבד)**: תכונה נפרדת מ"עמדות שמורות" הקיים — שומרת/טוענת/מוחקת פרמטרים בלי לגעת במיקום. Desktop: שני מפתחות-כלי חדשים (`radial_los_settings`/`radar_doppler_settings`) ב-`_STATIONS_VALID_TOOLS` (`weather_server.py`) — האנדפוינטים הגנריים לא השתנו. `_buildStationUI` ב-`MAP.py` נקרא פעמיים לכל כלי (עם/בלי `getObsFn`). Android: `_paramsFromState(includePosition:)` + מתודות/UI מקבילים חדשים בכל פאנל, ה-storage הגנרי (`loadStations`/`saveStation`/`deleteStation`) לא השתנה. ר' `MAPS-GUI_SRS.md` FR-D-209.

---

### 🌐 גרסת Web — פלטפורמה שלישית, שלב 1 (24-25/10/2026, Vercel + map.yechielalaluf.com)

בעבודה כעת: פריסה ציבורית תחת `map.yechielalaluf.com` (GoDaddy→Vercel, GitHub מחובר). תוכנית מלאה ב-`C:\Users\allof\.claude\plans\compiled-gliding-wren.md`. **החלטה מרכזית**: שימוש-חוזר ב-`MAP.py`/Leaflet הקיים (לא Flutter Web — ראה שם לנימוקים: FR24-scraping לא עובד מדפדפן, UI Android מגע-קודם לא מתאים לדסקטופ-web).

כל קוד ה-web מבודד תחת `web/` חדש (`web/api/{geo,flight,weather}.py`, `web/lib/*`, `vercel.json`, `build_web.py`) — **Desktop/Android לא נגעו בכלל**, אומת (`git diff`). `MAP.py::create_map()` קיבל `target`/`api_base`/`output_path` אופציונליים (ברירת-מחדל = התנהגות ישנה בדיוק) — `target='web'` מוסיף 6 בקרות UI חדשות (NOTAM/heatmap-mode/חיפוש-עיר/טיסה/GPS — ממירות widgets שהיום הם Qt-בלבד) + CSS רספונסיבי למובייל.

**מגבלת-שלב-1 מכוונת, לא באג**: job-polling (רדיוס-ראייה/מכ"ם-דופלר) ו"עמדות שמורות" לא אמינים על Vercel serverless עדיין (state-בזיכרון לא מובטח בין invocations; `_STATIONS_FILE`→`/tmp` כש-`VERCEL=1`, מונע קריסה אך לא מתמיד). שלב 2 (עתידי) יחליף ב-Redis (Upstash) + תבנית chunked-per-request. **אושר עם המשתמש**: רשימת עמדות-שמורות נשארת משותפת-לכולם (בלי auth/בידוד per-browser), Vercel Hobby (לא Pro) לשלב ראשון.

נבדק: `py_compile` על כל קובצי web/; `git diff map.html` (ברירת-מחדל desktop) = 3 שורות ריקות בלבד; render חי (QWebEngineView) של `target='web'` — 0 שגיאות JS; הרצה מקומית אמיתית של שלושת `web/api/*.py` — כולן 200 עם תגובות אמיתיות (כולל FR24_TOKEN ו-OpenWeather). **טרם בוצע**: הקמת הפרויקט ב-Vercel בפועל, Upstash, DNS ב-GoDaddy — אלה דורשים גישת-חשבון שאין לי.

ר' `MAPS-GUI_SRS.md` §3.24 (FR-D-216 עד FR-D-220) לפירוט המלא.

---

### 🧭 מסלול טיסה מותאם — כלי חמישי, מומש (28/09/2026, Desktop+Android)

כלי חדש: המשתמש מזין רשימת נקודות (טקסט חופשי/הדבקה/קליק על המפה) ומקבל מסלול **סגור** מצויר, סמן ממוספר לכל נקודה. אין חישוב פיזיקלי, אין תלות בשרת לציור עצמו — שמירה/טעינה משתמשות ב-`/stations` הגנרי הקיים (`tool='custom_route'`, כמו FR-D-209). Desktop: `MAP.py::CustomRouteControl` (טופס Leaflet חדש, `#14B8A6`). Android: `_CustomRoutePanel`/`RoutePoint`/`ApiService.parseCoordLine` (פורט Dart עצמאי).

**פרסר קואורדינטות** תומך ב-3 פורמטים (DDM דחוס / מעלות עשרוניות עם אות-כיוון / DMS עם סמלים) + גובה אופציונלי בסוף השורה. **regex יחיד בכל הכלי, בכוונה בלי אף backslash** (`[0-9]` במקום `\d` וכו') — נמנע מסיכון ה-escaping הכפול בתוך ה-f-string של `MAP.py` (אזהרה קיימת בקובץ זה, סעיף Desktop למעלה — **קרה בפועל תוך כדי הבנייה**: `\'` בפייתון קרס ל-`'` בפלט, שבר מחרוזת JS; `\d` הפיק SyntaxWarning — שניהם תוקנו, ר' לקח למטה).

**3 תיקונים נמצאו ותוקנו בבדיקה חיה של המשתמש עם קואורדינטות אמיתיות (לא בבדיקות סינתטיות שלי):**
1. פורמט "אות-כיוון + מעלות עשרוניות" (`N35.19`) היה חסר — הפרסר תמך רק בפורמט הדחוס (`N3127.551`).
2. תווית/מזהה-נקודה מובילה בשורה (`C N35.19 E29.61`) לא נתמכה — קבצי תכנון-מסלול אמיתיים כוללים תוויות כאלה. תוקן: אם השורה המלאה נכשלת, מנוסה שוב בלי הטוקן הראשון.
3. **ברירת המחדל לזוג עשרוני עמום (בלי אות-כיוון) היא קו-אורך-ואז-קו-רוחב, לא ההפך** — הוחלט תחילה (לפי תשובה מילולית של המשתמש בשיחה) על "קו-רוחב קודם", והתברר **שגוי** רק כשהמשתמש בדק מול מיקום אמיתי מוכר (אזור אילת/עקבה — "קו-רוחב קודם" מיקם בים התיכון). **לקח: לשאלות lat/lon-order אל תסתפק בתשובה מילולית מופשטת — תמיד תבקש/תבדוק דוגמה עם מיקום גיאוגרפי מוכר בפועל.**

גם תוקן: מיקוד-מפה אוטומטי (`fitBounds`) אחרי הוספה מרובה/טעינה — מסלול רחוק מהתצוגה הנוכחית "נעלם" בשקט (המשתמש דיווח "המסלול לא מוצג" כשבפועל הוא צויר, רק מחוץ למסך).

**החלטת-עיצוב מפורשת שאושרה עם המשתמש**: הכלי **לא** ממיין נקודות אוטומטית למניעת צורה חוצה-את-עצמה — תמיד מחבר לפי סדר הקלט בלבד, גם אם יוצא "פרפר". Android נבנה **ללא** כפתור "טען מקובץ" (Desktop כן) — הוחלט במכוון לא להוסיף תלות `file_picker` חדשה ל-Android; הדבקה רגילה מהלוח עונה על אותו צורך.

ר' `MAPS-GUI_SRS.md` §3.23 (FR-D-210 עד FR-D-215) לפרטים המלאים, כולל תיעוד מלא של כל מקרי הבדיקה.

---

*כעת תאר מה אתה רוצה לעשות/לשנות/לתקן בפרויקט.*

## ════════════════════════════════════════
