# דוח מיפוי Stage 0 — maps-gui, פלטפורמת Android (Flutter + Chaquopy)
קוד-אמת: `D:\PY-IS\maps-gui\maps-gui-android-src\` (לא נערך דבר — משימת קריאה בלבד, כולל הרצת `flutter analyze` שאומת כקריאה-בלבד).

---

## 1. טכנולוגיות

| רכיב | גרסה | מקור |
|---|---|---|
| Flutter SDK | **3.41.9-stable** (Windows) | `build_apk.ps1` |
| Dart SDK constraint | `>=3.3.0 <4.0.0` | `pubspec.yaml` |
| Flutter constraint | `>=3.19.0` | `pubspec.yaml` |
| Gradle | **9.5.1** | `android_gradle-wrapper.properties` |
| AGP | **8.11.1** | `android_settings.gradle.kts` |
| Kotlin | **2.2.20** | `android_settings.gradle.kts` |
| Chaquopy | **17.2.0** | `android_settings.gradle.kts` |
| Python (Chaquopy) | **3.14** (buildPython → `.venv`, 3.14.6) | `android_app_build.gradle.kts` |
| compileSdk/NDK | android-35, build-tools 35.0.0 | `build_apk.ps1` Step 5 |
| minSdk | **24** (max(flutter.minSdk, 24) — Chaquopy מחייב ≥24) | עם הערה מפורשת בקוד |
| ABI | **רק** arm64-v8a, x86_64 — 32-ביט לא נתמך | `android_app_build.gradle.kts` |
| Java/Kotlin JVM target | 17 | |
| applicationId | `com.mapsapp.maps_gui_android` (TODO-template לא טופל: "Specify your own unique Application ID") | |
| Signing | **release חתום במפתח debug** (TODO לא טופל) | |

### חבילות pub עיקריות
| חבילה | yaml | lock | תפקיד |
|---|---|---|---|
| flutter_map | ^7.0.2 | 7.0.2 | רינדור מפה |
| latlong2 | ^0.9.1 | 0.9.1 | חישובי LatLng |
| http | ^1.2.1 | 1.6.0 | HTTP ל-APIs חיצוניים |
| provider | ^6.1.2 | 6.1.5+1 | ChangeNotifier state |
| material_symbols_icons | ^4.2719.3 | 4.2960.0 | אייקונים (אולי unused) |
| geolocator | ^13.0.4 | 13.0.4 (+geolocator_android 4.6.2) | GPS |
| shared_preferences | ^2.2.2 | 2.5.5 (+shared_preferences_android 2.4.23) | אחסון מקומי לא-מוצפן |
| flutter_lints (dev) | ^3.0.2 | 3.0.2 | lint |

---

## 2. נקודות כניסה

- **`lib/main.dart`**: `main()`→`runApp(ChangeNotifierProvider<MapState>→MapsApp→MapScreen)`. locale `he_IL`, `themeMode: dark` קבוע.
- **Activity יחיד**: `MainActivity.kt` (`FlutterActivity`), `singleTop`, `exported=true`, MAIN/LAUNCHER בלבד — **אין deep links נכנסים**.
- **MethodChannel יחיד**: `com.mapsapp.maps_gui_android/mpm`, `dispatch(action, paramsJson)`→`mpm_api.dispatch_json`. אין whitelist בצד Kotlin ל-action.
- **אין background work/Timers/WorkManager/Foreground Service/BOOT_COMPLETED** (grep שלילי).
- **Screens**: מסך יחיד (`MapScreen`) + Bottom Sheets מודאליים + פאנלים צפים — אין Navigator עם routes.

---

## 3. מפת תהליכים

| תהליך | טריגר | קלט | מסלול בקוד | פלט |
|---|---|---|---|---|
| NOTAM toggle (7 קטגוריות) | checkbox ב-`LayersPanel` | — | `toggleNotamCategory`→`fetchUasNotamZones()`→GET `brin.iaa.gov.il`→regex parse→`classifyNotam` | פוליגונים/מעגלים + Undo; cache בזיכרון |
| שכבת גבהים/טמפרטורה | כפתור+בחירת-אזור | selectionStart/End | `loadElevation/loadTemperature`→`fetchElevationGrid/fetchTemperatureGrid`→batched GET open-meteo | `renderHeatImage` (PNG בזיכרון)→OverlayImageLayer |
| רדיוס-ראייה רדיאלי | `_RadialLosPanel`, קליק=משקיף | 10 פרמ' | `setRadialLosObserver/runRadialLos`→`fetchRadialLos` (`_horizonRatchet`, batching 30/req, 500ms delay, cancel token) | פוליגון+חישורים; Undo; עמדות שמורות |
| מכ"ם-דופלר+אנטנה | `_RadarDopplerPanel` | ~22 פרמ' כולל antennaType/boresight/maxScan | `setRadarObserver/runRadarDoppler`→`fetchRadarDoppler` (`_radarMaxRangeM`/`_lobingFactor`/`_dopplerDetectable`/`_scanLossFactor`) | פוליגון תלת-צבעוני; לחיצה→`_RadarProfilePanel` |
| הערכת מסלול-טיסה מול מכ"ם | כפתור `evaluateFlightRoute` | flightData.trail+תצורת מכ"ם | `rcsForAircraftType`→`fetchRouteEvaluation` (resample+per-point ratchet/דופלר) | קטעי-קו צבועים; bottom sheet פרטים |
| GPS/מיקום-עצמי | כפתור ב-`LocationPanel` | הרשאת מיקום | `goToMyLocation`→`Geolocator...getCurrentPosition(high)` | pin+מצלמה; `lastSelfLocation` למשקיף-מכ"ם |
| עמדות שמורות | שמירה/טעינה/מחיקה ×3 כלים | שם+פרמטרים | `saveStation/loadStations/deleteStation`→SharedPreferences `'${toolKey}_stations'` | אחסון קבוע, תקרה 20/toolKey |
| Undo/Redo | כפתורי חץ | — | `pushUndo/performUndo/performRedo` (מחסנית גנרית, `_undoMax=50`, דגל `_isRestoringUndo`) | NOTAM/CTR/UAS-coord toggles, מיקום משקיף, caches-תוצאה |
| מסלול בליסטי (MPM) | `BallisticsPanel`, 5 טאבים | תותח/מטרה **ידני בלבד**, מטאו, mv, fD/fL | `MpmBridge.call`→MethodChannel→Kotlin→Chaquopy→`mpm_api.dispatch_json` — **רק 3 actions בשימוש**: trajectory/solve/table (לא solve_mv/calibrate/terrain_check/min_qe_for_crest) | טקסט תוצאה; **אין** הצגת-מסלול-על-מפה (`include_path:false` קבוע) |

---

## 4. משטח תקיפה

**הרשאות (`android_manifest.xml`)**: INTERNET, ACCESS_NETWORK_STATE, ACCESS_FINE/COARSE_LOCATION. `android:usesCleartextTraffic="true"` — **מתיר HTTP גלובלית**, אין network_security_config/certificate pinning.

**HTTP ישיר מה-client ל-APIs חיצוניים (ב-`ApiService`, בלי שרת-ביניים):**
| שירות | פרוטוקול | הערה |
|---|---|---|
| api.open-meteo.com | HTTPS | ללא מפתח, batched |
| nominatim.openstreetmap.org | HTTPS | User-Agent חובה |
| opensky-network.org | HTTPS | ללא אימות |
| data.flightradar24.com | HTTPS | **טוקן "Gold" קשיח בקוד** (`api_service.dart:193`, `_fr24Token='qJOskJ9Njh...'`) — **חשוף בתוך ה-APK**, ללא obfuscation — ממצא מרכזי |
| brin.iaa.gov.il | HTTPS | User-Agent מזויף; regex שביר |
| `http://$flightServerHost:5004` | **HTTP cleartext** | `flightServerHost` **לעולם לא מאותחל** (אין מסך הגדרות ב-Android) — קוד מת בפועל |

