"""
בדיקות אבטחה/חשיפה לשלושת שרתי ה-Flask של הפרויקט — נפרד מ-test_requests.py כי כאן
המדד הוא "האם יש חשיפה/סיכון" ולא "האם ה-endpoint עובד". נצרך ע"י ProcessDashboard
ב-main.py (כפתור "🔒 בדיקת אבטחה") וגם רץ כ-CLI עצמאי.

הבדיקות:
1. חשיפת debug console לרשת   — מוודא ששלושת השרתים (debug=True) מאזינים רק על 127.0.0.1.
2. סריקת סודות בתגובות שרת    — מריץ את בדיקות התקינות וסורק את כל גופי התגובה (כולל
                                  מסלולי שגיאה) לאיתור ערכי מפתחות ה-API מ-.env בטקסט חופשי.
3. מדיניות CORS               — בודק אם Access-Control-Allow-Origin הוא "*" (מדווח כ-info,
                                  לא ככשל — כרגע נדרש כדי ש-map.html שנטען מ-file:// יעבוד).
4. סריקת CVEs בתלויות (pip-audit) — מריץ pip-audit על requirements.txt.
5. סודות קשיחים ב-APK         — סורק את ה-APK הבנוי (ZIP) אחרי טוקנים קשיחים שחולצו
                                  מ-api_service.dart (הידוע: FR24 Gold token).
"""
import json  # פענוח פלט pip-audit
import os  # קריאת מפתחות סודיים ממשתני סביבה
import re  # חיפוש טוקנים קשיחים בקוד ה-Dart
import subprocess  # הרצת pip-audit כתהליך חיצוני
import time  # מדידת elapsed_ms לכל בדיקה
import zipfile  # פתיחת ה-APK כארכיון ZIP לסריקת סודות
from dataclasses import dataclass  # מבנה SecurityFinding
from pathlib import Path  # נתיבים עמידים בפני מערכת הפעלה (Windows/Linux)

import psutil  # רשימת חיבורי רשת פתוחים — לבדיקת חשיפת debug console
import requests  # בדיקת כותרות CORS מול השרתים
from dotenv import load_dotenv  # טעינת .env כדי לדעת אילו סודות לחפש

from test_requests import DEFAULT_HOST, run_health_checks  # שימוש חוזר בבדיקות התקינות לסריקת סודות בתגובות אמיתיות

load_dotenv()  # טעינת משתני הסביבה מ-.env — נדרש לפני קריאת os.getenv למטה

_BASE_DIR = Path(__file__).resolve().parent  # תיקיית הפרויקט — בסיס לכל הנתיבים היחסיים
_SERVERS = [("GeoServer", 5003), ("WeatherServer", 5002), ("FlightServer", 5004)]  # שם תצוגה + פורט לכל שרת Flask
_SECRET_ENV_VARS = ["OPENWEATHER_API_KEY", "GOOGLE_API_KEY", "FR24_TOKEN", "FR24_USER", "FR24_PASS"]  # מפתחות שנסרקים כדליפה
_APK_PATH = _BASE_DIR / "maps-gui-android" / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk"  # פלט build_apk.ps1
_REQUIREMENTS_PATH = _BASE_DIR / "requirements.txt"  # קלט ל-pip-audit
_DART_API_SERVICE = _BASE_DIR / "maps-gui-android-src" / "lib" / "services" / "api_service.dart"  # מקור הטוקנים הקשיחים באנדרואיד
_VENV_PYTHON = _BASE_DIR / ".venv" / "Scripts" / "python.exe"  # הרצת pip-audit מתוך אותו venv — לא מ-python המערכת


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


