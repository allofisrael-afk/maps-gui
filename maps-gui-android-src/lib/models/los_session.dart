import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

// נקודה בודדת לאורך פרופיל קו הראייה
class LosPoint {
  final double lat;        // קו רוחב של הנקודה על המסלול
  final double lon;        // קו אורך של הנקודה על המסלול
  final double distKm;     // מרחק ממוצא התצפית בקילומטרים
  final double elevation;  // גובה שטח במטרים מעל פני הים
  final double losH;       // גובה קו הראייה הגיאומטרי המחושב בנקודה זו
  final bool visible;      // האם הנקודה גלויה מנקודת התצפית (ללא חסימה בשטח)

  const LosPoint({
    required this.lat,
    required this.lon,
    required this.distKm,
    required this.elevation,
    required this.losH,
    required this.visible,
  });

  // בניית אובייקט מתגובת JSON שהתקבלה מהשרת
  factory LosPoint.fromJson(Map<String, dynamic> j) => LosPoint(
    lat:       (j['lat']       as num).toDouble(), // קו רוחב מה-JSON
    lon:       (j['lon']       as num).toDouble(), // קו אורך מה-JSON
    distKm:    (j['dist_km']   as num).toDouble(), // מרחק מהמוצא בק"מ
    elevation: (j['elevation'] as num).toDouble(), // גובה שטח מ-open-meteo
    losH:      (j['los_h']     as num).toDouble(), // גובה קו הראייה המחושב
    visible:   j['visible']    as bool,            // סטטוס נראות מהשרת
  );
}

// סשן שלם של קו ראייה: נקודת תצפית, נקודת יעד ופרופיל השטח ביניהן
class LosSession {
  final LatLng obs;             // קואורדינטות נקודת התצפית
  final LatLng tgt;             // קואורדינטות נקודת היעד
  final List<LosPoint> points;  // פרופיל גובה לאורך קו הראייה
  final Color color;            // צבע ייחודי המבדיל סשן זה משאר הסשנים
  final int idx;                // מספר סידורי 1-based להצגה בממשק המשתמש
  final double totalKm;         // מרחק כולל בין תצפית ליעד בקילומטרים
  final double? firstBlockKm;   // מרחק עד החסימה הראשונה; null אם גלוי לגמרי
  final bool allVisible;        // true אם כל קו הראייה גלוי ללא שום חסימה

  const LosSession({
    required this.obs,
    required this.tgt,
    required this.points,
    required this.color,
    required this.idx,
    required this.totalKm,
    this.firstBlockKm,
    required this.allVisible,
  });
}