**MethodChannel**: `paramsJson` הוא JSON חופשי, Kotlin לא מאמת תוכן (רק שם המתודה). וקטור-הזרקה תיאורטי תלוי בוולידציה של `mpm_api.py` (מחוץ לתחום — סוכן אחר). שגיאות Python נתפסות ל-JSON-שגיאה, לא קורסות.

**קלט חופשי בלי שרת-ביניים**: LAT/LON (מאומת טווח בצד-לקוח בלבד), מסלול-מותאם (`parseCoordLine`, 3 פורמטים, שורות-לא-תקינות מדולגות בשקט), שם-עמדה-לשמירה (לא נוקה לפני jsonEncode, סיכון נמוך), callsign (מוגבל `[A-Za-z0-9]`).

---

## 5. מלאי רכיבי UI (עיקריים)

AppBar צף (5 כפתורים), BottomAppBar (שכבות/מיקום/טיסות), תג-גרסה (V1.0.2), Undo/Redo, `_RadialLosPanel`, `_RadarDopplerPanel`, `_CustomRoutePanel`, `BallisticsPanel`, `_LosProfilePanel`/`_RadarProfilePanel` (גרפים CustomPainter), `_VlosInfoButton`, `_ScaleBar`, `_WeatherCard`/`_ElevationCard`/`_RulerCard`, `_UasNotamLegend`/`_UasCoordLegend`.

