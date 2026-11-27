// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'dart:async'; // Timer ל-polling ול-debounce
import 'dart:convert'; // JSON לשמירת סטים ולחתימת המכ"מים

import 'package:flutter/foundation.dart'; // ChangeNotifier
import 'package:latlong2/latlong.dart' show LatLng; // נקודות המפה
import 'package:shared_preferences/shared_preferences.dart'; // שמירת סטי אזורים במכשיר

import '../services/mpm_bridge.dart'; // הגישור ל-Python (Chaquopy)

/// אזור שיגור/מטרה: שם, סוג ומצולע.
class AfArea {
  AfArea(this.kind, this.points, this.name); // בנאי
  final String kind; // 'launch' / 'target'
  final List<LatLng> points; // קודקודי המצולע
  String name; // שם (ניתן לשינוי)
  Map<String, dynamic> toJson() => {'name': name, 'kind': kind, 'polygon': [for (final p in points) [p.latitude, p.longitude]]}; // לבקשה ולשמירה
}

/// A6: "ירי מאזור לאזור" באנדרואיד (docs/PLAN_BALLISTICS_AREA_FIRE.md) — אותו מנוע (area_fire.py) כמו בדסקטופ, דרך
/// radar_android.py. הבקר מחזיק את האזורים, מצב הציור (הקשות על המפה), ה-job, התוצאה והצביעה (ירוק/אדום).
class AreaFireController extends ChangeNotifier {
  static const maxDraw = 2000; // דילול תצוגה מעל המספר הזה (החלטה 15)
  static const _setsKey = 'area_sets_v1'; // מפתח שמירת הסטים
  static const rejectNames = {'out_of_range': 'מחוץ לטווח', 'qe_limits': 'מחוץ לגבולות ההגבהה', 'min_range': 'קרוב מטווח מינימלי',
                              'max_tof': 'זמן מעוף ארוך', 'terrain': 'פוגע בשטח (רכס)'}; // שמות הפסילות

  final List<AfArea> areas = []; // האזורים
  String? drawKind; // סוג האזור בציור (null = לא מציירים)
  String drawShape = 'poly'; // 'poly' / 'rect'
  final List<LatLng> drawPts = []; // נקודות הציור
  bool low = true, high = true, crest = true; // ענפים ורכס
  double? qeMin, qeMax, minRange, maxTof; // גבולות (null = בלי)
  double margin = 0; // מרווח בטיחות מעל השטח
  String estimate = ''; // טקסט ההערכה
  String status = ''; // התקדמות / סיכום
  bool running = false; // job רץ
  String? _jobId, resultJob, visJob; // מזהים
  Map<String, dynamic>? result; // תוצאת החישוב
  List<List<int>>? masks; // מסיכות הנראות
  List<String> visRadars = []; // שמות המכ"מים לפי ביט
  String? visSig; // חתימת המכ"מים ברגע הצביעה
  String _visSigPending = ''; // חתימה בזמן הבקשה
  String visSummary = ''; // שורת סיכום הנראות
  String fBranch = 'all'; // סינון ענף
  int fLaunch = -1, fTarget = -1; // סינון אזורים (-1 = הכול)
  bool fUnseen = false; // רק לא נצפים
  bool showPaths = true, heatL = false, heatT = false; // שכבות
  int? selected; // מסלול שנבחר
  List<String> setNames = []; // סטים שמורים
  Timer? _poll, _vpoll, _estT; // טיימרים

  bool get drawing => drawKind != null; // מצב ציור

  // ── ציור אזורים ──
  void startDraw(String kind, String shape) { drawKind = kind; drawShape = shape; drawPts.clear(); notifyListeners(); } // התחלה
  void cancelDraw() { drawKind = null; drawPts.clear(); notifyListeners(); } // ביטול

