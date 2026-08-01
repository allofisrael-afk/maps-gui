import html  # נדרש ל-html.escape() — מניעת XSS בתוכן פופאפים
import json
import logging
import os
import subprocess
import sys
import urllib.parse
import requests
from datetime import datetime
from MAP import create_map
from PyQt5.QtCore import Qt, QUrl, QDateTime, QSize, QTimer, QPropertyAnimation, QEasingCurve, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout,
    QTextEdit, QFileDialog, QSplitter, QSizePolicy, QDoubleSpinBox,
    QMessageBox, QLabel, QTabWidget, QSlider, QComboBox, QFrame
)
from PyQt5.QtCore import QSettings
from apipyqt import fetch_weather_data

# BASE_DIR — תיקיית הקובץ הנוכחי (main.py).
# שימוש ב-__file__ במקום ספריית העבודה הנוכחית (CWD) מבטיח שכל
# קבצי הלוג ייווצרו תמיד לצד הקובץ הזה, בלי תלות ממיקום ההרצה.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    # os.path.join + BASE_DIR — נתיב מוחלט, לא יחסי ל-CWD
    filename=os.path.join(BASE_DIR, 'app_combined.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

MAX_LOG_LINES = 500

class LocationWorker(QThread):
    location_found = pyqtSignal(float, float, str, str)  # lat, lon, label, source ('gps'/'ip')
    location_error = pyqtSignal(str)

    def run(self):
        errors = []

        # 1. נסה GPS דרך Windows Location API (WinRT)
        try:
            lat, lon, accuracy = self._try_winrt_gps()
            label = f"{lat:.5f}, {lon:.5f}  (דיוק ≈{accuracy:.0f}מ')"
            self.location_found.emit(lat, lon, label, 'gps')
            return
        except Exception as e:
            errors.append(f"GPS: {e}")

        # 2. גיבוי: גיאו-לוקיישן לפי IP — מנסה שירותים לפי סדר
        for _fn in (LocationWorker._try_ip_api, LocationWorker._try_ipinfo):
            try:
                lat, lon, label = _fn()
                self.location_found.emit(lat, lon, label, 'ip')
                return
            except Exception as e:
                errors.append(f"IP({_fn.__name__}): {e}")

        self.location_error.emit("לא ניתן לאתר מיקום — " + " | ".join(errors))

    @staticmethod
    def _try_winrt_gps():
        import asyncio
        try:
            from winrt.windows.devices.geolocation import Geolocator
        except ImportError:
            raise RuntimeError("winrt לא מותקן")

        async def _get():
            locator = Geolocator()
            pos = await locator.get_geoposition_async()
            c = pos.coordinate
            return c.latitude, c.longitude, c.accuracy

        return asyncio.run(_get())

    @staticmethod
    def _try_ip_api():
        r = requests.get("http://ip-api.com/json/", timeout=6)
        r.raise_for_status()
        d = r.json()
        if d.get('status') != 'success':
            raise RuntimeError(d.get('message', 'ip-api נכשל'))
        lat = float(d['lat'])
        lon = float(d['lon'])
        city    = d.get('city', '')
        country = d.get('country', '')
        label = f"{city}, {country}" if city else f"{lat:.4f}, {lon:.4f}"
        return lat, lon, label

    @staticmethod
    def _try_ipinfo():
        r = requests.get("https://ipinfo.io/json", timeout=6)
        r.raise_for_status()
        d = r.json()
        loc = d.get('loc', '')
        if not loc or ',' not in loc:
            raise RuntimeError("ipinfo: loc חסר")
        lat, lon = (float(x) for x in loc.split(','))
        city    = d.get('city', '')
        country = d.get('country', '')
        label = f"{city}, {country}" if city else f"{lat:.4f}, {lon:.4f}"
        return lat, lon, label


class MapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ניהול מערכת מפה אינטראקטיבית")
        self.setMinimumSize(900, 600)
        self.resize(1280, 750)
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - 1280) // 2, (screen.height() - 750) // 2)
        self.map_view = QWebEngineView()
        self.map_view.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        self.map_view.setUrl(QUrl.fromLocalFile(os.path.abspath("map.html")))
        self.map_file = os.path.abspath("map.html")
        self.geo_server_process = None
        self.weather_server_process = None
        self.flight_server_process = None
        self.logs = []
        self.unread_log_count = 0
        self.weather_cache = {}
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.submit_coordinates)
        self.settings = QSettings("MapApp", "MapGUI")
        self._kill_zombie_servers()
        self.init_ui()

    def log_action(self, message, is_success=None):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        log_message = f"{timestamp} - {message}"

        self.logs.append(log_message)

        if len(self.logs) > MAX_LOG_LINES:
            self.logs = self.logs[-MAX_LOG_LINES:]

        self.update_log_view(message, is_success)

        if not self.log_area.isVisible():
            self.unread_log_count += 1
            self.badge_label.setText(str(self.unread_log_count))
            self.badge_label.setVisible(True)

        self.statusBar().showMessage(message, 4000)
        logging.info(log_message)

    def log_process_action(self, process_name, action, success=True):
        status = "הצליחה" if success else "נכשלה"
        self.log_action(f"פעולה '{action}' על {process_name} {status}.", is_success=success)

    def update_log_view(self, message="", is_success=None):
        if is_success is True:
            color = "#a6e3a1"
        elif is_success is False:
            color = "#f38ba8"
        else:
            color = "#cdd6f4"

        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        html_line = f'<span style="color:{color}">{timestamp} - {message}</span>'
        self.log_area.append(html_line)

        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_bell_icon(self, color):
        if color == "green":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_green.png"))
        elif color == "red":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_red.png"))
        else:
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon.png"))

        self.toggle_log_button.setIcon(bell_icon)

    def _restart_debounce(self):
        self.debounce_timer.start(600)

    def _load_city_history(self):
        history = self.settings.value("city_history", [])
        if isinstance(history, str):
            history = [history]
        for city in history:
            self.city_name_input.addItem(city)

    def _save_city_to_history(self, city_name):
        history = self.settings.value("city_history", [])
        if isinstance(history, str):
            history = [history]
        if city_name in history:
            history.remove(city_name)
        history.insert(0, city_name)
        history = history[:10]
        self.settings.setValue("city_history", history)
        self.city_name_input.clear()
        for city in history:
            self.city_name_input.addItem(city)

    def center_map_israel(self):
        self.map_view.page().runJavaScript(
            "map.setView([31.7683, 35.2137], 8);"
        )
        self.log_action("המפה מורכזת מעל ישראל.")

    def clear_map_markers(self):
        self.map_view.page().runJavaScript("""
            if (typeof allMarkers !== 'undefined') {
                allMarkers.forEach(function(m) { m.remove(); });
                allMarkers = [];
            }
        """)
        self.log_action("כל הסמנים נמחקו מהמפה.")

    def update_heatmap_opacity(self, value):
        opacity = value / 100.0
        self.map_view.page().runJavaScript(
            f"if (tempHeatLayer && tempHeatLayer.setOpacity) {{ tempHeatLayer.setOpacity({opacity}); }}"
        )

    def clear_logs(self):
        self.logs = []
        self.log_area.clear()
        self.unread_log_count = 0
        self.badge_label.setVisible(False)

    def _load_flight_history(self):
        history = self.settings.value("flight_history", [])
        if isinstance(history, str):
            history = [history]
        for flight in history:
            self.flight_input.addItem(flight)

    def _save_flight_to_history(self, flight_number):
        history = self.settings.value("flight_history", [])
        if isinstance(history, str):
            history = [history]
        if flight_number in history:
            history.remove(flight_number)
        history.insert(0, flight_number)
        history = history[:15]
        self.settings.setValue("flight_history", history)
        self.flight_input.clear()
        for flight in history:
            self.flight_input.addItem(flight)

    def fetch_and_draw_flight(self):
        flight_number = self.flight_input.currentText().strip().upper()

        if not flight_number:
            self.log_action("לא הוזן מספר טיסה.", is_success=False)
            return

        self.log_action(f"מחפש טיסה: {flight_number}...")
        self.show_flight_button.setEnabled(False)

        try:
            url = f"http://localhost:5004/flight_route?flight={flight_number}"
            # תיקון: timeout מופחת מ-35 ל-15 שניות
            response = requests.get(url, timeout=15)

            if response.status_code == 200:
                route_data = response.json()
                trail_count = len(route_data.get("trail", []))
                self.log_action(
                    f"נמצאה טיסה {route_data.get('callsign')} — {trail_count} נקודות מסלול",
                    is_success=True
                )
                self._draw_flight_on_map(route_data)
                self._save_flight_to_history(flight_number)
                self.clear_flight_button.setEnabled(True)
            else:
                error = response.json().get("error", "שגיאה לא ידועה")
                self.log_action(f"שגיאה בשליפת טיסה: {error}", is_success=False)

        except requests.exceptions.Timeout:
            self.log_action("פסק זמן בחיפוש הטיסה — נסה שנית.", is_success=False)
        except Exception as e:
            self.log_action(f"שגיאה בתקשורת עם FlightServer: {e}", is_success=False)
        finally:
            self.show_flight_button.setEnabled(True)

    def _draw_flight_on_map(self, route_data):
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
        if result and str(result).startswith("ERROR:"):
            self.log_action(f"שגיאת JavaScript בציור הטיסה: {result}", is_success=False)
        elif result == "ok":
            self.log_action("המסלול הוצג על המפה בהצלחה.", is_success=True)

    def clear_flight_route(self):
        self.map_view.page().runJavaScript("clearFlightRoute();")
        self.clear_flight_button.setEnabled(False)
        self.log_action("מסלול הטיסה הוסר מהמפה.")

    def init_ui(self):
        self.servers_running = False

        top_layout = QVBoxLayout()
        top_layout.setSpacing(6)
        top_layout.setContentsMargins(8, 10, 8, 6)

        lbl_servers = QLabel("שרתים")
        lbl_servers.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_servers)

        servers_row = QHBoxLayout()
        self.manage_servers_button = QPushButton("הפעל שרתים")
        self.manage_servers_button.setFixedSize(140, 34)
        self.manage_servers_button.setToolTip("הפעל / עצור את GeoServer ו-WeatherServer")
        self.manage_servers_button.clicked.connect(self.toggle_servers)
        servers_row.addWidget(self.manage_servers_button)

        status_col = QVBoxLayout()
        self.geo_status_dot = QLabel("⬤")
        self.geo_status_dot.setToolTip("GeoServer")
        self.geo_status_dot.setObjectName("dotOff")
        self.weather_status_dot = QLabel("⬤")
        self.weather_status_dot.setToolTip("WeatherServer")
        self.weather_status_dot.setObjectName("dotOff")
        status_col.addWidget(self.geo_status_dot)
        status_col.addWidget(self.weather_status_dot)
        servers_row.addLayout(status_col)
        top_layout.addLayout(servers_row)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setObjectName("separator")
        top_layout.addWidget(sep1)

        lbl_map = QLabel("מפה")
        lbl_map.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_map)

        self.load_map_button = QPushButton("יצירת / איפוס מפה")
        self.load_map_button.setFixedSize(140, 34)
        self.load_map_button.setEnabled(False)
        self.load_map_button.setToolTip("יצירת מפה חדשה או איפוס המפה הנוכחית")
        self.load_map_button.clicked.connect(self.create_map_from_file)
        top_layout.addWidget(self.load_map_button)

        self.home_button = QPushButton("ישראל")
        self.home_button.setFixedSize(140, 34)
        self.home_button.setToolTip("מרכז את המפה מעל ישראל")
        self.home_button.setEnabled(False)
        self.home_button.clicked.connect(self.center_map_israel)
        top_layout.addWidget(self.home_button)

        self.my_location_button = QPushButton("📍 מיקום עצמי")
        self.my_location_button.setFixedSize(140, 34)
        self.my_location_button.setToolTip("מרכז את המפה על מיקומך הנוכחי (מבוסס IP)")
        self.my_location_button.setEnabled(False)
        self.my_location_button.clicked.connect(self.go_to_my_location)
        top_layout.addWidget(self.my_location_button)

        self.clear_markers_button = QPushButton("נקה סמנים")
        self.clear_markers_button.setFixedHeight(36)
        self.clear_markers_button.setToolTip("מחיקת כל הסמנים וה-InfoWindows מהמפה")
        self.clear_markers_button.setEnabled(False)
        self.clear_markers_button.clicked.connect(self.clear_map_markers)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setObjectName("separator")
        top_layout.addWidget(sep2)

        lbl_location = QLabel("מיקום")
        lbl_location.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_location)

        self.Find_a_location = QPushButton("דקור נ.צ")
        self.Find_a_location.setFixedSize(140, 34)
        self.Find_a_location.setToolTip("הזן קואורדינטות או שם עיר כדי לדקור נקודה על המפה")
        self.Find_a_location.setEnabled(False)
        self.Find_a_location.clicked.connect(self.toggle_lat_lon_inputs)
        top_layout.addWidget(self.Find_a_location)

        self.input_tabs = QTabWidget()
        self.input_tabs.setVisible(False)
        self.input_tabs.setFixedHeight(130)

        coord_tab = QWidget()
        coord_layout = QVBoxLayout(coord_tab)
        coord_layout.setContentsMargins(4, 4, 4, 4)
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)
        self.lat_input.setPrefix("LAT: ")
        self.lat_input.setDecimals(6)
        self.lat_input.setFixedHeight(30)
        self.lat_input.valueChanged.connect(self._restart_debounce)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)
        self.lon_input.setPrefix("LON: ")
        self.lon_input.setDecimals(6)
        self.lon_input.setFixedHeight(30)
        self.lon_input.valueChanged.connect(self._restart_debounce)
        self.save_send_button = QPushButton("שלח")
        self.save_send_button.setFixedHeight(28)
        self.save_send_button.clicked.connect(self.save_and_send)
        coord_layout.addWidget(self.lat_input)
        coord_layout.addWidget(self.lon_input)
        coord_layout.addWidget(self.save_send_button)
        self.input_tabs.addTab(coord_tab, "קואורדינטות")

        city_tab = QWidget()
        city_layout = QVBoxLayout(city_tab)
        city_layout.setContentsMargins(4, 4, 4, 4)
        self.city_name_input = QComboBox()
        self.city_name_input.setEditable(True)
        self.city_name_input.setPlaceholderText("הכנס שם עיר")
        self.city_name_input.setFixedHeight(30)
        self._load_city_history()
        self.save_send_city_button = QPushButton("שלח")
        self.save_send_city_button.setFixedHeight(28)
        self.save_send_city_button.clicked.connect(self.save_and_send_city)
        self.city_name_input.lineEdit().returnPressed.connect(self.save_and_send_city)
        city_layout.addWidget(self.city_name_input)
        city_layout.addWidget(self.save_send_city_button)
        self.input_tabs.addTab(city_tab, "עיר")
        top_layout.addWidget(self.input_tabs)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setObjectName("separator")
        top_layout.addWidget(sep3)

        lbl_tools = QLabel("כלים")
        lbl_tools.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_tools)

        self.heatmap_button = QPushButton("הפעל מפת טמפרטורות")
        self.heatmap_button.setFixedSize(140, 34)
        self.heatmap_button.setEnabled(False)
        self.heatmap_button.setCheckable(True)
        self.heatmap_button.setToolTip("לחץ ואז גרור על המפה לבחירת אזור — כחול=קר, אדום=חם")
        self.heatmap_button.clicked.connect(self.toggle_heatmap)
        top_layout.addWidget(self.heatmap_button)

        heat_mode_row = QHBoxLayout()
        self.heat_mode_grid_btn = QPushButton("גריד")
        self.heat_mode_grid_btn.setFixedSize(44, 26)
        self.heat_mode_grid_btn.setEnabled(False)
        self.heat_mode_grid_btn.setCheckable(True)
        self.heat_mode_grid_btn.setChecked(False)
        self.heat_mode_grid_btn.setToolTip("מפה אחידה — תא צבעוני לכל נקודת דגימה, ללא רווחים")
        self.heat_mode_grid_btn.clicked.connect(lambda: self._set_temp_display_mode('grid'))
        self.heat_mode_heat_btn = QPushButton("חום")
        self.heat_mode_heat_btn.setFixedSize(44, 26)
        self.heat_mode_heat_btn.setEnabled(False)
        self.heat_mode_heat_btn.setCheckable(True)
        self.heat_mode_heat_btn.setChecked(True)
        self.heat_mode_heat_btn.setToolTip("שכבת חום חלקה עם מעברי צבע מרוככים")
        self.heat_mode_heat_btn.clicked.connect(lambda: self._set_temp_display_mode('heat'))
        self.heat_mode_dots_btn = QPushButton("נקודות")
        self.heat_mode_dots_btn.setFixedSize(44, 26)
        self.heat_mode_dots_btn.setEnabled(False)
        self.heat_mode_dots_btn.setCheckable(True)
        self.heat_mode_dots_btn.setToolTip("נקודות דגימה עם ערכי טמפרטורה")
        self.heat_mode_dots_btn.clicked.connect(lambda: self._set_temp_display_mode('dots'))
        heat_mode_row.addWidget(self.heat_mode_grid_btn)
        heat_mode_row.addWidget(self.heat_mode_heat_btn)
        heat_mode_row.addWidget(self.heat_mode_dots_btn)
        top_layout.addLayout(heat_mode_row)

        opacity_row = QHBoxLayout()
        opacity_lbl = QLabel("שקיפות:")
        opacity_lbl.setFixedWidth(50)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(60)
        self.opacity_slider.setEnabled(False)
        self.opacity_slider.setToolTip("שליטה בשקיפות שכבת מפת החום")
        self.opacity_slider.valueChanged.connect(self.update_heatmap_opacity)
        opacity_row.addWidget(opacity_lbl)
        opacity_row.addWidget(self.opacity_slider)
        top_layout.addLayout(opacity_row)

        self.heatmap_new_button = QPushButton("טען נתוני מזג אוויר")
        self.heatmap_new_button.setFixedSize(140, 34)
        self.heatmap_new_button.setEnabled(False)
        self.heatmap_new_button.setToolTip("הרצת weather_tool.py וטעינת נתוני מזג האוויר כשכבת חום")
        self.heatmap_new_button.clicked.connect(self.run_weather_tool)
        top_layout.addWidget(self.heatmap_new_button)

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

        self.elevation_button = QPushButton("שכבת גבהים")
        self.elevation_button.setFixedSize(140, 34)
        self.elevation_button.setEnabled(False)
        self.elevation_button.setCheckable(True)
        self.elevation_button.setToolTip("לחץ ואז גרור על המפה לבחירת אזור — כחול=נמוך, אדום=גבוה")
        self.elevation_button.clicked.connect(self.toggle_elevation_layer)
        top_layout.addWidget(self.elevation_button)

        elev_mode_row = QHBoxLayout()
        self.elev_mode_heat_btn = QPushButton("חום")
        self.elev_mode_heat_btn.setFixedSize(44, 26)
        self.elev_mode_heat_btn.setEnabled(False)
        self.elev_mode_heat_btn.setCheckable(True)
        self.elev_mode_heat_btn.setChecked(True)
        self.elev_mode_heat_btn.setToolTip("שכבת חום חלקה")
        self.elev_mode_heat_btn.clicked.connect(lambda: self._set_elev_display_mode('heat'))
        self.elev_mode_grid_btn = QPushButton("גריד")
        self.elev_mode_grid_btn.setFixedSize(44, 26)
        self.elev_mode_grid_btn.setEnabled(False)
        self.elev_mode_grid_btn.setCheckable(True)
        self.elev_mode_grid_btn.setToolTip("גריד תאים אחיד ללא רווחים")
        self.elev_mode_grid_btn.clicked.connect(lambda: self._set_elev_display_mode('grid'))
        self.elev_mode_dots_btn = QPushButton("נקודות")
        self.elev_mode_dots_btn.setFixedSize(44, 26)
        self.elev_mode_dots_btn.setEnabled(False)
        self.elev_mode_dots_btn.setCheckable(True)
        self.elev_mode_dots_btn.setToolTip("נקודות עם גובה במטרים מעל פני הים")
        self.elev_mode_dots_btn.clicked.connect(lambda: self._set_elev_display_mode('dots'))
        elev_mode_row.addWidget(self.elev_mode_heat_btn)
        elev_mode_row.addWidget(self.elev_mode_grid_btn)
        elev_mode_row.addWidget(self.elev_mode_dots_btn)
        top_layout.addLayout(elev_mode_row)

        sep4 = QFrame()
        sep4.setFrameShape(QFrame.HLine)
        sep4.setObjectName("separator")
        top_layout.addWidget(sep4)

        lbl_flights = QLabel("טיסות")
        lbl_flights.setObjectName("sectionLabel")
        top_layout.addWidget(lbl_flights)

        self.flight_input = QComboBox()
        self.flight_input.setEditable(True)
        self.flight_input.setPlaceholderText("מס' טיסה — LY001")
        self.flight_input.setFixedHeight(30)
        self.flight_input.setEnabled(False)
        self.flight_input.setToolTip("הכנס מספר טיסה או callsign (לדוגמה: LY001, ELY001)")
        self.flight_input.lineEdit().returnPressed.connect(self.fetch_and_draw_flight)
        self._load_flight_history()
        top_layout.addWidget(self.flight_input)

        flight_btn_row = QHBoxLayout()
        self.show_flight_button = QPushButton("הצג מסלול")
        self.show_flight_button.setFixedSize(90, 30)
        self.show_flight_button.setEnabled(False)
        self.show_flight_button.setToolTip("שלוף את מסלול הטיסה מ-FlightRadar24 והצג על המפה")
        self.show_flight_button.clicked.connect(self.fetch_and_draw_flight)
        self.clear_flight_button = QPushButton("נקה")
        self.clear_flight_button.setFixedSize(44, 30)
        self.clear_flight_button.setEnabled(False)
        self.clear_flight_button.setToolTip("הסר את מסלול הטיסה מהמפה")
        self.clear_flight_button.clicked.connect(self.clear_flight_route)
        flight_btn_row.addWidget(self.show_flight_button)
        flight_btn_row.addWidget(self.clear_flight_button)
        top_layout.addLayout(flight_btn_row)

        top_layout.addStretch()

        icon_layout = QHBoxLayout()
        self.toggle_log_button = QPushButton()
        self.toggle_log_button.setFixedSize(28, 28)
        self.toggle_log_button.setIconSize(QSize(20, 20))
        self.toggle_log_button.setIcon(QIcon(os.path.join("ICONS", "bell_icon.png")))
        self.toggle_log_button.setToolTip("הצג / הסתר לוגים")
        self.toggle_log_button.clicked.connect(self.toggle_log_view)

        self.badge_label = QLabel("", self.toggle_log_button)
        self.badge_label.setObjectName("badge")
        self.badge_label.setVisible(False)
        self.badge_label.move(16, 0)

        self.save_log_button = QPushButton()
        self.save_log_button.setFixedSize(28, 28)
        self.save_log_button.setIconSize(QSize(20, 20))
        self.save_log_button.setIcon(QIcon(os.path.join("ICONS", "save_log.png")))
        self.save_log_button.setToolTip("שמור לוגים לקובץ טקסט")
        self.save_log_button.clicked.connect(self.save_logs_to_file)

        self.clear_log_button = QPushButton("נקה")
        self.clear_log_button.setFixedSize(40, 28)
        self.clear_log_button.setToolTip("נקה את תצוגת הלוגים")
        self.clear_log_button.clicked.connect(self.clear_logs)

        icon_layout.addWidget(self.toggle_log_button)
        icon_layout.addWidget(self.save_log_button)
        icon_layout.addWidget(self.clear_log_button)
        icon_layout.addStretch()
        top_layout.addLayout(icon_layout)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setVisible(False)
        self.log_area.setMinimumHeight(80)
        self.log_area.setMaximumHeight(220)

        panel_splitter = QSplitter(Qt.Vertical)
        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        panel_splitter.addWidget(top_widget)
        panel_splitter.addWidget(self.log_area)
        panel_splitter.setSizes([1, 0])
        panel_splitter.setCollapsible(1, True)
        self.panel_splitter = panel_splitter

        button_widget = QWidget()
        button_widget.setLayout(QVBoxLayout())
        button_widget.layout().setContentsMargins(0, 0, 0, 0)
        button_widget.layout().addWidget(panel_splitter)
        button_widget.setMinimumWidth(165)

        main_layout = QHBoxLayout()

        map_container = QWidget()
        map_vbox = QVBoxLayout(map_container)
        map_vbox.setContentsMargins(0, 0, 0, 0)
        map_vbox.setSpacing(0)
        map_vbox.addWidget(self.map_view)
        map_vbox.addWidget(self.clear_markers_button)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(map_container)
        self.splitter.addWidget(button_widget)
        self.splitter.setSizes([1110, 170])
        self.splitter.setCollapsible(1, False)

        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_layout.addWidget(self.splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.statusBar().showMessage("מוכן")

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

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def create_map_from_file(self):
        self.log_action("יצירת המפה התחילה.")
        create_map()
        self.load_map()
        self.log_action("המפה נוצרה בהצלחה.", is_success=True)
        # ── מיקום ──
        self.Find_a_location.setEnabled(True)
        self.home_button.setEnabled(True)
        self.my_location_button.setEnabled(True)
        self.clear_markers_button.setEnabled(True)
        # ── מפת טמפרטורות — איפוס מצב ──
        self.heatmap_button.setEnabled(True)
        self.heatmap_button.setChecked(False)
        self.heatmap_button.setText("הפעל מפת טמפרטורות")
        self.heat_mode_grid_btn.setEnabled(False)
        self.heat_mode_heat_btn.setEnabled(False)
        self.heat_mode_dots_btn.setEnabled(False)
        self.heatmap_new_button.setEnabled(True)
        self.heatmap_pick_button.setEnabled(True)
        self.heatmap_pick_button.setChecked(False)
        self.opacity_slider.setEnabled(True)
        # ── שכבת גבהים — איפוס מצב ──
        self.elevation_button.setEnabled(True)
        self.elevation_button.setChecked(False)
        self.elevation_button.setText("שכבת גבהים")
        self.elev_mode_heat_btn.setEnabled(False)
        self.elev_mode_grid_btn.setEnabled(False)
        self.elev_mode_dots_btn.setEnabled(False)

    def load_map(self):
        if os.path.exists(self.map_file):
            try:
                self.map_view.page().loadFinished.disconnect(self._sync_servers_running)
            except TypeError:
                pass
            self.map_view.page().loadFinished.connect(self._sync_servers_running)
            self.map_view.setUrl(QUrl.fromLocalFile(self.map_file))
            self.log_action("המפה נטענה בהצלחה.", is_success=True)
        else:
            self.log_action("שגיאה: קובץ המפה לא נמצא.", is_success=False)

    def _sync_servers_running(self, ok):
        if ok:
            flag = "true" if self.servers_running else "false"
            self.map_view.page().runJavaScript(f"window.serversRunning = {flag};")

    def toggle_servers(self):
        if self.servers_running:
            self.stop_servers()
            self.servers_running = False
            self.manage_servers_button.setText("הפעל שרתים")
            self.manage_servers_button.setStyleSheet("background-color: #e64553; color: white; font-weight: bold;")
        else:
            self.start_servers()
            self.servers_running = True
            self.manage_servers_button.setText("עצור שרתים")
            self.manage_servers_button.setStyleSheet("background-color: #40a02b; color: white; font-weight: bold;")

    def start_servers(self):
        try:
            self.log_action("הפעלת GeoServer התחילה.")
            # תיקון: sys.executable במקום "python" — מבטיח שימוש במפרש הנכון
            self.geo_server_process = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "geo_server.py")])
            self.log_process_action("GeoServer", "הפעלת", success=True)
            self.geo_status_dot.setObjectName("dotOn")
            self.geo_status_dot.setStyle(self.geo_status_dot.style())
        except Exception as e:
            self.log_process_action("GeoServer", "הפעלת", success=False)
            self.log_action(f"שגיאה בהפעלת GeoServer: {e}", is_success=False)

        try:
            self.log_action("הפעלת WeatherServer התחילה.")
            self.weather_server_process = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "weather_server.py")])
            self.log_action("WeatherServer הופעל בהצלחה.", is_success=True)
            self.weather_status_dot.setObjectName("dotOn")
            self.weather_status_dot.setStyle(self.weather_status_dot.style())
        except Exception as e:
            self.log_action(f"שגיאה בהפעלת WeatherServer: {e}", is_success=False)

        try:
            self.log_action("הפעלת FlightServer התחילה.")
            self.flight_server_process = subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "flight_server.py")])
            self.log_action("FlightServer הופעל בהצלחה.", is_success=True)
            self.flight_input.setEnabled(True)
            self.show_flight_button.setEnabled(True)
        except Exception as e:
            self.log_action(f"שגיאה בהפעלת FlightServer: {e}", is_success=False)

        self.load_map_button.setEnabled(True)
        self.map_view.page().runJavaScript("window.serversRunning = true;")

    def stop_servers(self):
        try:
            if self.geo_server_process:
                self.geo_server_process.terminate()
                self.geo_server_process = None
                self.log_action("GeoServer נעצר בהצלחה.", is_success=True)
                self.geo_status_dot.setObjectName("dotOff")
                self.geo_status_dot.setStyle(self.geo_status_dot.style())
            if self.weather_server_process:
                self.weather_server_process.terminate()
                self.weather_server_process = None
                self.log_action("WeatherServer נעצר בהצלחה.", is_success=True)
                self.weather_status_dot.setObjectName("dotOff")
                self.weather_status_dot.setStyle(self.weather_status_dot.style())
            if self.flight_server_process:
                self.flight_server_process.terminate()
                self.flight_server_process = None
                self.log_action("FlightServer נעצר בהצלחה.", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בעצירת השרתים: {e}", is_success=False)
        self.load_map_button.setEnabled(False)
        self.Find_a_location.setEnabled(False)
        self.heatmap_button.setEnabled(False)
        self.heatmap_new_button.setEnabled(False)
        self.heatmap_pick_button.setEnabled(False)
        self.elevation_button.setEnabled(False)
        self.opacity_slider.setEnabled(False)
        self.show_flight_button.setEnabled(False)
        self.flight_input.setEnabled(False)
        self.map_view.page().runJavaScript("window.serversRunning = false;")

    def save_and_send(self):
        lat = self.lat_input.value()
        lon = self.lon_input.value()
        self.log_action("הנתונים נשמרו ונשלחו")

        if lat == 0 or lon == 0:
            self.log_action("נתוני קואורדינטות אינם תקינים.", is_success=False)
            return

        message = {"lat": lat, "lon": lon}

        try:
            # os.path.join(BASE_DIR, ...) — נתיב מוחלט, ראה הסבר ב-BASE_DIR
            # repr(message) — מוודא שהמילון מוצג כמחרוזת בטוחה;
            # אין צורך בסניטציה נוספת כי lat/lon הם float (מ-QDoubleSpinBox)
            # ולא קלט טקסט חופשי.
            coords_log_path = os.path.join(BASE_DIR, "coordinates_log.txt")
            with open(coords_log_path, "a") as log_file:
                log_file.write(f"{message}\n")
            self.log_action(f"מבנה ההודעה נשמר", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בשמירת מבנה ההודעה: {e}", is_success=False)
            return

        try:
            url = f"http://localhost:5002/weather?lat={lat}&lon={lon}"
            # timeout=10 — מגביל את ההמתנה ל-10 שניות.
            # ללא timeout, שרת תקוע יקפיא את ה-UI לתמיד כי הבקשה רצה
            # על ה-main thread של Qt.
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                weather_data = response.json()
                self.log_action("נתוני מזג האוויר התקבלו", is_success=True)
                self.display_weather_on_map(lat, lon, weather_data)
            else:
                self.log_action(f"שגיאה בשליחת הבקשה: {response.status_code}", is_success=False)
        except Exception as e:
            self.log_action(f"שגיאה בשליחת ההודעה לשרת: {e}", is_success=False)

    def toggle_lat_lon_inputs(self):
        is_visible = not self.input_tabs.isVisible()
        self.input_tabs.setVisible(is_visible)

        if is_visible:
            self.Find_a_location.clicked.connect(self.submit_coordinates)
            self.log_action("בוצע חיבור לפונקציה לדקירת נ.צ.")
        else:
            try:
                self.Find_a_location.clicked.disconnect(self.submit_coordinates)
            except TypeError:
                pass
            self.log_action("בוצע ניתוק מפונקציה לדקירת נ.צ.")

    def save_and_send_city(self):
        city_name = self.city_name_input.currentText().strip()
        self.log_action("הוקלד ונשלח שם של עיר")

        if not city_name:
            self.log_action("שם העיר אינו תקין.", is_success=False)
            return

        self._save_city_to_history(city_name)

        try:
            # os.path.join(BASE_DIR, ...) — נתיב מוחלט, ראה הסבר ב-BASE_DIR.
            # sanitized_city — מסיר תווי שורה חדשה (\n, \r) ותווי בקרה (ord < 32)
            # מקלט המשתמש לפני כתיבה לקובץ.
            # ללא זאת, קלט כמו "תל-אביב\nAdmin: logged in" ייכתב כשתי שורות
            # ויכול לזייף רשומות לוג (Log Injection).
            sanitized_city = "".join(
                ch for ch in city_name if ch not in ("\n", "\r") and ord(ch) >= 32
            )
            city_log_path = os.path.join(BASE_DIR, "city_log.txt")
            with open(city_log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"City: {sanitized_city}\n")
            self.log_action(f"שם העיר נשמר", is_success=True)
        except Exception as e:
            self.log_action(f"שגיאה בשמירת שם העיר: {e}", is_success=False)
            return

        encoded_city_name = urllib.parse.quote(city_name)

        try:
            url = f"http://localhost:5002/weather?region={encoded_city_name}"
            # timeout=10 — ראה הסבר בבקשה הקודמת (save_and_send).
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                weather_data = response.json()
                self.log_action("נתוני מזג האוויר התקבלו")
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
        QMessageBox.information(self, "מפת טמפרטורות", "שכבת מפת טמפרטורות נוספה למפה.")

    def toggle_log_view(self):
        if self.log_area.isVisible():
            self.log_area.setVisible(False)
            self.panel_splitter.setSizes([1, 0])
        else:
            self.log_area.setVisible(True)
            self.panel_splitter.setSizes([1, 160])
            self.unread_log_count = 0
            self.badge_label.setVisible(False)
            sb = self.log_area.verticalScrollBar()
            sb.setValue(sb.maximum())

    def toggle_heatmap(self):
        if self.heatmap_button.isChecked():
            self.heatmap_button.setText("גרור אזור על המפה...")
            self.log_action("גרור מלבן על המפה לבחירת אזור טמפרטורה")
            self._register_title_bridge()
            self.map_view.page().runJavaScript("clearTempHeatmap(); startTempHeatmap();")
        else:
            self.heatmap_button.setText("הפעל מפת טמפרטורות")
            self.heat_mode_grid_btn.setEnabled(False)
            self.heat_mode_heat_btn.setEnabled(False)
            self.heat_mode_dots_btn.setEnabled(False)
            self.map_view.page().runJavaScript("clearTempHeatmap();")

    def _set_temp_display_mode(self, mode):
        self.heat_mode_grid_btn.setChecked(mode == 'grid')
        self.heat_mode_heat_btn.setChecked(mode == 'heat')
        self.heat_mode_dots_btn.setChecked(mode == 'dots')
        js_fn = {'grid': 'showTempAsGrid', 'heat': 'showTempAsHeatmap', 'dots': 'showTempAsDots'}
        fn = js_fn[mode]
        js = f"""(function(){{try{{{fn}();}}catch(e){{document.title='__temp_mode_error__:'+(e.message||String(e));}}}})();"""
        self.map_view.page().runJavaScript(js, lambda _: None)

    def _register_title_bridge(self):
        try:
            self.map_view.page().titleChanged.disconnect(self._on_title_changed)
        except TypeError:
            pass
        self.map_view.page().titleChanged.connect(self._on_title_changed)

    def _set_elev_display_mode(self, mode):
        self.elev_mode_heat_btn.setChecked(mode == 'heat')
        self.elev_mode_grid_btn.setChecked(mode == 'grid')
        self.elev_mode_dots_btn.setChecked(mode == 'dots')
        js_fn = {'heat': 'showElevAsHeatmap', 'grid': 'showElevAsGrid', 'dots': 'showElevAsDots'}
        fn = js_fn[mode]
        js = f"""(function(){{try{{{fn}();}}catch(e){{document.title='__elev_mode_error__:'+(e.message||String(e));}}}})();"""
        self.map_view.page().runJavaScript(js, lambda _: None)

    def _on_title_changed(self, title):
        if title == '__heatmap_ok__':
            self.heatmap_button.setText("הפעל מפת טמפרטורות")
            self.heat_mode_grid_btn.setEnabled(True)
            self.heat_mode_heat_btn.setEnabled(True)
            self.heat_mode_dots_btn.setEnabled(True)
            self.heat_mode_grid_btn.setChecked(False)
            self.heat_mode_heat_btn.setChecked(True)
            self.heat_mode_dots_btn.setChecked(False)
            self.log_action("מפת טמפרטורות נטענה בהצלחה.", is_success=True)
        elif title == '__heatmap_cancel__':
            self.heatmap_button.setText("הפעל מפת טמפרטורות")
            self.heatmap_button.setChecked(False)
        elif title == '__heatmap_error__':
            self.heatmap_button.setText("הפעל מפת טמפרטורות")
            self.heatmap_button.setChecked(False)
            self.log_action("שגיאה בטעינת מפת החום.", is_success=False)
        elif title == '__elevation_ok__':
            self.elevation_button.setText("שכבת גבהים")
            self.elev_mode_heat_btn.setEnabled(True)
            self.elev_mode_grid_btn.setEnabled(True)
            self.elev_mode_dots_btn.setEnabled(True)
            self.elev_mode_heat_btn.setChecked(True)
            self.elev_mode_grid_btn.setChecked(False)
            self.elev_mode_dots_btn.setChecked(False)
            self.log_action("שכבת גבהים נטענה בהצלחה.", is_success=True)
        elif title.startswith('__elevation_error__'):
            self.elevation_button.setText("שכבת גבהים")
            self.elevation_button.setChecked(False)
            detail = title[len('__elevation_error__:'):] if ':' in title else ''
            msg = f"שגיאה בטעינת שכבת הגבהים. {detail}".strip()
            self.log_action(msg, is_success=False)
        elif title.startswith('__temp_mode_error__'):
            detail = title[len('__temp_mode_error__:'):] if ':' in title else title
            self.log_action(f"שגיאת JS במעבר מצב טמפרטורה: {detail}", is_success=False)
        elif title.startswith('__elev_mode_error__'):
            detail = title[len('__elev_mode_error__:'):] if ':' in title else title
            self.log_action(f"שגיאת JS במעבר מצב גבהים: {detail}", is_success=False)

    def _kill_zombie_servers(self):
        for port in [5002, 5003, 5004]:
            try:
                result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if f':{port} ' in line and 'LISTENING' in line:
                        pid = line.strip().split()[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            except Exception:
                pass

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

    def toggle_elevation_layer(self, checked):
        self.map_view.page().runJavaScript("toggleElevationLayer();")
        if checked:
            self.elevation_button.setText("גרור על המפה...")
            self.log_action("גרור מלבן על המפה לבחירת אזור גבהים")
            self._register_title_bridge()
        else:
            self.elevation_button.setText("שכבת גבהים")
            self.elev_mode_heat_btn.setEnabled(False)
            self.elev_mode_grid_btn.setEnabled(False)
            self.elev_mode_dots_btn.setEnabled(False)
            self.log_action("שכבת גבהים כובתה")

    def save_logs_to_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "שמור לוגים לקובץ", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    for log in self.logs:
                        f.write(log + "\n")
                self.log_action(f"לוגים נשמרו בהצלחה ב-{file_path}")
            except Exception as e:
                self.log_action(f"שגיאה בשמירת הלוגים: {e}")

    def submit_coordinates(self):
        lat = self.lat_input.value()
        lon = self.lon_input.value()

        self.log_action(f"שליחה של קואורדינטות")  # תיקון: לא מתעדים את הערכים עצמם

        weather_data = fetch_weather_data(f"{lat},{lon}")

        if weather_data:
            self.log_action("נתוני מזג האוויר התקבלו")

            lat = weather_data.get("coord", {}).get("lat")
            lon = weather_data.get("coord", {}).get("lon")

            if lat is not None and lon is not None:
                self.display_weather_on_map(lat, lon, weather_data)
            else:
                self.log_action(f"לא התקבלו קואורדינטות", is_success=False)
        else:
            self.log_action("לא הצלחנו לקבל נתוני מזג אוויר", is_success=False)

    def display_weather_on_map(self, lat, lon, weather_data):
        """
        הצגת נתוני מזג האוויר והוספת גבולות העיר על המפה.
        """
        try:
            weather_info = f"Temperature: {weather_data['temperature']}°C, Weather: {weather_data['weather']}"
            self.log_action(f"מציג מזג אוויר")  # תיקון: לא מתעדים נתונים מפורטים

            # תיקון: המרה מפורשת ל-float — מונעת הזרקת ערכים לא-מספריים ל-JavaScript
            lat_f = float(lat)
            lon_f = float(lon)

            # html.escape() על כל שדה שמגיע מ-API חיצוני לפני שהוא מוכנס ל-HTML.
            # למרות ש-json.dumps בשורה הבאה מגן מפני JS injection (בורח מ-" ו-\),
            # הוא אינו מגן מפני HTML injection בתוך הפופאפ עצמו:
            # Leaflet מרנדר את תוכן bindPopup() כ-HTML גולמי בדפדפן,
            # לכן <script> או <img onerror=...> יבוצעו ללא html.escape().
            safe_weather = html.escape(str(weather_data['weather']))
            safe_temp    = html.escape(str(weather_data['temperature']))

            # תיקון: שימוש ב-json.dumps לאסקייפינג תוכן הפופאפ — מונע JS injection
            popup_text = (
                f"קו רוחב: {lat_f}, קו אורך: {lon_f}<br>"
                f"מזג אוויר: {safe_weather}<br>"
                f"טמפרטורה: {safe_temp}°C"
            )
            js_code_marker = f"""
var marker = L.marker([{lat_f}, {lon_f}]).addTo(map);
allMarkers.push(marker);
marker.bindPopup({json.dumps(popup_text)}).openPopup();
"""
            self.map_view.page().runJavaScript(js_code_marker)

            boundary = weather_data.get("boundary")
            if boundary:
                ne = boundary["northeast"]
                sw = boundary["southwest"]

                # תיקון: המרה מפורשת ל-float לכל קואורדינטת גבול
                sw_lat = float(sw['lat'])
                sw_lng = float(sw['lng'])
                ne_lat = float(ne['lat'])
                ne_lng = float(ne['lng'])

                js_code_polygon = f"""
var cityRect = L.rectangle(
    [[{sw_lat}, {sw_lng}], [{ne_lat}, {ne_lng}]],
    {{
        color:       '#FF0000',
        weight:      2,
        opacity:     0.8,
        fillColor:   '#FF0000',
        fillOpacity: 0.25
    }}
).addTo(map);
allMarkers.push(cityRect);
"""
                self.map_view.page().runJavaScript(js_code_polygon)
                self.log_action("גבולות העיר סומנו בהצלחה.")
            else:
                self.log_action("גבולות העיר לא נמצאו.")
        except Exception as e:
            self.log_action(f"שגיאה בהצגת המידע על המפה: {e}")

    def fetch_weather_data(self, location):
        try:
            # תיקון: logging.info במקום print
            logging.info("שליחת בקשת מזג אוויר לשרת")

            # urllib.parse.quote(location) — מקודד תווים מיוחדים ב-location.
            # ללא זאת, קלט כמו "תל אביב&admin=1" עלול לשנות את מבנה ה-URL
            # ולהזריק פרמטרים נוספים לבקשה (URL Injection).
            # timeout=10 — ראה הסבר בבקשה הקודמת (save_and_send).
            encoded_location = urllib.parse.quote(str(location))
            url = f"http://localhost:5002/weather?region={encoded_location}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"שגיאה בקבלת מזג האוויר, סטטוס: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"שגיאה בתקשורת עם שרת ה-API: {e}")
            return None

    def run_weather_tool(self):
        try:
            # תיקון: sys.executable במקום "python"
            subprocess.Popen([sys.executable, "weather_tool.py"])
            self.log_action("הקובץ weather_tool.py הורץ בהצלחה.")
            self.map_view.page().runJavaScript("loadHeatmapDataFromCSV('weather_data.csv')")
            self.log_action("נוצרה שכבת חום.")
        except Exception as e:
            self.log_action(f"שגיאה בהרצת הקובץ weather_tool.py: {e}")

    def go_to_my_location(self):
        self.log_action("מאתר מיקום...")
        self.my_location_button.setEnabled(False)
        self._location_worker = LocationWorker()
        self._location_worker.location_found.connect(self._on_location_found)
        self._location_worker.location_error.connect(self._on_location_error)
        self._location_worker.finished.connect(
            lambda: self.my_location_button.setEnabled(True)
        )
        self._location_worker.start()

    def _on_location_found(self, lat, lon, label, source):
        zoom = 15 if source == 'gps' else 13
        dot_color = "#a6e3a1" if source == 'gps' else "#89b4fa"
        source_text = "GPS" if source == 'gps' else "IP"
        self.map_view.page().runJavaScript(f"map.setView([{lat}, {lon}], {zoom});")
        popup_html = html.escape(f"מיקומך ({source_text}): {label}")
        js = f"""
(function() {{
    var icon = L.divIcon({{
        html: '<div style="background:{dot_color};border:3px solid white;border-radius:50%;'
            + 'width:18px;height:18px;box-shadow:0 0 8px {dot_color};"></div>',
        iconSize: [18, 18], iconAnchor: [9, 9], className: ''
    }});
    var m = L.marker([{lat}, {lon}], {{icon: icon}}).addTo(map);
    allMarkers.push(m);
    m.bindPopup({json.dumps(popup_html)}).openPopup();
}})();
"""
        self.map_view.page().runJavaScript(js)
        self.log_action(f"מיקום ({source_text}): {label}", is_success=True)

    def _on_location_error(self, msg):
        self.log_action(msg, is_success=False)

    def closeEvent(self, event):
        self.stop_servers()
        self.log_action("היישום נסגר.")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MapApp()
    gui.show()
    sys.exit(app.exec_())
