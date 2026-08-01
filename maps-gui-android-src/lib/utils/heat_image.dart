import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../models/grid_point.dart';

ui.Color _valueToColor(double t) {
  t = t.clamp(0.0, 1.0);
  int r, g, b;
  if (t < 0.25) {
    final s = t / 0.25; r = 0; g = (s * 255).round(); b = 255;
  } else if (t < 0.5) {
    final s = (t - 0.25) / 0.25; r = 0; g = 255; b = (255 * (1 - s)).round();
  } else if (t < 0.75) {
    final s = (t - 0.5) / 0.25; r = (s * 255).round(); g = 255; b = 0;
  } else {
    final s = (t - 0.75) / 0.25; r = 255; g = (255 * (1 - s)).round(); b = 0;
  }
  return ui.Color.fromARGB(200, r, g, b);
}

double _bilinear({
  required double lat, required double lon,
  required List<double> uLats, required List<double> uLons,
  required Map<String, double> lookup,
  required double minVal, required double range,
}) {
  lat = lat.clamp(uLats.first, uLats.last);
  lon = lon.clamp(uLons.first, uLons.last);
  int li = 0, hi = uLats.length - 1;
  while (li < hi - 1) { final m = (li + hi) >> 1; if (uLats[m] <= lat) li = m; else hi = m; }
  int lj = 0, hj = uLons.length - 1;
  while (lj < hj - 1) { final m = (lj + hj) >> 1; if (uLons[m] <= lon) lj = m; else hj = m; }
  final ty = (lat - uLats[li]) / (uLats[hi] - uLats[li]);
  final tx = (lon - uLons[lj]) / (uLons[hj] - uLons[lj]);
  double v(int i, int j) => ((lookup['${uLats[i]}_${uLons[j]}'] ?? 0.0) - minVal) / range;
  return v(li,lj)*(1-ty)*(1-tx) + v(li,hj)*(1-ty)*tx + v(hi,lj)*ty*(1-tx) + v(hi,hj)*ty*tx;
}

Future<Uint8List> renderHeatImage(List<GridPoint> points) async {
  const size = 512;
  if (points.isEmpty) return Uint8List(0);
  final uLats = points.map((p) => p.lat).toSet().toList()..sort();
  final uLons = points.map((p) => p.lon).toSet().toList()..sort();
  double minVal = points.first.value, maxVal = points.first.value;
  for (final p in points) { if (p.value < minVal) minVal = p.value; if (p.value > maxVal) maxVal = p.value; }
  final range = max(maxVal - minVal, 1e-6);
  final lookup = <String, double>{ for (final p in points) '${p.lat}_${p.lon}': p.value };
  final minLat = uLats.first, maxLat = uLats.last;
  final minLon = uLons.first, maxLon = uLons.last;
  final pixels = Uint8List(size * size * 4);
  for (int row = 0; row < size; row++) {
    final lat = maxLat - (maxLat - minLat) * row / (size - 1);
    for (int col = 0; col < size; col++) {
      final lon = minLon + (maxLon - minLon) * col / (size - 1);
      final t = _bilinear(lat: lat, lon: lon, uLats: uLats, uLons: uLons, lookup: lookup, minVal: minVal, range: range);
      final c = _valueToColor(t);
      final idx = (row * size + col) * 4;
      pixels[idx] = c.red; pixels[idx+1] = c.green; pixels[idx+2] = c.blue; pixels[idx+3] = c.alpha;
    }
  }
  final completer = Completer<Uint8List>();
  ui.decodeImageFromPixels(pixels, size, size, ui.PixelFormat.rgba8888, (img) async {
    final byteData = await img.toByteData(format: ui.ImageByteFormat.png);
    completer.complete(byteData!.buffer.asUint8List());
  });
  return completer.future;
}

// שכבת חום מנקודות מפוזרות (בחירה ידנית) — בניגוד ל-renderHeatImage שמניח גריד סדיר,
// כאן כל נקודה תורמת "בלוב" רדיאלי דועך (gaussian falloff) המצטבר עם שכנותיו,
// מקביל ל-Leaflet.heat בגרסת הדסקטופ. רקע שקוף לחלוטין במקומות ללא תרומת חום.
Future<({Uint8List bytes, LatLngBounds bounds})> renderScatterHeatImage(
  List<LatLng> points, {
  double radiusDeg = 0.02,
}) async {
  const size = 512;
  if (points.isEmpty) {
    return (bytes: Uint8List(0), bounds: LatLngBounds(const LatLng(0, 0), const LatLng(0, 0)));
  }
  final lats = points.map((p) => p.latitude).toList();
  final lons = points.map((p) => p.longitude).toList();
  final minLat = lats.reduce(min) - radiusDeg, maxLat = lats.reduce(max) + radiusDeg;
  final minLon = lons.reduce(min) - radiusDeg, maxLon = lons.reduce(max) + radiusDeg;
  final bounds = LatLngBounds(LatLng(minLat, minLon), LatLng(maxLat, maxLon));

  final sigma = radiusDeg / 2;
  final pixels = Uint8List(size * size * 4);
  for (int row = 0; row < size; row++) {
    final lat = maxLat - (maxLat - minLat) * row / (size - 1);
    for (int col = 0; col < size; col++) {
      final lon = minLon + (maxLon - minLon) * col / (size - 1);
      double intensity = 0;
      for (final p in points) {
        final dLat = lat - p.latitude, dLon = lon - p.longitude;
        final distSq = dLat * dLat + dLon * dLon;
        intensity += exp(-distSq / (2 * sigma * sigma));
      }
      intensity = intensity.clamp(0.0, 1.0);
      final idx = (row * size + col) * 4;
      if (intensity < 0.03) {
        pixels[idx + 3] = 0; // שקוף — אין תרומת חום משמעותית כאן
      } else {
        final c = _valueToColor(intensity);
        pixels[idx] = c.red; pixels[idx + 1] = c.green; pixels[idx + 2] = c.blue; pixels[idx + 3] = c.alpha;
      }
    }
  }
  final completer = Completer<Uint8List>();
  ui.decodeImageFromPixels(pixels, size, size, ui.PixelFormat.rgba8888, (img) async {
    final byteData = await img.toByteData(format: ui.ImageByteFormat.png);
    completer.complete(byteData!.buffer.asUint8List());
  });
  return (bytes: await completer.future, bounds: bounds);
}
