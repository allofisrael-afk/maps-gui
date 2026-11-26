// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/api_service.dart';
import '../services/file_bridge.dart';
import '../services/mpm_bridge.dart';
import 'map_state.dart';

/// בחירה מהמפה שממתינה ללחיצה הבאה: מכ"ם (בלי לפתוח את פאנל הדופלר) או מרכז שיוט.
enum RtPick { none, radar, loiter }

/// מצב כלי בדיקת מעקב המכ"ם באנדרואיד (שלב ג', MAPS-GUI_SRS.md FR-D-283). שוויון מלא לדסקטופ: 6 מקורות מסלול,
/// גילוי/מעקב ו-3 סוגי סריקה, RCS לפי זווית, גשם (ITU-R P.838-3), פרופילים, פרופיל שטח, הצעת מיקום.
/// החישוב עצמו ב-Python בתוך ה-APK (radar_android.py -> radar_service.py — אותו קוד כמו בשרת), כ-job ברקע:
/// הפעולה חוזרת מיד, ואנחנו שואלים על המצב כל שנייה (ה-Kotlin מריץ Python על ה-thread של הממשק).
/// מכ"ם ופרמטריו נלקחים מ-MapState (כלי הדופלר הקיים), בדיוק כמו בדסקטופ.
class RadarTrackController extends ChangeNotifier {
  MapState? _map; // המצב המשותף של המפה (מכ"ם, טיסה, מסלול מצויר)
  LatLng? _lastRunRadar; // מיקום המכ"ם בבדיקה האחרונה — כדי לזהות הזזה ולהריץ מחדש

  /// מחבר את הבקר ל-MapState: הזזת המכ"ם (גרירה/הצבה) מריצה מחדש בדיקה מוצגת, כמו בדסקטופ.
  void attach(MapState m) {
    if (identical(_map, m)) return; // כבר מחובר
    _map?.removeListener(_onMapChanged); // ניתוק קודם
    _map = m; // החיבור
    m.addListener(_onMapChanged); // מאזין
  }

  void _onMapChanged() {
    final r = _map?.radarObs; // המכ"ם הנוכחי
    if (r == null || running || result == null || _lastRunRadar == null) return; // אין מה להריץ מחדש
    if (r.latitude == _lastRunRadar!.latitude && r.longitude == _lastRunRadar!.longitude) return; // לא זז
    run(rerun: true); // אותו מסלול, מיקום מכ"ם חדש
  }

  // ── נתונים שהפאנל הבליסטי מפרסם (מסלול אחרון, משגר, מטאו) ──
  List<Map<String, dynamic>>? ballisticPath; // המסלול האחרון (מסלול בודד / פתרון ירי)
  Map<String, dynamic>? ballisticGun; // התותח — גם המשגר של הרקטה
  Map<String, dynamic>? ballisticMet; // המטאו שנבחר בפאנל הבליסטי

  void setBallistic({List<Map<String, dynamic>>? path, Map<String, dynamic>? gun, Map<String, dynamic>? met}) {
    if (path != null) ballisticPath = path; // מסלול חדש
    if (gun != null) ballisticGun = gun; // משגר
    if (met != null) ballisticMet = met; // מטאו
    if (path != null && lastOpts['source'] == 'ballistic') _clearResultOnly(); // בדיקה של המסלול הקודם — לא רלוונטית
    notifyListeners(); // ציור מחדש
  }

  // ── מקור המסלול ──
  String source = 'ballistic'; // ballistic | rocket | fr24 | custom | loiter | csv
  String altRef = 'agl'; // ייחוס גובה למצויר/שיוט/CSV
  double customSpeedKt = 90, customDefaultAlt = 300; // מסלול מצויר
  LatLng? loiterCenter; // שיוט
  double loiterRadius = 1500, loiterAlt = 300, loiterSpeedKt = 60; // שיוט
  int loiterLaps = 2; // שיוט
  bool loiterCw = true; // כיוון השיוט
  List<Map<String, dynamic>>? csvPoints; // מסלול מקובץ
  String csvLabel = ''; // מצב הטעינה
  bool frRcsAuto = true; // RCS לפי סוג המטוס
  double rkElev = 45, rkAz = 0, rkMass = 40, rkProp = 12, rkBurn = 2, rkThrust = 12000, rkDiam = 0.15, rkCd = 0.4; // רקטה
  List<Map<String, dynamic>>? rocketPath; // מסלול הרקטה האחרון — לציור

  // ── סריקה ומעקב ──
  String trackMode = 'track', scanMode = 'rotating'; // מצב וסוג סריקה
  double rotPeriod = 4, phase = 0, revisit = 0.5, trackRate = 10, maxAngRate = 30, cueDelay = 1, coast = 8; // פרמטרים
  int trackM = 2, trackN = 3; // M מתוך N

  // ── RCS וגשם ──
  String rcsMode = 'fixed', pol = 'h'; // מצב RCS וקיטוב
  double rcsNose = 0.01, rcsSide = 0.05, rcsTail = 0.02, rainRate = 0, rainTop = 3000; // ערכים

