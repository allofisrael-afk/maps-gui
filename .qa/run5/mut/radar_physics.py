# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""
radar_physics — נוסחאות המכ"ם המשותפות (רעיוני/חינוכי, לא מבוסס מערכת אמיתית): משוואת המכ"ם, ריבוד,
דופלר (מהירויות עיוורות), טווח חד-משמעי, הפסד סריקה של מערך-מופעים, וקליטת הפרמטרים המשותפים.

הועבר כמו שהוא מ-weather_server.py (26/11/2026, החלטת הבעלים, MAPS-GUI_SRS.md FR-D-280) כדי שהשרת (Desktop)
והאפליקציה (Android, Python דרך Chaquopy) ישתמשו במקור אמת אחד. weather_server.py מייבא מכאן את אותם שמות.
השינוי היחיד בהעברה: _doppler_detectable — רוחב חור קבוע (±MDV) סביב כל מהירות עיוורת (החלטת הבעלים).
stdlib בלבד.
"""

import math  # טריגונומטריה ושורשים

# ── גבולות משותפים עם רדיוס-הראייה (weather_server.py מייבא אותם בחזרה, אותם שמות) ──
_RADIAL_RANGE_KM_MIN, _RADIAL_RANGE_KM_MAX = 0.5, 300.0  # טווח מרחק מותר, ק"מ
_RADIAL_RIDGE_MARGIN_MIN, _RADIAL_RIDGE_MARGIN_MAX = 0.0, 10.0  # מרווח רכס מותר, מעלות
_RADIAL_VERTICAL_CENTER_MIN, _RADIAL_VERTICAL_CENTER_MAX = -45.0, 45.0  # טווח מותר למרכז האלומה, מעלות
_RADIAL_VERTICAL_WIDTH_MIN, _RADIAL_VERTICAL_WIDTH_MAX = 1.0, 90.0  # טווח מותר לרוחב האלומה, מעלות

# ── קבועי מכ"ם-דופלר: ברירות מחדל וגבולות לכל פרמטר ──
_RADAR_RANGE_KM_DEFAULT = 50.0  # טווח בדיקה — שונה מרדיוס-הראייה (5) כי מכ"ם טיפוסי סורק רחוק יותר
_RADAR_H_ANTENNA_DEFAULT_M = 15.0  # גובה אנטנה ברירת מחדל
_RADAR_VBEAM_CENTER_DEFAULT_DEG = 0.0  # מרכז שדה-ראייה אנכי — אופקי כברירת מחדל
_RADAR_VBEAM_WIDTH_DEFAULT_DEG = 10.0  # רוחב שדה-ראייה אנכי — רחב יותר מרדיוס-הראייה (4°)
_RADAR_MIN_RANGE_KM_DEFAULT = 1.0  # "טווח מת" ברירת מחדל
_RADAR_POWER_KW_DEFAULT, _RADAR_POWER_KW_MIN, _RADAR_POWER_KW_MAX = 100.0, 0.1, 5000.0  # הספק שידור שיא, קילוואט
_RADAR_GAIN_DBI_DEFAULT, _RADAR_GAIN_DBI_MIN, _RADAR_GAIN_DBI_MAX = 30.0, 0.0, 50.0  # רווח אנטנה, dBi
_RADAR_FREQ_MHZ_DEFAULT, _RADAR_FREQ_MHZ_MIN, _RADAR_FREQ_MHZ_MAX = 3000.0, 100.0, 20000.0  # תדר עבודה, MHz — ברירת מחדל S-band
_RADAR_SENSITIVITY_DBM_DEFAULT, _RADAR_SENSITIVITY_DBM_MIN, _RADAR_SENSITIVITY_DBM_MAX = -100.0, -140.0, -60.0  # רגישות מקלט, dBm
_RADAR_SYSTEM_LOSSES_DB = 6.0  # הפסדי מערכת — קבוע, לא נחשף כשדה למשתמש
_RADAR_RCS_M2_DEFAULT, _RADAR_RCS_M2_MIN, _RADAR_RCS_M2_MAX = 2.0, 0.001, 1000.0  # שטח חתך רדארי, מ"ר — ברירת מחדל "מטוס קל"
_RADAR_PRF_HZ_DEFAULT, _RADAR_PRF_HZ_MIN, _RADAR_PRF_HZ_MAX = 1000.0, 50.0, 20000.0  # תדר חזרת פולסים, Hz
_RADAR_MDV_KT_DEFAULT, _RADAR_MDV_KT_MIN, _RADAR_MDV_KT_MAX = 20.0, 0.0, 200.0  # מהירות רדיאלית מינימלית לגילוי, קשר
_RADAR_TARGET_SPEED_KT_DEFAULT, _RADAR_TARGET_SPEED_KT_MIN, _RADAR_TARGET_SPEED_KT_MAX = 250.0, 0.0, 1500.0  # מהירות המטרה המשוערת, קשר
_RADAR_TARGET_HEADING_DEG_DEFAULT = 0.0  # כיוון תנועת המטרה המשוער — צפונה כברירת מחדל
_KT_TO_MS = 0.514444  # מקדם המרה קשר -> מטר/שנייה
_RADAR_REFLECTIVITY = {'land': 0.5, 'sea': 0.9}  # מקדם החזרה מפושט לפי סוג משטח — להדגמה בלבד, לא ערך פיזיקלי מדויק
_RADAR_REFLECTIVITY_DEFAULT = 'land'
_RADAR_ANTENNA_TYPES = ('generic', 'phased_array')
_RADAR_ANTENNA_TYPE_DEFAULT = 'generic'
_RADAR_BORESIGHT_DEG_DEFAULT = 0.0  # כיוון-פנים של המערך — צפונה כברירת מחדל
_RADAR_MAX_SCAN_DEG_DEFAULT, _RADAR_MAX_SCAN_DEG_MIN, _RADAR_MAX_SCAN_DEG_MAX = 60.0, 5.0, 180.0  # זווית סריקה מקסימלית מכיוון הפנים


def _radar_max_range_m(power_kw, gain_dbi, freq_mhz, rcs_m2, sensitivity_dbm, losses_db=_RADAR_SYSTEM_LOSSES_DB):
    """טווח גילוי מקסימלי לפי משוואת המכ"ם הסטנדרטית (monostatic):
    R_max = [(Pt·G²·λ²·σ) / ((4π)³·Pmin·L)]^(1/4).
    ככל שההספק/הרווח/שטח-החתך גדולים יותר — טווח הגילוי גדל; ככל שהתדר גבוה יותר
    (אורך גל קצר) — טווח הגילוי קטן. רעיוני/חינוכי, לא כולל רווחי עיבוד סיגנל מתקדמים."""
    Pt = power_kw * 1000.0  # קילוואט -> ואט
    G = 10 ** (gain_dbi / 10.0)  # dBi -> יחס ליניארי
    wavelength_m = 299792458.0 / (freq_mhz * 1e6)  # אורך גל = מהירות האור / תדר
    Pmin = 10 ** ((sensitivity_dbm - 30) / 10.0)  # dBm -> ואט (בסיס dBm הוא מיליוואט)
    L = 10 ** (losses_db / 10.0)  # dB -> יחס ליניארי
    numerator = Pt * (G ** 2) * (wavelength_m ** 2) * rcs_m2
    denominator = ((4 * math.pi) ** 3) * Pmin * L
    if numerator <= 0 or denominator <= 0:
        return 0.0
    return (numerator / denominator) ** 0.25


def _lobing_factor(elevation_angle_deg, h_antenna_m, wavelength_m, reflectivity):
    """גורם עוצמת 'ריבוד' (multipath lobing) — השתקפות מהקרקע יוצרת התאבכות עם הקרן
    הישירה, כך שבזוויות עילוי מסוימות הכיסוי מוגבר ובאחרות כמעט מבוטל (לא קונוס חלק).
    F=|1+ρ·e^(iΔφ)|, כאשר Δφ תלוי בגובה האנטנה, זווית העילוי ואורך הגל. מוכפל ישירות
    בטווח הגילוי (F נע בין 1-ρ ל-1+ρ). קירוב גס מעל משטח שטוח, רעיוני/חינוכי בלבד."""
    theta_rad = math.radians(elevation_angle_deg)
    delta_phi = (4 * math.pi * h_antenna_m * math.sin(theta_rad)) / wavelength_m
    real = 1 + reflectivity * math.cos(delta_phi)
    imag = reflectivity * math.sin(delta_phi)
    return math.sqrt(real * real + imag * imag)


def _doppler_detectable(radial_speed_ms, mdv_ms, wavelength_m, prf_hz):
    """True אם מהירות רדיאלית נתונה תתגלה ע"י מכ"ם דופלר. מסנן הדופלר חוסם את התחום |v|<MDV סביב אפס
    (רקע נייח: קרקע/עננים), ותגובתו מחזורית לפי ה-PRF — לכן אותו חור בדיוק (±MDV) חוזר סביב כל
    "מהירות עיוורת" n·λ·PRF/2. תוקן 26/11/2026 לפי החלטת הבעלים (MAPS-GUI_SRS.md FR-D-280): קודם רוחב
    החור היה 5% מהמהירות העיוורת עצמה וגדל עם n, כך שמ-n≥10 החורים כיסו כל מהירות — כמעט כל פגז סומן "עיוור"."""
    if radial_speed_ms < mdv_ms:  # בתוך החור סביב אפס — מסונן כרקע נייח
        return False  # לא מתגלה
    v_blind_unit = wavelength_m * prf_hz / 2.0  # מהירות עיוורת בסיסית (n=1)
    if v_blind_unit <= 0:  # מקרה קצה — לא אמור לקרות עם PRF תקין
        return True  # אין מהירויות עיוורות
    n = round(radial_speed_ms / v_blind_unit)  # הכפולה הקרובה ביותר
    if n >= 1 and abs(radial_speed_ms - n * v_blind_unit) < mdv_ms:  # בתוך אותו חור (±MDV) סביב המהירות העיוורת
        return False  # לא מתגלה
    return True  # מתגלה


def _max_unambiguous_range_m(prf_hz):
    """טווח לא-חד-משמעי מקסימלי: R_unambig=c/(2·PRF) — מעבר לו, זמן החזרת פולס עלול
    להתבלבל עם הפולס הבא. תקרת טווח נוספת, לא קשורה ל-Doppler עצמו."""
    return 299792458.0 / (2.0 * prf_hz)


def _angular_diff_deg(a, b):
    """הפרש הזוויות הקצר ביותר בין שתי מעלות (0-180) — למשל בין 350° ל-10° ההפרש הוא 20°, לא 340°."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _scan_loss_factor(bearing_deg, boresight_deg, max_scan_deg):
    """גורם הפסד-סריקה למכ"ם מערך-מופעים — הרווח האפקטיבי יורד ככל שמסטים את הקרן
    האלקטרונית הרחק מכיוון-הפנים (boresight), ומעבר לזווית הסריקה המקסימלית האנטנה
    כלל לא מכסה את הכיוון (מחזיר 0.0). R_max תלוי ב-G² בתוך שורש רביעי — כלומר R∝G^0.5 —
    ולכן ההפסד על הטווח (לא על הרווח עצמו) הוא שורש של הפסד ה-cosine הסטנדרטי."""
    scan_angle = _angular_diff_deg(bearing_deg, boresight_deg)
    if scan_angle > max_scan_deg:
        return 0.0  # מחוץ לתחום הסריקה של המערך — לא מכוסה כלל, לא רק מוחלש
    return math.sqrt(math.cos(math.radians(scan_angle)))


