"""המרות יחידות זוויתיות. מיל נאט"ו: מעגל מלא = 6400 מיל."""
import math

MILS_PER_CIRCLE = 6400.0
RAD_PER_MIL = 2.0 * math.pi / MILS_PER_CIRCLE


def mils_to_rad(m):
    return m * RAD_PER_MIL


def rad_to_mils(r):
    return r / RAD_PER_MIL


def deg_to_rad(d):
    return math.radians(d)


def rad_to_deg(r):
    return math.degrees(r)


def angle_to_rad(value, unit):
    """unit: 'mils' או 'deg'."""
    unit = (unit or "mils").lower()
    if unit in ("mil", "mils"):
        return mils_to_rad(value)
    if unit in ("deg", "degree", "degrees"):
        return deg_to_rad(value)
    raise ValueError(f"יחידת זווית לא מוכרת: {unit}")


def both(rad):
    """מחזיר מילון עם הזווית במילים ובמעלות."""
    return {"mils": round(rad_to_mils(rad), 2), "deg": round(rad_to_deg(rad), 4)}


def normalize_az_rad(a):
    return a % (2.0 * math.pi)
