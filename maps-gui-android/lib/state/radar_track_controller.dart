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
    _syncSiteFromMap(); // FR-D-288: מיקום/שדות הצבה/סוג "שלי" — מסונכרנים בין הכלים ונשמרים במכ"ם הפעיל
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
    _syncSiteFromMap(); // FR-D-288: שדה סריקה של סוג "שלי" — נשמר לפרופיל
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
    runProfileLbl = activeLabel(); // FR-D-286: הפרופיל שהיה פעיל כשהבדיקה התחילה — לסיכום ול-CSV
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
    if (runProfileLbl.isNotEmpty) lines.add('📡 $runProfileLbl'); // FR-D-286: לפי איזה פרופיל חושב
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
    final prof = '"${runProfileLbl.replaceAll('"', '""')}"'; // FR-D-286: עמודת הפרופיל — במירכאות, כי השם עלול לכלול פסיק
    final rows = (r['points'] as List).cast<Map>().map((p) => [...cols.map((c) => p[c] ?? ''), prof].join(',')); // שורות + הפרופיל
    final csv = '﻿${[...cols, 'profile'].join(',')}\n${rows.join('\n')}'; // BOM — Excel מזהה UTF-8
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
    _map?.applyRadarParams(() { // שדות המכ"ם ב-MapState — FR-D-286: applyRadarParams כדי שפאנל הדופלר יסנכרן את כל השדות
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
    await refreshMyProfiles(); // FR-D-286: בורר הפרופיל הפעיל מתעדכן
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
    await refreshMyProfiles(); // FR-D-286: בורר הפרופיל הפעיל מתעדכן (ואם הפעיל נמחק — חוזרים ל"ידני")
  }

  // ═══════════════════════ מכ"מים מוצבים (FR-D-288) ═══════════════════════
  // סוג מכ"ם = פרופיל (ספרייה מובנית / הפרופילים שלי). מכ"ם מוצב = סוג + פרמטרים של הצבה: מיקום, כיוון פנים, גובה אנטנה,
  // סקטור, טווח, משטח וריבוד. מכ"ם פעיל אחד שכל הכלים עובדים עליו; נתוני המטרה (RCS, מהירות) נשארים בכל כלי;
  // שדות של סוג מהספרייה נעולים ("שכפל לעריכה" יוצר עותק פתוח). אותו מודל ואותו קובץ JSON כמו בדסקטופ.

  List<Map<String, dynamic>> library = []; // סוגי מכ"ם מהספרייה המובנית (radar-profiles/ בתוך ה-APK, לקריאה בלבד)
  bool _libRequested = false; // נטענת פעם אחת
  int _libRetries = 0; // ניסיונות חוזרים לטעינת הספרייה
  List<String> myProfileNames = []; // סוגי מכ"ם של המשתמש (מקומית בטלפון)
  Map<String, dynamic> _myStore = {}; // שם -> פרמטרים של הסוגים שלי (עותק בזיכרון לגישה סינכרונית)
  static const typeKeys = ['min_range_km', 'vertical_center_deg', 'vertical_width_deg', 'power_kw', 'gain_dbi', 'freq_mhz', 'sensitivity_dbm',
      'prf_hz', 'mdv_kt', 'antenna_type', 'max_scan_deg', 'scan_mode', 'rot_period_s', 'revisit_s', 'track_rate_hz', 'max_ang_rate_dps',
      'cue_delay_s', 'track_m', 'track_n', 'coast_s']; // שדות שמגיעים מסוג המכ"ם (זהה לדסקטופ)
  static const _sitesPrefsKey = 'radar_sites_v1'; // מפתח השמירה המקומית של המכ"מים המוצבים
  List<Map<String, dynamic>> sites = []; // המכ"מים המוצבים: [{name, params}]
  String activeSite = ''; // שם המכ"ם הפעיל; '' = ידני
  Map<String, bool> detached = {'los': false, 'radial': false}; // "צופה נפרד" לכלי
  bool sitePick = false; // הלחיצה הבאה על המפה ממקמת את המכ"ם הפעיל
  bool _sitesLoaded = false; // המכ"מים נטענו מהאחסון
  bool _applying = false; // שינוי פנימי — לא לסנכרן חזרה
  Map<String, dynamic> _lastSite = {}, _lastRadialSite = {}, _lastType = {}; // ערכים בסנכרון האחרון — לזיהוי מה השתנה
  LatLng? _lastLoc, _lastRadialObs; // מיקומים בסנכרון האחרון
  Map<String, dynamic> _lastLosSite = {}; // FR-D-290: שדות ההצבה בקו הראייה בסנכרון האחרון
  Timer? _siteSaveTimer, _typeSaveTimer; // שמירות מושהות
  String runProfileLbl = ''; // המכ"ם שהיה פעיל כשבדיקת המעקב האחרונה התחילה
  String plProfileLbl = ''; // אותו דבר למפת החום
  String dopplerProfileLbl = ''; // אותו דבר לכיסוי הדופלר (נלכד בלחיצה על "הפעל חישוב")
  String routeEvalProfileLbl = ''; // אותו דבר להערכת מסלול הטיסה

  /// טוען את הספרייה המובנית מ-Python (פעם אחת), את הסוגים שלי ואת המכ"מים המוצבים.
  Future<void> loadLibrary() async {
    if (!_libRequested) { // פעם אחת
      _libRequested = true;
      try {
        final d = await MpmBridge.call('radar_profiles_library', {}); // קריאה סינכרונית קצרה ב-Python
        library = ((d['profiles'] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList(); // הרשימה
      } catch (_) {
        library = []; // כשל בגישור
      }
      if (library.isEmpty) { // לא נטען (Python עוד עולה / כשל) — ניסיון חוזר עד 10 פעמים כל 2 שנ'
        _libRequested = false; // יאפשר ניסיון נוסף
        if (_libRetries++ < 10) Future.delayed(const Duration(seconds: 2), loadLibrary);
      }
    }
    await refreshMyProfiles(); // הסוגים שלי
    if (!_sitesLoaded) { _sitesLoaded = true; await _loadSites(); } // המכ"מים המוצבים (פעם אחת)
  }

  /// מרענן את הסוגים שלי (עותק בזיכרון + שמות).
  Future<void> refreshMyProfiles() async {
    _myStore = await _loadStore(); // מהאחסון
    myProfileNames = _myStore.keys.toList()..sort(); // השמות
    notifyListeners(); // ציור
  }

  Future<void> _loadSites() async {
    // טוען את המכ"מים המוצבים, את הניתוק ואת המכ"ם הפעיל מההפעלה הקודמת (ברירת מחדל: ידני)
    final prefs = await SharedPreferences.getInstance(); // אחסון
    final raw = prefs.getString(_sitesPrefsKey); // ה-JSON
    if (raw == null) return; // אין עדיין
    try {
      final d = jsonDecode(raw) as Map; // פענוח
      sites = ((d['sites'] as List?) ?? const []).whereType<Map>().map(_normSite).toList(); // הרשימה
      final det = d['detached'] as Map?; // ניתוק
      if (det != null) detached = {'los': det['los'] == true, 'radial': det['radial'] == true};
      final a = '${d['active'] ?? ''}'; // הפעיל
      if (a.isNotEmpty && sites.any((s) => s['name'] == a)) { await activateSite(a); } else { notifyListeners(); } // שחזור
    } catch (_) {
      // קובץ פגום — מתחילים ריק, בלי לדרוס עד השמירה הבאה
    }
  }

  static Map<String, dynamic> _normSite(Map m) => {'name': '${m['name']}', 'params': Map<String, dynamic>.from((m['params'] as Map?) ?? const {})}; // מבנה אחיד

  Future<void> _saveSites() async {
    // שמירת הרשימה, המכ"ם הפעיל והניתוק — עם שדה גרסה
    final prefs = await SharedPreferences.getInstance(); // אחסון
    await prefs.setString(_sitesPrefsKey, jsonEncode({'v': 1, 'sites': sites, 'active': activeSite, 'detached': detached})); // שמירה
  }

  void _saveSitesSoon() { _siteSaveTimer?.cancel(); _siteSaveTimer = Timer(const Duration(milliseconds: 600), _saveSites); } // שמירה מושהית

  void _saveTypeSoon(String name, Map<String, dynamic> params) {
    // שמירה מושהית של סוג "שלי" שנערך
    _typeSaveTimer?.cancel();
    _typeSaveTimer = Timer(const Duration(milliseconds: 800), () async {
      final store = await _loadStore(); store[name] = params; // עדכון
      final prefs = await SharedPreferences.getInstance(); await prefs.setString(_prefsKey, jsonEncode(store)); // שמירה
    });
  }

  /// סוג מכ"ם לפי מפתח: 'lib:<קובץ>' (יציב) או 'my:<שם>'.
  Map<String, dynamic>? typeOf(String? key) {
    if (key == null) return null; // אין
    if (key.startsWith('lib:')) { // מהספרייה
      final f = key.substring(4);
      for (final p in library) {
        if (p['file'] == f) return {'key': key, 'name': '${p['name']}', 'params': (p['params'] as Map).cast<String, dynamic>(), 'notes': (p['notes'] as Map?)?.cast<String, dynamic>(), 'lib': true};
      }
      return null; // לא נמצא
    }
    if (key.startsWith('my:')) { // שלי
      final n = key.substring(3), p = _myStore[n];
      return p == null ? null : {'key': key, 'name': n, 'params': (p as Map).cast<String, dynamic>(), 'notes': null, 'lib': false};
    }
    return null; // לא מוכר
  }

  /// המכ"ם הפעיל (null = ידני).
  Map<String, dynamic>? get site { for (final s in sites) { if (s['name'] == activeSite) return s; } return null; }

  Map<String, dynamic> get _sp => (site?['params'] as Map<String, dynamic>?) ?? <String, dynamic>{}; // פרמטרי המכ"ם הפעיל

  String siteTypeName(Map<String, dynamic> s) { final p = s['params'] as Map; final t = typeOf(p['type_key'] as String?); return t != null ? '${t['name']}' : '${p['type_name'] ?? '?'}'; } // שם הסוג

  /// האם שדות הסוג נעולים (סוג מהספרייה); בכלי מנותק — לא.
  bool lockedFor(String tool) { if (site == null || (detached[tool] ?? false)) return false; final t = typeOf(_sp['type_key'] as String?); return t != null && t['lib'] == true; }

  /// סוג המכ"ם הפעיל (למקורות ולכפתור השכפול).
  Map<String, dynamic>? get activeType => site == null ? null : typeOf(_sp['type_key'] as String?);

  Map<String, dynamic>? get activeNotes => activeType?['notes'] as Map<String, dynamic>?; // מה פורסם ומה הונח

  /// התווית שנכתבת על כל תוצאה.
  String activeLabel() { final s = site; return s == null ? 'מכ"ם: ידני (ללא מכ"ם)' : 'מכ"ם: ${s['name']} (${siteTypeName(s)})'; }

  /// טקסט המקורות של סוג מהספרייה: מה פורסם (עם הקישור) ומה הונח.
  String notesText() {
    final n = activeNotes; // המקורות
    if (n == null) return ''; // אין
    final lines = <String>[]; // שורות
    if (n['system'] != null) lines.add('${n['system']}'); // תיאור המערכת
    final pub = (n['published'] as Map?) ?? const {}; // מה פורסם
    if (pub.isNotEmpty) { lines.addAll(['', 'פורסם:']); pub.forEach((k, v) => lines.addAll(['• $k', '   $v'])); } // נתון + מקור
    final asm = (n['assumed_not_published'] as Map?) ?? const {}; // מה הונח
    if (asm.isNotEmpty) { lines.addAll(['', 'הונח (לא פורסם):']); asm.forEach((k, v) => lines.add('• $k: $v')); } // הנחה + סיבה
    return lines.join('\n'); // הטקסט
  }

  /// נלכד בלחיצה על "הפעל חישוב" בפאנל הדופלר — לפי איזה מכ"ם חושב הכיסוי.
  void markDopplerRun() => dopplerProfileLbl = activeLabel();

  /// נלכד בלחיצה על "הערך מסלול טיסה מול המכ"ם".
  void markRouteEvalRun() => routeEvalProfileLbl = activeLabel();

  // ── קריאה/כתיבה של שדות ההצבה והסוג בכלים ──
  Map<String, dynamic> _radarSiteVals() { final m = _map!; return {'h_antenna': m.radarHAntenna, 'start_bearing_deg': m.radarStartBearingDeg,
      'end_bearing_deg': m.radarEndBearingDeg, 'angle_step_deg': m.radarAngleStepDeg, 'range_km': m.radarRangeKm, 'ridge_margin_deg': m.radarRidgeMarginDeg,
      'boresight_deg': m.radarBoresightDeg, 'reflectivity': m.radarReflectivity, 'lobing_enabled': m.radarLobingEnabled}; } // פאנל הדופלר

  Map<String, dynamic> _radialSiteVals() { final m = _map!; return {'h_antenna': m.radialObsH, 'start_bearing_deg': m.radialStartBearingDeg,
      'end_bearing_deg': m.radialEndBearingDeg, 'angle_step_deg': m.radialAngleStepDeg, 'range_km': m.radialRangeKm, 'ridge_margin_deg': m.radialRidgeMarginDeg}; } // רדיוס הראייה

  Map<String, dynamic> _typeVals() { final cp = currentProfile(); return {for (final k in typeKeys) if (cp.containsKey(k)) k: cp[k]}; } // שדות הסוג (דופלר + סריקה)

  Map<String, dynamic> _radialTypeVals() { final m = _map!; return {'min_range_km': m.radialMinRangeKm, 'vertical_center_deg': m.radialVCenterDeg, 'vertical_width_deg': m.radialVWidthDeg}; }

  void _writeSite(Map<String, dynamic> p) {
    // מחיל את שדות ההצבה על כל הכלים המחוברים
    final m = _map!; // המצב
    double? d(String k) => (p[k] as num?)?.toDouble(); // מספר
    m.applyRadarParams(() {
      m.radarHAntenna = d('h_antenna') ?? m.radarHAntenna; m.radarStartBearingDeg = d('start_bearing_deg') ?? m.radarStartBearingDeg;
      m.radarEndBearingDeg = d('end_bearing_deg') ?? m.radarEndBearingDeg; m.radarAngleStepDeg = d('angle_step_deg') ?? m.radarAngleStepDeg;
      m.radarRangeKm = d('range_km') ?? m.radarRangeKm; m.radarRidgeMarginDeg = d('ridge_margin_deg') ?? m.radarRidgeMarginDeg;
      m.radarBoresightDeg = d('boresight_deg') ?? m.radarBoresightDeg;
      if (p['reflectivity'] != null) m.radarReflectivity = '${p['reflectivity']}';
      if (p['lobing_enabled'] != null) m.radarLobingEnabled = p['lobing_enabled'] == true || '${p['lobing_enabled']}' == 'true';
    });
    if (!(detached['radial'] ?? false)) {
      m.applyRadialParams(() {
        m.radialObsH = d('h_antenna') ?? m.radialObsH; m.radialStartBearingDeg = d('start_bearing_deg') ?? m.radialStartBearingDeg;
        m.radialEndBearingDeg = d('end_bearing_deg') ?? m.radialEndBearingDeg; m.radialAngleStepDeg = d('angle_step_deg') ?? m.radialAngleStepDeg;
        m.radialRangeKm = d('range_km') ?? m.radialRangeKm; m.radialRidgeMarginDeg = d('ridge_margin_deg') ?? m.radialRidgeMarginDeg;
      });
    }
    if (!(detached['los'] ?? false)) { // קו הראייה — גובה צופה, ו-FR-D-290: מרווח רכס וגזרה
      m.losObsH = d('h_antenna') ?? m.losObsH; m.losMarginDeg = d('ridge_margin_deg') ?? m.losMarginDeg;
      m.losSecStart = d('start_bearing_deg') ?? m.losSecStart; m.losSecEnd = d('end_bearing_deg') ?? m.losSecEnd;
    }
  }

  Map<String, dynamic> _losSiteVals() { final m = _map!; return {'h_antenna': m.losObsH, 'ridge_margin_deg': m.losMarginDeg,
      'start_bearing_deg': m.losSecStart, 'end_bearing_deg': m.losSecEnd}; } // FR-D-290: שדות ההצבה שמופיעים בקו הראייה

  void _writeRadialType(Map<String, dynamic> tp) {
    // שדות הסוג שמופיעים גם ברדיוס הראייה (טווח מינימלי, שדה ראייה אנכי)
    if (_map == null || (detached['radial'] ?? false)) return; // מנותק
    final m = _map!; double? d(String k) => (tp[k] as num?)?.toDouble(); // מספר
    m.applyRadialParams(() {
      m.radialMinRangeKm = d('min_range_km') ?? m.radialMinRangeKm; m.radialVCenterDeg = d('vertical_center_deg') ?? m.radialVCenterDeg;
      m.radialVWidthDeg = d('vertical_width_deg') ?? m.radialVWidthDeg;
    });
  }

  void _snapAll() {
    // תמונת המצב אחרי סנכרון — כדי לזהות בפעם הבאה מה המשתמש שינה ובאיזה כלי
    final m = _map; if (m == null) return;
    _lastSite = _radarSiteVals(); _lastRadialSite = _radialSiteVals(); _lastType = {..._typeVals(), ..._radialTypeVals()};
    _lastLoc = m.radarObs; _lastRadialObs = m.radialLosObs; _lastLosSite = _losSiteVals(); // FR-D-290
  }

  void _moveObservers(LatLng ll, String? source) {
    // מיקום משותף: המכ"ם (דופלר + מעקב) ורדיוס הראייה אם מחובר ופתוח. source = הכלי שממנו הגיע השינוי
    final m = _map!; _applying = true; // מונע לולאת עדכונים
    try {
      if (source != 'radar' && m.radarObs != ll) m.setRadarObserver(ll); // המכ"ם
      if (source != 'radial' && !(detached['radial'] ?? false) && m.radialLosMode && m.radialLosObs != ll) m.setRadialLosObserver(ll); // רדיוס הראייה
    } finally { _applying = false; }
  }

  /// נקרא בכל שינוי ב-MapState ובכל update של הבקר: מסנכרן מיקום, שדות הצבה וסוג "שלי" בין הכלים.
  void _syncSiteFromMap() {
    if (_applying || _map == null) return; // שינוי פנימי
    final s = site; if (s == null) return; // ידני — הכלים עצמאיים
    final m = _map!, p = s['params'] as Map<String, dynamic>; // המצב
    var dirty = false; // נדרשת שמירה
    if (m.radarObs != null && m.radarObs != _lastLoc) { // המכ"ם זז
      p['lat'] = m.radarObs!.latitude; p['lon'] = m.radarObs!.longitude; dirty = true; _moveObservers(m.radarObs!, 'radar');
    } else if (!(detached['radial'] ?? false) && m.radialLosObs != null && m.radialLosObs != _lastRadialObs && m.radialLosObs != _lastLoc) { // רדיוס הראייה זז
      p['lat'] = m.radialLosObs!.latitude; p['lon'] = m.radialLosObs!.longitude; dirty = true; _moveObservers(m.radialLosObs!, 'radial');
    }
    final changed = <String, dynamic>{}; // שדות הצבה שהשתנו
    _radarSiteVals().forEach((k, v) { if (v != _lastSite[k]) changed[k] = v; });
    if (!(detached['radial'] ?? false)) _radialSiteVals().forEach((k, v) { if (v != _lastRadialSite[k]) changed[k] = v; });
    if (!(detached['los'] ?? false)) _losSiteVals().forEach((k, v) { if (v != _lastLosSite[k]) changed[k] = v; }); // FR-D-290: גובה צופה, מרווח רכס וגזרה
    if (changed.isNotEmpty) { p.addAll(changed); dirty = true; _applying = true; try { _writeSite(p); } finally { _applying = false; } } // לכל הכלים
    final t = typeOf(p['type_key'] as String?); // הסוג
    if (t != null && t['lib'] != true) { // סוג שלי — עריכה חופשית שנשמרת לפרופיל
      final tv = {..._typeVals(), if (!(detached['radial'] ?? false)) ..._radialTypeVals()}; // ערכים נוכחיים
      final tch = <String, dynamic>{}; tv.forEach((k, v) { if (v != _lastType[k]) tch[k] = v; }); // שינויים
      if (tch.isNotEmpty) {
        final tp = t['params'] as Map<String, dynamic>; tp.addAll(tch); _myStore['${t['name']}'] = tp; // בפרופיל
        _applying = true; try { applyProfile(Map.of(tch)); _writeRadialType(tch); } finally { _applying = false; } // לשאר הכלים
        _saveTypeSoon('${t['name']}', tp); // שמירה
      }
    }
    _snapAll(); // תמונה חדשה
    if (dirty) { _saveSitesSoon(); notifyListeners(); } // שמירה + ציור
  }

  /// בחירת מכ"ם פעיל: שדות הסוג (בלי RCS), שדות ההצבה, וכל הצופים למיקום שלו. '' = ידני.
  Future<void> activateSite(String name) async {
    Map<String, dynamic>? s; for (final x in sites) { if (x['name'] == name) s = x; } // המכ"ם
    activeSite = s == null ? '' : name; // הפעיל
    if (s != null && _map != null) {
      final p = s['params'] as Map<String, dynamic>, t = typeOf(p['type_key'] as String?); // ההצבה והסוג
      _applying = true; // מונע לולאת עדכונים
      try {
        if (t != null) { final tp = t['params'] as Map<String, dynamic>; final sub = {for (final k in typeKeys) if (tp[k] != null) k: tp[k]}; applyProfile(sub); _writeRadialType(sub); } // הסוג
        _writeSite(p); // ההצבה
        final lat = (p['lat'] as num?)?.toDouble(), lon = (p['lon'] as num?)?.toDouble(); // מיקום
        if (lat != null && lon != null) _moveObservers(LatLng(lat, lon), null);
      } finally { _applying = false; }
      _snapAll(); // תמונה
    }
    _saveSitesSoon(); notifyListeners(); // שמירה + ציור
  }

  /// ברירות מחדל למכ"ם מוצב חדש (זהה לדסקטופ): גובה אנטנה וטווח מהסוג; סקטור = כיוון פנים ± זווית סריקה, או 360°.
  Map<String, dynamic> siteDefaults(String typeKey, LatLng? ll) {
    final t = typeOf(typeKey), tp = (t?['params'] as Map<String, dynamic>?) ?? const <String, dynamic>{}; // הסוג
    final phased = tp['antenna_type'] == 'phased_array', ms = (tp['max_scan_deg'] as num?)?.toDouble() ?? 60.0; // מערך מופע
    return {'type_key': typeKey, 'type_name': t?['name'] ?? '', 'lat': ll?.latitude, 'lon': ll?.longitude, 'boresight_deg': 0.0,
        'h_antenna': (tp['h_antenna'] as num?)?.toDouble() ?? 10.0, 'range_km': (tp['range_km'] as num?)?.toDouble() ?? 50.0,
        'start_bearing_deg': phased ? (360 - ms) % 360 : 0.0, 'end_bearing_deg': phased ? ms : 360.0, 'angle_step_deg': 10.0,
        'reflectivity': tp['reflectivity'] ?? 'land', 'lobing_enabled': false, 'ridge_margin_deg': 0.0};
  }

  /// הוספת מכ"ם מוצב (או עריכת קיים: oldName). מחזיר הודעת שגיאה או null.
  Future<String?> saveSite(String name, String typeKey, {String? oldName}) async {
    name = name.trim(); if (name.length > 100) name = name.substring(0, 100); // שם
    if (name.isEmpty || typeKey.isEmpty) return 'נדרשים שם וסוג'; // ולידציה
    if (name != oldName && sites.any((s) => s['name'] == name)) return 'השם כבר קיים'; // כפילות
    Map<String, dynamic> p; // פרמטרים
    if (oldName != null) { // עריכה
      final old = sites.firstWhere((s) => s['name'] == oldName, orElse: () => <String, dynamic>{});
      if (old.isEmpty) return 'המכ"ם לא נמצא';
      p = Map<String, dynamic>.from(old['params'] as Map);
      if (p['type_key'] != typeKey) { p['type_key'] = typeKey; p['type_name'] = typeOf(typeKey)?['name'] ?? ''; } // סוג חדש — ההצבה נשמרת
      sites = sites.where((s) => s['name'] != oldName).toList(); // הסרת הישן
    } else {
      p = siteDefaults(typeKey, _map?.radarObs); // חדש
    }
    sites = [...sites, {'name': name, 'params': p}]; // הוספה
    await activateSite(name); // הפעלה
    if (p['lat'] == null) sitePick = true; // בלי מיקום — הלחיצה הבאה ממקמת
    await _saveSites(); notifyListeners(); // שמירה
    return null; // הצלחה
  }

  /// יצירת מכ"ם מוצב מסוג בלחיצה אחת (בחירת "➕ מכ"ם חדש מסוג…" בבורר): שם = שם הסוג (ייחודי), מיקום = המכ"ם הנוכחי.
  Future<String> quickCreate(String typeKey) async {
    final t = typeOf(typeKey); if (t == null) return 'הסוג לא נמצא'; // אין סוג
    var base = '${t['name']}'.replaceAll(' (נתונים פומביים)', ''); if (base.length > 90) base = base.substring(0, 90); // שם בסיס
    var name = base; var i = 2; while (sites.any((s) => s['name'] == name)) { name = '$base $i'; i++; } // שם פנוי
    final e = await saveSite(name, typeKey); // יצירה + הפעלה
    return e ?? (sitePick ? 'נוצר "$name" — הקש על המפה למיקום המכ"ם' : 'נוצר "$name" במיקום המכ"ם הנוכחי'); // הודעה
  }

  /// מחיקת המכ"ם הפעיל.
  Future<void> deleteActiveSite() async {
    sites = sites.where((s) => s['name'] != activeSite).toList(); activeSite = ''; // הסרה
    await _saveSites(); notifyListeners(); // שמירה
  }

  /// לחיצה על המפה במצב "📍 מקם".
  void placeSiteAt(LatLng ll) {
    sitePick = false; final s = site; if (s == null || _map == null) { notifyListeners(); return; } // אין פעיל
    final p = s['params'] as Map<String, dynamic>; p['lat'] = ll.latitude; p['lon'] = ll.longitude; // המיקום
    _moveObservers(ll, null); _snapAll(); _saveSitesSoon(); notifyListeners(); // הצופים + שמירה
  }

  /// "שכפל לעריכה": עותק של סוג מהספרייה תחת "הפרופילים שלי", והמכ"ם הפעיל עובר אליו (שדות פתוחים).
  Future<String?> cloneActiveType(String name) async {
    final t = activeType; if (t == null || t['lib'] != true) return 'אין סוג נעול לשכפל'; // רק סוג נעול
    name = name.trim(); if (name.isEmpty) return 'נדרש שם'; // ולידציה
    final store = await _loadStore(); store[name] = Map<String, dynamic>.from(t['params'] as Map); // עותק מלא של הסוג
    final prefs = await SharedPreferences.getInstance(); await prefs.setString(_prefsKey, jsonEncode(store)); // שמירה
    await refreshMyProfiles(); // רענון
    _sp['type_key'] = 'my:$name'; _sp['type_name'] = name; // המכ"ם עובר לעותק
    await activateSite(activeSite); // החלה מחדש (פתוח)
    return null; // הצלחה
  }

  /// "צופה נפרד": מנותק = הכלי עצמאי (מיקום ושדות); חיבור מחדש מחיל שוב את המכ"ם הפעיל.
  Future<void> setDetached(String tool, bool on) async {
    detached = {...detached, tool: on}; // המצב
    if (!on && site != null) { await activateSite(activeSite); } else { _snapAll(); notifyListeners(); } // חיבור מחדש — החלה
    _saveSitesSoon(); // שמירה
  }

  /// מיקום הצופה המשותף לכלי (null = ידני / מנותק / המכ"ם עוד לא הוצב).
  LatLng? sharedObs(String tool) {
    if (site == null || (detached[tool] ?? false)) return null; // ידני / מנותק
    final lat = (_sp['lat'] as num?)?.toDouble(), lon = (_sp['lon'] as num?)?.toDouble(); // המיקום
    return (lat == null || lon == null) ? null : LatLng(lat, lon);
  }

  /// כלי נפתח: אם מחובר למכ"ם פעיל עם מיקום — הצופה שלו מוצב במיקום המכ"ם.
  void onToolOpened(String tool) {
    final ll = sharedObs(tool); if (ll == null || _map == null) return; // מנותק / ידני / בלי מיקום
    if (tool == 'radial' && _map!.radialLosObs != ll) { _applying = true; try { _map!.setRadialLosObserver(ll); } finally { _applying = false; } _snapAll(); }
  }

  /// מגבלות המכ"ם לקו ראייה נקודתי (נלכד ביצירת הצמד): סקטור, טווח, טווח מינימלי, שדה ראייה אנכי.
  Map<String, dynamic>? losSnapshot() {
    final s = site; if (s == null || (detached['los'] ?? false)) return null; // ידני / מנותק
    final tp = (activeType?['params'] as Map<String, dynamic>?) ?? const <String, dynamic>{}; // הסוג
    double n(dynamic v, double dflt) => (v as num?)?.toDouble() ?? dflt; // מספר
    return {'label': '${s['name']} (${siteTypeName(s)})', 'boresight': n(_sp['boresight_deg'], 0), 'antenna': tp['antenna_type'] ?? 'generic',
        'maxScan': n(tp['max_scan_deg'], 180), 'range': n(_sp['range_km'], 0), 'minRange': n(tp['min_range_km'], 0),
        'vc': n(tp['vertical_center_deg'], 0), 'vw': n(tp['vertical_width_deg'], 180)};
  }

  /// ייצוא כל המכ"מים המוצבים + הסוגים "שלי" שבשימוש — אותו פורמט כמו בדסקטופ.
  Future<String> exportSites() async {
    final mine = <String, dynamic>{}; // סוגים שלי בשימוש
    for (final s in sites) { final t = typeOf((s['params'] as Map)['type_key'] as String?); if (t != null && t['lib'] != true) mine['${t['name']}'] = t['params']; }
    final doc = {'format': 'maps-gui-radar-sites', 'version': 1, 'active': activeSite, 'sites': sites,
        'my_types': [for (final e in mine.entries) {'name': e.key, 'params': e.value}]}; // המבנה
    try {
      return await FileBridge.saveText('radar_sites.json', 'application/json', const JsonEncoder.withIndent('  ').convert(doc)) ? 'נשמר ✔' : 'בוטל';
    } catch (e) {
      return '$e'; // שגיאה
    }
  }

  /// ייבוא מכ"מים מוצבים מקובץ (שם קיים — מוחלף).
  Future<String> importSites() async {
    try {
      final text = await FileBridge.openText(); if (text == null) return 'בוטל'; // חלון הפתיחה
      final doc = jsonDecode(text); // פענוח
      if (doc is Map && doc['format'] == 'maps-gui-radar-profile' && doc['params'] is Map) { // קובץ פרופיל בודד — נוסף כסוג "שלי" ונוצר ממנו מכ"ם
        var nm = '${doc['name'] ?? 'פרופיל מיובא'}'.trim(); if (nm.length > 100) nm = nm.substring(0, 100); if (nm.isEmpty) nm = 'פרופיל מיובא'; // שם הסוג
        final st = await _loadStore(); st[nm] = Map<String, dynamic>.from(doc['params'] as Map); // הוספה
        final pr = await SharedPreferences.getInstance(); await pr.setString(_prefsKey, jsonEncode(st)); await refreshMyProfiles(); // שמירה
        final m = await quickCreate('my:$nm'); // מכ"ם מוצב מהסוג
        return 'נוסף הסוג "$nm" ל"הפרופילים שלי" ✔ $m';
      }
      if (doc is! Map || doc['format'] != 'maps-gui-radar-sites' || doc['sites'] is! List) return 'זה לא קובץ מכ"ם של maps-gui (פרופיל או מכ"מים מוצבים)';
      final store = await _loadStore(); // סוגים שלי
      for (final t in (doc['my_types'] as List? ?? const [])) { if (t is Map && t['name'] != null && t['params'] is Map) store['${t['name']}'] = t['params']; }
      final prefs = await SharedPreferences.getInstance(); await prefs.setString(_prefsKey, jsonEncode(store)); await refreshMyProfiles(); // שמירה
      var n = 0; // כמה מכ"מים
      for (final s in (doc['sites'] as List)) {
        if (s is! Map || s['name'] == null || s['params'] is! Map || (s['params'] as Map)['type_key'] == null) continue; // לא תקין
        final ns = _normSite(s); sites = [...sites.where((x) => x['name'] != ns['name']), ns]; n++; // החלפה/הוספה
      }
      await _saveSites(); notifyListeners(); // שמירה
      return 'נטענו $n מכ"מים ✔';
    } on FormatException {
      return 'הקובץ אינו JSON תקין';
    } catch (e) {
      return '$e';
    }
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
      if (site != null) { // FR-D-288: יש מכ"ם פעיל — לא דורסים את שדותיו; הפרופיל נוסף כסוג "שלי" ונוצר ממנו מכ"ם
        var nm = '${doc['name'] ?? 'פרופיל מיובא'}'.trim(); if (nm.isEmpty) nm = 'פרופיל מיובא'; if (nm.length > 100) nm = nm.substring(0, 100); // שם
        final st = await _loadStore(); st[nm] = Map<String, dynamic>.from(doc['params'] as Map); // הוספה
        final pr = await SharedPreferences.getInstance(); await pr.setString(_prefsKey, jsonEncode(st)); await refreshMyProfiles(); // שמירה
        return 'נוסף כסוג "$nm" ✔ ${await quickCreate('my:$nm')}'; // מכ"ם מוצב מהסוג
      }
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
    plProfileLbl = activeLabel(); // FR-D-286: הפרופיל שהיה פעיל בתחילת החישוב
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
      plStatus = '📡 $plProfileLbl\n' // FR-D-286: לפי איזה פרופיל
          '🗺 ${(r['candidates'] as List).length} מיקומים | המיטבי: ${b?['score']}$unit (קרקע ${b?['ground_m']} מ\')\n'
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
    if (sitePick) { placeSiteAt(p); return true; } // FR-D-288: "📍 מקם" — מיקום המכ"ם הפעיל
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