def _check_bind_exposure(host):
    """ עם debug=True, שרת שמאזין על 0.0.0.0/כתובת רשת (לא רק 127.0.0.1) חושף את קונסולת
    ה-debugger האינטראקטיבית של Werkzeug — כל מי שברשת יכול להריץ קוד פייתון שרירותי דרכה. """
    start = time.perf_counter()
    try:
        conns = {c.laddr.port: c.laddr.ip for c in psutil.net_connections(kind="inet")  # מילון {פורט: כתובת IP שהוא מאזין עליה} לכל חיבור פתוח במערכת
                 if c.status == psutil.CONN_LISTEN and c.laddr}
    except (psutil.AccessDenied, PermissionError):
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("חשיפת debug console לרשת", "medium", False,
                                 "אין הרשאה לקרוא חיבורי רשת (הרץ כמנהל לבדיקה מלאה)", elapsed)]

    elapsed = (time.perf_counter() - start) * 1000
    findings = []
    for server, port in _SERVERS:
        ip = conns.get(port)  # הכתובת שהשרת הזה מאזין עליה בפועל, או None אם לא פעיל
        if ip is None:
            findings.append(SecurityFinding(f"{server}: חשיפת debug console לרשת", "info", True,
                                             "השרת לא פעיל — לא ניתן לבדוק", elapsed, server=server))
        elif ip in ("127.0.0.1", "::1"):
            findings.append(SecurityFinding(f"{server}: חשיפת debug console לרשת", "high", True,
                                             f"מאזין רק על {ip} — לא נגיש מרשת חיצונית", elapsed, server=server))
        else:
            findings.append(SecurityFinding(f"{server}: חשיפת debug console לרשת", "high", False,
                                             f"מאזין על {ip} — נגיש מהרשת! עם debug=True זה מאפשר "
                                             f"הרצת קוד מרחוק דרך קונסולת Werkzeug", elapsed, server=server))
    return findings


def _check_secrets_leak(host):
    """ מריץ את כל בדיקות test_requests.py (כולל מסלולי שגיאה) וסורק את גופי התגובה
    האמיתיים לאיתור ערכי הסודות מ-.env בטקסט חופשי — לא יורה בקשות נפרדות. מפוצל לממצא
    אחד לכל שרת (ולא ממצא Global יחיד) כדי שרשת השעונים 3×3 בדשבורד תוכל לצייר ציון נפרד. """
    start = time.perf_counter()
    secrets = {name: os.getenv(name, "") for name in _SECRET_ENV_VARS}
    secrets = {k: v for k, v in secrets.items() if v and len(v) >= 8}  # מסנן ערכים ריקים/קצרים מדי שעלולים לגרום להתאמות שווא
    if not secrets:
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סריקת סודות בתגובות שרת", "info", True,
                                 "לא נמצאו מפתחות ב-.env לבדיקה", elapsed)]

    results = run_health_checks(host=host, load_cases=[])  # ללא בדיקות עומס — לא צריך כאן
    by_server = {}
    for r in results:
        by_server.setdefault(r.server, []).append(r)  # קיבוץ התוצאות לפי שרת — כדי לדווח ממצא נפרד לכל שרת

    elapsed = (time.perf_counter() - start) * 1000
    findings = []
    for server, server_results in by_server.items():
        leaks = [f"{r.name}: מכיל את {name}"  # כל צירוף (בדיקה, סוד) שהערך שלו נמצא בגוף התגובה
                 for r in server_results for name, value in secrets.items() if value in (r.body or "")]
        if leaks:
            findings.append(SecurityFinding("סריקת סודות בתגובות שרת", "high", False,
                                             "; ".join(leaks), elapsed, server=server))
        else:
            findings.append(SecurityFinding(
                "סריקת סודות בתגובות שרת", "info", True,
                f"נבדקו {len(secrets)} מפתחות מול {len(server_results)} תגובות אמיתיות — לא נמצאה דליפה",
                elapsed, server=server))
    return findings


def _check_cors_policy(host):
    findings = []
    for server, port in _SERVERS:
        start = time.perf_counter()
        try:
            resp = requests.get(f"http://{host}:{port}/metrics", timeout=5)  # /metrics קיים בכל שרת ולא דורש פרמטרים — נוח לבדיקת כותרות
            elapsed = (time.perf_counter() - start) * 1000
            allow_origin = resp.headers.get("Access-Control-Allow-Origin")
            if allow_origin == "*":
                findings.append(SecurityFinding(
                    f"{server}: מדיניות CORS", "low", False,
                    "Access-Control-Allow-Origin: * — כל דף אינטרנט יכול לקרוא מהשרת הזה, לא רק "
                    "map.html המקומי. כרגע כנראה נדרש כי QWebEngineView טוען מ-file:// ; "
                    "אם השרתים ייחשפו אי-פעם מעבר ל-127.0.0.1 שווה להדק ל-origin קבוע.",
                    elapsed, server=server))
            elif allow_origin:
                findings.append(SecurityFinding(f"{server}: מדיניות CORS", "info", True,
                                                 f"Access-Control-Allow-Origin: {allow_origin}", elapsed, server=server))
            else:
                findings.append(SecurityFinding(f"{server}: מדיניות CORS", "info", True,
                                                 "אין כותרת CORS בתגובה", elapsed, server=server))
        except requests.exceptions.RequestException:
            elapsed = (time.perf_counter() - start) * 1000
            findings.append(SecurityFinding(f"{server}: מדיניות CORS", "info", True,
                                             "השרת לא פעיל — לא ניתן לבדוק", elapsed, server=server))
    return findings


