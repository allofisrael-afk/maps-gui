import logging  # רישום אירועים לקובץ לוג
import math  # חישוב זוויות למחוג שעוני הסקירה בדשבורד
import os  # גישה לנתיבי קבצים ומשתני סביבה
import subprocess  # הפעלת תהליכי שרת חיצוניים
import sys  # גישה לארגומנטים ויציאה מהאפליקציה
import time  # חישוב uptime בדשבורד התהליכים
import urllib.parse  # קידוד שמות ערים לפורמט URL
import psutil  # מדידת CPU/זיכרון לתהליכי השרתים בדשבורד
import requests  # שליחת בקשות HTTP לשרתים
from datetime import datetime  # חישוב פקיעת cache לפי זמן
from MAP import create_map  # ייבוא פונקציית יצירת המפה
from test_requests import run_health_checks, summarize  # בדיקת תקינות שרתים לדשבורד
from security_checks import run_security_checks, summarize_findings  # סריקת אבטחה/חשיפה לדשבורד
from PyQt5.QtCore import (  # רכיבי ליבה: טיימר, thread ברקע לדשבורד, אנימציה, כיוון, גיאומטריה לשעוני הסקירה
    Qt, QUrl, QDateTime, QSize, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, QPointF
)
from PyQt5.QtGui import QIcon, QColor, QPainter, QPen, QFont  # אייקונים/צבעים לממשק + ציור שעוני הסקירה בדשבורד
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage  # תצוגת דפדפן פנימי להצגת המפה
from PyQt5.QtWidgets import (  # רכיבי ממשק גרפי
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QGridLayout,
    QTextEdit, QFileDialog, QSplitter, QSizePolicy, QDoubleSpinBox,
    QMessageBox, QLabel, QTabWidget, QSlider, QComboBox, QFrame,  # QLabel לכותרות, QTabWidget ללשוניות, QSlider לשקיפות, QComboBox להיסטוריה, QFrame להפרדה
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView  # רכיבי דשבורד התהליכים
)
from PyQt5.QtCore import QSettings  # שמירת הגדרות והיסטוריית ערים בין הפעלות

# הגדרת הלוגים בתחילת הקובץ
logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')

MAX_LOG_LINES = 500  # מגבלת שורות לוג למניעת האטה לאחר שעות ריצה


class LoggingWebEnginePage(QWebEnginePage):
    """ עמוד WebEngine שמתעד שגיאות JS ללוג עם קובץ ומספר שורה מדויקים (לאבחון שגיאות כמו getSize). """
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        logging.warning(f"JS console [{level}] {sourceID}:{lineNumber} - {message}")
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


