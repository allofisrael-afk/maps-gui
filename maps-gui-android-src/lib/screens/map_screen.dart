import 'dart:math';
import 'dart:ui' as ui; // נדרש עבור ui.Path בציירן הגרף (Path של flutter_map מסתיר את Canvas Path)
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import '../models/grid_point.dart';
import '../models/los_session.dart'; // מודל סשן קו ראייה לפרופיל ולמפה
import '../models/uas_notam_zone.dart'; // מודל אזור NOTAM לרחפנים
import '../models/uas_coordination_zone.dart'; // מודל אזור תיאום כטב"ם
import '../data/uas_coordination_zones.dart'; // נתוני אזורי התיאום הסטטיים
import '../state/map_state.dart';
import '../widgets/controls_panel.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});
  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final _mapController = MapController();
  final _mapKey = GlobalKey();
  bool _selectMode = false;
  bool _isDragging = false;
  int? _draggingHandleIdx;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _mapController.mapEventStream.listen((_) {
        if (mounted) setState(() {});
      });
    });
  }

  LatLng? _screenToLatLng(Offset local) {
    try {
      return _mapController.camera.pointToLatLng(Point(local.dx, local.dy));
    } catch (_) { return null; }
  }

  LatLng? _globalToLatLng(Offset globalPos) {
    final rb = _mapKey.currentContext?.findRenderObject() as RenderBox?;
    if (rb == null) return null;
    return _screenToLatLng(rb.globalToLocal(globalPos));
  }

  Future<bool> _confirmNewSelection(MapState state) async {
    if (state.elevPoints.isEmpty && state.tempPoints.isEmpty) return true;
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('בחירה חדשה', textDirection: TextDirection.rtl),
        content: const Text('נתונים טעונים לאזור הנוכחי.\nלאפס ולבחור אזור חדש?', textDirection: TextDirection.rtl),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('ביטול')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('אפס')),
        ],
      ),
    );
    return result ?? false;
  }

  void _dragHandle(int handleIdx, Offset globalPos, MapState state) {
    final pt = _globalToLatLng(globalPos);
    if (pt == null) return;
    final bounds = state.selectionBounds;
    if (bounds == null) return;
    double n = bounds.north, s = bounds.south, e = bounds.east, w = bounds.west;
    switch (handleIdx) {
      case 0: s = pt.latitude;  w = pt.longitude; // SW
      case 1: s = pt.latitude;  e = pt.longitude; // SE
      case 2: n = pt.latitude;  e = pt.longitude; // NE
      case 3: n = pt.latitude;  w = pt.longitude; // NW
    }
    state.startSelection(LatLng(s, w));
    state.updateSelection(LatLng(n, e));
  }

  Widget _buildHandlesOverlay(MapState state, ColorScheme cs) {
    final bounds = state.selectionBounds;
    if (bounds == null) return const SizedBox.shrink();
    final corners = [
      LatLng(bounds.south, bounds.west), // SW — 0
      LatLng(bounds.south, bounds.east), // SE — 1
      LatLng(bounds.north, bounds.east), // NE — 2
      LatLng(bounds.north, bounds.west), // NW — 3
    ];
    return Positioned.fill(
      child: Stack(
        children: List.generate(4, (i) {
          final pt = _mapController.camera.latLngToScreenPoint(corners[i]);
          return Positioned(
            left: pt.x.toDouble() - 10,
            top:  pt.y.toDouble() - 10,
            width: 20, height: 20,
            child: GestureDetector(
              onPanStart:  (_)  => setState(() => _draggingHandleIdx = i),
              onPanUpdate: (d)  { if (_draggingHandleIdx == i) _dragHandle(i, d.globalPosition, state); },
              onPanEnd:    (_)  => setState(() => _draggingHandleIdx = null),
              onPanCancel: ()   => setState(() => _draggingHandleIdx = null),
              child: Container(
                decoration: BoxDecoration(
                  color: cs.primary,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: Colors.white, width: 2),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<MapState>();
    final cs = Theme.of(context).colorScheme;

    if (state.lastPinnedPoint != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _mapController.move(state.lastPinnedPoint!, 12);
        state.consumeLastPinned();
      });
    }

    if (state.flightFocusPoint != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final fd = state.flightData;
        if (fd != null && fd.path.length >= 2) {
          // יש מסלול — fit bounds לכיסוי מלא
          _mapController.fitCamera(CameraFit.bounds(
            bounds: LatLngBounds.fromPoints(fd.path),
            padding: const EdgeInsets.all(40),
          ));
        } else {
          // נקודה בודדת — zoom 8 על המיקום הנוכחי
          _mapController.move(state.flightFocusPoint!, 8);
        }
        state.consumeFlightFocus();
      });
    }

    if (state.cityFocusPoint != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _mapController.move(state.cityFocusPoint!, 12);
        state.consumeCityFocus();
      });
    }

    return Scaffold(
      resizeToAvoidBottomInset: true,
      bottomNavigationBar: BottomAppBar(
        padding: EdgeInsets.zero,
        height: 60,
        child: Directionality(
          textDirection: TextDirection.rtl,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavBtn(icon: Icons.layers_outlined, label: 'שכבות', onTap: () => _openSheet(context, const LayersPanel(), scrollControlled: true)),
              _NavBtn(icon: Icons.my_location_outlined, label: 'מיקום', onTap: () => _openSheet(context, const LocationPanel(), scrollControlled: true)),
              _NavBtn(icon: Icons.flight_outlined, label: 'טיסות', onTap: () => _openSheet(context, const FlightPanel(), scrollControlled: true)),
            ],
          ),
        ),
      ),
      body: Stack(
        children: [
          // ── מפה מסך מלא ──
          FlutterMap(
            key: _mapKey,
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(31.5, 34.9),
              initialZoom: 7,
              onTap: _selectMode ? null : (_, point) => _onMapTap(state, point),
              interactionOptions: InteractionOptions(
                flags: (_selectMode || _draggingHandleIdx != null)
                    ? InteractiveFlag.none
                    : InteractiveFlag.all,
              ),
            ),
            children: [
              TileLayer(
                urlTemplate: state.tileUrl,
                subdomains: const ['a', 'b', 'c'],
                userAgentPackageName: 'com.mapsapp.maps_gui_android',
              ),
              if (state.selectionStart != null && state.selectionEnd != null)
                PolygonLayer(polygons: [
                  Polygon(
                    points: _rectPoints(state.selectionStart!, state.selectionEnd!),
                    color: cs.primary.withAlpha(40),
                    borderColor: cs.primary,
                    borderStrokeWidth: 2,
                  ),
                ]),
              if (state.activeLayer == LayerType.elevation) _buildElevLayer(state),
              if (state.activeLayer == LayerType.temperature) _buildTempLayer(state),
              if (state.manualHeatImageBytes != null && state.manualHeatBounds != null)
                OverlayImageLayer(overlayImages: [
                  OverlayImage(
                    bounds: state.manualHeatBounds!,
                    opacity: 0.8,
                    imageProvider: MemoryImage(state.manualHeatImageBytes!),
                  ),
                ]),
              if (state.cityBounds != null)
                PolygonLayer(polygons: [
                  Polygon(
                    points: [
                      LatLng(state.cityBounds!.south, state.cityBounds!.west),
                      LatLng(state.cityBounds!.south, state.cityBounds!.east),
                      LatLng(state.cityBounds!.north, state.cityBounds!.east),
                      LatLng(state.cityBounds!.north, state.cityBounds!.west),
                    ],
                    color: Colors.transparent,
                    borderColor: cs.tertiary,
                    borderStrokeWidth: 2.5,
                  ),
                ]),
              // ── שכבת "אזורי פעילות רחפנים (NOTAM)" — צורות + סמני פרטים לחיצים ──
              if (state.uasNotamActive) ..._buildUasNotamLayers(state),
              // ── שכבת "אזורי תיאום כטב"ם" — נתונים סטטיים, לא תלויים ב-state ──
              if (state.uasCoordActive) ..._buildUasCoordZonesLayers(),
              if (state.flightData != null) ...[
                if (state.flightData!.path.length >= 2)
                  PolylineLayer(polylines: [
                    Polyline(
                      points: state.flightData!.path,
                      color: const Color(0xFF89b4fa),
                      strokeWidth: 3,
                    ),
                  ]),
                if (state.flightData!.current != null)
                  MarkerLayer(markers: [
                    Marker(
                      point: state.flightData!.current!,
                      width: 32, height: 32,
                      child: const Icon(Icons.flight, color: Color(0xFFa6e3a1), size: 28),
                    ),
                  ]),
              ],
              if (state.pinnedPoints.isNotEmpty)
                MarkerLayer(
                  markers: state.pinnedPoints.map((p) => Marker(
                    point: p,
                    width: 30, height: 30,
                    child: const Icon(Icons.place, color: Color(0xFFf38ba8), size: 28),
                  )).toList(),
                ),
              if (state.rulerPoints.length >= 2)
                PolylineLayer(polylines: [
                  Polyline(
                    points: state.rulerPoints,
                    color: const Color(0xFFa6e3a1),
                    strokeWidth: 2.5,
                    pattern: StrokePattern.dashed(segments: const [10, 6]),
                  ),
                ]),
              if (state.rulerPoints.isNotEmpty)
                MarkerLayer(markers: state.rulerPoints.map((p) => Marker(
                  point: p, width: 14, height: 14,
                  child: Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFFa6e3a1),
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                  ),
                )).toList()),
              // ── שכבות קו ראייה: קטעי פוליגון ירוק/אדום וסמני תצפית/יעד ──
              ..._buildLosLayers(state), // כל הסשנים הפעילים
              // ── סמן תצפית זמני: מוצג לאחר לחיצה ראשונה בטרם בחירת יעד ──
              if (state.losCurObs != null)
                CircleLayer(circles: [
                  CircleMarker(
                    point: state.losCurObs!,   // מיקום נקודת התצפית הממתינה
                    radius: 9,
                    color: const Color(0xFF4488FF).withAlpha(200), // כחול מלוא-שקוף
                    borderColor: Colors.white,
                    borderStrokeWidth: 2,
                  ),
                ]),
              RichAttributionWidget(attributions: [TextSourceAttribution(state.tileAttribution)]),
            ],
          ),

          // ── AppBar צף ──
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 12,
            right: 12,
            child: Material(
              color: cs.surface.withAlpha(230),
              borderRadius: BorderRadius.circular(14),
              elevation: 3,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: Row(
                  children: [
                    // כפתור בחירת אזור
                    IconButton(
                      tooltip: _selectMode ? 'בטל בחירה' : 'בחר אזור על המפה',
                      icon: Icon(
                        _selectMode ? Icons.cancel_outlined : Icons.crop_free,
                        color: _selectMode ? cs.error : cs.onSurface,
                      ),
                      onPressed: () async {
                        if (!_selectMode) {
                          // שמור הפניה ל-ScaffoldMessenger לפני ה-await כדי לא להשתמש ב-context אחריו
                          final messenger = ScaffoldMessenger.of(context);
                          final ok = await _confirmNewSelection(state);
                          if (!ok || !mounted) return; // המשתמש ביטל, או Widget הוסר
                          state.resetForNewSelection();
                          // הצג הסבר קצר בכניסה למצב בחירה — SnackBar נעלם אוטומטית
                          messenger.showSnackBar(
                            const SnackBar(
                              content: Text('גרור או הקש שתי נקודות לבחירת אזור, ואז טען שכבה מהתפריט'),
                              duration: Duration(seconds: 4),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                        setState(() { _selectMode = !_selectMode; _isDragging = false; });
                      },
                    ),
                    Expanded(
                      child: Text(
                        _selectMode
                            ? (state.selectionStart == null
                                ? 'הקש או גרור לבחירה'
                                : state.selectionEnd == null
                                    ? 'הקש נקודה שנייה'
                                    : 'אזור נבחר ✓')
                            : 'מפה אינטראקטיבית',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                          color: _selectMode ? cs.primary : cs.onSurface,
                        ),
                      ),
                    ),
                    // כפתור מדידת מרחק
                    IconButton(
                      tooltip: state.rulerMode ? 'סיים מדידה' : 'מדד מרחק',
                      icon: Icon(
                        Icons.straighten,
                        color: state.rulerMode ? cs.primary : cs.onSurface,
                      ),
                      onPressed: state.toggleRuler, // הפעל/כבה כלי מדידה
                    ),
                    // כפתור קו ראייה (LOS) — עין פעילה/לא פעילה
                    IconButton(
                      tooltip: state.losMode ? 'בטל קו ראייה' : 'קו ראייה',
                      icon: Icon(
                        state.losMode ? Icons.visibility : Icons.visibility_outlined, // עין מלאה=פעיל
                        color: state.losMode ? cs.primary : cs.onSurface,
                      ),
                      onPressed: state.toggleLosMode, // הפעל/כבה מצב LOS
                    ),
                    // כפתור בחירת נקודות חום ידנית — מקביל ל"בחר נקודות" בדסקטופ
                    IconButton(
                      tooltip: state.manualHeatMode ? 'סיים חום ידני' : 'חום ידני',
                      icon: Icon(
                        state.manualHeatMode ? Icons.local_fire_department : Icons.local_fire_department_outlined,
                        color: state.manualHeatMode ? cs.primary : cs.onSurface,
                      ),
                      onPressed: () {
                        final entering = !state.manualHeatMode;
                        state.toggleManualHeatMode();
                        if (entering) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('הקש על המפה להוספת נקודות חום'),
                              duration: Duration(seconds: 4),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
                    ),
                  ],
                ),
              ),
            ),
          ),

          // ── מחוון טעינה (גבהים, טמפ', LOS, חיפוש עיר או NOTAM רחפנים) ──
          if (state.elevLoading || state.tempLoading || state.losLoading || state.citySearchLoading || state.uasNotamLoading)
            const Positioned(
              top: 100,
              left: 0,
              right: 0,
              child: Center(child: _LoadingChip()),
            ),

          // ── שכבת גרירה לבחירת אזור ──
          if (_selectMode)
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTapUp: (d) {
                  final pt = _screenToLatLng(d.localPosition);
                  if (pt == null) return;
                  if (state.selectionStart == null || state.selectionEnd != null) {
                    state.startSelection(pt);
                  } else {
                    state.updateSelection(pt);
                    setState(() => _selectMode = false);
                  }
                },
                onPanStart: (d) {
                  final pt = _screenToLatLng(d.localPosition);
                  if (pt == null) return;
                  state.startSelection(pt);
                  setState(() => _isDragging = true);
                },
                onPanUpdate: (d) {
                  if (!_isDragging) return;
                  final pt = _screenToLatLng(d.localPosition);
                  if (pt != null) state.updateSelection(pt);
                },
                onPanEnd: (_) {
                  if (!_isDragging) return;
                  setState(() { _isDragging = false; _selectMode = false; });
                },
                onPanCancel: () => setState(() { _isDragging = false; }),
                onLongPressStart: (d) {
                  final pt = _screenToLatLng(d.localPosition);
                  if (pt == null) return;
                  state.startSelection(pt);
                  setState(() => _isDragging = true);
                },
                onLongPressMoveUpdate: (d) {
                  if (!_isDragging) return;
                  final pt = _screenToLatLng(d.localPosition);
                  if (pt != null) state.updateSelection(pt);
                },
                onLongPressEnd: (_) {
                  if (!_isDragging) return;
                  setState(() { _isDragging = false; _selectMode = false; });
                },
                onLongPressCancel: () => setState(() { _isDragging = false; }),
              ),
            ),

          // ── הנחיה בחירת אזור ──
          if (_selectMode)
            Positioned(
              bottom: 30,
              left: 20,
              right: 20,
              child: IgnorePointer(
                child: Material(
                  color: cs.inverseSurface.withAlpha(220),
                  borderRadius: BorderRadius.circular(20),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: Text(
                      state.selectionStart == null
                          ? 'גרור / לחץ-ארוך / הקש פעמיים לבחירה'
                          : state.selectionEnd == null
                              ? 'הקש שוב — נקודת סיום'
                              : 'אזור נבחר ✓  גרור פינה לעריכה',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: cs.onInverseSurface, fontSize: 13),
                    ),
                  ),
                ),
              ),
            ),

          // ── ידיות עריכת בחירה ──
          if (!_selectMode && state.selectionStart != null && state.selectionEnd != null)
            _buildHandlesOverlay(state, cs),

          // ── כרטיס גובה (נקודה נלחצה בשכבת גבהים) ──
          if (state.tappedElevPoint != null)
            _ElevationCard(state: state, cs: cs),

          // ── כרטיס מזג אוויר ──
          if (state.weatherPoint != null)
            _WeatherCard(state: state, cs: cs),

          // ── כרטיס מדידה ──
          if (state.rulerPoints.length >= 2)
            _RulerCard(state: state, cs: cs),

          // ── פאנל פרופיל קו ראייה (תחתית) ──
          if (state.losSessions.any((s) => s.points.isNotEmpty)) // הצג רק אם יש סשן מחושב
            _LosProfilePanel(state: state, cs: cs),

          // ── הנחיה: הוראות לחיצה במצב LOS ──
          if (state.losMode && !_selectMode)
            Positioned(
              bottom: state.losSessions.any((s) => s.points.isNotEmpty) ? 195 : 30, // מעל הפאנל אם פתוח
              left: 20,
              right: 20,
              child: IgnorePointer(
                child: Material(
                  color: cs.inverseSurface.withAlpha(220),
                  borderRadius: BorderRadius.circular(20),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    child: Text(
                      state.losCurObs == null
                          ? 'הקש על נקודת התצפית' // הוראה ללחיצה ראשונה
                          : 'הקש על נקודת היעד',  // הוראה ללחיצה שנייה
                      textAlign: TextAlign.center,
                      style: TextStyle(color: cs.onInverseSurface, fontSize: 13),
                    ),
                  ),
                ),
              ),
            ),

          // ── שגיאת LOS ──
          // הטקסט עטוף ב-IgnorePointer כדי שמגעי המשתמש יעברו למפה מתחתיו
          // רק כפתור ה-X מקבל מגעים — כך לא נחסמות ידיות הגרירה של בחירת אזור
          if (state.losError != null)
            Positioned(
              top: 110,
              left: 20,
              right: 20,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // חלק הטקסט — IgnorePointer: מגעים עוברים למפה
                  Expanded(
                    child: IgnorePointer(
                      child: Material(
                        color: cs.errorContainer,
                        borderRadius: const BorderRadius.only(
                          topLeft:     Radius.circular(12),
                          bottomLeft:  Radius.circular(12),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                          child: Row(children: [
                            Icon(Icons.error_outline, size: 14, color: cs.onErrorContainer),
                            const SizedBox(width: 6),
                            Expanded(child: Text(state.losError!,
                                style: TextStyle(fontSize: 11, color: cs.onErrorContainer),
                                maxLines: 2, overflow: TextOverflow.ellipsis)),
                          ]),
                        ),
                      ),
                    ),
                  ),
                  // כפתור X — מקבל מגעים; סוגר רק את השגיאה ללא מחיקת סשנים
                  GestureDetector(
                    onTap: state.clearLosError, // מנקה losError בלבד
                    child: Material(
                      color: cs.errorContainer,
                      borderRadius: const BorderRadius.only(
                        topRight:    Radius.circular(12),
                        bottomRight: Radius.circular(12),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Icon(Icons.close, size: 14, color: cs.onErrorContainer),
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // ── מקראות שכבות רחפנים + הודעת כלל VLOS — עמודה אחת כדי שלא יתנגשו זו בזו ──
          Positioned(
            bottom: 14,
            left: 12,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (state.uasCoordActive) ...[
                  const _UasCoordLegend(),
                  const SizedBox(height: 6),
                ],
                if (state.uasNotamActive) ...[
                  const _UasNotamLegend(),
                  const SizedBox(height: 6),
                ],
                const _VlosInfoButton(),
              ],
            ),
          ),

          // ── סרגל קנה-מידה ──
          Positioned(
            bottom: 14,
            right: 12,
            child: _ScaleBar(mapController: _mapController),
          ),
        ],
      ),
    );
  }

  // בונה את שכבות המפה עבור כל סשני LOS: קטעי קו (ירוק/אדום) וסמני נקודות
  List<Widget> _buildLosLayers(MapState state) {
    final layers = <Widget>[];
    for (final session in state.losSessions) {
      if (session.points.length < 2) continue; // נדרשות לפחות שתי נקודות לציור קו
      // ── בניית קטעי polyline לפי נראות ──
      final visSegs = <List<LatLng>>[]; // קטעים גלויים לציור בירוק
      final blkSegs = <List<LatLng>>[]; // קטעים חסומים לציור באדום
      var cur = [LatLng(session.points.first.lat, session.points.first.lon)]; // קטע נוכחי
      var curVis = session.points.first.visible;
      for (int i = 1; i < session.points.length; i++) {
        final p  = session.points[i];
        final pt = LatLng(p.lat, p.lon);
        if (p.visible == curVis) {
          cur.add(pt); // אותו סטטוס — המשך קטע
        } else {
          cur.add(pt); // סיים קטע קיים עם נקודת מעבר
          if (curVis) { visSegs.add(cur); } else { blkSegs.add(cur); } // מיין לרשימה המתאימה
          cur    = [pt]; // התחל קטע חדש
          curVis = p.visible;
        }
      }
      if (cur.length >= 2) { // הוסף קטע אחרון אם ארוך מספיק
        if (curVis) { visSegs.add(cur); } else { blkSegs.add(cur); }
      }
      // ── ציור קטעים גלויים (ירוק) ──
      if (visSegs.isNotEmpty) {
        layers.add(PolylineLayer(polylines: visSegs.map((s) => Polyline(
          points: s, color: const Color(0xFF44CC44), strokeWidth: 3, // ירוק לנראות
        )).toList()));
      }
      // ── ציור קטעים חסומים (אדום) ──
      if (blkSegs.isNotEmpty) {
        layers.add(PolylineLayer(polylines: blkSegs.map((s) => Polyline(
          points: s, color: const Color(0xFFFF4444), strokeWidth: 3, // אדום לחסימה
        )).toList()));
      }
      // ── סמני תצפית (מלא) ויעד (חלול) בצבע הסשן ──
      layers.add(CircleLayer(circles: [
        CircleMarker(
          point: session.obs, radius: 9,
          color: session.color.withAlpha(220),  // סמן תצפית מלא בצבע הסשן
          borderColor: Colors.white, borderStrokeWidth: 2,
        ),
        CircleMarker(
          point: session.tgt, radius: 9,
          color: session.color.withAlpha(100),  // סמן יעד שקוף יותר
          borderColor: session.color, borderStrokeWidth: 2,
        ),
      ]));
    }
    return layers; // רשימת שכבות לכל הסשנים
  }

  // בונה את שכבות המפה לאזורי NOTAM לרחפנים: צורות (מעגל/פוליגון) כתומות + סמן לחיץ בכל אזור לפתיחת פרטים
  List<Widget> _buildUasNotamLayers(MapState state) {
    const color = Color(0xFFFAB387); // כתום — מסמן "הימנעות/מודעות", לא ירוק "מותר"
    final circles = state.uasNotamZones
        .where((z) => z.geometryType == UasNotamGeometryType.circle && z.center != null && z.radiusM != null)
        .map((z) => CircleMarker(
              point: z.center!,
              radius: z.radiusM!,
              useRadiusInMeter: true, // רדיוס אמיתי במטרים, לא פיקסלים — קנה מידה נכון בכל זום
              color: color.withAlpha(55),
              borderColor: color,
              borderStrokeWidth: 2,
            ))
        .toList();
    final polygons = state.uasNotamZones
        .where((z) => z.geometryType == UasNotamGeometryType.polygon && z.points.length >= 3)
        .map((z) => Polygon(
              points: z.points,
              color: color.withAlpha(55),
              borderColor: color,
              borderStrokeWidth: 2,
            ))
        .toList();
    // סמן קטן בכל אזור — הדרך הפשוטה והאמינה ביותר ב-flutter_map לתמוך בלחיצה לפרטים
    // (בניגוד ל-Polygon/CircleMarker שדורשים hit-testing ידני מורכב יותר)
    final markers = state.uasNotamZones
        .map((z) => Marker(
              point: z.anchor,
              width: 30, height: 30,
              child: GestureDetector(
                onTap: () => _showUasNotamDetails(z),
                child: Container(
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: const Icon(Icons.warning_amber_rounded, size: 16, color: Colors.black87),
                ),
              ),
            ))
        .toList();
    return [
      if (circles.isNotEmpty) CircleLayer(circles: circles),
      if (polygons.isNotEmpty) PolygonLayer(polygons: polygons),
      if (markers.isNotEmpty) MarkerLayer(markers: markers),
    ];
  }

  // בניית שכבות "אזורי תיאום כטב"ם" — נתונים סטטיים (kUasCoordinationZones), לא תלוי ב-state
  List<Widget> _buildUasCoordZonesLayers() {
    const color = Color(0xFF6366F1); // אינדיגו — מובחן מכתום ה-NOTAM, מסמן "דורש תיאום" ולא "הימנעות"
    final circles = kUasCoordinationZones
        .where((z) => z.geometryType == UasNotamGeometryType.circle && z.center != null && z.radiusM != null)
        .map((z) => CircleMarker(
              point: z.center!,
              radius: z.radiusM!,
              useRadiusInMeter: true,
              color: color.withAlpha(55),
              borderColor: color,
              borderStrokeWidth: 2,
            ))
        .toList();
    final polygons = kUasCoordinationZones
        .where((z) => z.geometryType == UasNotamGeometryType.polygon && z.points.length >= 3)
        .map((z) => Polygon(
              points: z.points,
              color: color.withAlpha(55),
              borderColor: color,
              borderStrokeWidth: 2,
            ))
        .toList();
    final markers = kUasCoordinationZones
        .map((z) => Marker(
              point: z.anchor,
              width: 30, height: 30,
              child: GestureDetector(
                onTap: () => _showUasCoordDetails(z),
                child: Container(
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: const Icon(Icons.shield_outlined, size: 16, color: Colors.white),
                ),
              ),
            ))
        .toList();
    return [
      if (circles.isNotEmpty) CircleLayer(circles: circles),
      if (polygons.isNotEmpty) PolygonLayer(polygons: polygons),
      if (markers.isNotEmpty) MarkerLayer(markers: markers),
    ];
  }

  // כרטיס פרטים לאזור תיאום בודד — נפתח בלחיצה על הסמן האינדיגו
  void _showUasCoordDetails(UasCoordinationZone z) {
    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return Directionality(
          textDirection: TextDirection.rtl,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    width: 40, height: 4,
                    decoration: BoxDecoration(color: cs.outlineVariant, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                Row(children: [
                  const Icon(Icons.shield_outlined, color: Color(0xFF6366F1)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(z.name,
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: cs.onSurface)),
                  ),
                ]),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withAlpha(35),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'תחילת פעילות בכל אזור דורשת אישור יחידת הנת"א. אין להיכנס לפעילות ללא תיאום מראש.',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
                const SizedBox(height: 10),
                Text('גובה מרבי', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: cs.primary)),
                Text(z.altitudeLabel, style: TextStyle(fontSize: 13, color: cs.onSurface)),
                if (z.notes.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text('הערות', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: cs.primary)),
                  Text(z.notes, style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  // כרטיס פרטים לאזור NOTAM בודד — נפתח בלחיצה על הסמן הכתום
  void _showUasNotamDetails(UasNotamZone z) {
    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return Directionality(
          textDirection: TextDirection.rtl,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ידית גרירה — inline כי _sheetHandle ב-controls_panel.dart פרטית לקובץ שלה (privacy לפי קובץ ב-Dart)
                Center(
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    width: 40, height: 4,
                    decoration: BoxDecoration(color: cs.outlineVariant, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                Row(children: [
                  const Icon(Icons.warning_amber_rounded, color: Color(0xFFFAB387)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('${z.id}  (${z.icao})',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: cs.onSurface)),
                  ),
                ]),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFAB387).withAlpha(35),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'אזור פעילות רחפנים מאושרת של גורם אחר — להימנעות, לא לטיסה חופשית',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
                if (z.altitudeText.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text('גובה', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: cs.primary)),
                  Text(z.altitudeText, style: TextStyle(fontSize: 13, color: cs.onSurface)),
                ],
                if (z.hebrewGloss.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1).withAlpha(30),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('תרגום גס לעברית (לנוחות בלבד)',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: cs.primary)),
                        const SizedBox(height: 4),
                        Text(z.hebrewGloss, style: TextStyle(fontSize: 13, color: cs.onSurface)),
                        const SizedBox(height: 4),
                        Text(
                          'הטקסט האנגלי המקורי הוא הקובע — התרגום הוא כלי עזר בלבד ועלול להכיל טעויות או השמטות.',
                          style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 10),
                Text('פרטי ה-NOTAM', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: cs.primary)),
                Text(z.text, style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
        );
      },
    );
  }

  void _openSheet(BuildContext context, Widget content, {bool scrollControlled = false}) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: scrollControlled,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => content,
    );
  }

  void _onMapTap(MapState state, LatLng point) {
    // מצב בחירת נקודות חום ידנית גובר על הכל — לחיצה מוסיפה נקודה בלבד (מקביל ל-heatmapPickerActive בדסקטופ)
    if (state.manualHeatMode) {
      state.addManualHeatPoint(point);
      return;
    }
    // מצב LOS גובר על כל שאר הפעולות — לחיצה מוסיפה תצפית או מריצה חישוב
    if (state.losMode) {
      if (state.losLoading) return;  // מנע פעולה בזמן חישוב — הגנה מפני מצב מקביל
      if (state.losCurObs == null) {
        state.setLosObserver(point); // לחיצה ראשונה: שמור נקודת תצפית
      } else {
        state.runLos(point);         // לחיצה שנייה: חשב קו ראייה ליעד
      }
      return;
    }
    if (state.rulerMode) {
      state.addRulerPoint(point); // הוסף נקודה למדידת מרחק
      return;
    }
    if (state.activeLayer == LayerType.elevation && state.elevPoints.isNotEmpty) {
      state.tapElevation(point); // הצג גובה הנקודה שנלחצה
    } else {
      state.fetchWeather(point); // שלוף מזג אוויר לנקודה
    }
  }

  Widget _buildElevLayer(MapState state) {
    if (state.elevPoints.isEmpty) return const SizedBox.shrink();
    final cs = Theme.of(context).colorScheme;
    if (state.elevMode == DisplayMode.heat && state.elevHeatBytes != null) {
      final b = _gridBounds(state.elevPoints);
      return OverlayImageLayer(overlayImages: [
        OverlayImage(bounds: b, opacity: 0.75, imageProvider: MemoryImage(state.elevHeatBytes!))
      ]);
    }
    if (state.elevMode == DisplayMode.grid) return PolygonLayer(polygons: _buildCells(state.elevPoints));
    return CircleLayer(circles: _buildDots(state.elevPoints));
  }

  Widget _buildTempLayer(MapState state) {
    if (state.tempPoints.isEmpty) return const SizedBox.shrink();
    if (state.tempMode == DisplayMode.heat && state.tempHeatBytes != null) {
      final b = _gridBounds(state.tempPoints);
      return OverlayImageLayer(overlayImages: [
        OverlayImage(bounds: b, opacity: 0.75, imageProvider: MemoryImage(state.tempHeatBytes!))
      ]);
    }
    if (state.tempMode == DisplayMode.grid) return PolygonLayer(polygons: _buildCells(state.tempPoints));
    return CircleLayer(circles: _buildDots(state.tempPoints));
  }

  LatLngBounds _gridBounds(List<GridPoint> pts) {
    double minLat = pts.first.lat, maxLat = pts.first.lat;
    double minLon = pts.first.lon, maxLon = pts.first.lon;
    for (final p in pts) {
      if (p.lat < minLat) minLat = p.lat;
      if (p.lat > maxLat) maxLat = p.lat;
      if (p.lon < minLon) minLon = p.lon;
      if (p.lon > maxLon) maxLon = p.lon;
    }
    return LatLngBounds(LatLng(minLat, minLon), LatLng(maxLat, maxLon));
  }

  List<Polygon> _buildCells(List<GridPoint> pts) {
    final uLats = pts.map((p) => p.lat).toSet().toList()..sort();
    final uLons = pts.map((p) => p.lon).toSet().toList()..sort();
    if (uLats.length < 2 || uLons.length < 2) return [];
    final dLat = (uLats.last - uLats.first) / (uLats.length - 1) / 2;
    final dLon = (uLons.last - uLons.first) / (uLons.length - 1) / 2;
    double minV = pts.first.value, maxV = pts.first.value;
    for (final p in pts) {
      if (p.value < minV) minV = p.value;
      if (p.value > maxV) maxV = p.value;
    }
    final range = max(maxV - minV, 1e-6);
    return pts.map((p) {
      final t = (p.value - minV) / range;
      return Polygon(
        points: [
          LatLng(p.lat - dLat, p.lon - dLon), LatLng(p.lat - dLat, p.lon + dLon),
          LatLng(p.lat + dLat, p.lon + dLon), LatLng(p.lat + dLat, p.lon - dLon),
        ],
        color: _valueColor(t).withAlpha(180),
        borderStrokeWidth: 0, borderColor: Colors.transparent,
      );
    }).toList();
  }

  List<CircleMarker> _buildDots(List<GridPoint> pts) {
    double minV = pts.first.value, maxV = pts.first.value;
    for (final p in pts) {
      if (p.value < minV) minV = p.value;
      if (p.value > maxV) maxV = p.value;
    }
    final range = max(maxV - minV, 1e-6);
    return pts.map((p) => CircleMarker(
      point: LatLng(p.lat, p.lon),
      radius: 6,
      color: _valueColor((p.value - minV) / range).withAlpha(210),
      borderStrokeWidth: 0,
    )).toList();
  }

  Color _valueColor(double t) {
    t = t.clamp(0.0, 1.0);
    int r, g, b;
    if (t < 0.25)      { final s = t / 0.25;        r = 0;              g = (s * 255).round();       b = 255; }
    else if (t < 0.5)  { final s = (t - 0.25)/0.25; r = 0;              g = 255;                     b = (255*(1-s)).round(); }
    else if (t < 0.75) { final s = (t - 0.5) /0.25; r = (s*255).round(); g = 255;                    b = 0; }
    else               { final s = (t - 0.75)/0.25; r = 255;             g = (255*(1-s)).round();     b = 0; }
    return Color.fromARGB(255, r, g, b);
  }

  List<LatLng> _rectPoints(LatLng a, LatLng b) => [
    LatLng(a.latitude, a.longitude), LatLng(a.latitude, b.longitude),
    LatLng(b.latitude, b.longitude), LatLng(b.latitude, a.longitude),
  ];
}

