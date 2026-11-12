"""חבילת-רגרסיה תחת .qa/tests/ (לא בתיקיית-הבדיקות של הפרויקט - לפי מגבלת הריצה האוטונומית).
מריצה כ-subprocess את קבצי-הבדיקה הקיימים של הפרויקט (לא משכפלת/לא עורכת את הלוגיקה שלהם) +
בדיקות-שחזור (repro tests) לממצאים קונקרטיים שנמצאו (F-011/F-012/F-013/F-014). כולן self-contained,
0 קריאות-רשת-חיצוניות אמיתיות (F-011 משתמש ב-Flask test_client שהוא WSGI in-process, לא socket).

הרצה: python .qa/tests/run_regression.py  (מהשורש, עם .venv הראשי של הפרויקט - לא .qa/.venv,
כי אלה בדיקות-הפרויקט עצמו, לא כלי-ניתוח)
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
TESTS_DIR = Path(__file__).resolve().parent

# חייבות לעבור - רגרסיה אמיתית על קוד-קיים-ותקין
REGRESSION_SUITES = [
    ("mpm/ ballistics engine - self_test.py", PROJECT_ROOT / "tests" / "self_test.py"),
    ("mpm_api.py - test_ballistics_api.py", PROJECT_ROOT / "tests" / "test_ballistics_api.py"),
]

# צפויות להיכשל כרגע (משחזרות ממצא פתוח) - עוברות רק אחרי תיקון מאושר
BUG_REPRO_TESTS = [
    ("F-011 /radar_doppler/cancel missing return", TESTS_DIR / "test_f011_radar_cancel_return.py"),
    ("F-012 web/map.html stray file", TESTS_DIR / "test_f012_no_stray_webmap.py"),
    ("F-013 OpenStreetMap attribution missing", TESTS_DIR / "test_f013_osm_attribution.py"),
    ("F-014 ANOTHER_API_KEY not scanned", TESTS_DIR / "test_f014_secret_env_vars_coverage.py"),
]


def run_one(label, path):
    proc = subprocess.run([str(PYTHON), str(path)], cwd=PROJECT_ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
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
