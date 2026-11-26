// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' show LatLng; // רק LatLng — latlong2 מייצא גם Path שמתנגש עם Path של הציור (dart:ui)

import '../state/radar_track_controller.dart';

/// שכבות המפה והגרפים של כלי בדיקת מעקב המכ"ם באנדרואיד (שלב ג', MAPS-GUI_SRS.md FR-D-283) — מקבילים לציור
/// ב-MAP.py (Desktop): אותם צבעים, אותו סולם כחול רציף למפת החום, ואותם גרפים (ציר זמן, גרף צד, פרופיל, מקרא).

/// צבעי המצבים — זהים ל-_RADAR_TRACK_COLORS בדסקטופ.
const Map<String, Color> rtColors = {
  'detected': Color(0xFF00CC44), 'doppler_blind': Color(0xFFFF9500), 'blocked': Color(0xFFFF3300),
  'out_of_range': Color(0xFF6C7086), 'tracked': Color(0xFF00CC44), 'coasting': Color(0xFF86EFAC),
  'detected_untracked': Color(0xFF3B82F6),
};

/// מצב מעקב -> עברית.
const Map<String, String> rtStateText = {'tracked': 'במעקב', 'coasting': 'דעיכה (מעקב בלי גילוי)', 'detected_untracked': 'גילוי בלי מעקב'};

/// הסולם הרציף של מפת החום (כחול, בהיר = נמוך) — אותם צעדים כמו בדסקטופ (פלטת dataviz).
const List<Color> rtSeq = [Color(0xFFCCE3FD), Color(0xFF9DC8F7), Color(0xFF6AABF1), Color(0xFF338CED),
                           Color(0xFF2370CD), Color(0xFF1757AC), Color(0xFF0E3D7E)];

/// צבע לערך מנורמל t∈[0,1].
Color rtSeqColor(double t) {
  t = t.clamp(0.0, 1.0); // צמידה
  final x = t * (rtSeq.length - 1); // מיקום בסולם
  final i = min(rtSeq.length - 2, x.floor()); // הצעד התחתון
  return Color.lerp(rtSeq[i], rtSeq[i + 1], x - i)!; // אינטרפולציה
}

double _d(dynamic v) => (v as num).toDouble(); // מספר מ-JSON (int או double) -> double, כפי ש-LatLng דורש

Color _keyColor(Map p) => rtColors[p['track_state'] ?? p['status']] ?? const Color(0xFF6C7086); // צבע נקודה

