"""מנוע MPM (Modified Point Mass) — 4 דרגות חופש: x, y, z של מרכז הכובד וקצב הספין p.

מערכת צירים מקומית (שטוחה עם תיקון עקמומיות כדור הארץ, לפי McCoy):
    x – לאורך קו הירי (אזימוט הירי), y – למעלה, z – ימינה.
    הראשית בלוע התותח.

משוואות התנועה:
    v   = u − w                                   (מהירות יחסית לאוויר)
    αR  = −8·Ix·p·(v × u̇) / (π·ρ·d³·CMα·v⁴)       (זווית המנוחה, וקטור)
    u̇  = −(πρd²/8m)·fD·(CD0 + CDα2·αR²)·v·v
         + (πρd²/8m)·fL·CLα·v²·αR
         + (πρd³p/8m)·fM·CNpα·(αR × v)
         + g + Λ
    ṗ  = πρd⁴·p·v·Clp / (8·Ix)
    g  = −g0·(x/R, 1 − 2y/R, z/R)                (כבידה עם עקמומיות)
    Λ  = −2·Ω × u                                (קוריוליס)

u̇ בתוך αR מוערך מגרר אפס, כבידה וקוריוליס — הקירוב המקובל בתקן.
fD, fL, fM – מקדמי התאמה (fitting factors) לגרר, עילוי ומגנוס.
"""
import math
from dataclasses import dataclass, field

from .units import both

OMEGA_EARTH = 7.292115e-5
R_EARTH = 6356766.0
ALPHA_CAP = math.radians(20.0)
ALPHA_CAP2 = ALPHA_CAP * ALPHA_CAP


def gravity_at_latitude(lat_rad):
    """תאוצת כובד בפני הים לפי קו רוחב (נוסחה בינלאומית מקוצרת)."""
    s2 = math.sin(lat_rad) ** 2
    return 9.780327 * (1.0 + 0.0053024 * s2 - 0.0000058 * math.sin(2 * lat_rad) ** 2)


@dataclass
class FireParams:
    qe: float                     # זווית הגבהה [rad]
    azimuth: float                # אזימוט ירי מצפון אמיתי [rad]
    mv: float                     # מהירות לוע [m/s]
    latitude: float = 0.0         # [rad]
    gun_alt: float = 0.0          # גובה הלוע מעל פני הים [m]
    target_alt: float = None      # גובה נקודת הפגיעה מעל פני הים [m]; None = כגובה התותח
    dt: float = 0.02              # צעד אינטגרציה [s]
    drag_factor: float = 1.0
    lift_factor: float = 1.0
    magnus_factor: float = 1.0
    coriolis: bool = True
    earth_curvature: bool = True
    max_time: float = 400.0


@dataclass
class TrajectoryResult:
    ok: bool
    message: str = ""
    t: list = field(default_factory=list)
    x: list = field(default_factory=list)
    y: list = field(default_factory=list)
    z: list = field(default_factory=list)
    vel: list = field(default_factory=list)
    mach: list = field(default_factory=list)
    spin: list = field(default_factory=list)
    yaw_repose: list = field(default_factory=list)   # |αR| [rad]
    sg: list = field(default_factory=list)
    impact: dict = field(default_factory=dict)

    @property
    def ground_range(self):
        return self.impact.get("ground_range_m", 0.0)