  // ── תצוגה ותוצאה ──
  bool showFan = true; // מניפת LOS
  bool running = false; // job רץ
  String status = ''; // שורת המצב/הסיכום
  Map<String, dynamic>? result; // התוצאה האחרונה
  Map<String, dynamic> lastOpts = {}; // המקור של הבדיקה האחרונה (source/alt_ref/rcs/label)
  List<Map<String, dynamic>>? lastTrajectory; // המסלול שנבדק — להרצה מחדש בהזזת המכ"ם
  String? _jobId; // ה-job הפעיל
  Timer? _poll; // polling
  Map<String, dynamic>? profile; // פרופיל שטח לנקודה שנבחרה
  String profileTitle = ''; // כותרתו
  RtPick pick = RtPick.none; // בחירה מהמפה שממתינה

  // ── הצעת מיקום ──
  double plRadiusKm = 3, plStepM = 500; // רדיוס ומרווח
  String plMetric = 'warning'; // הציון
  bool plRunning = false; // job רץ
  String plStatus = ''; // מצב
  Map<String, dynamic>? placement; // התוצאה
  String? _plJob; // ה-job
  Timer? _plPoll; // polling

  /// עדכון שדה מהפאנל + ציור מחדש.
  void update(void Function() mutate) {
    mutate(); // השינוי
    notifyListeners(); // ציור מחדש
  }

  // ═══════════════════════ פרמטרים ═══════════════════════

  /// פרמטרי המכ"ם מכלי הדופלר (MapState) — אותם שמות כמו בגוף הבקשה בדסקטופ.
  Map<String, dynamic> radarParams() {
    final s = _map!; // המצב
    return {
      'range_km': s.radarRangeKm, 'min_range_km': s.radarMinRangeKm, 'h_antenna': s.radarHAntenna,
      'ridge_margin_deg': s.radarRidgeMarginDeg, 'vertical_center_deg': s.radarVCenterDeg, 'vertical_width_deg': s.radarVWidthDeg,
      'power_kw': s.radarPowerKw, 'gain_dbi': s.radarGainDbi, 'freq_mhz': s.radarFreqMhz, 'sensitivity_dbm': s.radarSensitivityDbm,
      'rcs_m2': s.radarRcsM2, 'prf_hz': s.radarPrfHz, 'mdv_kt': s.radarMdvKt, 'lobing_enabled': s.radarLobingEnabled,
      'reflectivity': s.radarReflectivity, 'antenna_type': s.radarAntennaType, 'boresight_deg': s.radarBoresightDeg,
      'max_scan_deg': s.radarMaxScanDeg,
    };
  }

  /// סריקה ומעקב — אותם שמות כמו בדסקטופ.
  Map<String, dynamic> scanParams() => {
        'track_mode': trackMode, 'scan_mode': scanMode, 'rot_period_s': rotPeriod, 'scan_phase_deg': phase,
        'revisit_s': revisit, 'track_rate_hz': trackRate, 'max_ang_rate_dps': maxAngRate, 'cue_delay_s': cueDelay,
        'track_m': trackM, 'track_n': trackN, 'coast_s': coast,
      };

  /// RCS וגשם — אותם שמות כמו בדסקטופ.
  Map<String, dynamic> envParams() => {
        'rcs_mode': rcsMode, 'rcs_nose': rcsNose, 'rcs_side': rcsSide, 'rcs_tail': rcsTail,
        'rain_rate_mmh': rainRate, 'rain_top_m': rainTop, 'polarization': pol,
      };

  // ═══════════════════════ מקורות המסלול ═══════════════════════

  static const double _ktMs = 0.514444; // קשר -> מ'/ש'
  static const double _ftM = 0.3048; // רגל -> מטר

  static double _hav(double lat1, double lon1, double lat2, double lon2) {
    // מרחק במטרים (Haversine) — אותה נוסחה כמו במנוע
    const r = pi / 180, R = 6371000.0; // מקדמים
    final dl = (lat2 - lat1) * r, dn = (lon2 - lon1) * r; // הפרשים
    final h = sin(dl / 2) * sin(dl / 2) + cos(lat1 * r) * cos(lat2 * r) * sin(dn / 2) * sin(dn / 2); // Haversine
    return 2 * R * atan2(sqrt(h), sqrt(1 - h)); // מטרים
  }

  static LatLng _dest(LatLng c, double brg, double d) {
    // נקודת יעד ממקור, אזימוט ומרחק (כדורי) — לשיוט
    const r = pi / 180, R = 6371000.0; // מקדמים
    final p1 = c.latitude * r, l1 = c.longitude * r, th = brg * r, dl = d / R; // ברדיאנים
    final p2 = asin(sin(p1) * cos(dl) + cos(p1) * sin(dl) * cos(th)); // רוחב
    final l2 = l1 + atan2(sin(th) * sin(dl) * cos(p1), cos(dl) - sin(p1) * sin(p2)); // אורך
    return LatLng(p2 / r, ((l2 / r) + 540) % 360 - 180); // מעלות
  }

  /// זמן לכל קודקוד לפי מרחק מצטבר ומהירות (קבועה, או של הנקודה).
  static List<Map<String, dynamic>> _timesBySpeed(List<Map<String, dynamic>> verts, double speedMs) {
    double t = 0; // זמן מצטבר
    final out = <Map<String, dynamic>>[]; // התוצאה
    for (int i = 0; i < verts.length; i++) { // כל קודקוד
      final v = verts[i]; // הקודקוד
      if (i > 0) {
        final a = verts[i - 1]; // הקודם
        final spd = (v['spd_ms'] as double?) ?? speedMs; // המהירות
        t += _hav(a['lat'], a['lon'], v['lat'], v['lon']) / max(0.1, spd > 0 ? spd : speedMs); // זמן הקטע
      }
      out.add({'t': t, 'lat': v['lat'], 'lon': v['lon'], 'alt': v['alt']}); // נקודה
    }
    return out; // המסלול
  }

