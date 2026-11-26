// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/map_state.dart';
import '../state/radar_track_controller.dart';
import 'radar_track_layers.dart';

/// פאנל כלי בדיקת מעקב המכ"ם באנדרואיד (שלב ג', MAPS-GUI_SRS.md FR-D-283) — מקביל לטאב "🎯 מעקב מכ"ם" בדסקטופ:
/// מקור מסלול, סריקה ומעקב, RCS וגשם, פרופילים, הפעלה, סיכום, ציר זמן, גרף צד, פרופיל שטח, CSV והצעת מיקום.
/// פאנל נפרד ונגלל (ולא טאב בפאנל הבליסטי, שגובה טאב בו 230 פיקסלים). פרמטרי המכ"ם — מכלי הדופלר הקיים.
class RadarTrackPanel extends StatefulWidget {
  const RadarTrackPanel({super.key, required this.cs});
  final ColorScheme cs; // ערכת הצבעים

  @override
  State<RadarTrackPanel> createState() => _RadarTrackPanelState();
}

class _RadarTrackPanelState extends State<RadarTrackPanel> {
  bool _open = false; // מצומצם / פתוח — כמו שאר הכלים
  final _profName = TextEditingController(); // שם פרופיל לשמירה
  String? _profSel; // פרופיל שנבחר
  List<String> _profNames = []; // הפרופילים השמורים
  String _profStatus = ''; // הודעת פרופילים

  @override
  void dispose() {
    _profName.dispose(); // ניקוי
    super.dispose();
  }

  Future<void> _refreshProfiles(RadarTrackController c) async {
    final names = await c.profileNames(); // מהאחסון
    if (!mounted) return; // נסגר
    setState(() { _profNames = names; if (!names.contains(_profSel)) _profSel = names.isEmpty ? null : names.first; }); // עדכון
  }

  // ── רכיבי טופס קטנים ──
  Widget _num(String label, double value, void Function(double) onChanged, {String? tip}) =>
      _NumField(label: label, value: value, onChanged: onChanged, cs: widget.cs, tip: tip); // שדה מספרי

