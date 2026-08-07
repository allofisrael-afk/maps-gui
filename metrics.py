"""
מודול משותף למדידת מטריקות קריאות API בשרתי ה-Flask (geo/weather/flight).
כל שרת קורא ל-register_metrics(app) מיד לאחר יצירת ה-app, ומקבל אוטומטית
נתיב GET /metrics המחזיר ספירת קריאות/שגיאות/זמן תגובה ממוצע לכל endpoint —
נצרך ע"י דשבורד התהליכים ב-main.py.
"""
import time
from collections import defaultdict
from datetime import datetime

from flask import request, jsonify

_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "last_status": None, "last_call": None})
_start_time = time.time()


def register_metrics(app):
    @app.before_request
    def _metrics_start():
        request._metrics_start = time.perf_counter()

    @app.after_request
    def _metrics_end(response):
        if request.path != "/metrics":
            elapsed_ms = (time.perf_counter() - getattr(request, "_metrics_start", time.perf_counter())) * 1000
            s = _stats[request.path]
            s["count"] += 1
            if response.status_code >= 400:
                s["errors"] += 1
            s["total_ms"] += elapsed_ms
            s["last_status"] = response.status_code
            s["last_call"] = datetime.now().strftime("%H:%M:%S")
        return response

    @app.route("/metrics")
    def _metrics():
        return jsonify({
            "uptime_sec": round(time.time() - _start_time, 1),
            "endpoints": {
                ep: {
                    "count": s["count"],
                    "errors": s["errors"],
                    "avg_ms": round(s["total_ms"] / s["count"], 1) if s["count"] else 0,
                    "last_status": s["last_status"],
                    "last_call": s["last_call"],
                }
                for ep, s in _stats.items()
            },
        })
