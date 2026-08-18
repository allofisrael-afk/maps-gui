import 'dart:async'; // TimeoutException, לשליפת גבהים מרובת-batches ברדיוס-ראייה רדיאלי
import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import '../models/grid_point.dart';
import '../models/los_session.dart'; // מודל נקודות ופרופיל קו ראייה
import '../models/city_result.dart'; // מודל תוצאת חיפוש עיר
import '../models/uas_notam_zone.dart'; // מודל אזור NOTAM לרחפנים
import '../models/radial_los_result.dart'; // מודל תוצאת רדיוס-ראייה רדיאלי
import '../data/icao_glossary.dart'; // תרגום גס לעברית לטקסט NOTAM
import '../data/notam_categories.dart'; // סיווג NOTAM ל-7 קטגוריות

/// טוקן ביטול לחישוב רדיוס-ראייה רדיאלי — נבדק בין כל batch בזמן שליפת הגבהים,
/// מאפשר למשתמש לעצור חישוב ארוך אמצע-הדרך (מקביל ל-cancelled ב-_radial_jobs בצד Desktop).
class RadialLosCancelToken {
  bool _cancelled = false;
  void cancel() => _cancelled = true;
  bool get isCancelled => _cancelled;
}

/// חריגה ייעודית ל-429 (מכסת בקשות Open-Meteo) — מפילה את כל החישוב, לא רק batch בודד,
/// באותו אופן בדיוק כמו /elevation ו-/temp_grid בצד Desktop.
class _RadialRateLimitException implements Exception {
  _RadialRateLimitException(this.message);
  final String message;
}

/// נקודת דגימה בודדת בתוך אלגוריתם ה-ratchet — מקביל למילון שמחזיר _horizon_ratchet בפייתון.
class _RatchetPoint {
  _RatchetPoint(this.distM, this.elevation, this.losH, this.visible);
  final double distM, elevation, losH;
  final bool visible;
}

class ApiService {
  static const String _elevBase = 'https://api.open-meteo.com/v1/elevation';
  static const String _forecastBase = 'https://api.open-meteo.com/v1/forecast';
  static const String _geocodeBase = 'https://nominatim.openstreetmap.org/search';

  /// GET משותף: מבצע בקשה, בודק status==200, ומפענח JSON. מאחד 7 מקומות בקובץ הזה
  /// שחזרו על אותה שרשרת Uri.parse→http.get→בדיקת status→json.decode. כמה מקומות עם
  /// התנהגות שונה בכשל (למשל נפילה חזרה לספק הבא בלי לזרוק, או המשך ללולאה) נשארו
  /// עצמאיים בכוונה — הכפלה קטנה עדיפה על פני helper שמנסה לכסות כל מקרה קצה.
  static Future<dynamic> _getJson(
    Uri uri, {
    Map<String, String>? headers,
    required Duration timeout,
    required String errorLabel,
  }) async {
    final response = await http.get(uri, headers: headers).timeout(timeout);
    if (response.statusCode != 200) throw Exception('$errorLabel ${response.statusCode}');
    return json.decode(response.body);
  }

  // ── חיפוש עיר (geocoding) — Nominatim/OSM, חינמי וללא מפתח ────────────────
  static Future<CityResult> geocodeCity(String name) async {
    // polygon_geojson=1 — מבקש את גבולות העיר בפועל (Polygon/MultiPolygon), לא רק תיבה מלבנית;
    // לא כל תוצאה כוללת זאת (תלוי בכיסוי OSM), ולכן CityResult נופל חזרה למלבן אם אין geojson
    final uri = Uri.parse(
      '$_geocodeBase?q=${Uri.encodeComponent(name)}&format=json&limit=1&addressdetails=0&polygon_geojson=1',
    );
    // Nominatim דורש User-Agent מזהה לפי מדיניות השימוש שלו
    final results = await _getJson(
      uri,
      headers: {'User-Agent': 'maps-gui-android/1.0'},
      timeout: const Duration(seconds: 15),
      errorLabel: 'שגיאת חיפוש עיר',
    ) as List;
    if (results.isEmpty) throw Exception('עיר "$name" לא נמצאה');
    return CityResult.fromNominatimJson(results.first as Map<String, dynamic>);
  }

  static Future<List<GridPoint>> fetchElevationGrid({
    required double swLat, required double swLon,
    required double neLat, required double neLon,
  }) async {
    const baseKm  = 5.0;
    const maxPts  = 100;
    final midLat  = (swLat + neLat) / 2;
    final cosLat  = cos(midLat * pi / 180);
    final latKm   = (neLat - swLat) * 111.0;
    final lngKm   = (neLon - swLon) * 111.0 * cosLat;
    double stepKm = baseKm;
    int nLat = max(2, (latKm / stepKm).ceil());
    int nLon = max(2, (lngKm / stepKm).ceil());
    if (nLat * nLon > maxPts) {
      stepKm *= sqrt((nLat * nLon) / maxPts);
      nLat = max(2, (latKm / stepKm).ceil());
      nLon = max(2, (lngKm / stepKm).ceil());
    }
    final List<double> lats = [];
    final List<double> lons = [];
    for (int i = 0; i < nLat; i++) {
      for (int j = 0; j < nLon; j++) {
        lats.add(swLat + (neLat - swLat) * i / (nLat - 1));
        lons.add(swLon + (neLon - swLon) * j / (nLon - 1));
      }
    }
    const chunkSize = 50;
    final List<GridPoint> results = [];
    for (int offset = 0; offset < lats.length; offset += chunkSize) {
      final end = (offset + chunkSize).clamp(0, lats.length);
      final chunkLats = lats.sublist(offset, end);
      final chunkLons = lons.sublist(offset, end);
      final uri = Uri.parse('$_elevBase?latitude=${chunkLats.join(',')}&longitude=${chunkLons.join(',')}');
      final data = await _getJson(uri, timeout: const Duration(seconds: 40), errorLabel: 'Elevation API error') as Map<String, dynamic>;
      final elevations = (data['elevation'] as List).cast<num>();
      for (int k = 0; k < chunkLats.length; k++) {
        results.add(GridPoint(lat: chunkLats[k], lon: chunkLons[k], value: elevations[k].toDouble()));
      }
    }
    return results;
  }

