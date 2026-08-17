import 'package:latlong2/latlong.dart';

/// גבול CTR (אזור פיקוח) קבוע של שדה תעופה — נתונים סטטיים ממקור AIP רשמי
/// (ר' data/airport_ctr_zones.dart). בשונה מ-UasNotamZone: אינו נגזר מהודעות
/// NOTAM אלא מהגבול הקבוע כפי שמפורסם רשמית (סעיף AD 2.17), ולכן תמיד פוליגון.
class AirportCtrZone {
  const AirportCtrZone({
    required this.name,
    required this.icao,
    required this.points,
    required this.verticalLimits,
    required this.notes,
  });

  final String name;
  final String icao;
  final List<LatLng> points;    // נקודות גבול הפוליגון — כל הרשומות הנוכחיות פוליגון (אין מעגלים)
  final String verticalLimits;  // ניסוח מקורי מדויק מהמקור, למשל "SFC – 2,000 רגל MSL"
  final String notes;

  /// נקודת עוגן לציור סמן פרטים על המפה — ממוצע נקודות הפוליגון (מרכז כובד גס).
  LatLng get anchor {
    final lat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final lon = points.map((p) => p.longitude).reduce((a, b) => a + b) / points.length;
    return LatLng(lat, lon);
  }
}
