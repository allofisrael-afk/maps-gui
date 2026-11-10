"""בקרת אש: פתרון ירי לטווח ואזימוט, טבלת ירי וכיול מקדמי התאמה."""
import math
from dataclasses import replace

from .engine import simulate, stability_warnings
from .units import mils_to_rad, rad_to_mils, both, normalize_az_rad

QE_MIN = mils_to_rad(5.0)
QE_MAX = mils_to_rad(1350.0)   # מעל ~76° זווית המנוחה בקודקוד גדלה מאוד והקירוב קורס


def _range(proj, atmo, fp, qe):
    r = simulate(proj, atmo, replace(fp, qe=qe), record=False)
    return (r.ground_range if r.ok else 0.0), r


def max_range(proj, atmo, fp):
    """מוצא את זווית ההגבהה לטווח המרבי (סריקה גסה + חתך זהב)."""
    best_q, best_r = QE_MIN, 0.0
    q = mils_to_rad(100)
    step = mils_to_rad(100)
    while q <= QE_MAX:
        r, _ = _range(proj, atmo, fp, q)
        if r > best_r:
            best_q, best_r = q, r
        q += step
    a, b = max(QE_MIN, best_q - step), min(QE_MAX, best_q + step)
    gr = (math.sqrt(5) - 1) / 2
    c, d = b - gr * (b - a), a + gr * (b - a)
    fc, _ = _range(proj, atmo, fp, c)
    fd, _ = _range(proj, atmo, fp, d)
    while b - a > mils_to_rad(0.5):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - gr * (b - a)
            fc, _ = _range(proj, atmo, fp, c)
        else:
            a, c, fc = c, d, fd
            d = a + gr * (b - a)
            fd, _ = _range(proj, atmo, fp, d)
    q = (a + b) / 2
    r, _ = _range(proj, atmo, fp, q)
    return q, r


def _solve_branch(proj, atmo, fp, target, lo, hi, increasing, tol=0.5):
    """חיפוש זווית בענף מונוטוני (low: עולה, high: יורד) — בי-סקציה עם צעד secant."""
    r_lo, _ = _range(proj, atmo, fp, lo)
    r_hi, _ = _range(proj, atmo, fp, hi)
    for it in range(60):
        # צעד secant בתוך הקטע, נופל לבי-סקציה אם יוצא מהגבולות
        if abs(r_hi - r_lo) > 1e-6:
            q = lo + (target - r_lo) * (hi - lo) / (r_hi - r_lo)
            if not (min(lo, hi) < q < max(lo, hi)) or abs(q - lo) < 1e-9 or abs(q - hi) < 1e-9:
                q = 0.5 * (lo + hi)
        else:
            q = 0.5 * (lo + hi)
        r, res = _range(proj, atmo, fp, q)
        if abs(r - target) < tol or abs(hi - lo) < 1e-7:
            return q, res
        below = r < target
        if (below and increasing) or (not below and not increasing):
            lo, r_lo = q, r
        else:
            hi, r_hi = q, r
        # שמירה על התכנסות: אם secant תקוע בצד אחד, בי-סקציה
        if it % 3 == 2:
            mid = 0.5 * (lo + hi)
            rm, _unused = _range(proj, atmo, fp, mid)
            if (rm < target) == increasing:
                lo, r_lo = mid, rm
            else:
                hi, r_hi = mid, rm
    q = 0.5 * (lo + hi)
    _, res = _range(proj, atmo, fp, q)
    return q, res