  static Future<List<GridPoint>> fetchTemperatureGrid({
    required double swLat, required double swLon,
    required double neLat, required double neLon,
  }) async {
    const baseKm   = 5.0;
    const maxPts   = 30;
    final midLat   = (swLat + neLat) / 2;
    final cosLat   = cos(midLat * pi / 180);
    final latKm    = (neLat - swLat) * 111.0;
    final lngKm    = (neLon - swLon) * 111.0 * cosLat;
    double stepKm  = baseKm;
    int nLat = max(2, (latKm / stepKm).ceil());
    int nLon = max(2, (lngKm / stepKm).ceil());
    if (nLat * nLon > maxPts) {
      stepKm *= sqrt((nLat * nLon) / maxPts);
      nLat = max(2, (latKm / stepKm).ceil());
      nLon = max(2, (lngKm / stepKm).ceil());
    }
    final List<double> lats = [];
    final List<double> lons = [];
    for (int i = 0; i < nLat; i++) {
      for (int j = 0; j < nLon; j++) {
        lats.add(swLat + (neLat - swLat) * i / (nLat - 1));
        lons.add(swLon + (neLon - swLon) * j / (nLon - 1));
      }
    }
    const chunkSize = 20;
    final List<GridPoint> results = [];
    for (int offset = 0; offset < lats.length; offset += chunkSize) {
      if (offset > 0) await Future.delayed(const Duration(milliseconds: 200));
      final end = (offset + chunkSize).clamp(0, lats.length);
      final chunkLats = lats.sublist(offset, end);
      final chunkLons = lons.sublist(offset, end);
      final uri = Uri.parse(
        '$_forecastBase?latitude=${chunkLats.join(',')}&longitude=${chunkLons.join(',')}'
        '&current=temperature_2m&timezone=UTC',
      );
      final body = await _getJson(uri, timeout: const Duration(seconds: 40), errorLabel: 'Forecast API error');
      if (body is List) {
        for (int k = 0; k < chunkLats.length; k++) {
          final temp = (body[k]['current']['temperature_2m'] as num).toDouble();
          results.add(GridPoint(lat: chunkLats[k], lon: chunkLons[k], value: temp));
        }
      } else {
        final temp = (body['current']['temperature_2m'] as num).toDouble();
        results.add(GridPoint(lat: chunkLats[0], lon: chunkLons[0], value: temp));
      }
    }
    return results;
  }

  // ── Flight tracking ─────────────────────────────────────
  // Primary: local FlightServer (desktop, same WiFi).
  // Fallback: FlightRadar24 unofficial API with Gold token.
  static String flightServerHost = ''; // set via settings, e.g. "192.168.1.100"
  static const _fr24Token = 'qJOskJ9NjhsiGXTIuSTCr6Zy5DOd0_jYqOipmTuSEqs';
  static const _fr24Headers = {
    'Cookie': '_frPl=$_fr24Token',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.flightradar24.com/',
  };

  static Future<({List<LatLng> path, LatLng? current, String callsign, String info})> fetchFlightTrack(String input) async {
    final callsign = input.trim().toUpperCase();

    // 1. Try local FlightServer (desktop, same WiFi)
    if (flightServerHost.isNotEmpty) {
      try {
        final uri = Uri.parse('http://$flightServerHost:5004/flight_route?flight=$callsign');
        final resp = await http.get(uri).timeout(const Duration(seconds: 12));
        if (resp.statusCode == 200) {
          return _parseFlightServerResponse(resp.body, callsign);
        }
      } catch (_) {}
    }

    // 2. OpenSky Network — חינמי, ללא Cloudflare
    try {
      return await _fetchOpenSky(callsign);
    } catch (_) {}

    // 3. FlightRadar24 Gold API — fallback אחרון
    return _fetchFR24(callsign);
  }

  static Future<({List<LatLng> path, LatLng? current, String callsign, String info})> _fetchOpenSky(String callsign) async {
    // שליפת טיסות פעילות לפי callsign
    final statesUri = Uri.parse(
      'https://opensky-network.org/api/states/all?callsign=${Uri.encodeComponent(callsign)}',
    );
    final statesData = await _getJson(statesUri, timeout: const Duration(seconds: 15), errorLabel: 'OpenSky states שגיאה') as Map<String, dynamic>;
    final states = statesData['states'] as List?;
    if (states == null || states.isEmpty) throw Exception('טיסה "$callsign" לא נמצאה ב-OpenSky');

    // מציאת הטיסה המתאימה — callsign מגיע עם רווחים ב-OpenSky
    List? match;
    for (final state in states) {
      final cs = (state[1] as String?)?.trim().toUpperCase() ?? '';
      if (cs == callsign || cs.contains(callsign) || callsign.contains(cs)) {
        match = state as List;
        break;
      }
    }
    if (match == null) throw Exception('טיסה "$callsign" לא נמצאה ב-OpenSky');

    final icao24  = match[0] as String;
    final curLon  = (match[5] as num?)?.toDouble();
    final curLat  = (match[6] as num?)?.toDouble();
    final current = (curLat != null && curLon != null) ? LatLng(curLat, curLon) : null;

    // שליפת מסלול לפי transponder ICAO24
    List<LatLng> trail = [];
    try {
      // time=0 מחזיר את הטיסה הנוכחית/אחרונה
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      for (final t in [0, now - 3600, now - 7200]) {
        final trackUri = Uri.parse('https://opensky-network.org/api/tracks/all?icao24=$icao24&time=$t');
        final trackResp = await http.get(trackUri).timeout(const Duration(seconds: 12));
        if (trackResp.statusCode == 200) {
          final trackData = json.decode(trackResp.body) as Map<String, dynamic>;
          final path = trackData['path'] as List? ?? [];
          final pts = path
              .where((p) => p[1] != null && p[2] != null)
              .map((p) => LatLng((p[1] as num).toDouble(), (p[2] as num).toDouble()))
              .toList();
          if (pts.length > trail.length) trail = pts;
        }
        if (trail.length >= 2) break;
      }
    } catch (_) {}

    if (trail.isEmpty && current != null) trail = [current];
    if (trail.isEmpty) throw Exception('אין נתוני מסלול לטיסה $callsign מ-OpenSky');

    return (path: trail, current: current ?? trail.last, callsign: callsign, info: '${trail.length} נקודות מסלול');
  }