/// בונה את כל שכבות הכלי על המפה. trackHit — לחיצה על קטע/קו (hitValue = אינדקס הנקודה); placeHit — לחיצה על תא.
List<Widget> buildRadarTrackLayers(RadarTrackController c, LayerHitNotifier<int> trackHit, LayerHitNotifier<int> placeHit,
    void Function(LatLng) onBestTap) {
  final layers = <Widget>[]; // התוצאה
  final pl = c.placement; // מפת החום
  if (pl != null) { // מפת חום — מתחת לכל השאר
    final cands = (pl['candidates'] as List).cast<Map>().where((m) => m['score'] != null).toList(); // מחושבים
    if (cands.isNotEmpty) {
      final scores = cands.map((m) => (m['score'] as num).toDouble()); // ציונים
      final lo = scores.reduce(min), hi = scores.reduce(max); // טווח
      final half = (pl['step_m'] as num) / 2.0; // חצי תא
      final cosLat = cos(_d((pl['center'] as Map)['lat']) * pi / 180); // תיקון אורך
      final dLat = half / 111194.9, dLon = half / (111194.9 * cosLat); // חצי תא במעלות
      final all = (pl['candidates'] as List).cast<Map>(); // לאינדקס המקורי
      layers.add(PolygonLayer<int>(hitNotifier: placeHit, polygons: [
        for (final m in cands)
          Polygon<int>(
            points: [LatLng(_d(m['lat']) - dLat, _d(m['lon']) - dLon), LatLng(_d(m['lat']) - dLat, _d(m['lon']) + dLon),
                     LatLng(_d(m['lat']) + dLat, _d(m['lon']) + dLon), LatLng(_d(m['lat']) + dLat, _d(m['lon']) - dLon)], // התא
            color: rtSeqColor(hi > lo ? ((m['score'] as num) - lo) / (hi - lo) : 1.0).withAlpha(150), // צבע הציון
            borderColor: Colors.white, borderStrokeWidth: 1, // מרווח לבן דק בין תאים
            hitValue: all.indexOf(m), // לזיהוי בלחיצה
          ),
      ]));
      final best = (pl['best'] as List).cast<Map>(); // הטובים
      layers.add(MarkerLayer(markers: [
        for (int i = 0; i < best.length; i++)
          Marker(
            point: LatLng(_d(best[i]['lat']), _d(best[i]['lon'])), width: i == 0 ? 30 : 20, height: i == 0 ? 30 : 20,
            child: GestureDetector(
              onTap: () => onBestTap(LatLng(_d(best[i]['lat']), _d(best[i]['lon']))), // הצבת המכ"ם
              child: i == 0
                  ? const Text('⭐', style: TextStyle(fontSize: 22)) // המיטבי
                  : Container(decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.black87, width: 2)),
                      alignment: Alignment.center, child: Text('${i + 1}', style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold))), // 2..5
            ),
          ),
      ]));
    }
  }
  if (c.source == 'loiter' && c.loiterCenter != null) { // תצוגה מקדימה של השיוט
    layers.add(CircleLayer(circles: [CircleMarker(point: c.loiterCenter!, radius: c.loiterRadius, useRadiusInMeter: true,
        color: Colors.transparent, borderColor: const Color(0xFF14B8A6), borderStrokeWidth: 2)]));
  }
  if (c.ballisticPath != null && c.ballisticPath!.length >= 2) { // המסלול הבליסטי (כתום, כמו בדסקטופ)
    layers.add(PolylineLayer(polylines: [Polyline(points: c.ballisticPath!.map((p) => LatLng(_d(p['lat']), _d(p['lon']))).toList(),
        color: const Color(0xFFFAB387), strokeWidth: 3)]));
  }
  if (c.rocketPath != null && c.rocketPath!.length >= 2) { // מסלול הרקטה (סגול מקווקו)
    layers.add(PolylineLayer(polylines: [Polyline(points: c.rocketPath!.map((p) => LatLng(_d(p['lat']), _d(p['lon']))).toList(),
        color: const Color(0xFFCBA6F7), strokeWidth: 3, pattern: StrokePattern.dashed(segments: const [8, 5]))]));
  }
  final r = c.result; // תוצאת הבדיקה
  if (r != null) {
    final pts = (r['points'] as List).cast<Map>(); // הנקודות
    final radar = r['radar'] as Map; // המכ"ם
    final lines = <Polyline<int>>[]; // קווים לחיצים
    if (c.showFan) { // מניפת LOS — עד ~60 קווים
      final step = max(1, (pts.length / 60).ceil()); // דילול
      for (int i = 0; i < pts.length; i += step) {
        lines.add(Polyline<int>(points: [LatLng(_d(radar['lat']), _d(radar['lon'])), LatLng(_d(pts[i]['lat']), _d(pts[i]['lon']))],
            color: _keyColor(pts[i]).withAlpha(115), strokeWidth: 1, hitValue: i)); // קו דק ושקוף
      }
    }
    for (int i = 1; i < pts.length; i++) { // המסלול הצבוע — צבע לפי הנקודה בקצה הקטע
      lines.add(Polyline<int>(points: [LatLng(pts[i - 1]['lat'], pts[i - 1]['lon']), LatLng(_d(pts[i]['lat']), _d(pts[i]['lon']))],
          color: _keyColor(pts[i]), strokeWidth: 5, hitValue: i));
    }
    layers.add(PolylineLayer<int>(polylines: lines, hitNotifier: trackHit)); // שכבה אחת לחיצה
  }
  return layers; // הכל
}

// ═══════════════════════ גרפים ═══════════════════════

TextPainter _tp(String s, double size, {Color color = const Color(0xFF333333)}) =>
    TextPainter(text: TextSpan(text: s, style: TextStyle(fontSize: size, color: color)), textDirection: TextDirection.rtl)..layout(); // טקסט

/// ציר זמן: פס צבעוני לפי מצב, מימין (התחלה) לשמאל (סוף), קו בפתיחת המעקב וזמן ההתרעה — כמו בדסקטופ.
class RtTimelinePainter extends CustomPainter {
  RtTimelinePainter(this.track);
  final Map track; // result['track']

  @override
  void paint(Canvas canvas, Size size) {
    final tl = (track['timeline'] as List).cast<Map>(); // המקטעים
    if (tl.isEmpty) return; // אין
    final t0 = (tl.first['t0'] as num).toDouble(), t1 = (tl.last['t1'] as num).toDouble(); // טווח
    final span = max(1e-6, t1 - t0), w = size.width; // רוחב
    double x(double t) => w - 4 - (t - t0) / span * (w - 8); // זמן -> פיקסל (RTL)
    for (final s in tl) { // כל מקטע
      final a = x((s['t1'] as num).toDouble()), b = x((s['t0'] as num).toDouble()); // קצוות
      canvas.drawRect(Rect.fromLTRB(a, 6, max(a + 1, b), 22), Paint()..color = rtColors[s['state']] ?? const Color(0xFF6C7086)); // הפס
    }
    if (track['first_track_t'] != null) { // פתיחת המעקב
      final xf = x((track['first_track_t'] as num).toDouble()); // מיקום
      canvas.drawRect(Rect.fromLTRB(xf - 1, 2, xf + 1, 26), Paint()..color = const Color(0xFF111111)); // קו כהה
    }
    _tp('${t0.toStringAsFixed(0)} שנ\'', 9).paint(canvas, Offset(w - 2 - _tp('${t0.toStringAsFixed(0)} שנ\'', 9).width, 28)); // התחלה
    _tp('${t1.toStringAsFixed(1)} שנ\'', 9).paint(canvas, const Offset(2, 28)); // סוף
    if (track['warning_time_s'] != null) { // זמן התרעה
      final s = _tp('התרעה: ${(track['warning_time_s'] as num).toStringAsFixed(1)} שנ\'', 9); // הטקסט
      s.paint(canvas, Offset((w - s.width) / 2, 28)); // באמצע
    }
  }

