import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import '../models/grid_point.dart';
import '../models/los_session.dart'; // מודל נקודות ופרופיל קו ראייה
import '../models/city_result.dart'; // מודל תוצאת חיפוש עיר
import '../models/uas_notam_zone.dart'; // מודל אזור NOTAM לרחפנים
import '../data/icao_glossary.dart'; // תרגום גס לעברית לטקסט NOTAM
import '../data/notam_categories.dart'; // סיווג NOTAM ל-7 קטגוריות

class ApiService {
  static const String _elevBase = 'https://api.open-meteo.com/v1/elevation';
  static const String _forecastBase = 'https://api.open-meteo.com/v1/forecast';
  static const String _geocodeBase = 'https://nominatim.openstreetmap.org/search';

  // ── חיפוש עיר (geocoding) — Nominatim/OSM, חינמי וללא מפתח ────────────────
  static Future<CityResult> geocodeCity(String name) async {
    // polygon_geojson=1 — מבקש את גבולות העיר בפועל (Polygon/MultiPolygon), לא רק תיבה מלבנית;
    // לא כל תוצאה כוללת זאת (תלוי בכיסוי OSM), ולכן CityResult נופל חזרה למלבן אם אין geojson
    final uri = Uri.parse(
      '$_geocodeBase?q=${Uri.encodeComponent(name)}&format=json&limit=1&addressdetails=0&polygon_geojson=1',
    );
    // Nominatim דורש User-Agent מזהה לפי מדיניות השימוש שלו
    final response = await http
        .get(uri, headers: {'User-Agent': 'maps-gui-android/1.0'})
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('שגיאת חיפוש עיר ${response.statusCode}');
    final results = json.decode(response.body) as List;
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
      final response = await http.get(uri);
      if (response.statusCode != 200) throw Exception('Elevation API error ${response.statusCode}');
      final data = json.decode(response.body) as Map<String, dynamic>;
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
      final response = await http.get(uri).timeout(const Duration(seconds: 40));
      if (response.statusCode != 200) throw Exception('Forecast API error ${response.statusCode}');
      final body = json.decode(response.body);
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
    final statesResp = await http.get(statesUri).timeout(const Duration(seconds: 15));
    if (statesResp.statusCode != 200) throw Exception('OpenSky states שגיאה ${statesResp.statusCode}');

    final statesData = json.decode(statesResp.body) as Map<String, dynamic>;
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
    final feedResp = await http.get(feedUri, headers: _fr24Headers).timeout(const Duration(seconds: 15));
    if (feedResp.statusCode != 200) throw Exception('FR24 שגיאה ${feedResp.statusCode}');

    final feed = json.decode(feedResp.body) as Map<String, dynamic>;
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
      final resp = await http.get(uri).timeout(const Duration(seconds: 30)); // תגובה תוך 30 שניות
      if (resp.statusCode != 200) throw Exception('שגיאת API גבהים ${resp.statusCode}');
      final data = json.decode(resp.body) as Map<String, dynamic>;
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
    final response = await http.get(uri);
    if (response.statusCode != 200) throw Exception('Weather API error ${response.statusCode}');
    final data = json.decode(response.body) as Map<String, dynamic>;
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

  // קואורדינטת DMS דחוסה, למשל "305819N0345601E" — 2 ספרות מעלות/דקות/שניות לרוחב, 3 מעלות לאורך
  static final _coordRe = RegExp(r'(\d{2})(\d{2})(\d{2})([NS])(\d{3})(\d{2})(\d{2})([EW])');
  // תבנית אזור מעגלי, למשל "0.3NM RADIUS CENTERED ON PSN 314643N0350539E"
  static final _radiusRe = RegExp(
    r'(\d+(?:\.\d+)?)\s*NM\s+RADIUS\s+CENTERED\s+ON\s+PSN\s+(\d{6}[NS]\d{7}[EW])',
    caseSensitive: false,
  );
  // משפט הגובה — מ"FM" (התחלה: GND או גובה) עד "UP TO ..." ועד לנקודה הבאה
  static final _altSentenceRe = RegExp(r'FM\s+(?:GND|[\d,]+\s*FT)\s+UP\s+TO[^.]*', caseSensitive: false);
  static final _notamIdRe = RegExp(r'class="NotamID">\s*([^<\n]+?)\s*</td>');   // תא הטבלה עם מספר ה-NOTAM
  static final _locationRe = RegExp(r'class="Location">\s*([^<\n]+?)\s*</td>'); // תא הטבלה עם קוד ה-ICAO
  static final _msgTextRe = RegExp(r'class="MsgText">\s*([^<]*?)\s*</td>');     // שורת טקסט אחת מתוך כמה

  /// ממיר קואורדינטת DMS דחוסה לנקודת LatLng עשרונית, או null אם הפורמט לא תואם.
  static LatLng? _coordToLatLng(String coord) {
    final m = _coordRe.firstMatch(coord);
    if (m == null) return null;
    final latD = int.parse(m.group(1)!), latM = int.parse(m.group(2)!), latS = int.parse(m.group(3)!);
    final ns = m.group(4)!;
    final lonD = int.parse(m.group(5)!), lonM = int.parse(m.group(6)!), lonS = int.parse(m.group(7)!);
    final ew = m.group(8)!;
    var lat = latD + latM / 60 + latS / 3600; // המרת DMS לעשרוני: מעלות + דקות/60 + שניות/3600
    var lon = lonD + lonM / 60 + lonS / 3600;
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
      final center = _coordToLatLng(radiusMatch.group(2)!);
      if (center != null) {
        return (
          type: UasNotamGeometryType.circle,
          center: center,
          radiusM: double.parse(radiusMatch.group(1)!) * 1852.0, // המרת NM למטרים
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