  static ({List<LatLng> path, LatLng? current, String callsign, String info}) _parseFlightServerResponse(
      String body, String callsign) {
    final d = json.decode(body) as Map<String, dynamic>;
    if (d.containsKey('error')) throw Exception(d['error']);
    final trail = (d['trail'] as List? ?? [])
        .where((p) => p['lat'] != null && (p['lng'] ?? p['lon']) != null)
        .map((p) => LatLng((p['lat'] as num).toDouble(), ((p['lng'] ?? p['lon']) as num).toDouble()))
        .toList();
    final lat = d['lat'] as num?;
    final lng = d['lng'] as num?;
    final current = (lat != null && lng != null) ? LatLng(lat.toDouble(), lng.toDouble()) : null;
    final cs = d['callsign'] as String? ?? callsign;
    final orig = d['origin_iata'] as String? ?? '';
    final dest = d['dest_iata'] as String? ?? '';
    final aircraft = d['aircraft'] as String? ?? '';
    final info = [if (orig.isNotEmpty && dest.isNotEmpty) '$orig → $dest', if (aircraft.isNotEmpty) aircraft].join(' · ');
    if (trail.isEmpty && current == null) throw Exception('אין נתוני מסלול לטיסה $callsign');
    return (path: trail.isNotEmpty ? trail : [current!], current: current ?? trail.last, callsign: cs, info: info);
  }

  static Future<({List<LatLng> path, LatLng? current, String callsign, String info})> _fetchFR24(String callsign) async {
    // Search for the flight
    final feedUri = Uri.parse(
      'https://data.flightradar24.com/zones/fcgi/feed.js'
      '?callsign=$callsign&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400',
    );
    final feed = await _getJson(feedUri, headers: _fr24Headers, timeout: const Duration(seconds: 15), errorLabel: 'FR24 שגיאה') as Map<String, dynamic>;
    String? flightId;
    double? curLat, curLon;

    for (final entry in feed.entries) {
      if (entry.key == 'version' || entry.key == 'full_count' || entry.key == 'stats') continue;
      final v = entry.value as List?;
      if (v == null || v.length < 17) continue;
      final cs = (v[16] as String?)?.trim() ?? '';
      if (cs.toUpperCase().contains(callsign)) {
        flightId = entry.key;
        curLat = (v[1] as num?)?.toDouble();
        curLon = (v[2] as num?)?.toDouble();
        break;
      }
    }

    if (flightId == null) throw Exception('טיסה "$callsign" לא נמצאה בשמים כרגע');

    // Get trail
    final detUri = Uri.parse('https://data.flightradar24.com/clickhandler/?flight=$flightId');
    final detResp = await http.get(detUri, headers: _fr24Headers).timeout(const Duration(seconds: 15));
    if (detResp.statusCode != 200) {
      if (curLat != null && curLon != null) {
        final p = LatLng(curLat, curLon);
        return (path: [p], current: p, callsign: callsign, info: '');
      }
      throw Exception('FR24 clickhandler שגיאה');
    }

    final det = json.decode(detResp.body) as Map<String, dynamic>;
    final trail = (det['trail'] as List? ?? [])
        .where((p) => p['lat'] != null && p['lng'] != null)
        .map((p) => LatLng((p['lat'] as num).toDouble(), (p['lng'] as num).toDouble()))
        .toList();

    final orig = (det['airport'] as Map?)?['origin']?['code']?['iata'] as String? ?? '';
    final dest = (det['airport'] as Map?)?['destination']?['code']?['iata'] as String? ?? '';
    final aircraft = (det['aircraft'] as Map?)?['model']?['text'] as String? ?? '';
    final info = [if (orig.isNotEmpty && dest.isNotEmpty) '$orig → $dest', if (aircraft.isNotEmpty) aircraft].join(' · ');
    final current = (curLat != null && curLon != null) ? LatLng(curLat!, curLon!) : (trail.isNotEmpty ? trail.last : null);

    if (trail.isEmpty && current == null) throw Exception('אין נתוני מסלול');
    return (path: trail.isNotEmpty ? trail : [current!], current: current, callsign: callsign, info: info);
  }

  // ── קו ראייה (LOS) — חישוב on-device ללא שרת מקומי ────────────────────────
  // מחשב קו ראייה ישירות: שולף גבהים מ-open-meteo ומריץ את האלגוריתם על המכשיר
  static Future<({List<LosPoint> points, double totalKm, double? firstBlockKm, bool allVisible})>
      fetchLos({
    required double lat1, required double lon1, // קואורדינטות נקודת התצפית
    required double lat2, required double lon2, // קואורדינטות נקודת היעד
  }) async {
    const R     = 6371000.0; // רדיוס כדור הארץ במטרים
    const k     = 0.13;      // מקדם שבירה אטמוספרי סטנדרטי
    const obsH  = 11.0;      // גובה עין התצפית מעל הקרקע במטרים
    const stepM = 5000.0;    // מרחק בין נקודות דגימה (5 ק"מ)
    const maxM  = 500000.0;  // מרחק מקסימלי נתמך (500 ק"מ)

    // חישוב מרחק כולל; חיתוך למקסימום
    final totalM = min(_haversineM(lat1, lon1, lat2, lon2), maxM);
    final n      = min(max(2, (totalM / stepM).ceil()), 100); // עד 100 נקודות דגימה

    // יצירת נקודות לאורך קשת גדולה (Great Circle)
    final coords = List.generate(n, (i) {
      final frac = n > 1 ? i / (n - 1.0) : 0.0; // שבר מהמוצא אל היעד
      return _interpolateGC(lat1, lon1, lat2, lon2, frac);
    });

    // שליפת גבהים מ-open-meteo בנתחים של 50 (מגבלת API)
    final elevs = <double>[];
    const chunkSize = 50;
    for (int off = 0; off < coords.length; off += chunkSize) {
      final end  = min(off + chunkSize, coords.length);
      final sub  = coords.sublist(off, end);
      final uri  = Uri.parse(
        '$_elevBase'
        '?latitude=${sub.map((c) => c[0].toStringAsFixed(6)).join(',')}'
        '&longitude=${sub.map((c) => c[1].toStringAsFixed(6)).join(',')}',
      );
      final data = await _getJson(uri, timeout: const Duration(seconds: 30), errorLabel: 'שגיאת API גבהים') as Map<String, dynamic>; // תגובה תוך 30 שניות
      elevs.addAll((data['elevation'] as List).map((e) => (e as num).toDouble())); // הוספה לרשימה
    }
    if (elevs.length < n) throw Exception('נתוני גובה חסרים'); // פחות גבהים מנקודות

    // ── אלגוריתם קו ראייה עם תיקון עקמומיות ──
    final hObs     = elevs[0] + obsH;          // גובה עין התצפית מעל פני הים
    var maxAngle   = double.negativeInfinity;   // זווית LOS מקסימלית שנראתה עד כה
    double? firstBlockM;                        // מרחק החסימה הראשונה במטרים
    final result   = <LosPoint>[];

    for (int i = 0; i < n; i++) {
      final elev = elevs[i];
      final d    = totalM * (n > 1 ? i / (n - 1.0) : 0.0); // מרחק מנקודת המוצא
      bool visible;
      double losH;
      if (d == 0) {
        visible = true; losH = hObs;            // נקודת מוצא תמיד גלויה
      } else {
        final drop  = d * d / (2 * R) * (1 - k); // ירידה בשל עקמומיות כדור הארץ + שבירה
        final corr  = elev - drop;               // גובה השטח המתוקן
        final angle = (corr - hObs) / d;         // זווית הנקודה הנוכחית
        visible     = angle >= maxAngle;          // גלוי אם לא חסום ע"י שטח קדום
        if (visible) maxAngle = angle;            // עדכן זווית מקסימלית
        losH = hObs + maxAngle * d;              // גובה קו הראייה בנקודה זו
      }
      if (!visible && firstBlockM == null) firstBlockM = d; // תעד חסימה ראשונה
      result.add(LosPoint(
        lat:       coords[i][0], lon:       coords[i][1],
        distKm:    d / 1000,     elevation: elev,
        losH:      losH,         visible:   visible,
      ));
    }

    return (
      points:       result,
      totalKm:      totalM / 1000,
      firstBlockKm: firstBlockM != null ? firstBlockM / 1000 : null, // null = גלוי לגמרי
      allVisible:   firstBlockM == null,
    );
  }

