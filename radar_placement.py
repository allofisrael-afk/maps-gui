# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
radar_placement — שלב ב' של כלי בדיקת מעקב המכ"ם (SRS FR-D-277..): הצעת מיקום למכ"ם עם מפת חום.

הבעיה: בדיקה רגילה (שלב א') שולפת מאות נקודות גובה לכל מיקום, ו-Open-Meteo סופר כל נקודה כקריאה
(600/דקה, 5000/שעה). 100 מיקומים היו דורשים פי כמה מהמכסה השעתית. הפתרון: שולפים **פעם אחת** רשת
גבהים גסה (DemGrid) של כל האזור — המיקומים המועמדים והמסלול — ומחשבים את כל המועמדים מתוכה,
באינטרפולציה בילינארית, בלי שום שליפה נוספת. המנוע עצמו (radar_track) משמש כמו שהוא: לכל מועמד אותו
תכנון קרניים, אותו פרופיל אופק, אותה הערכה ואותה לוגיקת מעקב — רק מקור הגבהים שונה.
זה סינון ראשוני ברזולוציה גסה; את המיקום שנבחר מאמתים בבדיקה המדויקת של שלב א'.
stdlib בלבד.
"""

import math  # גיאומטריה

import radar_track as rt  # המנוע של שלב א' — לא משתנה

DEM_BUDGET = 1200  # תקרת נקודות ברשת הגבהים — כ-2.5 דקות בקצב המבוקר, רבע מהמכסה השעתית
DEM_MIN_RES_M = 250.0  # רזולוציה מינימלית — מתחת לזה הרשת תעלה יותר נקודות בלי תועלת אמיתית לסינון
DEM_MAX_RES_M = 1500.0  # מעבר לזה הרשת גסה מדי לסינון משמעותי — מחזירים שגיאה עם הסבר
DEM_PAD_M = 1000.0  # שוליים סביב האזור — קרניים שעוברות קרוב לקצה
MAX_CANDIDATES = 400  # תקרת מיקומים מועמדים — זמן חישוב סביר (כל מועמד = בדיקה מלאה)
CANDIDATE_PLAN_BUDGET = 300  # תקציב תאים לכל מועמד — דגימה דלילה יותר מבשלב א' (ממילא מאונטרפל מרשת גסה)


def candidate_grid(center_lat, center_lon, radius_m, step_m):
    """מיקומים מועמדים: רשת ריבועית במרווח step_m (מזרח/צפון) בתוך מעגל ברדיוס radius_m סביב המרכז."""
    n = int(radius_m // step_m)  # כמה צעדים לכל צד
    cos_lat = math.cos(math.radians(center_lat))  # תיקון אורך-מעלה מזרחית
    out = []  # המועמדים
    for i in range(-n, n + 1):  # מזרח-מערב
        for j in range(-n, n + 1):  # צפון-דרום
            dx, dy = i * step_m, j * step_m  # היסט במטרים
            if dx * dx + dy * dy <= radius_m * radius_m + 1e-6:  # בתוך המעגל
                out.append({"lat": center_lat + dy / rt.DEG_TO_M,  # רוחב
                            "lon": center_lon + dx / (rt.DEG_TO_M * cos_lat),  # אורך
                            "dx_m": dx, "dy_m": dy})  # היסט — לציור התא במפה
    return out  # הרשימה


class DemGrid:
    """רשת גבהים סדירה בקווי רוחב/אורך, מיושרת לרשת התאים של radar_track (GRID_DEG) — כך שהצמתים שלה
    הם בדיוק מפתחות מטמון הגבהים בשרת, ושליפות קודמות (גם של שלב א') נחסכות."""

    def __init__(self, lat_min, lat_max, lon_min, lon_max, budget=DEM_BUDGET, min_res_m=DEM_MIN_RES_M):
        """בונה את הרשת על התיבה, ברזולוציה הגסה ביותר שנדרשת כדי לא לחרוג מהתקציב."""
        mid = math.radians((lat_min + lat_max) / 2.0)  # רוחב ממוצע
        h_m = (lat_max - lat_min) * rt.DEG_TO_M  # גובה התיבה במטרים
        w_m = (lon_max - lon_min) * rt.DEG_TO_M * math.cos(mid)  # רוחב התיבה במטרים
        res = max(min_res_m, math.sqrt(max(1.0, h_m * w_m) / budget))  # הרזולוציה שנכנסת לתקציב
        self.k_lat = max(1, int(math.ceil(res / rt.DEG_TO_M / rt.GRID_DEG)))  # צעד ברוחב, בכפולות של תא
        self.k_lon = max(1, int(math.ceil(res / (rt.DEG_TO_M * math.cos(mid)) / rt.GRID_DEG)))  # צעד באורך
        self.i0 = int(math.floor(lat_min / rt.GRID_DEG / self.k_lat)) * self.k_lat  # אינדקס הצומת הראשון ברוחב
        self.j0 = int(math.floor(lon_min / rt.GRID_DEG / self.k_lon)) * self.k_lon  # ובאורך
        self.n_lat = int(math.ceil(lat_max / rt.GRID_DEG / self.k_lat)) - self.i0 // self.k_lat + 1  # מספר שורות
        self.n_lon = int(math.ceil(lon_max / rt.GRID_DEG / self.k_lon)) - self.j0 // self.k_lon + 1  # מספר עמודות
        self.res_m = max(self.k_lat * rt.GRID_DEG * rt.DEG_TO_M, self.k_lon * rt.GRID_DEG * rt.DEG_TO_M * math.cos(mid))  # הרזולוציה בפועל
        self.values = [None] * (self.n_lat * self.n_lon)  # הגבהים — יתמלאו אחרי השליפה

    def node(self, r, c):
        """הצומת (שורה, עמודה) כמפתח תא — זהה בדיוק ל-radar_track.snap_cell."""
        return (round((self.i0 + r * self.k_lat) * rt.GRID_DEG, 6), round((self.j0 + c * self.k_lon) * rt.GRID_DEG, 6))  # (lat, lon)

    def nodes(self):
        """כל הצמתים, לפי סדר שורות — לשליפה."""
        return [self.node(r, c) for r in range(self.n_lat) for c in range(self.n_lon)]  # הרשימה

    def set_values(self, vals):
        """מציב את הגבהים שנשלפו (רשימה מקבילה ל-nodes)."""
        self.values = list(vals)  # עותק

    def at(self, lat, lon):
        """גובה באינטרפולציה בילינארית. מחוץ לרשת — הקצה הקרוב. פינה חסרה — ממוצע הפינות הקיימות."""
        fr = (lat / rt.GRID_DEG - self.i0) / self.k_lat  # מיקום רציף בשורות
        fc = (lon / rt.GRID_DEG - self.j0) / self.k_lon  # ובעמודות
        fr = min(max(fr, 0.0), self.n_lat - 1.000001)  # צמידה לרשת
        fc = min(max(fc, 0.0), self.n_lon - 1.000001)  # צמידה לרשת
        r, c = int(fr), int(fc)  # הצומת השמאלי-תחתון
        tr, tc = fr - r, fc - c  # המשקלות
        corners = [(self.values[r * self.n_lon + c], (1 - tr) * (1 - tc)), (self.values[r * self.n_lon + c + 1], (1 - tr) * tc),
                   (self.values[(r + 1) * self.n_lon + c], tr * (1 - tc)), (self.values[(r + 1) * self.n_lon + c + 1], tr * tc)]  # ארבע הפינות
        good = [(v, w) for v, w in corners if v is not None]  # פינות עם נתון
        if not good:  # אין נתון בכלל
            return None  # לא ממציאים
        if len(good) == 4:  # המקרה הרגיל
            return sum(v * w for v, w in good)  # בילינארי
        return sum(v for v, _w in good) / len(good)  # ממוצע הקיימות


def score_of(metric, summary, track_summary, t_end):
    """הציון של מועמד: 'warning' = זמן התרעה (במצב מעקב — מפתיחת המעקב; במצב גילוי — מהגילוי הראשון), או
    'coverage' = אחוז הזמן במעקב (או בגילוי, במצב גילוי). מועמד שלא רואה כלום מקבל 0. t_end = זמן סוף המסלול."""
    if metric == "coverage":  # אחוז כיסוי
        return track_summary["tracked_pct"] if track_summary is not None else summary["coverage_pct"]  # לפי המצב
    if track_summary is not None:  # זמן התרעה במצב מעקב
        return track_summary["warning_time_s"] or 0.0  # 0 אם לא נפתח מעקב
    first = summary["first_detection"]  # במצב גילוי
    return round(t_end - first["t"], 2) if first else 0.0  # מהגילוי הראשון עד סוף המסלול (לא מניח שהזמן מתחיל ב-0)


def evaluate_candidate(cand, traj, dem, params, physics_factory, track_cfg, metric):
    """בדיקה מלאה של מועמד אחד מתוך רשת הגבהים: אותו צינור כמו בשלב א' (תכנון, פרופיל, הערכה, מעקב)."""
    ground = dem.at(cand["lat"], cand["lon"])  # גובה הקרקע במועמד
    if ground is None:  # אין נתון
        return dict(cand, ground_m=None, score=None, error="אין גובה קרקע")  # מדלגים
    radar = {"lat": cand["lat"], "lon": cand["lon"], "h_msl": ground + params["h_antenna"]}  # המכ"ם במועמד
    plan = rt.plan_terrain_samples(radar, traj, params["range_km"] * 1000.0, budget=CANDIDATE_PLAN_BUDGET)  # קרניים
    elevs = [dem.at(lat, lon) for (lat, lon) in plan["cells"]]  # הגבהים — מהרשת, בלי שליפה
    profiles = rt.build_horizon_profiles(plan, elevs, radar["h_msl"])  # פרופילי אופק
    results = rt.evaluate_points(traj, radar, params, physics_factory(radar["h_msl"]), plan, profiles)  # הערכה
    summ = rt.summarize(results)  # סיכום פיזיקלי
    track_mode, scan, track = track_cfg  # מצב המעקב
    tsum = None  # סיכום מעקב (רק במצב מעקב)
    if track_mode == "track":  # עם סריקה ומעקב
        trk = rt.run_track_logic(results, scan, track)  # לוגיקה
        tsum = rt.summarize_track(results, trk, rt.track_states(results, trk["tracks"]))  # סיכום
    score = score_of(metric, summ, tsum, results[-1]["t"] if results else 0.0)  # הציון
    return dict(cand, ground_m=round(ground, 1), score=round(score, 2), coverage_pct=summ["coverage_pct"],
                detected_any=summ["detected_any"],
                track_initiated=(tsum["track_initiated"] if tsum else None),
                warning_time_s=(tsum["warning_time_s"] if tsum else None),
                tracked_pct=(tsum["tracked_pct"] if tsum else None))  # התוצאה למועמד


def region_bbox(candidates, traj, range_m):
    """התיבה שמכסה את המועמדים ואת נקודות המסלול שבטווח של מועמד כלשהו (קרניים עוברות רק ביניהם), עם שוליים."""
    lats = [c["lat"] for c in candidates]  # רוחב המועמדים
    lons = [c["lon"] for c in candidates]  # אורך המועמדים
    clat, clon = sum(lats) / len(lats), sum(lons) / len(lons)  # מרכז האזור
    reach = range_m + max(math.hypot(c["dx_m"], c["dy_m"]) for c in candidates)  # הטווח המרבי ממרכז האזור
    for p in traj:  # נקודות המסלול
        if rt.haversine_m(clat, clon, p["lat"], p["lon"]) <= reach:  # רלוונטית
            lats.append(p["lat"])  # נכנסת לתיבה
            lons.append(p["lon"])  # נכנסת לתיבה
    pad_lat = DEM_PAD_M / rt.DEG_TO_M  # שוליים ברוחב
    pad_lon = DEM_PAD_M / (rt.DEG_TO_M * math.cos(math.radians(clat)))  # שוליים באורך
    return min(lats) - pad_lat, max(lats) + pad_lat, min(lons) - pad_lon, max(lons) + pad_lon  # התיבה


def best_candidates(results, n=5):
    """המועמדים הטובים: לפי הציון, ואז לפי אחוז הכיסוי (שובר שוויון)."""
    ok = [r for r in results if r.get("score") is not None]  # רק מחושבים
    return sorted(ok, key=lambda r: (r["score"], r.get("coverage_pct") or 0.0), reverse=True)[:n]  # הטובים
