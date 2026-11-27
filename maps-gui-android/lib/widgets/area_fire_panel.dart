// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'dart:math'; // מינימום/מקסימום למפות החום

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' show LatLng; // רק LatLng (ראה radar_track_layers.dart)
import 'package:provider/provider.dart';

import '../services/file_bridge.dart'; // שמירת CSV
import '../state/area_fire_controller.dart'; // הבקר
import '../state/radar_track_controller.dart'; // המכ"מים המוצבים (החלטה 14)

const _green = Color(0xFF1E9E3A), _red = Color(0xFFD93025); // נצפה / לא נצפה — כמו בדסקטופ
const _launchC = Color(0xFFE8710A), _targetC = Color(0xFF8E44AD); // שיגור / מטרה — כמו בדסקטופ

double _d(dynamic v) => (v as num).toDouble(); // מספר מ-JSON → double

/// A6: שכבות המפה של "מאזור לאזור" — אזורים, ציור פעיל, מפות חום, מסלולים ירוק/אדום ומסלול נבחר.
List<Widget> buildAreaFireLayers(AreaFireController c) {
  final layers = <Widget>[]; // התוצאה
  if (c.areas.isNotEmpty) { // אזורים
    layers.add(PolygonLayer(polygons: [
      for (final a in c.areas)
        Polygon(points: a.points, color: (a.kind == 'launch' ? _launchC : _targetC).withAlpha(25), // מילוי עדין
            borderColor: a.kind == 'launch' ? _launchC : _targetC, borderStrokeWidth: 2, // גבול
            pattern: a.kind == 'target' ? StrokePattern.dashed(segments: [8, 4]) : const StrokePattern.solid()), // מטרה מקווקו — לא רק צבע (לא const: הבנאי בודק את אורך הרשימה בזמן ריצה)
    ]));
  }
  if (c.drawing && c.drawPts.isNotEmpty) { // ציור פעיל
    final col = c.drawKind == 'launch' ? _launchC : _targetC; // צבע
    layers.add(PolylineLayer(polylines: [Polyline(points: c.drawPts, color: col, strokeWidth: 2, pattern: const StrokePattern.dotted())])); // קו זמני
    layers.add(CircleLayer(circles: [for (final p in c.drawPts) CircleMarker(point: p, radius: 4, color: col)])); // הנקודות
  }
  final r = c.result; // התוצאה
  if (r == null) return layers; // אין עוד תוצאה
  for (final x in [if (c.heatL) ['launch', (r['resolution_m'] as Map)['launch'], const Color(0xFFDEEBF7), const Color(0xFF08519C)],  // שיגור בכחול
                   if (c.heatT) ['target', (r['resolution_m'] as Map)['target'], const Color(0xFFF2F0F7), const Color(0xFF54278F)]]) { // מטרה בסגול
    final pts = ((r['heat'] as Map)[x[0]] as List).cast<Map>(); // התאים
    final mx = max(1, pts.fold<int>(0, (m, p) => max(m, (p['count'] as num).toInt()))); // המרבי
    final half = _d(x[1]) / 2 / 111320.0; // חצי תא ברוחב
    layers.add(PolygonLayer(polygons: [
      for (final p in pts)
        Polygon(points: () { final la = _d(p['lat']), lo = _d(p['lon']), dl = half / cos(la * pi / 180); // תא סביב הנקודה
                  return [LatLng(la - half, lo - dl), LatLng(la - half, lo + dl), LatLng(la + half, lo + dl), LatLng(la + half, lo - dl)]; }(),
            color: Color.lerp(x[2] as Color, x[3] as Color, (p['count'] as num) / mx)!.withAlpha((p['count'] as num) > 0 ? 180 : 60)), // צבע בסולם רציף
    ]));
  }
  if (c.showPaths) { // מסלולים
    final rows = r['rows'] as List; // השורות
    final lines = <Polyline>[]; // הקטעים
    for (final i in c.thinned(c.filtered())) { // אחרי סינון ודילול
      final path = ((rows[i] as Map)['path'] as List).cast<List>(); // 21 נקודות
      final m = c.masks?[i]; // מסיכת הנראות (null = לא חושבה → הכול אדום)
      var seg = <LatLng>[LatLng(_d(path[0][0]), _d(path[0][1]))]; // קטע נוכחי
      var cur = m != null && m[0] != 0; // צבעו
      for (var k = 1; k < path.length; k++) { // כל נקודה
        final pt = LatLng(_d(path[k][0]), _d(path[k][1])); // הנקודה
        final vis = m != null && m[k] != 0; // נראית?
        seg.add(pt); // ממשיכים את הקטע
        if (vis != cur) { lines.add(Polyline(points: seg, color: (cur ? _green : _red).withAlpha(190), strokeWidth: 2)); seg = [pt]; cur = vis; } // מעבר צבע
      }
      if (seg.length > 1) lines.add(Polyline(points: seg, color: (cur ? _green : _red).withAlpha(190), strokeWidth: 2)); // הקטע האחרון
    }
    layers.add(PolylineLayer(polylines: lines)); // שכבה אחת
  }
  final sel = c.selected; // מסלול נבחר
  if (sel != null && sel < (r['rows'] as List).length) {
    final path = (((r['rows'] as List)[sel] as Map)['path'] as List).cast<List>(); // הנקודות
    layers.add(PolylineLayer(polylines: [Polyline(points: [for (final p in path) LatLng(_d(p[0]), _d(p[1]))], color: const Color(0xFF1565C0), strokeWidth: 5)])); // הדגשה בכחול
  }
  return layers; // השכבות
}

