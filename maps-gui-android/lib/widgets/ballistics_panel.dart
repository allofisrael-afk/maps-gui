import 'package:flutter/material.dart';
import '../services/mpm_bridge.dart';

/// כלי מסלול בליסטי (MPM) — Stage 3 (FR-D-237), Android. גרסה ראשונה, בכוונה מצומצמת-היקף
/// יחסית ל-Desktop/Web (ר' MAPS-GUI_SRS.md §3.27): הזנת תותח/מטרה ידנית (lat/lon/alt), לא
/// לחיצה-על-מפה (דורש אינטגרציה עם מנגנון ה-tap המשותף ב-map_screen.dart — נדחה, לא קריטי
/// לבדיקת ה-bridge/Chaquopy עצמו). טאבי טבלה/כיול/מטאו פשוטים-יותר מ-Desktop/Web. ווידג'ט
/// עצמאי (לא קשור ל-MapState/Provider המשותף) — נחסך הרחבה של ה-state העצום-כבר (map_state.dart).
class BallisticsPanel extends StatefulWidget {
  const BallisticsPanel({required this.cs});
  final ColorScheme cs;

  @override
  State<BallisticsPanel> createState() => _BallisticsPanelState();
}

class _BallisticsPanelState extends State<BallisticsPanel> with SingleTickerProviderStateMixin {
  bool _open = false; // מצב מצומצם (אייקון) / פתוח (פאנל מלא) — כמו _RadialLosPanel
  late final TabController _tabs = TabController(length: 5, vsync: this);

  // --- תותח/מטרה (הזנה ידנית — ר' הערת-היקף למעלה) ---
  final _gunLat = TextEditingController(text: '31.2520');
  final _gunLon = TextEditingController(text: '34.7915');
  final _gunAlt = TextEditingController(text: '280');
  final _tgtLat = TextEditingController(text: '31.3600');
  final _tgtLon = TextEditingController(text: '34.8900');
  final _tgtAlt = TextEditingController(text: '310');

  // --- מטאו/פגז/מקדמים (משותפים לכל הטאבים, כמו בלוח-הצד ב-Desktop) ---
  String _metSource = 'standard'; // ברירת-מחדל "standard" ולא "live" — נמנע מקריאת-רשת אוטומטית בכל פתיחה
  final _metTemp = TextEditingController();
  final _metPres = TextEditingController();
  final _metWspd = TextEditingController(text: '0');
  final _metWdir = TextEditingController(text: '0');
  final _mv = TextEditingController(text: '684');
  final _fD = TextEditingController(text: '1.0');
  final _fL = TextEditingController(text: '1.0');
  String _angleUnit = 'mils';
  bool _coriolis = true;
  bool _curvature = true;

  // --- טאב מסלול בודד ---
  final _trajAz = TextEditingController(text: '600');
  final _trajTalt = TextEditingController();
  double _qe = 450;
  bool _trajLoading = false;
  String _trajResult = '';

  // --- טאב פתרון ירי ---
  String _group = 'low';
  bool _loftLoading = false;
  String _solveResult = '';

  // --- טאב טבלת ירי ---
  final _tblStart = TextEditingController(text: '100');
  final _tblEnd = TextEditingController(text: '1200');
  final _tblStep = TextEditingController(text: '100');
  bool _tblLoading = false;
  String _tblResult = '';

  @override
  void dispose() {
    _tabs.dispose();
    for (final c in [_gunLat, _gunLon, _gunAlt, _tgtLat, _tgtLon, _tgtAlt, _metTemp, _metPres,
                      _metWspd, _metWdir, _mv, _fD, _fL, _trajAz, _trajTalt, _tblStart, _tblEnd, _tblStep]) {
      c.dispose();
    }
    super.dispose();
  }

  // בונה את params['gun']/['target'] ושדות-המטאו/המקדמים המשותפים לכל קריאה ל-MpmBridge
  Map<String, dynamic> _commonParams() => {
        'angle_unit': _angleUnit,
        'coriolis': _coriolis,
        'earth_curvature': _curvature,
        'mv': double.tryParse(_mv.text) ?? 684.0,
        'fitting': {'drag_factor': double.tryParse(_fD.text) ?? 1.0, 'lift_factor': double.tryParse(_fL.text) ?? 1.0},
        'met': _metSource == 'standard'
            ? {
                'source': 'standard',
                'surface_temp_c': double.tryParse(_metTemp.text),
                'surface_pressure_hpa': double.tryParse(_metPres.text),
                'wind_speed_mps': double.tryParse(_metWspd.text) ?? 0.0,
                'wind_dir_deg': double.tryParse(_metWdir.text) ?? 0.0,
              }
            : {'source': 'live'},
      };

