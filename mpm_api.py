# -*- coding: utf-8 -*-
"""
mpm_api.py — שכבת-API אחת לכלי "מסלול בליסטי (MPM)", לפי טבלת הפעולות בפרומפט המקורי
(trajectory/solve/solve_mv/terrain_check/min_qe_for_crest/table/calibrate). כל פעולה מחזירה
dict שניתן ל-JSON. המנוע (mpm/) עצמו הוא stdlib-בלבד ו-platform-agnostic (ר' MAPS-GUI_SRS.md
FR-D-230) — המודול הזה הוא נקודת-הכניסה היחידה שגם weather_server.py (Desktop) וגם
web/api/ballistics.py (Web) קוראים לה, וגם Chaquopy (Android) מריץ אותה ישירות בתוך ה-APK
ללא שינוי (ר' FR-D-231 — החלטה א).

הזרקת-תלות מכוונת: terrain_check/min_qe_for_crest מקבלים פרמטר elevation_fetcher (קריאה
חזרה, לא import) במקום לייבא ישירות מ-weather_server.py — כך אין import מעגלי (weather_server
מייבא את המודול הזה, לא להפך), והמודול נשאר שמיש גם בלי Flask (Chaquopy/Android).
"""
import math  # טריגונומטריה להמרת מסלול מקומי (x,y,z) לנקודות גאוגרפיות

from mpm.atmosphere import AtmosphereProfile  # בניית פרופיל-מטאו (standard/from_levels)
from mpm.engine import FireParams, simulate, stability_warnings, R_EARTH  # ליבת הפיזיקה — ללא שינוי
from mpm.fire_control import (  # שכבת בקרת-האש — solve/solve_mv הורחבו ב-Stage 2, שאר הפונקציות ללא שינוי
    solve as _mpm_solve,
    solve_mv as _mpm_solve_mv,
    firing_table as _mpm_firing_table,
    calibrate as _mpm_calibrate,
    TABLE_COLUMNS,
    QE_MIN,
    QE_MAX,
)
from mpm.geodesy import direct as _geo_direct, inverse as _geo_inverse  # Vincenty — ללא שינוי
from mpm.projectile import load_projectile  # טעינת קובץ-פגז (ברירת מחדל: generic_155)
from mpm.units import angle_to_rad, both, mils_to_rad  # המרות-זווית — ללא שינוי

_DEFAULT_PROJECTILE = load_projectile()  # generic_155 — נטען פעם אחת בטעינת המודול


def default_projectile_summary():
    """לשימוש ה-API כש-caller לא מעביר קובץ-פגז משלו — כולל את אזהרת generic_155 (FR-D-230)."""
    return _DEFAULT_PROJECTILE.summary()


def _build_atmosphere(met, site_alt):
    """
    בונה AtmosphereProfile ממפרט met. תת-קבוצה מכוונת של met_sources.py::profile_from_spec
    המקורי — רק "standard"/"inline" (ר' FR-D-231: שליפת-הרשת האמיתית מ-Open-Meteo, או קריאת
    קובץ CSV/JSON שהועלה, קורית ב-weather_server.py *לפני* הקריאה לכאן, ומוזנת כ-"inline").
    met: {"source": "standard", "surface_temp_c"?, "surface_pressure_hpa"?, "wind_speed_mps"?, "wind_dir_deg"?}
       | {"source": "inline", "surface": {...}, "levels": [...], "description"?, "time_utc"?}
    """
    met = met or {"source": "standard"}  # ברירת מחדל: אטמוספרה סטנדרטית, בדיוק כמו ב-gui.py המקורי
    src = (met.get("source") or "standard").lower()
    if src == "standard":
        prof = AtmosphereProfile.standard(
            site_alt, met.get("surface_temp_c"), met.get("surface_pressure_hpa"),
            float(met.get("wind_speed_mps") or 0.0), float(met.get("wind_dir_deg") or 0.0))
        return prof, {"source": "standard"}
    if src == "inline":
        surface = dict(met["surface"])  # עותק — לא לשנות את ה-dict שהקורא מסר
        surface.setdefault("alt_m", site_alt)
        prof = AtmosphereProfile.from_levels(surface, met.get("levels", []), met.get("description", "Inline met"))
        return prof, {"source": "inline", "valid_time_utc": met.get("time_utc")}
    raise ValueError(f"מקור מטאו לא נתמך בשכבת ה-API: {src}")  # "csv"/"open-meteo" נופלים לכאן בכוונה


