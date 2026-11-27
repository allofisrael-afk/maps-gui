# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
תשתית משותפת לשלושת שרתי ה-Flask (weather_server.py, geo_server.py, flight_server.py) —
מאחדת קוד שהיה כפול בכל אחד מהם בנפרד: טעינת .env, הגדרת logging משותף לקובץ אחד
(app_combined.log), יצירת מופע Flask, אפשור CORS, וחיבור נתיב /metrics המשותף
(ר' metrics.py). כל שרת עדיין מגדיר בעצמו את הנתיבים, הפורט, ואת ה-app.run() שלו —
זו רק ההכנה המשותפת שקדמה לזה בכל שלושת הקבצים.
"""

import logging
import os  # T4 (F-031): מקורות CORS נוספים ממשתנה סביבה (לפיתוח בלבד)

from dotenv import load_dotenv
from flask import Flask, jsonify, request  # T5: before_request שבודק את טוקן ההפעלה
from flask_cors import CORS

from app_token import HEADER as _TOKEN_HEADER, check_request as _check_app_token  # T5 (F-031): טוקן לכל הפעלה
from metrics import register_metrics

_log_configured = False  # מונע קריאה כפולה ל-basicConfig אם create_app נקרא יותר מפעם אחת בתהליך אחד


def create_app(import_name):
    """
    יוצר מופע Flask מוכן לשימוש: .env טעון, logging מוגדר (פעם אחת בלבד לכל תהליך),
    CORS מאופשר, ו-/metrics מחובר. import_name צריך להיות __name__ של הקורא — בדיוק
    כמו Flask(__name__) הרגיל — כדי ש-Flask יזהה נכון את מודול השורש (לא server_common).
    """
    global _log_configured
    load_dotenv()
    if not _log_configured:
        logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')
        _log_configured = True
    app = Flask(import_name)
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # T8 (F-042): גוף בקשה עד 8MB (מסלול של 6,000 נקודות ≈ 0.5MB) — מעבר לזה 413 לפני פענוח
    CORS(app, origins=_cors_origins(), allow_headers=["Content-Type", _TOKEN_HEADER])  # T4 (F-031): רק מקור הממשק (map.html נטען כ-file://), לא כל אתר
    app.before_request(_require_app_token)  # T5 (F-031): כל בקשה חייבת את טוקן ההפעלה כש-main.py הגדיר אותו
    register_metrics(app)  # מוסיף נתיב GET /metrics למעקב הדשבורד
    return app


def _cors_origins():  # T4 (F-031): רשימת המקורות שמותר להם לקרוא לשרת מדפדפן
    extra = [o.strip() for o in os.environ.get("MAPS_GUI_CORS_ORIGINS", "").split(",") if o.strip()]  # T4: הרחבה מפורשת לפיתוח, למשל http://localhost:8000
    return ["file://", "null"] + extra  # T4: דף מקומי — QtWebEngine שולח "Origin: file://" (נמדד ב-e2e), דפדפנים אחרים "null"; אתרים זרים לא מקבלים Access-Control-Allow-Origin


def _require_app_token():  # T5 (F-031): before_request — דוחה בקשה בלי טוקן תקין
    err = _check_app_token(request)  # T5: None = מותר
    if err:  # T5: אין טוקן או טוקן שגוי
        return jsonify({"error": err}), 403  # T5: Flask מחזיר את זה במקום להריץ את הנתיב
    return None  # T5: ממשיכים לנתיב
