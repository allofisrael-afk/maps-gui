import 'package:latlong2/latlong.dart';

/// אזור NOTAM — מקביל ל-notam_drones.py בגרסת הדסקטופ. מסווג ל-7 קטגוריות אפשריות
/// (ר' data/notam_categories.dart) — NOTAM בודד עשוי להתאים ליותר מקטגוריה אחת.
/// חשוב: אלה אזורים שבהם *מישהו אחר* קיבל אישור/פעילות מוכרזת והמרחב סגור/מוגבל
/// לתעבורה אחרת — שכבת הימנעות/מודעות, לא "מותר לך לטוס כאן".
enum UasNotamGeometryType { circle, polygon }

class UasNotamZone {
  const UasNotamZone({
    required this.id,
    required this.icao,
    required this.text,
    required this.altitudeText,
    required this.geometryType,
    required this.categories,
    this.hebrewGloss = '',
    this.altitudeGloss = '',
    this.center,
    this.radiusM,
    this.points = const [],
  });

  final String id;             // מספר NOTAM, למשל C1711/26
  final String icao;           // קוד מיקום, למשל LLLL
  final String text;           // טקסט ה-NOTAM המלא (לתצוגה בכרטיס הפרטים)
  final String altitudeText;   // משפט הגובה הגולמי, למשל "FM GND UP TO 250M AGL"
  final String hebrewGloss;    // תרגום גס לעברית של text — תמיד לצד המקור, לא במקומו
  final String altitudeGloss;  // תרגום גס לעברית של altitudeText
  final List<String> categories; // id-י הקטגוריות שהאזור תואם (ר' data/notam_categories.dart) — לרוב אחד, ייתכן יותר
  final UasNotamGeometryType geometryType;
  final LatLng? center;        // מרכז — רק לגיאומטריית מעגל
  final double? radiusM;       // רדיוס במטרים — רק לגיאומטריית מעגל
  final List<LatLng> points;   // נקודות הגבול — רק לגיאומטריית פוליגון

  /// נקודת עוגן לציור סמן פרטים על המפה — מרכז המעגל, או ממוצע נקודות הפוליגון (מרכז גס, מספיק לסמן).
  LatLng get anchor {
    if (geometryType == UasNotamGeometryType.circle && center != null) return center!;
    if (points.isEmpty) return const LatLng(0, 0);
    final lat = points.map((p) => p.latitude).reduce((a, b) => a + b) / points.length;
    final lon = points.map((p) => p.longitude).reduce((a, b) => a + b) / points.length;
    return LatLng(lat, lon);
  }
}