  /// הקשה על המפה: true אם הכלי טיפל בה (מצב ציור).
  bool handleMapTap(LatLng p) {
    if (drawKind == null) return false; // לא שלנו
    drawPts.add(p); // נקודה
    if (drawShape == 'rect' && drawPts.length == 2) { // מלבן — שתי פינות
      final a = drawPts[0], b = drawPts[1]; // הפינות
      _addArea(drawKind!, [a, LatLng(a.latitude, b.longitude), b, LatLng(b.latitude, a.longitude)]); // ארבע פינות
      drawKind = null; drawPts.clear(); // סיום
    }
    notifyListeners(); // ציור
    return true; // טופל
  }

  /// סיום מצולע (לפחות 3 נקודות). מחזיר הודעת שגיאה או null.
  String? finishDraw() {
    if (drawKind == null || drawPts.length < 3) return 'צריך לפחות 3 נקודות'; // מעט מדי
    _addArea(drawKind!, List.of(drawPts)); // הוספה
    drawKind = null; drawPts.clear(); notifyListeners(); // סיום
    return null; // תקין
  }

  void _addArea(String kind, List<LatLng> pts) { // הוספת אזור עם מספור לפי סוג
    final n = areas.where((a) => a.kind == kind).length + 1; // מספר
    areas.add(AfArea(kind, pts, '${kind == 'launch' ? 'שיגור' : 'מטרה'} $n')); // האזור
    scheduleEstimate(); // הערכה מחדש
  }

  void removeArea(int i) { areas.removeAt(i); scheduleEstimate(); notifyListeners(); } // מחיקה
  void renameArea(int i, String name) { if (name.trim().isNotEmpty) areas[i].name = name.trim().substring(0, name.trim().length.clamp(0, 80)); notifyListeners(); } // שינוי שם
  void update(VoidCallback fn) { fn(); notifyListeners(); } // שינוי כללי + ציור

  // ── בקשה, הערכה והרצה ──
  Map<String, dynamic> request(Map<String, dynamic> common) => { // בניית הבקשה (common: מהירות לוע, מטאו, פגז — מהכלי הבליסטי)
        'launch_areas': [for (final a in areas.where((a) => a.kind == 'launch')) {'name': a.name, 'polygon': a.toJson()['polygon']}], // שיגור
        'target_areas': [for (final a in areas.where((a) => a.kind == 'target')) {'name': a.name, 'polygon': a.toJson()['polygon']}], // מטרה
        'mv': common['mv'], 'met': common['met'], 'fitting': common['fitting'], 'coriolis': common['coriolis'], // פרמטרי ירי
        'earth_curvature': common['earth_curvature'], 'angle_unit': 'mils', // יחידות
        'groups': [if (low) 'low', if (high) 'high'], 'qe_min': qeMin, 'qe_max': qeMax, // ענפים וגבולות
        'min_range_m': minRange, 'max_tof_s': maxTof, 'crest': crest, 'safety_margin_m': margin, // סינונים
      };

  Map<String, dynamic> Function()? commonParams; // מקור פרמטרי הירי (מוגדר ע"י הכלי הבליסטי)

  void scheduleEstimate() { _estT?.cancel(); _estT = Timer(const Duration(milliseconds: 500), _estimate); } // debounce

  static String fmtTime(num? s) { // שניות → טקסט
    if (s == null) return ''; // אין
    if (s < 90) return '${s.round().clamp(1, 89)} שנ\''; // שניות
    if (s < 5400) return '${(s / 60).round()} דק\''; // דקות
    return '${(s / 3600).toStringAsFixed(1)} שעות'; // שעות
  }

