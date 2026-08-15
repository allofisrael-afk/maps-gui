// סיווג NOTAM ל-7 קטגוריות — נגזר מאותו מקור כמו notam_categories.py (השווה בעדכון עתידי).
// בהשראת מסך השכבות של אפליקציית DronesIL הרשמית — ר' notam_categories.py להסבר המלא.

class NotamCategory {
  const NotamCategory({required this.id, required this.label, required this.color});
  final String id;
  final String label;
  final int color; // 0xAARRGGBB — נבנה מ-Color בשימוש (ר' api_service.dart/map_screen.dart)
}

// הצבעים פרושים על גלגל הגוונים (לא פסטליים קרובים) כדי שיהיו מובחנים בבירור זה מזה
// וגם בולטים על רקע המפה הכהה — ר' אותה הערה ב-notam_categories.py
const List<NotamCategory> kNotamCategories = [
  NotamCategory(id: 'prohibited', label: 'אזורים אסורים לטיסה', color: 0xFFE63946),
  NotamCategory(id: 'restricted', label: 'אזורים מוגבלים לטיסה', color: 0xFFF4A261),
  NotamCategory(id: 'danger', label: 'אזורים מסוכנים לטיסה', color: 0xFFE9C46A),
  NotamCategory(id: 'uas', label: 'אזורי כלי טיס בלתי מאויש', color: 0xFF9B5DE5),
  NotamCategory(id: 'heliport_control', label: 'אזורי פיקוח מנחתים', color: 0xFF00B4D8),
  NotamCategory(id: 'helicopter', label: 'אזורי מסוקים', color: 0xFF2A9D8F),
  NotamCategory(id: 'airport_control', label: 'אזורי פיקוח שדות תעופה', color: 0xFF4361EE),
];

// מילות מפתח לכל קטגוריה — זהות בדיוק ל-notam_categories.py (השווה בעדכון עתידי)
const Map<String, List<String>> _categoryKeywords = {
  'prohibited': ['PROHIBITED'],
  'restricted': ['RESTRICTED'],
  'danger': ['DANGER'],
  'uas': ['UAS', 'UAV'],
  'heliport_control': ['HELIPORT', 'HELIPAD'],
  'helicopter': ['HELICOPTER'],
  'airport_control': ['AERODROME', 'AIRPORT', 'CTR', 'ATZ'],
};

// regex יחיד לכל קטגוריה, \b כדי שלא יתפוס תת-מחרוזת בתוך מילה אחרת (למשל AIRPORT בתוך SEAPORT)
final Map<String, RegExp> _categoryPatterns = {
  for (final entry in _categoryKeywords.entries)
    entry.key: RegExp(
      r'\b(?:' + entry.value.map(RegExp.escape).join('|') + r')\b',
      caseSensitive: false,
    ),
};

// קטגוריות "משתמעות" — זהה בדיוק ל-_IMPLIED_CATEGORIES ב-notam_categories.py (השווה בעדכון עתידי).
// NOTAM שמזכיר CTR/ATZ/AERODROME הוא תמיד גם "מוגבל" (לא "אסור" — זו קטגוריה חמורה יותר),
// גם כשהמילה "RESTRICTED" לא מופיעה במפורש — טיסת כטב"ם במרחב מבוקר דורשת אישור נת"א.
const Map<String, List<String>> _impliedCategories = {
  'airport_control': ['restricted'],
};

/// מחזיר רשימת id-ים של כל הקטגוריות שהטקסט תואם, כולל קטגוריות משתמעות (עשוי להיות יותר מאחת, או ריק)
List<String> classifyNotam(String text) {
  final matched = _categoryPatterns.entries
      .where((e) => e.value.hasMatch(text))
      .map((e) => e.key)
      .toList();
  for (final catId in List<String>.from(matched)) {
    for (final impliedId in _impliedCategories[catId] ?? const <String>[]) {
      if (!matched.contains(impliedId)) matched.add(impliedId);
    }
  }
  return matched;
}