// ── Elevation card ────────────────────────────────────────
class _ElevationCard extends StatelessWidget {
  const _ElevationCard({required this.state, required this.cs});
  final MapState state;
  final ColorScheme cs;
  @override
  Widget build(BuildContext context) => Positioned(
    bottom: 20,
    left: 12,
    child: Material(
      color: cs.surfaceContainerHigh,
      borderRadius: BorderRadius.circular(14),
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: SizedBox(
          width: 160,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(children: [
                Icon(Icons.terrain, size: 14, color: cs.primary),
                const SizedBox(width: 4),
                Text('גובה', style: TextStyle(fontWeight: FontWeight.bold, color: cs.primary, fontSize: 13)),
                const Spacer(),
                GestureDetector(
                  onTap: state.closeElevTap,
                  child: Icon(Icons.close, size: 15, color: cs.outline),
                ),
              ]),
              const SizedBox(height: 6),
              Text(
                '${state.tappedElevPoint!.value.toStringAsFixed(0)} מ\'',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: cs.onSurface),
              ),
              const SizedBox(height: 2),
              Text(
                '${state.tappedElevPoint!.lat.toStringAsFixed(4)}, ${state.tappedElevPoint!.lon.toStringAsFixed(4)}',
                style: TextStyle(fontSize: 10, color: cs.outline),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

// ── Loading chip ──────────────────────────────────────────
class _LoadingChip extends StatelessWidget {
  const _LoadingChip();
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: cs.surfaceContainerHigh,
      borderRadius: BorderRadius.circular(20),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: cs.primary)),
          const SizedBox(width: 10),
          Text('טוען נתונים...', style: TextStyle(color: cs.onSurface)),
        ]),
      ),
    );
  }
}