  Future<void> _estimate() async { // הערכה לפני הרצה (החלטה 11)
    final cp = commonParams; // פרמטרים
    if (cp == null) return; // הכלי עוד לא חובר
    final req = request(cp()); // הבקשה
    if ((req['launch_areas'] as List).isEmpty || (req['target_areas'] as List).isEmpty) { estimate = 'סמן לפחות אזור שיגור אחד ואזור מטרה אחד.'; notifyListeners(); return; } // חסר
    try {
      final d = await MpmBridge.call('radar_area_estimate', req); // ההערכה
      if (d['ok'] == false) { estimate = '⚠️ ${d['error']}'; } // שגיאה
      else {
        estimate = '${d['launch_points']} נקודות שיגור × ${d['target_points']} נקודות מטרה = ${d['pairs']} זוגות (${d['trajectories_max']} מסלולים). '
            'זמן משוער: ${fmtTime(d['eta_s'] as num?)}${(d['cells_missing'] as num) > 0 ? ' (שליפת שטח: ${fmtTime((d['eta_parts_s'] as Map)['terrain'] as num?)}; בפעם הבאה מהמטמון)' : ''}. בטלפון החישוב איטי יותר.'; // הטקסט
      }
    } catch (e) { estimate = 'הערכה נכשלה: $e'; } // כשל גישור
    notifyListeners(); // ציור
  }

  Future<void> run() async { // התחלת חישוב
    final cp = commonParams; // פרמטרים
    if (cp == null) return; // לא מחובר
    final req = request(cp()); // הבקשה
    if ((req['launch_areas'] as List).isEmpty || (req['target_areas'] as List).isEmpty) { status = 'סמן לפחות אזור שיגור אחד ואזור מטרה אחד.'; notifyListeners(); return; } // חסר
    if ((req['groups'] as List).isEmpty) { status = 'בחר לפחות ענף אחד.'; notifyListeners(); return; } // בלי ענפים
    cancel(silent: true); // job קודם
    result = null; masks = null; visJob = null; visSig = null; selected = null; visSummary = ''; // ניקוי
    status = 'מתחיל…'; running = true; notifyListeners(); // משוב
    try {
      final d = await MpmBridge.call('radar_area_start', req); // התחלה
      if (d['ok'] == false || d['job_id'] == null) { status = '⚠️ ${d['error'] ?? 'שגיאה'}'; running = false; notifyListeners(); return; } // שגיאה
      final id = d['job_id'] as String; _jobId = id; // המזהה
      _poll = Timer.periodic(const Duration(seconds: 1), (_) => _pollJob(id, false)); // polling
    } catch (e) { status = '⚠️ $e'; running = false; notifyListeners(); } // כשל גישור
  }

  void cancel({bool silent = false}) { // ביטול
    _poll?.cancel(); _poll = null; // עצירת polling
    final id = _jobId; _jobId = null; // ה-job
    if (id != null) { MpmBridge.call('radar_job_cancel', {'job_id': id}).catchError((_) => <String, dynamic>{}); if (!silent) status = 'בוטל.'; } // ביטול ב-Python
    running = false; notifyListeners(); // מצב רגיל
  }

  Future<void> _pollJob(String id, bool isVis) async { // מצב job (חישוב או צביעה)
    try {
      final st = await MpmBridge.call('radar_job_status', {'job_id': id}); // המצב
      if (isVis ? id != visJob : id != _jobId) return; // הוחלף
      if (st['status'] == 'running') { // עדיין רץ
        final tot = st['batches_total']; // שליפה
        final eta = st['eta_s'] as num?; // הערכה (T23)
        status = '${isVis ? '🎨' : '⏳'} ${st['note'] ?? 'מחשב…'}${tot != null ? ' (${st['batches_done']}/$tot)' : ''}${eta != null && eta > 0 ? ' · נותרו כ-${fmtTime(eta)}' : ''}'; // התקדמות
        notifyListeners(); return; // ממתין
      }
      if (isVis) { _vpoll?.cancel(); _vpoll = null; } else { _poll?.cancel(); _poll = null; _jobId = null; running = false; } // עצירה
      if (st['status'] == 'done') { // הצליח
        final r = (st['result'] as Map).cast<String, dynamic>(); // התוצאה
        if (isVis) { // צביעה
          masks = [for (final m in r['masks'] as List) [for (final x in m as List) (x as num).toInt()]]; // המסיכות
          visRadars = [for (final x in r['radars'] as List) ((x as Map)['name'] ?? '').toString()]; // שמות
          visSig = _visSigPending; // החתימה
          final s = r['summary'] as Map; // סיכום
          visSummary = '🎨 ${s['radars']} מכ"מים: ${s['trajectories_seen_any']} מסלולים נצפים בחלקם, ${s['trajectories_seen_full']} במלואם, ${s['trajectories_unseen']} לא נצפים כלל.'; // שורה
        } else { result = r; resultJob = id; masks = null; visJob = null; visSig = null; } // תוצאה חדשה
        status = summaryText(); // סיכום
      } else { status = st['status'] == 'error' ? '⚠️ ${st['error'] ?? 'שגיאה'}' : (isVis ? 'הצביעה בוטלה.' : 'בוטל.'); } // שגיאה/ביטול
      notifyListeners(); // ציור
    } catch (_) { /* כשל גישור בבדיקה בודדת — ה-tick הבא */ }
  }