  // ── רדיוס-ראייה רדיאלי (Viewshed מכומת) — כלי נפרד מ-LOS, פוליגון גבול-ראייה יחיד ──
  // מקביל ל-/los_radial/* בצד Desktop (weather_server.py) — כאן כולו on-device, בלי job/polling
  // בצד שרת (אין שרת בכלל ב-Android), במקום זאת progress callback + טוקן ביטול תוך כדי async.
  static const double _radialRangeKmMin = 0.5, _radialRangeKmMax = 300.0; // טווח מרחק מותר, ק"מ
  static const double _radialAngleStepMin = 3.0, _radialAngleStepMax = 45.0; // צעד זווית מותר, מעלות
  static const double _radialRidgeMarginMin = 0.0, _radialRidgeMarginMax = 10.0; // מרווח רכס מותר, מעלות
  static const double _radialVCenterMin = -45.0, _radialVCenterMax = 45.0; // מרכז אלומה אנכי מותר, מעלות
  static const double _radialVWidthMin = 1.0, _radialVWidthMax = 90.0; // רוחב אלומה אנכי מותר, מעלות
  static const int _radialBaseBudget = 720; // תקציב נקודות ל"רזולוציה גבוהה בטווח קצר"
  static const double _radialTargetSpacingKm = 2.0; // מרווח יעד בין דגימות לאורך קרן, גובר בטווח ארוך
  static const int _radialSamplesMin = 8, _radialSamplesMax = 150; // רצפת/תקרת דגימות לקרן בודדת
  static const int _radialMaxTotalPoints = 4000; // תקרת נקודות כוללת — גובלת את זמן הריצה המרבי
  static const int _radialBatchSize = 30; // נקודות לכל בקשת batch — כמו טמפרטורה/גבהים בצד Desktop
  static const Duration _radialBatchPause = Duration(milliseconds: 500); // השהיה בין batches — מונע חסימת Open-Meteo

  static double _clampD(double v, double lo, double hi) => v < lo ? lo : (v > hi ? hi : v);

  /// ליבת אלגוריתם "מנוע האופק" — זהה ל-_horizon_ratchet בצד Desktop (weather_server.py),
  /// כולל שני התיקונים שנמצאו בבדיקה חיה: (1) bareAngle (בלי hOffset) בונה את קו האופק,
  /// testAngle (עם hOffset) נבדק מולו — אחרת gt_h גדול על כל נקודה "מזהם" את עצמו ומחסים
  /// שטח ישר לגמרי בהדרגה; (2) הבדיקה הזו לא עוצרת אף פעם באמצע — הקורא (fetchRadialLos)
  /// אחראי למצוא את הנקודה הגלויה הרחוקה ביותר, לא רק לעצור בכישלון הראשון.
  static List<_RatchetPoint> _horizonRatchet(
    List<double> distsM, List<double> elevs, double hObs, List<double> hOffsets, {
    double marginSlope = 0.0,
    double? minAngleSlope,
    double? maxAngleSlope,
  }) {
    const R = 6371000.0; // רדיוס כדור הארץ, במטרים
    const k = 0.13; // מקדם שבירה אטמוספרי
    double maxAngle = double.negativeInfinity; // אופק הקרקע הגולמי בלבד (לא כולל hOffset)
    final out = <_RatchetPoint>[];
    for (int i = 0; i < distsM.length; i++) {
      final d = distsM[i];
      final elev = elevs[i];
      final drop = d * d / (2 * R) * (1 - k); // ירידת קו הראייה בגלל עקמומיות+רפרקציה
      if (d == 0) {
        out.add(_RatchetPoint(d, elev, hObs, true)); // נקודת המוצא עצמה — תמיד גלויה
      } else {
        final bareAngle = (elev - drop - hObs) / d; // זווית הקרקע הגולמית — בונה את קו האופק
        final testAngle = (elev + hOffsets[i] - drop - hObs) / d; // זווית הנקודה הנבדקת בפועל
        bool visible = testAngle >= maxAngle + marginSlope; // חייב "לנצח" את קו האופק + מרווח הביטחון
        if (minAngleSlope != null && testAngle < minAngleSlope) visible = false; // מתחת לשדה-הראייה האנכי המותר
        if (maxAngleSlope != null && testAngle > maxAngleSlope) visible = false; // מעל שדה-הראייה האנכי המותר
        if (bareAngle > maxAngle) maxAngle = bareAngle; // עדכון קו האופק — תמיד לפי הקרקע הגולמית
        final losH = hObs + maxAngle * d; // גובה קו הראייה בנקודה הזו, לצורך תצוגה עתידית
        out.add(_RatchetPoint(d, elev, losH, visible));
      }
    }
    return out;
  }