def _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt, qe=0.0, azimuth=0.0, target_alt=None):
    """בונה FireParams ממילון-תותח גאוגרפי (lat/lon/alt_m) ומקדמי-התאמה אופציונליים."""
    fitting = fitting or {}
    return FireParams(
        qe=qe, azimuth=azimuth, mv=float(mv), latitude=math.radians(float(gun["lat"])),
        gun_alt=float(gun["alt_m"]), target_alt=target_alt, dt=float(dt or 0.02),
        drag_factor=float(fitting.get("drag_factor", 1.0)), lift_factor=float(fitting.get("lift_factor", 1.0)),
        coriolis=bool(coriolis), earth_curvature=bool(earth_curvature),
    )


def _path_points(gun, fire_az_rad, traj_result, step=1):
    """
    ממיר נקודות-מסלול מקומיות (x,y,z של המנוע, ציר-x לאורך קו-הירי) לנקודות גאוגרפיות —
    בדיוק לפי הנוסחאות מהפרומפט המקורי (alt_msl עם תיקון-עקמומיות, קואורדינטה דרך geodesy.direct).
    """
    pts = []
    n = len(traj_result.t)
    for i in range(0, n, max(1, step)):
        x, y, z = traj_result.x[i], traj_result.y[i], traj_result.z[i]
        ground_dist = math.hypot(x, z)  # מרחק אופקי מהלוע לנקודה הזו, לאורך הקרקע המעוקלת
        bearing_deg = math.degrees(fire_az_rad) + math.degrees(math.atan2(z, x))  # אזימוט-ירי + סטייה-צידית
        lat, lon = _geo_direct(float(gun["lat"]), float(gun["lon"]), bearing_deg % 360.0, ground_dist)
        alt_msl = float(gun["alt_m"]) + y + (x * x + z * z) / (2.0 * R_EARTH)  # נוסחת-העקמומיות מהפרומפט
        pts.append({
            "t": round(traj_result.t[i], 3), "lat": round(lat, 7), "lon": round(lon, 7),
            "alt_msl": round(alt_msl, 1), "ground_dist": round(ground_dist, 1),
            "v": round(traj_result.vel[i], 1), "mach": round(traj_result.mach[i], 3),
            "spin": round(traj_result.spin[i] / (2.0 * math.pi), 1),  # rad/s -> rev/s, עקבי עם spin_*_rps
            "yaw_repose": round(math.degrees(traj_result.yaw_repose[i]), 2),  # מעלות (ציר-יחיד, לא "both")
        })
    # נקודת-הפגיעה המדויקת (אינטרפולציה בתוך simulate) חסרה אם step>1 לא נחת עליה בדיוק — מוסיפים אותה
    last = pts[-1] if pts else None
    if traj_result.ok and (last is None or abs(last["t"] - traj_result.t[-1]) > 1e-9):
        i = -1
        x, y, z = traj_result.x[i], traj_result.y[i], traj_result.z[i]
        ground_dist = math.hypot(x, z)
        bearing_deg = math.degrees(fire_az_rad) + math.degrees(math.atan2(z, x))
        lat, lon = _geo_direct(float(gun["lat"]), float(gun["lon"]), bearing_deg % 360.0, ground_dist)
        alt_msl = float(gun["alt_m"]) + y + (x * x + z * z) / (2.0 * R_EARTH)
        pts.append({
            "t": round(traj_result.t[i], 3), "lat": round(lat, 7), "lon": round(lon, 7),
            "alt_msl": round(alt_msl, 1), "ground_dist": round(ground_dist, 1),
            "v": round(traj_result.vel[i], 1), "mach": round(traj_result.mach[i], 3),
            "spin": round(traj_result.spin[i] / (2.0 * math.pi), 1),
            "yaw_repose": round(math.degrees(traj_result.yaw_repose[i]), 2),
        })
    return pts


