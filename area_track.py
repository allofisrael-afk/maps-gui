# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""בדיקת מעקב מכ"ם מלאה לכל המסלולים של "מאזור לאזור" (FR-D-302, 28/11/2026).

הצביעה לפי קו ראייה בלבד (area_fire.visibility) צובעת ירוק גם מסלול שמשיק למכ"ם — המהירות הרדיאלית שלו מתחת לסף
הדופלר (MDV), ובפועל המכ"ם לא יגלה אותו. כאן כל מסלול עובר את אותו צינור בדיוק כמו "🎯 בדוק מעקב מכ"ם" של מסלול בודד
(radar_service.run_check): גובה המכ"ם, דגימות שטח ופרופילי אופק, משוואת מכ"ם, ריבוד, דופלר, שדה ראייה, ובמצב מעקב גם
סריקה ופתיחת מעקב (M מתוך N). הזמן בכל נקודה מגיע מפרופיל הזמן שבטבלת הירי (area_fire, path[k][3]).
- כל מכ"ם מוצב עם הפרמטרים שלו (סוג + הצבה), ופרמטרי המטרה והמעקב מטאב "מעקב מכ"ם" — הלקוח בונה גוף בקשה לכל מכ"ם.
- לכל נקודת ציור: המצב הטוב ביותר מכל המכ"מים (קוד 0–5, ר' CODES). לכל מסלול: נפתח מעקב? זוהה? זמן מעקב ראשון, זמן התרעה.
- גבהים: אותה שליפה כמו בשאר הכלים (SRTM מקומי, מטמון, Open-Meteo רק לחסר).
- מהירות: תכנון דגימות השטח (קרניים מהמכ"ם) נעשה **פעם אחת לכל מכ"ם** על כל נקודות כל המסלולים, ופרופילי האופק משותפים
  לכולם — במקום תכנון נפרד לכל מסלול (נמדד: 97% מזמן הריצה, ‏~95 מ"ש למסלול). ההערכה עצמה (evaluate_points) ולוגיקת
  המעקב — אותן פונקציות בדיוק כמו בבדיקת מסלול בודד. תקציב התאים גדול יותר (AREA_TERRAIN_BUDGET), כי השטח מקומי.
ספריית התקן + מודולי הפרויקט בלבד (בלי תלות חדשה)."""
import time  # זמן ריצה והערכת זמן שנותר

import area_fire  # Aborted
import radar_service as rs  # הצינור של בדיקת המעקב (אותו קוד כמו במסלול בודד)
import radar_track as rt  # _nearest_index

AREA_MAX_AZ_BINS = 1440  # עד 360° ברבע מעלה — אותה רזולוציה זוויתית כמו בבדיקת מסלול בודד בגזרה צרה
AREA_TERRAIN_BUDGET = 60000  # תקציב תאי שטח לכל מכ"ם (מול 600 במסלול בודד, שנקבע בגלל מכסת Open-Meteo) — כל השטח מ-SRTM המקומי; שומר על אותה צפיפות קרניים גם בגזרה רחבה
CODES = ["out_of_range", "blocked", "doppler_blind", "detected", "coasting", "tracked"]  # קוד → מצב (גבוה = טוב יותר); המפתחות = מפתחות הצבעים של בדיקת המעקב בממשק


def point_code(r):  # נקודת תוצאה של run_check → קוד מצב (0..5)
    st = r.get("track_state")  # מצב מעקב (רק במצב מעקב)
    if st == "tracked":  # במעקב
        return 5  # הכי טוב
    if st == "coasting":  # דעיכה — מעקב בלי גילוי בסריקה הזו
        return 4  # כמעט
    s = r.get("status")  # הסטטוס הפיזיקלי
    return {"detected": 3, "doppler_blind": 2, "blocked": 1}.get(s, 0)  # מזוהה / עיוור לדופלר / חסום / מחוץ לטווח


def parse_radars(radars):  # [{name, body}] מהלקוח → רשימת מכ"מים מוכנים לצינור; מכ"ם בלי מיקום תקין — מדלגים
    out = []  # התוצאה
    for i, rd in enumerate(radars or []):  # כל מכ"ם
        body = (rd or {}).get("body") or {}  # גוף הבקשה שלו (סוג + הצבה + טאב המעקב)
        try:
            lat, lon = float(body["lat"]), float(body["lon"])  # מיקום
            rs.check_latlon(lat, lon)  # בטווח
        except (KeyError, TypeError, ValueError):  # חסר/שגוי
            continue  # הבא
        p, cfg, _ = rs.parse_all(body)  # אותה קליטה כמו בבדיקת מסלול בודד (צמידה לטווחים)
        out.append({"name": str((rd or {}).get("name") or f"מכ\"ם {i + 1}")[:80], "lat": lat, "lon": lon, "p": p, "cfg": cfg})  # מוכן
    return out  # הרשימה


def track_check(rows, radars, fetch_cells, progress=None, cancelled=None):  # הבדיקה המלאה לכל המסלולים
    """rows: שורות מ-area_fire.run (path עם זמן); radars: parse_radars(...). מחזיר states (קוד לכל נקודת ציור, הטוב מכל המכ"מים),
    rows (לכל מסלול: tk=נפתח מעקב, dt=זוהה, ft=זמן מעקב ראשון, ws=זמן התרעה, by=ביטי המכ"מים שזיהו), radars, summary."""
    memo = {}  # מטמון גבהים לכל ההרצה — תאי שטח משותפים לרוב המסלולים

    def fetch(cells):  # שליפה דרך המטמון; רק מה שחסר יורד לשליפה האמיתית
        need = list(dict.fromkeys(c for c in cells if c not in memo))  # חסרים, בלי כפילויות
        if need:  # יש מה לשלוף
            for c, e in zip(need, fetch_cells(need)):  # השליפה
                memo[c] = e  # למטמון
        return [memo.get(c) for c in cells]  # בסדר המקורי

    n_rows, n_rad = len(rows), len(radars)  # גדלים
    states = [[0] * len(r["path"]) for r in rows]  # ברירת מחדל: מחוץ לטווח
    per_row = [{"tk": 0, "dt": 0, "ft": None, "ws": None, "by": 0} for _ in rows]  # מדדים לכל מסלול
    stats, mode = [], "detection"  # סטטיסטיקה לכל מכ"ם; מצב הבדיקה
    t0, total = time.time(), max(1, n_rows * n_rad)  # להערכת זמן
    for ri, rd in enumerate(radars):  # כל מכ"ם
        mode = rd["cfg"][0]  # 'detection' / 'track' (אותו מצב לכל המכ"מים — מטאב המעקב)
        st = {"name": rd["name"], "tracked": 0, "detected": 0, "error": None}  # סטטיסטיקה
        ground = fetch([(round(rd["lat"], 6), round(rd["lon"], 6))])[0]  # גובה המכ"ם — פעם אחת לפני הלולאה
        if ground is None:  # אין גובה (למשל בים) — אי אפשר לחשב מכ"ם הזה
            st["error"] = "אין גובה קרקע למיקום המכ\"ם"  # הסבר
            stats.append(st)  # נרשם
            continue  # המכ"ם הבא
        radar = {"lat": rd["lat"], "lon": rd["lon"], "h_msl": ground + rd["p"]["h_antenna"]}  # המכ"ם: קרקע + אנטנה (כמו run_check)
        p = dict(rd["p"], radar_h_msl=radar["h_msl"])  # הגשם צריך את גובה האנטנה (עותק, כמו run_check)
        if progress:  # מאזין
            progress({"stage": "track", "note": f"מתכנן דגימות שטח מול {rd['name']}…"})  # שלב התכנון
        all_pts = [{"lat": q[0], "lon": q[1], "alt": q[2]} for r in rows for q in r["path"]]  # כל נקודות הציור של כל המסלולים
        plan = rt.plan_terrain_samples(radar, all_pts, p["range_km"] * 1000.0, budget=AREA_TERRAIN_BUDGET, max_bins=AREA_MAX_AZ_BINS)  # תכנון אחד לכל המסלולים, פחים של רבע מעלה גם בגזרה רחבה
        profiles = rt.build_horizon_profiles(plan, fetch(plan["cells"]), radar["h_msl"])  # פרופילי אופק משותפים
        physics = rs.build_physics(p)  # הפיזיקה (משוואת מכ"ם, ריבוד, דופלר) — אחת לכל מכ"ם
        track_mode, scan, track = rd["cfg"]  # מצב גילוי/מעקב, סריקה ופרמטרי מעקב
        for i, r in enumerate(rows):  # כל מסלול
            if i % 200 == 0:  # מדי פעם — התקדמות, הערכת זמן, בדיקת ביטול
                if cancelled and cancelled():  # בוטל
                    raise area_fire.Aborted()  # עצירה
                done = ri * n_rows + i  # כמה בדיקות הושלמו
                el = time.time() - t0  # זמן שעבר
                if progress:  # מאזין
                    progress({"stage": "track", "note": f"בדיקת מעקב מלאה מול {rd['name']}: {i:,}/{n_rows:,}",  # התקדמות
                              "eta_total_s": round(el / done * (total - done)) if done >= 200 and el > 1 else None})  # זמן שנותר לכל הבדיקה
            traj = [{"t": q[3], "lat": q[0], "lon": q[1], "alt": q[2]} for q in r["path"] if len(q) > 3]  # המסלול עם הזמן (מטבלת הירי)
            if len(traj) < 2:  # שורה בלי זמן (לא אמור לקרות)
                continue  # מדלגים
            try:
                dense = rs.prepare_trajectory(traj, "msl", fetch)  # ניקוי וציפוף לנקודה כל שנייה (כמו run_check)
            except ValueError:  # מסלול לא תקין לבדיקה
                continue  # הבא
            pts = rt.evaluate_points(dense, radar, p, physics, plan, profiles)  # ההערכה — אותה פונקציה כמו בבדיקת מסלול בודד
            res = {"summary": rt.summarize(pts), "track": None}  # הסיכום
            if track_mode == "track":  # מצב מעקב — סריקה ופתיחת מעקב (כמו run_check)
                trk = rt.run_track_logic(pts, scan, track)  # לוגיקת המעקב
                for r_, s_ in zip(pts, rt.track_states(pts, trk["tracks"])):  # מצב-מעקב לכל נקודה
                    r_["track_state"] = s_  # לצביעה
                res["track"] = rt.summarize_track(pts, trk, [r_.get("track_state") for r_ in pts])  # מדדים
            times = [p["t"] for p in pts]  # זמנים
            for k, q in enumerate(r["path"]):  # כל נקודת ציור
                c = point_code(pts[rt._nearest_index(times, q[3])])  # המצב בנקודה הקרובה בזמן
                if c > states[i][k]:  # טוב יותר מהמכ"מים הקודמים
                    states[i][k] = c  # הטוב ביותר
            pr, trk, sm = per_row[i], res.get("track"), res["summary"]  # מדדי המסלול
            detected = bool(sm.get("detected_any"))  # זוהה לפחות פעם אחת
            tracked = bool(trk and trk.get("track_initiated")) if mode == "track" else detected  # נפתח מעקב (במצב גילוי — זוהה)
            if detected:  # זוהה
                pr["dt"] = 1; pr["by"] |= (1 << ri); st["detected"] += 1  # נרשם
            if tracked:  # במעקב
                pr["tk"] = 1; st["tracked"] += 1  # נרשם
                ft = trk.get("first_track_t") if trk else (sm.get("first_detection") or {}).get("t")  # זמן מעקב/גילוי ראשון
                ws = trk.get("warning_time_s") if trk else None  # זמן התרעה
                if ft is not None and (pr["ft"] is None or ft < pr["ft"]):  # המוקדם מכל המכ"מים
                    pr["ft"] = round(ft, 1)  # שמירה
                if ws is not None and (pr["ws"] is None or ws > pr["ws"]):  # הארוך מכל המכ"מים
                    pr["ws"] = round(ws, 1)  # שמירה
        stats.append(st)  # הסטטיסטיקה של המכ"ם
    counts = [0] * len(CODES)  # נקודות לפי מצב
    for s in states:  # כל מסלול
        for c in s:  # כל נקודה
            counts[c] += 1  # ספירה
    return {"mode": "full", "track_mode": mode, "codes": CODES, "states": states, "rows": per_row,  # התוצאה
            "radars": stats,  # שמות וסטטיסטיקה (לפי סדר הביטים ב-by)
            "summary": {"radars": len([s for s in stats if not s["error"]]), "trajectories": n_rows,  # גדלים
                        "trajectories_tracked": sum(p["tk"] for p in per_row), "trajectories_detected": sum(p["dt"] for p in per_row),  # כמה במעקב / זוהו
                        "trajectories_unseen": sum(1 for p in per_row if not p["dt"]), "points_by_state": dict(zip(CODES, counts)),  # לא זוהו; נקודות לפי מצב
                        "cells": len(memo), "elapsed_s": round(time.time() - t0, 1)}}  # תאי שטח וזמן ריצה
