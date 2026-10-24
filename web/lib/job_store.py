# -*- coding: utf-8 -*-
"""
job_store.py — מחליף את _radial_jobs/_radar_jobs (dict בזיכרון-תהליך) ב-Redis (Upstash,
דרך Vercel Marketplace) — נדרש כי ב-Vercel אין הבטחת state בין invocations serverless
נפרדות (ר' MAPS-GUI_SRS.md §3.24/§3.25 להסבר המלא).

שימוש: get_job/set_job/delete_job על מצב job שלם (dict), כל קריאה היא GET/SET יחיד
ל-Redis (לא פעולות חלקיות) — כי כל "progress step" (batch בודד) נעשה בתוך invocation
אחת שגם קוראת וגם כותבת את המצב המלא, אין race condition בין כמה writers בו-זמנית
לאותו job_id (המשתמש לא שולח שתי בקשות /status מקבילות לאותו job בפועל).
"""

import json
import os

_TTL_SEC = 1800  # 30 דקות — job ישן מספיק מתפוגג לבד, מחליף את _cleanup_old_radial_jobs הידני

_client = None  # Upstash Redis client — אתחול עצל (lazy), רק כש-get_job/set_job נקראים לראשונה


def _get_client():
    """מאתחל את חיבור ה-Redis פעם אחת לכל תהליך. זורק RuntimeError ברור אם משתני הסביבה
    (שמוזרקים אוטומטית ע"י Vercel בהתקנת אינטגרציית Upstash) לא מוגדרים — למשל בפיתוח
    מקומי בלי Upstash מוגדר; הקורא (route ב-weather.py) צריך לתפוס את זה ולהחזיר שגיאה
    ברורה למשתמש ("שלב 2 של גרסת ה-web עדיין דורש הגדרת Redis"), לא לקרוס בלי הסבר."""
    global _client
    if _client is not None:
        return _client
    url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    if not url or not token:
        raise RuntimeError(
            "Redis לא מוגדר (חסר UPSTASH_REDIS_REST_URL/TOKEN) — התקן את אינטגרציית "
            "Upstash דרך Vercel Marketplace כדי שרדיוס-ראייה/מכ\"ם-דופלר/עמדות-שמורות יעבדו."
        )
    from upstash_redis import Redis  # ייבוא עצל — לא נדרש בכלל אם אף route לא משתמש ב-Redis בפועל
    _client = Redis(url=url, token=token)
    return _client


def set_job(job_id, state):
    """שומר/מחליף את כל מצב ה-job (dict) כ-JSON יחיד, עם TTL."""
    _get_client().set(f"job:{job_id}", json.dumps(state, ensure_ascii=False), ex=_TTL_SEC)


def get_job(job_id):
    """קורא את מצב ה-job. מחזיר None אם לא קיים/פג תוקף — הקורא מתרגם את זה ל-404."""
    raw = _get_client().get(f"job:{job_id}")
    return json.loads(raw) if raw else None


def delete_job(job_id):
    """מוחק job מפורשות — לא חובה (TTL כבר מנקה לבד), אך שימושי ב-/cancel לניקוי מיידי."""
    _get_client().delete(f"job:{job_id}")