/// A6: לוח "מאזור לאזור" בתוך הכלי הבליסטי (מוצג במקום התותח/המטרה והטאבים כשהמתג על "מאזור לאזור").
class AreaFirePanel extends StatefulWidget {
  const AreaFirePanel({super.key, required this.cs, required this.commonParams, required this.onOpenSingle}); // בנאי
  final ColorScheme cs; // צבעים
  final Map<String, dynamic> Function() commonParams; // מהירות לוע, מטאו, פגז — מהכלי הבליסטי
  final void Function(List launch, List target) onOpenSingle; // "פתח במסלול בודד"

  @override
  State<AreaFirePanel> createState() => _AreaFirePanelState();
}

class _AreaFirePanelState extends State<AreaFirePanel> {
  final _qeMin = TextEditingController(), _qeMax = TextEditingController(), _minRange = TextEditingController(); // גבולות
  final _maxTof = TextEditingController(), _margin = TextEditingController(text: '0'); // זמן מעוף ומרווח
  String? _set; // סט נבחר

  @override
  void initState() {
    super.initState(); // בסיס
    final c = context.read<AreaFireController>(); // הבקר
    c.commonParams = widget.commonParams; // חיבור לפרמטרי הירי
    WidgetsBinding.instance.addPostFrameCallback((_) => c.loadSetNames()); // הסטים השמורים
  }

  @override
  void dispose() {
    for (final t in [_qeMin, _qeMax, _minRange, _maxTof, _margin]) { t.dispose(); } // ניקוי
    super.dispose(); // בסיס
  }

  Widget _btn(String text, String tip, VoidCallback? fn, {Color? border}) => Tooltip(message: tip, // כפתור קטן ≥44 גובה מגע
      child: OutlinedButton(onPressed: fn, style: OutlinedButton.styleFrom(minimumSize: const Size(44, 36), padding: const EdgeInsets.symmetric(horizontal: 6),
          side: border != null ? BorderSide(color: border) : null, textStyle: const TextStyle(fontSize: 10)), child: Text(text)));