def _parse_radar_common_params(args):
    """קליטת/צמידת כל הפרמטרים המשותפים לחישוב מכ"ם-דופלר (משוואת מכ"ם/דופלר/תפוצה/
    מערך-מופעים/גיאומטריה) — משותף בין /radar_doppler/start (סריקה מלאה) ו-
    /radar_doppler/profile (קרן בודדת), כדי לא לשכפל ~19 בלוקי parsing כמעט-זהים.
    לא כולל lat/lon/bearing (שונים במהות בין שני ה-endpoints, כל אחד קולט אותם בעצמו)."""
    def _f(name, default):
        try:
            v = float(args.get(name, default))  # המרה
        except (TypeError, ValueError):
            return default
        return v if math.isfinite(v) else default  # T7 (F-032): NaN/Inf לא עוברים את min/max — ברירת המחדל במקום

    range_km = min(max(_f('range_km', _RADAR_RANGE_KM_DEFAULT), _RADIAL_RANGE_KM_MIN), _RADIAL_RANGE_KM_MAX)
    min_range_km = min(max(_f('min_range_km', _RADAR_MIN_RANGE_KM_DEFAULT), 0.0), range_km)  # לא שלילי, לא מעל range_km עצמו
    ridge_margin_deg = min(max(_f('ridge_margin_deg', 0.0), _RADIAL_RIDGE_MARGIN_MIN), _RADIAL_RIDGE_MARGIN_MAX)
    h_antenna = _f('h_antenna', _RADAR_H_ANTENNA_DEFAULT_M)
    vertical_center_deg = min(max(_f('vertical_center_deg', _RADAR_VBEAM_CENTER_DEFAULT_DEG),
                                   _RADIAL_VERTICAL_CENTER_MIN), _RADIAL_VERTICAL_CENTER_MAX)
    vertical_width_deg = min(max(_f('vertical_width_deg', _RADAR_VBEAM_WIDTH_DEFAULT_DEG),
                                  _RADIAL_VERTICAL_WIDTH_MIN), _RADIAL_VERTICAL_WIDTH_MAX)
    power_kw = min(max(_f('power_kw', _RADAR_POWER_KW_DEFAULT), _RADAR_POWER_KW_MIN), _RADAR_POWER_KW_MAX)
    gain_dbi = min(max(_f('gain_dbi', _RADAR_GAIN_DBI_DEFAULT), _RADAR_GAIN_DBI_MIN), _RADAR_GAIN_DBI_MAX)
    freq_mhz = min(max(_f('freq_mhz', _RADAR_FREQ_MHZ_DEFAULT), _RADAR_FREQ_MHZ_MIN), _RADAR_FREQ_MHZ_MAX)
    rcs_m2 = min(max(_f('rcs_m2', _RADAR_RCS_M2_DEFAULT), _RADAR_RCS_M2_MIN), _RADAR_RCS_M2_MAX)
    sensitivity_dbm = min(max(_f('sensitivity_dbm', _RADAR_SENSITIVITY_DBM_DEFAULT),
                              _RADAR_SENSITIVITY_DBM_MIN), _RADAR_SENSITIVITY_DBM_MAX)
    prf_hz = min(max(_f('prf_hz', _RADAR_PRF_HZ_DEFAULT), _RADAR_PRF_HZ_MIN), _RADAR_PRF_HZ_MAX)
    mdv_kt = min(max(_f('mdv_kt', _RADAR_MDV_KT_DEFAULT), _RADAR_MDV_KT_MIN), _RADAR_MDV_KT_MAX)
    target_speed_kt = min(max(_f('target_speed_kt', _RADAR_TARGET_SPEED_KT_DEFAULT),
                             _RADAR_TARGET_SPEED_KT_MIN), _RADAR_TARGET_SPEED_KT_MAX)
    target_heading_deg = _f('target_heading_deg', _RADAR_TARGET_HEADING_DEG_DEFAULT) % 360  # מנרמל שלילי/מעל 360

    lobing_enabled = str(args.get('lobing_enabled', 'false')).lower() == 'true'  # toggle — כבוי כברירת מחדל
    reflectivity_key = args.get('reflectivity', _RADAR_REFLECTIVITY_DEFAULT)
    if reflectivity_key not in _RADAR_REFLECTIVITY:
        reflectivity_key = _RADAR_REFLECTIVITY_DEFAULT  # ערך לא מוכר — נופל לברירת המחדל בשקט, לא שגיאה

    antenna_type = args.get('antenna_type', _RADAR_ANTENNA_TYPE_DEFAULT)
    if antenna_type not in _RADAR_ANTENNA_TYPES:
        antenna_type = _RADAR_ANTENNA_TYPE_DEFAULT  # ערך לא מוכר — נופל לברירת המחדל בשקט, לא שגיאה
    boresight_deg = _f('boresight_deg', _RADAR_BORESIGHT_DEG_DEFAULT) % 360
    max_scan_deg = min(max(_f('max_scan_deg', _RADAR_MAX_SCAN_DEG_DEFAULT),
                           _RADAR_MAX_SCAN_DEG_MIN), _RADAR_MAX_SCAN_DEG_MAX)

    return {
        'range_km': range_km, 'min_range_km': min_range_km, 'ridge_margin_deg': ridge_margin_deg,
        'h_antenna': h_antenna, 'vertical_center_deg': vertical_center_deg, 'vertical_width_deg': vertical_width_deg,
        'power_kw': power_kw, 'gain_dbi': gain_dbi, 'freq_mhz': freq_mhz, 'rcs_m2': rcs_m2,
        'sensitivity_dbm': sensitivity_dbm, 'prf_hz': prf_hz, 'mdv_kt': mdv_kt,
        'target_speed_kt': target_speed_kt, 'target_heading_deg': target_heading_deg,
        'lobing_enabled': lobing_enabled, 'reflectivity_key': reflectivity_key,
        'antenna_type': antenna_type, 'boresight_deg': boresight_deg, 'max_scan_deg': max_scan_deg,
    }