def trajectory(gun, qe, azimuth, mv, met=None, target_alt=None, fitting=None, angle_unit="mils",
               coriolis=True, earth_curvature=True, dt=0.02, include_path=True, path_step=10, projectile=None):
    """פעולת trajectory — מסלול בודד. qe/azimuth ביחידת angle_unit; שאר הפרמטרים לפי טבלת הפעולות."""
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    qe_rad = angle_to_rad(qe, angle_unit)
    az_rad = angle_to_rad(azimuth, angle_unit)
    talt = float(target_alt) if target_alt is not None else None
    fp = _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt, qe=qe_rad, azimuth=az_rad, target_alt=talt)
    res = simulate(proj, atmo, fp, record=True)
    out = {"ok": res.ok, "message": res.message, "met_used": met_meta, "projectile": proj.summary(),
           "qe": both(qe_rad), "fire_azimuth": both(az_rad)}
    if res.ok:
        out["impact"] = res.impact
        out["warnings"] = stability_warnings(res)
        if include_path:
            out["path"] = _path_points(gun, az_rad, res, step=max(1, int(path_step or 1)))
    return out


def solve(gun, target, mv, met=None, fitting=None, angle_unit="mils", coriolis=True, earth_curvature=True,
          dt=0.02, group="low", qe_min=None, qe_max=None, include_path=True, path_step=10, projectile=None):
    """
    פעולת solve. target: {"lat","lon","alt_m"} או {"range_m","azimuth","alt_m"} (azimuth ביחידת angle_unit).
    group: "low"/"high"/"both" — "both" מריץ את שני הענפים ומחזיר את שניהם אם שניהם נמצאו.
    qe_min/qe_max (אופציונלי, ביחידת angle_unit) — תחום-הגבהות מותר, ר' FR-D-234 ב-fire_control.solve.
    """
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    if "lat" in target and "lon" in target:
        rng_m, az_deg = _geo_inverse(float(gun["lat"]), float(gun["lon"]), float(target["lat"]), float(target["lon"]))
        az_rad = math.radians(az_deg)
    else:
        rng_m = float(target["range_m"])
        az_rad = angle_to_rad(target["azimuth"], angle_unit)
    talt = float(target.get("alt_m")) if target.get("alt_m") is not None else None
    fp = _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt)
    qe_min_rad = angle_to_rad(qe_min, angle_unit) if qe_min is not None else None
    qe_max_rad = angle_to_rad(qe_max, angle_unit) if qe_max is not None else None

    def _run_group(g):
        r = _mpm_solve(proj, atmo, fp, rng_m, az_rad, talt, g, qe_min=qe_min_rad, qe_max=qe_max_rad)
        if r.get("ok") and include_path:
            traj = r.pop("_trajectory", None)
            if traj is not None:
                r["path"] = _path_points(gun, angle_to_rad(r["fire_azimuth"]["mils"], "mils"), traj,
                                          step=max(1, int(path_step or 1)))
        else:
            r.pop("_trajectory", None)
        return r

    if group == "both":
        low, high = _run_group("low"), _run_group("high")
        return {"ok": low.get("ok") or high.get("ok"), "met_used": met_meta, "projectile": proj.summary(),
                "low": low, "high": high}
    out = _run_group(group)
    out["met_used"] = met_meta
    out["projectile"] = proj.summary()
    return out