  Widget _num(String label, TextEditingController t, void Function(double?) set) => Row(children: [ // שדה מספר (ריק = בלי)
        Expanded(child: Text(label, style: TextStyle(fontSize: 9.5, color: widget.cs.onSurfaceVariant))), // תווית
        SizedBox(width: 64, child: Semantics(label: label, child: TextField(controller: t, keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true), // השדה
            style: const TextStyle(fontSize: 11), textAlign: TextAlign.center, decoration: const InputDecoration(isDense: true, contentPadding: EdgeInsets.symmetric(vertical: 6)),
            onChanged: (v) { set(double.tryParse(v)); context.read<AreaFireController>().scheduleEstimate(); }))), // עדכון + הערכה
      ]);

  Widget _chk(String label, bool v, void Function(bool) set) => InkWell(onTap: () => set(!v), // תיבת סימון עם שטח מגע
      child: Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(v ? Icons.check_box : Icons.check_box_outline_blank, size: 16, color: widget.cs.primary), const SizedBox(width: 3),
        Text(label, style: TextStyle(fontSize: 9.5, color: widget.cs.onSurface)),
      ])));

  Future<void> _rename(AreaFireController c, int i) async { // שינוי שם אזור
    final t = TextEditingController(text: c.areas[i].name); // השדה
    final ok = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: const Text('שם האזור'), content: TextField(controller: t, autofocus: true),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('ביטול')), TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('שמור'))]));
    if (ok == true) c.renameArea(i, t.text); // עדכון
    t.dispose(); // ניקוי
  }

  Future<void> _saveSet(AreaFireController c) async { // שמירת סט
    final t = TextEditingController(text: 'אזורים'); // ברירת מחדל
    final ok = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: const Text('שם לסט האזורים'), content: TextField(controller: t, autofocus: true),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('ביטול')), TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('שמור'))]));
    if (ok == true && t.text.trim().isNotEmpty) await c.saveSet(t.text.trim()); // שמירה
    t.dispose(); // ניקוי
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.cs; // צבעים
    final c = context.watch<AreaFireController>(); // הבקר
    final sites = context.watch<RadarTrackController>().sites; // המכ"מים המוצבים
    final r = c.result; // התוצאה
    final idx = r != null ? c.filtered() : const <int>[]; // מסלולים אחרי סינון
    final small = TextStyle(fontSize: 9.5, color: cs.onSurfaceVariant); // טקסט משני
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('סמן אזורי שיגור (רשת כל 500 מ\') ואזורי מטרה (כל 200 מ\') בהקשות על המפה. מהירות הלוע, המטאו והפגז נלקחים מההגדרות למעלה.', style: small), // הסבר
      Wrap(spacing: 3, runSpacing: 3, children: [ // כפתורי ציור
        _btn('✏️ מצולע שיגור', 'הקשות על המפה, ואז "סיים"', () => c.startDraw('launch', 'poly'), border: _launchC),
        _btn('▭ מלבן שיגור', 'שתי הקשות: פינה ופינה נגדית', () => c.startDraw('launch', 'rect'), border: _launchC),
        _btn('✏️ מצולע מטרה', 'הקשות על המפה, ואז "סיים"', () => c.startDraw('target', 'poly'), border: _targetC),
        _btn('▭ מלבן מטרה', 'שתי הקשות: פינה ופינה נגדית', () => c.startDraw('target', 'rect'), border: _targetC),
      ]),
      if (c.drawing) Row(children: [ // ציור פעיל
        Expanded(child: Text(c.drawShape == 'rect' ? (c.drawPts.isEmpty ? 'הקש על פינה ראשונה…' : 'הקש על הפינה הנגדית…') : '${c.drawPts.length} נקודות — המשך, או "סיים"', style: TextStyle(fontSize: 9.5, color: cs.primary))),
        if (c.drawShape == 'poly') _btn('✔ סיים', 'סיום המצולע', () { final e = c.finishDraw(); if (e != null) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e))); }),
        _btn('בטל', 'ביטול הציור', c.cancelDraw),
      ]),
      for (var i = 0; i < c.areas.length; i++) Row(children: [ // רשימת האזורים
        Text(c.areas[i].kind == 'launch' ? '🚀' : '🎯'), const SizedBox(width: 3), // סמל סוג
        Expanded(child: InkWell(onTap: () => _rename(c, i), child: Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(c.areas[i].name, style: TextStyle(fontSize: 10, color: cs.onSurface))))), // שם (הקשה = שינוי)
        IconButton(tooltip: 'מחיקת האזור', icon: const Icon(Icons.close, size: 16), onPressed: () => c.removeArea(i)), // מחיקה
      ]),
      if (c.areas.isEmpty) Text('אין עדיין אזורים.', style: small), // ריק
      Row(children: [ // סטים שמורים
        Expanded(child: DropdownButton<String>(isExpanded: true, isDense: true, value: c.setNames.contains(_set) ? _set : null, hint: Text('סטים שמורים', style: small),
            items: [for (final n in c.setNames) DropdownMenuItem(value: n, child: Text(n, style: const TextStyle(fontSize: 10)))], onChanged: (v) => setState(() => _set = v))),
        IconButton(tooltip: 'טען סט', icon: const Icon(Icons.folder_open, size: 18), onPressed: _set == null ? null : () => c.loadSet(_set!)),
        IconButton(tooltip: 'שמור את האזורים כסט', icon: const Icon(Icons.save_outlined, size: 18), onPressed: c.areas.isEmpty ? null : () => _saveSet(c)),
        IconButton(tooltip: 'מחק סט', icon: const Icon(Icons.delete_outline, size: 18), onPressed: _set == null ? null : () { c.deleteSet(_set!); setState(() => _set = null); }),
      ]),
      Text('אפשרויות', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.bold, color: cs.onSurfaceVariant)), // כותרת
      Wrap(spacing: 10, children: [ // ענפים ורכס
        _chk('ענף נמוך', c.low, (v) => c.update(() { c.low = v; c.scheduleEstimate(); })),
        _chk('ענף גבוה', c.high, (v) => c.update(() { c.high = v; c.scheduleEstimate(); })),
        _chk('בדיקת רכס', c.crest, (v) => c.update(() { c.crest = v; c.scheduleEstimate(); })),
      ]),
      _num('הגבהה מינימלית [מיל]', _qeMin, (v) => c.qeMin = v), // גבולות
      _num('הגבהה מרבית [מיל]', _qeMax, (v) => c.qeMax = v),
      _num('טווח מינימלי [מ\']', _minRange, (v) => c.minRange = v),
      _num('זמן מעוף מרבי [ש\']', _maxTof, (v) => c.maxTof = v),
      _num('מרווח מעל השטח [מ\']', _margin, (v) => c.margin = v ?? 0),
      if (c.estimate.isNotEmpty) Text(c.estimate, style: small), // ההערכה
      Row(children: [ // הרצה וביטול
        Expanded(child: FilledButton(onPressed: c.running ? null : c.run, style: FilledButton.styleFrom(minimumSize: const Size(44, 40)), child: const Text('▶ חשב מסלולים', style: TextStyle(fontSize: 11)))),
        if (c.running) ...[const SizedBox(width: 4), _btn('⏹ בטל', 'ביטול החישוב', c.cancel)],
      ]),
      if (c.status.isNotEmpty) Semantics(liveRegion: true, child: SelectableText(c.status, style: TextStyle(fontSize: 9.5, color: cs.onSurface))), // מצב/סיכום
      if (r != null) ...[ // תוצאות
        const Divider(height: 8),
        Row(children: [ // צביעה (החלטה 16)
          _btn('🎨 עדכן צביעה', 'צביעה לפי כל המכ"מים המוצבים', () => c.recolor(sites), border: _green),
          const SizedBox(width: 4),
          if (c.isStale(sites)) Expanded(child: Text('⚠️ המכ"מים השתנו — הצביעה ישנה', style: TextStyle(fontSize: 9, color: cs.error))),
        ]),
        Text('🟩 ירוק = לפחות מכ"ם מוצב אחד רואה את הקטע · 🟥 אדום = אף מכ"ם לא רואה (או שלא נצבע). "רואה" = בטווח, בגזרה ולא מוסתר ע"י השטח (קירוב).', style: TextStyle(fontSize: 8.5, color: cs.onSurfaceVariant)), // מקרא
        Wrap(spacing: 8, children: [ // שכבות
          _chk('מסלולים', c.showPaths, (v) => c.update(() => c.showPaths = v)),
          _chk('חום שיגור', c.heatL, (v) => c.update(() => c.heatL = v)),
          _chk('חום מטרה', c.heatT, (v) => c.update(() => c.heatT = v)),
        ]),
        Wrap(spacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [ // סינון
          DropdownButton<String>(isDense: true, value: c.fBranch, items: const [DropdownMenuItem(value: 'all', child: Text('כל הענפים', style: TextStyle(fontSize: 10))),
              DropdownMenuItem(value: 'low', child: Text('נמוך', style: TextStyle(fontSize: 10))), DropdownMenuItem(value: 'high', child: Text('גבוה', style: TextStyle(fontSize: 10)))],
              onChanged: (v) => c.update(() => c.fBranch = v ?? 'all')),
          DropdownButton<int>(isDense: true, value: c.fLaunch, items: [const DropdownMenuItem(value: -1, child: Text('כל השיגור', style: TextStyle(fontSize: 10))),
              for (var i = 0; i < ((r['areas'] as Map)['launch'] as List).length; i++) DropdownMenuItem(value: i, child: Text('${((r['areas'] as Map)['launch'] as List)[i]}', style: const TextStyle(fontSize: 10)))],
              onChanged: (v) => c.update(() => c.fLaunch = v ?? -1)),
          DropdownButton<int>(isDense: true, value: c.fTarget, items: [const DropdownMenuItem(value: -1, child: Text('כל המטרות', style: TextStyle(fontSize: 10))),
              for (var i = 0; i < ((r['areas'] as Map)['target'] as List).length; i++) DropdownMenuItem(value: i, child: Text('${((r['areas'] as Map)['target'] as List)[i]}', style: const TextStyle(fontSize: 10)))],
              onChanged: (v) => c.update(() => c.fTarget = v ?? -1)),
          _chk('רק לא נצפים', c.fUnseen, (v) => c.update(() => c.fUnseen = v)),
        ]),
        Text(idx.length > AreaFireController.maxDraw ? 'מוצגים ${AreaFireController.maxDraw} מתוך ${idx.length} מסלולים (דילול תצוגה — כולם נספרים).' : '${idx.length} מסלולים מוצגים.', style: small), // דילול
        _btn('⬇ CSV', 'ייצוא כל המסלולים לקובץ CSV', () async { // ייצוא
          try {
            final text = await c.csv(); // הטקסט
            if (text == null) return; // אין
            final saved = await FileBridge.saveText('area_fire.csv', 'text/csv', text); // שמירה/שיתוף
            if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(saved ? 'נשמר ✔' : 'בוטל'))); // משוב
          } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('ייצוא נכשל: $e'))); } // כשל
        }),
        SizedBox(height: 170, child: ListView.builder( // טבלה (100 ראשונים)
          itemCount: min(100, idx.length),
          itemBuilder: (_, k) {
            final i = idx[k], row = (r['rows'] as List)[i] as Map, m = c.masks?[i]; // המסלול
            final seen = m == null ? '—' : '${(100 * m.where((x) => x != 0).length / m.length).round()}%'; // אחוז נצפה
            return InkWell(onTap: () => c.update(() => c.selected = i), child: Container( // בחירה
              color: c.selected == i ? cs.primary.withAlpha(40) : null, padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 2),
              child: Text('${((r['areas'] as Map)['launch'] as List)[row['la']]} #${(row['lp'] as num) + 1} → ${((r['areas'] as Map)['target'] as List)[row['ta']]} #${(row['tp'] as num) + 1} · '
                  '${row['group'] == 'low' ? 'נמוך' : 'גבוה'} · ${(row['qe'] as Map)['mils']} מיל · ${row['tof_s']} ש\' · נצפה $seen', style: const TextStyle(fontSize: 9.5)),
            ));
          },
        )),
        if (c.selected != null && c.selected! < (r['rows'] as List).length) Builder(builder: (_) { // פרטי מסלול נבחר
          final row = (r['rows'] as List)[c.selected!] as Map, m = c.masks?[c.selected!]; // המסלול
          var bits = 0; for (final x in m ?? const <int>[]) { bits |= x; } // מי ראה
          final who = [for (var b = 0; b < c.visRadars.length; b++) if (bits & (1 << b) != 0) c.visRadars[b]]; // שמות
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('🔵 טווח ${(row['range_m'] as num).round()} מ\' · הגבהה ${(row['qe'] as Map)['mils']} מיל · אזימוט ירי ${(row['fire_azimuth'] as Map)['mils']} מיל · קודקוד ${(row['apex_msl_m'] as num).round()} מ\'\n'
                '${m == null ? 'הצביעה עוד לא חושבה' : 'נצפה ע"י: ${who.isEmpty ? 'אף מכ"ם' : who.join(', ')}'}', style: TextStyle(fontSize: 9.5, color: cs.onSurface)),
            _btn('🔍 פתח במסלול בודד', 'מציב את התותח והמטרה של המסלול הזה בכלי הבודד, לחישוב מדויק', () => widget.onOpenSingle(row['launch'] as List, row['target'] as List)),
          ]);
        }),
      ],
    ]);
  }
}