// ── Weather card ──────────────────────────────────────────
class _WeatherCard extends StatelessWidget {
  const _WeatherCard({required this.state, required this.cs});
  final MapState state;
  final ColorScheme cs;

  static const _wmo = <int, String>{
    0:'שמיים בהירים', 1:'בהיר', 2:'מעונן חלקית', 3:'מעונן',
    45:'ערפל', 51:'טחב', 61:'גשם קל', 63:'גשם', 65:'גשם כבד',
    71:'שלג קל', 73:'שלג', 80:'מקלחות', 95:'סופת רעמים',
  };

  @override
  Widget build(BuildContext context) => Positioned(
    bottom: 20,
    right: 12,
    child: Material(
      color: cs.surfaceContainerHigh,
      borderRadius: BorderRadius.circular(14),
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: SizedBox(
          width: 160,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(children: [
                Text('מזג אוויר', style: TextStyle(fontWeight: FontWeight.bold, color: cs.primary, fontSize: 13)),
                const Spacer(),
                GestureDetector(
                  onTap: state.closeWeather,
                  child: Icon(Icons.close, size: 15, color: cs.outline),
                ),
              ]),
              const SizedBox(height: 6),
              if (state.weatherLoading)
                const Center(child: CircularProgressIndicator(strokeWidth: 2))
              else if (state.weatherData == null)
                Text('שגיאה', style: TextStyle(color: cs.error, fontSize: 11))
              else
                Directionality(
                  textDirection: TextDirection.rtl,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _WRow(Icons.thermostat, '${state.weatherData!['temp']}°C', cs),
                      _WRow(Icons.water_drop, '${state.weatherData!['humidity']}%', cs),
                      _WRow(Icons.air, '${state.weatherData!['wind']} km/h', cs),
                      _WRow(Icons.wb_cloudy, _wmo[state.weatherData!['code'] as int] ?? 'לא ידוע', cs),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _WRow extends StatelessWidget {
  const _WRow(this.icon, this.text, this.cs);
  final IconData icon;
  final String text;
  final ColorScheme cs;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(children: [
      Icon(icon, size: 13, color: cs.primary),
      const SizedBox(width: 5),
      Text(text, style: TextStyle(fontSize: 12, color: cs.onSurface)),
    ]),
  );
}

// ── Ruler card ────────────────────────────────────────────
class _RulerCard extends StatelessWidget {
  const _RulerCard({required this.state, required this.cs});
  final MapState state;
  final ColorScheme cs;

  String _fmt(double meters) {
    final km  = meters / 1000;
    final nm  = meters / 1852;
    final kmStr = km >= 10  ? '${km.toStringAsFixed(1)} ק"מ'  : '${km.toStringAsFixed(2)} ק"מ';
    final nmStr = nm >= 10  ? '${nm.toStringAsFixed(1)} NM'   : '${nm.toStringAsFixed(2)} NM';
    return '$kmStr  /  $nmStr';
  }

  @override
  Widget build(BuildContext context) => Positioned(
    bottom: 50,
    left: 12,
    child: Material(
      color: cs.surfaceContainerHigh,
      borderRadius: BorderRadius.circular(14),
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(children: [
              Icon(Icons.straighten, size: 13, color: cs.primary),
              const SizedBox(width: 4),
              Text('מרחק', style: TextStyle(fontWeight: FontWeight.bold, color: cs.primary, fontSize: 12)),
              const SizedBox(width: 12),
              GestureDetector(
                onTap: state.clearRuler,
                child: Icon(Icons.close, size: 14, color: cs.outline),
              ),
            ]),
            const SizedBox(height: 4),
            Text(_fmt(state.rulerTotalMeters),
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: cs.onSurface)),
            Text('${state.rulerPoints.length} נקודות', style: TextStyle(fontSize: 10, color: cs.outline)),
          ],
        ),
      ),
    ),
  );
}

