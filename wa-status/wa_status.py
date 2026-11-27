# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
"""
wa-status — כלי גנרי וחד-כיווני לשליחת עדכוני סטטוס לוואטסאפ ("הודעה לעצמי").
מועתק כתיקייה אחת לכל ריפו; אין בו שום תלות בשם/שפה/מבנה של ריפו מסוים.
החיבור לוואטסאפ דרך הספרייה הלא-רשמית neonize (Apache-2.0, ליבת whatsmeow ב-MPL-2.0).
"""

import argparse  # פרסור פקודות ה-CLI (setup/send/summary/daily/check-interval/test)
import datetime  # חותמות זמן ללוג, לדגל-הכשל ולמצב "נשלח לאחרונה"
import json  # קריאה/כתיבה של config.json ושל קבצי ה-state
import logging  # לוג מקומי לקובץ — שגיאות שליחה נרשמות כאן ולא שוברות את העבודה
import os  # os.startfile לפתיחת תמונת ה-QR במציג ברירת-המחדל של Windows
import re  # סינון סודות/נתיבים ופרסור --since
import shutil  # העתקת config.example.json ל-config.json בהגדרה ראשונה
import subprocess  # הרצת git לשם הפרויקט ולסיכומים
import sys  # קוד יציאה והגדרת קידוד הפלט
import threading  # טיימר-הגנה שעוצר את החיבור אחרי שליחה/פסק-זמן
import time  # מדידת זמן להמתנות קצרות
from pathlib import Path  # נתיבים יחסיים לתיקיית הכלי — עובד זהה בכל ריפו

# ── נתיבים — הכל יחסי לתיקיית הכלי עצמה, כדי שהעתקה לריפו אחר תעבוד בלי שינוי קוד ──
TOOL_DIR = Path(__file__).resolve().parent  # תיקיית wa-status/ בריפו הנוכחי
REPO_DIR = TOOL_DIR.parent  # שורש הריפו (התיקייה שמכילה את wa-status/)
CONFIG_PATH = TOOL_DIR / "config.json"  # הגדרות אמיתיות — מוחרג מ-git
EXAMPLE_PATH = TOOL_DIR / "config.example.json"  # תבנית ההגדרות — נכנסת ל-git
SESSION_DIR = TOOL_DIR / "session"  # נתוני החיבור לוואטסאפ — מוחרג מ-git, אסור לשתף
STATE_DIR = TOOL_DIR / "state"  # לוג, זמן שליחה אחרון ודגל-כשל — מוחרג מ-git
DB_PATH = SESSION_DIR / "wa.db"  # קובץ ה-session של neonize (SQLite)
LOG_PATH = STATE_DIR / "wa_status.log"  # לוג מקומי של כל ניסיון שליחה
LAST_SENT_PATH = STATE_DIR / "last_sent.json"  # מתי נשלח העדכון האחרון — עבור check-interval
FLAG_PATH = STATE_DIR / "failed.flag"  # דגל "ה-session פג / נדרש QR מחדש" — Claude מדווח עליו פעם אחת
QR_PNG_PATH = STATE_DIR / "qr.png"  # תמונת ה-QR של setup — נפתחת על המסך לסריקה
PAIR_CODE_PATH = STATE_DIR / "pair_code.txt"  # קוד-הצימוד (8 תווים) כשמשתמשים ב-setup --code

# ── קבועים ──
MAX_LEN = 500  # הודעות ארוכות מזה נחתכות אוטומטית
SEND_TIMEOUT_SEC = 60  # זמן מרבי לחיבור+שליחה בפקודות send/summary/daily/test
FILE_TIMEOUT_SEC = 900  # זמן מרבי לחיבור+העלאה בפקודת send-file — קובץ של ~100MB לוקח כמה דקות
FILE_MAX_MB = 2000  # מגבלת גודל מסמך בוואטסאפ (~2GB)
SETUP_TIMEOUT_SEC = 300  # זמן מרבי לסריקת QR / הזנת קוד-צימוד ב-setup
EMOJI = {  # אימוג'י הסטטוס לפי סוג ההודעה — לפי ההחלטה שסוכמה
    "start": "⏳",  # התחלת משימה
    "progress": "⏳",  # עדכון מחזורי בזמן עבודה ארוכה
    "done": "✅",  # הצלחה / סיום
    "error": "❌",  # שגיאה שלא נפתרה
    "blocked": "🛑",  # חסימה שדורשת החלטה של המשתמש
    "summary": "📊",  # סיכום לפי חלון זמן או סיכום יומי
    "test": "✅",  # הודעת בדיקה
}
DEFAULTS = {  # ערכי ברירת-מחדל לכל מפתח בהגדרות — משמשים כשמפתח חסר ב-config.json
    "phone": "",  # מספר הטלפון בפורמט בינלאומי בלי "+" (למשל 9725XXXXXXXX); ריק = יתמלא אוטומטית ב-setup
    "progress_interval_minutes": 30,  # מרווח העדכון המחזורי בדקות
    "daily_summary_time": "21:00",  # שעת הסיכום היומי (משמשת לרישום המשימה ב-Task Scheduler)
    "project_name": "",  # דריסת שם הפרויקט; ריק = שם תיקיית הריפו
    "enabled": True,  # False = השבתה מהירה, שום דבר לא נשלח
    "dry_run": False,  # True = מדפיס את ההודעה במקום לשלוח
}
SEND_TYPES = ("start", "done", "error", "blocked", "progress")  # הסוגים שמותר לשלוח בפקודת send


# ═══════════════════════════ עזרי תשתית ═══════════════════════════

