// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
// T25 (F-057): בדיקות יחידה ללוגיקה החדשה באנדרואיד — בלי מכשיר ובלי Python: מפענח המדריך, מגבלות קו הראייה,
// ובקר "מאזור לאזור" (ציור, סינון, דילול, צביעה ישנה). הרצה: flutter test (מתוך maps-gui-android-src).
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:maps_gui_android/screens/user_guide_screen.dart';
import 'package:maps_gui_android/state/area_fire_controller.dart';
import 'package:maps_gui_android/state/map_state.dart';

void main() {
  group('MarkdownLite — מפענח המדריך המוטמע', () {
    const md = '# כותרת ראשית\n\nפסקה ראשונה\nהמשך הפסקה\n\n## משנה\n\n| א | ב |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n> ציטוט\n\n- פריט\n  - פריט פנימי\n1. ממוספר\n\n---\n'; // כל הסוגים
    final blocks = MarkdownLite.parse(md); // הפענוח
    final kinds = blocks.map((b) => b.runtimeType.toString()).toList(); // סוגי הבלוקים
    test('כל סוגי הבלוקים מזוהים', () {
      expect(kinds.where((k) => k.contains('Heading')).length, 2); // שתי כותרות
      expect(kinds.where((k) => k.contains('Table')).length, 1); // טבלה אחת
      expect(kinds.where((k) => k.contains('Quote')).length, 1); // ציטוט
      expect(kinds.where((k) => k.contains('Item')).length, 3); // שלושה פריטים
      expect(kinds.where((k) => k.contains('Rule')).length, 1); // קו מפריד
      expect(kinds.where((k) => k.contains('Para')).length, 1); // פסקה אחת (שתי שורות מאוחדות)
    });
    test('שורת ההפרדה של הטבלה לא נספרת כשורה', () {
      final t = blocks.firstWhere((b) => b.runtimeType.toString().contains('Table')); // הטבלה
      expect((t as dynamic).rows.length, 3); // כותרת + 2 שורות
    });
    test('קובץ עם CRLF מפוענח כמו LF', () {
      expect(MarkdownLite.parse(md.replaceAll('\n', '\r\n')).length, blocks.length); // אותו מספר בלוקים
    });
  });

  group('MapState.losLimitsText / inSector — מגבלות קו הראייה (FR-D-288/290)', () {
    final obs = const LatLng(31.25, 34.80), north = const LatLng(31.35, 34.80); // יעד צפונה
    test('ידני בלי גזרה ובלי תוספת → אין שורה', () {
      expect(MapState.losLimitsText(null, obs, north, 11, 300, 300), isNull); // null
    });
    test('גזרה 300→60 דרך צפון: יעד צפוני בגזרה, דרומי מחוץ', () {
      expect(MapState.losLimitsText(null, obs, north, 11, 300, 300, 300, 60), contains('בגזרה ✔')); // בפנים
      expect(MapState.losLimitsText(null, obs, const LatLng(31.15, 34.80), 11, 300, 300, 300, 60), contains('מחוץ לגזרה')); // בחוץ
    });
    test('inSector: עטיפה דרך צפון וגזרה רגילה', () {
      expect(MapState.inSector(10, 300, 60), isTrue); // דרך צפון
      expect(MapState.inSector(180, 300, 60), isFalse); // דרום
      expect(MapState.inSector(90, 45, 135), isTrue); // רגילה
    });
    test('מכ"ם: טווח ועילוי בשדה', () {
      final r = {'label': 'R', 'antenna': 'generic', 'boresight': 0.0, 'maxScan': 60.0, 'range': 20.0, 'minRange': 0.5, 'vc': 5.0, 'vw': 30.0}; // מכ"ם
      final txt = MapState.losLimitsText(r, obs, north, 11, 305, 1300)!; // יעד גבוה
      expect(txt, contains('בטווח ✔')); // בטווח
      expect(txt, contains('בשדה ✔')); // בשדה האנכי
      expect(MapState.losLimitsText(r, obs, north, 30, 305, 1300)!, contains('מעבר לטווח')); // מעבר לטווח
    });
  });

  group('AreaFireController — ירי מאזור לאזור (A6)', () {
    test('הקשה בלי ציור לא נלכדת (לא מפריעה לכלים אחרים)', () {
      final c = AreaFireController(); // בקר
      expect(c.handleMapTap(const LatLng(31, 34)), isFalse); // לא שלנו
    });
    test('מלבן: שתי הקשות → אזור של 4 פינות, והציור נגמר', () {
      final c = AreaFireController()..startDraw('launch', 'rect'); // ציור
      expect(c.handleMapTap(const LatLng(31.0, 34.0)), isTrue); // פינה ראשונה
      c.handleMapTap(const LatLng(31.1, 34.2)); // פינה נגדית
      expect(c.areas.length, 1); // אזור אחד
      expect(c.areas.first.points.length, 4); // ארבע פינות
      expect(c.areas.first.kind, 'launch'); // סוג
      expect(c.drawing, isFalse); // הציור הסתיים
    });
    test('מצולע: פחות מ-3 נקודות נדחה, 3 נקודות מתקבלות', () {
      final c = AreaFireController()..startDraw('target', 'poly'); // ציור
      c.handleMapTap(const LatLng(31.0, 34.0)); c.handleMapTap(const LatLng(31.0, 34.1)); // שתי נקודות
      expect(c.finishDraw(), isNotNull); // שגיאה
      c.handleMapTap(const LatLng(31.1, 34.1)); // שלישית
      expect(c.finishDraw(), isNull); // תקין
      expect(c.areas.single.name, 'מטרה 1'); // מספור לפי סוג
    });
    AreaFireController withResult() { // בקר עם תוצאה מזויפת: 3 מסלולים
      final c = AreaFireController(); // בקר
      List path() => List.generate(21, (k) => [31.0 + k * 0.001, 34.0, 300.0]); // 21 נקודות
      c.result = {'rows': [
        {'group': 'low', 'la': 0, 'ta': 0, 'path': path()},
        {'group': 'high', 'la': 0, 'ta': 1, 'path': path()},
        {'group': 'low', 'la': 1, 'ta': 1, 'path': path()},
      ]};
      return c;
    }
    test('סינון לפי ענף, אזור שיגור ואזור מטרה', () {
      final c = withResult(); // בקר
      expect(c.filtered(), [0, 1, 2]); // הכול
      c.fBranch = 'low'; expect(c.filtered(), [0, 2]); // נמוך
      c.fBranch = 'all'; c.fLaunch = 1; expect(c.filtered(), [2]); // אזור שיגור 1
      c.fLaunch = -1; c.fTarget = 1; expect(c.filtered(), [1, 2]); // אזור מטרה 1
    });
    test('"רק לא נצפים" לפי המסיכות', () {
      final c = withResult()..fUnseen = true; // בקר
      c.masks = [List.filled(21, 0), [1, ...List.filled(20, 0)], List.filled(21, 0)]; // השני נצפה בנקודה אחת
      expect(c.filtered(), [0, 2]); // רק לא נצפים
    });
    test('דילול שווה מעל התקרה', () {
      final c = AreaFireController(); // בקר
      final idx = List.generate(5000, (i) => i); // 5000 מסלולים
      final t = c.thinned(idx); // מדולל
      expect(t.length, AreaFireController.maxDraw); // בדיוק התקרה
      expect(t.first, 0); // מתחיל בראשון
      expect(c.thinned([1, 2, 3]), [1, 2, 3]); // מתחת לתקרה — בלי שינוי
    });
    test('צביעה ישנה: שינוי במכ"ם המוצב משנה את החתימה', () {
      final c = withResult(); // בקר
      final sites = [{'name': 'R', 'params': {'lat': 31.0, 'lon': 34.0, 'range_km': 50}}]; // מכ"ם
      c.visSig = AreaFireController.sitesSig(sites); // צביעה עדכנית
      expect(c.isStale(sites), isFalse); // לא ישנה
      final moved = [{'name': 'R', 'params': {'lat': 31.1, 'lon': 34.0, 'range_km': 50}}]; // הוזז
      expect(c.isStale(moved), isTrue); // ישנה
    });
    test('fmtTime: שניות, דקות, שעות', () {
      expect(AreaFireController.fmtTime(30), "30 שנ'"); // שניות
      expect(AreaFireController.fmtTime(600), "10 דק'"); // דקות
      expect(AreaFireController.fmtTime(7200), '2.0 שעות'); // שעות
    });
  });
}
