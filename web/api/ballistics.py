# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
ballistics.py — Blueprint ל-7 פעולות כלי "מסלול בליסטי (MPM)" (Stage 2, FR-D-234,
ר' MAPS-GUI_SRS.md §3.27). עוטף את mpm_api.py (שורש-הפרויקט, משותף ל-Desktop+Web) ב-HTTP,
אותה גישה בדיוק כמו weather.py הקיים (Blueprint, לא Flask(__name__) עצמאי — ר' FLASK_ENTRYPOINT_NOT_FOUND
ב-MAPS-GUI_SRS.md §3.26). ה-routes וההתנהגות כאן זהים-בכוונה ל-weather_server.py (Desktop) —
אותו קוד, רק משטח-ה-HTTP משוכפל (כמו weather.py עצמו משוכפל מ-weather_server.py).
"""
import os  # איתור שורש-הפרויקט (מעל web/) כדי לייבא את mpm_api.py/mpm/
import sys  # הוספת שורש-הפרויקט ל-sys.path
import math  # חישובי עקמומיות/טריגונומטריה בהתאמת-הקרקע לגובה-הלוע
import time  # השהיה בין batches (זהה ל-_RADIAL_BATCH_PAUSE_SEC ב-weather.py)

from flask import Blueprint, jsonify, request  # Blueprint — לא Flask() נפרד, ר' docstring למעלה
import requests  # קריאת-רשת ל-Open-Meteo (שכבות-מטאו חיות)

# שורש-הפרויקט (תיקייה אחת מעל web/) — שם חיים mpm/ ו-mpm_api.py, משותפים ל-Desktop+Web
_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, _PROJECT_ROOT)
import mpm_api  # noqa: E402 — אחרי שינוי sys.path, בכוונה (אותו mpm_api.py בדיוק כמו ב-Desktop)

# weather.py הוא מודול-אח באותה תיקייה (web/api/), כבר על sys.path דרך web/app.py —
# שימוש-חוזר ב-_fetch_elevations/_RADIAL_BATCH_PAUSE_SEC הקיימים שם, לא שכפול שלהם
from weather import _fetch_elevations, _RADIAL_BATCH_PAUSE_SEC  # noqa: E402

ballistics_bp = Blueprint('ballistics', __name__)

_BALLISTICS_PRESSURE_LEVELS_HPA = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30]
# זהה בדיוק לרשימה ב-weather_server.py (Desktop) — ר' ההערה המקבילה שם


def _fetch_met_profile_live(lat, lon, alt_m, when_iso=None):
    """זהה ל-weather_server.py::_fetch_met_profile_live (Desktop) — ר' ההערות המלאות שם."""
    hourly = ["temperature_2m", "surface_pressure", "wind_speed_10m", "wind_direction_10m"]
    for p in _BALLISTICS_PRESSURE_LEVELS_HPA:
        hourly += [f"temperature_{p}hPa", f"wind_speed_{p}hPa", f"wind_direction_{p}hPa", f"geopotential_height_{p}hPa"]
    params = {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "hourly": ",".join(hourly),
              "wind_speed_unit": "ms", "timezone": "UTC"}
    if when_iso:
        params["start_hour"] = when_iso
        params["end_hour"] = when_iso
    for attempt in range(3):
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
            if r.status_code == 429:
                reason = r.json().get("reason", "מכסת בקשות Open-Meteo הגיעה למגבלה")
                return None, None, {"error": reason, "rate_limited": True}
            r.raise_for_status()
            d = r.json()
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
            else:
                return None, None, {"error": str(e)}
        except Exception as e:
            return None, None, {"error": str(e)}
    H = d.get("hourly") or {}
    times = H.get("time") or []
    if not times:
        return None, None, {"error": "לא התקבלו נתוני מטאו לשעה המבוקשת"}
    i = 0

    def val(key):
        v = H.get(key)
        return None if v is None else v[i]

    elev = float(d.get("elevation") or 0.0)
    surface = {"alt_m": elev, "temp_c": val("temperature_2m"), "pressure_hpa": val("surface_pressure"),
               "wind_speed_mps": val("wind_speed_10m") or 0.0, "wind_dir_deg": val("wind_direction_10m") or 0.0}
    if surface["temp_c"] is None or surface["pressure_hpa"] is None:
        return None, None, {"error": "חסרים נתוני-קרקע בתחזית"}
    levels = []
    for p in _BALLISTICS_PRESSURE_LEVELS_HPA:
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
    meta = {"source": "open-meteo", "valid_time_utc": times[0], "levels": len(levels)}
    return surface, levels, meta


def _resolve_ballistics_met(met, gun):
    """זהה ל-weather_server.py::_resolve_ballistics_met (Desktop) — ר' ההערות המלאות שם."""
    met = met or {"source": "standard"}
    if (met.get("source") or "").lower() not in ("live", "open-meteo", "openmeteo"):
        return met, None
    surface, levels, meta_or_err = _fetch_met_profile_live(float(gun["lat"]), float(gun["lon"]), gun.get("alt_m"),
                                                           met.get("time_utc"))
    if surface is None:
        return None, meta_or_err
    return {"source": "inline", "surface": surface, "levels": levels, "time_utc": meta_or_err.get("valid_time_utc"),
            "description": f"Open-Meteo {meta_or_err.get('valid_time_utc', '')} UTC"}, None


def _ballistics_batch_pause():
    """זהה ל-weather_server.py::_ballistics_batch_pause — משתמש ב-_RADIAL_BATCH_PAUSE_SEC המיובא מ-weather.py."""
    time.sleep(_RADIAL_BATCH_PAUSE_SEC)


@ballistics_bp.route("/ballistics/trajectory", methods=["POST"])
def ballistics_trajectory():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.trajectory(body["gun"], body["qe"], body["azimuth"], body["mv"], met=met,
                                 target_alt=body.get("target_alt"), fitting=body.get("fitting"),
                                 angle_unit=body.get("angle_unit", "mils"), coriolis=body.get("coriolis", True),
                                 earth_curvature=body.get("earth_curvature", True), dt=body.get("dt", 0.02),
                                 include_path=body.get("include_path", True), path_step=body.get("path_step", 10))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/solve", methods=["POST"])
def ballistics_solve():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.solve(body["gun"], body["target"], body["mv"], met=met, fitting=body.get("fitting"),
                            angle_unit=body.get("angle_unit", "mils"), coriolis=body.get("coriolis", True),
                            earth_curvature=body.get("earth_curvature", True), dt=body.get("dt", 0.02),
                            group=body.get("group", "low"), qe_min=body.get("qe_min"), qe_max=body.get("qe_max"),
                            include_path=body.get("include_path", True), path_step=body.get("path_step", 10))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/solve_mv", methods=["POST"])
def ballistics_solve_mv():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.solve_mv(body["gun"], body["target"], body["qe"], body["mv_min"], body["mv_max"],
                               met=met, fitting=body.get("fitting"), angle_unit=body.get("angle_unit", "mils"),
                               coriolis=body.get("coriolis", True), earth_curvature=body.get("earth_curvature", True),
                               dt=body.get("dt", 0.02), include_path=body.get("include_path", True),
                               path_step=body.get("path_step", 10))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/table", methods=["POST"])
def ballistics_table():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.table(body["gun"], body["azimuth"], body["qe_start"], body["qe_end"], body["qe_step"],
                            body["mv"], met=met, fitting=body.get("fitting"), angle_unit=body.get("angle_unit", "mils"),
                            coriolis=body.get("coriolis", True), earth_curvature=body.get("earth_curvature", True),
                            dt=body.get("dt", 0.02))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/calibrate", methods=["POST"])
def ballistics_calibrate():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.calibrate(body["gun"], body["mv"], body["points"], met=met, fitting=body.get("fitting"),
                                angle_unit=body.get("angle_unit", "mils"), coriolis=body.get("coriolis", True),
                                earth_curvature=body.get("earth_curvature", True), dt=body.get("dt", 0.02))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/terrain_check", methods=["POST"])
def ballistics_terrain_check():
    body = request.get_json() or {}
    try:
        out = mpm_api.terrain_check(body["path"], _fetch_elevations, safety_margin_m=body.get("safety_margin_m", 0.0),
                                    resolution_m=body.get("resolution_m", 75.0), batch_pause_fn=_ballistics_batch_pause)
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400


@ballistics_bp.route("/ballistics/min_qe_for_crest", methods=["POST"])
def ballistics_min_qe_for_crest():
    body = request.get_json() or {}
    try:
        met, err = _resolve_ballistics_met(body.get("met"), body["gun"])
        if err:
            return jsonify(err), 502
        out = mpm_api.min_qe_for_crest(body["gun"], body["target"], body["mv"], _fetch_elevations, met=met,
                                       fitting=body.get("fitting"), angle_unit=body.get("angle_unit", "mils"),
                                       coriolis=body.get("coriolis", True),
                                       earth_curvature=body.get("earth_curvature", True),
                                       safety_margin_m=body.get("safety_margin_m", 0.0),
                                       resolution_m=body.get("resolution_m", 100.0))
        return jsonify(out)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": f"קלט לא תקין: {e}"}), 400