def solve(proj, atmo, fp, target_range, target_azimuth, target_alt=None, group="low", iterations=3,
          qe_min=None, qe_max=None):
    """
    מחשב זווית הגבהה ואזימוט ירי לפגיעה במטרה.
    target_range – מרחק אופקי למטרה [m]; target_azimuth – אזימוט למטרה [rad];
    group – 'low' (זווית נמוכה, < טווח מרבי) או 'high' (זווית גבוהה).
    הסחיפה, הרוח הצידית וקוריוליס מתוקנים באיטרציה על אזימוט הירי.
    qe_min/qe_max [rad] — תחום-הגבהות מותר אופציונלי (None = כל התחום הפיזיקלי, כברירת מחדל הקיימת).
    """
    # qe_min/qe_max מצמצמים את תחום-החיפוש לענף הרלוונטי (מוחלים רק בתוך התחום הפיזיקלי הקבוע, לא מעבר לו)
    qe_lo_bound = max(QE_MIN, qe_min) if qe_min is not None else QE_MIN
    qe_hi_bound = min(QE_MAX, qe_max) if qe_max is not None else QE_MAX
    fp = replace(fp, target_alt=target_alt if target_alt is not None else fp.gun_alt)
    fire_az = target_azimuth
    q = None
    res = None
    q_max = r_max = None
    for it in range(iterations):
        fpi = replace(fp, azimuth=normalize_az_rad(fire_az))
        if q_max is None or it == 0:
            q_max, r_max = max_range(proj, atmo, fpi)
        if target_range > r_max:
            return {"ok": False, "error": f"המטרה מחוץ לטווח: מרחק {target_range:.0f} מ', טווח מרבי {r_max:.0f} מ'",
                    "max_range_m": round(r_max, 1), "qe_max_range": both(q_max)}
        # ענף הזווית מוצמד לתחום-ההגבהות המותר (qe_lo_bound/qe_hi_bound) בנוסף לגבולות-הענף הפיזיקליים
        if group == "high":
            branch_lo, branch_hi = max(q_max, qe_lo_bound), min(QE_MAX, qe_hi_bound)
        else:
            branch_lo, branch_hi = max(QE_MIN, qe_lo_bound), min(q_max, qe_hi_bound)
        if branch_lo >= branch_hi:
            # אין חפיפה בין הענף המבוקש לתחום-ההגבהות המותר — אין פתרון אפשרי בתחום
            return {"ok": False, "error": "אין זווית בענף המבוקש בתוך תחום-ההגבהות המותר",
                    "max_range_m": round(r_max, 1), "qe_max_range": both(q_max),
                    "qe_bound_low": both(qe_lo_bound), "qe_bound_high": both(qe_hi_bound)}
        # בודקים שהטווח המבוקש בכלל מושג בתוך הענף המוצמד, לפני הבי-סקציה — אחרת _solve_branch
        # יתכנס בשקט לקצה הענף עם שגיאת-טווח גדולה במקום לדווח "מחוץ לתחום ההגבהות"
        r_branch_lo, _ = _range(proj, atmo, fpi, branch_lo)
        r_branch_hi, _ = _range(proj, atmo, fpi, branch_hi)
        reachable_lo, reachable_hi = min(r_branch_lo, r_branch_hi), max(r_branch_lo, r_branch_hi)
        if not (reachable_lo - 0.5 <= target_range <= reachable_hi + 0.5):
            closest_r = reachable_lo if target_range < reachable_lo else reachable_hi
            closest_q = branch_lo if closest_r == r_branch_lo else branch_hi
            return {"ok": False,
                    "error": f"המטרה מחוץ לתחום-ההגבהות המותר — הטווח הקרוב ביותר האפשרי בענף זה: {closest_r:.0f} מ'",
                    "max_range_m": round(r_max, 1), "qe_max_range": both(q_max),
                    "qe_bound_low": both(qe_lo_bound), "qe_bound_high": both(qe_hi_bound),
                    "closest_achievable_range_m": round(closest_r, 1), "qe_closest": both(closest_q)}
        if group == "high":
            q, res = _solve_branch(proj, atmo, fpi, target_range, branch_lo, branch_hi, increasing=False)
        else:
            q, res = _solve_branch(proj, atmo, fpi, target_range, branch_lo, branch_hi, increasing=True)
        if not res.ok:
            return {"ok": False, "error": "לא נמצא פתרון: " + res.message}
        dev = math.atan2(res.impact["drift_z_m"], res.impact["range_x_m"])
        new_az = target_azimuth - dev
        if abs(new_az - fire_az) < mils_to_rad(0.05):
            fire_az = new_az
            break
        fire_az = new_az
    # הרצה סופית עם נתוני המסלול המלאים
    final = simulate(proj, atmo, replace(fp, qe=q, azimuth=normalize_az_rad(fire_az)), record=True)
    miss = final.ground_range - target_range
    dev_rad = target_azimuth - fire_az
    return {
        "ok": True,
        "qe": both(q),
        "fire_azimuth": both(normalize_az_rad(fire_az)),
        "target_azimuth": both(normalize_az_rad(target_azimuth)),
        "deflection_correction": both(-dev_rad),
        "deflection_note": "תיקון הכוונה יחסית לקו המטרה (שלילי = שמאלה)",
        "angle_group": group,
        "target_range_m": round(target_range, 1),
        "residual_range_error_m": round(miss, 2),
        "max_range_m": round(r_max, 1),
        "qe_max_range": both(q_max),
        "impact": final.impact,
        "warnings": stability_warnings(final),
        "_trajectory": final,
    }


def _range_at_mv(proj, atmo, fp, mv):
    """טווח אופקי [m] להגבהה קבועה (fp.qe) במהירות-לוע mv נתונה — אנלוגי ל-_range אך משתנה-החיפוש הוא mv."""
    r = simulate(proj, atmo, replace(fp, mv=mv), record=False)
    return (r.ground_range if r.ok else 0.0), r