  String summaryText() { // טקסט הסיכום (כמו בדסקטופ)
    final r = result; if (r == null) return status; // אין
    final s = r['summary'] as Map, v = (r['verification'] as Map?) ?? {}; // קיצורים
    final lines = <String>['✅ ${s['pairs_feasible']} מתוך ${s['pairs']} זוגות אפשריים · ${s['trajectories_feasible']} מסלולים אפשריים (מתוך ${s['trajectories_checked']} שנבדקו).']; // ספירות
    final rej = (s['rejected'] as Map).entries.where((e) => (e.value as num) > 0).map((e) => '${rejectNames[e.key] ?? e.key}: ${e.value}').toList(); // פסילות
    if (rej.isNotEmpty) lines.add('נפסלו: ${rej.join(' · ')}'); // פירוט
    if ((v['checked'] ?? 0) as num > 0) lines.add('דיוק (מדגם ${v['checked']}): החטאה מרבית ${v['miss_max_m']} מ\', RMS ${v['miss_rms_m']} מ\'; שגיאת הגבהה עד ${v['qe_err_max_mils']} מיל.'); // אימות
    if (visSummary.isNotEmpty) lines.add(visSummary); // נראות
    lines.add('זמן חישוב: ${fmtTime(s['elapsed_s'] as num?)}.'); // זמן
    return lines.join('\n'); // שורות
  }

  // ── צביעה (החלטות 14, 16) ──
  static String sitesSig(List<Map<String, dynamic>> sites) => jsonEncode([for (final s in sites) [s['name'], for (final k in ['lat', 'lon', 'h_antenna', 'range_km', 'start_bearing_deg', 'end_bearing_deg', 'ridge_margin_deg']) (s['params'] as Map?)?[k]]]); // חתימה
  bool isStale(List<Map<String, dynamic>> sites) => result != null && visSig != null && visSig != sitesSig(sites); // הצביעה ישנה

  Future<void> recolor(List<Map<String, dynamic>> sites) async { // "עדכן צביעה" — כל המכ"מים המוצבים
    final id = resultJob; if (id == null) return; // אין תוצאה
    _visSigPending = sitesSig(sites); // החתימה בזמן הבקשה
    if (sites.isEmpty) { masks = null; visSig = _visSigPending; visSummary = 'אין מכ"מים מוצבים — הכול אדום.'; status = summaryText(); notifyListeners(); return; } // בלי מכ"מים (החלטה 14)
    try {
      final d = await MpmBridge.call('radar_area_visibility', {'job_id': id, 'sites': sites}); // התחלה
      if (d['ok'] == false || d['job_id'] == null) { status = '⚠️ ${d['error'] ?? 'שגיאה'}'; notifyListeners(); return; } // שגיאה
      final vid = d['job_id'] as String; visJob = vid; // המזהה
      _vpoll?.cancel(); _vpoll = Timer.periodic(const Duration(seconds: 1), (_) => _pollJob(vid, true)); // polling
    } catch (e) { status = '⚠️ $e'; notifyListeners(); } // כשל
  }