  @override
  bool shouldRepaint(covariant RtTimelinePainter old) => !identical(old.track, track); // רק בתוצאה חדשה
}

double _drop(double d) => d * d / (2 * 6371000.0) * (1 - 0.13); // ירידת קו הראייה — אותה נוסחה כמו במנוע

/// גרף צד: מרחק קרקעי (מימין לשמאל) מול גובה — השטח החוסם, שדה הראייה האנכי, תקרת המכ"ם ונקודות המסלול.
class RtSidePainter extends CustomPainter {
  RtSidePainter(this.result);
  final Map result; // התוצאה

  @override
  void paint(Canvas canvas, Size size) {
    final pts = (result['points'] as List).cast<Map>(); // הנקודות
    final hm = ((result['radar'] as Map)['h_msl'] as num).toDouble(); // גובה האנטנה
    final beam = result['beam'] as Map; // אזור הכיסוי
    double dmax = 0, amax = hm, amin = hm; // טווחים
    for (final p in pts) { dmax = max(dmax, (p['dist_km'] as num) * 1000.0); amax = max(amax, (p['alt'] as num).toDouble()); amin = min(amin, (p['alt'] as num).toDouble()); }
    dmax = max(1000, dmax * 1.08); final pad = (amax - amin) * 0.1 + 50; amax += pad; amin = max(-100, amin - pad / 2); // שוליים
    const l0 = 30.0, t0 = 6.0; final r0 = size.width - 6, b0 = size.height - 16; // אזור הציור
    double X(double d) => r0 - d / dmax * (r0 - l0); // מרחק -> פיקסל (0 מימין)
    double Y(double a) => b0 - (a - amin) / (amax - amin) * (b0 - t0); // גובה -> פיקסל
    canvas.save(); canvas.clipRect(Rect.fromLTRB(l0, t0, r0, b0)); // חיתוך
    for (final p in pts) { // השטח החוסם בכיוון של כל נקודה
      if (p['horizon_deg'] == null) continue; // אין נתון
      final d = (p['dist_km'] as num) * 1000.0, hz = (p['horizon_deg'] as num) * pi / 180; // מרחק ואופק
      final hgt = hm + d * tan(hz) + _drop(d); // גובה קו האופק
      canvas.drawRect(Rect.fromLTRB(X(d) - 1, Y(hgt), X(d) + 1, b0), Paint()..color = const Color(0x59786450)); // עמודה חומה
    }
    final dash = Paint()..style = PaintingStyle.stroke..strokeWidth = 1; // קווי הכיסוי
    for (final e in [(beam['v_lo_deg'] as num).toDouble(), (beam['v_hi_deg'] as num).toDouble()]) { // שדה הראייה
      final path = Path(); // הקרן
      for (int k = 0; k <= 40; k++) { final d = dmax * k / 40; final a = hm + d * tan(e.clamp(-89.0, 89.0) * pi / 180) + _drop(d);
        k == 0 ? path.moveTo(X(d), Y(a)) : path.lineTo(X(d), Y(a)); }
      canvas.drawPath(path, dash..color = const Color(0xFF22D3EE)); // תכלת
    }
    final cM = (beam['ceiling_km'] as num) * 1000.0, path = Path(); // קשת התקרה
    for (int k = 0; k <= 40; k++) {
      final e = ((beam['v_lo_deg'] as num) + ((beam['v_hi_deg'] as num) - (beam['v_lo_deg'] as num)) * k / 40) * pi / 180; // זווית
      final d = cM * cos(e), a = hm + cM * sin(e) + _drop(d); // נקודה על הקשת
      k == 0 ? path.moveTo(X(d), Y(a)) : path.lineTo(X(d), Y(a));
    }
    canvas.drawPath(path, dash..color = const Color(0xFFA855F7)); // סגול
    for (final p in pts) { canvas.drawRect(Rect.fromCenter(center: Offset(X((p['dist_km'] as num) * 1000.0), Y((p['alt'] as num).toDouble())), width: 3, height: 3), Paint()..color = _keyColor(p)); } // המסלול
    canvas.restore(); // סוף החיתוך
    canvas.drawCircle(Offset(X(0), Y(hm)), 3, Paint()..color = const Color(0xFF111111)); // המכ"ם
    _tp('0', 9).paint(canvas, Offset(r0 - 6, size.height - 13)); // אפס (ימין)
    _tp('${(dmax / 1000).toStringAsFixed(1)} ק"מ', 9).paint(canvas, Offset(l0, size.height - 13)); // מרחק מרבי
    _tp('${amax.round()} מ\'', 8).paint(canvas, const Offset(0, 4)); // גובה עליון
    _tp('${amin.round()} מ\'', 8).paint(canvas, Offset(0, b0 - 10)); // גובה תחתון
  }