def solve_mv(proj, atmo, fp, target_range, target_azimuth, qe_fixed, mv_min, mv_max, target_alt=None,
             iterations=3, tol=0.5):
    """
    מוצא את מהירות-הלוע הנדרשת (בתחום [mv_min, mv_max]) לפגיעה במטרה בהגבהה קבועה (qe_fixed).
    בי-סקציה על mv (הטווח גדל-מונוטונית עם מהירות-הלוע בהגבהה קבועה — נבדק בפועל, לא מונח).
    אזימוט-הירי מתוקן באיטרציה (סחיפה/רוח/קוריוליס) בדיוק כמו ב-solve().
    """
    fp = replace(fp, target_alt=target_alt if target_alt is not None else fp.gun_alt, qe=qe_fixed)
    fire_az = target_azimuth
    mv = res = None
    for it in range(iterations):
        fpi = replace(fp, azimuth=normalize_az_rad(fire_az))
        r_lo, _ = _range_at_mv(proj, atmo, fpi, mv_min)
        r_hi, _ = _range_at_mv(proj, atmo, fpi, mv_max)
        r_mid, _ = _range_at_mv(proj, atmo, fpi, 0.5 * (mv_min + mv_max))
        # בדיקת-מונוטוניות אמיתית (3 נקודות) — לא ניחוש: אם הטווח לא עולה בעקביות עם mv בתחום הזה,
        # בי-סקציה תתכנס לתוצאה שגויה בשקט, אז מדווחים ולא מנסים
        if not (r_lo <= r_mid + 1e-6 <= r_hi + 1e-6) and not (r_lo <= r_hi):
            return {"ok": False, "error": "הטווח אינו מונוטוני ב-מהירות-הלוע בתחום שהוגדר — לא ניתן לפתור בבי-סקציה",
                    "range_at_mv_min_m": round(r_lo, 1), "range_at_mv_mid_m": round(r_mid, 1),
                    "range_at_mv_max_m": round(r_hi, 1)}
        if not (min(r_lo, r_hi) - tol <= target_range <= max(r_lo, r_hi) + tol):
            closest_r = r_lo if abs(target_range - r_lo) < abs(target_range - r_hi) else r_hi
            closest_mv = mv_min if closest_r == r_lo else mv_max
            return {"ok": False,
                    "error": f"המטרה מחוץ לתחום-מהירות-הלוע המותר — הטווח הקרוב ביותר האפשרי: {closest_r:.0f} מ'",
                    "range_at_mv_min_m": round(r_lo, 1), "range_at_mv_max_m": round(r_hi, 1),
                    "closest_achievable_range_m": round(closest_r, 1), "mv_closest": round(closest_mv, 1)}
        lo, hi = mv_min, mv_max
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            r_mid, res = _range_at_mv(proj, atmo, fpi, mid)
            if abs(r_mid - target_range) < tol or (hi - lo) < 1e-4:
                mv = mid
                break
            below = r_mid < target_range
            if below == (r_hi > r_lo):
                lo = mid
            else:
                hi = mid
        else:
            mv = 0.5 * (lo + hi)
        if not res.ok:
            return {"ok": False, "error": "לא נמצא פתרון: " + res.message}
        dev = math.atan2(res.impact["drift_z_m"], res.impact["range_x_m"])
        new_az = target_azimuth - dev
        if abs(new_az - fire_az) < mils_to_rad(0.05):
            fire_az = new_az
            break
        fire_az = new_az
    final = simulate(proj, atmo, replace(fp, mv=mv, azimuth=normalize_az_rad(fire_az)), record=True)
    miss = final.ground_range - target_range
    dev_rad = target_azimuth - fire_az
    return {
        "ok": True,
        "muzzle_velocity_mps": round(mv, 1),
        "qe": both(qe_fixed),
        "fire_azimuth": both(normalize_az_rad(fire_az)),
        "target_azimuth": both(normalize_az_rad(target_azimuth)),
        "deflection_correction": both(-dev_rad),
        "target_range_m": round(target_range, 1),
        "residual_range_error_m": round(miss, 2),
        "impact": final.impact,
        "warnings": stability_warnings(final),
        "_trajectory": final,
    }