def _setup_output():
    """מגדיר פלט UTF-8 — קונסולת Windows ברירת-מחדל לא תמיד מציגה עברית/אימוג'י, וזה לא אמור לקרוס."""
    for stream in (sys.stdout, sys.stderr):  # גם הפלט הרגיל וגם פלט השגיאות
        try:  # reconfigure קיים בכל TextIOWrapper סטנדרטי, אבל לא בכל סביבה (למשל pipe מיוחד)
            stream.reconfigure(encoding="utf-8", errors="replace")  # תווים שלא ניתנים להצגה מוחלפים ולא מפילים
        except (AttributeError, ValueError):  # סביבה בלי reconfigure — משאירים כמו שהוא
            pass  # לא קריטי — הלוג לקובץ נשאר תקין בכל מקרה


def _setup_logging():
    """מפנה את כל הלוגים (כולל של neonize/whatsmeow) לקובץ מקומי בלבד — לא מלכלך את הטרמינל של Claude."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)  # יוצר את תיקיית state/ אם לא קיימת
    logging.basicConfig(  # force=True מחליף גם את ה-handler ש-neonize מתקין בעצמו בזמן import
        filename=str(LOG_PATH),  # כל הלוגים לקובץ
        encoding="utf-8",  # עברית תקינה בלוג
        level=logging.INFO,  # רמת פירוט — INFO מספיק לאבחון חיבור
        format="%(asctime)s [%(name)s %(levelname)s] %(message)s",  # חותמת זמן + מקור + רמה
        force=True,  # מסיר handlers קודמים (כולל ה-StreamHandler של neonize)
    )


def _now_iso():
    """חותמת זמן מקומית קריאה — לדגל-הכשל ולקובץ last_sent."""
    return datetime.datetime.now().isoformat(timespec="seconds")  # למשל 2026-11-26T18:05:00


def load_config():
    """קורא את config.json וממזג עם ברירות-המחדל; אם הקובץ חסר/פגום — ברירות-המחדל בלבד."""
    cfg = dict(DEFAULTS)  # מתחילים מברירות-המחדל, כך שמפתח חסר לא יפיל את הכלי
    if CONFIG_PATH.exists():  # הקובץ קיים רק אחרי setup או יצירה ידנית
        try:  # קובץ פגום לא אמור לשבור את עבודת Claude
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))  # ערכי המשתמש גוברים
        except (OSError, ValueError) as exc:  # שגיאת קריאה או JSON לא תקין
            logging.error("config.json לא נקרא: %s", exc)  # נרשם בלוג, ממשיכים עם ברירות-המחדל
    return cfg  # מילון הגדרות מלא


def save_config(cfg):
    """שומר את ההגדרות ל-config.json (משמש את setup למילוי מספר הטלפון אוטומטית)."""
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")  # JSON קריא, עברית כמו שהיא


def ensure_config():
    """יוצר config.json מהתבנית אם עוד לא קיים — לא דורס קובץ קיים."""
    if not CONFIG_PATH.exists() and EXAMPLE_PATH.exists():  # רק בהגדרה ראשונה
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)  # העתקה של התבנית כנקודת התחלה


def normalize_phone(raw):
    """משאיר ספרות בלבד (מסיר +, רווחים, מקפים) — whatsmeow מצפה למספר בינלאומי בלי סימנים."""
    return re.sub(r"\D", "", str(raw or ""))  # כל תו שאינו ספרה נמחק


def _git(*args):
    """מריץ git בשורש הריפו ומחזיר את הפלט, או None אם git לא זמין / זה לא ריפו."""
    try:  # git עלול לא להיות מותקן, או שהתיקייה לא ריפו
        out = subprocess.run(  # הרצה סינכרונית עם פסק-זמן, בלי shell
            ["git", "-C", str(REPO_DIR), *args],  # -C = להריץ כאילו אנחנו בשורש הריפו
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,  # פלט כטקסט UTF-8
        )
    except (OSError, subprocess.SubprocessError) as exc:  # git חסר או נתקע
        logging.warning("git נכשל: %s", exc)  # נרשם, לא קריטי
        return None  # הקורא ישתמש בחלופה
    if out.returncode != 0:  # למשל "not a git repository"
        return None  # הקורא ישתמש בחלופה
    return out.stdout  # הפלט הגולמי של git


def project_name(cfg):
    """שם הפרויקט: דריסה מ-config, אחרת שם תיקיית שורש הריפו (git), אחרת שם התיקייה שמעל wa-status/."""
    if str(cfg.get("project_name") or "").strip():  # המשתמש הגדיר שם במפורש
        return str(cfg["project_name"]).strip()  # הדריסה גוברת
    top = _git("rev-parse", "--show-toplevel")  # שורש הריפו לפי git (נכון גם אם wa-status בתת-תיקייה)
    if top and top.strip():  # git החזיר נתיב
        return Path(top.strip()).name  # רק שם התיקייה האחרונה, לא נתיב מלא
    return REPO_DIR.name  # חלופה: שם התיקייה שמכילה את wa-status/


# ── סינון פרטיות — לא שולחים סודות, מפתחות, תוכן .env או נתיבים מלאים ──
_SECRET_WORD_RE = re.compile(  # מילת-סוד ואחריה ערך (עם או בלי : / =)
    r"(?i)\b(token|password|passwd|secret|api[_-]?key|apikey|access[_-]?key|private[_-]?key|bearer)\b(\s*[:=]\s*|\s+)\S+"
)
_SECRET_ASSIGN_RE = re.compile(r"(?i)\b(key|pwd|pass|auth|credential)s?\s*[:=]\s*\S+")  # מילים כלליות — רק עם : או =
_ENV_LINE_RE = re.compile(r"\b([A-Z][A-Z0-9_]{2,})=\S+")  # שורת .env בסגנון NAME=value
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-+/]{32,}={0,2}")  # מחרוזת ארוכה שנראית כמו טוקן/מפתח
_WIN_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]+")  # נתיב Windows מלא (C:\...)
_UNIX_PATH_RE = re.compile(r"(?<![\w.])/(?:[\w.\-]+/){2,}[\w.\-]+")  # נתיב Unix מלא עם 3+ רכיבים
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*")  # T3 (F-037): JWT (שלושה חלקי base64 מופרדים בנקודה)
_AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")  # T3: מזהה מפתח AWS
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")  # T3: כתובת דוא"ל
_PHONE_RE = re.compile(r"(?<![\d.])(?:\+\d[\d\- ]{8,14}\d|(?:972|0)\d{8,9}|0\d{1,2}-\d{3}-?\d{4})(?![\d.])")  # T3: טלפון: בינלאומי עם +, ישראלי רצוף (972/0), או 0X-XXX-XXXX — לא תאריכים ושעות
_COORD_RE = re.compile(r"(?<![\d.])-?\d{1,3}\.\d{3,}\s*[,/ ]\s*-?\d{1,3}\.\d{3,}(?![\d.])")  # T3: זוג קואורדינטות מדויק (3+ ספרות אחרי הנקודה) — מיקומי מכ"מים/עמדות
_SANITIZE_MAX_IN = 4000  # T3: תקרת אורך לקלט הסינון — מונע עבודה מיותרת על טקסט ענק (ההודעה עצמה נחתכת ב-MAX_LEN)


def _basename_of(match):
    """מחליף נתיב מלא בשם הקובץ/התיקייה האחרון בלבד."""
    return re.split(r"[\\/]", match.group(0).rstrip("\\/"))[-1]  # הרכיב האחרון של הנתיב


def sanitize(text):
    """סינון בסיסי: מסתיר ערכי סודות, שורות .env, טוקנים ארוכים, ומקצר נתיבים מלאים לשם בלבד."""
    text = str(text)[:_SANITIZE_MAX_IN]  # T3 (F-037): תקרת אורך לפני הסינון
    text = _SECRET_WORD_RE.sub(lambda m: f"{m.group(1)}=***", text)  # token xyz -> token=***
    text = _SECRET_ASSIGN_RE.sub(lambda m: f"{m.group(1)}=***", text)  # key=xyz -> key=***
    text = _ENV_LINE_RE.sub(lambda m: f"{m.group(1)}=***", text)  # API_TOKEN=xyz -> API_TOKEN=***
    text = _WIN_PATH_RE.sub(_basename_of, text)  # C:\a\b\file.py -> file.py
    text = _UNIX_PATH_RE.sub(_basename_of, text)  # /home/u/x/file.py -> file.py
    text = _JWT_RE.sub("***", text)  # T3: JWT -> *** (לפני הטוקן הארוך, שלא יתפוס רק חלק)
    text = _AWS_KEY_RE.sub("***", text)  # T3: מפתח AWS -> ***
    text = _EMAIL_RE.sub("***@***", text)  # T3: דוא"ל -> ***@***
    text = _COORD_RE.sub("[מיקום]", text)  # T3: קואורדינטות -> [מיקום] (לפני הטלפון, ששניהם מספרים)
    text = _PHONE_RE.sub("***", text)  # T3: מספר טלפון -> ***
    text = _LONG_TOKEN_RE.sub("***", text)  # מחרוזת-טוקן ארוכה -> ***
    return text  # הטקסט אחרי הסינון


def build_message(kind, body, cfg):
    """בונה את ההודעה: שורה ראשונה אימוג'י + שם הפרויקט מודגש, אחריה התוכן; מסנן וחותך ל-500 תווים."""
    header = f"{EMOJI.get(kind, 'ℹ️')} *{project_name(cfg)}*"  # למשל: ✅ *maps-gui*
    text = f"{header}\n{sanitize(body.strip())}" if body.strip() else header  # כותרת + תוכן מסונן
    if len(text) > MAX_LEN:  # חיתוך אוטומטי של הודעות ארוכות
        text = text[: MAX_LEN - 1] + "…"  # 499 תווים + סימן השמטה = בדיוק 500
    return text  # ההודעה הסופית לשליחה


