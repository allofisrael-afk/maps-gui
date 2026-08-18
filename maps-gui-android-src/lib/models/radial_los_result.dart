import 'package:latlong2/latlong.dart';

/// תוצאת קרן בודדת (אזימוט אחד) בחישוב רדיוס-ראייה רדיאלי — מקביל בדיוק לרשומת
/// "ray" שמחזיר /los_radial/status בצד Desktop (weather_server.py).
class RadialLosRay {
  const RadialLosRay({
    required this.bearingDeg,
    required this.clearDistKm,
    required this.point,
    required this.blocked,
    required this.ok,
    required this.samplesOk,
  });

  final double bearingDeg;
  final double clearDistKm; // המרחק הרחוק ביותר שעדיין גלוי לאורך הקרן (לא בהכרח עד סוף הטווח)
  final LatLng point;       // הנקודה שבה clearDistKm — קודקוד הפוליגון לכיוון הזה
  final bool blocked;       // true אם לא הגיע לסוף הטווח המבוקש (גם אם יש קטע גלוי לפני כן)
  final bool ok;            // false אם היו נקודות דגימה שנכשלו (לא כל samplesPerRay נשלפו)
  final int samplesOk;
}

/// תוצאת חישוב רדיוס-ראייה רדיאלי מלאה — משקיף אחד, פוליגון גבול-ראייה (קודקוד לכל אזימוט).
class RadialLosResult {
  const RadialLosResult({
    required this.observer,
    required this.observerElev,
    required this.observerH,
    required this.obsH,
    required this.tgtH,
    required this.ridgeMarginDeg,
    required this.verticalCenterDeg,
    required this.verticalWidthDeg,
    required this.rangeKm,
    required this.minRangeKm,
    required this.angleStepDeg,
    required this.startBearingDeg,
    required this.endBearingDeg,
    required this.spanDeg,
    required this.nBearings,
    required this.samplesPerRay,
    required this.clearCount,
    required this.failedRays,
    required this.rays,
  });

  final LatLng observer;
  final double observerElev, observerH;
  final double obsH, tgtH, ridgeMarginDeg;
  final double verticalCenterDeg, verticalWidthDeg;
  final double rangeKm, minRangeKm, angleStepDeg;
  final double startBearingDeg, endBearingDeg, spanDeg;
  final int nBearings, samplesPerRay, clearCount, failedRays;
  final List<RadialLosRay> rays;
}