def firing_table(proj, atmo, fp, qe_start, qe_end, qe_step):
    """טבלת ירי. זוויות ב-rad. מחזיר רשימת שורות (מילונים) ורשימת אזהרות."""
    rows, warns = [], []
    q = qe_start
    n = 0
    while q <= qe_end + 1e-12 and n < 2000:
        r = simulate(proj, atmo, replace(fp, qe=q), record=False)
        if r.ok:
            i = r.impact
            rows.append({
                "qe_mils": round(rad_to_mils(q), 1), "qe_deg": round(math.degrees(q), 3),
                "range_m": i["ground_range_m"], "drift_mils": i["deviation"]["mils"],
                "drift_m": i["drift_z_m"], "tof_s": i["time_of_flight_s"],
                "apex_m": i["apex_height_m"], "impact_vel_mps": i["impact_velocity_mps"],
                "fall_angle_mils": i["angle_of_fall"]["mils"], "fall_angle_deg": i["angle_of_fall"]["deg"],
                "sg_min": i["sg_min"],
            })
            for w in stability_warnings(r):
                warns.append(f"QE {rad_to_mils(q):.0f} mils: {w}")
        else:
            rows.append({"qe_mils": round(rad_to_mils(q), 1), "qe_deg": round(math.degrees(q), 3), "error": r.message})
        q += qe_step
        n += 1
    return rows, warns


TABLE_COLUMNS = ["qe_mils", "qe_deg", "range_m", "drift_mils", "drift_m", "tof_s", "apex_m",
                 "impact_vel_mps", "fall_angle_mils", "fall_angle_deg", "sg_min"]


def write_table_csv(rows, path):
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=TABLE_COLUMNS + ["error"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def calibrate(proj, atmo, fp, points, fit_drift=True, passes=3):
    """
    כיול מקדמי התאמה מול נקודות פגיעה שנמדדו.
    points: [{"qe": rad, "azimuth": rad, "range_m": מרחק אופקי שנמדד,
              "drift_mils": סטייה צידית שנמדדה (אופציונלי, ימינה חיובי), "target_alt": אופציונלי}]
    מקדם גרר fD מכויל מול הטווחים (Gauss-Newton), ומקדם עילוי fL מול הסחיפה.
    """
    if not points:
        raise ValueError("אין נקודות לכיול")
    fD, fL = fp.drag_factor, fp.lift_factor
    drift_pts = [p for p in points if p.get("drift_mils") is not None]

    def run(pt, fd, fl):
        f = replace(fp, qe=pt["qe"], azimuth=pt.get("azimuth", fp.azimuth),
                    target_alt=pt.get("target_alt", fp.target_alt), drag_factor=fd, lift_factor=fl)
        r = simulate(proj, atmo, f, record=False)
        if not r.ok:
            raise ValueError(f"נקודה בזווית {rad_to_mils(pt['qe']):.0f} מיל: {r.message}")
        return r.ground_range, r.impact["deviation"]["mils"]

    def gn(param_idx, current, key, other):
        x = current
        pts = points if param_idx == 0 else drift_pts
        for _ in range(6):
            num = den = 0.0
            h = 0.002 if param_idx == 0 else 0.01
            for pt in pts:
                args = (x, other) if param_idx == 0 else (other, x)
                args_h = (x + h, other) if param_idx == 0 else (other, x + h)
                v = run(pt, *args)[param_idx]
                vh = run(pt, *args_h)[param_idx]
                r = v - pt[key]
                J = (vh - v) / h
                num += r * J
                den += J * J
            if den < 1e-12:
                break
            step = num / den
            lo_b, hi_b = (0.3, 3.0) if param_idx == 0 else (0.0, 5.0)
            x = min(max(x - step, lo_b), hi_b)
            if abs(step) < (1e-5 if param_idx == 0 else 1e-4):
                break
        return x

    for _ in range(passes):
        fD_old, fL_old = fD, fL
        fD = gn(0, fD, "range_m", fL)
        if fit_drift and drift_pts:
            fL = gn(1, fL, "drift_mils", fD)
        if abs(fD - fD_old) < 1e-5 and abs(fL - fL_old) < 1e-4:
            break

    report = []
    for pt in points:
        rng, dr = run(pt, fD, fL)
        rng0, dr0 = run(pt, 1.0, 1.0)
        report.append({
            "qe": both(pt["qe"]),
            "measured_range_m": pt["range_m"], "sim_range_m": round(rng, 1),
            "range_error_m": round(rng - pt["range_m"], 1),
            "range_error_before_m": round(rng0 - pt["range_m"], 1),
            "measured_drift_mils": pt.get("drift_mils"),
            "sim_drift_mils": round(dr, 2),
            "drift_error_mils": round(dr - pt["drift_mils"], 2) if pt.get("drift_mils") is not None else None,
        })
    rms_r = math.sqrt(sum(r["range_error_m"] ** 2 for r in report) / len(report))
    return {"drag_factor": round(fD, 5), "lift_factor": round(fL, 4),
            "rms_range_error_m": round(rms_r, 2), "points": report,
            "drift_fitted": bool(fit_drift and drift_pts)}
