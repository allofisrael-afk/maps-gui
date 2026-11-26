# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""חבילת-רגרסיה תחת tests/ (Q-6, 14/11/2026: הועבר מ-.qa/tests/ המבודד - מעכשיו חלק קבוע מחבילת-הבדיקות
הרגילה של הפרויקט, לא סילו-QA נפרד).
מריצה כ-subprocess את קבצי-הבדיקה הקיימים של הפרויקט (לא משכפלת/לא עורכת את הלוגיקה שלהם) +
בדיקות-שחזור (repro tests) לממצאים קונקרטיים שנמצאו (F-011/F-012/F-013/F-014). כולן self-contained,
0 קריאות-רשת-חיצוניות אמיתיות (F-011 משתמש ב-Flask test_client שהוא WSGI in-process, לא socket).

הרצה: python tests/run_regression.py  (מהשורש, עם .venv הראשי של הפרויקט - לא .qa/.venv,
כי אלה בדיקות-הפרויקט עצמו, לא כלי-ניתוח)
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Q-6: הועבר מ-.qa/tests/ ל-tests/ - שתי רמות למעלה, לא שלוש
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
TESTS_DIR = Path(__file__).resolve().parent

# חייבות לעבור - רגרסיה אמיתית על קוד-קיים-ותקין
REGRESSION_SUITES = [
    ("mpm/ ballistics engine - self_test.py", PROJECT_ROOT / "tests" / "self_test.py"),
    ("mpm_api.py - test_ballistics_api.py", PROJECT_ROOT / "tests" / "test_ballistics_api.py"),
    ("radar_track.py - test_radar_track.py", PROJECT_ROOT / "tests" / "test_radar_track.py"),  # כלי בדיקת מעקב מכ"ם, שלבים א1-א5 (FR-D-264..274)
    ("rocket_model.py - test_rocket_model.py", PROJECT_ROOT / "tests" / "test_rocket_model.py"),  # מודל הרקטה, שלב א6 (FR-D-275)
    ("radar_placement.py - test_radar_placement.py", PROJECT_ROOT / "tests" / "test_radar_placement.py"),  # הצעת מיקום, שלב ב' (FR-D-277)
    ("radar_physics.py - test_radar_physics.py", PROJECT_ROOT / "tests" / "test_radar_physics.py"),  # נוסחאות משותפות + תיקון הדופלר (FR-D-280)
    ("radar_service.py - test_radar_service.py", PROJECT_ROOT / "tests" / "test_radar_service.py"),  # צינורות משותפים + השרת דרכם (FR-D-281)
    ("radar_android.py - test_radar_android.py", PROJECT_ROOT / "tests" / "test_radar_android.py"),  # מתאם האנדרואיד דרך mpm_api.dispatch_json (FR-D-282)
]

# צפויות להיכשל כרגע (משחזרות ממצא פתוח) - עוברות רק אחרי תיקון מאושר
BUG_REPRO_TESTS = [
    ("F-011 /radar_doppler/cancel missing return", TESTS_DIR / "test_f011_radar_cancel_return.py"),
    ("F-012 web/map.html stray file", TESTS_DIR / "test_f012_no_stray_webmap.py"),
    ("F-013 OpenStreetMap attribution missing", TESTS_DIR / "test_f013_osm_attribution.py"),
    ("F-014 ANOTHER_API_KEY not scanned", TESTS_DIR / "test_f014_secret_env_vars_coverage.py"),
]


def run_one(label, path):
    # F-030: timeout=120 - שונות-זמנים אמיתית נמדדה (47-87ש', חריגה אחת מ-120ש') בלי קוד תקוע;
    # בלי timeout, תקיעה אמיתית עתידית תיתקע את כל ריצת-הרגרסיה לנצח בלי אבחון.
    try:
        proc = subprocess.run([str(PYTHON), str(path)], cwd=PROJECT_ROOT, timeout=120,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        return label, False, None, out, err + "\n[TIMEOUT] חרג מ-120 שניות - נבדק כ-FAIL"
    return label, proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr


def main():
    print("=== חבילת רגרסיה (חייבת לעבור) ===")
    regression_results = [run_one(l, p) for l, p in REGRESSION_SUITES]
    for label, ok, code, out, err in regression_results:
        print(f"{'[OK]' if ok else '[FAIL]'} {label} (exit={code})")
        if not ok:
            print(out[-2000:]); print(err[-2000:])

    print("\n=== בדיקות-שחזור לממצאים פתוחים (צפויות להיכשל עד תיקון מאושר) ===")
    repro_results = [run_one(l, p) for l, p in BUG_REPRO_TESTS]
    for label, ok, code, out, err in repro_results:
        tag = "[CLOSED - נסגר]" if ok else "[OPEN - עדיין משוחזר]"
        print(f"{tag} {label} (exit={code})")

    print("\n--- סיכום ---")
    reg_failed = [r for r in regression_results if not r[1]]
    print(f"רגרסיה: {len(regression_results) - len(reg_failed)}/{len(regression_results)} עברו")
    open_findings = [r for r in repro_results if not r[1]]
    closed_findings = [r for r in repro_results if r[1]]
    print(f"ממצאים-פתוחים: {len(open_findings)}/{len(repro_results)} עדיין משוחזרים, {len(closed_findings)} נסגרו")

    # קוד-היציאה של הסקריפט הזה תלוי רק ברגרסיה האמיתית - כשלון בבדיקת-שחזור הוא *צפוי* ולא "השבר רגרסיה"
    sys.exit(1 if reg_failed else 0)


if __name__ == "__main__":
    main()
