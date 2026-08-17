import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart'; // נדרש עבור Color בפלטת צבעי LOS
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/grid_point.dart';
import '../models/los_session.dart'; // מודל סשן קו ראייה
import '../models/uas_notam_zone.dart'; // מודל אזור NOTAM לרחפנים
import '../services/api_service.dart'; // גם geocodeCity() -> CityResult, בשימוש מוסק (inferred) ללא ייבוא ישיר
import '../utils/heat_image.dart';

// Flight state
class FlightData {
  final List<LatLng> path;
  final LatLng? current;
  final String callsign;
  final String info;
  const FlightData({required this.path, required this.current, required this.callsign, this.info = ''});
}

enum DisplayMode { heat, grid, dots }
enum LayerType { none, elevation, temperature }

class MapState extends ChangeNotifier {
  MapState() { _loadHistory(); }

  static const int _maxHistoryItems = 10; // תואם למגבלת ההיסטוריה בגרסת הדסקטופ

  List<String> citySearchHistory = [];
  List<String> flightHistory = [];

  // טעינת היסטוריית חיפושים שנשמרה מהפעלות קודמות (SharedPreferences — מקביל ל-QSettings בדסקטופ)
  Future<void> _loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    citySearchHistory = prefs.getStringList('city_search_history') ?? [];
    flightHistory = prefs.getStringList('flight_history') ?? [];
    notifyListeners();
  }

  Future<void> _pushHistory(String key, List<String> list, String value) async {
    list.remove(value);
    list.insert(0, value);
    if (list.length > _maxHistoryItems) list.removeRange(_maxHistoryItems, list.length);
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(key, list);
  }

  LatLng? selectionStart;
  LatLng? selectionEnd;

  List<GridPoint> elevPoints = [];
  Uint8List? elevHeatBytes;
  DisplayMode elevMode = DisplayMode.heat;
  bool elevLoading = false;
  String? elevError;

  List<GridPoint> tempPoints = [];
  Uint8List? tempHeatBytes;
  DisplayMode tempMode = DisplayMode.heat;
  bool tempLoading = false;
  String? tempError;

  LayerType activeLayer = LayerType.none;

  // Pinned markers
  List<LatLng> pinnedPoints = [];
  LatLng? lastPinnedPoint;

  void pinCoordinate(double lat, double lon) {
    final p = LatLng(lat, lon);
    pinnedPoints = [...pinnedPoints, p];
    lastPinnedPoint = p;
    notifyListeners();
  }

  void clearPinnedPoints() {
    pinnedPoints = [];
    lastPinnedPoint = null;
    notifyListeners();
  }

  void consumeLastPinned() { lastPinnedPoint = null; }

  // Device location
  bool locationLoading = false;
  String? locationError;

  // מחזיר את הקואורדינטה שנמצאה (או null בכישלון) — כדי שהקורא (למשל שדות LAT/LON
  // בפאנל המיקום) יוכל להציג אותה ישירות, בלי תלות בטריגר lastPinnedPoint המשותף
  // (שגם דקירה ידנית מפעילה, ונצרך/מתאפס בנפרד ע"י map_screen.dart לצורך קפיצת מצלמה).
  Future<LatLng?> goToMyLocation() async {
    locationLoading = true; locationError = null; notifyListeners();
    LatLng? result; // הערך שיוחזר לקורא — נשאר null אם קרתה שגיאה
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) throw Exception('שירות המיקום כבוי במכשיר');
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
        if (perm == LocationPermission.denied) throw Exception('הרשאת מיקום נדחתה');
      }
      if (perm == LocationPermission.deniedForever) throw Exception('הרשאת מיקום חסומה — אפשר בהגדרות');
      final pos = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high));
      pinCoordinate(pos.latitude, pos.longitude); // מוסיף סיכה על המפה ומפעיל קפיצת מצלמה, כרגיל
      result = LatLng(pos.latitude, pos.longitude); // נשמר להחזרה — עותק עצמאי, לא מושפע מצריכת lastPinnedPoint
    } catch (e) {
      locationError = e.toString().replaceFirst('Exception: ', '');
    }
    locationLoading = false; notifyListeners();
    return result;
  }

  // Flight
  FlightData? flightData;
  bool flightLoading = false;
  String? flightError;
  LatLng? flightFocusPoint; // טריגר לקפיצת מפה — מתאפס לאחר צריכה

  Future<void> loadFlight(String callsign) async {
    flightLoading = true; flightError = null; notifyListeners();
    try {
      final result = await ApiService.fetchFlightTrack(callsign);
      flightData = FlightData(path: result.path, current: result.current, callsign: result.callsign, info: result.info);
      flightFocusPoint = result.current ?? (result.path.isNotEmpty ? result.path.last : null);
      unawaited(_pushHistory('flight_history', flightHistory, result.callsign));
      // נקודה בודדת = נמצא בפיד הרדאר אך אין מסלול זמין; מציגים מיקום + הסבר
      if (result.path.length == 1) flightError = 'מיקום נוכחי בלבד — אין מסלול זמין לטיסה $callsign';
    } catch (e) {
      flightError = e.toString().replaceFirst('Exception: ', '');
      flightData = null;
    }
    flightLoading = false; notifyListeners();
  }

  void consumeFlightFocus() { flightFocusPoint = null; }
  void clearFlight() { flightData = null; flightError = null; flightFocusPoint = null; notifyListeners(); }

  // ── חיפוש עיר ────────────────────────────────────────────────────────────
  bool citySearchLoading = false;
  String? citySearchError;
  LatLngBounds? cityBounds;   // תיבה מלבנית — לקפיצת מצלמה, ול-fallback אם אין גבול אמיתי
  List<List<LatLng>> cityBoundaryRings = []; // גבול העיר בפועל (OSM) — ריק אם לא זמין
  LatLng? cityFocusPoint;     // טריגר חד-פעמי לקפיצת מפה, מתאפס לאחר צריכה

  Future<void> searchCity(String name) async {
    if (name.trim().isEmpty) return;
    citySearchLoading = true; citySearchError = null; notifyListeners();
    try {
      final result = await ApiService.geocodeCity(name.trim());
      cityBounds = result.bounds;
      cityBoundaryRings = result.boundaryRings;
      cityFocusPoint = result.center;
      unawaited(_pushHistory('city_search_history', citySearchHistory, name.trim()));
    } catch (e) {
      citySearchError = e.toString().replaceFirst('Exception: ', '');
    }
    citySearchLoading = false; notifyListeners();
  }

  void consumeCityFocus() { cityFocusPoint = null; }
  void clearCitySearch() { cityBounds = null; cityBoundaryRings = []; citySearchError = null; notifyListeners(); }

  Map<String, dynamic>? weatherData;
  LatLng? weatherPoint;
  bool weatherLoading = false;

  String tileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  String tileAttribution = '© OpenStreetMap contributors';

  void setTileLayer({required String url, required String attribution}) {
    tileUrl = url; tileAttribution = attribution; notifyListeners();
  }

  void startSelection(LatLng point) { selectionStart = point; selectionEnd = null; notifyListeners(); }
  void updateSelection(LatLng point) { selectionEnd = point; notifyListeners(); }
  void clearSelection() { selectionStart = null; selectionEnd = null; notifyListeners(); }

  void resetForNewSelection() {
    selectionStart = null; selectionEnd = null;
    elevPoints = []; elevHeatBytes = null; elevError = null;
    tempPoints = []; tempHeatBytes = null; tempError = null;
    activeLayer = LayerType.none;
    notifyListeners();
  }

  LatLngBounds? get selectionBounds {
    if (selectionStart == null || selectionEnd == null) return null;
    return LatLngBounds(
      LatLng(selectionStart!.latitude < selectionEnd!.latitude ? selectionStart!.latitude : selectionEnd!.latitude,
             selectionStart!.longitude < selectionEnd!.longitude ? selectionStart!.longitude : selectionEnd!.longitude),
      LatLng(selectionStart!.latitude > selectionEnd!.latitude ? selectionStart!.latitude : selectionEnd!.latitude,
             selectionStart!.longitude > selectionEnd!.longitude ? selectionStart!.longitude : selectionEnd!.longitude),
    );
  }

  Future<void> loadElevation() async {
    final bounds = selectionBounds;
    if (bounds == null) return;
    if (elevPoints.isNotEmpty) {
      activeLayer = LayerType.elevation;
      notifyListeners();
      return;
    }
    elevLoading = true; elevError = null; notifyListeners();
    try {
      elevPoints = await ApiService.fetchElevationGrid(
        swLat: bounds.south, swLon: bounds.west, neLat: bounds.north, neLon: bounds.east,
      );
      elevHeatBytes = await renderHeatImage(elevPoints);
      activeLayer = LayerType.elevation;
    } catch (e) { elevError = e.toString(); }
    finally { elevLoading = false; notifyListeners(); }
  }

  void setElevMode(DisplayMode mode) { elevMode = mode; notifyListeners(); }
  void clearElevation() { elevPoints = []; elevHeatBytes = null; elevError = null; if (activeLayer == LayerType.elevation) activeLayer = LayerType.none; notifyListeners(); }

  Future<void> loadTemperature() async {
    final bounds = selectionBounds;
    if (bounds == null) return;
    if (tempPoints.isNotEmpty) {
      activeLayer = LayerType.temperature;
      notifyListeners();
      return;
    }
    tempLoading = true; tempError = null; notifyListeners();
    try {
      tempPoints = await ApiService.fetchTemperatureGrid(
        swLat: bounds.south, swLon: bounds.west, neLat: bounds.north, neLon: bounds.east,
      );
      tempHeatBytes = await renderHeatImage(tempPoints);
      activeLayer = LayerType.temperature;
    } catch (e) { tempError = e.toString(); }
    finally { tempLoading = false; notifyListeners(); }
  }

  void setTempMode(DisplayMode mode) { tempMode = mode; notifyListeners(); }
  void clearTemperature() { tempPoints = []; tempHeatBytes = null; tempError = null; if (activeLayer == LayerType.temperature) activeLayer = LayerType.none; notifyListeners(); }

  // ── בחירת נקודות חום ידנית ─────────────────────────────────────────────────
  // שכבת חום נפרדת מהטמפרטורה מבוססת-האזור: המשתמש מוסיף נקודות בלחיצה על המפה,
  // ללא קריאת שרת כלל — רינדור ויזואלי בלבד (מקביל ל-heatmapData/Leaflet.heat בדסקטופ)
  bool manualHeatMode = false;
  List<LatLng> manualHeatPoints = [];
  Uint8List? manualHeatImageBytes;
  LatLngBounds? manualHeatBounds;

  void toggleManualHeatMode() {
    manualHeatMode = !manualHeatMode; // כיבוי לא מוחק נקודות קיימות — מקביל ל-toggleLosMode
    notifyListeners();
  }

  Future<void> addManualHeatPoint(LatLng p) async {
    manualHeatPoints = [...manualHeatPoints, p];
    final res = await renderScatterHeatImage(manualHeatPoints);
    manualHeatImageBytes = res.bytes;
    manualHeatBounds = res.bounds;
    notifyListeners();
  }

  void clearManualHeatPoints() {
    manualHeatPoints = [];
    manualHeatImageBytes = null;
    manualHeatBounds = null;
    notifyListeners();
  }

  // נקודת גובה שנבחרה בלחיצה
  GridPoint? tappedElevPoint;
  LatLng?   tappedElevLatLng;

  void tapElevation(LatLng point) {
    if (elevPoints.isEmpty) return;
    GridPoint? nearest;
    double minDist = double.infinity;
    for (final p in elevPoints) {
      final d = (p.lat - point.latitude) * (p.lat - point.latitude) +
                (p.lon - point.longitude) * (p.lon - point.longitude);
      if (d < minDist) { minDist = d; nearest = p; }
    }
    tappedElevPoint  = nearest;
    tappedElevLatLng = point;
    notifyListeners();
  }

  void closeElevTap() { tappedElevPoint = null; tappedElevLatLng = null; notifyListeners(); }

  Future<void> fetchWeather(LatLng point) async {
    weatherLoading = true; weatherData = null; weatherPoint = point; notifyListeners();
    try { weatherData = await ApiService.fetchPointWeather(lat: point.latitude, lon: point.longitude); }
    catch (_) { weatherData = null; }
    finally { weatherLoading = false; notifyListeners(); }
  }

  void closeWeather() { weatherData = null; weatherPoint = null; notifyListeners(); }

  // ── כלי מדידה ──
  bool rulerMode = false;
  List<LatLng> rulerPoints = [];
  double rulerTotalMeters = 0.0;

  void toggleRuler() {
    rulerMode = !rulerMode;
    if (!rulerMode) { rulerPoints = []; rulerTotalMeters = 0; }
    notifyListeners();
  }

  void addRulerPoint(LatLng p) {
    if (rulerPoints.isNotEmpty) {
      rulerTotalMeters += _haversine(rulerPoints.last, p);
    }
    rulerPoints = [...rulerPoints, p];
    notifyListeners();
  }

  void clearRuler() {
    rulerPoints = []; rulerTotalMeters = 0; rulerMode = false; notifyListeners();
  }

  static double _haversine(LatLng p1, LatLng p2) {
    const R = 6371000.0;
    final phi1 = p1.latitude  * pi / 180;
    final phi2 = p2.latitude  * pi / 180;
    final dphi = (p2.latitude  - p1.latitude)  * pi / 180;
    final dlam = (p2.longitude - p1.longitude) * pi / 180;
    final a = sin(dphi/2)*sin(dphi/2) + cos(phi1)*cos(phi2)*sin(dlam/2)*sin(dlam/2);
    return R * 2 * atan2(sqrt(a), sqrt(1-a));
  }

  // ── כלי קווי ראייה (LOS) ────────────────────────────────────────────────────

  // פלטת צבעים: כל סשן LOS חדש מקבל צבע אחר כדי להבחין בין הקווים
  static const List<Color> _losPalette = [
    Color(0xFF4488FF), // כחול
    Color(0xFFFFAA00), // כתום
    Color(0xFFCC44FF), // סגול
    Color(0xFF00CCCC), // טורקיז
    Color(0xFFFF4488), // ורוד
    Color(0xFF88FF44), // ירוק-צהוב
  ];

  bool losMode = false;          // האם מצב LOS פעיל ומחכה ללחיצות המשתמש
  List<LosSession> losSessions = []; // כל הסשנים הפעילים עם פרופיל מחושב
  LatLng? losCurObs;             // נקודת תצפית זמנית לפני בחירת נקודת יעד
  bool losLoading = false;       // האם יש בקשת LOS פעילה בעיבוד ברקע
  String? losError;              // הודעת שגיאה מהבקשה האחרונה

  // הפעל או כבה את מצב LOS
  void toggleLosMode() {
    losMode = !losMode;          // הפוך בין מצב פעיל לכבוי
    if (!losMode) losCurObs = null; // בעת כיבוי: נקה נקודת תצפית ממתינה
    notifyListeners();
  }

  // שמור נקודת תצפית (לחיצה ראשונה) — הכלי ממתין לנקודת יעד
  void setLosObserver(LatLng p) {
    losCurObs = p;               // שמור נקודת התצפית עד לבחירת היעד
    notifyListeners();
  }

  // חשב קו ראייה (לחיצה שנייה) — שלח בקשה לשרת ושמור תוצאה
  Future<void> runLos(LatLng tgt) async {
    final obs = losCurObs;
    if (obs == null) return;     // חובה שיהיה מוצא — אחרת בטל
    losCurObs = null;            // אפס מיד כדי שהכלי יהיה מוכן לסשן הבא
    final sIdx = losSessions.length + 1; // מספר סידורי: הסשן הבא ברצף
    final color = _losPalette[(sIdx - 1) % _losPalette.length]; // בחר צבע מהפלטה
    losLoading = true; losError = null; notifyListeners();
    try {
      final r = await ApiService.fetchLos( // שליחת בקשת LOS לשרת
        lat1: obs.latitude,  lon1: obs.longitude,
        lat2: tgt.latitude,  lon2: tgt.longitude,
      );
      final session = LosSession(
        obs: obs, tgt: tgt, points: r.points, color: color,
        idx: sIdx, totalKm: r.totalKm,
        firstBlockKm: r.firstBlockKm, allVisible: r.allVisible,
      );
      losSessions = [...losSessions, session]; // הוסף סשן חדש לרשימה הפעילה
    } catch (e) {
      losError = e.toString().replaceFirst('Exception: ', ''); // שגיאת שרת — הצג למשתמש
    } finally {
      losLoading = false; notifyListeners(); // מובטח תמיד לאפס — גם במקרה חריג לא-צפוי
    }
  }

  // מחק סשן LOS בודד לפי מספר סידורי
  void removeLosSession(int idx) {
    losSessions = losSessions.where((s) => s.idx != idx).toList(); // סנן את הסשן הנבחר
    notifyListeners();
  }

  // סגור הודעת שגיאה בלבד — ללא מחיקת סשנים או כיבוי מצב LOS
  void clearLosError() { losError = null; notifyListeners(); }

  // נקה את כל קווי הראייה וחזור למצב ברירת מחדל
  void clearLosMap() {
    losSessions = [];    // מחק את כל הסשנים הפעילים
    losCurObs   = null;  // אפס נקודת תצפית ממתינה
    losMode     = false; // כבה מצב LOS
    losError    = null;  // נקה הודעת שגיאה
    notifyListeners();
  }

  // ── שכבת "אזורי פעילות טיסה (NOTAM)" — 7 קטגוריות, בהשראת מסך השכבות של DronesIL ──
  // חשוב: אזורים שבהם *מישהו אחר* קיבל אישור/פעילות מוכרזת — שכבת הימנעות/מודעות,
  // לא "מותר לך לטוס כאן". ר' ApiService.fetchUasNotamZones להסבר המקור ו-
  // data/notam_categories.dart לרשימת הקטגוריות. NOTAM בודד עשוי להתאים ליותר מקטגוריה אחת.
  List<UasNotamZone> uasNotamZones = []; // המידע הגולמי מהשרת — נטען פעם אחת, משותף לכל 7 הקטגוריות
  bool uasNotamLoaded  = false;          // האם הטעינה החד-פעמית כבר הצליחה
  bool uasNotamLoading = false;          // בקשת רשת פעילה ברקע
  String? uasNotamError;                 // הודעת השגיאה מהניסיון האחרון, אם נכשל
  Set<String> activeNotamCategories = {}; // אילו id-ים של קטגוריות מסומנים כרגע (תיבות סימון בפאנל)
  bool notamFitPending = false; // טריגר חד-פעמי — "יש קטגוריה חדשה שהופעלה, יש להתאים תצוגת מפה" — נצרך ע"י map_screen.dart

  Future<void> toggleNotamCategory(String catId) async {
    if (!uasNotamLoaded) {
      // סימון ראשון אי-פעם — מפעיל טעינה מהשרת, משותפת לכל 7 הקטגוריות
      uasNotamLoading = true; uasNotamError = null; notifyListeners();
      try {
        uasNotamZones = await ApiService.fetchUasNotamZones();
        uasNotamLoaded = true;
        activeNotamCategories.add(catId); // הקטגוריה שסומנה ברגע שהפעילה את הטעינה
        notamFitPending = true; // אזורים חדשים על המפה — יש להתאים את התצוגה אליהם
      } catch (e) {
        uasNotamError = e.toString().replaceFirst('Exception: ', '');
      }
      uasNotamLoading = false; notifyListeners();
      return;
    }
    // כבר נטען בעבר — toggle סינכרוני בלבד, בלי בקשת רשת נוספת
    if (activeNotamCategories.contains(catId)) {
      activeNotamCategories.remove(catId); // כיבוי — לא מתאים תצוגה מחדש, כדי לא "לקפוץ" עם המצלמה בלי צורך
    } else {
      activeNotamCategories.add(catId);
      notamFitPending = true; // הופעלה קטגוריה חדשה — אזורים קטנים (מאות מטרים) לא ייראו כפוליגון בזום ארצי בלי התאמה
    }
    notifyListeners();
  }

  void consumeNotamFit() { notamFitPending = false; }

  void clearUasNotamCache() {
    // מנקה גם את המטמון (לא רק את הבחירה) — לשימוש בכפתור "רענן" מפורש בפאנל
    uasNotamZones = [];
    uasNotamLoaded = false;
    activeNotamCategories.clear();
    uasNotamError = null;
    notifyListeners();
  }

  // ── שכבת "אזורי תיאום כטב"ם" ──
  // חשוב: אלה אזורים שניתן *לבקש* לפעול בהם, לא "מותר לטוס" — כל אזור דורש אישור
  // יחידת הנת"א מראש. נתונים סטטיים (kUasCoordinationZones) — אין fetch/loading/error.
  bool uasCoordActive = false;

  void toggleUasCoordZonesLayer() {
    uasCoordActive = !uasCoordActive;
    notifyListeners();
  }

  // ── שכבת "גבולות CTR שדות תעופה" ──
  // גבול מרחב פיקוח קבוע (CTR) כפי שמפורסם רשמית ב-AIP — נתונים סטטיים (kAirportCtrZones),
  // בשונה משכבת "אזורי פיקוח שדות תעופה" (NOTAM) שמציגה רק אזכורים אד-הוק בטקסט הודעות.
  bool airportCtrActive = false;

  void toggleAirportCtrLayer() {
    airportCtrActive = !airportCtrActive;
    notifyListeners();
  }

  // ── איפוס מפה מלא ─────────────────────────────────────────────────────────
  // מקביל ל-resetMapState() בגרסת הדסקטופ — מנקה את כל השכבות/הכלים/הסימונים
  // הפעילים ומחזיר את המצלמה למרכז ברירת המחדל. לא נוגע בהיסטוריית החיפוש
  // השמורה (citySearchHistory/flightHistory) — זו העדפת משתמש, לא מצב מפה.
  LatLng? resetFocusPoint; // טריגר חד-פעמי לקפיצת מצלמה בעת איפוס — נצרך ונמחק ע"י map_screen.dart
  void consumeResetFocus() { resetFocusPoint = null; } // מסמן שהקפיצה כבר בוצעה, מונע קפיצה חוזרת ברינדור הבא

  void resetMap() {
    selectionStart = null; selectionEnd = null; // ביטול בחירת אזור פעילה (גבהים/טמפרטורה)
    elevPoints = []; elevHeatBytes = null; elevError = null; // ניקוי שכבת גבהים שנטענה
    tempPoints = []; tempHeatBytes = null; tempError = null; // ניקוי שכבת טמפרטורה שנטענה
    activeLayer = LayerType.none; // אין יותר שכבת גבהים/טמפרטורה מוצגת
    manualHeatMode = false; // כיבוי מצב בחירת נקודות חום ידנית
    manualHeatPoints = []; manualHeatImageBytes = null; manualHeatBounds = null; // ניקוי נקודות החום הידניות שסומנו
    tappedElevPoint = null; tappedElevLatLng = null; // סגירת כרטיס גובה פתוח, אם קיים
    weatherData = null; weatherPoint = null; // סגירת כרטיס מזג אוויר פתוח, אם קיים
    rulerMode = false; rulerPoints = []; rulerTotalMeters = 0; // כיבוי כלי המדידה וניקוי הנקודות שסומנו
    losMode = false; losSessions = []; losCurObs = null; losError = null; // כיבוי מצב LOS וניקוי כל סשני קו הראייה
    activeNotamCategories = {}; // ביטול סימון קטגוריות NOTAM — המטמון (uasNotamZones) נשאר כדי שלא יידרש fetch חוזר בהפעלה הבאה
    uasCoordActive = false; // כיבוי שכבת אזורי התיאום
    airportCtrActive = false; // כיבוי שכבת גבולות ה-CTR
    flightData = null; flightError = null; flightFocusPoint = null; // ניקוי מסלול טיסה מוצג, אם קיים
    pinnedPoints = []; lastPinnedPoint = null; // מחיקת כל הסיכות שנוספו ידנית/ע"י GPS
    cityBounds = null; cityBoundaryRings = []; citySearchError = null; cityFocusPoint = null; // ניקוי תוצאת חיפוש עיר מוצגת
    resetFocusPoint = const LatLng(31.5, 34.9); // אותה נקודת פתיחה כמו initialCenter ב-map_screen.dart — מחזיר את המצלמה למרכז
    notifyListeners(); // עדכון כל ה-widgets שמאזינים ל-state בבת אחת
  }
}