def solve_mv(gun, target, qe, mv_min, mv_max, met=None, fitting=None, angle_unit="mils", coriolis=True,
             earth_curvature=True, dt=0.02, include_path=True, path_step=10, projectile=None):
    """פעולת solve_mv — הגבהה קבועה (qe), מחשב V0 נדרש בתחום [mv_min, mv_max]."""
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    if "lat" in target and "lon" in target:
        rng_m, az_deg = _geo_inverse(float(gun["lat"]), float(gun["lon"]), float(target["lat"]), float(target["lon"]))
        az_rad = math.radians(az_deg)
    else:
        rng_m = float(target["range_m"])
        az_rad = angle_to_rad(target["azimuth"], angle_unit)
    talt = float(target.get("alt_m")) if target.get("alt_m") is not None else None
    qe_rad = angle_to_rad(qe, angle_unit)
    fp = _fire_params(gun, mv_min, fitting, coriolis, earth_curvature, dt)  # mv בפועל מוחלף בתוך solve_mv
    out = _mpm_solve_mv(proj, atmo, fp, rng_m, az_rad, qe_rad, float(mv_min), float(mv_max), target_alt=talt)
    if out.get("ok") and include_path:
        traj = out.pop("_trajectory", None)
        if traj is not None:
            out["path"] = _path_points(gun, angle_to_rad(out["fire_azimuth"]["mils"], "mils"), traj,
                                       step=max(1, int(path_step or 1)))
    else:
        out.pop("_trajectory", None)
    out["met_used"] = met_meta
    out["projectile"] = proj.summary()
    return out


def table(gun, azimuth, qe_start, qe_end, qe_step, mv, met=None, fitting=None, angle_unit="mils",
          coriolis=True, earth_curvature=True, dt=0.02, projectile=None):
    """פעולת table — טבלת ירי. עמודות לפי mpm.fire_control.TABLE_COLUMNS."""
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    az_rad = angle_to_rad(azimuth, angle_unit)
    fp = _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt, azimuth=az_rad)
    a, b, st = angle_to_rad(qe_start, angle_unit), angle_to_rad(qe_end, angle_unit), angle_to_rad(qe_step, angle_unit)
    if st <= 0 or b < a:
        return {"ok": False, "error": "טווח זוויות לא תקין"}
    if (b - a) / st > 400:
        return {"ok": False, "error": "יותר מ-400 שורות — הגדל את הצעד"}
    rows, warns = _mpm_firing_table(proj, atmo, fp, a, b, st)
    return {"ok": True, "columns": TABLE_COLUMNS, "rows": rows, "warnings": warns,
            "met_used": met_meta, "projectile": proj.summary()}


def calibrate(gun, mv, points, met=None, fitting=None, angle_unit="mils", coriolis=True,
              earth_curvature=True, dt=0.02, projectile=None):
    """
    פעולת calibrate. points: [{"qe","azimuth","range_m","drift"?,"target_alt"?}] — qe/azimuth/drift
    ביחידת angle_unit (drift מומר למילים בתוך mpm.fire_control.calibrate, כמו ב-gui.py המקורי).
    """
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    fp = _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt)
    pts = []
    for p in points:
        d = {"qe": angle_to_rad(p["qe"], angle_unit), "azimuth": angle_to_rad(p["azimuth"], angle_unit),
             "range_m": float(p["range_m"])}
        if p.get("drift") is not None:
            d["drift_mils"] = float(p["drift"]) if angle_unit == "mils" else float(p["drift"]) * 6400.0 / 360.0
        if p.get("target_alt") is not None:
            d["target_alt"] = float(p["target_alt"])
        pts.append(d)
    out = _mpm_calibrate(proj, atmo, fp, pts)
    out["met_used"] = met_meta
    return out


