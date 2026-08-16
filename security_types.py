# -*- coding: utf-8 -*-
""" מבנה התוצאה המשותף לכל בדיקות האבטחה בפרויקט (security_checks.py + cis_checks.py) —
קובץ נפרד כדי ששני המודולים יוכלו לייבא אותו בלי circular import ביניהם. """
from dataclasses import dataclass


@dataclass
class SecurityFinding:
    check: str
    severity: str  # "info" | "low" | "medium" | "high"
    ok: bool        # True = לא נמצאה בעיה, False = נמצא ממצא לתשומת לב
    message: str
    elapsed_ms: float = 0.0
    server: str = "Global"  # "GeoServer"/"WeatherServer"/"FlightServer", או "Global" לממצא שחל על כל הפרויקט
    # (dependency scan, APK, בדיקות CIS) — נצרך ע"י רשת השעונים 3×3 בדשבורד לצירוף ממצא לכל שרת
    remediation: str = ""  # הנחיה/פקודה לתיקון — מוצג בדשבורד רק כשok=False