// ── Nav button ───────────────────────────────────────────
class _NavBtn extends StatelessWidget {
  const _NavBtn({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: cs.onSurfaceVariant, size: 22),
            const SizedBox(height: 2),
            Text(label, style: TextStyle(fontSize: 10, color: cs.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}

// ── LOS Profile Panel ─────────────────────────────────────
// פאנל תחתי המציג גרפי פרופיל לכל סשני LOS הפעילים
class _LosProfilePanel extends StatelessWidget {
  const _LosProfilePanel({required this.state, required this.cs});
  final MapState state;
  final ColorScheme cs;

  @override
  Widget build(BuildContext context) {
    final sessions = state.losSessions.where((s) => s.points.isNotEmpty).toList(); // רק סשנים מחושבים
    if (sessions.isEmpty) return const SizedBox.shrink(); // אל תרנדר אם אין נתונים
    // viewPadding.bottom = גובה פס הניווט הפיזי של אנדרואיד (לא מושפע מ-Scaffold)
    // משמש להוספת ריפוד תחתון כדי שהפאנל לא יחפוף עם פס הניווט במכשירים edge-to-edge
    final navBarH = MediaQuery.of(context).viewPadding.bottom;
    return Positioned(
      bottom: 0, left: 0, right: 0, // הדבק לתחתית אזור הגוף
      child: Material(
        color: cs.surface.withAlpha(245), // רקע שקוף-למחצה
        elevation: 6,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // ── כותרת הפאנל ──
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              child: Row(children: [
                Icon(Icons.visibility_outlined, size: 13, color: cs.primary), // אייקון כלי LOS
                const SizedBox(width: 5),
                Text('קווי ראייה',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: cs.primary)),
                const Spacer(),
                GestureDetector(
                  onTap: state.clearLosMap, // כפתור ניקוי כל הסשנים
                  child: Icon(Icons.close, size: 16, color: cs.outline),
                ),
              ]),
            ),
            const Divider(height: 1, thickness: 1), // מפריד בין כותרת לגרפים
            // ── גרפים גלילה אופקית ──
            SizedBox(
              height: 155, // גובה אזור הגרפים
              child: ListView.separated(
                scrollDirection: Axis.horizontal, // גלילה ימינה-שמאלה
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                itemCount: sessions.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8), // רווח בין גרפים
                itemBuilder: (_, i) => _LosProfileCard(
                  session: sessions[i],
                  cs: cs,
                  onRemove: () => state.removeLosSession(sessions[i].idx), // מחיקת סשן בודד
                ),
              ),
            ),
            // ריפוד תחתון לפס הניווט — מונע חפיפה במכשירי edge-to-edge
            if (navBarH > 0) SizedBox(height: navBarH),
          ],
        ),
      ),
    );
  }
}

