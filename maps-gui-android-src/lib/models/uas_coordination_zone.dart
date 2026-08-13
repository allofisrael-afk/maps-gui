import 'package:latlong2/latlong.dart';
import 'uas_notam_zone.dart' show UasNotamGeometryType;

/// אזור "תיאום כטב"ם" — נתונים סטטיים ממקור רשמי (ר' data/uas_coordination_zones.dart).
/// חשוב: תחילת פעילות בכל אזור דורשת אישור יחידת הנת"א מראש — זו *לא* שכבת "מותר לטוס".
class UasCoordinationZone {
  const UasCoordinationZone({
    required this.name,
    required this.geometryType,
    required this.maxAltitudeFt,
    required this.altitudeLabel,
    required this.notes,
    this.center,
    this.radiusM,
    this.points = const [],
  });

  final String name;
  final UasNotamGeometryType geometryType;
  final int maxAltitudeFt;
  final String altitudeLabel; // ניסוח מקורי מדויק מהמקור (עלול להיות מעפ"י=AMSL ולא AGL)
  final String notes;
  final LatLng? center;        // מרכז — רק לגיאומטריית מעגל
  final double? radiusM;       // רדיוס במטרים — רק לגיאומטריית מעגל
  final List<LatLng> points;   // נקודות הגבול — רק לגיאומטריית פוליגון

  /// נקודת עוגן לציור סמן פרטים על המפה — מרכז המעגל, או ממוצע נקודות הפוליגון.
  LatLng get anchor {
    if (geometryType == UasNotamGeometryType.circle && center != null) return center!;
    if (points.isEmpty) return const LatLng(0, 0);
    final lat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final lon = points.map((p) => p.longitude).reduce((a, b) => a + b) / points.length;
    return LatLng(lat, lon);
  }
}