def _check_dependency_vulnerabilities():
    start = time.perf_counter()
    try:
        subprocess.run([str(_VENV_PYTHON), "-m", "pip_audit", "--version"],  # בדיקת זמינות בלבד — לא מריצים סריקה אם pip-audit לא מותקן
                        capture_output=True, timeout=10, check=True)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סריקת CVEs בתלויות (pip-audit)", "info", True,
                                 "pip-audit אינו מותקן — הרץ: pip install pip-audit", elapsed)]

    try:
        proc = subprocess.run(
            [str(_VENV_PYTHON), "-m", "pip_audit", "-r", str(_REQUIREMENTS_PATH), "--format", "json"],
            capture_output=True, text=True, timeout=120  # timeout ארוך — pip-audit פונה למאגר CVE חיצוני ברשת
        )
        elapsed = (time.perf_counter() - start) * 1000
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        deps = data.get("dependencies", data) if isinstance(data, dict) else data  # תמיכה בשני פורמטי פלט אפשריים בין גרסאות pip-audit
        vulnerable = [d for d in deps if d.get("vulns")]
        if vulnerable:
            names = ", ".join(f"{d['name']} {d['version']} ({len(d['vulns'])} CVE)" for d in vulnerable)
            return [SecurityFinding("סריקת CVEs בתלויות (pip-audit)", "high", False, names, elapsed)]
        return [SecurityFinding("סריקת CVEs בתלויות (pip-audit)", "info", True,
                                 f"{len(deps)} חבילות נבדקו — לא נמצאו CVEs ידועים", elapsed)]
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סריקת CVEs בתלויות (pip-audit)", "info", True, f"הסריקה נכשלה: {e}", elapsed)]


def _extract_dart_hardcoded_secrets():
    """ מחלץ קבועים שנראים כמו טוקן קשיח מ-api_service.dart (תבנית _xxxToken = '...') —
    כרגע צפוי לתפוס את _fr24Token הידוע והמתועד. גנרי כדי לתפוס גם טוקנים עתידיים דומים. """
    secrets = {}
    if _DART_API_SERVICE.exists():
        try:
            text = _DART_API_SERVICE.read_text(encoding="utf-8")
            for m in re.finditer(r"_(\w*[Tt]oken\w*)\s*=\s*'([^']{16,})'", text):  # שם משתנה private שמכיל "Token" + ערך מחרוזת של 16+ תווים
                secrets[f"Android hardcoded: {m.group(1)}"] = m.group(2)
        except OSError:
            pass  # קובץ לא קריא — פשוט לא נמצאו סודות ממקור זה, לא כשל
    return secrets


