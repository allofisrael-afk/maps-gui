"""
מודול משותף למדידת מטריקות קריאות API בשרתי ה-Flask (geo/weather/flight).
כל שרת קורא ל-register_metrics(app) מיד לאחר יצירת ה-app, ומקבל אוטומטית
נתיב GET /metrics המחזיר ספירת קריאות/שגיאות/זמן תגובה ממוצע לכל endpoint —
נצרך ע"י דשבורד התהליכים ב-main.py.
"""
import time  # מדידת זמני תגובה ו-uptime
from collections import defaultdict  # יוצר אוטומטית רשומת סטטיסטיקה ריקה לכל endpoint חדש
from datetime import datetime  # חותמת שעה קריאה לקריאה האחרונה

from flask import request, jsonify  # גישה לבקשה הנוכחית והחזרת JSON

# מילון גלובלי: {נתיב endpoint: {count, errors, total_ms, last_status, last_call}} — משותף לכל הבקשות של השרת
_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "last_status": None, "last_call": None})
_start_time = time.time()  # זמן עליית השרת — לחישוב uptime_sec


def register_metrics(app):
    @app.before_request  # רץ לפני כל בקשה נכנסת
    def _metrics_start():
        request._metrics_start = time.perf_counter()  # שמירת זמן ההתחלה על אובייקט הבקשה עצמו

    @app.after_request  # רץ אחרי שהבקשה טופלה, לפני שהתגובה נשלחת
    def _metrics_end(response):
        if request.path != "/metrics":  # לא סופרים קריאות ל-/metrics עצמו — היה מנפח את הסטטיסטיקה מלחיצות דשבורד חוזרות
            elapsed_ms = (time.perf_counter() - getattr(request, "_metrics_start", time.perf_counter())) * 1000  # זמן טיפול בבקשה במילישניות
            s = _stats[request.path]  # שליפת/יצירת רשומת הסטטיסטיקה של הנתיב הזה
            s["count"] += 1  # ספירת קריאה נוספת
            if response.status_code >= 400:  # קוד שגיאה HTTP
                s["errors"] += 1  # ספירת שגיאה נוספת
            s["total_ms"] += elapsed_ms  # מצטבר לחישוב ממוצע בהמשך
            s["last_status"] = response.status_code  # קוד הסטטוס האחרון שהוחזר
            s["last_call"] = datetime.now().strftime("%H:%M:%S")  # שעת הקריאה האחרונה, לתצוגה בדשבורד
        return response  # חובה להחזיר את התגובה כדי שהיא תישלח ללקוח

    @app.route("/metrics")  # נתיב שנצרך ע"י MetricsWorker בדשבורד התהליכים
    def _metrics():
        return jsonify({
            "uptime_sec": round(time.time() - _start_time, 1),  # כמה זמן השרת רץ ברציפות
            "endpoints": {
                ep: {
                    "count": s["count"],  # סה"כ קריאות לנתיב הזה
                    "errors": s["errors"],  # מתוכן כמה החזירו שגיאה
                    "avg_ms": round(s["total_ms"] / s["count"], 1) if s["count"] else 0,  # ממוצע זמן תגובה — מגן מחלוקה באפס
                    "last_status": s["last_status"],  # קוד הסטטוס האחרון
                    "last_call": s["last_call"],  # שעת הקריאה האחרונה
                }
                for ep, s in _stats.items()  # בונה מילון תוצאה לכל endpoint שנצפה עד כה
            },
        })