  Map<String, dynamic> get _gun => {
        'lat': double.tryParse(_gunLat.text) ?? 0.0,
        'lon': double.tryParse(_gunLon.text) ?? 0.0,
        'alt_m': double.tryParse(_gunAlt.text) ?? 0.0,
      };

  Map<String, dynamic> get _target => {
        'lat': double.tryParse(_tgtLat.text) ?? 0.0,
        'lon': double.tryParse(_tgtLon.text) ?? 0.0,
        'alt_m': double.tryParse(_tgtAlt.text) ?? 0.0,
      };

  // מציג זווית בשתי היחידות, כמו _ballisticsFmtAngle ב-MAP.py (עקביות בין הפלטפורמות)
  String _fmtAngle(Map? a) => a == null ? '-' : '${(a['mils'] as num).toStringAsFixed(1)} מיל (${(a['deg'] as num).toStringAsFixed(3)}°)';

  // אותו תוכן/ניסוח בדיוק כמו _ballisticsImpactLines ב-MAP.py (ר' שלב 3, Desktop/Web)
  String _impactLines(Map imp) {
    final lines = <String>[
      'טווח אופקי: ${(imp['ground_range_m'] as num).toStringAsFixed(0)} מ\'',
      'סטייה צידית: ${(imp['drift_z_m'] as num).abs().toStringAsFixed(1)} מ\' ${(imp['drift_z_m'] as num) >= 0 ? "ימינה" : "שמאלה"} = ${_fmtAngle(imp['deviation'])}',
      'זמן מעוף: ${(imp['time_of_flight_s'] as num).toStringAsFixed(2)} ש\'',
      'קודקוד: ${(imp['apex_height_m'] as num).round()} מ\' מעל הלוע',
      'מהירות פגיעה: ${(imp['impact_velocity_mps'] as num).toStringAsFixed(1)} מ\'/ש\' (מאך ${(imp['impact_mach'] as num).toStringAsFixed(2)})',
      'זווית נפילה: ${_fmtAngle(imp['angle_of_fall'])}',
      'Sg בלוע: ${(imp['sg_muzzle'] as num).toStringAsFixed(2)}  |  Sg מינימלי: ${(imp['sg_min'] as num).toStringAsFixed(2)}',
    ];
    return lines.join('\n');
  }

  Future<void> _runTrajectory() async {
    setState(() { _trajLoading = true; _trajResult = 'מחשב...'; });
    try {
      final d = await MpmBridge.call('trajectory', {
        ..._commonParams(),
        'gun': _gun,
        'qe': _qe,
        'azimuth': double.tryParse(_trajAz.text) ?? 0.0,
        'target_alt': _trajTalt.text.isEmpty ? null : double.tryParse(_trajTalt.text),
        'include_path': false, // Android v1 — בלי הצגת-מסלול-על-מפה/פרופיל (ר' הערת-היקף למעלה)
      });
      setState(() {
        _trajLoading = false;
        _trajResult = d['ok'] == true
            ? 'הגבהה ${_fmtAngle(d['qe'])} | אזימוט ${_fmtAngle(d['fire_azimuth'])}\n${_impactLines(d['impact'])}'
            : (d['message'] ?? d['error'] ?? 'שגיאה').toString();
      });
    } catch (e) {
      setState(() { _trajLoading = false; _trajResult = 'שגיאה: $e'; });
    }
  }

  Future<void> _runSolve() async {
    setState(() { _loftLoading = true; _solveResult = 'מחשב...'; });
    try {
      final d = await MpmBridge.call('solve', {
        ..._commonParams(),
        'gun': _gun,
        'target': _target,
        'group': _group,
        'include_path': false,
      });
      setState(() {
        _loftLoading = false;
        if (d['ok'] != true) { _solveResult = (d['error'] ?? 'שגיאה').toString(); return; }
        _solveResult = 'הגבהה: ${_fmtAngle(d['qe'])}\nאזימוט ירי: ${_fmtAngle(d['fire_azimuth'])}\n'
            'טווח למטרה: ${(d['target_range_m'] as num).toStringAsFixed(0)} מ\' | שארית: ${d['residual_range_error_m']} מ\'\n'
            '${_impactLines(d['impact'])}';
      });
    } catch (e) {
      setState(() { _loftLoading = false; _solveResult = 'שגיאה: $e'; });
    }
  }

