// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
import 'package:flutter/services.dart';

/// שמירה ופתיחה של קובץ טקסט דרך חלון הקבצים המובנה של אנדרואיד (Storage Access Framework) — שלב ג' של כלי
/// בדיקת מעקב המכ"ם (MAPS-GUI_SRS.md FR-D-283). בלי ספריית צד-שלישי ובלי הרשאות אחסון: הצד הנאטיבי ב-
/// android_MainActivity.kt (אותו שם ערוץ בדיוק). משמש לייצוא CSV, לפרופילי מכ"ם (JSON) ולטעינת מסלול מ-CSV.
class FileBridge {
  static const _channel = MethodChannel('com.mapsapp.maps_gui_android/files'); // זהה ל-FILES_CHANNEL ב-Kotlin

  /// פותח חלון "שמירה בשם" ושומר את הטקסט (UTF-8). true = נשמר, false = המשתמש ביטל. זורק Exception על כשל כתיבה.
  static Future<bool> saveText(String fileName, String mime, String text) async {
    try {
      final r = await _channel.invokeMethod<bool>('saveText', {'fileName': fileName, 'mime': mime, 'text': text}); // החלון
      return r == true; // null = בוטל
    } on PlatformException catch (e) {
      throw Exception('שמירת הקובץ נכשלה: ${e.message ?? e.code}'); // הודעה ברורה
    }
  }

  /// פותח חלון בחירת קובץ ומחזיר את התוכן כטקסט, או null אם המשתמש ביטל.
  static Future<String?> openText() async {
    try {
      return await _channel.invokeMethod<String>('openText'); // החלון
    } on PlatformException catch (e) {
      throw Exception('פתיחת הקובץ נכשלה: ${e.message ?? e.code}'); // הודעה ברורה
    }
  }
}