// כרטיס גרף פרופיל לסשן LOS בודד
class _LosProfileCard extends StatelessWidget {
  const _LosProfileCard({required this.session, required this.cs, required this.onRemove});
  final LosSession session;
  final ColorScheme cs;
  final VoidCallback onRemove; // callback למחיקת הסשן מהרשימה

  @override
  Widget build(BuildContext context) => SizedBox(
    width: 220, // רוחב קבוע לכל כרטיס
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── שורת כותרת: צבע, מספר, מרחק, X ──
        Row(children: [
          Container(
            width: 9, height: 9,
            decoration: BoxDecoration(color: session.color, shape: BoxShape.circle), // נקודת צבע הסשן
          ),
          const SizedBox(width: 4),
          Text(
            'LOS ${session.idx}  ${session.totalKm.toStringAsFixed(1)} ק"מ', // שם וגובה מרחק
            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: cs.onSurface),
          ),
          const Spacer(),
          GestureDetector(
            onTap: onRemove, // לחיצה על X מוחקת סשן בודד
            child: Icon(Icons.close, size: 13, color: cs.outline),
          ),
        ]),
        const SizedBox(height: 2),
        // ── שורת מידע: תוצאת נראות ──
        Text(
          session.allVisible
              ? '✓ גלוי לגמרי' // כל הקו גלוי
              : session.firstBlockKm != null
                  ? '✗ חסימה ב-${session.firstBlockKm!.toStringAsFixed(1)} ק"מ' // מרחק חסימה ראשונה
                  : '✗ חסום', // חסום מלכתחילה
          style: TextStyle(
            fontSize: 9,
            color: session.allVisible ? const Color(0xFF44CC44) : const Color(0xFFFF4444), // ירוק/אדום
          ),
        ),
        const SizedBox(height: 3),
        // ── גרף פרופיל השטח ──
        Expanded(
          child: CustomPaint(
            painter: _LosProfilePainter(session: session, cs: cs), // ציירן הגרף
            size: Size.infinite,
          ),
        ),
      ],
    ),
  );
}

