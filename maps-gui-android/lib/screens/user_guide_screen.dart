// Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
// See LICENSE in the project root.
// מדריך ההפעלה למשתמש — מוטמע ב-APK כנכס (assets/user_guide.md), מועתק ממדריך-הפעלה-Android.md בכל בנייה
// ע"י build_apk.ps1. מוצג במסך מלא עם מפַרש Markdown פשוט (קוד עצמי — בלי ספרייה חיצונית ובלי רישיון חדש).
import 'package:flutter/material.dart'; // רכיבי הממשק
import 'package:flutter/services.dart' show rootBundle; // קריאת הנכס מתוך ה-APK
import 'package:shared_preferences/shared_preferences.dart'; // זיכרון "המדריך כבר הוצג" בין הפעלות

/// נתיב הנכס בתוך ה-APK — חייב להתאים ל-pubspec.yaml ול-build_apk.ps1
const String kUserGuideAsset = 'assets/user_guide.md';

/// מפתח ההעדפה: המדריך הוצג אוטומטית אחרי ההתקנה (פעם אחת בלבד)
const String _kGuideShownKey = 'user_guide_shown_v1';

/// פותח את מסך המדריך
void openUserGuide(BuildContext context) {
  Navigator.of(context).push(MaterialPageRoute(builder: (_) => const UserGuideScreen())); // מסך מלא
}

/// הפעלה ראשונה אחרי התקנה: פותח את המדריך פעם אחת, וזוכר שכבר הוצג
Future<void> showUserGuideOnFirstRun(BuildContext context) async {
  final prefs = await SharedPreferences.getInstance(); // האחסון המקומי
  if (prefs.getBool(_kGuideShownKey) ?? false) return; // כבר הוצג — לא מציגים שוב
  await prefs.setBool(_kGuideShownKey, true); // מסמנים לפני הפתיחה — שלא ייפתח פעמיים
  if (!context.mounted) return; // המסך נסגר בינתיים
  openUserGuide(context); // הצגה
}

/// מסך המדריך: טוען את הנכס ומציג אותו
class UserGuideScreen extends StatelessWidget {
  const UserGuideScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme; // הצבעים
    return Directionality(
      textDirection: TextDirection.rtl, // עברית — מימין לשמאל
      child: Scaffold(
        appBar: AppBar(title: const Text('📖 מדריך הפעלה')), // כותרת + חזרה
        body: FutureBuilder<String>(
          future: rootBundle.loadString(kUserGuideAsset), // הקובץ מתוך ה-APK
          builder: (context, snap) {
            if (snap.hasError) return Center(child: Text('המדריך לא נמצא באפליקציה', style: TextStyle(color: cs.error))); // נכס חסר
            if (!snap.hasData) return const Center(child: CircularProgressIndicator()); // טוען
            final blocks = MarkdownLite.parse(snap.data!); // פירוק לבלוקים
            return SelectionArea( // אפשר לסמן ולהעתיק טקסט
              child: ListView.builder(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 30), // שוליים
                itemCount: blocks.length, // מספר הבלוקים
                itemBuilder: (context, i) => blocks[i].build(context, cs), // בלוק אחר בלוק — גלילה חלקה גם במסמך ארוך
              ),
            );
          },
        ),
      ),
    );
  }
}

/// בלוק אחד במסמך (כותרת / פסקה / פריט רשימה / טבלה / ציטוט / קו מפריד)
abstract class GuideBlock {
  Widget build(BuildContext context, ColorScheme cs); // ציור הבלוק
}

