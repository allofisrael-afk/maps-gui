import 'package:latlong2/latlong.dart';
import 'package:flutter_map/flutter_map.dart';

// תוצאת חיפוש עיר: מיקום מרכזי ואופציונלית גבולות (bounding box) לציור מלבן על המפה
class CityResult {
  final String displayName;   // השם המלא שהוחזר מהשירות, לתצוגה/היסטוריה
  final LatLng center;        // נקודת המרכז לקפיצת המפה
  final LatLngBounds? bounds; // גבולות העיר; null אם השירות לא החזיר boundingbox

  const CityResult({
    required this.displayName,
    required this.center,
    this.bounds,
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
    );
  }
}
