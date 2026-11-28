# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
radar_track — ליבת כלי "בדיקת מעקב מכ"ם" (כלי שביעי, SRS FR-D-259..). רעיוני/חינוכי — לא מבוסס מערכת אמיתית.

שלב א1: איחוד מסלול (בליסטי/אווירי) למבנה אחד, תכנון דגימת-שטח לפי אזימוט ("פרופיל אופק"),
והערכה פר-נקודה: טווח, אזור-עיוור, חסימת שטח, שדה-ראייה אנכי, סקטור, תקרת מכ"ם ודופלר תלת-ממדי.

stdlib בלבד (כמו mpm_api.py) — נבדק בלי רשת, ומתאים בעתיד גם ל-Chaquopy באנדרואיד.
הפיזיקה של המכ"ם עצמו (משוואת מכ"ם/ריבוד/דופלר/הפסד-סריקה) לא משוכפלת כאן: weather_server.py
מזריק אותה כפונקציות (physics), כך שכלי הדופלר הקיים והכלי הזה משתמשים בדיוק באותן נוסחאות.
"""

import bisect  # חיפוש בינארי בפרופיל האופק המצטבר
import math  # טריגונומטריה וגיאודזיה כדורית

R_EARTH = 6371000.0  # רדיוס כדור הארץ הממוצע (מ') — זהה ל-_haversine_m/_horizon_ratchet ב-weather_server.py
REFRACTION_K = 0.13  # מקדם שבירה אטמוספרי — זהה ל-k ב-_horizon_ratchet, כדי שכל הכלים יראו אותו אופק
DEG_TO_M = R_EARTH * math.pi / 180.0  # מטרים למעלה אחת של קו-רוחב (קירוב כדורי)

MAX_TERRAIN_POINTS = 600  # תקציב תאי-רשת ייחודיים להרצה — Open-Meteo סופר כל נקודה כקריאה (600/דקה, 5000/שעה) — נמדד בבדיקה חיה
MIN_SPACING_M = 100.0  # מרווח דגימה מינימלי לאורך כל קרן — ~רזולוציית ה-DEM של Open-Meteo (90 מ')
SPACING_FRAC_START = 0.01  # מרווח יחסי למרחק (1% מהמרחק ≈ 0.6° זוויתי) — צפוף ליד המכ"ם, דליל רחוק ממנו
SPACING_FRAC_MAX = 0.12  # המרווח היחסי הגדול ביותר שמותר להגיע אליו כדי להיכנס לתקציב
GRID_DEG = 0.001  # רשת קבועה (~100 מ') שאליה "נצמדות" הדגימות — קרניים סמוכות והרצות חוזרות חולקות תאים
AZ_BIN_MIN_DEG = 0.25  # רוחב "פח" אזימוט מינימלי — פרופיל אופק נפרד לכל רבע מעלה
MAX_AZ_BINS = 240  # תקרת פחים — אם המסלול נפרש על זווית רחבה, הפחים מתרחבים כדי לא לחרוג מהתקציב
HORIZON_SELF_GAP_M = 60.0  # לא בודקים מול דגימת-שטח שנמצאת ממש מתחת לנקודה עצמה (פחות מזה מהמרחק שלה)

# ── סטטוסים וסיבות — אותם שמות-סטטוס כמו הערכת המסלול הקיימת (detected/doppler_blind/blocked/out_of_range) ──
STATUS_DETECTED = "detected"  # מזוהה — ירוק
STATUS_DOPPLER_BLIND = "doppler_blind"  # גלוי ובטווח, אבל הדופלר לא מבחין בו — כתום
STATUS_BLOCKED = "blocked"  # חסום (שטח/זווית/סקטור/תקרה/אזור-עיוור) — אדום
STATUS_OUT_OF_RANGE = "out_of_range"  # מעבר לטווח הבדיקה שהוגדר — אפור


# ═══════════════════════════ גיאודזיה כדורית ═══════════════════════════
# שכפול מכוון וקטן של 3 פונקציות מ-weather_server.py (אותו R ואותן נוסחאות) — כדי שהמודול יישאר
# עצמאי (בלי import של Flask/requests) ויהיה ניתן לבדיקה ולהרצה מחוץ לשרת.

def haversine_m(lat1, lon1, lat2, lon2):
    """מרחק על פני הכדור בין שתי נקודות, במטרים."""
    r = math.pi / 180.0  # מעלות -> רדיאנים
    phi1, phi2 = lat1 * r, lat2 * r  # קווי הרוחב ברדיאנים
    dphi, dlam = (lat2 - lat1) * r, (lon2 - lon1) * r  # הפרשי רוחב/אורך ברדיאנים
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2  # נוסחת Haversine
    return R_EARTH * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))  # מרחק קשת במטרים


def bearing_deg(lat1, lon1, lat2, lon2):
    """אזימוט התחלתי (0=צפון, בכיוון השעון) מנקודה 1 לנקודה 2, במעלות [0,360)."""
    r = math.pi / 180.0  # מעלות -> רדיאנים
    phi1, phi2 = lat1 * r, lat2 * r  # קווי הרוחב ברדיאנים
    dlam = (lon2 - lon1) * r  # הפרש האורך ברדיאנים
    x = math.sin(dlam) * math.cos(phi2)  # רכיב מזרחי
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)  # רכיב צפוני
    return math.degrees(math.atan2(x, y)) % 360.0  # נרמול ל-[0,360)


def destination_point(lat, lon, brg_deg, distance_m):
    """נקודת יעד ממקור, לפי אזימוט ומרחק (בעיה גיאודטית ישירה, קירוב כדורי)."""
    if distance_m <= 0:  # מרחק אפס — היעד הוא המקור
        return lat, lon  # בלי חישוב
    r = math.pi / 180.0  # מעלות -> רדיאנים
    phi1, lam1, theta = lat * r, lon * r, brg_deg * r  # מקור ואזימוט ברדיאנים
    delta = distance_m / R_EARTH  # מרחק זוויתי
    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))  # רוחב היעד
    lam2 = lam1 + math.atan2(math.sin(theta) * math.sin(delta) * math.cos(phi1),
                             math.cos(delta) - math.sin(phi1) * math.sin(phi2))  # אורך היעד
    return phi2 / r, (lam2 / r + 540.0) % 360.0 - 180.0  # מעלות, אורך מנורמל ל-[-180,180]


def curvature_drop_m(ground_dist_m):
    """ירידת קו-הראייה בגלל עקמומיות כדור הארץ פחות רפרקציה — אותה נוסחה כמו _horizon_ratchet."""
    return ground_dist_m * ground_dist_m / (2.0 * R_EARTH) * (1.0 - REFRACTION_K)  # d²/2R·(1-k)


# ═══════════════════════════ איחוד מסלול ═══════════════════════════

def normalize_trajectory(points):
    """
    מאחד כל מקור מסלול למבנה אחד: [{'t','lat','lon','alt','ve','vn','vu','speed'}, ...], ממוין לפי זמן.
    קלט: dict-ים עם 't' (שניות), 'lat', 'lon' (או 'lng'), 'alt_msl' (או 'alt', מטרים מעל פני הים).
    המהירות התלת-ממדית (מזרח/צפון/מעלה, מ'/ש') מחושבת מהפרש נקודות עוקבות (הפרש מרכזי בפנים,
    חד-צדדי בקצוות) — כך שהיא זמינה גם למקורות שלא מספקים מהירות בכלל (CSV, מסלול מצויר).
    נקודות לא תקינות (בלי זמן/מיקום/גובה) מושמטות; זמנים כפולים — נשמרת הראשונה.
    """
    clean = []  # נקודות תקינות בלבד
    for p in points or []:  # עובר על כל נקודת קלט
        try:  # כל שדה חסר/לא-מספרי פוסל את הנקודה, לא את כל המסלול
            t = float(p["t"])  # זמן מתחילת המסלול, שניות
            lat = float(p["lat"])  # קו רוחב
            lon = float(p["lon"] if p.get("lon") is not None else p["lng"])  # קו אורך — תומך גם ב-'lng' (פורמט Leaflet/FR24)
            alt = float(p["alt_msl"] if p.get("alt_msl") is not None else p["alt"])  # גובה מעל פני הים, מטרים
        except (KeyError, TypeError, ValueError):  # שדה חסר או לא מספרי
            continue  # מדלגים על הנקודה
        if not (math.isfinite(t) and math.isfinite(lat) and math.isfinite(lon) and math.isfinite(alt)):  # NaN/אינסוף
            continue  # מדלגים
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):  # T13 (F-044): קואורדינטה מחוץ לטווח — חסרת משמעות, ואסור לשלוח אותה לשירות הגבהים
            continue  # מדלגים כמו על NaN
        clean.append({"t": t, "lat": lat, "lon": lon, "alt": alt})  # נקודה תקינה
    clean.sort(key=lambda q: q["t"])  # סדר כרונולוגי
    uniq = []  # בלי זמנים כפולים (הפרש-זמן אפס היה מחלק באפס בחישוב המהירות)
    for q in clean:  # עובר בסדר הזמן
        if not uniq or q["t"] > uniq[-1]["t"]:  # זמן חדש בלבד
            uniq.append(q)  # נשמר
    n = len(uniq)  # מספר הנקודות הסופי
    for i, q in enumerate(uniq):  # חישוב מהירות לכל נקודה
        if n < 2:  # נקודה בודדת — אין ממה לגזור מהירות
            q.update(ve=0.0, vn=0.0, vu=0.0, speed=0.0)  # מהירות אפס
            continue  # לנקודה הבאה (אין)
        a = uniq[max(0, i - 1)]  # השכנה הקודמת (או הנקודה עצמה בהתחלה)
        b = uniq[min(n - 1, i + 1)]  # השכנה הבאה (או הנקודה עצמה בסוף)
        dt = b["t"] - a["t"]  # הפרש הזמן ביניהן (חיובי — הזמנים ייחודיים וממוינים)
        lat_mid = math.radians((a["lat"] + b["lat"]) / 2.0)  # רוחב ממוצע — לתיקון אורך-מעלה מזרחית
        dn = (b["lat"] - a["lat"]) * DEG_TO_M  # תזוזה צפונה, מטרים
        de = (b["lon"] - a["lon"]) * DEG_TO_M * math.cos(lat_mid)  # תזוזה מזרחה, מטרים
        du = b["alt"] - a["alt"]  # תזוזה כלפי מעלה, מטרים
        q["ve"], q["vn"], q["vu"] = de / dt, dn / dt, du / dt  # רכיבי המהירות, מ'/ש'
        q["speed"] = math.sqrt(q["ve"] ** 2 + q["vn"] ** 2 + q["vu"] ** 2)  # גודל המהירות
    return uniq  # המסלול המאוחד


def densify_trajectory(points, max_step_s=1.0, max_points=5000):
    """
    שלב א4: מצפף מסלול דליל (טיסת FR24 — נקודה כל עשרות שניות; מסלול מצויר — רק הקודקודים) לנקודה
    לפחות כל max_step_s שניות, באינטרפולציה ליניארית של זמן/רוחב/אורך/גובה. בלי זה לוגיקת המעקב
    (שלב א2) הייתה "רואה" את הנקודה הקרובה בזמן שבפועל רחוקה בעשרות שניות. אם הצפיפות הייתה חורגת
    מ-max_points, הצעד גדל בהתאם. קלט ופלט באותו פורמט כמו normalize_trajectory (t/lat/lon/alt_msl).
    """
    pts = sorted((p for p in points or [] if p.get("t") is not None), key=lambda q: float(q["t"]))  # לפי זמן
    if len(pts) < 2:  # אין מה לצפף
        return list(pts)  # כמו שהוא
    duration = float(pts[-1]["t"]) - float(pts[0]["t"])  # משך המסלול
    step = max(max_step_s, duration / max(1, max_points - 1))  # הצעד בפועל — לא חורגים מהתקרה
    out = []  # התוצאה
    for a, b in zip(pts, pts[1:]):  # כל קטע
        ta, tb = float(a["t"]), float(b["t"])  # זמני הקצוות
        n = max(1, int(math.ceil((tb - ta) / step)))  # כמה תת-קטעים
        for k in range(n):  # בלי הקצה הסופי — הוא יתווסף כתחילת הקטע הבא
            f = k / n  # מיקום יחסי
            out.append({"t": ta + f * (tb - ta),  # זמן
                        "lat": a["lat"] + f * (b["lat"] - a["lat"]),  # רוחב
                        "lon": a["lon"] + f * (b["lon"] - a["lon"]),  # אורך (קטעים קצרים — אינטרפולציה ליניארית מספיקה)
                        "alt_msl": a["alt_msl"] + f * (b["alt_msl"] - a["alt_msl"])})  # גובה
    last = pts[-1]  # הנקודה האחרונה
    out.append({"t": float(last["t"]), "lat": last["lat"], "lon": last["lon"], "alt_msl": last["alt_msl"]})  # נוספת בסוף
    return out  # המסלול המצופף


# ═══════════════════════════ גיאומטריה מכ"ם -> נקודה ═══════════════════════════

def point_geometry(radar, p):
    """
    גיאומטריה מהמכ"ם לנקודה: מרחק קרקעי, אזימוט, גובה יחסי מתוקן-עקמומיות, זווית עילוי וטווח אלכסוני.
    radar: {'lat','lon','h_msl'} — h_msl = גובה הקרקע + גובה האנטנה.
    """
    d = haversine_m(radar["lat"], radar["lon"], p["lat"], p["lon"])  # מרחק קרקעי
    brg = bearing_deg(radar["lat"], radar["lon"], p["lat"], p["lon"]) if d > 0 else 0.0  # אזימוט (0 אם בדיוק מעל המכ"ם)
    dh = p["alt"] - curvature_drop_m(d) - radar["h_msl"]  # גובה הנקודה מעל קו האופקי של האנטנה, אחרי עקמומיות+רפרקציה
    elev = math.degrees(math.atan2(dh, d)) if (d > 0 or dh != 0) else 0.0  # זווית העילוי, מעלות (90 = בדיוק מעל)
    slant = math.hypot(d, dh)  # טווח אלכסוני (קירוב מישורי מקומי — טוב לטווחי הכלי)
    return {"dist_m": d, "bearing_deg": brg, "dh_m": dh, "elev_deg": elev, "slant_m": slant}  # כל הגיאומטריה


def radial_speed_ms(geom, p):
    """מהירות רדיאלית (מתקרב/מתרחק, בערך מוחלט) — היטל וקטור המהירות התלת-ממדי על כיוון קו הראייה.
    בשונה מהערכת המסלול הקיימת (מהירות אופקית בלבד) — כאן גם הרכיב האנכי נכנס, וזה קריטי לפגז."""
    b = math.radians(geom["bearing_deg"])  # אזימוט קו הראייה
    e = math.radians(geom["elev_deg"])  # עילוי קו הראייה
    ux, uy, uz = math.sin(b) * math.cos(e), math.cos(b) * math.cos(e), math.sin(e)  # וקטור יחידה מזרח/צפון/מעלה מהמכ"ם לנקודה
    return abs(p["ve"] * ux + p["vn"] * uy + p["vu"] * uz)  # מכפלה סקלרית = הרכיב הרדיאלי


# ═══════════════════════════ פרופיל אופק לפי אזימוט ═══════════════════════════

def _azimuth_span(bearings):
    """מוצא את התחום הזוויתי המינימלי שמכסה את כל האזימוטים (מטפל במעבר 360->0). מחזיר (התחלה, רוחב)."""
    s = sorted(b % 360.0 for b in bearings)  # אזימוטים ממוינים
    if len(s) == 1:  # אזימוט יחיד
        return s[0], 0.0  # רוחב אפס
    gaps = [(s[(i + 1) % len(s)] - s[i]) % 360.0 for i in range(len(s))]  # פערים בין שכנים, כולל המעבר מהאחרון לראשון
    i_max = max(range(len(gaps)), key=lambda i: gaps[i])  # הפער הגדול ביותר — התחום הוא כל השאר
    start = s[(i_max + 1) % len(s)]  # התחום מתחיל אחרי הפער הגדול
    return start, 360.0 - gaps[i_max]  # (התחלה, רוחב)


def snap_cell(lat, lon):
    """מצמיד מיקום לתא ברשת הקבועה (GRID_DEG). מחזיר (lat, lon) מעוגלים — גם מפתח המטמון בשרת."""
    return (round(round(lat / GRID_DEG) * GRID_DEG, 6), round(round(lon / GRID_DEG) * GRID_DEG, 6))  # מרכז התא


def _ray_distances(max_d, frac):
    """מרחקי הדגימה לאורך קרן: מרווח שגדל עם המרחק (frac·d, לפחות 100 מ') — צפוף ליד המכ"ם, שם
    כל מטר-גובה משנה הרבה בזווית, ודליל רחוק, שם אותה שגיאה זוויתית מכסה יותר מטרים."""
    out, d = [], MIN_SPACING_M  # רשימה, המרחק הראשון
    while d < max_d:  # עד קצה הקרן
        out.append(d)  # הדגימה
        d += max(MIN_SPACING_M, frac * d)  # הצעד הבא
    out.append(max_d)  # תמיד גם בקצה עצמו
    return out  # כל המרחקים


def plan_terrain_samples(radar, traj, range_m, budget=MAX_TERRAIN_POINTS, max_bins=MAX_AZ_BINS):  # 28/11: max_bins — מאזור לאזור (area_track) מבקש פחים של רבע מעלה גם בגזרה רחבה; ברירת המחדל לא השתנתה
    """
    מתכנן את דגימות הגובה: קרן לכל "פח" אזימוט שבו יש נקודות-מסלול בטווח, עד המרחק הרחוק ביותר
    שנדרש באותו פח. במקום קרן נפרדת לכל נקודה (כמו הערכת המסלול הקיימת, כל 5 ק"מ):
      - נקודות באותו כיוון חולקות קרן אחת;
      - המרווח גדל עם המרחק (צפוף ליד המכ"ם);
      - כל דגימה נצמדת לתא ברשת קבועה, ותאים כפולים נשלפים פעם אחת (קרניים סמוכות חופפות ליד המכ"ם);
      - אם התאים הייחודיים חורגים מהתקציב, המרווח היחסי גדל עד שנכנסים.
    מחזיר {'start','bin_deg','n_bins','spacing_frac','bins':{idx:max_d},
            'cells':[(lat,lon),...] ייחודיים, 'samples':[{'bin','d','cell'}]} — cell = אינדקס ב-cells.
    """
    geoms = [(p, point_geometry(radar, p)) for p in traj]  # גיאומטריה לכל נקודה
    need = [(g["bearing_deg"], g["dist_m"]) for _p, g in geoms if 0 < g["dist_m"] <= range_m]  # רק נקודות בטווח, לא בדיוק מעל המכ"ם
    plan = {"start": 0.0, "bin_deg": AZ_BIN_MIN_DEG, "n_bins": 0, "spacing_frac": SPACING_FRAC_START,
            "bins": {}, "cells": [], "samples": []}  # תוכנית ריקה
    if not need:  # אין שום נקודה בטווח — אין צורך בשטח
        return plan  # תוכנית ריקה
    start, span = _azimuth_span([b for b, _d in need])  # התחום הזוויתי שהמסלול תופס מנקודת המכ"ם
    bin_deg = max(AZ_BIN_MIN_DEG, span / max_bins)  # רבע מעלה, או רחב יותר אם התחום רחב מאוד (28/11: תקרת הפחים כפרמטר)
    n_bins = int(span / bin_deg) + 1  # מספר הפחים
    bins = {}  # אינדקס פח -> המרחק הרחוק ביותר שנדרש בו
    for b, d in need:  # כל נקודה בטווח
        idx = min(n_bins - 1, int(((b - start) % 360.0) / bin_deg))  # הפח שלה
        bins[idx] = max(bins.get(idx, 0.0), d)  # מרחק מרבי בפח
    frac = SPACING_FRAC_START  # מתחילים מהצפוף ביותר
    while True:  # מגדילים את המרווח עד שנכנסים לתקציב
        cell_index, cells, samples = {}, [], []  # מיפוי תא->אינדקס, רשימת תאים ייחודיים, דגימות
        for idx in sorted(bins):  # פח אחר פח
            az = (start + (idx + 0.5) * bin_deg) % 360.0  # כיוון מרכז הפח
            for d in _ray_distances(bins[idx], frac):  # הדגימות לאורך הקרן
                lat, lon = destination_point(radar["lat"], radar["lon"], az, d)  # מיקום הדגימה
                key = snap_cell(lat, lon)  # התא שלה
                if key not in cell_index:  # תא חדש
                    cell_index[key] = len(cells)  # אינדקס
                    cells.append(key)  # לשליפה
                samples.append({"bin": idx, "d": d, "cell": cell_index[key]})  # הדגימה מצביעה לתא
        if len(cells) <= budget or frac >= SPACING_FRAC_MAX:  # בתוך התקציב, או הגענו לדליל ביותר
            break  # סיימנו
        frac = min(SPACING_FRAC_MAX, frac * 1.5)  # מרווח גדול יותר ומנסים שוב
    plan.update(start=start, bin_deg=bin_deg, n_bins=n_bins, spacing_frac=frac, bins=bins, cells=cells, samples=samples)  # התוכנית
    return plan  # מוחזרת לשליפת גבהים


def build_horizon_profiles(plan, elevations, radar_h_msl):
    """
    בונה לכל פח פרופיל אופק מצטבר: לכל מרחק d — השיפוע הגבוה ביותר של השטח (מתוקן עקמומיות+רפרקציה)
    מהמכ"ם ועד d. elevations: רשימה מקבילה ל-plan['cells'] (None = נכשל, מדולג).
    מחזיר {bin_idx: (רשימת מרחקים, רשימת שיפוע-מרבי-מצטבר)}.
    """
    per_bin = {}  # פח -> [(d, שיפוע)]
    for s in plan["samples"]:  # כל דגימה
        elev = elevations[s["cell"]]  # הגובה של התא שאליו היא נצמדה
        if elev is None:  # שליפה שנכשלה לתא הזה
            continue  # מדלגים — לא ממציאים שטח
        slope = (elev - curvature_drop_m(s["d"]) - radar_h_msl) / s["d"]  # שיפוע השטח מהאנטנה, כמו bare_angle ב-_horizon_ratchet
        per_bin.setdefault(s["bin"], []).append((s["d"], slope))  # לפח שלה
    profiles = {}  # התוצאה
    for idx, pts in per_bin.items():  # כל פח
        pts.sort()  # לפי מרחק
        ds, cum, best = [], [], -float("inf")  # מרחקים, מקסימום מצטבר, המקסימום עד כה
        for d, slope in pts:  # מהקרוב לרחוק
            best = max(best, slope)  # מעדכן את קו האופק
            ds.append(d)  # המרחק
            cum.append(best)  # האופק עד המרחק הזה
        profiles[idx] = (ds, cum)  # נשמר לפח
    return profiles  # כל הפרופילים


def horizon_slope_before(profiles, plan, brg, dist_m):
    """שיפוע האופק בכיוון brg עד מעט לפני dist_m (בלי הקרקע שממש מתחת לנקודה). None = אין נתוני שטח."""
    if not plan["n_bins"]:  # אין תוכנית שטח בכלל
        return None  # אין נתונים
    idx = min(plan["n_bins"] - 1, int(((brg - plan["start"]) % 360.0) / plan["bin_deg"]))  # הפח של הכיוון
    prof = profiles.get(idx)  # הפרופיל שלו
    if not prof:  # פח בלי דגימות תקינות
        return None  # אין נתונים
    ds, cum = prof  # מרחקים ומקסימום מצטבר
    k = bisect.bisect_left(ds, dist_m - HORIZON_SELF_GAP_M)  # כמה דגימות נמצאות לפני הנקודה (פחות מרווח-עצמי)
    if k == 0:  # הנקודה קרובה מאוד למכ"ם — אין שטח ביניהם
        return -float("inf")  # שום דבר לא חוסם
    return cum[k - 1]  # האופק הגבוה ביותר עד שם


# ═══════════════════════════ הערכה פר-נקודה ═══════════════════════════

def evaluate_points(traj, radar, params, physics, plan, profiles):
    """
    מעריך כל נקודה במסלול מול המכ"ם. סדר הבדיקות קובע את סיבת הכישלון שתוצג (הראשונה שנכשלה):
      1. מעבר לטווח הבדיקה -> out_of_range (אפור)
      2. בתוך אזור-העיוור הקרוב (min_range) -> blocked/min_range
      3. מתחת לאופק השטח (+מרווח רכס) -> blocked/terrain
      4. מחוץ לשדה-הראייה האנכי (נאכף כאן — בשונה מהערכת המסלול הקיימת, FR-D-260) -> blocked/elevation
      5. מחוץ לסקטור של מערך-מופעים -> blocked/sector
      6. מעבר לתקרת המכ"ם (משוואת מכ"ם × ריבוד × הפסד-סריקה) לפי טווח אלכסוני -> blocked/radar_range
      7. דופלר לא מבחין (MDV / מהירות עיוורת) לפי מהירות רדיאלית תלת-ממדית -> doppler_blind
      אחרת -> detected.
    params: הפרמטרים המשותפים של כלי הדופלר (_parse_radar_common_params). physics: dict של פונקציות
    מוזרקות — 'ceiling_m' (מספר), 'lobing'(עילוי)->גורם, 'scan_loss'(אזימוט)->גורם, 'doppler_ok'(מ'/ש')->bool.
    """
    range_m = params["range_km"] * 1000.0  # טווח הבדיקה
    min_range_m = params.get("min_range_km", 0.0) * 1000.0  # אזור-העיוור הקרוב
    margin_slope = math.tan(math.radians(params.get("ridge_margin_deg", 0.0)))  # מרווח ביטחון מעל הרכס
    v_half = params.get("vertical_width_deg", 180.0) / 2.0  # חצי רוחב שדה-הראייה האנכי
    v_lo = params.get("vertical_center_deg", 0.0) - v_half  # גבול תחתון, מעלות
    v_hi = params.get("vertical_center_deg", 0.0) + v_half  # גבול עליון, מעלות
    out = []  # תוצאה לכל נקודה
    for p in traj:  # כל נקודה במסלול
        g = point_geometry(radar, p)  # הגיאומטריה שלה
        vr = radial_speed_ms(g, p)  # מהירות רדיאלית
        rec = {  # רשומת התוצאה — נתונים לתצוגה ולגרפים
            "t": round(p["t"], 3), "lat": p["lat"], "lon": p["lon"], "alt": round(p["alt"], 1),
            "dist_km": round(g["dist_m"] / 1000.0, 3), "slant_km": round(g["slant_m"] / 1000.0, 3),
            "bearing_deg": round(g["bearing_deg"], 2), "elev_deg": round(g["elev_deg"], 3),
            "radial_ms": round(vr, 1), "speed_ms": round(p["speed"], 1),
        }
        status, reason = STATUS_DETECTED, "ok"  # ברירת-מחדל: מזוהה
        if g["dist_m"] > range_m:  # 1. מעבר לטווח הבדיקה
            status, reason = STATUS_OUT_OF_RANGE, "out_of_range"  # אפור
        elif g["slant_m"] < min_range_m:  # 2. קרוב מדי — אזור עיוור
            status, reason = STATUS_BLOCKED, "min_range"  # אדום
        else:  # בטווח — בדיקות שטח/זווית/מכ"ם
            hz = horizon_slope_before(profiles, plan, g["bearing_deg"], g["dist_m"])  # האופק בכיוון הזה
            tgt_slope = g["dh_m"] / g["dist_m"] if g["dist_m"] > 0 else float("inf")  # שיפוע הנקודה (אינסוף = בדיוק מעל)
            rec["horizon_deg"] = round(math.degrees(math.atan(hz)), 3) if (hz is not None and math.isfinite(hz)) else None  # לתצוגה
            if hz is not None and tgt_slope < hz + margin_slope:  # 3. מתחת לאופק השטח
                status, reason = STATUS_BLOCKED, "terrain"  # אדום
            elif not (v_lo <= g["elev_deg"] <= v_hi):  # 4. מחוץ לשדה-הראייה האנכי
                status, reason = STATUS_BLOCKED, "elevation"  # אדום — כולל חרוט העיוורון מעל המכ"ם
            else:  # גלוי גיאומטרית — בדיקות המכ"ם עצמו
                scan = physics["scan_loss"](g["bearing_deg"])  # הפסד-סריקה (1 = אנטנה גנרית)
                ceiling = physics["ceiling_m"] * physics["lobing"](g["elev_deg"]) * scan  # תקרת הגילוי בכיוון ובעילוי הזה
                rcs_fn = physics.get("rcs_factor")  # שלב א5: RCS לפי זווית (None = RCS קבוע)
                if rcs_fn is not None:  # מודל זווית פעיל
                    asp = aspect_angle_deg(g, p)  # זווית ההסתכלות
                    factor, rcs_now = rcs_fn(asp)  # גורם התקרה (σ/σ_ref)^¼ וה-RCS עצמו
                    ceiling *= factor  # הטווח גדל/קטן עם שורש רביעי של ה-RCS
                    rec["aspect_deg"], rec["rcs_m2"] = round(asp, 1), round(rcs_now, 4)  # לתצוגה ולייצוא
                rain_db = 0.0  # שלב א5: הנחתת גשם הלוך-חזור, dB
                rain_fn = physics.get("rain_db")  # None = בלי גשם
                if rain_fn is not None:  # יש גשם
                    rain_db = rain_fn(g, p)  # לפי אורך המסלול בגשם בנקודה הזו
                    rec["rain_db"] = round(rain_db, 2)  # לתצוגה ולייצוא
                ceiling_dry = ceiling  # התקרה בלי גשם — כדי להבחין אם הגשם הוא הסיבה
                ceiling *= 10 ** (-rain_db / 40.0)  # הפסד של A dB בהספק מקצר טווח ב-10^(-A/40) (שורש רביעי)
                rec["ceiling_km"] = round(ceiling / 1000.0, 3)  # לתצוגה
                if scan <= 0.0:  # 5. מחוץ לסקטור של המערך
                    status, reason = STATUS_BLOCKED, "sector"  # אדום
                elif g["slant_m"] > ceiling_dry:  # 6. רחוק מתקרת המכ"ם גם בלי גשם
                    status, reason = STATUS_BLOCKED, "radar_range"  # אדום
                elif g["slant_m"] > ceiling:  # 6א. בטווח ביבש — רק הגשם מוציא אותו (שלב א5)
                    status, reason = STATUS_BLOCKED, "rain"  # אדום, סיבה נפרדת
                elif not physics["doppler_ok"](vr):  # 7. הדופלר לא מבחין
                    status, reason = STATUS_DOPPLER_BLIND, "doppler"  # כתום
        rec["status"], rec["reason"] = status, reason  # התוצאה הסופית לנקודה
        out.append(rec)  # לרשימה
    return out  # כל התוצאות


# ═══════════════════════════ סיכום ═══════════════════════════

def summarize(results):
    """
    סיכום שלב א1: האם נצפה בכלל, אחוז הכיסוי (משוקלל-זמן — כל נקודה "מחזיקה" חצי מהמרווח לכל צד),
    הגילוי הראשון, ספירות לפי סטטוס, שניות לפי סיבה, וקטעים רציפים (סטטוס+סיבה) לתצוגה ולציר הזמן.
    """
    n = len(results)  # מספר הנקודות
    summary = {"n_points": n, "detected_any": False, "coverage_pct": 0.0, "duration_s": 0.0,
               "first_detection": None, "counts": {}, "reason_seconds": {}, "segments": []}  # מבנה ריק
    if n == 0:  # אין נקודות
        return summary  # ריק
    weights = []  # משקל-זמן לכל נקודה
    for i in range(n):  # חצי מרווח לכל צד
        t_prev = results[i - 1]["t"] if i > 0 else results[i]["t"]  # הזמן הקודם (או עצמה בהתחלה)
        t_next = results[i + 1]["t"] if i < n - 1 else results[i]["t"]  # הזמן הבא (או עצמה בסוף)
        weights.append((t_next - t_prev) / 2.0)  # משקל = חצי מהמרווח הכולל
    duration = results[-1]["t"] - results[0]["t"]  # משך המסלול
    det_time = 0.0  # זמן מזוהה מצטבר
    for r, w in zip(results, weights):  # כל נקודה
        summary["counts"][r["status"]] = summary["counts"].get(r["status"], 0) + 1  # ספירה לפי סטטוס
        summary["reason_seconds"][r["reason"]] = round(summary["reason_seconds"].get(r["reason"], 0.0) + w, 2)  # שניות לפי סיבה
        if r["status"] == STATUS_DETECTED:  # מזוהה
            det_time += w  # מצטבר
            if summary["first_detection"] is None:  # הראשונה
                summary["first_detection"] = {k: r[k] for k in ("t", "lat", "lon", "alt", "dist_km", "slant_km")}  # מיקום וזמן
    summary["detected_any"] = summary["first_detection"] is not None  # האם נצפה אי פעם
    summary["duration_s"] = round(duration, 2)  # משך
    summary["coverage_pct"] = round(100.0 * det_time / duration, 1) if duration > 0 else (100.0 if summary["detected_any"] else 0.0)  # אחוז
    seg = None  # הקטע הנוכחי
    for r in results:  # בניית קטעים רציפים
        key = (r["status"], r["reason"])  # מה מגדיר קטע
        if seg is None or seg["key"] != key:  # קטע חדש
            if seg is not None:  # סוגרים את הקודם
                summary["segments"].append({"status": seg["key"][0], "reason": seg["key"][1], "t0": seg["t0"], "t1": r["t"]})  # עד תחילת החדש
            seg = {"key": key, "t0": r["t"]}  # פותחים חדש
    summary["segments"].append({"status": seg["key"][0], "reason": seg["key"][1], "t0": seg["t0"], "t1": results[-1]["t"]})  # הקטע האחרון
    return summary  # הסיכום


# ═══════════════════════════ שלב א2: סריקה ומעקב ═══════════════════════════
# המצב "גילוי" (שלב א1) בודק כל נקודה בנפרד. המצב "מעקב" מוסיף מעליו את הזמן: המכ"ם רואה את המטרה רק
# ב"הזדמנויות" (כשהאלומה עוברת עליה), מעקב נפתח אחרי M גילויים מתוך N הזדמנויות, ונשבר אם עבר זמן
# "דעיכה" (coast) בלי גילוי. בנקודה עצמה הפיזיקה זהה לשלב א1 — רק תזמון הדגימה והלוגיקה מעליה חדשים.

TRACK_TRACKED = "tracked"  # בתוך מעקב פעיל, עד הגילוי האחרון — ירוק
TRACK_COASTING = "coasting"  # מעקב פעיל בלי גילוי מאז הגילוי האחרון ("דעיכה") — ירוק בהיר
TRACK_DETECTED_ONLY = "detected_untracked"  # הפיזיקה מאפשרת גילוי, אבל אין מעקב — כחול

SCAN_ROTATING = "rotating"  # אנטנה מסתובבת — זמן סיבוב קבוע
SCAN_PHASED = "phased"  # מערך-מופע — ביקור בסקטור כל revisit שניות
SCAN_TRACKER = "tracker"  # מכ"ם מעקב ייעודי — מקבל הכוונה, ואז מעדכן בקצב קבוע עד קצב-סיבוב מרבי


def _nearest_index(times, t):
    """אינדקס הנקודה שהזמן שלה הכי קרוב ל-t (times ממוינים)."""
    k = bisect.bisect_left(times, t)  # המקום של t ברשימה
    if k <= 0:  # לפני הנקודה הראשונה
        return 0  # הראשונה
    if k >= len(times):  # אחרי האחרונה
        return len(times) - 1  # האחרונה
    return k if (times[k] - t) < (t - times[k - 1]) else k - 1  # הקרובה מבין השתיים


def _bearing_at(results, times, t):
    """אזימוט המטרה מהמכ"ם בזמן t — אינטרפולציה ליניארית בין שתי נקודות, עם טיפול במעבר 360->0."""
    k = bisect.bisect_left(times, t)  # הנקודה הראשונה שזמנה >= t
    if k <= 0:  # לפני ההתחלה
        return results[0]["bearing_deg"]  # האזימוט הראשון
    if k >= len(times):  # אחרי הסוף
        return results[-1]["bearing_deg"]  # האזימוט האחרון
    a, b = results[k - 1], results[k]  # שתי הנקודות שמקיפות את t
    f = (t - a["t"]) / (b["t"] - a["t"]) if b["t"] > a["t"] else 0.0  # מיקום יחסי ביניהן
    diff = (b["bearing_deg"] - a["bearing_deg"] + 540.0) % 360.0 - 180.0  # ההפרש הקצר, עם סימן
    return (a["bearing_deg"] + f * diff) % 360.0  # האזימוט המשוערך


def angular_rates(results):
    """קצב השינוי הזוויתי של קו-הראייה (מעלות/שנייה) לכל נקודה — כמה מהר מכ"ם מעקב צריך להסתובב.
    משלב אזימוט (מוקטן ב-cos העילוי — ליד הזנית שינוי אזימוט גדול הוא תנועה קטנה) ועילוי."""
    n = len(results)  # מספר הנקודות
    out = []  # התוצאה
    for i in range(n):  # כל נקודה
        a, b = results[max(0, i - 1)], results[min(n - 1, i + 1)]  # השכנות (הפרש מרכזי)
        dt = b["t"] - a["t"]  # הפרש הזמן
        if dt <= 0:  # נקודה בודדת
            out.append(0.0)  # אין קצב
            continue  # הבאה
        daz = (b["bearing_deg"] - a["bearing_deg"] + 540.0) % 360.0 - 180.0  # שינוי אזימוט קצר
        el = math.radians((a["elev_deg"] + b["elev_deg"]) / 2.0)  # עילוי ממוצע
        d_el = b["elev_deg"] - a["elev_deg"]  # שינוי עילוי
        out.append(math.hypot(daz * math.cos(el), d_el) / dt)  # קצב זוויתי כולל, מעלות/שנייה
    return out  # קצב לכל נקודה


def scan_opportunities(results, scan):
    """זמני ההזדמנויות לגילוי במצבי חיפוש (מסתובבת / מערך-מופע). במכ"ם מעקב ייעודי ההזדמנויות נבנות
    בתוך run_track_logic, כי הן תלויות ברגע שבו הוא מקבל הכוונה."""
    times = [r["t"] for r in results]  # זמני הנקודות
    if not times:  # אין מסלול
        return []  # אין הזדמנויות
    t0, t1 = times[0], times[-1]  # תחילת וסוף המסלול
    opps = []  # התוצאה
    if scan["mode"] == SCAN_ROTATING:  # אנטנה מסתובבת
        period = scan["rot_period_s"]  # זמן סיבוב
        phase = scan["phase_deg"]  # כיוון האלומה ברגע תחילת המסלול (0 = צפון)
        k = 0  # מספר הסיבוב
        while True:  # סיבוב אחר סיבוב
            t = t0 + k * period  # ניחוש התחלתי: תחילת הסיבוב
            for _ in range(4):  # האלומה פוגשת את המטרה כשהאזימוט שלה = אזימוט המטרה; איטרציה קצרה מתכנסת
                frac = ((_bearing_at(results, times, t) - phase) % 360.0) / 360.0  # איזה חלק מהסיבוב עד הכיוון של המטרה
                t = t0 + k * period + frac * period  # הזמן שבו האלומה מגיעה לשם בסיבוב הזה
            if t > t1:  # מעבר לסוף המסלול
                break  # סיימנו
            opps.append(t)  # הזדמנות (תמיד >= t0, כי frac >= 0)
            k += 1  # הסיבוב הבא
    elif scan["mode"] == SCAN_PHASED:  # מערך-מופע
        t = t0  # מתחילים בתחילת המסלול
        while t <= t1:  # עד הסוף
            opps.append(t)  # ביקור
            t += scan["revisit_s"]  # הביקור הבא
    return opps  # כל ההזדמנויות


def run_track_logic(results, scan, track):
    """
    מריץ את לוגיקת המעקב על תוצאות שלב א1. scan: {'mode', 'rot_period_s', 'phase_deg', 'revisit_s',
    'track_rate_hz', 'max_ang_rate_dps', 'cue_delay_s'}. track: {'m', 'n', 'coast_s'}.
    מחזיר {'opportunities', 'opp_detected', 'first_opp_detection', 'tracks':[{t_start,t_last_det,t_end,end_reason}], 'rates'}.
    מכ"ם מעקב ייעודי: מקבל הכוונה ברגע שהמטרה מזוהה (הנחה 2, FR-D-262) + השהיה, ומשם מתעדכן בקצב קבוע;
    עדכון שבו קצב-הסיבוב הנדרש גבוה מהמרבי נחשב החטאה עם סיבה 'angular_rate'.
    """
    times = [r["t"] for r in results]  # זמני הנקודות
    rates = angular_rates(results)  # קצב זוויתי לכל נקודה
    out = {"opportunities": 0, "opp_detected": 0, "tracks": [], "rates": rates, "first_opp_detection": None}  # מבנה התוצאה
    if len(times) < 2:  # אין מסלול אמיתי
        return out  # ריק
    t_end_traj = times[-1]  # סוף המסלול
    m, n, coast = track["m"], track["n"], track["coast_s"]  # פרמטרי המעקב

    def look(t):
        """מה המכ"ם רואה ברגע t: (גילוי?, סיבה) — לפי הנקודה הקרובה, ובמכ"ם מעקב גם לפי קצב הסיבוב."""
        i = _nearest_index(times, t)  # הנקודה הקרובה
        r = results[i]  # התוצאה שלה
        if r["status"] != STATUS_DETECTED:  # הפיזיקה לא מאפשרת
            return False, r["reason"]  # החטאה, עם הסיבה של הנקודה
        if scan["mode"] == SCAN_TRACKER and rates[i] > scan["max_ang_rate_dps"]:  # המטרה מהירה מדי לאנטנה
            return False, "angular_rate"  # החטאה בגלל קצב הסיבוב
        return True, "ok"  # גילוי

    def process(opp_times, give_up_after_n_misses):
        """מעבד רצף הזדמנויות: פתיחת מעקב ב-M מתוך N, דעיכה ושבירה. מחזיר את זמן השבירה/הוויתור,
        או None אם הגענו לסוף. give_up_after_n_misses: מכ"ם מעקב שלא הצליח לפתוח מעקב אחרי N
        החטאות ברצף מוותר על ההכוונה וחוזר לחכות להכוונה חדשה."""
        window, active, misses = [], None, 0  # חלון N האחרונות, המעקב הפעיל, החטאות ברצף לפני פתיחה
        for t in opp_times:  # כל הזדמנות
            seen, reason = look(t)  # מה רואים
            out["opportunities"] += 1  # ספירה
            if seen:  # גילוי
                out["opp_detected"] += 1  # ספירה
                if out["first_opp_detection"] is None:  # הראשון בכלל
                    out["first_opp_detection"] = round(t, 3)  # נשמר
            if active is None:  # אין מעקב — בודקים פתיחה
                window = (window + [seen])[-n:]  # חלון N האחרונות
                misses = 0 if seen else misses + 1  # החטאות ברצף
                if sum(window) >= m:  # M גילויים מתוך N
                    active = {"t_start": round(t, 3), "t_last_det": round(t, 3), "miss_reason": None}  # מעקב נפתח
                    window, misses = [], 0  # איפוס לפתיחה הבאה
                elif give_up_after_n_misses and misses >= n:  # מכ"ם מעקב שלא תפס — מוותר
                    return t  # חוזר לחכות להכוונה חדשה
            elif seen:  # יש מעקב ויש גילוי
                active["t_last_det"] = round(t, 3)  # מתעדכן
                active["miss_reason"] = None  # אין החטאה פתוחה
            else:  # יש מעקב והחטאה
                if active["miss_reason"] is None:  # ההחטאה הראשונה מאז הגילוי האחרון
                    active["miss_reason"] = reason  # היא הסיבה לאובדן אם המעקב ייפול
                if t - active["t_last_det"] > coast:  # עבר זמן הדעיכה
                    active.update(t_end=round(t, 3), end_reason=active.pop("miss_reason"))  # המעקב נשבר
                    out["tracks"].append(active)  # נשמר
                    active = None  # אין מעקב
                    if give_up_after_n_misses:  # מכ"ם מעקב — צריך הכוונה חדשה
                        return t  # זמן השבירה
        if active is not None:  # ההזדמנויות נגמרו בזמן מעקב
            reason = active.pop("miss_reason", None)  # סיבת ההחטאה הפתוחה, אם יש (שדה פנימי)
            if reason and t_end_traj - active["t_last_det"] > coast:  # היו החטאות, וזמן הדעיכה עבר לפני סוף המסלול
                active.update(t_end=round(active["t_last_det"] + coast, 3), end_reason=reason)  # נשבר בתום הדעיכה
            else:  # המעקב החזיק עד סוף המסלול
                active.update(t_end=round(t_end_traj, 3), end_reason="end")  # עד הסוף
            out["tracks"].append(active)  # נשמר
        return None  # הגענו לסוף ההזדמנויות

    if scan["mode"] in (SCAN_ROTATING, SCAN_PHASED):  # מכ"ם חיפוש — הזדמנויות קבועות מראש
        process(scan_opportunities(results, scan), give_up_after_n_misses=False)  # כל המסלול ברצף אחד
    else:  # מכ"ם מעקב ייעודי
        step = 1.0 / scan["track_rate_hz"]  # מרווח בין עדכונים
        t_free = times[0]  # מתי מותר לחפש את ההכוונה הבאה
        while True:  # הכוונה אחר הכוונה
            cue = next((r["t"] for r in results if r["t"] >= t_free and r["status"] == STATUS_DETECTED), None)  # הגילוי הבא = ההכוונה
            if cue is None:  # אין עוד הכוונה
                break  # סיימנו
            start = cue + scan["cue_delay_s"]  # המכ"ם מתחיל לעקוב אחרי ההשהיה
            if start > t_end_traj:  # ההכוונה מאוחרת מדי
                break  # סיימנו
            count = int((t_end_traj - start) / step) + 1  # כמה עדכונים עד הסוף
            stopped_at = process([start + k * step for k in range(count)], give_up_after_n_misses=True)  # עוקבים עד שבירה/ויתור
            if stopped_at is None:  # הגענו לסוף המסלול
                break  # סיימנו
            t_free = stopped_at + 1e-6  # ההכוונה הבאה רק אחרי השבירה
    return out  # תוצאת המעקב


def track_states(results, tracks):
    """מצב-מעקב לכל נקודה (לצביעה ולציר הזמן): מעקב / דעיכה / גילוי-בלי-מעקב / הסטטוס המקורי."""
    states = []  # התוצאה
    for r in results:  # כל נקודה
        t = r["t"]  # הזמן שלה
        st = None  # מצב-מעקב, אם יש
        for tr in tracks:  # כל מעקב
            if tr["t_start"] <= t <= tr["t_end"]:  # בתוך חלון המעקב
                # דעיכה = בין הגילוי האחרון לשבירה; פערים קצרים באמצע מעקב (בין סיבובי אנטנה) הם עדיין "במעקב"
                coasting = t > tr["t_last_det"] and tr["end_reason"] != "end"  # רק לפני שבירה אמיתית
                st = TRACK_COASTING if coasting else TRACK_TRACKED  # המצב
                break  # מספיק
        if st is None:  # לא במעקב
            st = TRACK_DETECTED_ONLY if r["status"] == STATUS_DETECTED else r["status"]  # גילוי בלי מעקב, או הסטטוס המקורי
        states.append(st)  # לרשימה
    return states  # מצב לכל נקודה


def summarize_track(results, trk, states):
    """מדדי שלב א2: האם נפתח מעקב, מתי, זמן ההתרעה (מפתיחת המעקב הראשון עד סוף המסלול), אחוז הזמן
    במעקב, הזדמנויות וגילויים, ומקטעי ציר-הזמן (מצב-מעקב + סיבה)."""
    out = {"track_initiated": bool(trk["tracks"]), "first_track_t": None, "warning_time_s": None,
           "tracked_pct": 0.0, "opportunities": trk["opportunities"], "opp_detected": trk["opp_detected"],
           "first_opp_detection": trk["first_opp_detection"], "tracks": trk["tracks"], "timeline": []}  # מבנה
    if not results:  # אין מסלול
        return out  # ריק
    t0, t1 = results[0]["t"], results[-1]["t"]  # תחילה וסוף
    if trk["tracks"]:  # נפתח מעקב
        first = trk["tracks"][0]["t_start"]  # הפתיחה הראשונה
        out["first_track_t"] = first  # נשמר
        out["warning_time_s"] = round(t1 - first, 2)  # זמן ההתרעה
        tracked = sum(min(tr["t_end"], t1) - tr["t_start"] for tr in trk["tracks"])  # זמן במעקב (כולל דעיכה)
        out["tracked_pct"] = round(100.0 * tracked / (t1 - t0), 1) if t1 > t0 else 100.0  # אחוז
    seg = None  # המקטע הנוכחי
    for r, st in zip(results, states):  # בניית מקטעים רציפים
        key = (st, "" if st in (TRACK_TRACKED, TRACK_COASTING) else r["reason"])  # מצב, וסיבה רק מחוץ למעקב
        if seg is None or seg["key"] != key:  # מקטע חדש
            if seg is not None:  # סוגרים את הקודם
                out["timeline"].append({"state": seg["key"][0], "reason": seg["key"][1], "t0": seg["t0"], "t1": r["t"]})  # עד תחילת החדש
            seg = {"key": key, "t0": r["t"]}  # פותחים חדש
    out["timeline"].append({"state": seg["key"][0], "reason": seg["key"][1], "t0": seg["t0"], "t1": t1})  # האחרון
    return out  # המדדים


# ═══════════════════════════ שלב א5: הנחתת גשם ו-RCS לפי זווית ═══════════════════════════

# ── מודל הנחתת הגשם: Recommendation ITU-R P.838-3 (2005), "Specific attenuation model for rain for use in
# prediction methods". המקדמים הועתקו מטבלאות 1-4 של ה-PDF הרשמי (itu.int, הורדה חינמית) ונבדקו מול
# טבלה 5 שלו (tests/test_radar_track.py). שימוש לפי החלטת הבעלים D8 (docs/DEPENDENCIES.md), עם ציון מקור. ──
# כל שורה: (a_j, b_j, c_j)
_P838_KH = ((-5.33980, -0.10008, 1.13098), (-0.35351, 1.26970, 0.45400),
            (-0.23789, 0.86036, 0.15354), (-0.94158, 0.64552, 0.16817))  # טבלה 1 — kH
_P838_KH_M, _P838_KH_C = -0.18961, 0.71147  # mk, ck של kH
_P838_KV = ((-3.80595, 0.56934, 0.81061), (-3.44965, -0.22911, 0.51059),
            (-0.39902, 0.73042, 0.11899), (0.50167, 1.07319, 0.27195))  # טבלה 2 — kV
_P838_KV_M, _P838_KV_C = -0.16398, 0.63297  # mk, ck של kV
_P838_AH = ((-0.14318, 1.82442, -0.55187), (0.29591, 0.77564, 0.19822), (0.32177, 0.63773, 0.13164),
            (-5.37610, -0.96230, 1.47828), (16.1721, -3.29980, 3.43990))  # טבלה 3 — αH
_P838_AH_M, _P838_AH_C = 0.67849, -1.95537  # mα, cα של αH
_P838_AV = ((-0.07771, 2.33840, -0.76284), (0.56727, 0.95545, 0.54039), (-0.20238, 1.14520, 0.26809),
            (-48.2991, 0.791669, 0.116226), (48.5833, 0.791459, 0.116479))  # טבלה 4 — αV
_P838_AV_M, _P838_AV_C = -0.053739, 0.83433  # mα, cα של αV


def _p838_sum(rows, lf):
    """הסכום הגאוסי המשותף למשוואות (2) ו-(3): Σ a·exp(-((log f - b)/c)²)."""
    return sum(a * math.exp(-((lf - b) / c) ** 2) for a, b, c in rows)  # לפי ההמלצה


def p838_coefficients(f_ghz):
    """kH, αH, kV, αV לתדר נתון (משוואות 2-3 של ITU-R P.838-3). ההמלצה מוגדרת ל-1–1000 GHz — מתחת
    ל-1 GHz משתמשים בערכי 1 GHz (ההנחתה שם זניחה ממילא — כ-0.00003 dB/ק"מ בגשם של 1 מ"מ/שעה)."""
    lf = math.log10(min(1000.0, max(1.0, f_ghz)))  # log10 של התדר, בתוך תחום ההגדרה
    kh = 10 ** (_p838_sum(_P838_KH, lf) + _P838_KH_M * lf + _P838_KH_C)  # משוואה (2), קיטוב אופקי
    kv = 10 ** (_p838_sum(_P838_KV, lf) + _P838_KV_M * lf + _P838_KV_C)  # משוואה (2), קיטוב אנכי
    ah = _p838_sum(_P838_AH, lf) + _P838_AH_M * lf + _P838_AH_C  # משוואה (3), אופקי
    av = _p838_sum(_P838_AV, lf) + _P838_AV_M * lf + _P838_AV_C  # משוואה (3), אנכי
    return kh, ah, kv, av  # ארבעת המקדמים


def rain_specific_attenuation(rate_mm_h, f_ghz, elev_deg, tilt_deg):
    """הנחתה סגולית γ [dB/ק"מ] = k·R^α (משוואה 1), עם k ו-α משולבים לפי זווית העילוי של המסלול θ וזווית
    הקיטוב τ (0 = אופקי, 90 = אנכי, 45 = מעגלי) — משוואות 4-5 של ITU-R P.838-3."""
    if rate_mm_h <= 0:  # בלי גשם
        return 0.0  # בלי הנחתה
    kh, ah, kv, av = p838_coefficients(f_ghz)  # המקדמים לתדר
    g = math.cos(math.radians(elev_deg)) ** 2 * math.cos(math.radians(2.0 * tilt_deg))  # cos²θ·cos2τ
    k = (kh + kv + (kh - kv) * g) / 2.0  # משוואה (4)
    alpha = (kh * ah + kv * av + (kh * ah - kv * av) * g) / (2.0 * k)  # משוואה (5)
    return k * rate_mm_h ** alpha  # משוואה (1)


def rain_path_km(slant_m, radar_h_msl, target_alt, rain_top_m):
    """אורך המסלול בתוך הגשם [ק"מ]: הגשם מניחים אחיד מהקרקע ועד "תקרת הגשם". קו ישר בין האנטנה למטרה —
    החלק שמתחת לתקרה (קירוב: ליניארי בגובה; עקמומיות זניחה בטווחי הכלי)."""
    lo, hi = min(radar_h_msl, target_alt), max(radar_h_msl, target_alt)  # הגובה הנמוך והגבוה בקצוות
    if lo >= rain_top_m:  # שני הקצוות מעל הגשם
        return 0.0  # אין גשם בדרך
    if hi <= rain_top_m or hi == lo:  # כל הקו בתוך הגשם
        return slant_m / 1000.0  # כל הטווח
    return slant_m / 1000.0 * (rain_top_m - lo) / (hi - lo)  # רק החלק שמתחת לתקרה


def aspect_angle_deg(geom, p):
    """זווית ההסתכלות על המטרה: 0° = המטרה טסה ישר אל המכ"ם (רואים חרטום), 90° = צד, 180° = זנב.
    הזווית בין וקטור המהירות לבין הכיוון מהמטרה אל המכ"ם."""
    if p["speed"] <= 0:  # מטרה נייחת — אין חרטום
        return 90.0  # מתייחסים כאל צד
    b, e = math.radians(geom["bearing_deg"]), math.radians(geom["elev_deg"])  # כיוון מהמכ"ם אל המטרה
    tx, ty, tz = -math.sin(b) * math.cos(e), -math.cos(b) * math.cos(e), -math.sin(e)  # היחידה מהמטרה אל המכ"ם (הפוך)
    dot = (p["ve"] * tx + p["vn"] * ty + p["vu"] * tz) / p["speed"]  # cos של הזווית
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))  # מעלות 0..180


def aspect_rcs(aspect_deg, nose_m2, side_m2, tail_m2):
    """RCS לפי זווית: מעבר הדרגתי (ליניארי ב-dB) בין חרטום (0°), צד (90°) וזנב (180°) — מודל רעיוני פשוט."""
    def db(x):  # מ"ר -> dBsm
        return 10.0 * math.log10(max(1e-6, x))  # עם רצפה, בלי log של אפס
    if aspect_deg <= 90.0:  # בין חרטום לצד
        f = aspect_deg / 90.0  # מיקום יחסי
        val = db(nose_m2) + f * (db(side_m2) - db(nose_m2))  # אינטרפולציה
    else:  # בין צד לזנב
        f = (aspect_deg - 90.0) / 90.0  # מיקום יחסי
        val = db(side_m2) + f * (db(tail_m2) - db(side_m2))  # אינטרפולציה
    return 10 ** (val / 10.0)  # חזרה למ"ר