def terrain_check(path, elevation_fetcher, safety_margin_m=0.0, resolution_m=75.0, batch_size=100,
                  batch_pause_fn=None):
    """
    פעולת terrain_check. path — רשימת נקודות (כמו שמוחזר מ-trajectory()/solve()["path"]), כבר
    בקואורדינטות-המסלול האמיתיות (לא קו-ישר לתותח). דוגם מחדש ברזולוציית resolution_m [מ'] לאורך
    ground_dist (לא כל נקודת-אינטגרציה — מונע הצפת שירות-הגובה), שולף גבהים ב-batches של עד
    batch_size (מגבלת Open-Meteo), ומשווה אל alt_msl-safety_margin_m.
    elevation_fetcher(list[{"lat","lon"}]) -> (list[float|None], error_dict|None) — מוזרק מבחוץ
    (ב-weather_server.py/web זה _fetch_elevations הקיים; ר' docstring המודול).
    """
    if not path:
        return {"ok": False, "error": "אין נתוני מסלול לבדיקה"}
    sampled = [path[0]]  # הלוע נבדק תמיד
    next_mark = resolution_m
    for p in path[1:]:
        if p["ground_dist"] >= next_mark:
            sampled.append(p)
            next_mark += resolution_m
    if sampled[-1] is not path[-1]:
        sampled.append(path[-1])  # נקודת-הפגיעה נבדקת תמיד, גם אם לא מדויקת על רשת הרזולוציה
    elevations = [None] * len(sampled)
    for start in range(0, len(sampled), batch_size):
        chunk = sampled[start:start + batch_size]
        locs = [{"lat": p["lat"], "lon": p["lon"]} for p in chunk]
        elevs, err = elevation_fetcher(locs)
        if err:
            return {"ok": False, "error": err.get("error", "שגיאה בשליפת גבהים לבדיקת כיסוי-שטח")}
        elevations[start:start + len(chunk)] = elevs
        if batch_pause_fn is not None and start + batch_size < len(sampled):
            batch_pause_fn()  # השהיה בין batches, כמו בכל שאר הכלים הקיימים (לא לפני ה-batch הראשון)
    profile = []
    min_margin = None
    first_collision = None
    for p, gelev in zip(sampled, elevations):
        if gelev is None:
            continue  # נקודה שנכשלה בשליפה — מדלגים, לא מפילים את כל הבדיקה
        margin = p["alt_msl"] - safety_margin_m - gelev
        profile.append({"ground_dist": p["ground_dist"], "lat": p["lat"], "lon": p["lon"],
                        "traj_alt_msl": p["alt_msl"], "ground_alt_msl": round(gelev, 1), "margin_m": round(margin, 1)})
        if min_margin is None or margin < min_margin:
            min_margin = margin
        if margin < 0 and first_collision is None:
            first_collision = {"ground_dist": p["ground_dist"], "lat": p["lat"], "lon": p["lon"],
                               "traj_alt_msl": p["alt_msl"], "ground_alt_msl": round(gelev, 1)}
    return {"ok": True, "clear": first_collision is None,
            "min_margin_m": round(min_margin, 1) if min_margin is not None else None,
            "first_collision": first_collision, "profile": profile}