/// מפַרש Markdown מינימלי — בדיוק מה שהמדריך משתמש בו: #/##/###, פסקאות, "- " ו-"1. " (כולל הזחה),
/// טבלאות "|", ציטוט ">", "---", ו-**מודגש** / `קוד` / *נטוי* בתוך שורה
class MarkdownLite {
  static List<GuideBlock> parse(String src) {
    final lines = src.replaceAll('\r\n', '\n').split('\n'); // שורות (גם קובץ Windows)
    final out = <GuideBlock>[]; // התוצאה
    final para = <String>[]; // שורות של פסקה שנאספת
    void flushPara() { if (para.isNotEmpty) { out.add(_Para(para.join(' '))); para.clear(); } } // סוגר פסקה פתוחה
    var i = 0; // השורה הנוכחית
    while (i < lines.length) {
      final raw = lines[i]; final t = raw.trim(); // השורה, ובלי רווחים בקצוות
      if (t.isEmpty) { flushPara(); i++; continue; } // שורה ריקה — סוף פסקה
      final h = RegExp(r'^(#{1,4})\s+(.*)$').firstMatch(t); // כותרת
      if (h != null) { flushPara(); out.add(_Heading(h.group(1)!.length, h.group(2)!)); i++; continue; }
      if (RegExp(r'^-{3,}$').hasMatch(t)) { flushPara(); out.add(_Rule()); i++; continue; } // קו מפריד
      if (t.startsWith('|')) { // טבלה — כל השורות הרצופות שמתחילות ב-|
        flushPara(); final rows = <List<String>>[]; // השורות
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          final r = lines[i].trim(); // שורת טבלה
          final cells = r.substring(1, r.endsWith('|') ? r.length - 1 : r.length).split('|').map((c) => c.trim()).toList(); // התאים
          if (!cells.every((c) => RegExp(r'^:?-{2,}:?$').hasMatch(c))) rows.add(cells); // מדלג על שורת ההפרדה |---|
          i++;
        }
        if (rows.isNotEmpty) out.add(_Table(rows)); // הטבלה
        continue;
      }
      if (t.startsWith('>')) { // ציטוט — שורות רצופות שמתחילות ב->
        flushPara(); final q = <String>[]; // הטקסט
        while (i < lines.length && lines[i].trim().startsWith('>')) { q.add(lines[i].trim().substring(1).trim()); i++; }
        out.add(_Quote(q.join(' '))); continue;
      }
      final li = RegExp(r'^(\s*)([-*]|\d+\.)\s+(.*)$').firstMatch(raw); // פריט רשימה (עם הזחה)
      if (li != null) {
        flushPara(); final indent = li.group(1)!.replaceAll('\t', '    ').length ~/ 2; // רמת ההזחה (2 רווחים = רמה)
        final marker = li.group(2)!; var text = li.group(3)!; i++; // הסימן והטקסט
        while (i < lines.length) { // שורות המשך של אותו פריט (מוזחות, לא פריט חדש ולא ריקות)
          final nx = lines[i]; if (nx.trim().isEmpty || RegExp(r'^\s*([-*]|\d+\.)\s+').hasMatch(nx) || nx.trim().startsWith('|') || !nx.startsWith(' ')) break;
          text += ' ${nx.trim()}'; i++;
        }
        out.add(_Item(marker == '-' || marker == '*' ? '•' : marker, text, indent.clamp(0, 4))); continue;
      }
      if (raw.startsWith('   ') && out.isNotEmpty && out.last is _Item && para.isEmpty) { // פסקה מוזחת אחרי פריט — שייכת לפריט
        final last = out.last as _Item; out[out.length - 1] = _Item(last.marker, '${last.text}\n$t', last.indent); i++; continue;
      }
      para.add(t); i++; // שורת טקסט רגילה — לפסקה
    }
    flushPara(); // פסקה אחרונה
    return out;
  }

  /// עיצוב בתוך שורה: **מודגש**, `קוד`, *נטוי*
  static TextSpan inline(String s, TextStyle base, ColorScheme cs) {
    final spans = <InlineSpan>[]; // החלקים
    final re = RegExp(r'\*\*(.+?)\*\*|`([^`]+)`|\*([^*\s][^*]*?)\*'); // שלושת הסוגים
    var pos = 0; // המיקום הנוכחי
    for (final m in re.allMatches(s)) {
      if (m.start > pos) spans.add(TextSpan(text: s.substring(pos, m.start))); // טקסט רגיל לפני
      if (m.group(1) != null) {
        spans.add(TextSpan(text: m.group(1), style: const TextStyle(fontWeight: FontWeight.bold))); // מודגש
      } else if (m.group(2) != null) {
        spans.add(TextSpan(text: m.group(2), style: TextStyle(fontFamily: 'monospace', backgroundColor: cs.surfaceContainerHighest))); // קוד
      } else {
        spans.add(TextSpan(text: m.group(3), style: const TextStyle(fontStyle: FontStyle.italic))); // נטוי
      }
      pos = m.end; // ממשיכים אחרי
    }
    if (pos < s.length) spans.add(TextSpan(text: s.substring(pos))); // שארית
    return TextSpan(style: base, children: spans); // השורה המעוצבת
  }
}

