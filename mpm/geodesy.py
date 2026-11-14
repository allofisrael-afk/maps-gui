# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""מרחק ואזימוט בין נקודות על אליפסואיד WGS84 (נוסחת Vincenty ההפוכה, דיוק מילימטרי)."""
import math

A = 6378137.0
F = 1 / 298.257223563
B = A * (1 - F)


def inverse(lat1, lon1, lat2, lon2):
    """קלט במעלות. מחזיר (distance_m, initial_azimuth_deg) מנקודה 1 לנקודה 2."""
    if abs(lat1 - lat2) < 1e-12 and abs(lon1 - lon2) < 1e-12:
        return 0.0, 0.0
    L = math.radians(lon2 - lon1)
    U1 = math.atan((1 - F) * math.tan(math.radians(lat1)))
    U2 = math.atan((1 - F) * math.tan(math.radians(lat2)))
    sU1, cU1, sU2, cU2 = math.sin(U1), math.cos(U1), math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.sqrt((cU2 * sl) ** 2 + (cU1 * sU2 - sU1 * cU2 * cl) ** 2)
        if ss == 0:
            return 0.0, 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl
        sig = math.atan2(ss, cs)
        sa = cU1 * cU2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * sU1 * sU2 / c2a if c2a != 0 else 0.0
        C = F / 16 * c2a * (4 + F * (4 - 3 * c2a))
        lam_p = lam
        lam = L + (1 - C) * F * sa * (sig + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm * c2sm)))
        if abs(lam - lam_p) < 1e-12:
            break
    else:
        return _haversine(lat1, lon1, lat2, lon2)
    u2 = c2a * (A * A - B * B) / (B * B)
    Ak = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    Bk = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    ds = Bk * ss * (c2sm + Bk / 4 * (cs * (-1 + 2 * c2sm * c2sm)
                                      - Bk / 6 * c2sm * (-3 + 4 * ss * ss) * (-3 + 4 * c2sm * c2sm)))
    dist = B * Ak * (sig - ds)
    az = math.degrees(math.atan2(cU2 * math.sin(lam), cU1 * sU2 - sU1 * cU2 * math.cos(lam))) % 360.0
    return dist, az


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * R * math.asin(math.sqrt(h))
    az = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                 math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
    return d, az


def direct(lat, lon, az_deg, dist):
    """נקודת יעד ממיקום, אזימוט ומרחק (Vincenty הישירה, WGS84)."""
    a1 = math.radians(az_deg)
    sa1, ca1 = math.sin(a1), math.cos(a1)
    tU1 = (1 - F) * math.tan(math.radians(lat))
    cU1 = 1 / math.sqrt(1 + tU1 * tU1)
    sU1 = tU1 * cU1
    s1 = math.atan2(tU1, ca1)
    sa = cU1 * sa1
    c2a = 1 - sa * sa
    u2 = c2a * (A * A - B * B) / (B * B)
    Ak = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    Bk = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    sig = dist / (B * Ak)
    for _ in range(200):
        c2sm = math.cos(2 * s1 + sig)
        ss, cs = math.sin(sig), math.cos(sig)
        ds = Bk * ss * (c2sm + Bk / 4 * (cs * (-1 + 2 * c2sm * c2sm)
                                          - Bk / 6 * c2sm * (-3 + 4 * ss * ss) * (-3 + 4 * c2sm * c2sm)))
        sig_p = sig
        sig = dist / (B * Ak) + ds
        if abs(sig - sig_p) < 1e-12:
            break
    ss, cs = math.sin(sig), math.cos(sig)
    c2sm = math.cos(2 * s1 + sig)
    tmp = sU1 * ss - cU1 * cs * ca1
    lat2 = math.atan2(sU1 * cs + cU1 * ss * ca1, (1 - F) * math.sqrt(sa * sa + tmp * tmp))
    lam = math.atan2(ss * sa1, cU1 * cs - sU1 * ss * ca1)
    C = F / 16 * c2a * (4 + F * (4 - 3 * c2a))
    L = lam - (1 - C) * F * sa * (sig + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm * c2sm)))
    lon2 = (lon + math.degrees(L) + 540) % 360 - 180
    return math.degrees(lat2), lon2