def min_qe_for_crest(gun, target, mv, elevation_fetcher, met=None, fitting=None, angle_unit="mils",
                     coriolis=True, earth_curvature=True, dt=0.05, safety_margin_m=0.0,
                     resolution_m=100.0, qe_step_mils=10.0, projectile=None):
    """
    פעולת min_qe_for_crest. שימוש: לחצן "הגבהה מינימלית לכיסוי שטח" (שלב 3) — מציב את התוצאה
    כ-qe_min לפתרון-ירי. גישה (לא קיימת בחבילה המקורית — ר' FR-D-230, זה הרחבה חדשה):
    עבור mv/azimuth נתונים (אזימוט ישיר למטרה, בלי תיקון-סחיפה — קירוב סביר לסריקה הזו), סורקים
    QE מ-QE_MIN מעלה; לכל QE מריצים מסלול בודד ובודקים terrain_check על החלק שמגיע עד למרחק-המטרה.
    "עובר" = מגיע לפחות למרחק-המטרה (אחרת לא רלוונטי כלל) וללא התנגשות. מניחים (לא מוכח פורמלית,
    אך פיזיקלית סביר) שמעבר-הקרקע משתפר מונוטונית עם QE בתחום הזה — בי-סקציה בין QE חסום
    ל-QE עובר שנמצאו בסריקה גסה ראשונית; אם שום QE בסריקה הגסה לא עובר, מוחזר "לא נמצא".
    """
    proj = projectile or _DEFAULT_PROJECTILE
    atmo, met_meta = _build_atmosphere(met, float(gun["alt_m"]))
    if "lat" in target and "lon" in target:
        rng_m, az_deg = _geo_inverse(float(gun["lat"]), float(gun["lon"]), float(target["lat"]), float(target["lon"]))
    else:
        rng_m, az_deg = float(target["range_m"]), math.degrees(angle_to_rad(target["azimuth"], angle_unit))
    az_rad = math.radians(az_deg)
    talt = float(target.get("alt_m")) if target.get("alt_m") is not None else None
    fp = _fire_params(gun, mv, fitting, coriolis, earth_curvature, dt, azimuth=az_rad, target_alt=talt)

    def _try(qe_rad):
        """מריץ מסלול ב-QE נתון, בודק שמגיע לפחות למרחק-המטרה, ואם כן — terrain_check עד שם."""
        res = simulate(proj, atmo, replace_fp(fp, qe_rad), record=True)
        if not res.ok or res.ground_range < rng_m - 1.0:
            return False, None  # לא מגיע כלל למרחק המטרה בזווית הזו — לא רלוונטי
        path = _path_points(gun, az_rad, res, step=1)
        path_to_target = [p for p in path if p["ground_dist"] <= rng_m + resolution_m]
        tc = terrain_check(path_to_target, elevation_fetcher, safety_margin_m, resolution_m)
        return bool(tc.get("ok") and tc.get("clear")), tc

    step = mils_to_rad(qe_step_mils) if angle_unit == "mils" else angle_to_rad(qe_step_mils, angle_unit)
    q = QE_MIN
    last_blocked_q, last_blocked_tc = None, None
    found_q, found_tc = None, None
    while q <= QE_MAX:
        ok, tc = _try(q)
        if ok:
            found_q, found_tc = q, tc
            break
        last_blocked_q, last_blocked_tc = q, tc
        q += step
    if found_q is None:
        return {"ok": False, "error": "לא נמצאה הגבהה שמכסה את השטח בתחום הזוויות שנסרק",
                "last_checked": last_blocked_tc}
    lo, hi = (last_blocked_q if last_blocked_q is not None else QE_MIN), found_q
    for _ in range(20):  # בי-סקציה לדיוק תת-צעד-הסריקה
        mid = 0.5 * (lo + hi)
        ok, tc = _try(mid)
        if ok:
            hi, found_q, found_tc = mid, mid, tc
        else:
            lo = mid
        if (hi - lo) < mils_to_rad(0.2):
            break
    return {"ok": True, "qe_min": both(found_q), "terrain_check": found_tc,
            "met_used": met_meta, "projectile": proj.summary()}


def replace_fp(fp, qe):
    """עזר קטן — dataclasses.replace בלי לייבא dataclasses בכל קורא (נוח ל-min_qe_for_crest בלבד)."""
    from dataclasses import replace
    return replace(fp, qe=qe)


# ============================================================================
# Android/Chaquopy בלבד (Stage 3, FR-D-237): ל-Android אין weather_server.py שמספק
# elevation_fetcher/met-חי — אין Flask על המכשיר. urllib (stdlib, לא pip חדש כדי לשמור
# על Chaquopy קל) קורא ל-Open-Meteo *ישירות מתוך הקוד הפייתוני הרץ ב-APK* — זה עצמו עקבי
# עם החלטה א (Chaquopy מריץ Python אמיתי, כולל רשת, לא רק חישוב) ועם התקדים הקיים ב-Android
# (api_service.dart כבר קורא ל-Open-Meteo ישירות ללא שרת-ביניים לכלים אחרים).
# ============================================================================
import json as _json  # noqa: E402 — ייבוא מאוחר בכוונה, רק לקוד ה-Android בסוף הקובץ
import urllib.error as _urlerror  # noqa: E402
import urllib.parse as _urlparse  # noqa: E402
import urllib.request as _urlrequest  # noqa: E402