  @override
  bool shouldRepaint(covariant RtSidePainter old) => !identical(old.result, result); // רק בתוצאה חדשה
}

/// פרופיל שטח לנקודה: שטח "אפקטיבי" (גובה פחות ירידת העקמומיות), קו ראייה ירוק/אדום ונקודת החסימה.
class RtProfilePainter extends CustomPainter {
  RtProfilePainter(this.pr);
  final Map pr; // הפרופיל

  @override
  void paint(Canvas canvas, Size size) {
    final dists = (pr['dists'] as List).cast<num>(), elevs = pr['elevs'] as List, drops = (pr['drops'] as List).cast<num>(); // נתונים
    final dist = (pr['dist_m'] as num).toDouble(), hm = (pr['radar_h_msl'] as num).toDouble(); // מרחק וגובה אנטנה
    final tgt = (pr['target_alt'] as num).toDouble() - _drop(dist); // הנקודה במערכת האפקטיבית
    final eff = [for (int i = 0; i < dists.length; i++) elevs[i] == null ? null : (elevs[i] as num).toDouble() - drops[i]]; // שטח אפקטיבי
    final vals = [...eff.whereType<double>(), hm, tgt]; // כל הערכים
    var lo = vals.reduce(min), hi = vals.reduce(max); final pad = (hi - lo) * 0.1 + 10; lo -= pad; hi += pad; // טווח
    final w = size.width, h = size.height; // מידות
    double X(double d) => w - 4 - d / dist * (w - 8); // מרחק -> פיקסל (המכ"ם מימין)
    double Y(double a) => h - 4 - (a - lo) / (hi - lo) * (h - 8); // גובה -> פיקסל
    final ground = Path()..moveTo(X(0), h); // השטח
    for (int i = 0; i < dists.length; i++) { if (eff[i] != null) ground.lineTo(X(dists[i].toDouble()), Y(eff[i]!)); }
    ground..lineTo(X(dist), h)..close(); // סגירה
    canvas.drawPath(ground, Paint()..color = const Color(0xFFC8B28A)); // חום
    final visible = pr['visible'] == true; // פנוי?
    canvas.drawLine(Offset(X(0), Y(hm)), Offset(X(dist), Y(tgt)),
        Paint()..color = visible ? const Color(0xFF00CC44) : const Color(0xFFFF3300)..strokeWidth = 2); // קו הראייה
    if (pr['block_dist_m'] != null) { // נקודת החסימה
      final bd = (pr['block_dist_m'] as num).toDouble(); // המרחק
      canvas.drawCircle(Offset(X(bd), Y(hm + (tgt - hm) * bd / dist)), 3, Paint()..color = const Color(0xFFFF3300)); // עיגול אדום
    }
  }

  @override
  bool shouldRepaint(covariant RtProfilePainter old) => !identical(old.pr, pr); // רק בפרופיל חדש
}

/// מקרא מפת החום: פס הסולם מימין (נמוך) לשמאל (גבוה), מינימום, מקסימום ושם הציון — בצבע טקסט.
class RtLegendPainter extends CustomPainter {
  RtLegendPainter(this.lo, this.hi, this.name, this.unit);
  final double lo, hi; // טווח
  final String name, unit; // שם ויחידה

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width; // רוחב
    for (double x = 0; x < w - 8; x++) { canvas.drawRect(Rect.fromLTWH(4 + x, 2, 1, 12), Paint()..color = rtSeqColor(1 - x / (w - 9))); } // הפס
    final a = _tp('$lo$unit', 9), b = _tp('$hi$unit', 9), n = _tp(name, 9); // טקסטים
    a.paint(canvas, Offset(w - 4 - a.width, 16)); // מינימום (ימין)
    b.paint(canvas, const Offset(4, 16)); // מקסימום (שמאל)
    n.paint(canvas, Offset((w - n.width) / 2, 16)); // שם
  }

  @override
  bool shouldRepaint(covariant RtLegendPainter old) => old.lo != lo || old.hi != hi || old.name != name; // שינוי
}
