# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
radar_service — צינורות העבודה של כלי בדיקת מעקב המכ"ם, משותפים לשרת (Desktop, weather_server.py) ולאפליקציה
(Android, radar_android.py דרך Chaquopy) — MAPS-GUI_SRS.md FR-D-281. הועבר מ-weather_server.py כמו שהוא.

כאן: קליטת פרמטרי הסריקה/המעקב והסביבה, בניית הפיזיקה המוזרקת למנוע, והצינורות המלאים — בדיקה (שלבים א1-א5),
פרופיל שטח לנקודה (א3) והצעת מיקום (ב'). שליפת הגבהים **מוזרקת** (fetch_cells): השרת מזריק שליפה עם מעקב
התקדמות ומטמון משלו, והאפליקציה — שליפה ישירה ל-Open-Meteo דרך urllib. stdlib בלבד.
"""

import math  # גיאומטריה

import radar_physics as rph  # נוסחאות המכ"ם (משותף)
import radar_placement as rpl  # הצעת מיקום (שלב ב')
import radar_track as rt  # מנוע הבדיקה (שלבים א1-א5)

MAX_TRACK_POINTS = 6000  # תקרת נקודות-מסלול בבקשה — מסלול MPM של ~100 שנ' בצעד 0.1 שנ' הוא ~1000
MAX_AGL_POINTS = 600  # תקרת קודקודים בגובה "מעל הקרקע" — כל קודקוד דורש שליפת גובה (מכסת Open-Meteo)


class Aborted(Exception):
    """נזרק מ-fetch_cells כשהשליפה בוטלה או נחסמה במכסה — הקורא כבר קבע את הסטטוס, אין מה לדווח."""


# ═══════════════════════════ קליטת פרמטרים ═══════════════════════════

def _clamp_getter(body):
    """מחזיר פונקציה שקוראת מספר מהגוף וצומדת לטווח; ערך לא מספרי -> ברירת המחדל (אותו דפוס כמו _parse_radar_common_params)."""
    def _f(name, default, lo, hi):  # מספר צמוד לטווח
        try:  # ערך לא מספרי -> ברירת מחדל
            return min(max(float(body.get(name, default)), lo), hi)  # צמידה
        except (TypeError, ValueError):  # לא מספר
            return default  # ברירת מחדל
    return _f  # הפונקציה


def parse_track_params(body):
    """פרמטרי שלב א2 (סריקה ומעקב). מחזיר (track_mode, scan, track)."""
    _f = _clamp_getter(body)  # קורא-מספרים
    track_mode = body.get('track_mode', 'track')  # 'detection' = שלב א1 בלבד; 'track' = עם סריקה ומעקב
    if track_mode not in ('detection', 'track'):  # ערך לא מוכר
        track_mode = 'track'  # ברירת מחדל
    mode = body.get('scan_mode', rt.SCAN_ROTATING)  # מצב הסריקה
    if mode not in (rt.SCAN_ROTATING, rt.SCAN_PHASED, rt.SCAN_TRACKER):  # ערך לא מוכר
        mode = rt.SCAN_ROTATING  # ברירת מחדל
    scan = {
        'mode': mode,  # מצב
        'rot_period_s': _f('rot_period_s', 4.0, 0.2, 60.0),  # זמן סיבוב אנטנה
        'phase_deg': _f('scan_phase_deg', 0.0, 0.0, 360.0) % 360.0,  # כיוון האלומה בתחילת המסלול
        'revisit_s': _f('revisit_s', 0.5, 0.02, 30.0),  # זמן ביקור במערך-מופע
        'track_rate_hz': _f('track_rate_hz', 10.0, 0.5, 100.0),  # קצב עדכון במכ"ם מעקב
        'max_ang_rate_dps': _f('max_ang_rate_dps', 30.0, 0.1, 360.0),  # קצב סיבוב מרבי של אנטנת המעקב
        'cue_delay_s': _f('cue_delay_s', 1.0, 0.0, 30.0),  # השהיית הכוונה
    }
    m = int(_f('track_m', 2, 1, 10))  # M — גילויים לפתיחת מעקב
    n = max(m, int(_f('track_n', 3, 1, 10)))  # N — חלון ההזדמנויות (לא קטן מ-M)
    track = {'m': m, 'n': n, 'coast_s': _f('coast_s', 8.0, 0.1, 120.0)}  # פרמטרי המעקב
    return track_mode, scan, track  # שלושתם


def parse_env_params(body):
    """שלב א5: RCS לפי זווית וגשם (ITU-R P.838-3), צמודים לטווחים סבירים."""
    _f = _clamp_getter(body)  # קורא-מספרים
    pol = {'h': 0.0, 'v': 90.0, 'c': 45.0}.get(body.get('polarization', 'h'), 0.0)  # קיטוב -> זווית τ לפי ההמלצה
    return {
        'rcs_mode': 'aspect' if body.get('rcs_mode') == 'aspect' else 'fixed',  # קבוע / לפי זווית
        'rcs_nose': _f('rcs_nose', 0.01, 0.0001, 10000.0),  # חרטום, מ"ר
        'rcs_side': _f('rcs_side', 0.05, 0.0001, 10000.0),  # צד
        'rcs_tail': _f('rcs_tail', 0.02, 0.0001, 10000.0),  # זנב
        'rain_rate_mmh': _f('rain_rate_mmh', 0.0, 0.0, 200.0),  # עוצמת גשם
        'rain_top_m': _f('rain_top_m', 3000.0, 100.0, 10000.0),  # תקרת הגשם
        'pol_tilt_deg': pol,  # קיטוב
    }


def parse_all(body):
    """כל הפרמטרים של בדיקה: (p עם env, track_cfg, alt_ref)."""
    p = rph._parse_radar_common_params(body)  # פרמטרי המכ"ם — אותה צמידה כמו בכלי הדופלר
    p['env'] = parse_env_params(body)  # RCS וגשם
    alt_ref = 'agl' if body.get('alt_ref') == 'agl' else 'msl'  # ייחוס הגובה
    return p, parse_track_params(body), alt_ref  # הכל


def build_physics(p):
    """הפיזיקה המוזרקת למנוע — עטיפה דקה סביב radar_physics (אותן נוסחאות כמו בכלי הדופלר)."""
    wavelength_m = 299792458.0 / (p['freq_mhz'] * 1e6)  # אורך הגל
    ceiling_m = min(rph._radar_max_range_m(p['power_kw'], p['gain_dbi'], p['freq_mhz'], p['rcs_m2'], p['sensitivity_dbm']),
                    rph._max_unambiguous_range_m(p['prf_hz']))  # תקרה נקייה: משוואת מכ"ם או טווח חד-משמעי, הקטן מביניהם
    mdv_ms = p['mdv_kt'] * rph._KT_TO_MS  # MDV במ'/ש'
    reflectivity = rph._RADAR_REFLECTIVITY.get(p['reflectivity_key'], rph._RADAR_REFLECTIVITY[rph._RADAR_REFLECTIVITY_DEFAULT])  # מקדם החזרה
    lobing = ((lambda e: rph._lobing_factor(e, p['h_antenna'], wavelength_m, reflectivity))
              if p['lobing_enabled'] else (lambda e: 1.0))  # ריבוד רק אם הופעל
    scan = ((lambda b: rph._scan_loss_factor(b, p['boresight_deg'], p['max_scan_deg']))
            if p['antenna_type'] == 'phased_array' else (lambda b: 1.0))  # הפסד-סריקה רק במערך-מופעים
    phys = {'ceiling_m': ceiling_m, 'lobing': lobing, 'scan_loss': scan,
            'doppler_ok': lambda v: rph._doppler_detectable(v, mdv_ms, wavelength_m, p['prf_hz'])}  # ה-dict שהמנוע מצפה לו
    env = p.get('env') or {}  # RCS לפי זווית וגשם — נוספים רק אם הופעלו
    if env.get('rcs_mode') == 'aspect':  # RCS לפי זווית ההסתכלות
        ref = p['rcs_m2']  # ה-RCS שעליו חושבה התקרה
        nose, side, tail = env['rcs_nose'], env['rcs_side'], env['rcs_tail']  # שלושת הערכים
        phys['rcs_factor'] = lambda a: ((rt.aspect_rcs(a, nose, side, tail) / ref) ** 0.25,
                                        rt.aspect_rcs(a, nose, side, tail))  # (גורם התקרה, ה-RCS עצמו)
    if env.get('rain_rate_mmh', 0.0) > 0:  # יש גשם
        rate, top, tilt = env['rain_rate_mmh'], env['rain_top_m'], env['pol_tilt_deg']  # עוצמה, תקרה, קיטוב
        f_ghz = p['freq_mhz'] / 1000.0  # התדר ב-GHz
        h_msl = p.get('radar_h_msl', 0.0)  # גובה האנטנה מעל פני הים
        phys['rain_db'] = lambda g, q: 2.0 * rt.rain_specific_attenuation(rate, f_ghz, g['elev_deg'], tilt) * \
            rt.rain_path_km(g['slant_m'], h_msl, q['alt'], top)  # הלוך-חזור: פעמיים γ·L
    return phys  # הפיזיקה


# ═══════════════════════════ הכנת המסלול ═══════════════════════════

def to_msl(trajectory, fetch_cells):
    """גובה "מעל הקרקע" -> מעל פני הים: לכל קודקוד מוסיפים את גובה הקרקע שלו (לפני הציפוף; בין קודקודים — קירוב)."""
    cells = [rt.snap_cell(float(q['lat']), float(q.get('lon', q.get('lng')))) for q in trajectory]  # תא לכל קודקוד
    ground = fetch_cells(cells)  # גבהי הקרקע (Aborted אם בוטל/מכסה)
    out = []  # המסלול המומר
    for q, g in zip(trajectory, ground):  # כל קודקוד
        if g is None:  # אין גובה קרקע — לא ממציאים
            continue  # מדלגים
        q2 = dict(q)  # עותק
        q2['alt_msl'] = float(q.get('alt_msl', q.get('alt'))) + g  # מעל הקרקע + גובה הקרקע
        out.append(q2)  # לרשימה
    return out  # המסלול בגובה מעל פני הים


def prepare_trajectory(trajectory, alt_ref, fetch_cells):
    """המרת גובה (אם צריך) -> ניקוי -> ציפוף לנקודה כל שנייה -> איחוד. ValueError אם לא נשארו 2 נקודות."""
    if alt_ref == 'agl':  # גובה מעל הקרקע
        trajectory = to_msl(trajectory, fetch_cells)  # המרה
    clean = rt.normalize_trajectory(trajectory)  # ניקוי, מיון והסרת כפילויות
    dense = rt.densify_trajectory([{'t': q['t'], 'lat': q['lat'], 'lon': q['lon'], 'alt_msl': q['alt']} for q in clean])  # ציפוף
    traj = rt.normalize_trajectory(dense)  # איחוד (כולל מהירות תלת-ממדית)
    if len(traj) < 2:  # אין מסלול
        raise ValueError('במסלול פחות משתי נקודות תקינות (זמן/מיקום/גובה)')  # שגיאה ברורה
    return traj  # המסלול


# ═══════════════════════════ הצינורות ═══════════════════════════

def run_check(radar_lat, radar_lon, p, trajectory, track_cfg, alt_ref, fetch_cells):
    """בדיקה מלאה (שלבים א1-א5): גובה המכ"ם -> מסלול -> דגימות שטח -> הערכה -> מעקב. מחזיר את התוצאה לממשק.
    terrain.cached נשאר None — הקורא ממלא אותו (רק הוא יודע מה הגיע מהמטמון)."""
    ground = fetch_cells([(round(radar_lat, 6), round(radar_lon, 6))])[0]  # גובה הקרקע בנקודת המכ"ם המדויקת
    if ground is None:  # לא הצליח
        raise ValueError('לא ניתן לשלוף את גובה המכ"ם')  # שגיאה ברורה
    radar = {'lat': radar_lat, 'lon': radar_lon, 'h_msl': ground + p['h_antenna']}  # המכ"ם: קרקע + אנטנה
    traj = prepare_trajectory(trajectory, alt_ref, fetch_cells)  # המסלול
    plan = rt.plan_terrain_samples(radar, traj, p['range_km'] * 1000.0)  # תכנון דגימות השטח
    terrain = fetch_cells(plan['cells'])  # הגבהים
    profiles = rt.build_horizon_profiles(plan, terrain, radar['h_msl'])  # פרופילי אופק
    p = dict(p, radar_h_msl=radar['h_msl'])  # הגשם צריך את גובה האנטנה (עותק)
    physics = build_physics(p)  # הפיזיקה
    results = rt.evaluate_points(traj, radar, p, physics, plan, profiles)  # הערכה
    result = {
        'radar': {'lat': radar_lat, 'lon': radar_lon, 'ground_m': ground, 'h_msl': round(radar['h_msl'], 1)},
        'range_km': p['range_km'], 'points': results, 'summary': rt.summarize(results),
        'terrain': {'cells': len(plan['cells']), 'samples': len(plan['samples']), 'cached': None,
                    'missing': sum(1 for e in terrain if e is None), 'spacing_frac': round(plan['spacing_frac'], 4),
                    'bin_deg': round(plan['bin_deg'], 3), 'n_bins': plan['n_bins']},
        'beam': {'v_lo_deg': p['vertical_center_deg'] - p['vertical_width_deg'] / 2.0,  # גבול תחתון של שדה הראייה
                 'v_hi_deg': p['vertical_center_deg'] + p['vertical_width_deg'] / 2.0,  # גבול עליון
                 'min_range_km': p['min_range_km'], 'ceiling_km': round(physics['ceiling_m'] / 1000.0, 3)},  # לגרף הצד
        'env': p.get('env'),  # ה-RCS והגשם שבהם חושב
    }  # התוצאה
    track_mode, scan, track = track_cfg  # שלב א2
    result['track_mode'] = track_mode  # איזה מצב חושב
    if track_mode == 'track':  # מצב מעקב
        trk = rt.run_track_logic(results, scan, track)  # לוגיקת המעקב
        states = rt.track_states(results, trk['tracks'])  # מצב-מעקב לכל נקודה
        for r, st, rate in zip(results, states, trk['rates']):  # לכל נקודה
            r['track_state'] = st  # לצביעה
            r['ang_rate_dps'] = round(rate, 2)  # לפופאפ
        result['track'] = rt.summarize_track(results, trk, states)  # מדדים וציר זמן
        result['scan'] = dict(scan, **track)  # התצורה שבה חושב
    return result  # לממשק


def ray_profile(radar_lat, radar_lon, p, point, fetch_cells):
    """פרופיל שטח בין המכ"ם לנקודה (שלב א3): עד 99 דגימות + המכ"ם, האם הקו פנוי, והיכן נחסם לראשונה."""
    plat, plon, palt = float(point['lat']), float(point['lon']), float(point['alt'])  # הנקודה
    d_total = rt.haversine_m(radar_lat, radar_lon, plat, plon)  # מרחק קרקעי
    brg = rt.bearing_deg(radar_lat, radar_lon, plat, plon)  # כיוון
    n = max(2, min(99, int(d_total / 100.0)))  # מספר הדגימות
    dists = [d_total * k / n for k in range(1, n + 1)]  # מרחקי הדגימה (בלי 0)
    cells = [rt.snap_cell(radar_lat, radar_lon)] + [rt.snap_cell(*rt.destination_point(radar_lat, radar_lon, brg, d)) for d in dists]  # המכ"ם + הדגימות
    elevs = fetch_cells(cells)  # הגבהים
    if elevs[0] is None:  # אין גובה למכ"ם
        raise ValueError('אין גובה קרקע במיקום המכ"ם')  # שגיאה
    h_msl = elevs[0] + p['h_antenna']  # גובה האנטנה
    margin = math.tan(math.radians(p['ridge_margin_deg']))  # מרווח הרכס כשיפוע
    tgt_slope = (palt - rt.curvature_drop_m(d_total) - h_msl) / d_total if d_total > 0 else float('inf')  # שיפוע הנקודה
    block_d = None  # המרחק שבו הקו נחסם לראשונה
    for d, e in zip(dists, elevs[1:]):  # לאורך הקו
        if e is None or d >= d_total - rt.HORIZON_SELF_GAP_M:  # חסר, או ממש מתחת לנקודה
            continue  # מדלגים — כמו במנוע
        if tgt_slope < (e - rt.curvature_drop_m(d) - h_msl) / d + margin:  # השטח כאן חוסם
            block_d = d  # הראשון
            break  # מספיק
    return {'radar_h_msl': round(h_msl, 1), 'dist_m': round(d_total, 1), 'target_alt': palt,
            'dists': [round(d, 1) for d in dists], 'elevs': elevs[1:],
            'drops': [round(rt.curvature_drop_m(d), 2) for d in dists],  # ירידת העקמומיות — לשטח "אפקטיבי"
            'visible': block_d is None, 'block_dist_m': round(block_d, 1) if block_d is not None else None}  # הפרופיל


def run_placement(center_lat, center_lon, radius_m, step_m, metric, p, trajectory, track_cfg, alt_ref, fetch_cells,
                  note=lambda text: None, cancelled=lambda: False):
    """הצעת מיקום (שלב ב'): מועמדים -> מסלול -> רשת גבהים אחת לאזור -> בדיקה מלאה לכל מועמד ממנה.
    note(text) — הודעת התקדמות; cancelled() — האם לעצור (נזרק Aborted). dem.cached נשאר None — הקורא ממלא."""
    cands = rpl.candidate_grid(center_lat, center_lon, radius_m, step_m)  # המועמדים
    traj = prepare_trajectory(trajectory, alt_ref, fetch_cells)  # המסלול
    dem = rpl.DemGrid(*rpl.region_bbox(cands, traj, p['range_km'] * 1000.0))  # רשת הגבהים לאזור
    if dem.res_m > rpl.DEM_MAX_RES_M:  # גסה מדי לסינון משמעותי
        raise ValueError(f'האזור גדול מדי: רשת הגבהים יוצאת ברזולוציה {int(dem.res_m)} מ\'. '
                         'הקטן את רדיוס החיפוש או את טווח המכ"ם.')  # הסבר
    note(f'שולף רשת גבהים לאזור ({dem.n_lat * dem.n_lon} נקודות, ~{int(dem.res_m)} מ\')…')  # שלב 1 מתוך 2
    vals = fetch_cells(dem.nodes())  # שליפה
    dem.set_values(vals)  # לרשת
    phys_factory = lambda h_msl: build_physics(dict(p, radar_h_msl=h_msl))  # noqa: E731 — הפיזיקה עם גובה האנטנה של המועמד
    out = []  # תוצאות
    for k, c in enumerate(cands):  # מועמד אחר מועמד
        if cancelled():  # בוטל
            raise Aborted()  # עצירה
        note(f'מחשב מיקומים {k + 1}/{len(cands)}…')  # שלב 2 מתוך 2
        out.append(rpl.evaluate_candidate(c, traj, dem, p, phys_factory, track_cfg, metric))  # בדיקה מלאה
    return {'center': {'lat': center_lat, 'lon': center_lon}, 'radius_m': radius_m, 'step_m': step_m,
            'metric': metric, 'track_mode': track_cfg[0], 'candidates': out, 'best': rpl.best_candidates(out, 5),
            'dem': {'nodes': len(vals), 'res_m': round(dem.res_m), 'cached': None,
                    'missing': sum(1 for v in vals if v is None)}}  # התוצאה