**הערה**: אין `Semantics`/accessibility label מפורש בשום מקום (grep שלילי) — נגישות מסתמכת רק על `tooltip:` חלקי.

---

## 6. תמיכה במובייל/נגישות

- אוריינטציה: portrait+landscape, נעולה. `configChanges` מטפל ב-fontScale/density/uiMode/locale בלי restart.
- **Dark mode קבוע קשיח** — אין מתג משתמש, אין קריאה ל-`MediaQuery.platformBrightness`.
- **אין טיפול ב-`textScaler`/`textScaleFactor`** — טקסטים קשיחים (9-16px, כולל שדות קריטיים 9-11px) — **לא עומד ב-WCAG להגדלת-טקסט דינמית**.
- Split-screen: לא מוגדר מפורש (ברירת-מחדל Android) — לא נבדק בפועל.
- **Touch targets קטנים**: `VisualDensity.compact`+`BoxConstraints()` מבטל מינימום 48dp — iconSize 19-21, ידיות-גרירה 16-20px — **קטן מהמלצת WCAG/Material**.
- RTL: `Directionality` עקבי; שדות LAT/LON עטופים LTR (נכון למספרים).
- אין בדיקות אוטומטיות לנגישות (אין golden/semantics tests).

---

## 7. מלאי צד-שלישי

| חבילה | רישיון (כללי, לא אומת מול LICENSE) | שימוש |
|---|---|---|
| flutter_map 7.0.2 | BSD-3-Clause | מפה; tiles: OSM/ESRI/CartoDB Dark, נבחר ע"י משתמש |
| latlong2 0.9.1 | BSD-3-Clause/MIT | Vincenty ellipsoidal |
| http 1.6.0 | BSD-3-Clause | HTTP |
| provider 6.1.5+1 | MIT | state |
| geolocator 13.0.4+geolocator_android 4.6.2 | MIT/BSD | GPS |
| shared_preferences 2.5.5+android 2.4.23 | BSD-3-Clause | אחסון — **ללא הצפנה** (XML רגיל, לא EncryptedSharedPreferences) |
| material_symbols_icons 4.2960.0 | MIT | אייקונים (אולי unused) |
| Chaquopy 17.2.0 (Gradle plugin) | **מסחרי/dual-license** | מריץ Python ב-APK |

שירותי tiles/geo חיצוניים נוספים (HTTP ישיר, לא pub): Nominatim, Open-Meteo, OpenSky, FlightRadar24 (לא-רשמי, טוקן קשיח), brin.iaa.gov.il.

---

## 8. מלאי מידע אישי

| סוג מידע | מקור | נשמר ב- | משך |
|---|---|---|---|
| GPS נוכחי | `Geolocator.getCurrentPosition` | בזיכרון בלבד (`lastSelfLocation`/`pinnedPoints`) | עד resetMap/סגירה |
| עמדות שמורות (lat/lon+פרמטרים) | משתמש/GPS | **SharedPreferences** (`radial_los_stations`/`radar_doppler_stations`) — JSON לא-מוצפן | **קבוע עד מחיקה מפורשת**, תקרה 20/toolKey |
| מסלול-מותאם שמור | משתמש | `SharedPreferences` (`custom_route_stations`) | קבוע עד מחיקה |
| היסטוריית חיפוש עיר/טיסה | משתמש | `SharedPreferences` (`city_search_history`/`flight_history`) | קבוע, תקרה 10 (FIFO) |
| סיכות (`pinnedPoints`) | קליק/GPS | בזיכרון בלבד | נמחק ב-resetMap |

