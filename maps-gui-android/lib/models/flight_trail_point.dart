// נקודת מסלול טיסה בודדת עם טלמטריה מלאה (גובה/מהירות/כיוון) — לשימוש בהערכת מסלול טיסה
// מול מכ"ם-דופלר (ר' ApiService.fetchRouteEvaluation). שונה מ-FlightData.path הקיים (רק
// List<LatLng>, בלי טלמטריה) — נשמר כשדה נוסף לצדו, לא מחליף אותו, כדי לא לגעת בכל מקום
// שכבר קורא FlightData.path כרשימת LatLng פשוטה (ציור הקו, fitBounds וכו').
class FlightTrailPoint {
  const FlightTrailPoint({required this.lat, required this.lng, this.altFt, this.spdKt, this.hdDeg});

  final double lat;
  final double lng;
  final double? altFt; // גובה, רגל MSL — null אם המקור (OpenSky וכו') לא סיפק גובה לנקודה הזו
  final double? spdKt;  // מהירות קרקע, קשר — null אם לא זמין
  final double? hdDeg;  // כיוון תנועה, מעלות — null אם לא זמין (0 הוא כיוון-צפון תקף, אסור לבלבל עם "אין נתון")
}