def _write_flag(reason):
    """כותב את דגל-הכשל פעם אחת בלבד (בכשל הראשון) — Claude מדווח עליו פעם אחת ומוחק לא."""
    if FLAG_PATH.exists():  # הדגל כבר קיים — לא דורסים, הכשל הראשון הוא שנרשם
        return  # אין מה לעשות
    STATE_DIR.mkdir(parents=True, exist_ok=True)  # לוודא שהתיקייה קיימת
    FLAG_PATH.write_text(f"{_now_iso()} {reason}\nיש להריץ: python wa-status/wa_status.py setup\n", encoding="utf-8")  # זמן + סיבה + מה לעשות


def _mark_sent():
    """שומר את זמן השליחה האחרונה — check-interval משווה אליו."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)  # לוודא שהתיקייה קיימת
    LAST_SENT_PATH.write_text(json.dumps({"ts": time.time(), "iso": _now_iso()}), encoding="utf-8")  # epoch לחישוב + ISO לקריאה


_native_stderr_redirected = False  # האם fd 2 כבר הופנה לקובץ הלוג בתהליך הזה


def _redirect_native_stderr():
    """
    מפנה את stderr ברמת מערכת ההפעלה (fd 2) לקובץ הלוג, לפני טעינת ספריית ה-Go — ספריית ההצפנה
    של whatsmeow כותבת אזהרות ישירות לשם (עוקפת את logging של Python) ומלכלכת את הטרמינל של Claude.
    בכוונה לא משחזרים: Go שומר את ה-handle בזמן הטעינה, ושחזור היה משאיר אותו מצביע על handle סגור.
    לכן הודעות השגיאה של הכלי עצמו אחרי השליחה נכתבות ל-stdout.
    """
    global _native_stderr_redirected  # דגל ברמת המודול
    if _native_stderr_redirected:  # כבר הופנה — לא חוזרים על זה
        return  # אין מה לעשות
    STATE_DIR.mkdir(parents=True, exist_ok=True)  # לוודא שתיקיית הלוג קיימת
    sys.stderr.flush()  # כותבים כל מה שממתין לפני ההחלפה
    log_fd = os.open(str(LOG_PATH), os.O_WRONLY | os.O_APPEND | os.O_CREAT)  # פתיחת הלוג להוספה ברמת מערכת ההפעלה
    os.dup2(log_fd, 2)  # fd 2 מצביע מעכשיו לקובץ הלוג (ב-Windows זה מעדכן גם את ה-STD_ERROR_HANDLE)
    os.close(log_fd)  # ה-fd הזמני כבר לא נחוץ — fd 2 מחזיק עותק משלו
    _native_stderr_redirected = True  # מסמנים שבוצע


def _import_neonize():
    """ייבוא עצל של neonize (רק כשבאמת שולחים), ואחריו החזרת הלוגים לקובץ — neonize מתקין handler לטרמינל ב-import."""
    _redirect_native_stderr()  # חייב לקרות לפני טעינת ה-DLL של Go, אחרת הוא ימשיך לכתוב לטרמינל
    from neonize.client import NewClient  # מחלקת הלקוח
    from neonize.events import ConnectedEv, LoggedOutEv, PairStatusEv, TemporaryBanEv, ConnectFailureEv  # אירועי החיבור הרלוונטיים
    from neonize.utils import build_jid  # בניית JID ממספר טלפון
    _setup_logging()  # מבטל את ה-StreamHandler של neonize — הכל חוזר לקובץ בלבד
    return NewClient, ConnectedEv, LoggedOutEv, PairStatusEv, TemporaryBanEv, ConnectFailureEv, build_jid  # כל מה שצריך לחיבור


# ═══════════════════════════ חיבור ושליחה ═══════════════════════════

def deliver(text, cfg, setup_mode=False, use_code=False, timeout=SEND_TIMEOUT_SEC, file_path=None):  # file_path: שליחת קובץ (מסמך) עם text ככיתוב
    """
    מתחבר לוואטסאפ, שולח את text ל"הודעה לעצמי" ומתנתק. מחזיר (ok, reason).
    setup_mode=True: אם אין session תקף — מציג QR (או קוד-צימוד עם use_code) ומחכה לסריקה.
    setup_mode=False: אם אין session תקף — לא מציג QR; כותב דגל-כשל ומחזיר כשל.
    """
    if not cfg.get("enabled", True):  # השבתה מהירה דרך config
        return True, "disabled"  # לא נחשב כשל — פשוט כבוי
    if cfg.get("dry_run"):  # מצב בדיקה — מדפיסים במקום לשלוח
        print("[dry_run] ההודעה שהייתה נשלחת:")  # כותרת לפלט
        print(text)  # ההודעה עצמה
        return True, "dry_run"  # הצלחה מדומה
    if not setup_mode and not DB_PATH.exists():  # אין session בכלל — setup לא הורץ בריפו הזה
        _write_flag("אין session — setup עוד לא הורץ בריפו הזה")  # Claude ידווח פעם אחת
        return False, "no_session"  # כשל, בלי לנסות להתחבר
    try:  # neonize עלול לא להיות מותקן בסביבת ה-Python הזו
        NewClient, ConnectedEv, LoggedOutEv, PairStatusEv, TemporaryBanEv, ConnectFailureEv, build_jid = _import_neonize()  # ייבוא עצל
    except ImportError as exc:  # הספרייה חסרה
        logging.error("neonize לא מותקן: %s", exc)  # נרשם בלוג
        return False, "neonize_missing"  # כשל עם סיבה ברורה

    SESSION_DIR.mkdir(parents=True, exist_ok=True)  # תיקיית ה-session חייבת להתקיים לפני יצירת ה-DB
    result = {"ok": False, "reason": "timeout"}  # ברירת-מחדל: אם לא קרה כלום עד פסק-הזמן
    done = threading.Event()  # מסומן כשיש תוצאה (נשלח / כשל) — משחרר את טיימר-ההגנה
    state = {"qr_opened": False, "code_requested": False}  # מונע פתיחה חוזרת של חלון ה-QR / בקשת קוד כפולה
    phone = normalize_phone(cfg.get("phone"))  # המספר מההגדרות, ספרות בלבד
    client = NewClient(str(DB_PATH))  # הלקוח; שם = נתיב קובץ ה-session

    def finish(ok, reason):
        """רושם את התוצאה (רק הראשונה נחשבת) ומשחרר את ההמתנה."""
        if not done.is_set():  # רק התוצאה הראשונה קובעת
            result.update(ok=ok, reason=reason)  # שמירת התוצאה
            done.set()  # טיימר-ההגנה יעצור את החיבור

    def on_qr(_client, data_qr):
        """אירוע QR = אין session תקף. ב-setup מציגים אותו; בשליחה רגילה זה כשל שדורש setup מחדש."""
        if not setup_mode:  # בשליחה רגילה לא מציגים QR
            _write_flag("ה-session פג — נדרש QR מחדש")  # דגל לדיווח חד-פעמי של Claude
            finish(False, "session_expired")  # כשל
            return  # לא ממשיכים
        import segno  # תלות של neonize — יצירת תמונת QR
        STATE_DIR.mkdir(parents=True, exist_ok=True)  # לוודא שהתיקייה קיימת
        segno.make_qr(data_qr).save(str(QR_PNG_PATH), scale=10, border=4)  # שומר PNG גדול וקריא לסריקה (מתעדכן כשה-QR מתחלף)
        try:  # הדפסת QR בטרמינל — שימושי כשמריצים setup ידנית
            segno.make_qr(data_qr).terminal(compact=True)  # QR בתווי טקסט
        except (OSError, UnicodeError):  # טרמינל שלא תומך בתווים — לא קריטי, יש PNG
            pass  # ממשיכים עם ה-PNG בלבד
        print(f"QR עודכן: {QR_PNG_PATH}", flush=True)  # הודעה שה-QR מוכן/התחלף
        if not state["qr_opened"] and hasattr(os, "startfile"):  # פתיחה פעם אחת בלבד, רק ב-Windows
            state["qr_opened"] = True  # לא לפתוח שוב בכל החלפת QR
            try:  # פתיחה במציג התמונות ברירת-המחדל
                os.startfile(str(QR_PNG_PATH))  # החלון נפתח על המסך של המשתמש
            except OSError as exc:  # אין מציג משויך — המשתמש יפתח ידנית
                logging.warning("פתיחת QR נכשלה: %s", exc)  # נרשם בלוג
        if use_code and not state["code_requested"]:  # מצב קוד-צימוד — מבקשים קוד פעם אחת
            state["code_requested"] = True  # לא לבקש שוב
            threading.Thread(target=request_pair_code, daemon=True).start()  # בקשה ב-thread נפרד — לא קוראים ל-Go מתוך ה-callback שלו

    def request_pair_code():
        """מבקש קוד-צימוד בן 8 תווים — מזינים אותו בטלפון: מכשירים מקושרים > קישור עם מספר טלפון."""
        try:  # הבקשה עלולה להיכשל (מספר שגוי, חסימה)
            code = client.PairPhone(phone, True)  # True = להקפיץ התראה בטלפון
        except Exception as exc:  # noqa: BLE001 — כל כשל בבקשת הקוד מדווח, ה-QR עדיין זמין כחלופה
            print(f"בקשת קוד-צימוד נכשלה ({exc}) — אפשר לסרוק את ה-QR במקום.", flush=True)  # הודעה ברורה
            logging.error("PairPhone נכשל: %s", exc)  # נרשם בלוג
            return  # ה-QR נשאר זמין
        PAIR_CODE_PATH.write_text(code + "\n", encoding="utf-8")  # שמירת הקוד לקובץ — Claude יכול לקרוא ולמסור אותו
        print(f"קוד צימוד: {code}", flush=True)  # הקוד בפלט

    def on_connected(_client, _ev):
        """מחובר עם session תקף — שולחים את ההודעה ל"הודעה לעצמי"."""
        try:  # השליחה עצמה עלולה להיכשל (רשת, שרת)
            target = phone  # היעד: המספר מההגדרות
            if not target:  # מספר לא הוגדר — לוקחים את המספר של החשבון המחובר עצמו
                me = _client.get_me()  # פרטי המכשיר המחובר
                target = me.JID.User  # ספרות המספר של החשבון = "הודעה לעצמי"
                if setup_mode and target:  # ב-setup — שומרים את המספר להגדרות לשימוש הבא
                    cfg["phone"] = target  # עדכון בזיכרון
                    save_config(cfg)  # עדכון config.json
            if file_path:  # שליחת קובץ כמסמך (למשל APK) — הטקסט הוא הכיתוב
                data = Path(file_path).read_bytes()  # תוכן הקובץ כבייטים — חד-משמעי (מחרוזת עלולה להתפרש ככתובת URL)
                mime = "application/vnd.android.package-archive" if str(file_path).lower().endswith(".apk") else "application/octet-stream"  # סוג הקובץ להתקנה בטלפון
                _client.send_document(build_jid(target), data, caption=text, filename=Path(file_path).name, mimetype=mime)  # העלאה ושליחה; חוזר אחרי אישור השרת
            else:  # הודעת טקסט רגילה — כמו קודם
                _client.send_message(build_jid(target), text)  # שליחה; חוזר אחרי אישור השרת
            finish(True, "sent")  # הצלחה
        except Exception as exc:  # noqa: BLE001 — כל כשל שליחה נרשם ומוחזר כסיבה, לא מפיל את Claude
            logging.error("שליחה נכשלה: %s", exc)  # נרשם בלוג
            finish(False, f"send_error: {exc}")  # כשל עם סיבה

    def on_logged_out(_client, ev):
        """החשבון התנתק (נמחק מהמכשירים המקושרים / session פג) — נדרש setup מחדש."""
        logging.error("LoggedOut: %s", ev)  # פרטי האירוע ללוג
        _write_flag("החיבור נותק מהטלפון — נדרש QR מחדש")  # דגל לדיווח חד-פעמי
        finish(False, "logged_out")  # כשל

    def on_temp_ban(_client, ev):
        """חסימה זמנית מצד וואטסאפ — נרשם; אין טעם לנסות שוב מיד."""
        logging.error("TemporaryBan: %s", ev)  # פרטי החסימה ללוג
        finish(False, "temporary_ban")  # כשל

    def on_connect_failure(_client, ev):
        """כשל התחברות מצד השרת (למשל גרסה מיושנת / שגיאת שרת)."""
        logging.error("ConnectFailure: %s", ev)  # פרטי הכשל ללוג
        finish(False, f"connect_failure: {ev.Reason}")  # כשל עם קוד הסיבה

    def on_pair_status(_client, ev):
        """תוצאת הצימוד (QR/קוד) — לרישום בלבד; ההצלחה האמיתית נקבעת ב-on_connected."""
        logging.info("PairStatus: %s", ev)  # ללוג
        if ev.Error:  # הצימוד נכשל
            print(f"הצימוד נכשל: {ev.Error}", flush=True)  # הודעה ברורה
        else:  # הצימוד הצליח — ממתינים לחיבור ולשליחת הודעת האימות
            print("הצימוד הצליח, שולח הודעת אימות...", flush=True)  # עדכון התקדמות

    client.event.qr(on_qr)  # רישום מטפל ה-QR — חייב לפני connect
    client.event(ConnectedEv)(on_connected)  # רישום מטפל "מחובר"
    client.event(LoggedOutEv)(on_logged_out)  # רישום מטפל "נותק"
    client.event(TemporaryBanEv)(on_temp_ban)  # רישום מטפל "חסימה זמנית"
    client.event(ConnectFailureEv)(on_connect_failure)  # רישום מטפל "כשל התחברות"
    client.event(PairStatusEv)(on_pair_status)  # רישום מטפל "תוצאת צימוד"

    def guard():
        """טיימר-הגנה: מחכה לתוצאה או לפסק-זמן, ואז עוצר את החיבור — connect() חוסם עד stop()."""
        done.wait(timeout)  # עד שיש תוצאה, או עד פסק-הזמן
        time.sleep(0.5)  # חצי שנייה לסיום תקין של השליחה/הלוג לפני הניתוק
        try:  # stop עלול להיכשל אם החיבור כבר נסגר
            client.stop()  # מבטל את הקשר ה-Go — connect() חוזר
        except Exception as exc:  # noqa: BLE001 — כשל בעצירה לא משנה את התוצאה
            logging.warning("stop נכשל: %s", exc)  # נרשם בלוג

    threading.Thread(target=guard, daemon=True).start()  # מפעיל את טיימר-ההגנה ברקע
    try:  # החיבור עצמו — חוסם עד ש-guard קורא ל-stop
        client.connect()  # התחברות לשרתי וואטסאפ
    except Exception as exc:  # noqa: BLE001 — כל כשל חיבור (רשת וכו') נרשם ומוחזר כסיבה
        logging.error("connect נכשל: %s", exc)  # נרשם בלוג
        finish(False, f"connect_error: {exc}")  # כשל
    if not done.is_set():  # connect חזר בלי תוצאה (למשל פג תוקף ה-QR ב-setup)
        finish(False, "timeout")  # כשל — פסק-זמן
    logging.info("deliver: ok=%s reason=%s", result["ok"], result["reason"])  # תיעוד התוצאה
    return result["ok"], result["reason"]  # (הצלחה?, סיבה)


def send_text(kind, body, strict=False):
    """
    בונה ושולח הודעה. strict=False (send/summary/daily): כל כשל נרשם בלוג וקוד-היציאה 0 —
    לא שוברים את העבודה של Claude. strict=True (test): כשל = הודעה ברורה וקוד-יציאה 1.
    """
    cfg = load_config()  # ההגדרות הנוכחיות
    text = build_message(kind, body, cfg)  # ההודעה המעוצבת והמסוננת
    ok, reason = deliver(text, cfg)  # ניסיון השליחה
    if ok and reason in ("sent", "dry_run"):  # נשלח בפועל (או בבדיקה) — מעדכנים את זמן העדכון האחרון
        _mark_sent()  # עבור check-interval
    if ok:  # הצלחה (כולל disabled)
        print("נשלח." if reason == "sent" else f"לא נשלח ({reason}).")  # הודעה קצרה לפלט
        return 0  # קוד יציאה תקין
    logging.error("שליחה נכשלה (%s): %s", reason, text[:80])  # נרשם בלוג עם תחילת ההודעה
    if strict:  # test — דיווח ברור
        print(f"שגיאה: השליחה נכשלה ({reason}). פרטים: {LOG_PATH.name}")  # ל-stdout: stderr כבר מופנה ללוג אחרי טעינת neonize; שם הלוג בלבד, לא נתיב מלא
        return 1  # קוד יציאה של כשל
    print(f"השליחה נכשלה ({reason}) — נרשם בלוג, ממשיכים.")  # מידע קצר, בלי לשבור
    return 0  # תמיד 0 — לא שוברים את העבודה


# ═══════════════════════════ סיכומים מ-git ═══════════════════════════

def parse_since(expr):
    """ממיר 90m / 3h / 2d לביטוי ש-git מבין ('3 hours ago') + תווית בעברית."""
    m = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", expr or "")  # מספר + יחידה
    if not m:  # פורמט לא תקין
        return None, None  # הקורא ידווח שגיאה
    n, unit = int(m.group(1)), m.group(2)  # הכמות והיחידה
    git_unit = {"m": "minutes", "h": "hours", "d": "days"}[unit]  # יחידה באנגלית עבור git
    he_unit = {"m": "הדקות", "h": "השעות", "d": "הימים"}[unit]  # יחידה בעברית לתווית
    return f"{n} {git_unit} ago", f"ב-{n} {he_unit} האחרונות"  # ('3 hours ago', 'ב-3 השעות האחרונות')


def build_git_summary(since_git, label):
    """סיכום קצר: מספר commits, הכותרות הראשונות, ומספר הקבצים ששונו (כולל שינויים שלא נשמרו)."""
    log = _git("log", f"--since={since_git}", "--no-merges", "--pretty=format:%s")  # כותרות ה-commits בחלון
    if log is None:  # git לא זמין / לא ריפו
        return f"{label}: אין נתוני git."  # סיכום מינימלי
    subjects = [s.strip() for s in log.splitlines() if s.strip()]  # רשימת הכותרות
    names = _git("log", f"--since={since_git}", "--no-merges", "--name-only", "--pretty=format:") or ""  # קבצים ששונו ב-commits
    files = {f.strip() for f in names.splitlines() if f.strip()}  # קבצים ייחודיים
    status = _git("status", "--porcelain") or ""  # שינויים שעוד לא נשמרו ב-commit
    dirty = len([s for s in status.splitlines() if s.strip()])  # מספרם
    line = f"{label}: {len(subjects)} commits, {len(files)} קבצים שונו"  # שורת הסיכום הראשית
    if dirty:  # יש שינויים פתוחים
        line += f" (+{dirty} לא נשמרו)"  # תוספת לשורה
    bullets = [f"• {s}" for s in subjects[:3]]  # עד 3 כותרות — שומר על הודעה קצרה
    if len(subjects) > 3:  # יש עוד
        bullets.append(f"• ועוד {len(subjects) - 3}")  # ציון הכמות הנותרת
    return "\n".join([line] + bullets)  # הסיכום המלא


# ═══════════════════════════ פקודות ═══════════════════════════

def cmd_setup(args):
    """התחברות ראשונה: QR (או קוד-צימוד), שמירת session, ואימות בשליחת הודעת בדיקה."""
    ensure_config()  # יוצר config.json מהתבנית אם חסר
    cfg = load_config()  # ההגדרות
    if args.code and not normalize_phone(cfg.get("phone")):  # קוד-צימוד דורש מספר מראש
        print("שגיאה: למצב --code צריך למלא phone ב-config.json (פורמט בינלאומי, למשל 9725XXXXXXXX).", file=sys.stderr)  # הוראה ברורה
        return 1  # כשל
    cfg = dict(cfg, dry_run=False, enabled=True)  # setup תמיד מתחבר באמת, גם אם dry_run מוגדר
    print("ממתין לסריקה: וואטסאפ בטלפון > הגדרות > מכשירים מקושרים > קישור מכשיר.", flush=True)  # הוראות למשתמש
    text = build_message("test", "wa-status מחובר ✔ — עדכוני סטטוס יגיעו לכאן.", cfg)  # הודעת האימות
    ok, reason = deliver(text, cfg, setup_mode=True, use_code=args.code, timeout=SETUP_TIMEOUT_SEC)  # חיבור + שליחה
    for tmp in (QR_PNG_PATH, PAIR_CODE_PATH):  # ניקוי קבצים זמניים של הצימוד
        try:  # הקובץ אולי לא נוצר בכלל
            tmp.unlink(missing_ok=True)  # מחיקה
        except OSError:  # הקובץ פתוח במציג תמונות — לא קריטי
            pass  # יימחק/יידרס בפעם הבאה
    if ok:  # הצלחה
        FLAG_PATH.unlink(missing_ok=True)  # דגל-הכשל נמחק אחרי setup מוצלח
        _mark_sent()  # הודעת האימות נחשבת עדכון אחרון
        print("✅ מחובר. נשלחה הודעת אימות ל\"הודעה לעצמי\".")  # סיכום
        return 0  # הצלחה
    print(f"שגיאה: ההתחברות נכשלה ({reason}). פרטים בלוג: {LOG_PATH.name}")  # ל-stdout: stderr כבר מופנה ללוג אחרי טעינת neonize
    return 1  # כשל


def cmd_send(args):
    """שליחת עדכון מסוג start/done/error/blocked/progress."""
    return send_text(args.type, args.msg)  # כשל נרשם ומחזיר 0


def cmd_summary(args):
    """סיכום לפי חלון זמן (למשל --since 3h) מ-git log ומהקבצים ששונו, ושליחה."""
    since_git, label = parse_since(args.since)  # המרת החלון
    if not since_git:  # פורמט לא תקין — לא שולחים
        print("פורמט --since לא תקין. דוגמאות: 90m, 3h, 2d", file=sys.stderr)  # הוראה
        return 0  # לא שוברים את העבודה
    return send_text("summary", build_git_summary(since_git, label))  # בנייה ושליחה


def cmd_daily(_args):
    """סיכום יומי (מחצות) — מיועד להרצה מ-Windows Task Scheduler, בלי Claude."""
    return send_text("summary", build_git_summary("midnight", "סיכום יומי — היום"))  # מחצות עד עכשיו


def cmd_check_interval(_args):
    """מדפיס yes אם עבר מרווח העדכון המחזורי מאז העדכון האחרון, אחרת no (+ דקות שנותרו). קוד-יציאה תמיד 0."""
    cfg = load_config()  # בשביל המרווח
    interval_min = float(cfg.get("progress_interval_minutes") or DEFAULTS["progress_interval_minutes"])  # המרווח בדקות
    last = None  # זמן העדכון האחרון (epoch)
    if LAST_SENT_PATH.exists():  # נשלח משהו בעבר
        try:  # קובץ פגום = כאילו לא נשלח
            last = float(json.loads(LAST_SENT_PATH.read_text(encoding="utf-8")).get("ts"))  # הזמן השמור
        except (OSError, ValueError, TypeError):  # קריאה/פרסור נכשלו
            last = None  # מתייחסים כאילו אין
    if last is None:  # מעולם לא נשלח עדכון
        print("yes")  # הגיע הזמן לשלוח
        return 0  # קוד יציאה תקין
    elapsed_min = (time.time() - last) / 60.0  # כמה דקות עברו
    if elapsed_min >= interval_min:  # עבר המרווח
        print("yes")  # לשלוח progress
    else:  # עוד לא עבר
        print(f"no ({int(interval_min - elapsed_min) + 1} דקות נותרו)")  # כמה נותר, מעוגל למעלה
    return 0  # קוד יציאה תקין


def cmd_send_file(args):
    """שליחת קובץ (למשל APK) ל"הודעה לעצמי" עם כיתוב קצר. הכיתוב עובר את אותו ניקוי כמו הודעות (בלי נתיבים/סודות)."""
    p = Path(args.path)  # הקובץ לשליחה
    if not p.is_file():  # קובץ חסר — הודעה ברורה
        print(f"הקובץ לא נמצא: {p.name}")  # רק שם הקובץ, בלי נתיב מלא
        return 1  # כשל — פקודה ידנית, מדווחים בבירור
    size_mb = p.stat().st_size / (1024 * 1024)  # גודל במגה-בייט
    if size_mb > FILE_MAX_MB:  # מעל מגבלת המסמכים של וואטסאפ
        print(f"הקובץ גדול מדי ({size_mb:.0f}MB > {FILE_MAX_MB}MB)")  # הסבר
        return 1  # כשל
    cfg = load_config()  # ההגדרות (מספר, enabled)
    caption = sanitize(args.msg or p.name)  # כיתוב מנוקה — כמו כל הודעה
    if len(caption) > MAX_LEN:  # T3: אותה תקרה כמו הודעה רגילה
        caption = caption[: MAX_LEN - 1] + "…"  # T3: חיתוך עם סימן השמטה
    ok, reason = deliver(caption, cfg, timeout=FILE_TIMEOUT_SEC, file_path=str(p))  # העלאה ושליחה, עם זמן ארוך לקובץ גדול
    logging.info("send-file: ok=%s reason=%s name=%s size=%.1fMB", ok, reason, p.name, size_mb)  # תיעוד בלוג
    print("נשלח." if ok else f"השליחה נכשלה: {reason}")  # תוצאה למשתמש
    return 0 if ok else 1  # פקודה ידנית — כשל מדווח בקוד יציאה


def cmd_test(_args):
    """הודעת בדיקה — כשל מחזיר שגיאה ברורה וקוד-יציאה 1."""
    return send_text("test", "הודעת בדיקה מ-wa-status.", strict=True)  # strict = דיווח כשל ברור


def main(argv=None):
    """נקודת הכניסה: פרסור הפקודה והרצתה. פקודות השליחה לעולם לא מחזירות קוד-כשל."""
    _setup_output()  # פלט UTF-8
    _setup_logging()  # לוג לקובץ
    parser = argparse.ArgumentParser(prog="wa_status.py", description="עדכוני סטטוס לוואטסאפ (חד-כיווני)")  # הפרסר הראשי
    sub = parser.add_subparsers(dest="cmd", required=True)  # פקודת-משנה חובה
    p_setup = sub.add_parser("setup", help="התחברות ראשונה (QR) ושליחת הודעת אימות")  # setup
    p_setup.add_argument("--code", action="store_true", help="קוד-צימוד בן 8 תווים במקום QR (דורש phone ב-config)")  # חלופה ל-QR
    p_send = sub.add_parser("send", help="שליחת עדכון")  # send
    p_send.add_argument("--type", required=True, choices=SEND_TYPES, help="סוג העדכון")  # סוג
    p_send.add_argument("--msg", required=True, help="תוכן ההודעה (שורה-שתיים)")  # תוכן
    p_summary = sub.add_parser("summary", help="סיכום לפי חלון זמן מ-git")  # summary
    p_summary.add_argument("--since", required=True, help="חלון זמן: 90m / 3h / 2d")  # חלון
    sub.add_parser("daily", help="סיכום יומי (ל-Task Scheduler)")  # daily
    sub.add_parser("check-interval", help="האם עבר מרווח העדכון המחזורי (yes/no)")  # check-interval
    sub.add_parser("test", help="הודעת בדיקה")  # test
    p_file = sub.add_parser("send-file", help="שליחת קובץ (למשל APK) להודעה לעצמי")  # send-file
    p_file.add_argument("--path", required=True, help="הקובץ לשליחה")  # הקובץ
    p_file.add_argument("--msg", default="", help="כיתוב קצר (ברירת מחדל: שם הקובץ)")  # כיתוב
    args = parser.parse_args(argv)  # פרסור
    handlers = {  # מיפוי פקודה -> פונקציה
        "setup": cmd_setup, "send": cmd_send, "summary": cmd_summary,
        "daily": cmd_daily, "check-interval": cmd_check_interval, "test": cmd_test,
        "send-file": cmd_send_file,  # שליחת קובץ
    }
    try:  # רשת ביטחון — באג לא צפוי לא ישבור את עבודת Claude
        return handlers[args.cmd](args)  # הרצת הפקודה
    except Exception as exc:  # noqa: BLE001 — חריגה לא צפויה: נרשמת; פקודות שליחה מחזירות 0
        logging.exception("שגיאה לא צפויה בפקודה %s", args.cmd)  # לוג מלא עם traceback
        if args.cmd in ("setup", "test", "send-file"):  # פקודות שחייבות לדווח כשל בבירור
            print(f"שגיאה: {exc}")  # ל-stdout: ייתכן ש-stderr כבר מופנה ללוג
            return 1  # כשל
        return 0  # send/summary/daily/check-interval — לא שוברים את העבודה


if __name__ == "__main__":  # הרצה ישירה מה-CLI
    _code = main()  # מריצים את הפקודה ושומרים את קוד היציאה
    sys.stdout.flush()  # מוודאים שכל הפלט נכתב לפני היציאה המהירה
    sys.stderr.flush()  # כנ"ל לפלט השגיאות
    logging.shutdown()  # סוגר את קובץ הלוג בצורה תקינה
    # יציאה מיידית בלי שלב ה-finalization של Python: ספריית ה-Go של neonize קורסת (segfault, קוד 139)
    # כשהמפרש מנקה אותה בכיבוי — נצפה בפועל ב-Python 3.14 אחרי שליחה מוצלחת. os._exit מדלג על זה
    # ושומר על הדרישה ש-send/summary/daily יחזירו 0 תמיד.
    os._exit(_code)  # קוד היציאה של הפקודה, בלי ניקוי שעלול לקרוס
