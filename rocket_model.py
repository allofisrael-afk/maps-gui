# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
rocket_model — מודל רקטה פשוט ורעיוני לכלי בדיקת מעקב המכ"ם (שלב א6, SRS FR-D-261). לא מבוסס מערכת אמיתית.

נקודת-מסה בשלוש דרגות חופש: שלב דחיפה (דחף קבוע, מסה שיורדת ליניארית לאורך זמן הבעירה) ואחריו מעוף
בליסטי. כוחות: דחף, גרר (½ρv²·Cd·A, Cd קבוע, מול האוויר — כולל רוח) וכובד. בתחילת הדרך הדחף בכיוון
השיגור ("מסילה"), ואחרי שהמהירות עוברת סף — לאורך וקטור המהירות ("gravity turn").
האטמוספרה מוזרקת (AtmosphereProfile של מנוע ה-MPM — סטנדרטית או מטאו אמיתי), ומנוע ה-MPM עצמו לא משתנה.
stdlib בלבד, כמו radar_track.py — נבדק בלי רשת.
"""

import math  # טריגונומטריה ושורשים

G0 = 9.80665  # תאוצת הכובד [מ'/ש'²] — זהה ל-mpm/atmosphere.py
R_EARTH = 6371000.0  # רדיוס כדור הארץ [מ'] — לתיקון העקמומיות בגובה, כמו ב-mpm_api._path_points
RAIL_SPEED_MS = 40.0  # עד המהירות הזו הדחף בכיוון השיגור (יציאה טיפוסית מקנה/מסילה); מעליה — לאורך וקטור המהירות.
# ערך נמוך מדי גורם ל"גלגול כובד" מוקדם שמשטיח את המסלול — נמדד: 20 מ'/ש' ביחס דחף-משקל 5 נתן זווית 2.9° בסוף הבעירה
DT = 0.01  # צעד האינטגרציה [שנ']
RECORD_EVERY_S = 0.1  # מרווח הנקודות במסלול שמוחזר — כמו path_step=5 של ה-MPM (0.02×5)
T_MAX_S = 1200.0  # תקרת זמן מעוף — הגנה מלולאה אינסופית בפרמטרים לא סבירים


def _unit(x, y, z):
    """וקטור יחידה, ו-(0,0,0) אם האורך אפס."""
    n = math.sqrt(x * x + y * y + z * z)  # האורך
    return (x / n, y / n, z / n) if n > 0 else (0.0, 0.0, 0.0)  # מנורמל


def simulate(launch, elev_deg, az_deg, rocket, atmo, impact_alt=None, geo_direct=None):
    """
    מדמה מעוף רקטה. launch: {'lat','lon','alt_m'}. rocket: {'mass_kg' (כולל דלק), 'prop_kg', 'burn_s', 'thrust_n',
    'diam_m', 'cd'}. atmo: אובייקט עם at(h_msl) -> (rho, a, T, P, wind_e, wind_n). impact_alt: גובה הפגיעה
    מעל פני הים (ברירת מחדל: גובה המשגר). geo_direct(lat, lon, az, dist) -> (lat, lon) — מוזרק (Vincenty של ה-MPM).
    מחזיר {'ok', 'message', 'path':[{t,lat,lon,alt_msl,v,mach}], 'burnout', 'apex', 'impact'}.
    """
    m0 = float(rocket["mass_kg"])  # מסה התחלתית
    prop = float(rocket["prop_kg"])  # מסת הדלק
    burn = float(rocket["burn_s"])  # זמן בעירה
    thrust = float(rocket["thrust_n"])  # דחף
    area = math.pi * float(rocket["diam_m"]) ** 2 / 4.0  # שטח חתך
    cd = float(rocket["cd"])  # מקדם גרר
    if not (m0 > 0 and 0 <= prop < m0 and burn > 0 and thrust >= 0 and area > 0 and cd >= 0):  # בדיקת תקינות
        return {"ok": False, "message": "פרמטרי רקטה לא תקינים (מסה, דלק < מסה, זמן בעירה, דחף, קוטר, Cd)"}  # שגיאה
    mdot = prop / burn  # קצב צריכת הדלק
    h0 = float(launch["alt_m"])  # גובה המשגר
    z_stop = (float(impact_alt) if impact_alt is not None else h0) - h0  # גובה הפגיעה ביחס למשגר
    el, az = math.radians(elev_deg), math.radians(az_deg)  # זוויות השיגור
    launch_dir = (math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el))  # כיוון השיגור: מזרח/צפון/מעלה

    def accel(t, z, vx, vy, vz):
        """התאוצה ברגע t: (דחף − גרר)/מסה − כובד. מחזיר גם מסה ומאך לרישום."""
        m = m0 - mdot * min(t, burn)  # המסה הנוכחית
        f_thrust = thrust if t < burn else 0.0  # דחף רק בזמן הבעירה
        rho, a_snd, _T, _P, we, wn = atmo.at(h0 + z)  # האוויר בגובה הזה
        rx, ry, rz = vx - we, vy - wn, vz  # מהירות יחסית לאוויר (הרוח אופקית)
        vrel = math.sqrt(rx * rx + ry * ry + rz * rz)  # גודלה
        drag = 0.5 * rho * vrel * vrel * cd * area  # כוח הגרר
        speed = math.sqrt(vx * vx + vy * vy + vz * vz)  # המהירות מול הקרקע
        ux, uy, uz = launch_dir if speed < RAIL_SPEED_MS else _unit(vx, vy, vz)  # כיוון הדחף
        dx, dy, dz = _unit(rx, ry, rz)  # כיוון הגרר (נגד המהירות היחסית)
        ax = (f_thrust * ux - drag * dx) / m  # תאוצה מזרחה
        ay = (f_thrust * uy - drag * dy) / m  # תאוצה צפונה
        az_ = (f_thrust * uz - drag * dz) / m - G0  # תאוצה כלפי מעלה, פחות כובד
        return ax, ay, az_, m, (vrel / a_snd if a_snd > 0 else 0.0)  # תאוצה, מסה, מאך

    t, x, y, z, vx, vy, vz = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0  # מצב התחלתי: נייח על המשגר
    if thrust * math.sin(el) <= m0 * G0:  # הרכיב האנכי של הדחף לא מתגבר על המשקל — אין מסילה במודל שתחזיק אותה
        return {"ok": False, "message": "הדחף (ברכיב האנכי) קטן מהמשקל — הרקטה לא מתרוממת"}  # שגיאה
    raw = []  # נקודות גולמיות (מקומיות)
    burnout = apex = None  # אירועים לרישום
    next_rec = 0.0  # הזמן הבא לרישום נקודה
    while t <= T_MAX_S:  # לולאת האינטגרציה
        a1 = accel(t, z, vx, vy, vz)  # שיטת נקודת-אמצע (RK2): תאוצה בתחילת הצעד
        hx, hy, hz = vx + a1[0] * DT / 2, vy + a1[1] * DT / 2, vz + a1[2] * DT / 2  # מהירות באמצע הצעד
        a2 = accel(t + DT / 2, z + vz * DT / 2, hx, hy, hz)  # תאוצה באמצע הצעד
        if t >= next_rec - 1e-9:  # הגיע זמן לרשום
            raw.append((t, x, y, z, math.sqrt(vx * vx + vy * vy + vz * vz), a1[4]))  # זמן, מיקום, מהירות, מאך
            next_rec += RECORD_EVERY_S  # הרישום הבא
        nx, ny, nz = x + hx * DT, y + hy * DT, z + hz * DT  # מיקום חדש
        nvx, nvy, nvz = vx + a2[0] * DT, vy + a2[1] * DT, vz + a2[2] * DT  # מהירות חדשה
        if burnout is None and t + DT >= burn:  # סוף הבעירה בצעד הזה
            burnout = {"t": round(burn, 2), "alt_m": round(h0 + nz, 1), "v_ms": round(math.sqrt(nvx ** 2 + nvy ** 2 + nvz ** 2), 1)}  # נרשם
        if apex is None and vz > 0 >= nvz:  # שיא הגובה
            apex = {"t": round(t, 2), "alt_m": round(h0 + z, 1), "range_m": round(math.hypot(x, y), 1)}  # נרשם
        if t > burn and nz <= z_stop and nvz < 0:  # חצה את גובה הפגיעה בירידה
            f = (z - z_stop) / (z - nz) if z != nz else 1.0  # אינטרפולציה לנקודת החצייה המדויקת
            x, y, z = x + f * (nx - x), y + f * (ny - y), z_stop  # נקודת הפגיעה
            t += f * DT  # זמן הפגיעה
            v_imp = math.sqrt(nvx ** 2 + nvy ** 2 + nvz ** 2)  # מהירות הפגיעה
            raw.append((t, x, y, z, v_imp, a2[4]))  # הנקודה האחרונה
            break  # סיום
        if t > burn + 1.0 and nz < z_stop - 5000.0:  # הגנה: ירד הרבה מתחת לגובה הפגיעה (לא אמור לקרות)
            break  # יציאה
        t, x, y, z, vx, vy, vz = t + DT, nx, ny, nz, nvx, nvy, nvz  # מתקדמים
    else:  # נגמר הזמן בלי פגיעה
        return {"ok": False, "message": f"לא נחת תוך {int(T_MAX_S)} שניות — בדוק את הפרמטרים"}  # שגיאה
    if len(raw) < 2:  # מסלול קצר מדי
        return {"ok": False, "message": "הרקטה לא עזבה את המשגר"}  # שגיאה
    path = []  # המסלול הגיאוגרפי
    for (tt, px, py, pz, v, mach) in raw:  # כל נקודה
        dist = math.hypot(px, py)  # מרחק קרקעי מהמשגר
        brg = math.degrees(math.atan2(px, py)) % 360.0 if dist > 0 else az_deg % 360.0  # כיוון
        lat, lon = geo_direct(float(launch["lat"]), float(launch["lon"]), brg, dist) if dist > 0 else (float(launch["lat"]), float(launch["lon"]))  # מיקום
        path.append({"t": round(tt, 3), "lat": round(lat, 7), "lon": round(lon, 7),
                     "alt_msl": round(h0 + pz + dist * dist / (2.0 * R_EARTH), 1),  # תיקון עקמומיות כמו ב-mpm_api
                     "ground_dist": round(dist, 1), "v": round(v, 1), "mach": round(mach, 3)})  # הנקודה
    last = raw[-1]  # הפגיעה
    return {"ok": True, "message": "", "path": path, "burnout": burnout, "apex": apex,
            "impact": {"t": round(last[0], 2), "range_m": round(math.hypot(last[1], last[2]), 1), "v_ms": round(last[4], 1)}}  # התוצאה