class MetricsWorker(QThread):
    """
    אוסף את נתוני הדשבורד ב-thread נפרד: קריאות HTTP חוסמות ל-GET /metrics (עד timeout=1
    שנייה, כפול 3 שרתים) ופעולות psutil היו רצות קודם בתוך QTimer על ה-thread הראשי —
    מה שהקפיא את כל ה-GUI (כולל תצוגת המפה) לזמן ניכר בכל טיק. כאן העבודה החוסמת
    מתבצעת ב-thread ברקע, ורק תוצאה מוכנה (רשימות טקסט) נשלחת ל-thread הראשי דרך signal.
    """
    resultReady = pyqtSignal(list, list)  # (proc_rows, api_rows)

    def __init__(self, app_ref, interval_sec, parent=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.interval_sec = interval_sec
        self._running = True
        self._psutil_procs = {}
        self._psutil_children = {}

    def stop(self):
        self._running = False
        self.wait(2000)

    def run(self):
        while self._running:
            try:
                proc_rows, api_rows = self._collect()
                self.resultReady.emit(proc_rows, api_rows)
            except Exception:
                pass  # לא מפילים את thread המדידה על שגיאה חד-פעמית — פשוט מדלגים לטיק הבא
            self.msleep(int(self.interval_sec * 1000))

    def _collect(self):
        proc_rows = []
        api_rows = []
        for attr, label, port in ProcessDashboard.SERVERS:
            proc = getattr(self.app_ref, attr, None)
            running = proc is not None and proc.poll() is None
            pid_str, uptime_str, res_str = "—", "—", "—"

            if running:
                pid_str = str(proc.pid)
                try:
                    ps = self._get_root_process(attr, proc.pid)
                    # ה-PID שנשמר הוא ה"עוטף" החיצוני בלבד: virtualenv (python.exe ב-.venv) מריץ
                    # launcher stub שמבצע re-exec לתהליך האמיתי, ו-Flask עם debug=True מוסיף שכבת
                    # reloader משלו — כך שבפועל יש שרשרת תהליכי-בן. סיכום CPU/זיכרון על כל העץ
                    # (הורה + כל הצאצאים) הוא הדרך היחידה לקבל מספר משמעותי, במקום למדוד עוטף כמעט-ריק.
                    # cpu_percent(None) חייב להיקרא בדיוק פעם אחת לכל תהליך בכל טיק —
                    # קריאה שנייה מיד תמדוד דלתא של מיקרו-שניות ותחזיר כמעט תמיד 0.
                    children = self._get_cached_children(attr, ps)
                    tree = [ps] + children
                    uptime_str = ProcessDashboard._fmt_uptime(time.time() - ps.create_time())
                    cpu_total, rss_total = 0.0, 0
                    for p in tree:
                        try:
                            cpu_total += p.cpu_percent(None)
                            rss_total += p.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    res_str = f"{cpu_total:.1f}%  /  {rss_total / (1024 * 1024):.0f} MB"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                try:
                    # "127.0.0.1" ולא "localhost" — במחשב הזה resolve ל-localhost מנסה IPv6 קודם
                    # ונופל ל-IPv4 רק אחרי ~2 שניות, כך שה-timeout=1 כאן היה נכשל כמעט תמיד.
                    resp = requests.get(f"http://127.0.0.1:{port}/metrics", timeout=1)
                    if resp.status_code == 200:
                        for endpoint, s in resp.json().get("endpoints", {}).items():
                            api_rows.append((label, endpoint, s["count"], s["errors"], s["avg_ms"], s["last_call"] or "—"))
                except requests.exceptions.RequestException:
                    pass  # שרת פעיל אך /metrics עדיין לא זמין (למשל ברגע ההפעלה) — פשוט מדלגים הפעם
            else:
                self._psutil_procs.pop(attr, None)
                self._psutil_children.pop(attr, None)

            proc_rows.append((label, port, running, pid_str, uptime_str, res_str))
        return proc_rows, api_rows

    def _get_root_process(self, attr, pid):
        """ מחזיר psutil.Process יציב עבור תהליך השורש, ממטמון בין טיקים — נדרש כדי
        ש-cpu_percent(None) ימדוד דלתא אמיתית מאז הטיק הקודם ולא מאז רגע ההפעלה. """
        ps = self._psutil_procs.get(attr)
        if ps is None or ps.pid != pid:
            ps = psutil.Process(pid)
            ps.cpu_percent(None)  # קריאת "חימום" — מדידה ראשונה תמיד מחזירה 0.0
            self._psutil_procs[attr] = ps
            self._psutil_children[attr] = {}
        return ps

    def _get_cached_children(self, attr, root_process):
        """ מחזיר את כל צאצאי התהליך (ה-launcher stub של virtualenv + reloader של Werkzeug
        יוצרים שרשרת תהליכי-בן), תוך שימוש במטמון קבוע per-PID כדי לשמר את מצב cpu_percent. """
        cached = self._psutil_children.setdefault(attr, {})
        current = {}
        try:
            for child in root_process.children(recursive=True):
                cached_child = cached.get(child.pid)
                if cached_child is None:
                    child.cpu_percent(None)  # קריאת "חימום" לתהליך-בן שהתגלה עכשיו לראשונה
                    current[child.pid] = child
                else:
                    current[child.pid] = cached_child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        self._psutil_children[attr] = current
        return list(current.values())


class HealthCheckWorker(QThread):
    """
    מריץ את בדיקות התקינות (test_requests.run_health_checks) על thread נפרד, כדי
    שהקריאות ל-HTTP (חלקן עד 20 שניות timeout — למשל /los, /flight_search) לא יקפיאו
    את ה-GUI. שולח תוצאה מלאה בסיום; progressReady משודר אחרי כל בדיקה בודדת כדי
    שהטבלה תתמלא בהדרגה במקום לקפוץ בבת אחת בסוף.
    """
    progressReady = pyqtSignal(object)  # TestResult בודד — נשלח מיד אחרי כל בדיקה
    finished_results = pyqtSignal(list)  # רשימת כל ה-TestResult בסיום

    def run(self):
        try:
            results = run_health_checks(on_progress=self.progressReady.emit)
        except Exception:
            results = []
        self.finished_results.emit(results)


class SecurityCheckWorker(QThread):
    """
    מריץ את בדיקות האבטחה (security_checks.run_security_checks) על thread נפרד — כולל
    סריקת pip-audit (עד 120 שניות) וסריקת קובץ APK שלם, כדי לא להקפיא את ה-GUI.
    """
    progressReady = pyqtSignal(object)  # SecurityFinding בודד — נשלח מיד אחרי כל בדיקה
    finished_findings = pyqtSignal(list)  # רשימת כל ה-SecurityFinding בסיום

    def run(self):
        try:
            findings = run_security_checks(on_progress=self.progressReady.emit)
        except Exception:
            findings = []
        self.finished_findings.emit(findings)


class GaugeWidget(QWidget):
    """
    שעון מד-מהירות (קשת 270°, אזורי צבע אדום/צהוב/ירוק, מחוג) שמציג אחוז תקינות בודד —
    נצרך ברשת 3×3 (שרת × סוג בדיקה) בלשונית "סקירה" של הדשבורד. value=None (לפני
    שהבדיקה הרלוונטית רצה בכלל) מצויר כקשת אפורה עם "—" במקום מספר.
    """
    _BANDS = ((0, 60, "#f38ba8"), (60, 90, "#f9e2af"), (90, 100, "#a6e3a1"))  # אדום / צהוב / ירוק
    _START_ANGLE = 225.0  # תחילת הקשת (למטה-שמאל, במעלות בקונבנציית Qt: 0°=3 שעונים, CCW חיובי)
    _SWEEP = 270.0        # טווח הקשת (מעלות) — נגמר ב-225-270=-45° (למטה-ימין)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None  # None = אין נתונים עדיין
        self.setFixedSize(120, 120)

    def setValue(self, value):
        """ value: אחוז 0–100, או None להצגת "אין נתונים". """
        self._value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())
        margin = 16
        rect = QRectF((self.width() - side) / 2 + margin, (self.height() - side) / 2 + margin,
                       side - 2 * margin, side - 2 * margin)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        radius = rect.width() / 2.0

        # קשת רקע אפורה על כל הטווח
        painter.setPen(QPen(QColor("#313244"), 10, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, int(self._START_ANGLE * 16), int(-self._SWEEP * 16))

        # שלושת אזורי הצבע לפי סף (אדום/צהוב/ירוק)
        for lo, hi, color in self._BANDS:
            start_angle = self._START_ANGLE - (lo / 100.0) * self._SWEEP
            span_angle = -((hi - lo) / 100.0) * self._SWEEP
            painter.setPen(QPen(QColor(color), 10, Qt.SolidLine, Qt.FlatCap))
            painter.drawArc(rect, int(start_angle * 16), int(span_angle * 16))

        if self._value is None:
            painter.setPen(QColor("#585b70"))
            painter.setFont(QFont("Segoe UI", 15, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, "—")
            return

        value = max(0.0, min(100.0, self._value))
        angle_deg = self._START_ANGLE - (value / 100.0) * self._SWEEP
        angle_rad = math.radians(angle_deg)
        needle_len = radius - 8
        nx = cx + needle_len * math.cos(angle_rad)
        ny = cy - needle_len * math.sin(angle_rad)  # y הפוך — Qt מתחיל מלמעלה

        painter.setPen(QPen(QColor("#cdd6f4"), 3))
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#cdd6f4"))
        painter.drawEllipse(QPointF(cx, cy), 5, 5)

        painter.setPen(QColor("#cdd6f4"))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        text_rect = QRectF(0, cy + radius * 0.32, self.width(), 24)
        painter.drawText(text_rect, Qt.AlignCenter, f"{value:.0f}%")


class ProcessDashboard(QDialog):
    """
    חלון נפרד (לא-מודלי) למעקב חי אחר 3 שרתי ה-Flask: סטטוס תהליך (פעיל/כבוי, PID,
    זמן ריצה, CPU/זיכרון דרך psutil), מטריקות קריאות API לכל endpoint (נשלף מ-GET
    /metrics של כל שרת, ר' metrics.py), ותצוגת יומן חי המשקפת את self.logs.
    כל הפעולות החוסמות (HTTP, psutil) רצות ב-MetricsWorker על thread נפרד.
    """
    SERVERS = [
        ("geo_server_process", "GeoServer", 5003),
        ("weather_server_process", "WeatherServer", 5002),
        ("flight_server_process", "FlightServer", 5004),
    ]
    REFRESH_SEC = 1.5  # תדירות רענון הדשבורד

    def __init__(self, app_ref, parent=None):
        super().__init__(parent)
        self.app_ref = app_ref  # הפניה ל-MapApp — גישה לתהליכים וליומן
        self.setWindowTitle("דשבורד מעקב תהליכים")
        # QDialog לא מציג כפתור מזעור כברירת מחדל ב-Windows — מוסיפים אותו במפורש
        # (כפתור מקסום לא מתבקש, אבל מזעור וסגירה כן) כדי שהחלון יתנהג כמו חלון רגיל.
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.resize(820, 820)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())  # ירושת ערכת הנושא הכהה מהחלון הראשי

        layout = QVBoxLayout(self)

        # ארבע לשוניות — סקירה (שעונים), סטטוס/מטריקות רגיל, בדיקת תקינות, ובדיקת אבטחה —
        # במקום ערימה אנכית אחת שהייתה נהיית עמוסה מדי עם כל הטבלאות יחד.
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- לשונית 0: סקירה כללית — רשת שעונים 3×3 (שרת × תקינות/עומס/אבטחה) ---
        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)

        overview_header = QHBoxLayout()
        overview_label = QLabel("סקירה כללית")
        overview_label.setObjectName("sectionLabel")
        overview_header.addWidget(overview_label)
        overview_header.addStretch()
        self.overview_run_button = QPushButton("▶ הרץ הכל")
        self.overview_run_button.clicked.connect(self.run_all_checks)
        overview_header.addWidget(self.overview_run_button)
        overview_layout.addLayout(overview_header)

        gauge_grid = QGridLayout()
        gauge_grid.setHorizontalSpacing(24)
        gauge_grid.setVerticalSpacing(8)

        self._GAUGE_CATEGORIES = [("health", "תקינות"), ("load", "עומס"), ("security", "אבטחה")]
        self._GAUGE_SERVERS = ["GeoServer", "WeatherServer", "FlightServer"]

        for col, (_, cat_label) in enumerate(self._GAUGE_CATEGORIES, start=1):
            col_label = QLabel(cat_label)
            col_label.setAlignment(Qt.AlignCenter)
            col_label.setObjectName("sectionLabel")
            gauge_grid.addWidget(col_label, 0, col)

        self.gauges = {}  # {(server, category): GaugeWidget}
        for row, server in enumerate(self._GAUGE_SERVERS, start=1):
            row_label = QLabel(server)
            row_label.setAlignment(Qt.AlignCenter)
            gauge_grid.addWidget(row_label, row, 0)
            for col, (category, _) in enumerate(self._GAUGE_CATEGORIES, start=1):
                gauge = GaugeWidget()
                self.gauges[(server, category)] = gauge
                gauge_grid.addWidget(gauge, row, col, Qt.AlignCenter)

        overview_layout.addLayout(gauge_grid)
        overview_layout.addStretch()

        self.tabs.addTab(overview_tab, "סקירה")
        self._last_health_results = []    # תוצאות הריצה האחרונה — נצרך גם ע"י _update_gauges
        self._last_security_findings = []  # ממצאי הריצה האחרונה — נצרך גם ע"י _update_gauges

        # --- לשונית 1: סטטוס שרתים + מטריקות API + יומן ---
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)

        proc_label = QLabel("סטטוס שרתים")
        proc_label.setObjectName("sectionLabel")
        status_layout.addWidget(proc_label)

        self.proc_table = QTableWidget(len(self.SERVERS), 6)
        self.proc_table.setHorizontalHeaderLabels(["שרת", "פורט", "סטטוס", "PID", "זמן ריצה", "CPU / זיכרון"])
        self.proc_table.verticalHeader().setVisible(False)
        self.proc_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.proc_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.proc_table.setFixedHeight(150)
        status_layout.addWidget(self.proc_table)

        api_label = QLabel("מטריקות קריאות API")
        api_label.setObjectName("sectionLabel")
        status_layout.addWidget(api_label)

        self.api_table = QTableWidget(0, 6)
        self.api_table.setHorizontalHeaderLabels(["שרת", "נתיב", "קריאות", "שגיאות", "זמן ממוצע (ms)", "קריאה אחרונה"])
        self.api_table.verticalHeader().setVisible(False)
        self.api_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.api_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.api_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        status_layout.addWidget(self.api_table)

        log_label = QLabel("יומן חי")
        log_label.setObjectName("sectionLabel")
        status_layout.addWidget(log_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        for line in self.app_ref.logs[-200:]:  # מילוי ראשוני מהיומן הקיים
            self.log_view.append(f'<span style="color:#cdd6f4;">{line}</span>')
        status_layout.addWidget(self.log_view)

        self.tabs.addTab(status_tab, "שרתים ומטריקות")

        # --- לשונית 2: בדיקת תקינות (test_requests.py) ---
        health_tab = QWidget()
        health_layout = QVBoxLayout(health_tab)

        health_header = QHBoxLayout()
        health_label = QLabel("בדיקת תקינות (Health Check)")
        health_label.setObjectName("sectionLabel")
        health_header.addWidget(health_label)
        health_header.addStretch()
        self.health_run_button = QPushButton("▶ הרץ בדיקה")
        self.health_run_button.clicked.connect(self.run_health_check)
        health_header.addWidget(self.health_run_button)
        health_layout.addLayout(health_header)

        self.health_summary_label = QLabel("לא הורצה בדיקה עדיין")
        health_layout.addWidget(self.health_summary_label)

        self.health_table = QTableWidget(0, 5)
        self.health_table.setHorizontalHeaderLabels(["שרת", "בדיקה", "סטטוס", "זמן (ms)", "הודעה"])
        self.health_table.verticalHeader().setVisible(False)
        self.health_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.health_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.health_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        health_layout.addWidget(self.health_table)

        self.tabs.addTab(health_tab, "בדיקת תקינות")
        self.health_worker = None  # מופע HealthCheckWorker פעיל — None כשאין בדיקה רצה

        # --- לשונית 3: בדיקת אבטחה (security_checks.py) ---
        security_tab = QWidget()
        security_layout = QVBoxLayout(security_tab)

        security_header = QHBoxLayout()
        security_label = QLabel("בדיקת אבטחה (Security Scan)")
        security_label.setObjectName("sectionLabel")
        security_header.addWidget(security_label)
        security_header.addStretch()
        self.security_run_button = QPushButton("🔒 הרץ סריקה")
        self.security_run_button.clicked.connect(self.run_security_check)
        security_header.addWidget(self.security_run_button)
        security_layout.addLayout(security_header)

        self.security_summary_label = QLabel("לא הורצה סריקה עדיין")
        security_layout.addWidget(self.security_summary_label)

        self.security_table = QTableWidget(0, 4)
        self.security_table.setHorizontalHeaderLabels(["בדיקה", "חומרה", "תוצאה", "הודעה"])
        self.security_table.verticalHeader().setVisible(False)
        self.security_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.security_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.security_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        security_layout.addWidget(self.security_table)

        self.tabs.addTab(security_tab, "אבטחה")
        self.security_worker = None  # מופע SecurityCheckWorker פעיל — None כשאין סריקה רצה

        # כל העבודה החוסמת (HTTP ל-/metrics, psutil) רצה ב-thread נפרד; כאן רק מציירים
        # את התוצאה המוכנה שהוא שולח — כך שה-GUI (כולל תצוגת המפה בחלון הראשי) לא נתקע.
        self.worker = MetricsWorker(self.app_ref, self.REFRESH_SEC, self)
        self.worker.resultReady.connect(self._apply_data)
        self.worker.start()

    def append_log_line(self, log_message, is_success=None):
        """ נקרא מ-MapApp.log_action בכל הודעת יומן חדשה, כדי לשקף אותה כאן חי. """
        color = "#a6e3a1" if is_success is True else "#f38ba8" if is_success is False else "#cdd6f4"
        self.log_view.append(f'<span style="color:{color};">{log_message}</span>')
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _apply_data(self, proc_rows, api_rows):
        """ Slot מהיר בלבד (ללא I/O) שמצייר את התוצאות שחושבו ב-MetricsWorker לתוך הטבלאות. """
        for row, (label, port, running, pid_str, uptime_str, res_str) in enumerate(proc_rows):
            self._set_cell(self.proc_table, row, 0, label)
            self._set_cell(self.proc_table, row, 1, str(port))
            status_item = QTableWidgetItem("● פעיל" if running else "○ כבוי")
            status_item.setForeground(QColor("#a6e3a1" if running else "#585b70"))
            self.proc_table.setItem(row, 2, status_item)
            self._set_cell(self.proc_table, row, 3, pid_str)
            self._set_cell(self.proc_table, row, 4, uptime_str)
            self._set_cell(self.proc_table, row, 5, res_str)

        self.api_table.setRowCount(len(api_rows))
        for r, (label, endpoint, count, errors, avg_ms, last_call) in enumerate(api_rows):
            self._set_cell(self.api_table, r, 0, label)
            self._set_cell(self.api_table, r, 1, endpoint)
            self._set_cell(self.api_table, r, 2, str(count))
            err_item = QTableWidgetItem(str(errors))
            if errors > 0:
                err_item.setForeground(QColor("#f38ba8"))
            self.api_table.setItem(r, 3, err_item)
            self._set_cell(self.api_table, r, 4, str(avg_ms))
            self._set_cell(self.api_table, r, 5, last_call)

    def run_health_check(self):
        """ מריץ בדיקת תקינות מלאה (test_requests.run_health_checks) על thread נפרד — שומר את ה-GUI חי גם כשבדיקה בודדת (למשל /los, /flight_search) לוקחת עד 20 שניות. """
        if self.health_worker is not None and self.health_worker.isRunning():
            return  # בדיקה כבר רצה — מונע הרצות כפולות בלחיצה חוזרת
        self.health_run_button.setEnabled(False)
        self.health_summary_label.setText("מריץ בדיקה...")
        self.health_summary_label.setStyleSheet("")
        self.health_table.setRowCount(0)
        self.health_worker = HealthCheckWorker(self)
        self.health_worker.progressReady.connect(self._append_health_row)
        self.health_worker.finished_results.connect(self._finish_health_check)
        self.health_worker.start()

    def _append_health_row(self, result):
        """ מוסיף שורת תוצאה בודדת לטבלה מיד עם קבלתה — הטבלה מתמלאת בהדרגה במקום לקפוץ בסוף. """
        row = self.health_table.rowCount()
        self.health_table.insertRow(row)
        self._set_cell(self.health_table, row, 0, result.server)
        self._set_cell(self.health_table, row, 1, result.name)
        status_item = QTableWidgetItem("✓ תקין" if result.ok else "✗ שגיאה")
        status_item.setForeground(QColor("#a6e3a1" if result.ok else "#f38ba8"))
        self.health_table.setItem(row, 2, status_item)
        self._set_cell(self.health_table, row, 3, f"{result.elapsed_ms:.0f}")
        self._set_cell(self.health_table, row, 4, result.message)

    def _finish_health_check(self, results):
        """ מציג את אחוז התקינות הכולל ופירוט תקין/סה"כ לכל שרת — כך שרואים מיד גם ציון כללי וגם איזה שרת ספציפי לא תקין. """
        self.health_run_button.setEnabled(True)
        self._last_health_results = results
        self._update_gauges()
        health_percent, per_server = summarize(results)
        if health_percent >= 90:
            color = "#a6e3a1"  # ירוק — תקין
        elif health_percent >= 60:
            color = "#f9e2af"  # צהוב — תקין חלקית
        else:
            color = "#f38ba8"  # אדום — בעייתי
        per_server_text = "   |   ".join(f"{server}: {ok}/{total}" for server, (ok, total) in per_server.items())
        self.health_summary_label.setText(f"תקינות כוללת: {health_percent}%    ({per_server_text})")
        self.health_summary_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def run_security_check(self):
        """ מריץ סריקת אבטחה מלאה (security_checks.run_security_checks) על thread נפרד — כוללת pip-audit וסריקת APK שעלולות לקחת עד כ-2 דקות. """
        if self.security_worker is not None and self.security_worker.isRunning():
            return  # סריקה כבר רצה — מונע הרצות כפולות בלחיצה חוזרת
        self.security_run_button.setEnabled(False)
        self.security_summary_label.setText("מריץ סריקה...")
        self.security_summary_label.setStyleSheet("")
        self.security_table.setRowCount(0)
        self.security_worker = SecurityCheckWorker(self)
        self.security_worker.progressReady.connect(self._append_security_row)
        self.security_worker.finished_findings.connect(self._finish_security_check)
        self.security_worker.start()

    def _append_security_row(self, finding):
        """ מוסיף שורת ממצא בודד לטבלה מיד עם קבלתו. """
        row = self.security_table.rowCount()
        self.security_table.insertRow(row)
        self._set_cell(self.security_table, row, 0, finding.check)
        severity_colors = {"high": "#f38ba8", "medium": "#f9e2af", "low": "#89b4fa", "info": "#585b70"}
        severity_item = QTableWidgetItem(finding.severity)
        severity_item.setForeground(QColor(severity_colors.get(finding.severity, "#cdd6f4")))
        self.security_table.setItem(row, 1, severity_item)
        result_item = QTableWidgetItem("✓ תקין" if finding.ok else "⚠ ממצא")
        result_item.setForeground(QColor("#a6e3a1" if finding.ok else severity_colors.get(finding.severity, "#f38ba8")))
        self.security_table.setItem(row, 2, result_item)
        self._set_cell(self.security_table, row, 3, finding.message)

    def _finish_security_check(self, findings):
        """ מציג כמה ממצאים נמצאו ובאיזו חומרה — כדי שרואים מיד אם יש משהו לטפל בו. """
        self.security_run_button.setEnabled(True)
        self._last_security_findings = findings
        self._update_gauges()
        issue_count, severity_counts = summarize_findings(findings)
        if issue_count == 0:
            color = "#a6e3a1"  # ירוק — לא נמצאו ממצאים
            self.security_summary_label.setText("לא נמצאו ממצאים")
        else:
            color = "#f38ba8" if severity_counts.get("high") else "#f9e2af"
            parts = "   |   ".join(f"{v} {k}" for k, v in severity_counts.items() if v)
            self.security_summary_label.setText(f"נמצאו {issue_count} ממצאים:    ({parts})")
        self.security_summary_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def run_all_checks(self):
        """ מריץ גם בדיקת תקינות וגם סריקת אבטחה במקביל (כל אחת ב-thread נפרד משלה) —
        כפתור "הרץ הכל" בלשונית הסקירה. השעונים מתעדכנים בהדרגה ככל שכל בדיקה מסיימת. """
        self.run_health_check()
        self.run_security_check()

    def _update_gauges(self):
        """ מחשב אחוז תקין/סה"כ לכל תא ברשת (שרת × תקינות/עומס/אבטחה) מתוך תוצאות הריצה
        האחרונות, ומעדכן את שעוני ה-GaugeWidget בהתאם. ממצאי אבטחה "Global" (pip-audit,
        APK) לא שייכים לשרת ספציפי — נספרים בציון האבטחה של כל שלושת השרתים כאחד. """
        health_by_server = {}
        load_by_server = {}
        for r in self._last_health_results:
            bucket = load_by_server if getattr(r, "category", "health") == "load" else health_by_server
            ok, total = bucket.get(r.server, (0, 0))
            bucket[r.server] = (ok + (1 if r.ok else 0), total + 1)

        security_by_server = {}
        global_ok, global_total = 0, 0
        for f in self._last_security_findings:
            if f.server == "Global":
                global_ok += 1 if f.ok else 0
                global_total += 1
            else:
                ok, total = security_by_server.get(f.server, (0, 0))
                security_by_server[f.server] = (ok + (1 if f.ok else 0), total + 1)

        for server in self._GAUGE_SERVERS:
            self._set_gauge(server, "health", health_by_server.get(server))
            self._set_gauge(server, "load", load_by_server.get(server))

            sec_ok, sec_total = security_by_server.get(server, (0, 0))
            combined_total = sec_total + global_total
            if combined_total == 0:
                self._set_gauge(server, "security", None)
            else:
                self._set_gauge(server, "security", (sec_ok + global_ok, combined_total))

    def _set_gauge(self, server, category, data):
        gauge = self.gauges.get((server, category))
        if gauge is None:
            return
        if not data or data[1] == 0:
            gauge.setValue(None)
        else:
            ok, total = data
            gauge.setValue(round(100.0 * ok / total, 1))

    @staticmethod
    def _set_cell(table, row, col, text):
        table.setItem(row, col, QTableWidgetItem(text))

    @staticmethod
    def _fmt_uptime(seconds):
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def closeEvent(self, event):
        self.worker.stop()  # עוצר את thread המדידה בצורה מסודרת לפני סגירה
        if self.health_worker is not None and self.health_worker.isRunning():
            # בדיקת תקינות עשויה עדיין לרוץ ברקע (עד 20 שניות לבדיקה) — מנתקים את ה-signals
            # כדי שהיא לא תנסה לעדכן widgets של דיאלוג שעומד להיהרס.
            try:
                self.health_worker.progressReady.disconnect(self._append_health_row)
                self.health_worker.finished_results.disconnect(self._finish_health_check)
            except TypeError:
                pass
        if self.security_worker is not None and self.security_worker.isRunning():
            # סריקת אבטחה עשויה לרוץ ברקע עד ~2 דקות (pip-audit) — אותו טיפול.
            try:
                self.security_worker.progressReady.disconnect(self._append_security_row)
                self.security_worker.finished_findings.disconnect(self._finish_security_check)
            except TypeError:
                pass
        self.app_ref._process_dashboard = None  # מאפשר פתיחה מחדש בלחיצה הבאה
        event.accept()


class MapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ניהול מערכת מפה אינטראקטיבית")  # כותרת החלון
        self.setMinimumSize(900, 600)  # גודל מינימלי שמבטיח שהמפה תישאר שמישה
        self.resize(1280, 750)  # גודל פתיחה נוח — רחב מספיק למפה ולפאנל
        screen = QApplication.primaryScreen().geometry()  # קבלת גודל המסך הראשי לצורך מרכוז
        self.move((screen.width() - 1280) // 2, (screen.height() - 750) // 2)  # מרכוז החלון במסך
        self.map_view = QWebEngineView()  # תצוגת המפה המוטמעת
        self.map_view.setPage(LoggingWebEnginePage(self.map_view))  # עמוד מותאם שמתעד שגיאות JS עם קובץ ומספר שורה
        self.map_view.setUrl(QUrl.fromLocalFile(os.path.abspath("map.html")))  # טעינת המפה בנתיב מוחלט — נדרש ב-QWebEngineView
        self.map_file = os.path.abspath("map.html")  # נתיב מוחלט לקובץ המפה לשימוש בטעינה מחדש
        self.geo_server_process = None      # תהליך GeoServer — None כשהשרת כבוי
        self.weather_server_process = None  # תהליך WeatherServer — None כשהשרת כבוי
        self.flight_server_process = None   # תהליך FlightServer — None כשהשרת כבוי
        self.logs = []  # רשימת הודעות הלוג שנצברו מאז הפעלת האפליקציה
        self.unread_log_count = 0  # מונה לוגים שלא נצפו — מוצג כ-badge על כפתור הפעמון
        self.weather_cache = {}  # cache בזיכרון: {(lat, lon): (weather_data, timestamp)} — מונע בקשות כפולות
        self.debounce_timer = QTimer()  # טיימר debounce — שולח בקשה רק אחרי שהמשתמש הפסיק להקליד
        self.debounce_timer.setSingleShot(True)  # הטיימר יורה פעם אחת בלבד לכל הפעלה
        self.debounce_timer.timeout.connect(self.submit_coordinates)  # בסיום ה-debounce — שליחת הקואורדינטות
        self.settings = QSettings("MapApp", "MapGUI")  # אחסון הגדרות קבועות (היסטוריית ערים) בין הפעלות
        self._map_created = False  # האם המפה נוצרה לפחות פעם אחת — קובע אם לאפס JS או לייצר מחדש
        self._process_dashboard = None  # מופע יחיד של חלון דשבורד התהליכים — None כשסגור
        self._kill_zombie_servers()  # הרג שרתים שנשארו רצים מהפעלות קודמות
        self.init_ui()  # בניית ממשק המשתמש

    def _kill_zombie_servers(self):
        """ הורג תהליכים שנשארו רצים על פורטי השרתים מהפעלות קודמות. """
        for port in [5002, 5003, 5004]:
            try:
                result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if f':{port} ' in line and 'LISTENING' in line:
                        pid = line.strip().split()[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            except Exception:
                pass

    def log_action(self, message, is_success=None):
        """ פונקציה שמוסיפה את ההודעה לרשימת הלוגים עם תאריך ושעה. """
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")  # חותמת זמן לכל הודעה
        log_message = f"{timestamp} - {message}"  # הרכבת הודעת הלוג המלאה

        self.logs.append(log_message)  # הוספה לרשימה הפנימית לצורך שמירה וייצוא

        if len(self.logs) > MAX_LOG_LINES:  # חיתוך רשימה ל-500 שורות — מונע האטה עם הזמן
            self.logs = self.logs[-MAX_LOG_LINES:]

        self.update_log_view(message, is_success)  # עדכון תצוגה עם צביעה לפי סוג ההודעה

        if self._process_dashboard is not None:  # שיקוף חי ליומן הדשבורד אם הוא פתוח
            self._process_dashboard.append_log_line(log_message, is_success)

        if not self.log_area.isVisible():  # רק כשהלוג סגור — עדכון badge
            self.unread_log_count += 1  # הגדלת מונה לוגים שלא נצפו
            self.badge_label.setText(str(self.unread_log_count))  # הצגת המספר על הbadge
            self.badge_label.setVisible(True)  # הצגת ה-badge

        self.statusBar().showMessage(message, 4000)  # הצגת ההודעה האחרונה ב-Status bar ל-4 שניות
        logging.info(log_message)  # כתיבה לקובץ הלוג

    def log_process_action(self, process_name, action, success=True):
        """
        פונקציה שמבצעת רישום של כל פעולה הקשורה בתהליך.
        :param process_name: שם התהליך (למשל, GeoServer או WeatherServer)
        :param action: פעולה שמתבצעת (הפעלה/עצירה)
        :param success: האם הפעולה הצליחה או לא
        """
        status = "הצליחה" if success else "נכשלה"
        self.log_action(f"פעולה '{action}' על {process_name} {status}.", is_success=success)

    def open_process_dashboard(self):
        """ פותח (או מעלה לחזית) את חלון דשבורד מעקב התהליכים. מופע יחיד — לא נפתח כפול. """
        if self._process_dashboard is None:
            self._process_dashboard = ProcessDashboard(self, self)
            self._process_dashboard.show()
        else:
            self._process_dashboard.raise_()
            self._process_dashboard.activateWindow()

    def update_log_view(self, message="", is_success=None):
        """ הוספת שורת לוג אחת עם צבע מתאים — מהיר יותר מ-setPlainText מחדש בכל פעם. """
        if is_success is True:
            color = "#a6e3a1"  # ירוק להצלחה
        elif is_success is False:
            color = "#f38ba8"  # אדום לשגיאה
        else:
            color = "#cdd6f4"  # אפור-לבן למידע רגיל

        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")  # חותמת זמן לתצוגה
        html_line = f'<span style="color:{color}">{timestamp} - {message}</span>'  # שורה מעוצבת ב-HTML
        self.log_area.append(html_line)  # append מוסיף שורה בודדת — יעיל מ-setPlainText כולו

        sb = self.log_area.verticalScrollBar()  # גלילה אוטומטית לתחתית בכל הוספה
        sb.setValue(sb.maximum())  # גלילה לשורה האחרונה

    def update_bell_icon(self, color):
        """ עדכון אייקון פעמון בצבע מתאים """
        if color == "green":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_green.png"))  # אייקון ירוק — שרתים פעילים
        elif color == "red":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_red.png"))  # אייקון אדום — שגיאה
        else:
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon.png"))  # אייקון ברירת מחדל

        self.toggle_log_button.setIcon(bell_icon)  # עדכון האייקון על הכפתור

    # ── שיטות עזר חדשות ──

    def _restart_debounce(self):
        """ מאפס את טיימר ה-debounce — הבקשה תישלח רק 600ms אחרי שינוי אחרון. """
        self.debounce_timer.start(600)  # כל שינוי ב-Spinbox מאפס את הספירה לאחור

    def _load_city_history(self):
        """ טוען רשימת ערים אחרונות מ-QSettings ומאכלס את ה-ComboBox. """
        history = self.settings.value("city_history", [])  # קריאה מ-QSettings — רשימה ריקה אם לא קיים
        if isinstance(history, str):  # QSettings מחזיר str אם רק פריט אחד נשמר
            history = [history]
        for city in history:
            self.city_name_input.addItem(city)  # הוספת כל עיר כאפשרות בתפריט

    def _save_city_to_history(self, city_name):
        """ שומר עיר בהיסטוריה ב-QSettings ומעדכן את ה-ComboBox. """
        history = self.settings.value("city_history", [])  # קריאת ההיסטוריה הקיימת
        if isinstance(history, str):
            history = [history]
        if city_name in history:  # הסרת הכניסה הישנה אם קיימת — נוסיף אותה בראש
            history.remove(city_name)
        history.insert(0, city_name)  # הוספה לראש הרשימה — האחרון ראשון
        history = history[:10]  # שמירת 10 ערים אחרונות בלבד
        self.settings.setValue("city_history", history)  # כתיבה בחזרה ל-QSettings
        self.city_name_input.clear()  # ניקוי ה-ComboBox לפני אכלוס מחדש
        for city in history:
            self.city_name_input.addItem(city)  # אכלוס ה-ComboBox מחדש עם הסדר המעודכן

    def center_map_israel(self):
        """ מחזיר את מרכז המפה מעל ישראל עם zoom מתאים. """
        self.map_view.page().runJavaScript(
            "map.setView([31.7683, 35.2137], 8);"  # Leaflet: setView([lat, lng], zoom)
        )
        self.log_action("המפה מורכזת מעל ישראל.")  # תיעוד הפעולה

    def clear_map_markers(self):
        """ מוחק את כל הסמנים וה-InfoWindows מהמפה דרך JavaScript. """
        self.map_view.page().runJavaScript("""
            if (typeof allMarkers !== 'undefined') {
                allMarkers.forEach(function(m) { m.remove(); });  /* Leaflet: remove() מסיר מהמפה */
                allMarkers = [];
            }
        """)
        self.log_action("כל הסמנים נמחקו מהמפה.")  # תיעוד

    def update_heatmap_opacity(self, value):
        """ שולח את ערך ה-Slider כ-opacity לשכבת מפת החום הטמפרטורה ב-JavaScript. """
        opacity = value / 100.0
        self.map_view.page().runJavaScript(f"setTempLayerOpacity({opacity});")

    def clear_logs(self):
        """ מנקה את תצוגת הלוגים ואת רשימת הלוגים הפנימית. """
        self.logs = []  # איפוס הרשימה הפנימית
        self.log_area.clear()  # ניקוי תצוגת ה-HTML
        self.unread_log_count = 0  # איפוס מונה הלוגים הלא-נקראים
        self.badge_label.setVisible(False)  # הסתרת ה-badge

    def _load_flight_history(self):
        """ טוען היסטוריית מספרי טיסות מ-QSettings לתוך ה-ComboBox. """
        history = self.settings.value("flight_history", [])  # קריאת היסטוריה — רשימה ריקה אם לא קיים
        if isinstance(history, str):  # QSettings מחזיר str אם רק פריט אחד נשמר
            history = [history]
        for flight in history:
            self.flight_input.addItem(flight)  # הוספת כל מספר טיסה לתפריט

    def _save_flight_to_history(self, flight_number):
        """ שומר מספר טיסה בהיסטוריה ב-QSettings ומעדכן את ה-ComboBox. """
        history = self.settings.value("flight_history", [])  # קריאת ההיסטוריה הקיימת
        if isinstance(history, str):
            history = [history]
        if flight_number in history:  # הסרת כניסה ישנה — נוסיף בראש
            history.remove(flight_number)
        history.insert(0, flight_number)  # הוספה לראש — האחרון ראשון
        history = history[:15]  # שמירת 15 טיסות אחרונות
        self.settings.setValue("flight_history", history)  # כתיבה ל-QSettings
        self.flight_input.clear()  # ניקוי לפני אכלוס מחדש
        for flight in history:
            self.flight_input.addItem(flight)  # אכלוס מחדש בסדר המעודכן

    def fetch_and_draw_flight(self):
        """ שולף מסלול טיסה מ-FlightServer ומצייר אותו על המפה. """
        flight_number = self.flight_input.currentText().strip().upper()  # קריאת מספר הטיסה מה-ComboBox

        if not flight_number:
            self.log_action("לא הוזן מספר טיסה.", is_success=False)
            return

        self.log_action(f"מחפש טיסה: {flight_number}...")
        self.show_flight_button.setEnabled(False)  # נעילת הכפתור למניעת לחיצות כפולות בזמן הבקשה

        try:
            url = f"http://127.0.0.1:5004/flight_route?flight={flight_number}"  # בקשה לשרת הטיסות
            response = requests.get(url, timeout=35)  # FR24 get_flights() יכול לקחת 20+ שניות

            if response.status_code == 200:
                route_data = response.json()  # פירוק תשובת JSON עם נתוני המסלול
                trail_count = len(route_data.get("trail", []))  # מספר נקודות המסלול
                self.log_action(
                    f"נמצאה טיסה {route_data.get('callsign')} — {trail_count} נקודות מסלול",
                    is_success=True
                )
                self._draw_flight_on_map(route_data)  # ציור המסלול על המפה
                self._save_flight_to_history(flight_number)  # שמירה בהיסטוריה
                self.clear_flight_button.setEnabled(True)  # אפשור כפתור ניקוי לאחר הצגה
            else:
                error = response.json().get("error", "שגיאה לא ידועה")
                self.log_action(f"שגיאה בשליפת טיסה: {error}", is_success=False)

        except requests.exceptions.Timeout:
            self.log_action("פסק זמן בחיפוש הטיסה — נסה שנית.", is_success=False)
        except Exception as e:
            self.log_action(f"שגיאה בתקשורת עם FlightServer: {e}", is_success=False)
        finally:
            self.show_flight_button.setEnabled(True)  # שחרור הכפתור בכל מקרה — הצלחה או כישלון

    def _draw_flight_on_map(self, route_data):
        """ מעביר את נתוני המסלול ל-JavaScript ומצייר קו על המפה. """
        import json
        route_json = json.dumps(route_data, ensure_ascii=False)
        js = f"""
(function() {{
    try {{
        drawFlightRoute({route_json});
        'ok';
    }} catch(e) {{
        'ERROR: ' + e.message;
    }}
}})()
"""
        self.map_view.page().runJavaScript(js, self._on_flight_draw_result)

    def _on_flight_draw_result(self, result):
        """ callback מ-JavaScript לאחר ניסיון ציור המסלול. """
        if result and str(result).startswith("ERROR:"):
            self.log_action(f"שגיאת JavaScript בציור הטיסה: {result}", is_success=False)
        elif result == "ok":
            self.log_action("המסלול הוצג על המפה בהצלחה.", is_success=True)

    def clear_flight_route(self):
        """ מוחק את מסלול הטיסה מהמפה דרך JavaScript. """
        self.map_view.page().runJavaScript("clearFlightRoute();")  # קריאה לפונקציית JS לניקוי
        self.clear_flight_button.setEnabled(False)  # נעילת כפתור הניקוי לאחר הניקוי
        self.log_action("מסלול הטיסה הוסר מהמפה.")

    def init_ui(self):
        """ יצירת ממשק המשתמש, כולל כפתורים, תצוגת המפה, ולוגים. """
        self.servers_running = False  # השרתים כבויים בהפעלה ראשונה

        # ── פאנל עליון: כפתורים ושדות קלט ──
        top_layout = QVBoxLayout()  # Layout אנכי לכפתורים ולשדות הקלט
        top_layout.setSpacing(6)  # רווח אחיד של 6px בין כל רכיב
        top_layout.setContentsMargins(8, 10, 8, 6)  # שוליים פנימיים לפאנל הצד

        # ── סעיף: שרתים ──
        lbl_servers = QLabel("שרתים")  # כותרת קבוצת כפתורי השרתים
        lbl_servers.setObjectName("sectionLabel")  # שם לעיצוב QSS
        top_layout.addWidget(lbl_servers)

        # שורת כפתור שרתים + נורות סטטוס
        servers_row = QHBoxLayout()  # Layout אופקי לכפתור ולנורות בשורה אחת
        self.manage_servers_button = QPushButton("הפעל שרתים")  # כפתור הפעלה/עצירת שרתים
        self.manage_servers_button.setFixedSize(140, 34)  # גודל עקבי עם שאר הכפתורים
        self.manage_servers_button.setToolTip("הפעל / עצור את GeoServer ו-WeatherServer")  # tooltip מסביר תפקיד
        self.manage_servers_button.clicked.connect(self.toggle_servers)  # חיבור לפונקציה המנהלת הפעלה/עצירה
        servers_row.addWidget(self.manage_servers_button)

        status_col = QVBoxLayout()  # עמודה אנכית לשתי נורות הסטטוס
        self.geo_status_dot = QLabel("⬤")  # נורת סטטוס GeoServer — ⬤ מעוצב ב-QSS
        self.geo_status_dot.setToolTip("GeoServer")  # tooltip מזהה את השרת
        self.geo_status_dot.setObjectName("dotOff")  # צבע ברירת מחדל: כבוי (QSS)
        self.weather_status_dot = QLabel("⬤")  # נורת סטטוס WeatherServer
        self.weather_status_dot.setToolTip("WeatherServer")  # tooltip מזהה את השרת
        self.weather_status_dot.setObjectName("dotOff")  # צבע ברירת מחדל: כבוי
        status_col.addWidget(self.geo_status_dot)
        status_col.addWidget(self.weather_status_dot)
        servers_row.addLayout(status_col)
        top_layout.addLayout(servers_row)

        self.dashboard_button = QPushButton("📊 דשבורד תהליכים")  # פותח חלון מעקב חי אחר תהליכי השרתים
        self.dashboard_button.setFixedSize(140, 34)  # גודל עקבי עם שאר הכפתורים
        self.dashboard_button.setToolTip("מעקב חי: סטטוס תהליכים, CPU/זיכרון, מטריקות API ויומן")  # tooltip
        self.dashboard_button.clicked.connect(self.open_process_dashboard)  # חיבור לפתיחת הדשבורד
        top_layout.addWidget(self.dashboard_button)

        sep1 = QFrame()  # קו הפרדה חזותי בין הסעיפים
        sep1.setFrameShape(QFrame.HLine)  # קו אופקי
        sep1.setObjectName("separator")  # שם לעיצוב QSS
        top_layout.addWidget(sep1)

        # ── סעיף: מפה ──
        lbl_map = QLabel("מפה")  # כותרת קבוצת כפתורי המפה
        lbl_map.setObjectName("sectionLabel")  # שם לעיצוב QSS
        top_layout.addWidget(lbl_map)

        self.load_map_button = QPushButton("יצירת / איפוס מפה")  # יצירת מפה חדשה או טעינה מחדש
        self.load_map_button.setFixedSize(140, 34)  # גודל עקבי
        self.load_map_button.setEnabled(False)  # נעול עד להפעלת השרתים
        self.load_map_button.setToolTip("יצירת מפה חדשה או איפוס המפה הנוכחית")  # tooltip
        self.load_map_button.clicked.connect(self.create_map_from_file)  # חיבור לפונקציית יצירת המפה
        top_layout.addWidget(self.load_map_button)

        # כפתורי ניווט מהיר במפה
        self.home_button = QPushButton("ישראל")  # חזרה למרכז המפה מעל ישראל
        self.home_button.setFixedSize(140, 34)  # רוחב מלא לאחר הוצאת "נקה סמנים" לאזור המפה
        self.home_button.setToolTip("מרכז את המפה מעל ישראל")  # tooltip
        self.home_button.setEnabled(False)  # נעול עד ליצירת מפה
        self.home_button.clicked.connect(self.center_map_israel)  # חיבור לפונקציית מרכוז
        top_layout.addWidget(self.home_button)

        # clear_markers_button יוצב מתחת למפה — מוגדר כאן, מוסף לתצוגה בהמשך
        self.clear_markers_button = QPushButton("נקה סמנים")
        self.clear_markers_button.setFixedHeight(36)
        self.clear_markers_button.setToolTip("מחיקת כל הסמנים וה-InfoWindows מהמפה")
        self.clear_markers_button.setEnabled(False)
        self.clear_markers_button.clicked.connect(self.clear_map_markers)

        sep2 = QFrame()  # קו הפרדה בין מפה למיקום
        sep2.setFrameShape(QFrame.HLine)  # קו אופקי
        sep2.setObjectName("separator")  # שם לעיצוב QSS
        top_layout.addWidget(sep2)

        # ── סעיף: מיקום ──
        lbl_location = QLabel("מיקום")  # כותרת קבוצת שדות הקלט
        lbl_location.setObjectName("sectionLabel")  # שם לעיצוב QSS
        top_layout.addWidget(lbl_location)

        self.Find_a_location = QPushButton("דקור נ.צ")  # כפתור להצגת/הסתרת שדות הקלט
        self.Find_a_location.setFixedSize(140, 34)  # גודל עקבי
        self.Find_a_location.setToolTip("הזן קואורדינטות או שם עיר כדי לדקור נקודה על המפה")  # tooltip
        self.Find_a_location.setEnabled(False)  # נעול עד ליצירת מפה
        self.Find_a_location.clicked.connect(self.toggle_lat_lon_inputs)  # חיבור להצגת/הסתרת שדות
        top_layout.addWidget(self.Find_a_location)

        # QTabWidget — בוחר בין קואורדינטות לעיר (במקום שתי שיטות גלויות בו-זמנית)
        self.input_tabs = QTabWidget()  # לשוניות בין מצב קואורדינטות למצב עיר
        self.input_tabs.setVisible(False)  # מוסתר עד ללחיצה על "דקור נ.צ"
        self.input_tabs.setFixedHeight(130)  # גובה קבוע כדי שהפאנל לא יקפוץ

        # לשונית קואורדינטות
        coord_tab = QWidget()  # וידג'ט תכולת לשונית קואורדינטות
        coord_layout = QVBoxLayout(coord_tab)  # Layout אנכי בתוך הלשונית
        coord_layout.setContentsMargins(4, 4, 4, 4)  # שוליים צמודים בתוך הלשונית
        self.lat_input = QDoubleSpinBox()  # שדה הזנת קו רוחב
        self.lat_input.setRange(-90, 90)  # תחום תקין לקו רוחב
        self.lat_input.setPrefix("LAT: ")  # תווית מובנית בשדה
        self.lat_input.setDecimals(6)  # דיוק של 6 ספרות עשרוניות
        self.lat_input.setFixedHeight(30)  # גובה עקבי
        self.lat_input.valueChanged.connect(self._restart_debounce)  # הפעלת debounce בכל שינוי ערך
        self.lon_input = QDoubleSpinBox()  # שדה הזנת קו אורך
        self.lon_input.setRange(-180, 180)  # תחום תקין לקו אורך
        self.lon_input.setPrefix("LON: ")  # תווית מובנית בשדה
        self.lon_input.setDecimals(6)  # דיוק של 6 ספרות עשרוניות
        self.lon_input.setFixedHeight(30)  # גובה עקבי
        self.lon_input.valueChanged.connect(self._restart_debounce)  # הפעלת debounce בכל שינוי ערך
        self.save_send_button = QPushButton("שלח")  # כפתור שליחת קואורדינטות מיידית (עוקף debounce)
        self.save_send_button.setFixedHeight(28)  # גובה מותאם ללשונית
        self.save_send_button.clicked.connect(self.save_and_send)  # חיבור לשליחה מיידית
        coord_layout.addWidget(self.lat_input)
        coord_layout.addWidget(self.lon_input)
        coord_layout.addWidget(self.save_send_button)
        self.input_tabs.addTab(coord_tab, "קואורדינטות")  # הוספת לשונית ראשונה

        # לשונית שם עיר
        city_tab = QWidget()  # וידג'ט תכולת לשונית עיר
        city_layout = QVBoxLayout(city_tab)  # Layout אנכי בתוך הלשונית
        city_layout.setContentsMargins(4, 4, 4, 4)  # שוליים צמודים
        self.city_name_input = QComboBox()  # ComboBox עם היסטוריה במקום QLineEdit פשוט
        self.city_name_input.setEditable(True)  # מאפשר הקלדה חופשית
        self.city_name_input.setPlaceholderText("הכנס שם עיר")  # טקסט placeholder
        self.city_name_input.setFixedHeight(30)  # גובה עקבי
        self._load_city_history()  # טעינת ערים אחרונות מ-QSettings
        self.save_send_city_button = QPushButton("שלח")  # כפתור שליחת שם עיר
        self.save_send_city_button.setFixedHeight(28)  # גובה מותאם ללשונית
        self.save_send_city_button.clicked.connect(self.save_and_send_city)  # חיבור לשליחת עיר
        self.city_name_input.lineEdit().returnPressed.connect(self.save_and_send_city)  # Enter שולח ישירות
        city_layout.addWidget(self.city_name_input)
        city_layout.addWidget(self.save_send_city_button)
        self.input_tabs.addTab(city_tab, "עיר")  # הוספת לשונית שנייה
        top_layout.addWidget(self.input_tabs)

        sep3 = QFrame()  # קו הפרדה בין מיקום לכלים
        sep3.setFrameShape(QFrame.HLine)  # קו אופקי
        sep3.setObjectName("separator")  # שם לעיצוב QSS
        top_layout.addWidget(sep3)

        # ── סעיף: כלים ──
        lbl_tools = QLabel("כלים")  # כותרת קבוצת כלי המפה
        lbl_tools.setObjectName("sectionLabel")  # שם לעיצוב QSS
        top_layout.addWidget(lbl_tools)

        self.heatmap_button = QPushButton("שכבת חום")  # הפעלה/כיבוי שכבת HeatMap
        self.heatmap_button.setFixedSize(210, 34)  # גודל מותאם לטקסט הארוך ביותר
        self.heatmap_button.setEnabled(False)  # נעול עד ליצירת מפה
        self.heatmap_button.setCheckable(True)  # מצב דו-כיווני: לחיצה ראשונה מפעילה בחירה, שנייה מוחקת
        self.heatmap_button.setToolTip("לחץ ואז גרור על המפה לבחירת אזור — שכבת חום טמפרטורה ברזולוציה 5 ק\"מ")
        self.heatmap_button.clicked.connect(self.toggle_heatmap)  # חיבור לפונקציית toggle ב-JavaScript
        top_layout.addWidget(self.heatmap_button)

        # Slider לשקיפות מפת החום — שינוי opacity בלי לפגוע בשרתים
        opacity_row = QHBoxLayout()  # שורת Slider + תווית
        opacity_lbl = QLabel("שקיפות:")  # תווית מסבירה את הSlider
        opacity_lbl.setFixedWidth(50)  # רוחב קבוע לתווית
        self.opacity_slider = QSlider(Qt.Horizontal)  # Slider אופקי לשליטה ב-opacity
        self.opacity_slider.setRange(0, 100)  # טווח 0–100 אחוז
        self.opacity_slider.setValue(60)  # ערך ברירת מחדל: 60%
        self.opacity_slider.setEnabled(False)  # נעול עד להפעלת מפת החום
        self.opacity_slider.setToolTip("שליטה בשקיפות שכבת מפת החום")  # tooltip
        self.opacity_slider.valueChanged.connect(self.update_heatmap_opacity)  # שולח opacity ל-JS בכל שינוי
        opacity_row.addWidget(opacity_lbl)
        opacity_row.addWidget(self.opacity_slider)
        top_layout.addLayout(opacity_row)

        # שורת מצב תצוגת טמפרטורה — חום / גריד / נקודות
        temp_mode_row = QHBoxLayout()
        self.temp_mode_heat_btn = QPushButton("חום")
        self.temp_mode_heat_btn.setCheckable(True)
        self.temp_mode_heat_btn.setChecked(True)
        self.temp_mode_heat_btn.setFixedSize(44, 26)
        self.temp_mode_heat_btn.setEnabled(False)
        self.temp_mode_heat_btn.clicked.connect(lambda: self.set_temp_mode('heat'))
        self.temp_mode_grid_btn = QPushButton("גריד")
        self.temp_mode_grid_btn.setCheckable(True)
        self.temp_mode_grid_btn.setFixedSize(44, 26)
        self.temp_mode_grid_btn.setEnabled(False)
        self.temp_mode_grid_btn.clicked.connect(lambda: self.set_temp_mode('grid'))
        self.temp_mode_dots_btn = QPushButton("נקודות")
        self.temp_mode_dots_btn.setCheckable(True)
        self.temp_mode_dots_btn.setFixedSize(52, 26)
        self.temp_mode_dots_btn.setEnabled(False)
        self.temp_mode_dots_btn.clicked.connect(lambda: self.set_temp_mode('dots'))
        temp_mode_row.addWidget(self.temp_mode_heat_btn)
        temp_mode_row.addWidget(self.temp_mode_grid_btn)
        temp_mode_row.addWidget(self.temp_mode_dots_btn)
        top_layout.addLayout(temp_mode_row)

        # שורת כפתורי בחירת נקודות חום ידנית
        heat_pick_row = QHBoxLayout()
        self.heatmap_pick_button = QPushButton("בחר נקודות")
        self.heatmap_pick_button.setFixedSize(90, 30)
        self.heatmap_pick_button.setEnabled(False)
        self.heatmap_pick_button.setToolTip("לחץ על המפה כדי להוסיף נקודות חום ידנית")
        self.heatmap_pick_button.setCheckable(True)
        self.heatmap_pick_button.clicked.connect(self.toggle_heatmap_picker)
        self.heatmap_clear_points_button = QPushButton("נקה")
        self.heatmap_clear_points_button.setFixedSize(44, 30)
        self.heatmap_clear_points_button.setEnabled(False)
        self.heatmap_clear_points_button.setToolTip("נקה את כל נקודות החום שנבחרו")
        self.heatmap_clear_points_button.clicked.connect(self.clear_heatmap_points)
        heat_pick_row.addWidget(self.heatmap_pick_button)
        heat_pick_row.addWidget(self.heatmap_clear_points_button)
        top_layout.addLayout(heat_pick_row)

        self.elevation_button = QPushButton("שכבת גבהים")  # כפתור toggle להפעלה/כיבוי שכבת גבהים
        self.elevation_button.setFixedSize(210, 34)  # גודל מותאם לטקסט הארוך ביותר
        self.elevation_button.setEnabled(False)  # נעול עד ליצירת מפה — אין טעם לטעון גבהים ללא מפה
        self.elevation_button.setCheckable(True)  # כפתור דו-מצבי: לחיצה ראשונה מפעילה, שנייה מכבה
        self.elevation_button.setToolTip("לחץ ואז גרור על המפה לבחירת אזור — כחול=נמוך, אדום=גבוה")  # הסבר ל-tooltip בריחוף
        self.elevation_button.clicked.connect(self.toggle_elevation_layer)  # חיבור לפונקציית הפעלה/כיבוי
        top_layout.addWidget(self.elevation_button)  # הוספת הכפתור לפאנל הכלים

        # שורת מצב תצוגת גבהים — חום / גריד / נקודות
        elev_mode_row = QHBoxLayout()
        self.elev_mode_heat_btn = QPushButton("חום")
        self.elev_mode_heat_btn.setCheckable(True)
        self.elev_mode_heat_btn.setChecked(True)
        self.elev_mode_heat_btn.setFixedSize(44, 26)
        self.elev_mode_heat_btn.setEnabled(False)
        self.elev_mode_heat_btn.clicked.connect(lambda: self.set_elev_mode('heat'))
        self.elev_mode_grid_btn = QPushButton("גריד")
        self.elev_mode_grid_btn.setCheckable(True)
        self.elev_mode_grid_btn.setFixedSize(44, 26)
        self.elev_mode_grid_btn.setEnabled(False)
        self.elev_mode_grid_btn.clicked.connect(lambda: self.set_elev_mode('grid'))
        self.elev_mode_dots_btn = QPushButton("נקודות")
        self.elev_mode_dots_btn.setCheckable(True)
        self.elev_mode_dots_btn.setFixedSize(52, 26)
        self.elev_mode_dots_btn.setEnabled(False)
        self.elev_mode_dots_btn.clicked.connect(lambda: self.set_elev_mode('dots'))
        elev_mode_row.addWidget(self.elev_mode_heat_btn)
        elev_mode_row.addWidget(self.elev_mode_grid_btn)
        elev_mode_row.addWidget(self.elev_mode_dots_btn)
        top_layout.addLayout(elev_mode_row)

        sep_measure = QFrame()
        sep_measure.setFrameShape(QFrame.HLine)
        sep_measure.setObjectName("separator")
        top_layout.addWidget(sep_measure)

        lbl_measure = QLabel("מדידה")
        lbl_measure.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_measure)

        self.ruler_button = QPushButton("📏 מדד מרחק")
        self.ruler_button.setFixedSize(140, 34)
        self.ruler_button.setEnabled(False)
        self.ruler_button.setCheckable(True)
        self.ruler_button.setToolTip('לחץ על המפה להוספת נקודות מדידה — מציג מרחק בק"מ ו-NM')
        self.ruler_button.clicked.connect(self.toggle_ruler)
        top_layout.addWidget(self.ruler_button)

        self.ruler_clear_button = QPushButton("נקה מדידה")
        self.ruler_clear_button.setFixedSize(140, 30)
        self.ruler_clear_button.setEnabled(False)
        self.ruler_clear_button.setToolTip("מחק את קו המדידה מהמפה")
        self.ruler_clear_button.clicked.connect(self.clear_ruler)
        top_layout.addWidget(self.ruler_clear_button)

        sep4 = QFrame()  # קו הפרדה בין כלים לטיסות
        sep4.setFrameShape(QFrame.HLine)  # קו אופקי
        sep4.setObjectName("separator")  # שם לעיצוב QSS
        top_layout.addWidget(sep4)

        # ── סעיף: טיסות ──
        lbl_flights = QLabel("טיסות")  # כותרת סעיף מעקב טיסות
        lbl_flights.setObjectName("sectionLabel")  # שם לעיצוב QSS
        top_layout.addWidget(lbl_flights)

        self.flight_input = QComboBox()  # שדה הזנת מספר טיסה עם היסטוריה
        self.flight_input.setEditable(True)  # מאפשר הקלדה חופשית
        self.flight_input.setPlaceholderText("מס' טיסה — LY001")  # רמז לפורמט
        self.flight_input.setFixedHeight(30)  # גובה עקבי
        self.flight_input.setEnabled(False)  # נעול עד להפעלת שרת הטיסות
        self.flight_input.setToolTip("הכנס מספר טיסה או callsign (לדוגמה: LY001, ELY001)")  # tooltip
        self.flight_input.lineEdit().returnPressed.connect(self.fetch_and_draw_flight)  # Enter מפעיל חיפוש
        self._load_flight_history()  # טעינת מספרי טיסות אחרונים מ-QSettings
        top_layout.addWidget(self.flight_input)

        flight_btn_row = QHBoxLayout()  # שורת כפתורי טיסה
        self.show_flight_button = QPushButton("הצג מסלול")  # כפתור שליפה והצגת המסלול
        self.show_flight_button.setFixedSize(90, 30)  # גודל מותאם לשורה
        self.show_flight_button.setEnabled(False)  # נעול עד להפעלת שרת הטיסות
        self.show_flight_button.setToolTip("שלוף את מסלול הטיסה מ-FlightRadar24 והצג על המפה")  # tooltip
        self.show_flight_button.clicked.connect(self.fetch_and_draw_flight)  # חיבור לפונקציית שליפה
        self.clear_flight_button = QPushButton("נקה")  # כפתור ניקוי המסלול מהמפה
        self.clear_flight_button.setFixedSize(44, 30)  # גודל צר
        self.clear_flight_button.setEnabled(False)  # נעול עד שיש מסלול
        self.clear_flight_button.setToolTip("הסר את מסלול הטיסה מהמפה")  # tooltip
        self.clear_flight_button.clicked.connect(self.clear_flight_route)  # חיבור לניקוי
        flight_btn_row.addWidget(self.show_flight_button)
        flight_btn_row.addWidget(self.clear_flight_button)
        top_layout.addLayout(flight_btn_row)

        top_layout.addStretch()  # דוחף את כל הכפתורים לראש הפאנל — המרחב הפנוי נופל לתחתית

        # ── שורת אייקונים תחתונה ──
        icon_layout = QHBoxLayout()  # Layout אופקי לאייקוני פעמון ושמירה
        self.toggle_log_button = QPushButton()  # כפתור פעמון לפתיחת/סגירת אזור הלוג
        self.toggle_log_button.setFixedSize(28, 28)  # גודל ריבועי
        self.toggle_log_button.setIconSize(QSize(20, 20))  # אייקון קצת קטן מהכפתור
        self.toggle_log_button.setIcon(QIcon(os.path.join("ICONS", "bell_icon.png")))  # אייקון פעמון
        self.toggle_log_button.setToolTip("הצג / הסתר לוגים")  # tooltip
        self.toggle_log_button.clicked.connect(self.toggle_log_view)  # חיבור לפתיחת/סגירת הלוג

        self.badge_label = QLabel("", self.toggle_log_button)  # badge מספרי מעל כפתור הפעמון
        self.badge_label.setObjectName("badge")  # שם לעיצוב QSS (עיגול אדום)
        self.badge_label.setVisible(False)  # מוסתר כשאין לוגים חדשים
        self.badge_label.move(16, 0)  # מיקום badge בפינה הימנית-עליונה של הכפתור

        self.save_log_button = QPushButton()  # כפתור שמירת לוגים לקובץ
        self.save_log_button.setFixedSize(28, 28)  # גודל ריבועי
        self.save_log_button.setIconSize(QSize(20, 20))  # אייקון קצת קטן מהכפתור
        self.save_log_button.setIcon(QIcon(os.path.join("ICONS", "save_log.png")))  # אייקון שמירה
        self.save_log_button.setToolTip("שמור לוגים לקובץ טקסט")  # tooltip
        self.save_log_button.clicked.connect(self.save_logs_to_file)  # חיבור לשמירת הלוגים

        self.clear_log_button = QPushButton("נקה")  # כפתור ניקוי לוגים מהתצוגה
        self.clear_log_button.setFixedSize(40, 28)  # רוחב מצומצם
        self.clear_log_button.setToolTip("נקה את תצוגת הלוגים")  # tooltip
        self.clear_log_button.clicked.connect(self.clear_logs)  # חיבור לניקוי

        icon_layout.addWidget(self.toggle_log_button)
        icon_layout.addWidget(self.save_log_button)
        icon_layout.addWidget(self.clear_log_button)
        icon_layout.addStretch()  # דוחף את האייקונים לצד שמאל
        top_layout.addLayout(icon_layout)

        # ── אזור לוגים ──
        self.log_area = QTextEdit()  # תיבת טקסט להצגת הלוגים הצבועים
        self.log_area.setReadOnly(True)  # מונע עריכה ידנית של הלוגים
        self.log_area.setVisible(False)  # מוסתר עד ללחיצה על הפעמון
        self.log_area.setMinimumHeight(80)  # גובה מינימלי כשמוצג
        self.log_area.setMaximumHeight(220)  # גובה מקסימלי — מונע כיסוי הכפתורים

        # ── פאנל צד: Splitter אנכי בין כפתורים ללוגים ──
        panel_splitter = QSplitter(Qt.Vertical)  # מאפשר למשתמש לגרור ולשנות גובה הלוג
        top_widget = QWidget()  # וידג'ט עוטף לחלק העליון של הפאנל
        top_widget.setLayout(top_layout)  # חיבור ה-Layout לוידג'ט
        panel_splitter.addWidget(top_widget)  # חלק עליון: כפתורים
        panel_splitter.addWidget(self.log_area)  # חלק תחתון: לוגים
        panel_splitter.setSizes([1, 0])  # לוג סגור בהתחלה — גובה 0
        panel_splitter.setCollapsible(1, True)  # ניתן לכווץ את אזור הלוג לאפס
        self.panel_splitter = panel_splitter  # שמירת הפניה לניהול פתיחה/סגירה

        button_widget = QWidget()  # וידג'ט חיצוני לפאנל הצד כולו
        button_widget.setLayout(QVBoxLayout())  # Layout עוטף
        button_widget.layout().setContentsMargins(0, 0, 0, 0)  # ביטול שוליים כפולים
        button_widget.layout().addWidget(panel_splitter)  # הכנסת ה-Splitter לפאנל
        button_widget.setMinimumWidth(165)  # רוחב מינימלי שמבטיח קריאות הכפתורים

        # ── Layout ראשי: מפה + פאנל צד ──
        main_layout = QHBoxLayout()  # Layout ראשי אופקי

        # ── עטיפת המפה + כפתור "נקה סמנים" מורחב מתחתיה ──
        map_container = QWidget()
        map_vbox = QVBoxLayout(map_container)
        map_vbox.setContentsMargins(0, 0, 0, 0)
        map_vbox.setSpacing(0)
        map_vbox.addWidget(self.map_view)
        map_vbox.addWidget(self.clear_markers_button)

        self.splitter = QSplitter(Qt.Horizontal)  # Splitter בין המפה לפאנל הצד
        self.splitter.addWidget(map_container)  # המפה + כפתור ניקוי בצד שמאל
        self.splitter.addWidget(button_widget)  # הפאנל בצד ימין
        self.splitter.setSizes([1110, 170])  # חלוקה ראשונית: מפה רחבה, פאנל קבוע
        self.splitter.setCollapsible(1, False)  # מונע כיסוי מוחלט של הפאנל

        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # המפה מתרחבת לכל השטח הפנוי

        main_layout.addWidget(self.splitter)  # הוספת ה-Splitter ל-Layout הראשי
        main_layout.setContentsMargins(0, 0, 0, 0)  # ביטול שוליים חיצוניים

        container = QWidget()  # וידג'ט מרכזי שעוטף את כל הממשק
        container.setLayout(main_layout)  # חיבור ה-Layout המרכזי
        self.setCentralWidget(container)  # קביעת הוידג'ט המרכזי לחלון

        # ── Status bar ──
        self.statusBar().showMessage("מוכן")  # הודעת סטטוס ראשונית בתחתית החלון

        # ── QSS Stylesheet ──
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial;
                font-size: 13px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 3px 8px;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:disabled { background-color: #1e1e2e; color: #585b70; border-color: #313244; }
            QPushButton:pressed { background-color: #585b70; }
            QPushButton:checked { background-color: #89b4fa; color: #1e1e2e; border-color: #89b4fa; font-weight: bold; }
            QLabel#sectionLabel {
                color: #89b4fa;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 0px;
            }
            QFrame#separator { color: #313244; }
            QTextEdit {
                background-color: #181825;
                color: #a6e3a1;
                border: 1px solid #313244;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QDoubleSpinBox, QLineEdit, QComboBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QTabWidget::pane { border: 1px solid #313244; background-color: #1e1e2e; }
            QTabBar::tab {
                background-color: #313244;
                color: #cdd6f4;
                padding: 4px 10px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected { background-color: #45475a; color: #89b4fa; }
            QSlider::groove:horizontal {
                height: 4px;
                background: #313244;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSplitter::handle { background-color: #313244; }
            QStatusBar { background-color: #181825; color: #6c7086; font-size: 11px; }
            QLabel#dotOff  { color: #585b70; font-size: 10px; }
            QLabel#dotOn   { color: #a6e3a1; font-size: 10px; }
            QLabel#badge {
                background-color: #f38ba8;
                color: white;
                border-radius: 7px;
                font-size: 9px;
                min-width: 14px;
                min-height: 14px;
                padding: 0px 2px;
            }
        """)


    def create_map_from_file(self):
        """ יצירת המפה בפעם הראשונה, או איפוס מצב המפה בלחיצות הבאות ללא טעינה מחדש. """
        if not self._map_created:
            self.log_action("יצירת המפה התחילה.")
            create_map()
            self.load_map()
            self._map_created = True
            self.log_action("המפה נוצרה בהצלחה.", is_success=True)
            self.Find_a_location.setEnabled(True)
            self.home_button.setEnabled(True)
            self.clear_markers_button.setEnabled(True)
            self.heatmap_button.setEnabled(True)
            self.heatmap_pick_button.setEnabled(True)
            self.elevation_button.setEnabled(True)
            self.ruler_button.setEnabled(True)
            self.opacity_slider.setEnabled(True)
            if not getattr(self, '_title_connected', False):
                self.map_view.titleChanged.connect(self._on_title_changed)
                self._title_connected = True
        else:
            self.log_action("איפוס המפה...")
            self.map_view.page().runJavaScript("resetMapState();")
            self._reset_layer_buttons()
            self.log_action("המפה אופסה — כל השכבות נוקו.", is_success=True)

    def _reset_layer_buttons(self):
        """ מאפס את מצב כל כפתורי השכבות לברירת המחדל שלהם. """
        self.heatmap_button.setChecked(False)
        self.heatmap_button.setText("שכבת חום")
        self.elevation_button.setChecked(False)
        self.elevation_button.setText("שכבת גבהים")
        self.heatmap_pick_button.setChecked(False)
        self.heatmap_pick_button.setText("בחר נקודות")
        self.heatmap_clear_points_button.setEnabled(False)
        for btn in (self.temp_mode_heat_btn, self.temp_mode_grid_btn, self.temp_mode_dots_btn):
            btn.setEnabled(False)
        self.temp_mode_heat_btn.setChecked(True)
        self.temp_mode_grid_btn.setChecked(False)
        self.temp_mode_dots_btn.setChecked(False)
        for btn in (self.elev_mode_heat_btn, self.elev_mode_grid_btn, self.elev_mode_dots_btn):
            btn.setEnabled(False)
        self.elev_mode_heat_btn.setChecked(True)
        self.elev_mode_grid_btn.setChecked(False)
        self.elev_mode_dots_btn.setChecked(False)

    def load_map(self):
        """ טעינת המפה לתוך תצוגת QWebEngineView. """
        if os.path.exists(self.map_file):  # בדיקה שהקובץ אכן נוצר
            self.map_view.setUrl(QUrl.fromLocalFile(self.map_file))  # טעינת הקובץ בנתיב מוחלט
            self.log_action("המפה נטענה בהצלחה.", is_success=True)

            def _sync_servers(ok):
                self.map_view.loadFinished.disconnect(_sync_servers)
                if self.servers_running:
                    self.map_view.page().runJavaScript("window.serversRunning = true;")
            self.map_view.loadFinished.connect(_sync_servers)
        else:
            self.log_action("שגיאה: קובץ המפה לא נמצא.", is_success=False)

    def toggle_servers(self):
        """ ניהול הפעלת וכיבוי השרתים בכפתור אחד """
        if self.servers_running:
            self.stop_servers()  # עצירת שני השרתים
            self.servers_running = False  # עדכון מצב פנימי
            self.manage_servers_button.setText("הפעל שרתים")  # עדכון טקסט הכפתור
            self.manage_servers_button.setStyleSheet("background-color: #e64553; color: white; font-weight: bold;")  # אדום — שרתים כבויים
        else:
            self.start_servers()  # הפעלת שני השרתים
            self.servers_running = True  # עדכון מצב פנימי
            self.manage_servers_button.setText("עצור שרתים")  # עדכון טקסט הכפתור
            self.manage_servers_button.setStyleSheet("background-color: #40a02b; color: white; font-weight: bold;")  # ירוק — שרתים פעילים

    def start_servers(self):
        """ הפעלת שרתי GeoServer ו-WeatherServer. """
        try:
            self.log_action("הפעלת GeoServer התחילה.")
            self.geo_server_process = subprocess.Popen([sys.executable, "geo_server.py"])  # הפעלת GeoServer בתהליך נפרד
            self.log_process_action("GeoServer", "הפעלת", success=True)
            self.geo_status_dot.setObjectName("dotOn")  # נורת סטטוס ירוקה — GeoServer פעיל
            self.geo_status_dot.setStyle(self.geo_status_dot.style())  # רענון QSS לאחר שינוי objectName
        except Exception as e:
            self.log_process_action("GeoServer", "הפעלת", success=False)
            self.log_action(f"שגיאה בהפעלת GeoServer: {e}", is_success=False)

        try:
            self.log_action("הפעלת WeatherServer התחילה.")
            self.weather_server_process = subprocess.Popen([sys.executable, "weather_server.py"])  # הפעלת WeatherServer בתהליך נפרד
            self.log_action("WeatherServer הופעל בהצלחה.", is_success=True)
            self.weather_status_dot.setObjectName("dotOn")  # נורת סטטוס ירוקה — WeatherServer פעיל
            self.weather_status_dot.setStyle(self.weather_status_dot.style())  # רענון QSS
        except Exception as e:
            self.log_action(f"שגיאה בהפעלת WeatherServer: {e}", is_success=False)

        try:
            self.log_action("הפעלת FlightServer התחילה.")
            self.flight_server_process = subprocess.Popen([sys.executable, "flight_server.py"])  # הפעלת שרת הטיסות על פורט 5004
            self.log_action("FlightServer הופעל בהצלחה.", is_success=True)
            self.flight_input.setEnabled(True)  # אפשור שדה מספר הטיסה לאחר הפעלת השרת
            self.show_flight_button.setEnabled(True)  # אפשור כפתור הצגת מסלול
        except Exception as e:
            self.log_action(f"שגיאה בהפעלת FlightServer: {e}", is_success=False)

        self.map_view.page().runJavaScript("window.serversRunning = true;")  # עדכון JS שהשרתים פעילים
        self.load_map_button.setEnabled(True)  # אפשור יצירת מפה לאחר הפעלת השרתים
        if self._map_created:  # אם המפה כבר נוצרה בעבר, יש לשחזר כפתורים שנעלו ע"י stop_servers
            self.Find_a_location.setEnabled(True)  # שחזור נעילת דקירת נ.צ
            self.heatmap_button.setEnabled(True)  # שחזור נעילת שכבת חום
            self.opacity_slider.setEnabled(True)  # שחזור נעילת ה-slider

    @staticmethod
    def _terminate_process_tree(proc):
        """ עוצר תהליך + כל צאצאיו. השרת נפתח דרך python.exe של virtualenv (launcher stub
        שמבצע re-exec) ודרך reloader של Flask debug=True — שתי שכבות שכל אחת מוסיפה תהליך-בן.
        terminate() על ה-PID הנשמר בלבד משאיר את הצאצאים חיים ותופסים את הפורט, כך שהשרת
        בפועל ממשיך לרוץ גם אחרי "עצירה" והפעלה חוזרת עלולה להיכשל על פורט תפוס. """
        try:
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        if children:
            _, alive = psutil.wait_procs(children, timeout=3)
            for child in alive:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    def stop_servers(self):
        """ עצירת שרתי GeoServer ו-WeatherServer. """
        try:
            if self.geo_server_process:  # עצירה רק אם התהליך קיים
                self._terminate_process_tree(self.geo_server_process)  # עצירת התהליך וכל צאצאיו
                self.geo_server_process = None  # ניקוי הפניה
                self.log_action("GeoServer נעצר בהצלחה.", is_success=True)
                self.geo_status_dot.setObjectName("dotOff")  # נורה אפורה — כבוי
                self.geo_status_dot.setStyle(self.geo_status_dot.style())  # רענון QSS
            if self.weather_server_process:  # עצירה רק אם התהליך קיים
                self._terminate_process_tree(self.weather_server_process)  # עצירת התהליך וכל צאצאיו
                self.weather_server_process = None  # ניקוי הפניה
                self.log_action("WeatherServer נעצר בהצלחה.", is_success=True)
                self.weather_status_dot.setObjectName("dotOff")  # נורה אפורה — כבוי
                self.weather_status_dot.setStyle(self.weather_status_dot.style())  # רענון QSS
            if self.flight_server_process:  # עצירה רק אם התהליך קיים
                self._terminate_process_tree(self.flight_server_process)  # עצירת התהליך וכל צאצאיו
                self.flight_server_process = None  # ניקוי הפניה
                self.log_action("FlightServer נעצר בהצלחה.", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בעצירת השרתים: {e}", is_success=False)
        self.map_view.page().runJavaScript("window.serversRunning = false;")  # עדכון JS שהשרתים כבויים
        self.load_map_button.setEnabled(False)  # נעילת יצירת מפה
        self.Find_a_location.setEnabled(False)  # נעילת דקירת נ.צ
        self.heatmap_button.setEnabled(False)  # נעילת שכבת חום
        self.opacity_slider.setEnabled(False)  # נעילת Slider
        self.show_flight_button.setEnabled(False)  # נעילת כפתור הצגת מסלול
        self.flight_input.setEnabled(False)  # נעילת שדה מספר הטיסה

    def save_and_send(self):
        """ שמור ושלח את נתוני ה-LAT ו-LON """
        lat = self.lat_input.value()  # קריאת קו רוחב מה-SpinBox
        lon = self.lon_input.value()  # קריאת קו אורך מה-SpinBox
        self.log_action("הנתונים נשמרו ונשלחו")

        if lat == 0 or lon == 0:  # ולידציה בסיסית — 0,0 לא מיקום תקין
            self.log_action("נתוני קואורדינטות אינם תקינים.", is_success=False)
            return

        message = {"lat": lat, "lon": lon}  # מבנה ההודעה לשמירה ולשליחה

        try:
            with open("coordinates_log.txt", "a") as log_file:  # שמירה לקובץ לוג קואורדינטות
                log_file.write(f"{message}\n")
            self.log_action(f"מבנה ההודעה נשמר: {message}", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בשמירת מבנה ההודעה: {e}", is_success=False)
            return

        try:
            url = f"http://127.0.0.1:5002/weather?lat={lat}&lon={lon}"  # בניית URL עם פרמטרים נפרדים
            response = requests.get(url)  # שליחת בקשת GET לשרת מזג האוויר

            if response.status_code == 200:
                weather_data = response.json()  # פירוק תשובת JSON
                self.log_action(f"נתוני מזג האוויר התקבלו: {weather_data}", is_success=True)
                self.display_weather_on_map(lat, lon, weather_data)  # הצגה על המפה
            else:
                self.log_action(f"שגיאה בשליחת הבקשה: {response.status_code}", is_success=False)
        except Exception as e:
            self.log_action(f"שגיאה בשליחת ההודעה לשרת: {e}", is_success=False)

    def toggle_lat_lon_inputs(self):
        """ הצגת או הסתרת לשוניות הקלט (קואורדינטות / עיר) """
        is_visible = not self.input_tabs.isVisible()  # toggle מצב הlשוניות
        self.input_tabs.setVisible(is_visible)  # הצגה/הסתרה של ה-QTabWidget

        # חיבור/ניתוק submit_coordinates לפי מצב התצוגה
        if is_visible:
            self.Find_a_location.clicked.connect(self.submit_coordinates)  # חיבור בפתיחת הלשוניות
            self.log_action("בוצע חיבור לפונקציה לדקירת נ.צ.")
        else:
            try:
                self.Find_a_location.clicked.disconnect(self.submit_coordinates)  # ניתוק submit_coordinates בלבד — לא ניתוק toggle_lat_lon_inputs
            except TypeError:
                pass  # disconnect זורק TypeError אם הסיגנל לא היה מחובר — בטוח להתעלם
            self.log_action("בוצע ניתוק מפונקציה לדקירת נ.צ.")

    def save_and_send_city(self):
        """ שמור ושלח את שם העיר """
        city_name = self.city_name_input.currentText().strip()  # קריאת הטקסט הנוכחי מה-ComboBox
        self.log_action("הוקלד ונשלח שם של עיר")

        if not city_name:
            self.log_action("שם העיר אינו תקין.", is_success=False)
            return

        self._save_city_to_history(city_name)  # שמירת העיר בהיסטוריה ל-QSettings ולComboBox

        try:
            with open("city_log.txt", "a", encoding="utf-8") as log_file:  # שמירת לוג ערים עם תמיכה בעברית
                log_file.write(f"City: {city_name}\n")
            self.log_action(f"שם העיר נשמר: {city_name}", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בשמירת שם העיר: {e}", is_success=False)
            return

        # קידוד שם העיר ל-URL
        encoded_city_name = urllib.parse.quote(city_name)

        # שליחת הבקשה לשרת
        try:
            url = f"http://127.0.0.1:5002/weather?region={encoded_city_name}"
            response = requests.get(url)

            if response.status_code == 200:
                weather_data = response.json()
                self.log_action(f"נתוני מזג האוויר התקבלו: {weather_data}")
                # הצגת נתונים על המפה
                lat = weather_data.get("latitude")
                lon = weather_data.get("longitude")
                if lat and lon:
                    self.display_weather_on_map(lat, lon, weather_data)
                else:
                    self.log_action(f"לא התקבלו קואורדינטות עבור העיר {city_name}")
            else:
                self.log_action(f"שגיאה בשליחת הבקשה לשרת: {response.status_code}")
        except Exception as e:
            self.log_action(f"שגיאה בשליחת הבקשה לשרת: {e}")

    def enable_heatmap_layer(self):
        """
        מפעיל שכבת חום על המפה
        """
        QMessageBox.information(self, "שכבת חום", "שכבת חום נוספה למפה.")

    def toggle_log_view(self):
        """ פתיחה / סגירה של אזור הלוגים דרך ניהול ה-Splitter. """
        if self.log_area.isVisible():
            self.log_area.setVisible(False)
            self.panel_splitter.setSizes([1, 0])
        else:
            self.log_area.setVisible(True)
            self.panel_splitter.setSizes([1, 160])  # פתיחה בגובה 160px
            self.unread_log_count = 0
            self.badge_label.setVisible(False)
            sb = self.log_area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _register_heatmap_bridge(self):
        """ רושם callback מ-JS שיעדכן את טקסט הכפתור כשמפת החום נטענה. """
        self.map_view.page().runJavaScript("""
            window.pyBridge = window.pyBridge || {};
            window.pyBridge.onHeatmapLoaded = function() {
                document.title = '__heatmap_loaded__';
            };
        """)

    def _on_title_changed(self, title):
        if title.startswith('__jserror__:'):
            logging.error(f"JS error: {title[len('__jserror__:'):]}")
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
            return
        if title == '__heatmap_computing__':
            self.heatmap_button.setText("מחשב מפה")
        elif title == '__heatmap_loaded__':
            self.heatmap_button.setText("נקה שכבה")
            for btn in (self.temp_mode_heat_btn, self.temp_mode_grid_btn, self.temp_mode_dots_btn):
                btn.setEnabled(True)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
        elif title == '__heatmap_error__':
            self.heatmap_button.setChecked(False)
            self.heatmap_button.setText("שכבת חום")
            self.log_action("שגיאה בטעינת נתוני טמפרטורה — בדוק חיבור רשת", is_success=False)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
        elif title == '__heatmap_edit_error__':
            self.log_action("שגיאה בעדכון נתוני טמפרטורה — הנתונים הקודמים נשמרו", is_success=False)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
        elif title == '__elev_computing__':
            self.elevation_button.setText("מחשב מפה")
        elif title == '__elev_loaded__':
            self.elevation_button.setText("נקה שכבה")
            for btn in (self.elev_mode_heat_btn, self.elev_mode_grid_btn, self.elev_mode_dots_btn):
                btn.setEnabled(True)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
        elif title == '__elev_error__':
            self.elevation_button.setChecked(False)
            self.elevation_button.setText("שכבת גבהים")
            self.log_action("שגיאה בטעינת נתוני גבהים — בדוק חיבור רשת", is_success=False)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")
        elif title == '__los_loading__':
            # JS שלח איתות — החישוב החל, השרת שולף נתוני גובה מ-open-meteo
            self.log_action("מחשב קו ראייה — שולף נתוני גובה...")
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")  # איפוס הכותרת למניעת הפעלה חוזרת
        elif title == '__los_loaded__':
            # JS שלח איתות — החישוב הסתיים בהצלחה, הגרף והקווים מוצגים
            self.log_action("קו ראייה חושב בהצלחה", is_success=True)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")  # איפוס הכותרת
        elif title == '__los_error__':
            # JS שלח איתות — החישוב נכשל (בעיית רשת או שגיאת שרת)
            self.log_action("שגיאה בחישוב קו ראייה — בדוק חיבור רשת", is_success=False)
            self.map_view.page().runJavaScript("document.title = 'מפת Leaflet משולבת';")

    def toggle_heatmap(self):
        if self.heatmap_button.isChecked():
            self.heatmap_button.setText("בחר איזור ליצירת השכבה")
            self.log_action("גרור מלבן על המפה לבחירת אזור טמפרטורה")
            self._register_heatmap_bridge()
            self.map_view.page().runJavaScript("clearTempHeatmap(); startTempHeatmap();")
        else:
            self.heatmap_button.setText("שכבת חום")
            self.map_view.page().runJavaScript("clearTempHeatmap();")
            for btn in (self.temp_mode_heat_btn, self.temp_mode_grid_btn, self.temp_mode_dots_btn):
                btn.setEnabled(False)

    def toggle_heatmap_picker(self, checked):
        self.map_view.page().runJavaScript("startHeatmapPicker();")
        if checked:
            self.heatmap_pick_button.setText("סיים בחירה")
            self.heatmap_clear_points_button.setEnabled(True)
            self.log_action("מצב בחירת נקודות חום פעיל — לחץ על המפה להוספת נקודות")
        else:
            self.heatmap_pick_button.setText("בחר נקודות")
            self.log_action("מצב בחירת נקודות חום כובה")

    def clear_heatmap_points(self):
        self.map_view.page().runJavaScript("clearHeatmapPoints();")
        self.log_action("נקודות מפת החום נמחקו")

    def toggle_ruler(self, checked):
        self.map_view.page().runJavaScript("toggleRuler();")
        if checked:
            self.ruler_button.setText("לחץ על המפה לנקודה...")
            self.ruler_clear_button.setEnabled(True)
            self.log_action("מצב מדידת מרחק הופעל — לחץ על המפה להוספת נקודות")
        else:
            self.ruler_button.setText("📏 מדד מרחק")

    def clear_ruler(self):
        self.map_view.page().runJavaScript("clearRuler();")
        self.ruler_button.setChecked(False)
        self.ruler_button.setText("📏 מדד מרחק")
        self.ruler_clear_button.setEnabled(False)
        self.log_action("קו המדידה נמחק")

    def set_elev_mode(self, mode):
        self.elev_mode_heat_btn.setChecked(mode == 'heat')
        self.elev_mode_grid_btn.setChecked(mode == 'grid')
        self.elev_mode_dots_btn.setChecked(mode == 'dots')
        self.map_view.page().runJavaScript(f"setElevMode('{mode}');")

    def set_temp_mode(self, mode):
        self.temp_mode_heat_btn.setChecked(mode == 'heat')
        self.temp_mode_grid_btn.setChecked(mode == 'grid')
        self.temp_mode_dots_btn.setChecked(mode == 'dots')
        self.map_view.page().runJavaScript(f"setTempMode('{mode}');")

    def toggle_elevation_layer(self, checked):
        """ הפעלה/כיבוי שכבת גבהים — לחיצה ראשונה פותחת מצב בחירת אזור. """
        self.map_view.page().runJavaScript("toggleElevationLayer();")
        if checked:
            self.elevation_button.setText("בחר איזור ליצירת השכבה")
            self.log_action("גרור מלבן על המפה לבחירת אזור גבהים")
        else:
            self.elevation_button.setText("שכבת גבהים")
            self.log_action("שכבת גבהים כובתה")
            for btn in (self.elev_mode_heat_btn, self.elev_mode_grid_btn, self.elev_mode_dots_btn):
                btn.setEnabled(False)

    def save_logs_to_file(self):
        """ שמירה של הלוגים לקובץ טקסט במערכת הקבצים. """
        options = QFileDialog.Options()  # יצירת חלון שמירה
        file_path, _ = QFileDialog.getSaveFileName(self, "שמור לוגים לקובץ", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:  # אם נבחר קובץ לשמירה
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    for log in self.logs:  # כתיבת הלוגים לקובץ
                        f.write(log + "\n")
                self.log_action(f"לוגים נשמרו בהצלחה ב-{file_path}")
            except Exception as e:
                self.log_action(f"שגיאה בשמירת הלוגים: {e}")

    def submit_coordinates(self):
        """שליחת הקואורדינטות כדי לקבל נתוני מזג אוויר ולתעד את הפעולה"""
        # קבלת קואורדינטות מהשדות
        lat = self.lat_input.value()
        lon = self.lon_input.value()

        # תיעוד שליחת הקואורדינטות
        self.log_action(f"שליחה של קואורדינטות: LAT={lat}, LON={lon}")

        # בדיקת cache — אם כבר שלפנו נתונים לקואורדינטות אלו לאחרונה, לא נשלח בקשה חוזרת
        cache_key = (round(lat, 3), round(lon, 3))  # דיוק 3 ספרות — הבדל של פחות מ-100 מ' נחשב זהה
        cached = self.weather_cache.get(cache_key)
        if cached:
            weather_data, _ = cached
            self.log_action(f"נתוני מזג האוויר נטענו מה-cache עבור {cache_key}")
        else:
            # שליחת בקשה ישירה לשרת עם lat ו-lon כפרמטרים נפרדים — לא כשם עיר
            try:
                url = f"http://127.0.0.1:5002/weather?lat={lat}&lon={lon}"
                response = requests.get(url, timeout=10)
                weather_data = response.json() if response.status_code == 200 else {}
                if weather_data:
                    self.weather_cache[cache_key] = (weather_data, datetime.now())  # שמירה ב-cache
            except Exception as e:
                self.log_action(f"שגיאה בשליחת בקשה לשרת: {e}", is_success=False)
                weather_data = {}

        # אם התקבלה תשובה מהשרת
        if weather_data:
            self.log_action(f"נתוני מזג האוויר התקבלו: {weather_data}")

            # קבלת הקואורדינטות מהתשובה — WeatherServer מחזיר latitude/longitude (לא coord)
            res_lat = weather_data.get("latitude")
            res_lon = weather_data.get("longitude")

            # בדיקה אם הקואורדינטות התקבלו
            if res_lat is not None and res_lon is not None:
                self.display_weather_on_map(res_lat, res_lon, weather_data)
            else:
                self.log_action(f"לא התקבלו קואורדינטות בתשובת השרת", is_success=False)
        else:
            # תיעוד כישלון בקבלת נתונים
            self.log_action(f"לא הצלחנו לקבל נתוני מזג אוויר עבור LAT={lat}, LON={lon}", is_success=False)

    def display_weather_on_map(self, lat, lon, weather_data):
        """
         פונקציה להצגת נתוני מזג האוויר והוספת גבולות העיר על המפה.
         :param lat: קו רוחב של המיקום המרכזי
         :param lon: קו אורך של המיקום המרכזי
         :param weather_data: נתוני מזג האוויר שהתקבלו מהשרת
         """
        try:
            # שליפת גובה פני השטח — נדרש לפני בניית ה-JS כי ה-popup נבנה ב-Python
            elevation_text = "לא זמין"
            try:
                elev_response = requests.post(
                    "http://127.0.0.1:5002/elevation",
                    json={"locations": [{"latitude": lat, "longitude": lon}]},
                    timeout=5
                )
                if elev_response.status_code == 200:
                    elev_results = elev_response.json().get("results", [])
                    if elev_results:
                        elevation_text = f"{elev_results[0]['elevation']} מ'"
            except Exception:
                pass  # כשל בגובה לא מונע הצגת מזג אוויר

            # הכנת טקסט להצגה על גבי הסמן
            weather_info = f"Temperature: {weather_data['temperature']}°C, Weather: {weather_data['weather']}"

            # רישום בלוג של נתוני מזג האוויר שמוצגים
            self.log_action(f"מציג מזג אוויר: {weather_info}")

            # קוד JavaScript להצגת סמן Leaflet במיקום המרכזי
            js_code_marker = f"""
             var marker = L.marker([{lat}, {lon}]).addTo(map);  /* Leaflet: [lat, lng] */
             allMarkers.push(marker);  /* רישום לניקוי עתידי */
             marker.bindPopup(
                 "קו רוחב: {lat}, קו אורך: {lon}<br>מזג אוויר: {weather_data['weather']}<br>טמפרטורה: {weather_data['temperature']}°C<br>גובה: {elevation_text}"
             ).openPopup();  /* קישור ופתיחת Popup מיידית */
             """
            #הרצת קוד ה-JavaScript להצגת הסמן על המפה
            # הרצת קוד ה-JavaScript להצגת הסמן על המפה
            self.map_view.page().runJavaScript(js_code_marker)

            # בדיקה אם נתוני גבולות העיר קיימים בתגובה
            boundary = weather_data.get("boundary")
            if boundary:
                # שליפת נתוני הנקודות הצפונית-מזרחית והדרומית-מערבית
                ne = boundary["northeast"]
                sw = boundary["southwest"]

                # קוד JavaScript ליצירת מלבן Leaflet שמייצג את גבולות העיר
                js_code_polygon = f"""
                        var cityRect = L.rectangle(
                            [[{sw['lat']}, {sw['lng']}], [{ne['lat']}, {ne['lng']}]],
                            {{
                                color:       '#FF0000',  /* צבע קו המסגרת */
                                weight:      2,          /* עובי הקו */
                                opacity:     0.8,        /* שקיפות הקו */
                                fillColor:   '#FF0000',  /* צבע המילוי */
                                fillOpacity: 0.25        /* שקיפות המילוי */
                            }}
                        ).addTo(map);
                        allMarkers.push(cityRect);  /* רישום לניקוי עתידי */
                        """
                # הרצת קוד ה-JavaScript להצגת המלבן על המפה
                self.map_view.page().runJavaScript(js_code_polygon)

                # תיעוד בלוג שגבולות העיר סומנו בהצלחה
                self.log_action("גבולות העיר סומנו בהצלחה.")
            else:
                # תיעוד בלוג במקרה שנתוני הגבולות לא נמצאו
                self.log_action("גבולות העיר לא נמצאו.")
        except Exception as e:
            # טיפול בשגיאה ותיעוד בלוג
            self.log_action(f"שגיאה בהצגת המידע על המפה: {e}")

    def fetch_weather_data(self, location):
        """ שולחת בקשה לשרת ה-API לקבלת נתוני מזג אוויר עבור מיקום נתון """
        try:
            # בדוק שהפרמטרים נכונים
            print(f"שליחת בקשה לשרת עבור המיקום: {location}")

            url = f"http://127.0.0.1:5002/weather?region={location}"
            response = requests.get(url)

            # מדפיס את התשובה שהתקבלה לצורך ניתוח שגיאות
            print(f"סטטוס הבקשה: {response.status_code}")

            if response.status_code == 200:
                return response.json()  # החזרת הנתונים אם הם תקינים
            else:
                print(f"שגיאה בקבלת מזג האוויר עבור {location}, סטטוס: {response.status_code}")
                return None  # במקרה של שגיאה
        except Exception as e:
            # טיפול בשגיאות
            print(f"שגיאה בתקשורת עם שרת ה-API: {e}")
            return None  # במקרה של שגיאה

    def closeEvent(self, event):
        """ טיפול בסגירת היישום. """
        self.stop_servers()  # עצירת השרתים לפני סגירת היישום
        self.log_action("היישום נסגר.")  # רישום סגירת היישום בלוגים
        event.accept()  # קבלת האירוע וסגירת היישום



if __name__ == "__main__":
    app = QApplication(sys.argv)  # יצירת אובייקט אפליקציה
    gui = MapApp()  # יצירת אובייקט של הממשק הגרפי
    gui.show()  # הצגת הממשק
    sys.exit(app.exec_())  # הרצת לולאת האירועים של PyQt