  /// שליפת גבהים ל-batch נתון — עד 3 ניסיונות על timeout, לא זורק על כשל רגיל (מחזיר null
  /// לכל הנקודות, לא מפיל את כל החישוב), אבל זורק מיידית על 429 (מפיל את כל החישוב, כמו Desktop).
  static Future<List<double?>> _fetchRadialElevChunk(List<LatLng> points) async {
    final uri = Uri.parse(
      '$_elevBase?latitude=${points.map((p) => p.latitude.toStringAsFixed(6)).join(',')}'
      '&longitude=${points.map((p) => p.longitude.toStringAsFixed(6)).join(',')}',
    );
    for (int attempt = 0; attempt < 3; attempt++) {
      try {
        final response = await http.get(uri).timeout(const Duration(seconds: 30));
        if (response.statusCode == 429) {
          throw _RadialRateLimitException('מכסת בקשות Open-Meteo הגיעה למגבלה');
        }
        if (response.statusCode != 200) {
          return List<double?>.filled(points.length, null); // שגיאת שרת אחרת — לא retry, לא מפיל הכל
        }
        final data = json.decode(response.body) as Map<String, dynamic>;
        final elevs = (data['elevation'] as List).map((e) => (e as num).toDouble()).toList();
        return List<double?>.generate(points.length, (i) => i < elevs.length ? elevs[i] : null);
      } on _RadialRateLimitException {
        rethrow; // 429 — מועבר הלאה מיד, לא retry, מפיל את כל fetchRadialLos
      } on TimeoutException {
        if (attempt < 2) {
          await Future.delayed(Duration(milliseconds: 500 * (attempt + 1))); // 0.5/1 שנ' — כמו Desktop
        } else {
          return List<double?>.filled(points.length, null); // נכשל אחרי 3 ניסיונות — לא מפיל הכל
        }
      } catch (_) {
        return List<double?>.filled(points.length, null); // כשל לא-timeout (רשת/פענוח) — לא retry, לא מפיל הכל
      }
    }
    return List<double?>.filled(points.length, null);
  }