def default_elevation_fetcher(locations):
    """elevation_fetcher ברירת-מחדל ל-Android — זהה בתפיסה ל-weather_server.py::_fetch_elevations
    אך עם urllib במקום requests (Chaquopy, בלי תלות-pip חדשה). עד 100 נקודות (מגבלת Open-Meteo)."""
    lats = ",".join(str(p["lat"]) for p in locations)
    lons = ",".join(str(p["lon"]) for p in locations)
    url = "https://api.open-meteo.com/v1/elevation?" + _urlparse.urlencode({"latitude": lats, "longitude": lons})
    # F-016 (QA engagement): הגנת-הגנה-לעומק נגד bandit B310 (urlopen scheme לא-מאומת) - raise ולא assert
    # כי assert נמחק תחת python -O, ולא היה מגן בפועל בסביבת-ריצה כזו.
    if not url.startswith("https://"):
        raise ValueError(f"scheme לא-מאובטח ב-URL: {url!r}")
    try:
        # scheme כבר אומת למעלה (F-016, QA engagement) - bandit B310 לא עושה ניתוח-זרימת-נתונים
        # ומסמן כל urlopen גורף, ללא קשר לבדיקה שקדמה לו; nosec מתועד בכוונה, לא התעלמות-סתמית.
        with _urlrequest.urlopen(url, timeout=30) as r:  # nosec B310
            elevs = _json.loads(r.read().decode("utf-8")).get("elevation", [])
        return [elevs[i] if i < len(elevs) else None for i in range(len(locations))], None
    except (_urlerror.URLError, _urlerror.HTTPError) as e:
        return None, {"error": str(e)}


_ANDROID_PRESSURE_LEVELS_HPA = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30]
# זהה בדיוק לרשימה ב-weather_server.py/web/api/ballistics.py — ר' ההערה המקבילה שם


def _default_fetch_met_live(lat, lon, alt_m):
    """met="live" ל-Android — זהה בתפיסה ל-weather_server.py::_fetch_met_profile_live, urllib במקום requests.
    מחזיר met-dict מוכן ל-_build_atmosphere (מצב "inline"), או None+error."""
    hourly = ["temperature_2m", "surface_pressure", "wind_speed_10m", "wind_direction_10m"]
    for p in _ANDROID_PRESSURE_LEVELS_HPA:
        hourly += [f"temperature_{p}hPa", f"wind_speed_{p}hPa", f"wind_direction_{p}hPa", f"geopotential_height_{p}hPa"]
    params = {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "hourly": ",".join(hourly), "wind_speed_unit": "ms", "timezone": "UTC"}
    url = "https://api.open-meteo.com/v1/forecast?" + _urlparse.urlencode(params)
    # F-016 (QA engagement): הגנת-הגנה-לעומק נגד bandit B310 (urlopen scheme לא-מאומת) - raise ולא assert
    # כי assert נמחק תחת python -O, ולא היה מגן בפועל בסביבת-ריצה כזו.
    if not url.startswith("https://"):
        raise ValueError(f"scheme לא-מאובטח ב-URL: {url!r}")
    try:
        # scheme כבר אומת למעלה (F-016, QA engagement) - bandit B310 לא עושה ניתוח-זרימת-נתונים
        # ומסמן כל urlopen גורף, ללא קשר לבדיקה שקדמה לו; nosec מתועד בכוונה, לא התעלמות-סתמית.
        with _urlrequest.urlopen(url, timeout=30) as r:  # nosec B310
            d = _json.loads(r.read().decode("utf-8"))
    except (_urlerror.URLError, _urlerror.HTTPError) as e:
        return None, {"error": str(e)}
    H = d.get("hourly") or {}
    times = H.get("time") or []
    if not times:
        return None, {"error": "לא התקבלו נתוני מטאו"}
    i = 0

    def val(key):
        v = H.get(key)
        return None if v is None else v[i]

    elev = float(d.get("elevation") or 0.0)
    surface = {"alt_m": elev, "temp_c": val("temperature_2m"), "pressure_hpa": val("surface_pressure"),
               "wind_speed_mps": val("wind_speed_10m") or 0.0, "wind_dir_deg": val("wind_direction_10m") or 0.0}
    if surface["temp_c"] is None or surface["pressure_hpa"] is None:
        return None, {"error": "חסרים נתוני-קרקע בתחזית"}
    levels = []
    for p in _ANDROID_PRESSURE_LEVELS_HPA:
        h, t = val(f"geopotential_height_{p}hPa"), val(f"temperature_{p}hPa")
        ws, wd = val(f"wind_speed_{p}hPa"), val(f"wind_direction_{p}hPa")
        if None in (h, t) or h <= elev + 10:
            continue
        levels.append({"height_m": h, "temp_c": t, "wind_speed_mps": ws or 0.0, "wind_dir_deg": wd or 0.0})
    if alt_m is not None and abs(float(alt_m) - elev) > 1.0:
        dz = float(alt_m) - elev
        T = surface["temp_c"] + 273.15
        surface["pressure_hpa"] = surface["pressure_hpa"] * math.exp(-9.80665 * dz / (287.05 * (T - 0.00325 * dz)))
        surface["temp_c"] = surface["temp_c"] - 0.0065 * dz
        surface["alt_m"] = float(alt_m)
    return {"source": "inline", "surface": surface, "levels": levels, "time_utc": times[0],
            "description": f"Open-Meteo {times[0]} UTC"}, None