// ציירן גרף פרופיל LOS — שטח (ירוק-זית) + קו ראייה (ירוק/אדום)
class _LosProfilePainter extends CustomPainter {
  const _LosProfilePainter({required this.session, required this.cs});
  final LosSession session;
  final ColorScheme cs;

  @override
  void paint(Canvas canvas, Size size) {
    if (session.points.isEmpty) return; // אין נקודות לצייר
    final pts     = session.points;
    final maxDist = pts.last.distKm;    // ציר X: ק"מ מלא לסוף
    if (maxDist <= 0) return;

    // ── חישוב טווח Y (גובה) עם ריפוד ──
    double minE = pts.first.elevation, maxE = pts.first.elevation;
    for (final p in pts) {
      if (p.elevation < minE) minE = p.elevation; // מינימום שטח
      if (p.elevation > maxE) maxE = p.elevation; // מקסימום שטח
      if (p.losH > maxE)      maxE = p.losH;      // גם גובה LOS בטווח
    }
    final pad  = (maxE - minE) * 0.12 + 5.0; // ריפוד 12% + 5 מ' קבוע
    final yMin = minE - pad;
    final yMax = maxE + pad;
    final yRng = yMax - yMin;

    // פונקציות המרה: ערכי נתונים ← → פיקסלים על הקנבס
    double toX(double km) => km / maxDist * size.width;                          // ציר מרחק
    double toY(double m)  => size.height - (m - yMin) / yRng * size.height;      // ציר גובה

    // ── קווי רשת אופקיים ──
    final gridPaint = Paint()
      ..color = cs.outline.withAlpha(35)
      ..strokeWidth = 0.5;
    for (int g = 1; g <= 3; g++) { // 3 קווי רשת פנימיים
      final y = size.height * g / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // ── פוליגון שטח (ירוק-זית, מלא) ──
    // משתמשים ב-ui.Path כדי להבדיל מ-Path של flutter_map
    final terrainPath = ui.Path()..moveTo(0, size.height); // פינה שמאל-תחתון
    for (final p in pts) {
      terrainPath.lineTo(toX(p.distKm), toY(p.elevation)); // קו לאורך פני השטח
    }
    terrainPath.lineTo(size.width, size.height); // ירידה לפינה ימין-תחתון
    terrainPath.close();
    canvas.drawPath(terrainPath, Paint()
      ..color = const Color(0xFF556B2F).withAlpha(185) // ירוק-כהה שקוף לשטח
      ..style  = PaintingStyle.fill);
    canvas.drawPath(terrainPath, Paint()
      ..color       = const Color(0xFF8B9B5A) // קו מתאר ירוק-זית
      ..strokeWidth = 1.0
      ..style       = PaintingStyle.stroke);

    // ── קו LOS: ירוק לחלקים גלויים, אדום לחסומים ──
    final visPaint = Paint()
      ..color       = const Color(0xFF44CC44) // ירוק לקטעים גלויים
      ..strokeWidth = 1.5
      ..style       = PaintingStyle.stroke;
    final blkPaint = Paint()
      ..color       = const Color(0xFFFF4444) // אדום לקטעים חסומים
      ..strokeWidth = 1.5
      ..style       = PaintingStyle.stroke;

    // עוברים על כל הנקודות ומצרפים לקטעים לפי סטטוס נראות
    if (pts.isEmpty) return; // אין נקודות — אין מה לצייר
    var segPath = ui.Path(); // ui.Path כדי להבדיל מ-Path של flutter_map
    bool segVis = pts.first.visible; // לא-nullable: מאותחל מהנקודה הראשונה
    segPath.moveTo(toX(pts.first.distKm), toY(pts.first.losH)); // נקודת התחלה
    for (int i = 1; i < pts.length; i++) {
      final p  = pts[i];
      final x  = toX(p.distKm);
      final y  = toY(p.losH); // גובה קו הראייה (לא השטח)
      if (p.visible != segVis) {
        canvas.drawPath(segPath, segVis ? visPaint : blkPaint); // סיים קטע קיים
        segPath = ui.Path()
          ..moveTo(toX(pts[i - 1].distKm), toY(pts[i - 1].losH)); // התחל קטע חדש מנקודת המעבר
        segPath.lineTo(x, y);
        segVis = p.visible; // עדכן נראות לקטע החדש
      } else {
        segPath.lineTo(x, y); // המשך קטע קיים
      }
    }
    canvas.drawPath(segPath, segVis ? visPaint : blkPaint); // קטע אחרון — תמיד קיים
  }

  @override
  bool shouldRepaint(_LosProfilePainter old) =>
      old.session != session; // צייר מחדש רק בשינוי נתונים
}

// ── מקרא שכבת NOTAM רחפנים ─────────────────────────────────
class _UasNotamLegend extends StatelessWidget {
  const _UasNotamLegend();
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Material(
        color: cs.surface.withAlpha(230),
        borderRadius: BorderRadius.circular(8),
        elevation: 3,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 220),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    width: 12, height: 12,
                    decoration: const BoxDecoration(color: Color(0xFFFAB387), shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text('אזורי NOTAM רחפנים',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: cs.onSurface)),
                ]),
                const SizedBox(height: 2),
                Text('פעילות מאושרת של גורם אחר — להימנעות, לא לטיסה חופשית',
                    style: TextStyle(fontSize: 9, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── מקרא שכבת "אזורי תיאום כטב"ם" ────────────────────────
class _UasCoordLegend extends StatelessWidget {
  const _UasCoordLegend();
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Material(
        color: cs.surface.withAlpha(230),
        borderRadius: BorderRadius.circular(8),
        elevation: 3,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 220),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Container(
                    width: 12, height: 12,
                    decoration: const BoxDecoration(color: Color(0xFF6366F1), shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text('אזורי תיאום כטב"ם — דורש אישור נת"א',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: cs.onSurface)),
                ]),
                const SizedBox(height: 2),
                Text('כל שימוש באזור מחייב תיאום ואישור מראש מיחידת הנת"א — לא אזור חופשי לטיסה',
                    style: TextStyle(fontSize: 9, color: cs.onSurfaceVariant)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── כפתור מידע — כלל טיסת VLOS — תוכן טקסטואלי סטטי, תמיד מוצג ──
class _VlosInfoButton extends StatelessWidget {
  const _VlosInfoButton();

  static const _vlosText =
      'טיסת כטב"ם בקשר עין (VLOS) פטורה מדרישת סגירה אווירית והגשת תוכנית טיסה כאשר '
      'מתקיימים כל התנאים הבאים:\n\n'
      '• גובה שאינו עולה על 100 מטר מעל פני הקרקע\n'
      '• מחוץ לאזורים אסורים/מוגבלים/מסוכנים (אלא אם התקבל אישור מאחראי האזור)\n'
      '• במרחק הגדול מ-500 רגל מבסיס ענן\n'
      '• בתנאי ראות אופקית העולים על 3 ק"מ\n'
      '• מחוץ לתשתית תעופתית (נתיבים)\n\n'
      'שימו לב: הפטור מסגירה אווירית/תוכנית טיסה אינו מבטל את הצורך באישור נפרד '
      'להפעלה באזור פיקוח שדה תעופה (CTR) או באזור מנחת (ATZ) — פירוט מלא: פמ"ת פנים ארצי, פרק ב\'-09.';

  void _showVlosInfoSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        final cs = Theme.of(ctx).colorScheme;
        return Directionality(
          textDirection: TextDirection.rtl,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    width: 40, height: 4,
                    decoration: BoxDecoration(color: cs.outlineVariant, borderRadius: BorderRadius.circular(2)),
                  ),
                ),
                Row(children: [
                  Icon(Icons.info_outline, color: cs.primary),
                  const SizedBox(width: 8),
                  Text('כלל טיסת VLOS',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: cs.onSurface)),
                ]),
                const SizedBox(height: 10),
                Text(_vlosText, style: TextStyle(fontSize: 13, color: cs.onSurface, height: 1.5)),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: cs.surface.withAlpha(230),
      shape: const CircleBorder(),
      elevation: 3,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: () => _showVlosInfoSheet(context),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Icon(Icons.info_outline, size: 18, color: cs.primary),
        ),
      ),
    );
  }
}