  // ── סינון ──
  List<int> filtered() { // אינדקסי המסלולים אחרי הסינון
    final r = result; if (r == null) return const []; // אין
    final rows = r['rows'] as List; // השורות
    final out = <int>[]; // התוצאה
    for (var i = 0; i < rows.length; i++) { // כל מסלול
      final row = rows[i] as Map; // המסלול
      if (fBranch != 'all' && row['group'] != fBranch) continue; // ענף
      if (fLaunch >= 0 && row['la'] != fLaunch) continue; // אזור שיגור
      if (fTarget >= 0 && row['ta'] != fTarget) continue; // אזור מטרה
      if (fUnseen && masks != null && masks![i].any((x) => x != 0)) continue; // רק לא נצפים
      out.add(i); // עבר
    }
    return out; // הרשימה
  }

  List<int> thinned(List<int> idx) { // דילול שווה מעל maxDraw
    if (idx.length <= maxDraw) return idx; // מתחת לתקרה
    final step = idx.length / maxDraw; // צעד
    return [for (var k = 0; k < maxDraw; k++) idx[(k * step).floor()]]; // מדולל
  }

  // ── CSV ──
  Future<String?> csv() async { // טקסט CSV (או null)
    final id = resultJob; if (id == null) return null; // אין
    final d = await MpmBridge.call('radar_area_csv', {'job_id': id, if (visJob != null && masks != null) 'vis_job': visJob}); // הבקשה
    return d['csv'] as String?; // הטקסט
  }

  // ── סטים שמורים במכשיר ──
  Future<void> loadSetNames() async { // שמות הסטים
    final prefs = await SharedPreferences.getInstance(); // האחסון
    final m = jsonDecode(prefs.getString(_setsKey) ?? '{}') as Map; // המפה
    setNames = m.keys.cast<String>().toList()..sort(); notifyListeners(); // ממוינים
  }
  Future<void> saveSet(String name) async { // שמירה
    final prefs = await SharedPreferences.getInstance(); // האחסון
    final m = (jsonDecode(prefs.getString(_setsKey) ?? '{}') as Map).cast<String, dynamic>(); // המפה
    m[name] = [for (final a in areas) a.toJson()]; // הסט
    await prefs.setString(_setsKey, jsonEncode(m)); await loadSetNames(); // שמירה ורענון
  }
  Future<void> loadSet(String name) async { // טעינה
    final prefs = await SharedPreferences.getInstance(); // האחסון
    final list = (jsonDecode(prefs.getString(_setsKey) ?? '{}') as Map)[name] as List?; // הסט
    if (list == null) return; // לא קיים
    areas..clear()..addAll([ // אזורים תקינים בלבד
      for (final a in list.cast<Map>())
        if (a['polygon'] is List && (a['polygon'] as List).length >= 3)
          AfArea(a['kind'] == 'target' ? 'target' : 'launch', [for (final p in (a['polygon'] as List).cast<List>()) LatLng((p[0] as num).toDouble(), (p[1] as num).toDouble())], (a['name'] ?? '').toString()),
    ]);
    scheduleEstimate(); notifyListeners(); // הערכה וציור
  }
  Future<void> deleteSet(String name) async { // מחיקה
    final prefs = await SharedPreferences.getInstance(); // האחסון
    final m = (jsonDecode(prefs.getString(_setsKey) ?? '{}') as Map).cast<String, dynamic>()..remove(name); // בלי הסט
    await prefs.setString(_setsKey, jsonEncode(m)); await loadSetNames(); // שמירה ורענון
  }

  @override
  void dispose() { _poll?.cancel(); _vpoll?.cancel(); _estT?.cancel(); super.dispose(); } // ניקוי טיימרים
}