  Widget _drop<T>(String label, T value, List<(T, String)> items, void Function(T) onChanged) {
    final cs = widget.cs; // צבעים
    return Row(children: [
      Expanded(child: Text(label, style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant))), // תווית
      DropdownButton<T>(
        value: value, isDense: true, // הערך
        items: [for (final it in items) DropdownMenuItem<T>(value: it.$1, child: Text(it.$2, style: const TextStyle(fontSize: 10)))], // אפשרויות
        onChanged: (v) { if (v != null) onChanged(v); }, // שינוי
      ),
    ]);
  }

  Widget _section(String title, List<Widget> children) => Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent), // בלי קווי הפרדה
        child: ExpansionTile(
          title: Text(title, style: const TextStyle(fontSize: 10.5)), // כותרת
          tilePadding: EdgeInsets.zero, childrenPadding: const EdgeInsets.only(bottom: 4), dense: true, // צפוף
          children: children,
        ),
      );

  Widget _small(String text) => Text(text, style: TextStyle(fontSize: 9, color: widget.cs.onSurfaceVariant)); // טקסט משני

  Widget _btn(String text, VoidCallback? onTap, {bool primary = false}) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 1.5),
        child: primary
            ? FilledButton.tonal(onPressed: onTap, child: Text(text, style: const TextStyle(fontSize: 10.5))) // ראשי
            : OutlinedButton(onPressed: onTap, child: Text(text, style: const TextStyle(fontSize: 10))), // משני
      );

  // ── מקור המסלול ──
  List<Widget> _sourceFields(RadarTrackController c) {
    final f = <Widget>[]; // השדות
    final u = c.update; // עדכון
    if (const ['custom', 'loiter', 'csv'].contains(c.source)) {
      f.add(_drop('גובה המסלול', c.altRef, const [('msl', 'מעל פני הים'), ('agl', 'מעל הקרקע')], (v) => u(() => c.altRef = v))); // ייחוס
    }
    switch (c.source) {
      case 'ballistic':
        f.add(_small(c.ballisticPath == null ? 'חשב מסלול בפאנל הבליסטי (מסלול בודד / פתרון ירי)' : 'מסלול אחרון: ${c.ballisticPath!.length} נקודות ✔'));
        break;
      case 'rocket':
        f.add(_small('המשגר = התותח בפאנל הבליסטי. דחף קבוע ואחריו מעוף בליסטי — מודל רעיוני.'));
        f.addAll([
          _num('זווית שיגור [°]', c.rkElev, (v) => u(() => c.rkElev = v)), _num('אזימוט [°]', c.rkAz, (v) => u(() => c.rkAz = v)),
          _num('מסה בשיגור [ק"ג]', c.rkMass, (v) => u(() => c.rkMass = v)), _num('מסת דלק [ק"ג]', c.rkProp, (v) => u(() => c.rkProp = v)),
          _num('זמן בעירה [שנ\']', c.rkBurn, (v) => u(() => c.rkBurn = v)), _num('דחף [N]', c.rkThrust, (v) => u(() => c.rkThrust = v)),
          _num('קוטר [מ\']', c.rkDiam, (v) => u(() => c.rkDiam = v)), _num('מקדם גרר Cd', c.rkCd, (v) => u(() => c.rkCd = v)),
        ]);
        break;
      case 'fr24':
        f.add(Row(children: [
          Checkbox(value: c.frRcsAuto, onChanged: (v) => u(() => c.frRcsAuto = v ?? true)), // RCS אוטומטי
          Expanded(child: _small('RCS לפי סוג המטוס (במקום השדה בכלי הדופלר)')),
        ]));
        break;
      case 'custom':
        f.addAll([_num('מהירות [קשר]', c.customSpeedKt, (v) => u(() => c.customSpeedKt = v)),
                  _num('גובה לנקודות בלי גובה [מ\']', c.customDefaultAlt, (v) => u(() => c.customDefaultAlt = v))]);
        break;
      case 'loiter':
        f.add(Row(children: [
          _btn(c.pick == RtPick.loiter ? 'לחץ על המפה…' : '📍 בחר מרכז', () => u(() => c.pick = RtPick.loiter)), // בחירה
          Expanded(child: _small(c.loiterCenter == null ? 'לא נבחר' : '${c.loiterCenter!.latitude.toStringAsFixed(4)}, ${c.loiterCenter!.longitude.toStringAsFixed(4)}')),
        ]));
        f.addAll([
          _num('רדיוס [מ\']', c.loiterRadius, (v) => u(() => c.loiterRadius = v)), _num('גובה [מ\']', c.loiterAlt, (v) => u(() => c.loiterAlt = v)),
          _num('מהירות [קשר]', c.loiterSpeedKt, (v) => u(() => c.loiterSpeedKt = v)),
          _num('מספר סיבובים', c.loiterLaps.toDouble(), (v) => u(() => c.loiterLaps = v.round().clamp(1, 50))),
          _drop('כיוון', c.loiterCw, const [(true, 'עם כיוון השעון'), (false, 'נגד כיוון השעון')], (v) => u(() => c.loiterCw = v)),
        ]);
        break;
      case 'csv':
        f.add(Row(children: [_btn('📂 טען CSV', c.loadCsv), Expanded(child: _small(c.csvLabel.isEmpty ? 't, lat, lon, alt [מ\']' : c.csvLabel))]));
        break;
    }
    return f; // השדות
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.cs; // צבעים
    final c = context.watch<RadarTrackController>(); // הבקר
    final map = context.watch<MapState>(); // מיקום המכ"ם
    if (!_open) { // מצומצם — אייקון בלבד, כמו שאר הכלים
      return Material(
        color: cs.surface.withAlpha(230), shape: const CircleBorder(), elevation: 3,
        child: Semantics(
          label: 'פתח כלי בדיקת מעקב מכ"ם', // נגישות
          child: InkWell(customBorder: const CircleBorder(), onTap: () { setState(() => _open = true); _refreshProfiles(c); },
              child: Padding(padding: const EdgeInsets.all(12), child: Icon(Icons.track_changes, size: 20, color: cs.onSurface))), // ≥44x44
        ),
      );
    }
    final u = c.update; // עדכון
    final r = c.result; // התוצאה
    final pl = c.placement; // מפת החום
    final isTrack = c.trackMode == 'track'; // מצב מעקב
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Material(
        color: cs.surface.withAlpha(240), borderRadius: BorderRadius.circular(10), elevation: 4,
        child: Container(
          width: 285, padding: const EdgeInsets.all(8),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [ // כותרת
              Row(children: [Icon(Icons.track_changes, size: 15, color: cs.primary), const SizedBox(width: 4),
                  Text('בדיקת מעקב מכ"ם', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: cs.onSurface))]),
              Semantics(label: 'סגור כלי בדיקת מעקב מכ"ם', child: InkWell(onTap: () => setState(() => _open = false),
                  child: Padding(padding: const EdgeInsets.all(15), child: Icon(Icons.close, size: 15, color: cs.onSurfaceVariant)))), // ≥44x44
            ]),
            _small('הפרמטרים של המכ"ם — מכלי תצפית המכ"ם או מהפרופיל הפעיל. פרופילי הספרייה מבוססים על נתונים פומביים בלבד — רעיוניים/חינוכיים, לא מפרט אמיתי.'), // FR-D-286
            ActiveProfileBar(cs: cs), // FR-D-286: בורר "פרופיל פעיל" — אותו בורר כמו בפאנל תצפית המכ"ם, מסונכרן דרך הבקר
            Row(children: [ // הצבת מכ"ם בלי לפתוח את כלי הדופלר
              _btn(c.pick == RtPick.radar ? 'לחץ על המפה…' : '📍 הצב/הזז מכ"ם', () => u(() => c.pick = RtPick.radar)),
              Expanded(child: _small(map.radarObs == null ? 'לא הוצב' : '${map.radarObs!.latitude.toStringAsFixed(4)}, ${map.radarObs!.longitude.toStringAsFixed(4)}')),
            ]),
            _drop('מקור המסלול', c.source, const [('ballistic', 'מסלול בליסטי אחרון'), ('rocket', 'רקטה (מודל דחיפה)'), ('fr24', 'טיסה שנטענה'),
                ('custom', 'מסלול מצויר'), ('loiter', 'שיוט במעגל'), ('csv', 'קובץ CSV')], (v) => u(() => c.source = v)),
            ..._sourceFields(c),
            _section('⚙ סריקה ומעקב', [
              _drop('מצב בדיקה', c.trackMode, const [('track', 'מעקב (סריקה + M מתוך N)'), ('detection', 'גילוי לכל נקודה')], (v) => u(() => c.trackMode = v)),
              if (isTrack) _drop('סוג סריקה', c.scanMode, const [('rotating', 'אנטנה מסתובבת'), ('phased', 'מערך-מופע'), ('tracker', 'מכ"ם מעקב ייעודי')], (v) => u(() => c.scanMode = v)),
              if (isTrack && c.scanMode == 'rotating') ...[_num('זמן סיבוב [שנ\']', c.rotPeriod, (v) => u(() => c.rotPeriod = v)),
                  _num('כיוון אלומה בהתחלה [°]', c.phase, (v) => u(() => c.phase = v))],
              if (isTrack && c.scanMode == 'phased') _num('זמן ביקור [שנ\']', c.revisit, (v) => u(() => c.revisit = v)),
              if (isTrack && c.scanMode == 'tracker') ...[_num('קצב עדכון [Hz]', c.trackRate, (v) => u(() => c.trackRate = v)),
                  _num('קצב סיבוב מרבי [°/שנ\']', c.maxAngRate, (v) => u(() => c.maxAngRate = v)),
                  _num('השהיית הכוונה [שנ\']', c.cueDelay, (v) => u(() => c.cueDelay = v))],
              if (isTrack) ...[_num('M — גילויים לפתיחה', c.trackM.toDouble(), (v) => u(() => c.trackM = v.round().clamp(1, 10))),
                  _num('N — מתוך הזדמנויות', c.trackN.toDouble(), (v) => u(() => c.trackN = v.round().clamp(1, 10))),
                  _num('זמן דעיכה [שנ\']', c.coast, (v) => u(() => c.coast = v))],
            ]),
            _section('⚙ RCS וגשם', [
              _drop('RCS', c.rcsMode, const [('fixed', 'קבוע (מכלי הדופלר)'), ('aspect', 'לפי זווית הסתכלות')], (v) => u(() => c.rcsMode = v)),
              if (c.rcsMode == 'aspect') ...[
                _drop<String>('מילוי מהיר (משוער)', '', const [('', '—'), ('0.005,0.02,0.01', 'פגז'), ('0.02,0.3,0.05', 'רקטה'),
                    ('0.01,0.03,0.01', 'רחפן קטן'), ('0.5,3,1', 'מטוס קל')], (v) {
                  if (v.isEmpty) return; // "—"
                  final x = v.split(',').map(double.parse).toList(); // חרטום, צד, זנב
                  u(() { c.rcsNose = x[0]; c.rcsSide = x[1]; c.rcsTail = x[2]; }); // מילוי
                }),
                _num('חרטום [מ"ר]', c.rcsNose, (v) => u(() => c.rcsNose = v)), _num('צד [מ"ר]', c.rcsSide, (v) => u(() => c.rcsSide = v)),
                _num('זנב [מ"ר]', c.rcsTail, (v) => u(() => c.rcsTail = v)),
              ],
              _num('עוצמת גשם [מ"מ/שעה]', c.rainRate, (v) => u(() => c.rainRate = v), tip: '0 = יבש'),
              _num('תקרת הגשם [מ\']', c.rainTop, (v) => u(() => c.rainTop = v)),
              _drop('קיטוב', c.pol, const [('h', 'אופקי'), ('v', 'אנכי'), ('c', 'מעגלי')], (v) => u(() => c.pol = v)),
              const Directionality(textDirection: TextDirection.ltr, // ציון מקור — חובה לפי החלטת הבעלים D8
                  child: Text('Rain attenuation model: Recommendation ITU-R P.838-3 (ITU)', style: TextStyle(fontSize: 8, color: Colors.grey))),
            ]),
            _section('💾 פרופילי מכ"ם', [
              Row(children: [
                Expanded(child: SizedBox(height: 30, child: TextField(controller: _profName, style: const TextStyle(fontSize: 11),
                    decoration: const InputDecoration(hintText: 'שם פרופיל', isDense: true, border: OutlineInputBorder())))), // שם
                IconButton(tooltip: 'שמור', icon: const Icon(Icons.save, size: 18), onPressed: () async { // שמירה
                  if (_profName.text.trim().isEmpty) return; // בלי שם
                  await c.saveProfile(_profName.text.trim()); _profName.clear(); await _refreshProfiles(c); }),
              ]),
              Row(children: [
                Expanded(child: DropdownButton<String>(value: _profSel, isExpanded: true, isDense: true, hint: _small('(אין פרופילים)'),
                    items: [for (final n in _profNames) DropdownMenuItem(value: n, child: Text(n, style: const TextStyle(fontSize: 10)))],
                    onChanged: (v) => setState(() => _profSel = v))), // בחירה
                IconButton(tooltip: 'טען', icon: const Icon(Icons.folder_open, size: 18), onPressed: _profSel == null ? null : () async {
                  final n = await c.loadProfile(_profSel!); setState(() => _profStatus = 'נטענו $n שדות ✔'); }), // טעינה
                IconButton(tooltip: 'מחק', icon: const Icon(Icons.delete_outline, size: 18), onPressed: _profSel == null ? null : () async {
                  await c.deleteProfile(_profSel!); await _refreshProfiles(c); }), // מחיקה
              ]),
              Row(children: [
                Expanded(child: _btn('⬇ ייצוא JSON', () async { final m = await c.exportProfileJson(); setState(() => _profStatus = m); })),
                Expanded(child: _btn('⬆ ייבוא JSON', () async { final m = await c.importProfileJson(); setState(() => _profStatus = m); })),
              ]),
              if (_profStatus.isNotEmpty) _small(_profStatus),
            ]),
            const SizedBox(height: 4),
            Row(children: [ // הפעלה
              Expanded(child: _btn('🎯 בדוק מעקב מכ"ם', c.running ? null : () => c.run(), primary: true)),
              _btn('בטל', c.running ? () => c.cancel() : null), _btn('נקה', r == null && c.rocketPath == null ? null : c.clear),
            ]),
            if (c.running) const LinearProgressIndicator(minHeight: 2), // התקדמות
            if (c.status.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4),
                child: SelectableText(c.status, style: TextStyle(fontSize: 9.5, color: cs.onSurface))), // הסיכום
            if (r != null && r['track'] != null) SizedBox(width: 269, height: 42, child: CustomPaint(painter: RtTimelinePainter(r['track'] as Map))), // ציר זמן
            if (r != null) ...[
              Row(children: [
                Checkbox(value: c.showFan, onChanged: (v) => u(() => c.showFan = v ?? true)), _small('קווי LOS מהמכ"ם'), const Spacer(), // מניפה
                _btn('⬇ CSV', () async { final m = await c.exportCsv(); if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('CSV: $m'))); }),
              ]),
              Container(decoration: BoxDecoration(border: Border.all(color: Colors.black12)),
                  child: SizedBox(width: 269, height: 120, child: CustomPaint(painter: RtSidePainter(r)))), // גרף צד
              _small('לחיצה על קטע במסלול או על קו LOS — פרטים ופרופיל שטח.'),
            ],
            _section('🗺 הצעת מיקום (מפת חום)', [
              _small('מיקומים סביב המכ"ם, על המסלול של הבדיקה האחרונה. רשת גבהים גסה — סינון ראשוני; מאמתים בבדיקה הרגילה.'),
              _num('רדיוס חיפוש [ק"מ]', c.plRadiusKm, (v) => u(() => c.plRadiusKm = v)),
              _num('מרווח בין מיקומים [מ\']', c.plStepM, (v) => u(() => c.plStepM = v)),
              _drop('מה נחשב טוב', c.plMetric, const [('warning', 'זמן התרעה מרבי'), ('coverage', 'אחוז כיסוי מרבי')], (v) => u(() => c.plMetric = v)),
              Row(children: [
                Expanded(child: _btn('🗺 חשב מפת חום', c.plRunning ? null : c.runPlacement, primary: true)),
                _btn('בטל', c.plRunning ? () => c.cancelPlacement() : null), _btn('נקה', pl == null ? null : c.clearPlacement),
              ]),
              if (c.plRunning) const LinearProgressIndicator(minHeight: 2),
              if (c.plStatus.isNotEmpty) _small(c.plStatus),
              if (pl != null) Builder(builder: (_) { // מקרא
                final sc = (pl['candidates'] as List).cast<Map>().where((m) => m['score'] != null).map((m) => (m['score'] as num).toDouble()).toList();
                if (sc.isEmpty) return const SizedBox.shrink(); // אין
                final unit = pl['metric'] == 'coverage' ? '%' : ' שנ\''; // יחידה
                final name = pl['metric'] == 'coverage' ? (pl['track_mode'] == 'track' ? 'במעקב' : 'כיסוי') : 'זמן התרעה'; // שם
                return SizedBox(width: 269, height: 30, child: CustomPaint(painter: RtLegendPainter(sc.reduce((a, b) => a < b ? a : b), sc.reduce((a, b) => a > b ? a : b), name, unit)));
              }),
            ]),
          ]),
        ),
      ),
    );
  }
}