  /// קורא CSV של מסלול: t, lat, lon, alt — עם שורת כותרת בכל סדר (שמות כמו בדסקטופ) או בלעדיה.
  static List<Map<String, dynamic>>? parseCsv(String text) {
    var rows = text.replaceAll('\r', '').split('\n').map((l) => l.trim()).where((l) => l.isNotEmpty).toList(); // שורות
    if (rows.isEmpty) return []; // ריק
    var idx = {'t': 0, 'lat': 1, 'lon': 2, 'alt': 3}; // ברירת המחדל
    final first = rows.first.replaceFirst('﻿', '').split(RegExp(r'[,;\t]')).map((h) => h.trim().toLowerCase()).toList(); // כותרת?
    if (first.any((h) => RegExp(r'[a-z]').hasMatch(h))) { // יש אותיות — כותרת
      int find(List<String> names) => first.indexWhere((h) => names.contains(h)); // חיפוש
      idx = {'t': find(['t', 'time', 't_s', 'time_s']), 'lat': find(['lat', 'latitude']),
             'lon': find(['lon', 'lng', 'longitude']), 'alt': find(['alt', 'alt_m', 'alt_msl', 'altitude', 'height'])}; // מיפוי
      rows = rows.sublist(1); // בלי הכותרת
      if (idx.values.any((v) => v < 0)) return null; // חסרה עמודה
    }
    final pts = <Map<String, dynamic>>[]; // הנקודות
    for (final r in rows) { // כל שורה
      final c = r.split(RegExp(r'[,;\t]')); // עמודות
      double? at(int i) => i < c.length ? double.tryParse(c[i].trim()) : null; // ערך
      final t = at(idx['t']!), lat = at(idx['lat']!), lon = at(idx['lon']!), alt = at(idx['alt']!); // הערכים
      if (t != null && lat != null && lon != null && alt != null) pts.add({'t': t, 'lat': lat, 'lon': lon, 'alt': alt}); // תקינה
    }
    return pts; // המסלול
  }

  /// טוען CSV מחלון הקבצים.
  Future<void> loadCsv() async {
    try {
      final text = await FileBridge.openText(); // החלון
      if (text == null) return; // בוטל
      final pts = parseCsv(text); // פענוח
      csvPoints = (pts != null && pts.length >= 2) ? pts : null; // רק מסלול תקין
      csvLabel = pts == null ? 'חסרה עמודה (t, lat, lon, alt) בשורת הכותרת'
          : (pts.length >= 2 ? 'נטענו ${pts.length} נקודות ✔' : 'לא נמצאו מספיק נקודות תקינות'); // תוצאה
    } catch (e) {
      csvLabel = '$e'; // שגיאה
    }
    notifyListeners(); // ציור
  }

