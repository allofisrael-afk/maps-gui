// נקודה בודדת ב"מסלול טיסה מותאם" (הכלי שהמשתמש מזין בו ידנית רשימת נקודות) —
// גובה אופציונלי (nullable), בשונה מ-FlightTrailPoint שמגיע ממקור חיצוני (FR24/OpenSky).
class RoutePoint {
  const RoutePoint({required this.lat, required this.lng, this.altM});

  final double lat;
  final double lng;
  final double? altM; // גובה במטרים — null אם המשתמש לא הזין גובה לנקודה הזו
}