/// שדה מספרי שמתעדכן מבחוץ (טעינת פרופיל) כשהוא לא בפוקוס, ומדווח כל שינוי תקין.
class _NumField extends StatefulWidget {
  const _NumField({required this.label, required this.value, required this.onChanged, required this.cs, this.tip});
  final String label; // תווית
  final double value; // הערך הנוכחי
  final void Function(double) onChanged; // דיווח
  final ColorScheme cs; // צבעים
  final String? tip; // הסבר

  @override
  State<_NumField> createState() => _NumFieldState();
}

class _NumFieldState extends State<_NumField> {
  late final TextEditingController _ctrl = TextEditingController(text: _fmt(widget.value)); // התוכן
  final _focus = FocusNode(); // פוקוס

  static String _fmt(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : '$v'; // בלי ".0" מיותר

  @override
  void didUpdateWidget(covariant _NumField old) {
    super.didUpdateWidget(old);
    if (!_focus.hasFocus && double.tryParse(_ctrl.text) != widget.value) _ctrl.text = _fmt(widget.value); // עדכון מבחוץ
  }

  @override
  void dispose() { _ctrl.dispose(); _focus.dispose(); super.dispose(); } // ניקוי

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 1.5),
        child: Row(children: [
          Expanded(child: Tooltip(message: widget.tip ?? '', child: Text(widget.label, style: TextStyle(fontSize: 10, color: widget.cs.onSurfaceVariant)))), // תווית
          SizedBox(width: 70, height: 28, child: TextField(
            controller: _ctrl, focusNode: _focus, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11),
            keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true), // מקלדת מספרים
            decoration: const InputDecoration(isDense: true, contentPadding: EdgeInsets.symmetric(horizontal: 4), border: OutlineInputBorder()),
            onChanged: (t) { final v = double.tryParse(t); if (v != null) widget.onChanged(v); }, // רק ערך תקין
          )),
        ]),
      );
}