def _resolve_met_for_android(params):
    """מחליף met={{"source":"live"}} ב-met={{"source":"inline",...}} בתוך params, לפני קריאה לפונקציית
    ה-API — זהה בתפקיד ל-weather_server.py::_resolve_ballistics_met, בלי Flask."""
    met = params.get("met")
    if not met or (met.get("source") or "").lower() not in ("live", "open-meteo", "openmeteo"):
        return params, None
    gun = params.get("gun") or {}
    resolved, err = _default_fetch_met_live(float(gun["lat"]), float(gun["lon"]), gun.get("alt_m"))
    if err:
        return None, err
    params = dict(params)
    params["met"] = resolved
    return params, None


def dispatch_json(action, params_json):
    """
    נקודת-הכניסה היחידה שה-bridge ב-Android (Kotlin, MainActivity.kt) קורא לה דרך Chaquopy —
    מחרוזת-JSON אחת נכנסת, מחרוזת-JSON אחת חוזרת (בדיוק כמו כל /ballistics/* ב-weather_server.py,
    רק בלי Flask). action תואם לשם-הפעולה (trajectory/solve/solve_mv/table/calibrate/
    terrain_check/min_qe_for_crest); params תואמים 1:1 לפרמטרי הפונקציה המתאימה למעלה.
    """
    try:
        params = _json.loads(params_json)
        if action != "terrain_check":  # terrain_check לא מקבל gun/met כלל — אין מה לפענח
            params, met_err = _resolve_met_for_android(params)
            if met_err:
                return _json.dumps({"ok": False, "error": met_err.get("error", "שגיאת מטאו")})
        fn = {"trajectory": trajectory, "solve": solve, "solve_mv": solve_mv, "table": table,
              "calibrate": calibrate}.get(action)
        if fn is not None:
            return _json.dumps(fn(**params))
        if action == "terrain_check":
            return _json.dumps(terrain_check(params["path"], default_elevation_fetcher,
                                              safety_margin_m=params.get("safety_margin_m", 0.0),
                                              resolution_m=params.get("resolution_m", 75.0)))
        if action == "min_qe_for_crest":
            params = dict(params)
            params.pop("elevation_fetcher", None)  # לעולם לא מגיע מ-JSON — מוזרק כאן, לא מהקריאה
            return _json.dumps(min_qe_for_crest(elevation_fetcher=default_elevation_fetcher, **params))
        return _json.dumps({"ok": False, "error": f"פעולה לא מוכרת: {action}"})
    except Exception as e:  # noqa: BLE001 — גבול-API ל-Kotlin; כל חריגה חייבת לחזור כ-JSON תקין, לא לקרוס את ה-bridge
        return _json.dumps({"ok": False, "error": f"שגיאה בצד Python: {e}"})
