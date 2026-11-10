"""פרופיל אטמוספרי: טמפרטורה, לחץ, צפיפות, מהירות קול ורוח כפונקציה של גובה מעל פני הים.

הפרופיל נבנה על רשת אנכית צפופה (כל 25 מ'), כך שחיפוש בזמן האינטגרציה מהיר.
הלחץ מחושב באינטגרציה הידרוסטטית מהקרקע, בעקביות עם הטמפרטורה שבכל שכבה.
הרוח נשמרת ברכיבים: מזרח (E) וצפון (N), בכיוון שאליו היא נושבת.
"""
import math

R_AIR = 287.05287      # J/(kg·K)
GAMMA = 1.4
G0 = 9.80665
GRID_DZ = 25.0
TOP_MSL = 40000.0


def std_lapse(h):
    """קצב שינוי טמפרטורה סטנדרטי (ICAO) לפי גובה [K/m]."""
    if h < 11000.0:
        return -0.0065
    if h < 20000.0:
        return 0.0
    if h < 32000.0:
        return 0.001
    return 0.0028


def isa_temperature(h):
    """טמפרטורה סטנדרטית ICAO [K] בגובה h מעל פני הים."""
    if h < 11000.0:
        return 288.15 - 0.0065 * h
    if h < 20000.0:
        return 216.65
    if h < 32000.0:
        return 216.65 + 0.001 * (h - 20000.0)
    return 228.65 + 0.0028 * (h - 32000.0)


def isa_pressure(h):
    """לחץ סטנדרטי ICAO [Pa] (אינטגרציה הידרוסטטית של isa_temperature)."""
    p = 101325.0
    z = 0.0
    step = 50.0 if h >= 0 else -50.0
    while (step > 0 and z < h) or (step < 0 and z > h):
        dz = min(step, h - z) if step > 0 else max(step, h - z)
        tm = isa_temperature(z + dz / 2.0)
        p *= math.exp(-G0 * dz / (R_AIR * tm))
        z += dz
    return p


def wind_from_to_components(speed, dir_from_deg):
    """כיוון רוח מטאורולוגי ("נושבת מ-") ← רכיבי מזרח/צפון של הווקטור."""
    a = math.radians(dir_from_deg)
    return -speed * math.sin(a), -speed * math.cos(a)


def wind_components_to_from(we, wn):
    speed = math.hypot(we, wn)
    if speed < 1e-9:
        return 0.0, 0.0
    return speed, math.degrees(math.atan2(-we, -wn)) % 360.0


