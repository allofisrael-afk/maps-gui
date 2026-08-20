import 'package:latlong2/latlong.dart';

/// תוצאת קרן בודדת (אזימוט אחד) בחישוב תצפית מכ"ם דופלר — מקביל בדיוק לרשומת "ray"
/// שמחזיר /radar_doppler/status בצד Desktop (weather_server.py).
class RadarDopplerRay {
  const RadarDopplerRay({
    required this.bearingDeg,
    required this.radarDistKm,
    required this.point,
    required this.dopplerOk,
    required this.blocked,
    required this.ok,
    required this.samplesOk,
  });

  final double bearingDeg;
  final double radarDistKm; // המרחק הרחוק ביותר שעדיין בטווח המכ"ם ולא חסום שטח (בלי קשר לדופלר)
  final LatLng point;       // הנקודה שבה radarDistKm — קודקוד הפוליגון לכיוון הזה
  final bool dopplerOk;     // false = כל הקרן הזו "עיוורת" לדופלר (מהירות המטרה המשוערת לא מתגלה בכיוון הזה)
  final bool blocked;       // true אם לא הגיע לסוף הטווח המבוקש (שטח או טווח מכ"ם/סריקה)
  final bool ok;            // false אם היו נקודות דגימה שנכשלו
  final int samplesOk;
}

/// תוצאת חישוב תצפית מכ"ם דופלר מלאה — רעיוני/חינוכי, לא מבוסס מערכת אמיתית ספציפית.
class RadarDopplerResult {
  const RadarDopplerResult({
    required this.observer,
    required this.observerElev,
    required this.observerH,
    required this.hAntenna,
    required this.ridgeMarginDeg,
    required this.rangeKm,
    required this.minRangeKm,
    required this.angleStepDeg,
    required this.verticalCenterDeg,
    required this.verticalWidthDeg,
    required this.startBearingDeg,
    required this.endBearingDeg,
    required this.spanDeg,
    required this.nBearings,
    required this.samplesPerRay,
    required this.powerKw,
    required this.gainDbi,
    required this.freqMhz,
    required this.rcsM2,
    required this.sensitivityDbm,
    required this.radarCleanRangeKm,
    required this.unambigRangeKm,
    required this.prfHz,
    required this.mdvKt,
    required this.targetSpeedKt,
    required this.targetHeadingDeg,
    required this.lobingEnabled,
    required this.reflectivityKey,
    required this.antennaType,
    required this.boresightDeg,
    required this.maxScanDeg,
    required this.clearCount,
    required this.dopplerBlockedRays,
    required this.failedRays,
    required this.rays,
  });

  final LatLng observer;
  final double observerElev, observerH, hAntenna, ridgeMarginDeg;
  final double rangeKm, minRangeKm, angleStepDeg;
  final double verticalCenterDeg, verticalWidthDeg;
  final double startBearingDeg, endBearingDeg, spanDeg;
  final int nBearings, samplesPerRay;
  final double powerKw, gainDbi, freqMhz, rcsM2, sensitivityDbm;
  final double radarCleanRangeKm, unambigRangeKm;
  final double prfHz, mdvKt, targetSpeedKt, targetHeadingDeg;
  final bool lobingEnabled;
  final String reflectivityKey;
  final String antennaType; // 'generic' | 'phased_array'
  final double boresightDeg, maxScanDeg;
  final int clearCount, dopplerBlockedRays, failedRays;
  final List<RadarDopplerRay> rays;
}
