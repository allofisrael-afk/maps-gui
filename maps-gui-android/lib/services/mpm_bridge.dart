// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'dart:convert';
import 'package:flutter/services.dart';

/// גישור ל-mpm_api.py (שורש-הפרויקט) דרך Chaquopy — Stage 3 (FR-D-237). מריץ את הקוד הפייתוני
/// המקורי (stdlib-בלבד, ר' MAPS-GUI_SRS.md FR-D-230) בתוך ה-APK, ללא שרת כלל — אותה החלטה
/// בדיוק כמו שאר הכלים ב-Android (on-device), רק דרך Python ולא Dart (החלטה א בשלב 1).
/// ה-MethodChannel מצופה ב-android_MainActivity.kt (maps-gui-android-src) — שם ושם-המתודה
/// חייבים להישאר תואמים.
class MpmBridge {
  static const _channel = MethodChannel('com.mapsapp.maps_gui_android/mpm');

  /// קורא ל-action נתון (trajectory/solve/solve_mv/table/calibrate/terrain_check/min_qe_for_crest)
  /// עם params, ומחזיר את ה-dict המפורש מה-JSON שחזר מ-mpm_api.dispatch_json. זורק Exception
  /// עם הודעה ברורה בעברית אם הערוץ-הנאטיבי עצמו נכשל (לא שגיאה-עסקית, שתמיד חוזרת כ-ok:false).
  static Future<Map<String, dynamic>> call(String action, Map<String, dynamic> params) async {
    final String resultJson;
    try {
      resultJson = await _channel.invokeMethod<String>('dispatch', {
        'action': action,
        'paramsJson': jsonEncode(params),
      }) ?? '{"ok": false, "error": "תשובה ריקה מ-Python"}';
    } on PlatformException catch (e) {
      throw Exception('שגיאת-גישור ל-Python (Chaquopy): ${e.message ?? e.code}');
    }
    return (jsonDecode(resultJson) as Map).cast<String, dynamic>();
  }
}