  /// מחשב רדיוס-ראייה רדיאלי מלאה — כל האזימוטים (או מגזר חלקי) ממשקיף אחד. onProgress נקרא
  /// אחרי כל batch (לתצוגת התקדמות), cancelToken נבדק בין כל batch (לעצירה אמצע-הדרך). מחזיר
  /// null אם בוטל, זורק חריגה על כשל (429/שגיאת גובה משקיף), אחרת מחזיר תוצאה מלאה.
  static Future<RadialLosResult?> fetchRadialLos({
    required LatLng observer,
    required double rangeKm,
    required double minRangeKm,
    required double angleStepDeg,
    required double startBearingDeg,
    required double endBearingDeg,
    required double obsH,
    required double tgtH,
    required double ridgeMarginDeg,
    required double verticalCenterDeg,
    required double verticalWidthDeg,
    void Function(int done, int total)? onProgress,
    RadialLosCancelToken? cancelToken,
  }) async {
    // הצמדת פרמטרים לטווח מותר, לא דחייה — כמו /los_radial/start בצד Desktop
    rangeKm = _clampD(rangeKm, _radialRangeKmMin, _radialRangeKmMax);
    minRangeKm = _clampD(minRangeKm, 0.0, rangeKm);
    angleStepDeg = _clampD(angleStepDeg, _radialAngleStepMin, _radialAngleStepMax);
    ridgeMarginDeg = _clampD(ridgeMarginDeg, _radialRidgeMarginMin, _radialRidgeMarginMax);
    verticalCenterDeg = _clampD(verticalCenterDeg, _radialVCenterMin, _radialVCenterMax);
    verticalWidthDeg = _clampD(verticalWidthDeg, _radialVWidthMin, _radialVWidthMax);

    final rangeM = rangeKm * 1000.0;
    final minRangeM = minRangeKm * 1000.0;
    const distCalc = Distance(); // ברירת מחדל Vincenty (אליפסואידלי) — מדויק יותר מהמודל הכדורי בצד Desktop, ההבדל זניח כאן

    // שלב 1: גובה המשקיף עצמו — בנפרד, לפני הכל, נכשל-מהר אם לא זמין
    final obsElevs = await _fetchRadialElevChunk([observer]);
    if (obsElevs.isEmpty || obsElevs[0] == null) {
      throw Exception('לא ניתן לשלוף את גובה המשקיף');
    }
    final observerElev = obsElevs[0]!;
    final hObs = observerElev + obsH; // גובה עין המשקיף בפועל

    // שלב 2: בניית כיווני הסריקה — תמיכה במגזר חלקי + "עטיפה" מעל 360°/0°
    var span = (endBearingDeg - startBearingDeg) % 360;
    if (span == 0) span = 360; // start==end פירושו "הכל" (מעגל מלא), לא מגזר ברוחב אפס
    final nBearings = max(1, (span / angleStepDeg).round());
    final effectiveStepDeg = span / nBearings; // שלב אפקטיבי — מחלק את המגזר בדיוק
    final bearings = List<double>.generate(nBearings, (i) => (startBearingDeg + i * effectiveStepDeg) % 360);

    // שלב 3: צפיפות דגימה — מרבי בין "תקציב לפי כיוונים" (טווח קצר) ל"מרווח יעד קבוע" (טווח ארוך)
    final budgetBased = min(20, max(_radialSamplesMin, _radialBaseBudget ~/ nBearings));
    final spacingBased = ((rangeKm - minRangeKm) / _radialTargetSpacingKm).round() + 1;
    int samplesPerRay = max(_radialSamplesMin, min(_radialSamplesMax, max(budgetBased, spacingBased)));
    if (nBearings * samplesPerRay > _radialMaxTotalPoints) {
      samplesPerRay = max(_radialSamplesMin, _radialMaxTotalPoints ~/ nBearings); // שילוב קיצוני — מצמצם
    }

    // שלב 4: בניית כל נקודות הדגימה מראש (כל כיוון × כל מרחק דגימה לאורכו) — רשימה שטוחה אחת
    final allPoints = <LatLng>[];
    final allDists = <double>[];
    for (final bearing in bearings) {
      for (int j = 0; j < samplesPerRay; j++) {
        final frac = samplesPerRay > 1 ? j / (samplesPerRay - 1) : 0.0;
        final dist = minRangeM + frac * (rangeM - minRangeM); // מרחק הדגימה ה-j לאורך הקרן
        allPoints.add(dist <= 0 ? observer : distCalc.offset(observer, dist, bearing));
        allDists.add(dist);
      }
    }

    // שלב 5: שליפת גבהים ב-batches, עם השהיה ביניהם — עדכון התקדמות ובדיקת ביטול אחרי כל batch
    final totalBatches = (allPoints.length / _radialBatchSize).ceil();
    final elevations = List<double?>.filled(allPoints.length, null); // None = נקודה שלא נשלף עבורה גובה
    for (int batchIdx = 0; batchIdx < totalBatches; batchIdx++) {
      if (cancelToken?.isCancelled ?? false) return null; // בדיקת ביטול בין כל batch
      if (batchIdx > 0) await Future.delayed(_radialBatchPause); // השהיה בין batches — לא לפני הראשון
      final start = batchIdx * _radialBatchSize;
      final end = min(start + _radialBatchSize, allPoints.length);
      final batchElevs = await _fetchRadialElevChunk(allPoints.sublist(start, end));
      for (int k = 0; k < batchElevs.length; k++) {
        elevations[start + k] = batchElevs[k]; // כשל חלקי משאיר null — לא מפיל את כל החישוב
      }
      onProgress?.call(batchIdx + 1, totalBatches);
    }

    // שלב 6: פירוק בחזרה לפי קרן, הרצת ה-ratchet לכל קרן בנפרד (מקומית — בלי עוד קריאות רשת)
    final marginSlope = tan(ridgeMarginDeg * pi / 180);
    final vHalf = verticalWidthDeg / 2.0;
    final minAngleSlope = tan((verticalCenterDeg - vHalf) * pi / 180);
    final maxAngleSlope = tan((verticalCenterDeg + vHalf) * pi / 180);
    final rays = <RadialLosRay>[];
    int clearCount = 0, failedRays = 0;
    for (int rayIdx = 0; rayIdx < nBearings; rayIdx++) {
      final start = rayIdx * samplesPerRay;
      final rayPoints = allPoints.sublist(start, start + samplesPerRay);
      final rayDists = allDists.sublist(start, start + samplesPerRay);
      final rayElevs = elevations.sublist(start, start + samplesPerRay);
      final survivingIdx = <int>[for (int i = 0; i < rayElevs.length; i++) if (rayElevs[i] != null) i]; // מסנן נקודות בלי גובה, שומר סדר
      final samplesOk = survivingIdx.length;
      if (samplesOk < 2) { // אין מספיק נתונים בכלל לאורך הקרן הזו
        rays.add(RadialLosRay(bearingDeg: bearings[rayIdx], clearDistKm: 0.0, point: observer,
            blocked: true, ok: false, samplesOk: samplesOk));
        failedRays++;
        continue;
      }
      final dists = survivingIdx.map((i) => rayDists[i]).toList();
      final elevsOnly = survivingIdx.map((i) => rayElevs[i]!).toList();
      final hOffsets = List<double>.filled(survivingIdx.length, tgtH); // tgtH מוחל על כל נקודה, לא רק האחרונה
      final ratchet = _horizonRatchet(dists, elevsOnly, hObs, hOffsets,
          marginSlope: marginSlope, minAngleSlope: minAngleSlope, maxAngleSlope: maxAngleSlope);
      // קודקוד הקרן = הנקודה הגלויה **הרחוקה ביותר**, לא בהכרח רציפה מהקצה הקרוב (תיקון שנמצא בבדיקה חיה)
      double clearDistM = 0.0;
      LatLng clearPoint = observer;
      for (int i = 0; i < ratchet.length; i++) {
        if (ratchet[i].visible) {
          clearDistM = ratchet[i].distM;
          clearPoint = rayPoints[survivingIdx[i]];
        }
      }
      final blocked = !ratchet.last.visible; // "פנוי לגמרי" רק אם הנקודה הרחוקה ביותר בקרן עצמה גלויה
      if (!blocked) clearCount++;
      rays.add(RadialLosRay(bearingDeg: bearings[rayIdx], clearDistKm: clearDistM / 1000,
          point: clearPoint, blocked: blocked, ok: samplesOk == samplesPerRay, samplesOk: samplesOk));
      if (samplesOk != samplesPerRay) failedRays++;
    }

    return RadialLosResult(
      observer: observer, observerElev: observerElev, observerH: hObs,
      obsH: obsH, tgtH: tgtH, ridgeMarginDeg: ridgeMarginDeg,
      verticalCenterDeg: verticalCenterDeg, verticalWidthDeg: verticalWidthDeg,
      rangeKm: rangeKm, minRangeKm: minRangeKm, angleStepDeg: effectiveStepDeg,
      startBearingDeg: startBearingDeg, endBearingDeg: endBearingDeg, spanDeg: span,
      nBearings: nBearings, samplesPerRay: samplesPerRay,
      clearCount: clearCount, failedRays: failedRays, rays: rays,
    );
  }

  // מרחק Haversine בין שתי נקודות גיאוגרפיות במטרים
  static double _haversineM(double lat1, double lon1, double lat2, double lon2) {
    const R   = 6371000.0;
    final phi1 = lat1 * pi / 180, phi2 = lat2 * pi / 180;
    final dphi = (lat2 - lat1) * pi / 180, dlam = (lon2 - lon1) * pi / 180;
    final a = sin(dphi/2)*sin(dphi/2) + cos(phi1)*cos(phi2)*sin(dlam/2)*sin(dlam/2);
    return R * 2 * atan2(sqrt(a), sqrt(1-a));
  }