כל הנתונים באחסון פרטי של האפליקציה בלבד (SharedPreferences = XML ב-`shared_prefs`) — לא cloud. **אין הצפנה** — חשוף ל-`adb backup`/root/גיבוי-מכשיר לא-מוצפן.

---

## 9. שמירה ופורמטים

מפתחות SharedPreferences: `city_search_history`, `flight_history` (List\<String\>), `radial_los_stations`/`radial_los_settings_stations` (jsonEncode עם/בלי lat/lon), `radar_doppler_stations`/`radar_doppler_settings_stations` (+~12 שדות מכ"ם/אנטנה), `custom_route_stations` (points[{lat,lng,alt}]).

**אין קבצים מקומיים אחרים** (אין `path_provider`/`File`/`dart:io` ישיר ל-lib/). `kAppVersion` מסונכרן **ידנית** מ-VERSION (לא נקרא ב-runtime מה-APK).

---

## 10. תזמון/רקע/אינטגרציה

**אין** WorkManager/Foreground Service/BOOT_COMPLETED/AlarmManager (grep שלילי מלא). **אין** אינטגרציה עם אפליקציות חיצוניות בפועל (queries ל-ACTION_VIEW קיים ב-manifest אך לא בשימוש בקוד — remnant מ-scaffold). FlightServer מקומי (desktop) — נקודת-אינטגרציה מתוכננת שלא ניתנת-להגדרה בפועל כרגע (קוד מת).

---

## 11. הרצה/בדיקות קיימות

**`flutter analyze` הורץ בהצלחה** (לא נבנה APK, אומת ללא שינוי קבצים): **13 ממצאים, כולם warnings/info** (0 errors) — `unused_local_variable`, 2×`unnecessary_non_null_assertion`, `unnecessary_import`, 8×`deprecated_member_use` (Color.red/green/blue/alpha ב-heat_image.dart — API ישן; DropdownButtonFormField.value).

**`test/` לא קיים בכלל** — **אין unit/widget tests לאנדרואיד** (רק flutter_test/flutter_lints כ-dev deps סטנדרטיים מה-scaffold).

---

## 12. Scope-reduction מתועד + ממצאים מרכזיים

**Scope-reduction מכוון (החלטת-מוצר, לא תקלה):**
1. BallisticsPanel v1: תותח/מטרה ידני בלבד (לא קליק-מפה); כיול לא ממומש; 4/7 actions לא בשימוש (solve_mv/calibrate/terrain_check/min_qe_for_crest); `include_path:false` קבוע; טבלה כטקסט; לא מחובר ל-MapState/Undo-Redo.
2. `flightServerHost` מתועד "set via settings" אך אין מסך הגדרות — קוד מת.
3. LOS הרגיל לא נכלל ב"עמדות שמורות" — החלטת-עיצוב מכוונת (גבהים קבועים בקוד).

**לא נבדק (דורש סביבת-הרצה מלאה)**: בניית APK/הרצה על מכשיר-אמיתי (לא התבקש); תקינות-ריצה בפועל של Chaquopy bridge (נבדק סטטית בלבד; mpm_api.py/mpm/ עצמם מחוץ לתחום); split-screen/font-scale-קיצוני/TalkBack בפועל; Signing — לא נמצא key.properties/keystore ייעודי, עדיין debug-signed לפי הקוד.

**ממצאים מרכזיים לדגל (מפורט בסעיף 4):**
- טוקן FlightRadar24 "Gold" קשיח בקוד, חשוף בתוך ה-APK.
- `usesCleartextTraffic="true"` גלובלי + אין network security config/pinning.
- SharedPreferences לא-מוצפן למיקום אישי/עמדות שמורות.
- Release build חתום במפתח debug (TODO לא טופל).
- Touch targets <48dp, אין text-scale דינמי, אין Semantics מפורש — פערי WCAG/MASVS-נגישות.