class AtmosphereProfile:
    """פרופיל על רשת אחידה. אובייקטים נוצרים דרך standard() או from_levels()."""

    def __init__(self, h0, T, P, we, wn, description="", surface_alt=0.0, levels_used=None):
        self.h0 = h0
        self.T = T
        self.P = P
        self.we = we
        self.wn = wn
        self.n = len(T)
        self.description = description
        self.surface_alt = surface_alt
        self.levels_used = levels_used or []

    # ---------- חיפוש מהיר ----------
    def at(self, h):
        """מחזיר (rho, a, T, P, wind_e, wind_n) בגובה h [m MSL]."""
        f = (h - self.h0) / GRID_DZ
        if f <= 0.0:
            i, t = 0, 0.0
        elif f >= self.n - 1:
            i, t = self.n - 2, 1.0
        else:
            i = int(f)
            t = f - i
        T = self.T[i] + t * (self.T[i + 1] - self.T[i])
        P = self.P[i] * (self.P[i + 1] / self.P[i]) ** t
        we = self.we[i] + t * (self.we[i + 1] - self.we[i])
        wn = self.wn[i] + t * (self.wn[i + 1] - self.wn[i])
        rho = P / (R_AIR * T)
        a = math.sqrt(GAMMA * R_AIR * T)
        return rho, a, T, P, we, wn

    def summary(self, heights=None):
        """טבלה מקוצרת לתצוגה: גובה, טמפ', לחץ, צפיפות, רוח."""
        heights = heights or [self.surface_alt + d for d in (0, 500, 1000, 2000, 3000, 5000, 7000, 10000, 15000, 20000)]
        out = []
        for h in heights:
            rho, a, T, P, we, wn = self.at(h)
            spd, dfrom = wind_components_to_from(we, wn)
            out.append({
                "alt_msl_m": round(h, 0), "temp_c": round(T - 273.15, 1), "pressure_hpa": round(P / 100.0, 1),
                "density_kgm3": round(rho, 4), "sound_mps": round(a, 1),
                "wind_speed_mps": round(spd, 1), "wind_from_deg": round(dfrom, 0),
            })
        return out

    # ---------- בנייה ----------
    @classmethod
    def _build(cls, surface_alt, surface_T, surface_P, T_func, wind_func, description, levels_used=None):
        h0 = surface_alt - 2000.0
        n = int((TOP_MSL - h0) / GRID_DZ) + 1
        hs = [h0 + i * GRID_DZ for i in range(n)]
        T = [T_func(h) for h in hs]
        P = [0.0] * n
        # אינטגרציה הידרוסטטית מעלה ומטה מהקרקע
        k = int((surface_alt - h0) / GRID_DZ)
        Ts = T_func(surface_alt)
        P[k] = surface_P * math.exp(-G0 * (hs[k] - surface_alt) / (R_AIR * 0.5 * (Ts + T[k])))
        for i in range(k + 1, n):
            P[i] = P[i - 1] * math.exp(-G0 * GRID_DZ / (R_AIR * 0.5 * (T[i] + T[i - 1])))
        for i in range(k - 1, -1, -1):
            P[i] = P[i + 1] * math.exp(G0 * GRID_DZ / (R_AIR * 0.5 * (T[i] + T[i + 1])))
        we, wn = [], []
        for h in hs:
            e, nn = wind_func(h)
            we.append(e)
            wn.append(nn)
        return cls(h0, T, P, we, wn, description, surface_alt, levels_used)

    @classmethod
    def standard(cls, surface_alt=0.0, surface_temp_c=None, surface_pressure_hpa=None,
                 wind_speed=0.0, wind_from_deg=0.0):
        """אטמוספרה סטנדרטית מותאמת לגובה, טמפרטורה ולחץ בקרקע, ורוח קבועה אופציונלית."""
        Ts = (surface_temp_c + 273.15) if surface_temp_c is not None else isa_temperature(surface_alt)
        Ps = (surface_pressure_hpa * 100.0) if surface_pressure_hpa is not None else isa_pressure(surface_alt)
        dT = Ts - isa_temperature(surface_alt)

        def T_func(h):
            # הסטת עקומת ICAO כך שתעבור דרך טמפרטורת הקרקע; ההסטה דועכת עד הטרופופאוזה
            fade = max(0.0, 1.0 - max(0.0, h - surface_alt) / max(1.0, 11000.0 - surface_alt)) if surface_alt < 11000 else 0.0
            return isa_temperature(h) + dT * fade

        we, wn = wind_from_to_components(wind_speed, wind_from_deg)
        desc = (f"ICAO standard, surface {surface_alt:.0f} m, {Ts - 273.15:.1f}°C, {Ps / 100:.1f} hPa"
                + (f", wind {wind_speed:.1f} m/s from {wind_from_deg:.0f}°" if wind_speed > 0 else ""))
        return cls._build(surface_alt, Ts, Ps, T_func, lambda h: (we, wn), desc)

    @classmethod
    def from_levels(cls, surface, levels, description="Met by layers"):
        """
        surface: {"alt_m", "temp_c", "pressure_hpa", "wind_speed_mps"?, "wind_dir_deg"?}
        levels:  [{"height_m" (MSL), "temp_c", "wind_speed_mps", "wind_dir_deg"}, ...]
        wind_dir_deg = כיוון מטאורולוגי ("נושבת מ-"), במעלות מצפון אמיתי.
        מעל השכבה העליונה: טמפרטורה לפי קצב סטנדרטי, רוח קבועה.
        """
        s_alt = float(surface["alt_m"])
        pts = [(s_alt, float(surface["temp_c"]) + 273.15,
                *wind_from_to_components(float(surface.get("wind_speed_mps", 0.0) or 0.0),
                                         float(surface.get("wind_dir_deg", 0.0) or 0.0)))]
        for L in levels:
            h = float(L["height_m"])
            if h <= s_alt + 1.0:
                continue
            pts.append((h, float(L["temp_c"]) + 273.15,
                        *wind_from_to_components(float(L.get("wind_speed_mps", 0.0) or 0.0),
                                                 float(L.get("wind_dir_deg", 0.0) or 0.0))))
        pts.sort(key=lambda p: p[0])
        # הסרת כפילויות גובה
        clean = [pts[0]]
        for p in pts[1:]:
            if p[0] - clean[-1][0] > 1.0:
                clean.append(p)
        pts = clean
        top_h, top_T = pts[-1][0], pts[-1][1]
        hs = [p[0] for p in pts]

        def interp(h, idx):
            if h <= hs[0]:
                return pts[0][idx]
            if h >= hs[-1]:
                return pts[-1][idx]
            lo, hi = 0, len(hs) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if hs[mid] <= h:
                    lo = mid
                else:
                    hi = mid
            t = (h - hs[lo]) / (hs[hi] - hs[lo])
            return pts[lo][idx] + t * (pts[hi][idx] - pts[lo][idx])

        def T_func(h):
            if h < hs[0]:
                return pts[0][1] + 0.0065 * (hs[0] - h)
            if h <= top_h:
                return interp(h, 1)
            # מעל השכבה העליונה: המשך לפי צורת עקומת ICAO
            return top_T + (isa_temperature(h) - isa_temperature(top_h))

        def wind_func(h):
            return interp(h, 2), interp(h, 3)

        Ps = float(surface.get("pressure_hpa") or isa_pressure(s_alt) / 100.0) * 100.0
        used = [{"height_m": round(p[0], 0), "temp_c": round(p[1] - 273.15, 1),
                 "wind_speed_mps": round(wind_components_to_from(p[2], p[3])[0], 1),
                 "wind_dir_deg": round(wind_components_to_from(p[2], p[3])[1], 0)} for p in pts]
        return cls._build(s_alt, pts[0][1], Ps, T_func, wind_func,
                          f"{description} ({len(pts)} levels, top {top_h / 1000:.1f} km)", used)
