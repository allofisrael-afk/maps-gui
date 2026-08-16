# -*- coding: utf-8 -*-
"""
תשתית משותפת לשלושת שרתי ה-Flask (weather_server.py, geo_server.py, flight_server.py) —
מאחדת קוד שהיה כפול בכל אחד מהם בנפרד: טעינת .env, הגדרת logging משותף לקובץ אחד
(app_combined.log), יצירת מופע Flask, אפשור CORS, וחיבור נתיב /metrics המשותף
(ר' metrics.py). כל שרת עדיין מגדיר בעצמו את הנתיבים, הפורט, ואת ה-app.run() שלו —
זו רק ההכנה המשותפת שקדמה לזה בכל שלושת הקבצים.
"""

import logging

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

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
    CORS(app)
    register_metrics(app)  # מוסיף נתיב GET /metrics למעקב הדשבורד
    return app