  // אינטרפולציה על קשת גדולה — מחזיר [lat, lon] בשבר frac מהמסלול
  static List<double> _interpolateGC(double lat1, double lon1, double lat2, double lon2, double frac) {
    final f1 = lat1 * pi / 180, l1 = lon1 * pi / 180;
    final f2 = lat2 * pi / 180, l2 = lon2 * pi / 180;
    final d  = 2 * asin(sqrt(pow(sin((f2-f1)/2), 2) + cos(f1)*cos(f2)*pow(sin((l2-l1)/2), 2)));
    if (d < 1e-10) return [lat1, lon1]; // נקודות כמעט זהות — החזר מוצא
    final A  = sin((1 - frac) * d) / sin(d); // משקל נקודת המוצא
    final B  = sin(frac * d)       / sin(d); // משקל נקודת היעד
    final x  = A*cos(f1)*cos(l1) + B*cos(f2)*cos(l2);
    final y  = A*cos(f1)*sin(l1) + B*cos(f2)*sin(l2);
    final z  = A*sin(f1)         + B*sin(f2);
    return [atan2(z, sqrt(x*x + y*y)) * 180 / pi, atan2(y, x) * 180 / pi]; // [lat, lon]
  }

  static Future<Map<String, dynamic>> fetchPointWeather({
    required double lat, required double lon,
  }) async {
    final uri = Uri.parse(
      '$_forecastBase?latitude=$lat&longitude=$lon'
      '&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto',
    );
    final data = await _getJson(uri, timeout: const Duration(seconds: 20), errorLabel: 'Weather API error') as Map<String, dynamic>;
    final current = data['current'] as Map<String, dynamic>;
    return {
      'temp': current['temperature_2m'],
      'humidity': current['relative_humidity_2m'],
      'wind': current['wind_speed_10m'],
      'code': current['weather_code'],
    };
  }

  // ── שכבת "אזורי פעילות רחפנים (NOTAM)" — מקביל ל-notam_drones.py בגרסת הדסקטופ ──
  // brin.iaa.gov.il הוא אתר ציבורי (רשות שדות התעופה) שנגיש ישירות מהמכשיר —
  // בשונה מ-FlightServer, אין כאן תלות ברשת ה-WiFi המקומית של הדסקטופ.
  // חשוב — סמנטיקה: "UAS/UAV ACT WILL TAKE PLACE... CLSD FM GND UP TO Xft" מתארת
  // פעילות רחפנים *מאושרת של מפעיל אחר* שסוגרת את המרחב לתעבורה אחרת — זה *לא*
  // "מותר לך לטוס כאן". השכבה היא כלי הימנעות/מודעות בלבד.
  static const _notamUrl = 'https://brin.iaa.gov.il/aeroinfo/AeroInfo.aspx?msgType=Notam';

  // קואורדינטת DMS דחוסה — נתמכים שני סדרי-טוקנים אמיתיים שנצפו ב-NOTAM: "ספרות-ואז-אות-כיוון"
  // (315907.32N0345601.24E, הנפוץ) ו"אות-כיוון-ואז-ספרות" (N314945E0345822, נצפה בפוליגונים
  // כמו LATRUN/OR-AKIVA — לפני התיקון הזה הם נפלו ל"טקסט בלבד" כי הפורמט לא זוהה כלל).
  // שניות עשרוניות (`.32`) נתמכות בשני הפורמטים — נצפו ב-NOTAM-ים אחרים (מנופי בנייה).
  static const _coordPattern =
      r'(?:\d{2}\d{2}\d{2}(?:\.\d+)?[NS]\d{3}\d{2}\d{2}(?:\.\d+)?[EW]'
      r'|[NS]\d{2}\d{2}\d{2}(?:\.\d+)?[EW]\d{3}\d{2}\d{2}(?:\.\d+)?)';
  static final _coordRe = RegExp(_coordPattern); // לאיתור כל הקואורדינטות בטקסט חופשי (לפוליגונים) — allMatches
  // פירוק בפועל לפי הפורמט הספציפי שהתקבל — נבדק ב-_coordToLatLng אחרי שהתאמה נמצאה
  static final _coordSuffixRe = RegExp(r'^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([NS])(\d{3})(\d{2})(\d{2}(?:\.\d+)?)([EW])$');
  static final _coordPrefixRe = RegExp(r'^([NS])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)([EW])(\d{3})(\d{2})(\d{2}(?:\.\d+)?)$');
  // תבנית אזור מעגלי, למשל "0.3NM RADIUS CENTERED ON PSN 314643N0350539E" — נתמכות 3 יחידות
  // מרחק אמיתיות שנצפו ב-NOTAM (NM/KM/M, ר' _unitToMeters למטה); הקואורדינטה יכולה להיות
  // בכל אחד משני הפורמטים הנתמכים (ר' _coordPattern למעלה). (?:\S+\s+){0,4}? מאפשר עד 4
  // מילים בין RADIUS ל-CENTERED (למשל "RADIUS SEMI-CIRCLE TO EAST CENTERED", נצפה בפועל).
  static final _radiusRe = RegExp(
    r'(\d+(?:\.\d+)?)\s*(NM|KM|M)\s+RADIUS\s+(?:\S+\s+){0,4}?CENTERED\s+ON\s+PSN\s+(' + _coordPattern + r')',
    caseSensitive: false,
  );
  static const _unitToMeters = {'NM': 1852.0, 'KM': 1000.0, 'M': 1.0}; // גורם המרה לכל יחידת רדיוס נתמכת
  // משפט הגובה — מ"FM" (התחלה: GND או גובה) עד "UP TO ..." ועד לנקודה הבאה
  static final _altSentenceRe = RegExp(r'FM\s+(?:GND|[\d,]+\s*FT)\s+UP\s+TO[^.]*', caseSensitive: false);
  static final _notamIdRe = RegExp(r'class="NotamID">\s*([^<\n]+?)\s*</td>');   // תא הטבלה עם מספר ה-NOTAM
  static final _locationRe = RegExp(r'class="Location">\s*([^<\n]+?)\s*</td>'); // תא הטבלה עם קוד ה-ICAO
  static final _msgTextRe = RegExp(r'class="MsgText">\s*([^<]*?)\s*</td>');     // שורת טקסט אחת מתוך כמה

