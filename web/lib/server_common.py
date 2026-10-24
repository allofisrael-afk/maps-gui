# -*- coding: utf-8 -*-
"""
תשתית משותפת לגרסת ה-Web (Vercel) — מותאמת מ-server_common.py המקורי (Desktop).
שינויים מהמקור (ר' MAPS-GUI_SRS.md §3.24 להסבר המלא):
1. CORS מוגבל לדומיין המותר בלבד (ALLOWED_ORIGIN), לא פתוח-לכל (*) כמו בדסקטופ —
   בדסקטופ זה בטוח כי השרת נגיש רק מ-localhost; בפריסה ציבורית זה לא בטוח.
2. logging ל-stdout, לא לקובץ מקומי — ב-Vercel מערכת הקבצים לקריאה-בלבד (חוץ מ-/tmp
   האפמרי), ו-Vercel כבר אוסף stdout/stderr כלוגים של הפונקציה בעצמו.
3. אין register_metrics — /metrics הוא פיצ'ר-עזר לדשבורד Qt של הדסקטופ, לא רלוונטי ל-web.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

_log_configured = False  # מונע קריאה כפולה ל-basicConfig אם create_app נקרא יותר מפעם אחת בתהליך אחד


def create_app(import_name):
    """
    יוצר מופע Flask מוכן לשימוש עבור web/api/*.py: .env טעון, logging ל-stdout מוגדר
    (פעם אחת בלבד לכל תהליך), ו-CORS מוגבל ל-ALLOWED_ORIGIN בלבד (משתנה סביבה ב-Vercel
    Dashboard). אם ALLOWED_ORIGIN לא מוגדר (למשל בפיתוח מקומי) — נופל חזרה לפתוח-לכל,
    עם אזהרה בלוג, כדי לא לחסום פיתוח/בדיקות לפני שהדומיין הסופי נקבע.
    """
    global _log_configured
    load_dotenv()
    if not _log_configured:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(message)s')
        _log_configured = True
    app = Flask(import_name)
    allowed_origin = os.getenv("ALLOWED_ORIGIN")
    if allowed_origin:
        CORS(app, origins=[allowed_origin])
    else:
        logging.warning("ALLOWED_ORIGIN לא מוגדר — CORS פתוח-לכל זמנית (תקין לפיתוח בלבד, לא לפרודקשן)")
        CORS(app)
    return app
