# -*- coding: utf-8 -*-
"""
stations_store.py — מחליף את _load_stations/_save_stations (saved_stations.json על דיסק)
ב-Redis (Upstash) — מחליף קובץ שטוח יחיד במפתח Redis יחיד לכל tool, בדיוק באותו מבנה-
נתונים (list של {name, params}) — ר' MAPS-GUI_SRS.md §3.25. משתמש באותו client-אתחול-
עצל כמו job_store.py (אותו Redis instance, שני מודולים נפרדים לבהירות-תפקיד בלבד).
"""

import json
import os

_MAX_PER_TOOL = 20  # זהה לתקרה בדסקטופ (_STATIONS_MAX_PER_TOOL)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    url = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    if not url or not token:
        raise RuntimeError(
            "Redis לא מוגדר (חסר UPSTASH_REDIS_REST_URL/TOKEN) — התקן את אינטגרציית "
            "Upstash דרך Vercel Marketplace כדי ש'עמדות שמורות'/'מסלול מותאם' יישמרו."
        )
    from upstash_redis import Redis
    _client = Redis(url=url, token=token)
    return _client


def list_stations(tool):
    """מחזיר [{name, params}, ...] לכלי נתון — [] אם אין עדיין כלום."""
    raw = _get_client().get(f"stations:{tool}")
    return json.loads(raw) if raw else []


def save_station(tool, name, params):
    """שומר/מחליף עמדה תחת שם — זהה בהתנהגותו ל-_save_stations בדסקטופ (מחליף כפילות, חותך ישן-ביותר בחריגה מהתקרה)."""
    stations = list_stations(tool)
    stations = [s for s in stations if s.get('name') != name]
    stations.append({'name': name, 'params': params})
    if len(stations) > _MAX_PER_TOOL:
        stations = stations[-_MAX_PER_TOOL:]  # חותך את הישנות ביותר (תחילת הרשימה), שומר את ה-20 האחרונות
    _get_client().set(f"stations:{tool}", json.dumps(stations, ensure_ascii=False))


def delete_station(tool, name):
    """מוחק עמדה לפי שם — מתעלם בשקט אם לא נמצאה, זהה להתנהגות הדסקטופ."""
    stations = [s for s in list_stations(tool) if s.get('name') != name]
    _get_client().set(f"stations:{tool}", json.dumps(stations, ensure_ascii=False))