  /// ממיר קואורדינטת DMS דחוסה (בכל אחד משני הפורמטים הנתמכים) לנקודת LatLng עשרונית,
  /// או null אם אף פורמט לא תואם. מנסה קודם את הפורמט הנפוץ (ספרות ואז אות-כיוון), ואם
  /// לא תואם — את הפורמט ההפוך (אות-כיוון ואז ספרות), שנצפה בפועל בכמה NOTAM-ים של פוליגונים.
  static LatLng? _coordToLatLng(String coord) {
    var m = _coordSuffixRe.firstMatch(coord); // פורמט 1: 315907N0345601E (הנפוץ)
    String latD, latM, latS, ns, lonD, lonM, lonS, ew;
    if (m != null) {
      latD = m.group(1)!; latM = m.group(2)!; latS = m.group(3)!; ns = m.group(4)!;
      lonD = m.group(5)!; lonM = m.group(6)!; lonS = m.group(7)!; ew = m.group(8)!;
    } else {
      m = _coordPrefixRe.firstMatch(coord); // פורמט 2: N315907E0345601 (הפוך)
      if (m == null) return null; // אף אחד משני הפורמטים לא תואם — הקורא מסנן null בעצמו
      ns = m.group(1)!; latD = m.group(2)!; latM = m.group(3)!; latS = m.group(4)!;
      ew = m.group(5)!; lonD = m.group(6)!; lonM = m.group(7)!; lonS = m.group(8)!;
    }
    // double.parse תומך גם בשניות עשרוניות (למשל "07.32"), לא רק int
    var lat = double.parse(latD) + double.parse(latM) / 60 + double.parse(latS) / 3600; // מעלות + דקות/60 + שניות/3600
    var lon = double.parse(lonD) + double.parse(lonM) / 60 + double.parse(lonS) / 3600;
    if (ns == 'S') lat = -lat; // דרום = ערך שלילי
    if (ew == 'W') lon = -lon; // מערב = ערך שלילי
    return LatLng(lat, lon);
  }

  /// מזהה מעגל ("X NM RADIUS CENTERED ON PSN ...") או פוליגון (3+ קואורדינטות בטקסט).
  /// מחזיר null אם לא נמצאה גיאומטריה ניתנת לזיהוי — הרשומה תידלג במקום להיכשל.
  static ({UasNotamGeometryType type, LatLng? center, double? radiusM, List<LatLng> points})? _extractGeometry(
      String text) {
    final radiusMatch = _radiusRe.firstMatch(text); // קודם בודקים מעגל — יותר ספציפי מפוליגון
    if (radiusMatch != null) {
      final center = _coordToLatLng(radiusMatch.group(3)!); // קבוצה 3 = הקואורדינטה (1=מספר, 2=יחידה)
      if (center != null) {
        final unit = radiusMatch.group(2)!.toUpperCase();
        return (
          type: UasNotamGeometryType.circle,
          center: center,
          radiusM: double.parse(radiusMatch.group(1)!) * _unitToMeters[unit]!, // המרה ליחידה שנתפסה בפועל
          points: const <LatLng>[],
        );
      }
    }
    final coords = _coordRe
        .allMatches(text)
        .map((m) => _coordToLatLng(m.group(0)!))
        .whereType<LatLng>()
        .toList();
    if (coords.length >= 3) {
      return (type: UasNotamGeometryType.polygon, center: null, radiusM: null, points: coords);
    }
    return null; // אין מספיק מידע גיאומטרי בטקסט
  }

  static String _extractAltitudeText(String text) {
    final m = _altSentenceRe.firstMatch(text);
    return m?.group(0)?.trim() ?? '';
  }

  /// מפצל את ה-HTML לבלוקים לפי divMainInfo_ (רשומת NOTAM אחת לכל בלוק) ומחלץ
  /// מכל בלוק: מזהה NOTAM, מיקום ICAO, וטקסט ההודעה המלא (מחובר מכל שורות ה-MsgText).
  static List<({String id, String icao, String text})> _parseNotamBlocks(String html) {
    final starts = RegExp(r'<div id="divMainInfo_').allMatches(html).map((m) => m.start).toList();
    final notams = <({String id, String icao, String text})>[];
    for (int i = 0; i < starts.length; i++) {
      final end = i + 1 < starts.length ? starts[i + 1] : html.length;
      final block = html.substring(starts[i], end);
      final idMatch = _notamIdRe.firstMatch(block);
      final locMatch = _locationRe.firstMatch(block);
      if (idMatch == null || locMatch == null) continue; // בלוק שלא בפורמט הצפוי — מדלגים
      final msgParts = _msgTextRe
          .allMatches(block)
          .map((m) => m.group(1)!.trim())
          .where((p) => p.isNotEmpty);
      final fullText = msgParts.join(' '); // חיבור כל שורות הטקסט לרצף אחד — כולל קואורדינטות שנחתכו על פני כמה שורות
      notams.add((id: idMatch.group(1)!.trim(), icao: locMatch.group(1)!.trim(), text: fullText));
    }
    return notams;
  }

  static Future<List<UasNotamZone>> fetchUasNotamZones() async {
    final resp = await http
        .get(Uri.parse(_notamUrl), headers: {'User-Agent': 'Mozilla/5.0'}) // UA דפדפן — נדרש כדי לעבור את הגנת ה-WAF של האתר
        .timeout(const Duration(seconds: 20));
    if (resp.statusCode != 200) throw Exception('שגיאת שרת NOTAM ${resp.statusCode}');

    final notams = _parseNotamBlocks(resp.body);
    final zones = <UasNotamZone>[];
    for (final n in notams) {
      final categories = classifyNotam(n.text); // התאמה ל-0 או יותר מ-7 הקטגוריות (ר' data/notam_categories.dart)
      if (categories.isEmpty) continue; // לא תואם אף קטגוריה רלוונטית — לא נכלל בשכבה
      final geo = _extractGeometry(n.text);
      if (geo == null) continue; // רשומה רלוונטית, אבל בלי גיאומטריה ניתנת לחילוץ מהטקסט
      final altText = _extractAltitudeText(n.text);
      zones.add(UasNotamZone(
        id: n.id,
        icao: n.icao,
        text: n.text,
        altitudeText: altText,
        categories: categories, // רשימת id-ים — שימוש בסינון/צביעה לפי קטגוריה בצד הלקוח
        hebrewGloss: renderHebrewGloss(n.text), // תרגום גס — תמיד לצד המקור האנגלי, לא במקומו
        altitudeGloss: renderHebrewGloss(altText),
        geometryType: geo.type,
        center: geo.center,
        radiusM: geo.radiusM,
        points: geo.points,
      ));
    }
    return zones;
  }
}