  Future<void> _runTable() async {
    setState(() { _tblLoading = true; _tblResult = 'מחשב...'; });
    try {
      final d = await MpmBridge.call('table', {
        ..._commonParams(),
        'gun': _gun,
        'azimuth': double.tryParse(_trajAz.text) ?? 0.0,
        'qe_start': double.tryParse(_tblStart.text) ?? 100.0,
        'qe_end': double.tryParse(_tblEnd.text) ?? 1200.0,
        'qe_step': double.tryParse(_tblStep.text) ?? 100.0,
      });
      setState(() {
        _tblLoading = false;
        if (d['ok'] != true) { _tblResult = (d['error'] ?? 'שגיאה').toString(); return; }
        // Android v1 — טבלה כטקסט שורות-שורות, לא רכיב DataTable (ר' הערת-היקף למעלה)
        final rows = (d['rows'] as List).cast<Map>();
        _tblResult = rows.map((r) => r.containsKey('error')
            ? '${r['qe_mils']} מיל: ${r['error']}'
            : '${r['qe_mils']} מיל → ${(r['range_m'] as num).toStringAsFixed(0)} מ\', סחיפה ${(r['drift_m'] as num).toStringAsFixed(1)} מ\'').join('\n');
      });
    } catch (e) {
      setState(() { _tblLoading = false; _tblResult = 'שגיאה: $e'; });
    }
  }