class _Heading extends GuideBlock {
  _Heading(this.level, this.text);
  final int level; final String text; // רמה וטקסט
  @override
  Widget build(BuildContext context, ColorScheme cs) {
    final size = [0.0, 21.0, 17.0, 14.5, 13.0][level]; // גודל לפי רמה
    return Padding(
      padding: EdgeInsets.only(top: level == 1 ? 4 : 14, bottom: 6), // רווח מעל כותרת
      child: Text.rich(MarkdownLite.inline(text, TextStyle(fontSize: size, fontWeight: FontWeight.bold, color: level <= 2 ? cs.primary : cs.onSurface), cs)),
    );
  }
}

class _Para extends GuideBlock {
  _Para(this.text);
  final String text; // הטקסט
  @override
  Widget build(BuildContext context, ColorScheme cs) => Padding(
        padding: const EdgeInsets.only(bottom: 8), // רווח אחרי פסקה
        child: Text.rich(MarkdownLite.inline(text, TextStyle(fontSize: 13, height: 1.45, color: cs.onSurface), cs)),
      );
}

class _Item extends GuideBlock {
  _Item(this.marker, this.text, this.indent);
  final String marker, text; final int indent; // סימן, טקסט, הזחה
  @override
  Widget build(BuildContext context, ColorScheme cs) => Padding(
        padding: EdgeInsetsDirectional.only(start: 6.0 + indent * 16, bottom: 4), // הזחה לפי רמה
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: marker == '•' ? 14 : 22, child: Text(marker, style: TextStyle(fontSize: 13, height: 1.45, color: cs.primary))), // הסימן
          Expanded(child: Text.rich(MarkdownLite.inline(text, TextStyle(fontSize: 13, height: 1.45, color: cs.onSurface), cs))), // הטקסט
        ]),
      );
}

class _Quote extends GuideBlock {
  _Quote(this.text);
  final String text; // הטקסט
  @override
  Widget build(BuildContext context, ColorScheme cs) => Container(
        margin: const EdgeInsets.only(bottom: 10), padding: const EdgeInsets.all(10), // ריווח
        decoration: BoxDecoration(color: cs.secondaryContainer, borderRadius: BorderRadius.circular(6)), // רקע מודגש
        child: Text.rich(MarkdownLite.inline(text, TextStyle(fontSize: 12.5, height: 1.4, color: cs.onSecondaryContainer), cs)),
      );
}

class _Rule extends GuideBlock {
  @override
  Widget build(BuildContext context, ColorScheme cs) => const Divider(height: 20); // קו מפריד
}

class _Table extends GuideBlock {
  _Table(this.rows);
  final List<List<String>> rows; // השורה הראשונה = כותרות
  @override
  Widget build(BuildContext context, ColorScheme cs) {
    final cols = rows.map((r) => r.length).reduce((a, b) => a > b ? a : b); // מספר העמודות
    TableRow row(List<String> cells, bool head) => TableRow( // שורה אחת
          decoration: head ? BoxDecoration(color: cs.surfaceContainerHighest) : null, // רקע לכותרות
          children: [
            for (var c = 0; c < cols; c++)
              Padding(
                padding: const EdgeInsets.all(6), // ריווח בתא
                child: Text.rich(MarkdownLite.inline(c < cells.length ? cells[c] : '',
                    TextStyle(fontSize: 12, height: 1.35, fontWeight: head ? FontWeight.bold : FontWeight.normal, color: cs.onSurface), cs)),
              ),
          ],
        );
    return Padding(
      padding: const EdgeInsets.only(bottom: 10), // רווח אחרי טבלה
      child: Table(
        border: TableBorder.all(color: cs.outlineVariant), // מסגרת
        defaultVerticalAlignment: TableCellVerticalAlignment.top, // יישור למעלה
        columnWidths: cols == 2 ? const {0: FlexColumnWidth(1), 1: FlexColumnWidth(1.4)} : null, // שתי עמודות: לעמודת הפעולה יותר מקום
        children: [for (var r = 0; r < rows.length; r++) row(rows[r], r == 0)], // כותרות + שורות
      ),
    );
  }
}