// ── Scale bar ─────────────────────────────────────────────
class _ScaleBar extends StatelessWidget {
  const _ScaleBar({required this.mapController});
  final MapController mapController;

  static double _metersPerPixel(MapController c) {
    final zoom = c.camera.zoom;
    final lat  = c.camera.center.latitude;
    return 156543.03392 * cos(lat * pi / 180) / pow(2, zoom);
  }

  static double _nice(double v) {
    final exp = (log(v) / log(10)).floor();
    final f   = v / pow(10, exp);
    final n   = f < 1.5 ? 1.0 : f < 3.0 ? 2.0 : f < 7.0 ? 5.0 : 10.0;
    return n * pow(10, exp).toDouble();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    double mpp;
    try { mpp = _metersPerPixel(mapController); }
    catch (_) { return const SizedBox.shrink(); }

    const maxPx   = 110.0;
    final maxM    = mpp * maxPx;
    final niceM   = _nice(maxM);
    final barW    = (niceM / mpp).clamp(20.0, 180.0);

    final km  = niceM / 1000;
    final nm  = niceM / 1852;
    final kmLabel = km >= 1
        ? '${km >= 10 ? km.toStringAsFixed(0) : km.toStringAsFixed(1)} ק"מ'
        : '${niceM.round()} מ\'';
    final nmLabel = nm >= 1
        ? '${nm >= 10 ? nm.toStringAsFixed(0) : nm.toStringAsFixed(1)} NM'
        : '${(nm * 1852).round()} מ\'';

    return Material(
      color: cs.surface.withAlpha(200),
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: barW,
              height: 3,
              decoration: BoxDecoration(
                color: cs.onSurface,
                borderRadius: BorderRadius.circular(1.5),
              ),
            ),
            const SizedBox(height: 2),
            Text('$kmLabel / $nmLabel',
                style: TextStyle(fontSize: 9, color: cs.onSurface, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}