  /// בונה את המסלול מהמקור שנבחר (סינכרוני; הרקטה מטופלת ב-run). מחזיר null + status אם חסר משהו.
  List<Map<String, dynamic>>? _buildTrajectory() {
    final s = _map!; // המצב
    switch (source) {
      case 'ballistic':
        if (ballisticPath == null || ballisticPath!.length < 2) { status = 'חשב קודם מסלול בפאנל הבליסטי (מסלול בודד או פתרון ירי)'; return null; }
        lastOpts = {'source': 'ballistic', 'alt_ref': 'msl', 'label': 'מסלול בליסטי'}; // תמיד מעל פני הים
        return ballisticPath!.map((p) => {'t': p['t'], 'lat': p['lat'], 'lon': p['lon'], 'alt': p['alt_msl']}).toList();
      case 'fr24':
        final fd = s.flightData; // הטיסה שנטענה
        final tr = fd?.trail ?? const []; // המסלול שלה
        if (tr.length < 2) { status = 'טען קודם טיסה עם מסלול בכלי הטיסות'; return null; }
        final withTs = tr.where((p) => p.tsEpoch != null).toList(); // נקודות עם זמן אמיתי
        List<Map<String, dynamic>> pts; // הנקודות עם זמן
        if (withTs.length >= 2) { // יש זמנים
          final ts0 = withTs.map((p) => p.tsEpoch!).reduce(min); // הזמן הראשון
          pts = withTs.map((p) => <String, dynamic>{'t': p.tsEpoch! - ts0, 'lat': p.lat, 'lon': p.lng, 'alt': (p.altFt ?? 0) * _ftM}).toList(); // רגל -> מטר
        } else { // לפי מרחק ומהירות
          pts = _timesBySpeed(tr.map((p) => <String, dynamic>{'lat': p.lat, 'lon': p.lng, 'alt': (p.altFt ?? 0) * _ftM,
                                                              'spd_ms': p.spdKt != null ? p.spdKt! * _ktMs : null}).toList(), 120);
        }
        final rcs = frRcsAuto ? ApiService.rcsForAircraftType(fd?.aircraftIcao) : null; // RCS לפי סוג המטוס — אותה טבלה כמו בהערכת המסלול הקיימת
        lastOpts = {'source': 'fr24', 'alt_ref': 'msl', 'rcs_m2': rcs,
                    'label': 'טיסה ${fd?.callsign ?? ''}${rcs != null ? ' (RCS $rcs מ"ר)' : ''}${withTs.length >= 2 ? '' : ' — בלי זמנים, לפי מהירות'}'};
        return pts;
      case 'custom':
        final cr = s.customRoutePoints; // המסלול המצויר
        if (cr.length < 2) { status = 'צייר קודם מסלול (לפחות 2 נקודות) בכלי "מסלול טיסה מותאם"'; return null; }
        final verts = cr.map((p) => <String, dynamic>{'lat': p.lat, 'lon': p.lng, 'alt': p.altM ?? customDefaultAlt}).toList(); // קודקודים
        verts.add(verts.first); // סגירת הלולאה — כמו שהכלי מצייר
        lastOpts = {'source': 'custom', 'alt_ref': altRef, 'label': 'מסלול מצויר, ${customSpeedKt.toStringAsFixed(0)} קשר'};
        return _timesBySpeed(verts, customSpeedKt * _ktMs);
      case 'loiter':
        if (loiterCenter == null) { status = 'בחר קודם מרכז לשיוט'; return null; }
        final vs = <Map<String, dynamic>>[]; // קודקודים
        for (int k = 0; k <= loiterLaps * 36; k++) { // כל 10°
          final p = _dest(loiterCenter!, ((loiterCw ? 1 : -1) * k * 10 + 360000) % 360.0, loiterRadius); // על המעגל
          vs.add({'lat': p.latitude, 'lon': p.longitude, 'alt': loiterAlt}); // קודקוד
        }
        lastOpts = {'source': 'loiter', 'alt_ref': altRef, 'label': 'שיוט: רדיוס ${loiterRadius.toStringAsFixed(0)} מ\', $loiterLaps סיבובים'};
        return _timesBySpeed(vs, loiterSpeedKt * _ktMs);
      case 'csv':
        if (csvPoints == null || csvPoints!.length < 2) { status = 'טען קודם קובץ CSV של מסלול'; return null; }
        lastOpts = {'source': 'csv', 'alt_ref': altRef, 'label': 'קובץ CSV (${csvPoints!.length} נקודות)'};
        return csvPoints;
    }
    return null; // לא אמור לקרות
  }

  // ═══════════════════════ jobs ═══════════════════════

  /// מתחיל job ב-Python ושואל עליו כל שנייה. onProgress(טקסט), onDone(תוצאה), onError(הודעה).
  Future<String?> _startJob(String action, Map<String, dynamic> params, void Function(String) onProgress,
      void Function(Map<String, dynamic>) onDone, void Function(String) onError, void Function(Timer) keepTimer) async {
    final Map<String, dynamic> d;
    try {
      d = await MpmBridge.call(action, params); // ההתחלה (חוזרת מיד)
    } catch (e) {
      onError('$e'); // גישור נכשל
      return null;
    }
    if (d['ok'] != true || d['job_id'] == null) { onError((d['error'] ?? 'שגיאה').toString()); return null; } // קלט שגוי
    final jobId = d['job_id'] as String; // המזהה
    keepTimer(Timer.periodic(const Duration(seconds: 1), (t) async { // polling
      try {
        final st = await MpmBridge.call('radar_job_status', {'job_id': jobId}); // המצב
        final s = st['status']; // הסטטוס
        if (s == 'running') { // עדיין רץ
          final note = st['note']; // הודעה
          final tot = st['batches_total']; // שליפות
          onProgress(note != null ? '$note' : (tot != null ? 'שולף גבהי שטח… ${st['batches_done']}/$tot' : 'מחשב…'));
          return;
        }
        t.cancel(); // הסתיים
        if (s == 'done') { onDone((st['result'] as Map).cast<String, dynamic>()); }
        else if (s == 'cancelled') { onError('בוטל.'); }
        else { onError((st['error'] ?? 'שגיאה').toString()); }
      } catch (e) {
        // כשל בגישור בבדיקה בודדת — ה-tick הבא ינסה שוב
      }
    }));
    return jobId; // למעקב/ביטול
  }

  // ═══════════════════════ הבדיקה ═══════════════════════

  /// מריץ בדיקה מהמקור שנבחר (rerun=true: אותו מסלול, אחרי הזזת המכ"ם).
  Future<void> run({bool rerun = false}) async {
    final s = _map; // המצב
    if (s == null) return; // לא מחובר
    if (s.radarObs == null) { status = 'הצב קודם מכ"ם: "📍 הצב מכ"ם" כאן, או בכלי תצפית המכ"ם'; notifyListeners(); return; }
    cancel(silent: true); // בדיקה קודמת
    List<Map<String, dynamic>>? traj; // המסלול
    if (rerun && lastTrajectory != null) {
      traj = lastTrajectory; // אותו מסלול
    } else if (source == 'rocket') {
      await _runRocketThenCheck(); // הרקטה מחושבת קודם (job), והבדיקה רצה אחריה
      return;
    } else {
      traj = _buildTrajectory(); // מהמקור
    }
    if (traj == null) { notifyListeners(); return; } // חסר משהו — status כבר נקבע
    _runCheck(traj); // הבדיקה
  }

  void _runCheck(List<Map<String, dynamic>> traj) {
    final s = _map!; // המצב
    lastTrajectory = traj; // להרצה מחדש
    _lastRunRadar = s.radarObs; // המיקום שבו בודקים
    running = true; status = '🎯 בודק מעקב מכ"ם…'; profile = null; // משוב
    notifyListeners();
    final params = {...radarParams(), ...scanParams(), ...envParams(), 'lat': s.radarObs!.latitude, 'lon': s.radarObs!.longitude,
                    'trajectory': traj, 'alt_ref': lastOpts['alt_ref'] ?? 'msl'}; // הבקשה
    if (lastOpts['rcs_m2'] != null) params['rcs_m2'] = lastOpts['rcs_m2']; // RCS לפי סוג המטוס (FR24)
    _startJob('radar_check_start', params, (p) { status = '🎯 $p'; notifyListeners(); },
        (r) { running = false; result = r; status = summaryText(r); notifyListeners(); },
        (e) { running = false; status = '🎯 $e'; notifyListeners(); },
        (t) => _poll = t).then((id) => _jobId = id);
  }

  Future<void> _runRocketThenCheck() async {
    final gun = ballisticGun; // המשגר = התותח שבפאנל הבליסטי
    if (gun == null) { status = 'הזן קודם תותח (משגר) בפאנל הבליסטי וחשב מסלול אחד'; notifyListeners(); return; }
    running = true; status = '🚀 מחשב מסלול רקטה…'; notifyListeners(); // משוב
    _startJob('rocket_start', {
      'gun': gun, 'elev_deg': rkElev, 'azimuth_deg': rkAz, 'met': ballisticMet ?? {'source': 'standard'},
      'rocket': {'mass_kg': rkMass, 'prop_kg': rkProp, 'burn_s': rkBurn, 'thrust_n': rkThrust, 'diam_m': rkDiam, 'cd': rkCd},
    }, (p) {}, (d) {
      if (d['ok'] != true) { running = false; status = '🚀 ${d['message'] ?? d['error'] ?? 'שגיאה'}'; notifyListeners(); return; }
      rocketPath = (d['path'] as List).cast<Map>().map((m) => m.cast<String, dynamic>()).toList(); // לציור
      final imp = d['impact'] as Map, apex = d['apex'] as Map?, bo = d['burnout'] as Map; // נתונים
      lastOpts = {'source': 'rocket', 'alt_ref': 'msl',
                  'label': 'רקטה: טווח ${((imp['range_m'] as num) / 1000).toStringAsFixed(1)} ק"מ, שיא ${(apex?['alt_m'] as num? ?? 0).round()} מ\', '
                           'סוף בעירה בשנ\' ${bo['t']} ב-${(bo['v_ms'] as num).round()} מ\'/ש\''};
      _runCheck(rocketPath!.map((p) => {'t': p['t'], 'lat': p['lat'], 'lon': p['lon'], 'alt': p['alt_msl']}).toList()); // הבדיקה
    }, (e) { running = false; status = '🚀 $e'; notifyListeners(); }, (t) => _poll = t).then((id) => _jobId = id);
  }

  /// ביטול בדיקה רצה.
  void cancel({bool silent = false}) {
    _poll?.cancel(); _poll = null; // polling
    if (_jobId != null) { MpmBridge.call('radar_job_cancel', {'job_id': _jobId}).catchError((_) => <String, dynamic>{}); } // ביטול ב-Python
    _jobId = null; // אין job
    if (running && !silent) status = 'בוטל.'; // משוב
    running = false; // לא רץ
    if (!silent) notifyListeners(); // ציור
  }

  void _clearResultOnly() {
    cancel(silent: true); // job רץ
    result = null; profile = null; status = ''; lastTrajectory = null; // ניקוי
  }

  /// ניקוי מלא של הבדיקה מהמפה.
  void clear() {
    _clearResultOnly(); // ניקוי
    rocketPath = null; // מסלול הרקטה
    notifyListeners(); // ציור
  }

  /// פרופיל שטח לנקודה (לחיצה על קטע/קו במפה).
  Future<void> showProfile(Map<String, dynamic> p) async {
    final s = _map, r = result; // המצב והתוצאה
    if (s == null || r == null) return; // אין תוצאה
    profileTitle = 'פרופיל שטח לשנ\' ${p['t']}…'; profile = null; notifyListeners(); // משוב
    final radar = r['radar'] as Map; // המכ"ם של הבדיקה
    _startJob('radar_profile_start', {...radarParams(), 'lat': radar['lat'], 'lon': radar['lon'],
        'point': {'lat': p['lat'], 'lon': p['lon'], 'alt': p['alt']}}, (_) {}, (pr) {
      profile = pr; // הפרופיל
      profileTitle = 'LOS לשנ\' ${p['t']} (${((pr['dist_m'] as num) / 1000).toStringAsFixed(2)} ק"מ): '
          '${pr['visible'] == true ? 'פנוי ✔' : 'חסום ע"י שטח ב-${((pr['block_dist_m'] as num) / 1000).toStringAsFixed(2)} ק"מ ✖'}';
      notifyListeners();
    }, (e) { profileTitle = 'פרופיל: $e'; notifyListeners(); }, (timer) {}); // job קצר — הטיימר לא נשמר (נעצר לבד בסיום)
  }

  // ═══════════════════════ סיכום ═══════════════════════

  static const Map<String, String> reasonText = { // סיבה -> עברית (כמו בדסקטופ)
    'ok': 'מזוהה', 'terrain': 'חסום ע"י שטח', 'elevation': 'מחוץ לשדה-הראייה האנכי', 'sector': 'מחוץ לסקטור המערך',
    'radar_range': 'מעבר לתקרת המכ"ם', 'min_range': 'בתוך אזור העיוור הקרוב', 'doppler': 'עיוור לדופלר',
    'out_of_range': 'מחוץ לטווח הבדיקה', 'angular_rate': 'מהיר מדי לאנטנת המעקב', 'end': 'עד סוף המסלול',
    'rain': 'נחלש בגשם מעבר לטווח',
  };
  static const Map<String, String> scanNames = {'rotating': 'אנטנה מסתובבת', 'phased': 'מערך-מופע', 'tracker': 'מכ"ם מעקב ייעודי'};

  /// טקסט הסיכום — אותו תוכן כמו _radarTrackSummaryText בדסקטופ.
  String summaryText(Map<String, dynamic> r) {
    final s = r['summary'] as Map; // סיכום פיזיקלי
    final lines = <String>[]; // שורות
    if (lastOpts['label'] != null) lines.add('מקור: ${lastOpts['label']}'); // המקור
    final k = r['track'] as Map?, sc = r['scan'] as Map?; // מעקב
    if (k != null && sc != null) {
      lines.add('🎯 ${scanNames[sc['mode']] ?? sc['mode']}, ${sc['m']} מתוך ${sc['n']}: ' +
          (k['track_initiated'] == true ? 'מעקב נפתח ✔ בשנ\' ${(k['first_track_t'] as num).toStringAsFixed(1)} — זמן התרעה ${(k['warning_time_s'] as num).toStringAsFixed(1)} שנ\''
              : 'מעקב לא נפתח ✖'));
      lines.add('במעקב ${k['tracked_pct']}% מזמן המעוף | ${k['opportunities']} הזדמנויות, ${k['opp_detected']} גילויים');
      final tracks = (k['tracks'] as List).cast<Map>(); // המעקבים
      if (tracks.isNotEmpty) {
        lines.add('מעקבים: ' + tracks.map((tr) => '${(tr['t_start'] as num).toStringAsFixed(1)}–${(tr['t_end'] as num).toStringAsFixed(1)} שנ\' (${reasonText[tr['end_reason']] ?? tr['end_reason']})').join(' · '));
      }
    }
    final env = (r['env'] as Map?) ?? {}; // תנאים
    final envParts = <String>[]; // חלקים
    if (env['rcs_mode'] == 'aspect') envParts.add('RCS לפי זווית (${env['rcs_nose']}/${env['rcs_side']}/${env['rcs_tail']} מ"ר)');
    if ((env['rain_rate_mmh'] as num? ?? 0) > 0) envParts.add('גשם ${env['rain_rate_mmh']} מ"מ/שעה עד ${env['rain_top_m']} מ\' (ITU-R P.838-3)');
    if (envParts.isNotEmpty) lines.add(envParts.join(' · '));
    lines.add('${k != null ? 'פיזיקה' : '🎯 מכ"ם'}: ${s['detected_any'] == true ? 'נצפה ✔' : 'לא נצפה כלל ✖'} | כיסוי ${s['coverage_pct']}% מזמן המעוף (${s['duration_s']} שנ\')');
    final f = s['first_detection'] as Map?; // גילוי ראשון
    if (f != null) lines.add('גילוי ראשון: שנ\' ${f['t']}, טווח ${f['slant_km']} ק"מ, גובה ${(f['alt'] as num).round()} מ\'');
    final rs = (s['reason_seconds'] as Map).cast<String, dynamic>(); // אובדן לפי סיבה
    final lost = rs.entries.where((e) => e.key != 'ok' && (e.value as num) > 0).toList()
      ..sort((a, b) => (b.value as num).compareTo(a.value as num)); // מהגדול
    if (lost.isNotEmpty) lines.add('אובדן: ' + lost.map((e) => '${reasonText[e.key] ?? e.key} ${(e.value as num).toStringAsFixed(1)} שנ\'').join(' · '));
    final t = r['terrain'] as Map; // שטח
    lines.add('שטח: ${t['cells']} תאי-גובה (${t['cached'] ?? 0} מהמטמון${(t['missing'] as num) > 0 ? ', ${t['missing']} חסרים' : ''})');
    return lines.join('\n');
  }

  // ═══════════════════════ ייצוא CSV ═══════════════════════

  Future<String> exportCsv() async {
    final r = result; // התוצאה
    if (r == null) return 'הרץ קודם בדיקה';
    const cols = ['t', 'lat', 'lon', 'alt', 'dist_km', 'slant_km', 'bearing_deg', 'elev_deg', 'horizon_deg', 'radial_ms', 'speed_ms',
                  'ceiling_km', 'ang_rate_dps', 'aspect_deg', 'rcs_m2', 'rain_db', 'status', 'reason', 'track_state']; // כמו בדסקטופ
    final rows = (r['points'] as List).cast<Map>().map((p) => cols.map((c) => p[c] ?? '').join(',')); // שורות
    final csv = '﻿${cols.join(',')}\n${rows.join('\n')}'; // BOM — Excel מזהה UTF-8
    try {
      return await FileBridge.saveText('radar_track.csv', 'text/csv', csv) ? 'נשמר ✔' : 'בוטל'; // חלון השמירה
    } catch (e) {
      return '$e'; // שגיאה
    }
  }

  // ═══════════════════════ פרופילי מכ"ם (תואם לדסקטופ) ═══════════════════════

  static const _prefsKey = 'radar_track_profiles'; // מפתח השמירה המקומית

  /// הפרופיל הנוכחי — אותו פורמט ושמות שדות כמו בדסקטופ (maps-gui-radar-profile v1).
  Map<String, dynamic> currentProfile() => {
        ...radarParams(), ...scanParams(),
        'rcs_mode': rcsMode, 'rcs_nose': rcsNose, 'rcs_side': rcsSide, 'rcs_tail': rcsTail, // RCS (הגשם לא נכלל — תנאי סביבה)
      };

  /// מחיל פרופיל על השדות. מחזיר כמה שדות נטענו.
  int applyProfile(Map<String, dynamic> p) {
    int n = 0; // מונה
    double? d(String k) { final v = p[k]; if (v == null) return null; final x = v is num ? v.toDouble() : double.tryParse('$v'); if (x != null) n++; return x; } // מספר
    String? str(String k) { final v = p[k]; if (v == null) return null; n++; return '$v'; } // טקסט
    _map?.updateRadarParam(() { // שדות המכ"ם ב-MapState
      final s = _map!;
      s.radarRangeKm = d('range_km') ?? s.radarRangeKm; s.radarMinRangeKm = d('min_range_km') ?? s.radarMinRangeKm;
      s.radarHAntenna = d('h_antenna') ?? s.radarHAntenna; s.radarRidgeMarginDeg = d('ridge_margin_deg') ?? s.radarRidgeMarginDeg;
      s.radarVCenterDeg = d('vertical_center_deg') ?? s.radarVCenterDeg; s.radarVWidthDeg = d('vertical_width_deg') ?? s.radarVWidthDeg;
      s.radarPowerKw = d('power_kw') ?? s.radarPowerKw; s.radarGainDbi = d('gain_dbi') ?? s.radarGainDbi;
      s.radarFreqMhz = d('freq_mhz') ?? s.radarFreqMhz; s.radarSensitivityDbm = d('sensitivity_dbm') ?? s.radarSensitivityDbm;
      s.radarRcsM2 = d('rcs_m2') ?? s.radarRcsM2; s.radarPrfHz = d('prf_hz') ?? s.radarPrfHz; s.radarMdvKt = d('mdv_kt') ?? s.radarMdvKt;
      final lob = p['lobing_enabled']; if (lob != null) { s.radarLobingEnabled = lob == true || '$lob' == 'true'; n++; }
      s.radarReflectivity = str('reflectivity') ?? s.radarReflectivity; s.radarAntennaType = str('antenna_type') ?? s.radarAntennaType;
      s.radarBoresightDeg = d('boresight_deg') ?? s.radarBoresightDeg; s.radarMaxScanDeg = d('max_scan_deg') ?? s.radarMaxScanDeg;
    });
    trackMode = str('track_mode') ?? trackMode; scanMode = str('scan_mode') ?? scanMode; // סריקה
    rotPeriod = d('rot_period_s') ?? rotPeriod; phase = d('scan_phase_deg') ?? phase; revisit = d('revisit_s') ?? revisit;
    trackRate = d('track_rate_hz') ?? trackRate; maxAngRate = d('max_ang_rate_dps') ?? maxAngRate; cueDelay = d('cue_delay_s') ?? cueDelay;
    trackM = (d('track_m') ?? trackM.toDouble()).round(); trackN = (d('track_n') ?? trackN.toDouble()).round(); coast = d('coast_s') ?? coast;
    rcsMode = str('rcs_mode') ?? rcsMode; rcsNose = d('rcs_nose') ?? rcsNose; rcsSide = d('rcs_side') ?? rcsSide; rcsTail = d('rcs_tail') ?? rcsTail; // RCS
    notifyListeners(); // ציור
    return n; // כמה נטענו
  }

  Future<Map<String, dynamic>> _loadStore() async {
    final prefs = await SharedPreferences.getInstance(); // אחסון מקומי
    final raw = prefs.getString(_prefsKey); // ה-JSON
    if (raw == null) return {}; // ריק
    try { return (jsonDecode(raw) as Map).cast<String, dynamic>(); } catch (_) { return {}; } // פגום = ריק
  }

  Future<List<String>> profileNames() async => (await _loadStore()).keys.toList()..sort(); // השמות

  Future<void> saveProfile(String name) async {
    final store = await _loadStore(); // הקיים
    store[name] = currentProfile(); // הוספה/דריסה
    final prefs = await SharedPreferences.getInstance(); // אחסון
    await prefs.setString(_prefsKey, jsonEncode(store)); // שמירה
  }

  Future<int> loadProfile(String name) async {
    final p = (await _loadStore())[name]; // הפרופיל
    return p == null ? 0 : applyProfile((p as Map).cast<String, dynamic>()); // החלה
  }

  Future<void> deleteProfile(String name) async {
    final store = await _loadStore(); // הקיים
    store.remove(name); // מחיקה
    final prefs = await SharedPreferences.getInstance(); // אחסון
    await prefs.setString(_prefsKey, jsonEncode(store)); // שמירה
  }

  Future<String> exportProfileJson() async {
    final doc = {'format': 'maps-gui-radar-profile', 'version': 1, 'params': currentProfile()}; // אותו פורמט כמו בדסקטופ
    try {
      return await FileBridge.saveText('radar_profile.json', 'application/json', const JsonEncoder.withIndent('  ').convert(doc))
          ? 'נשמר ✔' : 'בוטל'; // חלון השמירה
    } catch (e) {
      return '$e';
    }
  }

  Future<String> importProfileJson() async {
    try {
      final text = await FileBridge.openText(); // חלון הפתיחה
      if (text == null) return 'בוטל';
      final doc = jsonDecode(text); // פענוח
      if (doc is! Map || doc['format'] != 'maps-gui-radar-profile' || doc['params'] is! Map) return 'זה לא קובץ פרופיל מכ"ם של maps-gui';
      return 'נטענו ${applyProfile((doc['params'] as Map).cast<String, dynamic>())} שדות מהפרופיל ✔';
    } on FormatException {
      return 'הקובץ אינו JSON תקין';
    } catch (e) {
      return '$e';
    }
  }

  // ═══════════════════════ הצעת מיקום (שלב ב') ═══════════════════════

  void runPlacement() {
    final s = _map; // המצב
    if (s?.radarObs == null) { plStatus = 'הצב קודם מכ"ם — החיפוש סביבו'; notifyListeners(); return; }
    if (lastTrajectory == null) { plStatus = 'הרץ קודם בדיקת מעקב — מפת החום נבנית על המסלול שלה'; notifyListeners(); return; }
    cancelPlacement(silent: true); placement = null; // הרצה קודמת
    plRunning = true; plStatus = '🗺 מתחיל…'; notifyListeners(); // משוב
    final params = {...radarParams(), ...scanParams(), ...envParams(), 'lat': s!.radarObs!.latitude, 'lon': s.radarObs!.longitude,
                    'radius_km': plRadiusKm, 'step_m': plStepM, 'metric': plMetric, 'trajectory': lastTrajectory,
                    'alt_ref': lastOpts['alt_ref'] ?? 'msl'}; // אותם פרמטרים כמו בבדיקה
    if (lastOpts['rcs_m2'] != null) params['rcs_m2'] = lastOpts['rcs_m2']; // RCS של FR24
    _startJob('radar_placement_start', params, (p) { plStatus = '🗺 $p'; notifyListeners(); }, (r) {
      plRunning = false; placement = r; // התוצאה
      final b = (r['best'] as List).isNotEmpty ? (r['best'] as List).first as Map : null; // המיטבי
      final unit = plMetric == 'coverage' ? '%' : ' שנ\''; // יחידה
      final dem = r['dem'] as Map; // הרשת
      plStatus = '🗺 ${(r['candidates'] as List).length} מיקומים | המיטבי: ${b?['score']}$unit (קרקע ${b?['ground_m']} מ\')\n'
          'רשת גבהים: ${dem['nodes']} נקודות, ~${dem['res_m']} מ\' (${dem['cached']} מהמטמון)\nלחץ על תא או על ⭐ כדי להציב שם את המכ"ם.';
      notifyListeners();
    }, (e) { plRunning = false; plStatus = '🗺 $e'; notifyListeners(); }, (t) => _plPoll = t).then((id) => _plJob = id);
  }

  void cancelPlacement({bool silent = false}) {
    _plPoll?.cancel(); _plPoll = null; // polling
    if (_plJob != null) { MpmBridge.call('radar_job_cancel', {'job_id': _plJob}).catchError((_) => <String, dynamic>{}); } // ביטול
    _plJob = null; // אין job
    if (plRunning && !silent) plStatus = 'בוטל.'; // משוב
    plRunning = false; // לא רץ
    if (!silent) notifyListeners(); // ציור
  }

  void clearPlacement() { cancelPlacement(silent: true); placement = null; plStatus = ''; notifyListeners(); } // ניקוי

  /// מציב את המכ"ם במיקום מוצע (לחיצה על תא/⭐) — הבדיקה רצה מחדש אוטומטית דרך המאזין.
  void placeRadarAt(LatLng p) => _map?.setRadarObserver(p);

  /// לחיצה על המפה כשבחירה ממתינה. מחזיר true אם הלחיצה טופלה כאן.
  bool handleMapTap(LatLng p) {
    if (pick == RtPick.none) return false; // לא שלנו
    if (pick == RtPick.radar) { _map?.setRadarObserver(p); } // הצבת מכ"ם
    else { loiterCenter = p; } // מרכז שיוט
    pick = RtPick.none; // הבחירה הסתיימה
    notifyListeners(); // ציור
    return true; // טופל
  }

  @override
  void dispose() {
    _map?.removeListener(_onMapChanged); // ניתוק
    _poll?.cancel(); _plPoll?.cancel(); // polling
    super.dispose();
  }
}