/// בורר "פרופיל פעיל" (FR-D-286) — בראש פאנל בדיקת המעקב ובראש פאנל תצפית המכ"ם דופלר. שני המופעים קוראים
/// מאותו בקר (RadarTrackController), ולכן מסונכרנים. בחירה טוענת את הפרופיל לשדות של כל תהליכי המכ"ם; כיוון הפנים
/// לא משתנה (של האתר, לא של המכ"ם). שינוי שדה אחרי הטעינה מוצג כ"שונה ידנית".
class ActiveProfileBar extends StatefulWidget {
  const ActiveProfileBar({super.key, required this.cs});
  final ColorScheme cs; // ערכת הצבעים

  @override
  State<ActiveProfileBar> createState() => _ActiveProfileBarState();
}

class _ActiveProfileBarState extends State<ActiveProfileBar> {
  bool _showNotes = false; // אזור "מה פורסם ומה הונח" פתוח
  static const _green = Color(0xFF2ECC40); // צבע כלי המכ"ם — כמו בדסקטופ

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) { // אחרי הציור הראשון — לא בתוך build
      if (mounted) context.read<RadarTrackController>().loadLibrary(); // הספרייה (פעם אחת) + הפרופילים שלי
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.cs; // צבעים
    final c = context.watch<RadarTrackController>(); // הבקר
    context.watch<MapState>(); // גם שינוי שדה בכלי הדופלר מרענן את "שונה ידנית"
    const st = TextStyle(fontSize: 10); // גופן הרשימה
    final items = <DropdownMenuItem<String>>[
      const DropdownMenuItem(value: '', child: Text('— ידני (השדות כפי שהם) —', style: st)), // בלי פרופיל
      if (c.library.isNotEmpty) // כותרת קבוצה — Flutter בלי optgroup, לכן שורה לא-לחיצה
        DropdownMenuItem(value: '#lib', enabled: false, child: Text('ספרייה מובנית — נתונים פומביים', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: cs.onSurfaceVariant))),
      for (int i = 0; i < c.library.length; i++) // כל פרופיל בספרייה
        DropdownMenuItem(value: 'lib:$i', child: Text('📚 ${c.library[i]['name']}', style: st, overflow: TextOverflow.ellipsis)),
      if (c.myProfileNames.isNotEmpty) // כותרת קבוצה
        DropdownMenuItem(value: '#my', enabled: false, child: Text('הפרופילים שלי', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: cs.onSurfaceVariant))),
      for (final n in c.myProfileNames) DropdownMenuItem(value: 'my:$n', child: Text('👤 $n', style: st, overflow: TextOverflow.ellipsis)), // שלי
    ];
    final value = items.any((it) => it.value == c.activeKey) ? c.activeKey : ''; // ערך שלא ברשימה — "ידני" (מונע קריסת DropdownButton)
    final mod = c.activeModified; // שונה ידנית?
    final String statusText; // שורת המצב
    final Color statusColor; // צבעה — עם סימן, לא רק צבע
    if (c.activeName == null) { statusText = 'ידני: התהליכים ירוצו לפי השדות כפי שהוזנו.'; statusColor = cs.onSurfaceVariant; }
    else if (mod) { statusText = '✎ ${c.activeName} — שונה ידנית אחרי הטעינה'; statusColor = const Color(0xFF9A5B00); } // כתום-כהה
    else { statusText = '✔ ${c.activeName} — פעיל בכל תהליכי המכ"ם'; statusColor = const Color(0xFF15803D); } // ירוק-כהה
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 3),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(border: Border.all(color: _green), borderRadius: BorderRadius.circular(5), color: _green.withAlpha(22)), // מסגרת בולטת
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text('📡 פרופיל פעיל', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: cs.onSurface)), // תווית
          const SizedBox(width: 6),
          Expanded(child: Semantics(label: 'פרופיל מכ"ם פעיל לכל התהליכים', child: DropdownButton<String>( // הבורר
            value: value, isExpanded: true, isDense: true, items: items,
            onChanged: (v) { if (v != null && !v.startsWith('#')) c.setActive(v); }, // בחירה (כותרות לא נבחרות)
          ))),
        ]),
        Text(statusText, style: TextStyle(fontSize: 9, color: statusColor)), // מצב
        if (c.activeNotes != null) ...[
          InkWell( // פתיחה/סגירה של המקורות — שטח מגע מורחב
            onTap: () => setState(() => _showNotes = !_showNotes),
            child: Padding(padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text('${_showNotes ? '▾' : '◂'} מה פורסם ומה הונח', style: TextStyle(fontSize: 9, color: cs.primary))),
          ),
          if (_showNotes)
            ConstrainedBox(constraints: const BoxConstraints(maxHeight: 170), child: SingleChildScrollView( // גלילה פנימית
              child: Directionality(textDirection: TextDirection.ltr, // המקורות באנגלית — משמאל לימין
                  child: SelectableText(c.notesText(), style: TextStyle(fontSize: 8.5, color: cs.onSurfaceVariant))), // ניתן להעתקה (קישורים כטקסט)
            )),
        ],
      ]),
    );
  }
}