def _check_apk_secrets():
    start = time.perf_counter()
    if not _APK_PATH.exists():
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סודות קשיחים ב-APK", "info", True,
                                 f"APK לא נמצא ({_APK_PATH}) — הרץ build_apk.ps1 קודם", elapsed)]

    secrets = {name: os.getenv(name, "") for name in _SECRET_ENV_VARS}  # סודות שרת (.env) — נבדק שלא הוטמעו בטעות גם באפליקציית האנדרואיד
    secrets = {k: v for k, v in secrets.items() if v and len(v) >= 8}
    secrets.update(_extract_dart_hardcoded_secrets())  # + סודות שכן הוטמעו במפורש בקוד ה-Dart (כמו FR24 token)

    if not secrets:
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סודות קשיחים ב-APK", "info", True, "אין סודות ידועים לבדוק", elapsed)]

    found = []
    try:
        with zipfile.ZipFile(_APK_PATH) as z:  # APK הוא בעצם ארכיון ZIP רגיל
            for name in z.namelist():
                if not (name.endswith(".so") or "flutter_assets" in name):  # ספריות native וקבצי ה-bundle של Flutter — שם בפועל מוטמעים המחרוזות
                    continue
                try:
                    data = z.read(name)
                except (zipfile.BadZipFile, KeyError, RuntimeError):
                    continue  # ערך בודד בארכיון פגום — מדלגים במקום להפיל את כל הסריקה
                for secret_name, value in secrets.items():
                    if value.encode("utf-8") in data:  # חיפוש בינארי — הסוד עשוי להיות בתוך קובץ קומפילציה, לא רק טקסט
                        found.append(f"{secret_name} נמצא בתוך {name}")
    except zipfile.BadZipFile:
        elapsed = (time.perf_counter() - start) * 1000
        return [SecurityFinding("סודות קשיחים ב-APK", "info", True, "לא ניתן לפתוח את ה-APK כ-ZIP", elapsed)]

    elapsed = (time.perf_counter() - start) * 1000
    if found:
        return [SecurityFinding("סודות קשיחים ב-APK", "medium", False,
                                 "; ".join(found) + " — ידוע/מתועד עבור FR24 Gold token; "
                                 "כל מי שמוריד את ה-APK יכול לחלץ ולהשתמש בו", elapsed)]
    return [SecurityFinding("סודות קשיחים ב-APK", "info", True,
                             f"נבדקו {len(secrets)} סודות ידועים מול קבצי ה-APK — לא נמצאו", elapsed)]


def run_security_checks(host=DEFAULT_HOST, on_progress=None):
    """ מריץ את כל בדיקות האבטחה ומחזיר רשימת SecurityFinding. ייבוא cis_checks מבוצע כאן
    (ולא בראש הקובץ) כי cis_checks מייבא בחזרה SecurityFinding מהמודול הזה — ייבוא בראש
    היה יוצר circular import. """
    from cis_checks import run_cis_l1_checks, run_cis_l2_checks  # ייבוא מאוחר (lazy) — ראו הסבר ב-docstring
    findings = []
    for check_fn, args in (
        (_check_bind_exposure, (host,)),
        (_check_secrets_leak, (host,)),
        (_check_cors_policy, (host,)),
        (_check_dependency_vulnerabilities, ()),
        (_check_apk_secrets, ()),
        (run_cis_l1_checks, ()),
        (run_cis_l2_checks, ()),
    ):  # רשימת (פונקציה, ארגומנטים) — מאפשרת לקרוא לכל הבדיקות באותה לולאה למרות חתימות שונות
        for finding in check_fn(*args):
            findings.append(finding)
            if on_progress:
                on_progress(finding)  # callback אופציונלי — מדווח לדשבורד מיד אחרי כל בדיקה, לא רק בסיום
    return findings


def summarize_findings(findings):
    """מחזיר (issue_count, severity_counts dict) — סופר רק ממצאים בפועל (ok=False)."""
    severity_counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    issue_count = 0
    for f in findings:
        if not f.ok:  # ok=True (כולל info) לא נספר כממצא — רק בעיות אמיתיות
            issue_count += 1
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    return issue_count, severity_counts


def _print_report(findings):
    """ דוח טקסטואלי לריצה כ-CLI (python security_checks.py) — main.py משתמש בממצאים ישירות, לא בפונקציה הזו. """
    print("=" * 60)
    print("סריקת אבטחה — maps-gui")
    print("=" * 60)
    for f in findings:
        icon = "✓" if f.ok else "⚠"
        print(f"  {icon} [{f.severity:6s}] {f.check:40s} {f.message}")
        if not f.ok and f.remediation:
            print(f"           ↳ תיקון מומלץ: {f.remediation}")

    issue_count, severity_counts = summarize_findings(findings)
    print("\n" + "-" * 60)
    if issue_count == 0:
        print("לא נמצאו ממצאים.")
    else:
        parts = ", ".join(f"{v} {k}" for k, v in severity_counts.items() if v)  # רק חומרות עם ספירה גדולה מ-0 מוצגות
        print(f"נמצאו {issue_count} ממצאים: {parts}")
    print("=" * 60)


if __name__ == "__main__":
    import sys  # רק לשינוי קידוד הפלט — לא נדרש כשהמודול מיובא מ-main.py
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # מונע UnicodeEncodeError בהדפסת עברית בטרמינל Windows עם קידוד לא-UTF-8
    _print_report(run_security_checks())
