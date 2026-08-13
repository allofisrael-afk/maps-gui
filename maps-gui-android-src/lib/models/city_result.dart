import 'package:latlong2/latlong.dart';
import 'package:flutter_map/flutter_map.dart';

// תוצאת חיפוש עיר: מיקום מרכזי, גבולות (bounding box) לקפיצת מצלמה, ואופציונלית
// גבול העיר בפועל (טבעות פוליגון אמיתיות) לציור מודגש על המפה
class CityResult {
  final String displayName;   // השם המלא שהוחזר מהשירות, לתצוגה/היסטוריה
  final LatLng center;        // נקודת המרכז לקפיצת המפה
  final LatLngBounds? bounds; // תיבה מלבנית — לקפיצת מצלמה/fallback אם אין גבול אמיתי
  final List<List<LatLng>> boundaryRings; // גבול/גבולות העיר בפועל מ-OSM; ריק אם השירות לא החזיר geojson

  const CityResult({
    required this.displayName,
    required this.center,
    this.bounds,
    this.boundaryRings = const [],
  });

  // בניית אובייקט מתגובת ה-JSON של Nominatim (רשימה, לוקחים את האיבר הראשון)
  factory CityResult.fromNominatimJson(Map<String, dynamic> j) {
    final lat = double.parse(j['lat'] as String);
    final lon = double.parse(j['lon'] as String);
    LatLngBounds? bounds;
    final bbox = j['boundingbox'] as List<dynamic>?;
    if (bbox != null && bbox.length == 4) {
      // סדר Nominatim: [south, north, west, east] — כל הערכים כ-strings
      final south = double.parse(bbox[0] as String);
      final north = double.parse(bbox[1] as String);
      final west = double.parse(bbox[2] as String);
      final east = double.parse(bbox[3] as String);
      bounds = LatLngBounds(LatLng(south, west), LatLng(north, east));
    }
    return CityResult(
      displayName: j['display_name'] as String? ?? '',
      center: LatLng(lat, lon),
      bounds: bounds,
      boundaryRings: _extractBoundaryRings(j['geojson'] as Map<String, dynamic>?),
    );
  }

  // ממיר geojson.geometry (Polygon/MultiPolygon בלבד — כל היתר, כמו Point לעיר קטנה
  // בלי גבול OSM ידוע, מוחזר ריק ונופל חזרה לתיבה המלבנית) לרשימת טבעות LatLng.
  // כל טבעת (חיצונית וגם חורים פנימיים, אם יש) מצוירת בנפרד — פשוט וממוקד לתצוגה בלבד.
  static List<List<LatLng>> _extractBoundaryRings(Map<String, dynamic>? geojson) {
    if (geojson == null) return const [];
    final type = geojson['type'] as String?;
    final coords = geojson['coordinates'];
    List<LatLng> ringFrom(List<dynamic> ring) => ring
        .map((p) => LatLng(((p as List)[1] as num).toDouble(), (p[0] as num).toDouble()))
        .toList();
    try {
      if (type == 'Polygon' && coords is List) {
        return coords.map((ring) => ringFrom(ring as List<dynamic>)).toList();
      }
      if (type == 'MultiPolygon' && coords is List) {
        final rings = <List<LatLng>>[];
        for (final polygon in coords) {
          for (final ring in polygon as List<dynamic>) {
            rings.add(ringFrom(ring as List<dynamic>));
          }
        }
        return rings;
      }
    } catch (_) {
      return const []; // geojson מעוות/לא צפוי — נופלים חזרה בשקט לתיבה המלבנית
    }
    return const []; // Point/LineString וכד' — אין גבול שטח להציג
  }
}
