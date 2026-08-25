import 'package:latlong2/latlong.dart';

// תוצאת הערכת מסלול טיסה מול תצורת מכ"ם-דופלר — מקביל ל-result שמחזיר
// _radar_route_eval_worker ב-weather_server.py (Desktop). ר' ApiService.fetchRouteEvaluation.
class RouteEvalPoint {
  const RouteEvalPoint({
    required this.lat, required this.lng, this.altFt, this.spdKt,
    required this.distKm, required this.status, required this.reason,
  });
  final double lat;
  final double lng;
  final double? altFt;
  final double? spdKt;
  final double distKm; // מרחק מהמשקיף, ק"מ
  final String status; // 'detected' | 'doppler_blind' | 'blocked' | 'out_of_range'
  final String reason;  // 'ok' | 'terrain' | 'radar_range' | 'doppler' | 'out_of_range' | 'no_elevation_data'
}

class RouteEvaluationResult {
  const RouteEvaluationResult({
    required this.observer, required this.observerElev, required this.observerH, required this.rangeKm,
    required this.points, required this.detectedCount, required this.dopplerBlindCount,
    required this.blockedCount, required this.outOfRangeCount, required this.pointsEvaluated,
    required this.pointsTotal, required this.rcsUsed, required this.aircraftLabel,
  });
  final LatLng observer;
  final double observerElev;
  final double observerH;
  final double rangeKm;
  final List<RouteEvalPoint> points;
  final int detectedCount, dopplerBlindCount, blockedCount, outOfRangeCount;
  final int pointsEvaluated, pointsTotal;
  final double rcsUsed;   // ה-RCS שנגזר אוטומטית מסוג כלי-הטיס ושימש בפועל בחישוב — לשקיפות
  final String aircraftLabel; // שם כלי-הטיס לתצוגה
}
