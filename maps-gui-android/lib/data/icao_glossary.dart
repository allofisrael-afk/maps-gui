// מילון קיצורי ICAO/NOTAM נפוצים + "תרגום גס" לעברית.
// השווה מול icao_glossary.py — לשמור מסונכרן ידנית בעת עדכון מילון הביטויים.
//
// חשוב: זהו gloss מבוסס-החלפת-ביטויים על טקסט חופשי, לא תרגום מובנה/דקדוקי.
// אזהרת בטיחות: התרגום העברי חייב תמיד להיות מוצג לצד הטקסט האנגלי המקורי,
// לעולם לא במקומו — תרגום שגוי/חלקי עלול להטעות בהקשר בטיחות טיסה.

// רשימת (ביטוי, עברית) — ביטויים רב-מיליים מוזנים כאן, וממוינים בזמן ריצה
// מהארוך לקצר כדי ש"UP TO"/"CENTERED ON" ייתפסו לפני "UP"/"TO"/"RADIUS" בנפרד.
const List<MapEntry<String, String>> _icaoAbbreviations = [
  // סטטוס/מצב
  MapEntry('CLSD', 'סגור'),
  MapEntry('ACT', 'פעיל'),
  MapEntry('PERM', 'קבוע'),
  MapEntry('TEMPO', 'זמני'),
  MapEntry('U/S', 'לא תקין'),
  MapEntry('WIP', 'עבודות בביצוע'),
  MapEntry('WILL TAKE PLACE', 'תתקיים'),

  // גיאומטריה/מיקום
  MapEntry('RADIUS CENTERED ON', 'רדיוס מרכזו ב'),
  MapEntry('CENTERED ON', 'מרכזו ב'),
  MapEntry('PSN', 'מיקום'),
  MapEntry('WI', 'בתוך'),
  MapEntry('BTN', 'בין'),
  MapEntry('RADIUS', 'רדיוס'),
  MapEntry('RTE', 'מסלול'),
  MapEntry('OBST', 'מכשול'),
  MapEntry('AN AREA', 'אזור'),

  // גובה/ייחוס אנכי
  MapEntry('GND', 'פני הקרקע'),
  MapEntry('SFC', 'פני השטח'),
  MapEntry('AMSL', 'מעל פני הים'),
  MapEntry('AGL', 'מעל פני הקרקע'),
  MapEntry('MSL', 'מעל פני הים'),
  MapEntry('FT', 'רגל'),
  MapEntry('NM', 'מייל ימי'),

  // זמן
  MapEntry('WEF', 'החל מ'),
  MapEntry('FM', 'החל מ'),
  MapEntry('TIL', 'עד'),
  MapEntry('UP TO', 'עד'),
  MapEntry('H24', '24 שעות ביממה'),
  MapEntry('DAILY', 'יומי'),
  MapEntry('SR', 'זריחה'),
  MapEntry('SS', 'שקיעה'),
  MapEntry('EST', 'משוער'),

  // תפעולי
  MapEntry('PPR', 'באישור מראש'),
  MapEntry('O/R', 'לפי בקשה'),
  MapEntry('SKED', 'מתוכנן'),
  MapEntry('EXC', 'למעט'),
  MapEntry('MAX', 'מקסימום'),
  MapEntry('MIN', 'מינימום'),
  MapEntry('APRX', 'בקירוב'),
  MapEntry('NR', 'מספר'),

  // שדה תעופה/מרחב אווירי
  MapEntry('RWY', 'מסלול המראה/נחיתה'),
  MapEntry('TWY', 'מסלול הסעה'),
  MapEntry('ARP', 'נקודת ייחוס שדה'),
  MapEntry('AD', 'שדה תעופה'),
  MapEntry('HEL', 'מסוק'),
  MapEntry('MIL', 'צבאי'),
  MapEntry('CIV', 'אזרחי'),

  // תחומי — כטב"ם
  MapEntry('UAS', 'כטב"ם'),
  MapEntry('UAV', 'כטב"ם'),
];

Map<String, String> get _lookup => {
      for (final e in _icaoAbbreviations) e.key.toUpperCase(): e.value,
    };

final List<MapEntry<String, String>> _sortedAbbreviations =
    List<MapEntry<String, String>>.from(_icaoAbbreviations)
      ..sort((a, b) => b.key.length.compareTo(a.key.length));

final RegExp _abbrRe = RegExp(
  r'\b(' +
      _sortedAbbreviations
          .map((e) => RegExp.escape(e.key))
          .join('|') +
      r')\b',
  caseSensitive: false,
);

/// מחזיר תרגום גס לעברית של טקסט NOTAM — תמיד להציג לצד המקור האנגלי, לא במקומו.
String renderHebrewGloss(String text) {
  if (text.isEmpty) return '';
  final lookup = _lookup;
  return text.replaceAllMapped(
    _abbrRe,
    (m) => lookup[m.group(0)!.toUpperCase()] ?? m.group(0)!,
  );
}