  // שדה-מספר פשוט — בלי מעקב-Undo (בניגוד ל-_field של RadialLos/RadarDoppler) כי הפאנל הזה
  // עצמאי ולא מחובר ל-MapState המשותף (ר' הערת-ההיקף בראש הקובץ)
  Widget _num(String label, TextEditingController ctrl, {double width = 70}) {
    final cs = widget.cs;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1.5),
      child: Row(children: [
        Expanded(child: Text(label, style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant))),
        SizedBox(
          width: width,
          height: 28,
          child: TextField(
            controller: ctrl,
            keyboardType: const TextInputType.numberWithOptions(signed: true, decimal: true),
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 11),
            decoration: const InputDecoration(isDense: true, contentPadding: EdgeInsets.symmetric(horizontal: 4), border: OutlineInputBorder()),
          ),
        ),
      ]),
    );
  }

  Widget _header(String text) {
    final cs = widget.cs;
    return Padding(
      padding: const EdgeInsets.only(top: 4, bottom: 2),
      child: Text(text, style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: cs.onSurfaceVariant)),
    );
  }

  Widget _resultBox(String text, bool loading) {
    final cs = widget.cs;
    if (loading) {
      return Row(children: [
        const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
        const SizedBox(width: 8),
        Text('מחשב...', style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant)),
      ]);
    }
    if (text.isEmpty) return const SizedBox.shrink();
    return Container(
      constraints: const BoxConstraints(maxHeight: 140),
      child: SingleChildScrollView(
        child: Text(text, style: TextStyle(fontSize: 10, color: cs.onSurface)),
      ),
    );
  }

  Widget _trajTab() {
    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _num('אזימוט ירי', _trajAz),
        _num('גובה פגיעה (ריק=גובה תותח)', _trajTalt),
        _header('הגבהה: ${_qe.toStringAsFixed(0)} מיל'),
        Slider(
          value: _qe, min: 5, max: 1350, divisions: 1345,
          onChanged: (v) => setState(() => _qe = v),
        ),
        Row(children: [
          Expanded(child: FilledButton.tonal(onPressed: _trajLoading ? null : _runTrajectory, child: const Text('חשב מסלול', style: TextStyle(fontSize: 11)))),
        ]),
        const SizedBox(height: 4),
        _resultBox(_trajResult, _trajLoading),
      ]),
    );
  }

  Widget _solveTab() {
    final cs = widget.cs;
    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('משתמש בשדות "מטרה" שהוזנו למעלה', style: TextStyle(fontSize: 9, color: cs.onSurfaceVariant)),
        Row(children: [
          Expanded(child: Text('קבוצת זוויות', style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant))),
          DropdownButton<String>(
            value: _group, isDense: true,
            items: const [DropdownMenuItem(value: 'low', child: Text('נמוכה', style: TextStyle(fontSize: 11))),
                         DropdownMenuItem(value: 'high', child: Text('גבוהה', style: TextStyle(fontSize: 11)))],
            onChanged: (v) => setState(() => _group = v ?? 'low'),
          ),
        ]),
        FilledButton.tonal(onPressed: _loftLoading ? null : _runSolve, child: const Text('חשב פתרון ירי', style: TextStyle(fontSize: 11))),
        const SizedBox(height: 4),
        _resultBox(_solveResult, _loftLoading),
      ]),
    );
  }

  Widget _tableTab() {
    return SingleChildScrollView(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _num('הגבהה מ-', _tblStart),
        _num('עד', _tblEnd),
        _num('צעד', _tblStep),
        FilledButton.tonal(onPressed: _tblLoading ? null : _runTable, child: const Text('חשב טבלה', style: TextStyle(fontSize: 11))),
        const SizedBox(height: 4),
        _resultBox(_tblResult, _tblLoading),
      ]),
    );
  }

  Widget _calTab() {
    final cs = widget.cs;
    // כיול לא מומש עדיין ב-Android v1 (ר' הערת-ההיקף בראש הקובץ) — Desktop/Web כן תומכים בו
    return Center(child: Padding(
      padding: const EdgeInsets.all(16),
      child: Text('כיול עדיין לא זמין ב-Android — זמין ב-Desktop/Web', style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant), textAlign: TextAlign.center),
    ));
  }

  Widget _metTab() {
    final cs = widget.cs;
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Text(
        _metSource == 'standard'
            ? 'מקור: אטמוספרה סטנדרטית (ללא קריאת-רשת)'
            : 'מקור: תחזית חיה — מוצג סטטוס אחרי חישוב ראשון',
        style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = widget.cs;
    if (!_open) {
      // מצב מצומצם — אייקון בלבד, אותו דפוס בדיוק כמו _RadialLosPanel/_RadarDopplerPanel
      return Material(
        color: cs.surface.withAlpha(230),
        shape: const CircleBorder(),
        elevation: 3,
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: () => setState(() => _open = true),
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Icon(Icons.rocket_launch, size: 20, color: cs.onSurface),
          ),
        ),
      );
    }
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Material(
        color: cs.surface.withAlpha(240),
        borderRadius: BorderRadius.circular(10),
        elevation: 4,
        child: Container(
          width: 270,
          padding: const EdgeInsets.all(8),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Row(children: [
                Icon(Icons.rocket_launch, size: 15, color: cs.primary),
                const SizedBox(width: 4),
                Text('מסלול בליסטי (MPM)', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: cs.onSurface)),
              ]),
              InkWell(onTap: () => setState(() => _open = false), child: Icon(Icons.close, size: 15, color: cs.onSurfaceVariant)),
            ]),
            Text('⚠ פגז generic_155 — להדגמה בלבד', style: TextStyle(fontSize: 8.5, color: cs.error)),
            _header('תותח'),
            _num('קו רוחב', _gunLat, width: 80),
            _num('קו אורך', _gunLon, width: 80),
            _num('גובה [מ\']', _gunAlt, width: 80),
            _header('מטרה'),
            _num('קו רוחב', _tgtLat, width: 80),
            _num('קו אורך', _tgtLon, width: 80),
            _num('גובה [מ\']', _tgtAlt, width: 80),
            _header('מטאו'),
            Row(children: [
              Expanded(child: DropdownButton<String>(
                value: _metSource, isDense: true, isExpanded: true,
                items: const [DropdownMenuItem(value: 'standard', child: Text('אטמוספרה סטנדרטית', style: TextStyle(fontSize: 10))),
                             DropdownMenuItem(value: 'live', child: Text('תחזית חיה', style: TextStyle(fontSize: 10)))],
                onChanged: (v) => setState(() => _metSource = v ?? 'standard'),
              )),
            ]),
            if (_metSource == 'standard') ...[
              _num('טמפ\' קרקע [°C] (ריק=סטנדרט)', _metTemp, width: 60),
              _num('לחץ קרקע [hPa] (ריק=סטנדרט)', _metPres, width: 60),
              _num('רוח [מ\'/ש\']', _metWspd, width: 60),
              _num('כיוון רוח [°]', _metWdir, width: 60),
            ],
            _header('פגז ומקדמים'),
            _num('מהירות לוע [מ\'/ש\']', _mv, width: 60),
            _num('מקדם גרר fD', _fD, width: 60),
            _num('מקדם עילוי fL', _fL, width: 60),
            const SizedBox(height: 4),
            TabBar(
              controller: _tabs, isScrollable: true, labelColor: cs.primary, unselectedLabelColor: cs.onSurfaceVariant,
              labelStyle: const TextStyle(fontSize: 10), indicatorColor: cs.primary,
              tabs: const [Tab(text: 'מסלול בודד'), Tab(text: 'פתרון ירי'), Tab(text: 'טבלת ירי'), Tab(text: 'כיול'), Tab(text: 'מטאו')],
            ),
            SizedBox(
              height: 230,
              child: TabBarView(controller: _tabs, children: [_trajTab(), _solveTab(), _tableTab(), _calTab(), _metTab()]),
            ),
          ]),
        ),
      ),
    );
  }
}