def simulate(proj, atmo, fp: FireParams, record=True):
    m, d, ix, iy = proj.mass, proj.diameter, proj.ix, proj.iy
    coeffs = proj.coeffs
    at = atmo.at
    gun_alt = fp.gun_alt
    tgt_rel = (fp.target_alt - gun_alt) if fp.target_alt is not None else 0.0
    fD, fL, fM = fp.drag_factor, fp.lift_factor, fp.magnus_factor
    pi = math.pi
    sA, cA = math.sin(fp.azimuth), math.cos(fp.azimuth)
    g0 = gravity_at_latitude(fp.latitude)
    Re = R_EARTH
    curv = fp.earth_curvature
    if fp.coriolis:
        cL, sL = math.cos(fp.latitude), math.sin(fp.latitude)
        Ox, Oy, Oz = OMEGA_EARTH * cL * cA, OMEGA_EARTH * sL, -OMEGA_EARTH * cL * sA
    else:
        Ox = Oy = Oz = 0.0
    k_d2 = pi * d * d / (8.0 * m)
    k_d3 = pi * d ** 3 / (8.0 * m)

    def deriv(s):
        x, y, z, ux, uy, uz, p = s
        rho, a, T, P, we, wn = at(gun_alt + y)
        wx = we * sA + wn * cA
        wz = we * cA - wn * sA
        vx, vy, vz = ux - wx, uy, uz - wz
        v2 = vx * vx + vy * vy + vz * vz
        v = math.sqrt(v2)
        mach = v / a
        cd0, cda2, cla, cma, cnpa, clp = coeffs(mach)
        if curv:
            gx, gy, gz = -g0 * x / Re, -g0 * (1.0 - 2.0 * y / Re), -g0 * z / Re
        else:
            gx, gy, gz = 0.0, -g0, 0.0
        # קוריוליס: Λ = −2 Ω × u
        Lx = -2.0 * (Oy * uz - Oz * uy)
        Ly = -2.0 * (Oz * ux - Ox * uz)
        Lz = -2.0 * (Ox * uy - Oy * ux)
        kd = rho * k_d2
        # u̇ משוער לחישוב זווית המנוחה
        c0 = -kd * fD * cd0 * v
        dux0 = c0 * vx + gx + Lx
        duy0 = c0 * vy + gy + Ly
        duz0 = c0 * vz + gz + Lz
        # αR = −8·Ix·p·(v × u̇) / (π·ρ·d³·CMα·v⁴)
        cx = vy * duz0 - vz * duy0
        cy = vz * dux0 - vx * duz0
        cz = vx * duy0 - vy * dux0
        kr = -8.0 * ix * p / (pi * rho * d ** 3 * cma * v2 * v2)
        ax_, ay_, az_ = kr * cx, kr * cy, kr * cz
        al2 = ax_ * ax_ + ay_ * ay_ + az_ * az_
        if al2 > ALPHA_CAP2:
            # הגבלת זווית המנוחה — מעבר לזה המודל אינו תקף (מסומן באזהרה)
            sc = ALPHA_CAP / math.sqrt(al2)
            ax_, ay_, az_ = ax_ * sc, ay_ * sc, az_ * sc
            al2 = ALPHA_CAP2
        cD = fD * (cd0 + cda2 * al2)
        cdrag = -kd * cD * v
        clift = kd * fL * cla * v2
        cmag = rho * k_d3 * p * fM * cnpa
        # αR × v
        mx = ay_ * vz - az_ * vy
        my = az_ * vx - ax_ * vz
        mz = ax_ * vy - ay_ * vx
        dux = cdrag * vx + clift * ax_ + cmag * mx + gx + Lx
        duy = cdrag * vy + clift * ay_ + cmag * my + gy + Ly
        duz = cdrag * vz + clift * az_ + cmag * mz + gz + Lz
        dp = pi * rho * d ** 4 * p * v * clp / (8.0 * ix)
        aux = (v, mach, math.sqrt(al2), rho, cma)
        return (ux, uy, uz, dux, duy, duz, dp), aux

    def ground(x, z):
        return tgt_rel - ((x * x + z * z) / (2.0 * Re) if curv else 0.0)

    def sg_of(p, rho, v, cma):
        return 2.0 * ix * ix * p * p / (pi * rho * iy * d ** 3 * v * v * cma)

    p0 = proj.muzzle_spin(fp.mv)
    s = (0.0, 0.0, 0.0, fp.mv * math.cos(fp.qe), fp.mv * math.sin(fp.qe), 0.0, p0)
    t = 0.0
    h = fp.dt
    res = TrajectoryResult(ok=False)
    apex_y, apex_x, apex_t = 0.0, 0.0, 0.0
    sg_min = float("inf")
    k1, aux = deriv(s)
    sg0 = sg_of(p0, aux[3], aux[0], aux[4])
    max_mach = aux[1]

    def rec(t, s, aux, sg):
        res.t.append(t); res.x.append(s[0]); res.y.append(s[1]); res.z.append(s[2])
        res.vel.append(aux[0]); res.mach.append(aux[1]); res.spin.append(s[6])
        res.yaw_repose.append(aux[2]); res.sg.append(sg)

    if record:
        rec(t, s, aux, sg0)
    went_up = False
    while t < fp.max_time:
        # RK4
        s2 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k1))
        k2, _ = deriv(s2)
        s3 = tuple(si + 0.5 * h * ki for si, ki in zip(s, k2))
        k3, _ = deriv(s3)
        s4 = tuple(si + h * ki for si, ki in zip(s, k3))
        k4, _ = deriv(s4)
        sn = tuple(si + h / 6.0 * (a1 + 2 * a2 + 2 * a3 + a4) for si, a1, a2, a3, a4 in zip(s, k1, k2, k3, k4))
        if not all(math.isfinite(v) for v in sn):
            res.message = "החישוב התבדר (ערך לא סופי) — בדוק נתוני קלט"
            return res
        tn = t + h
        k1n, auxn = deriv(sn)
        sg = sg_of(sn[6], auxn[3], auxn[0], auxn[4])
        sg_min = min(sg_min, sg)
        max_mach = max(max_mach, auxn[1])
        if sn[1] > apex_y:
            apex_y, apex_x, apex_t = sn[1], sn[0], tn
        if sn[1] > ground(sn[0], sn[2]) + 0.5:
            went_up = True
        # תנאי פגיעה: בירידה וחציית פני הקרקע במטרה
        f_new = sn[1] - ground(sn[0], sn[2])
        if sn[4] < 0.0 and f_new <= 0.0 and (went_up or tgt_rel <= 0.0):
            f_old = s[1] - ground(s[0], s[2])
            frac = f_old / (f_old - f_new) if f_old != f_new else 1.0
            frac = min(max(frac, 0.0), 1.0)
            si = tuple(a + frac * (b - a) for a, b in zip(s, sn))
            ti = t + frac * h
            _, auxi = deriv(si)
            if record:
                rec(ti, si, auxi, sg)
            x, y, z, ux, uy, uz, p = si
            horiz = math.hypot(ux, uz)
            dev = math.atan2(z, x)
            res.ok = True
            res.message = "פגיעה"
            res.impact = {
                "time_of_flight_s": round(ti, 3),
                "range_x_m": round(x, 2),
                "drift_z_m": round(z, 2),
                "ground_range_m": round(math.hypot(x, z), 2),
                "deviation": both(dev),
                "drift_direction": "R" if z >= 0 else "L",
                "impact_velocity_mps": round(auxi[0], 1),
                "impact_mach": round(auxi[1], 3),
                "angle_of_fall": both(math.atan2(-uy, horiz)),
                "apex_height_m": round(apex_y, 1),
                "apex_range_m": round(apex_x, 1),
                "apex_time_s": round(apex_t, 2),
                "max_ordinate_msl_m": round(apex_y + gun_alt, 1),
                "spin_muzzle_rps": round(p0 / (2 * math.pi), 1),
                "spin_impact_rps": round(p / (2 * math.pi), 1),
                "sg_muzzle": round(sg0, 3),
                "sg_min": round(sg_min, 3),
                "max_yaw_repose": both(max(res.yaw_repose) if res.yaw_repose else auxi[2]),
                "max_mach": round(max_mach, 3),
            }
            return res
        if record:
            rec(tn, sn, auxn, sg)
        s, t, k1 = sn, tn, k1n
        if t > 5.0 and not went_up and sn[4] < 0.0:
            res.message = "המסלול לא מגיע לגובה המטרה"
            return res
    res.message = "חריגה מזמן הסימולציה המרבי"
    return res


def stability_warnings(res: TrajectoryResult):
    w = []
    imp = res.impact
    if not imp:
        return w
    if imp["sg_muzzle"] < 1.0:
        w.append(f"Sg בלוע {imp['sg_muzzle']:.2f} < 1 — הפגז אינו יציב ג'ירוסקופית; המודל אינו תקף")
    elif imp["sg_min"] < 1.0:
        w.append(f"Sg מינימלי במסלול {imp['sg_min']:.2f} < 1 — אובדן יציבות סביב הקודקוד; המודל אינו תקף")
    elif imp["sg_min"] < 1.3:
        w.append(f"Sg מינימלי {imp['sg_min']:.2f} — יציבות גבולית, דיוק המודל יורד")
    yr = imp["max_yaw_repose"]["deg"]
    if yr > 5.0:
        w.append(f"זווית מנוחה מרבית {yr:.1f}° — מעבר לתחום הלינארי, הקירוב נחלש")
    return w
