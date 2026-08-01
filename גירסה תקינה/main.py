import logging
import os
import subprocess
import sys
import urllib.parse
import requests
from MAP import create_map  # Import create_map function from MAP
from PyQt5.QtCore import Qt, QUrl, QDateTime, pyqtSlot, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, \
    QTextEdit, QFileDialog, QSplitter, QSizePolicy, QLineEdit, QDoubleSpinBox, QMessageBox
from apipyqt import fetch_weather_data

# הגדרת הלוגים בתחילת הקובץ
logging.basicConfig(filename='app_combined.log', level=logging.INFO, format='%(asctime)s - %(message)s')

class MapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ניהול מערכת מפה אינטראקטיבית")  # הגדרת כותרת חלון
        self.setGeometry(0, 0, 800, 600)  # הגדרת גודל ומיקום חלון ראשוני
        self.setMinimumSize(600, 400)  # הגדרת גודל מינימלי לחלון
        self.map_view = QWebEngineView()  # יצירת אובייקט תצוגת המפה
        # יצירת WebEngineView לטעינת ה-HTML
        self.map_view.setUrl(QUrl("map.html"))  # טוען את קובץ ה-HTML
        self.map_file = os.path.abspath("map.html")  # קביעת נתיב מוחלט לקובץ המפה
        self.main_layout = QVBoxLayout()  # הגדרת main_layout כחלק מהאובייקט
        self.geo_server_process = None  # משתנה לניהול התהליך של GeoServer
        self.weather_server_process = None  # משתנה לניהול התהליך של WeatherServer
        self.logs = []  # רשימת הלוגים לשמירת הודעות מערכת
        self.init_ui()  # קריאה לפונקציה לאתחול הממשק הגרפי

    def log_action(self, message, is_success=None):
        """ פונקציה שמוסיפה את ההודעה לרשימת הלוגים עם תאריך ושעה. """
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")  # השגת זמן האירוע
        log_message = f"{timestamp} - {message}"  # יצירת הודעת לוג עם תאריך ושעה

        # הוספת ההודעה לרשימת הלוגים
        self.logs.append(log_message)

        # עדכון תצוגת הלוגים בתיבת הטקסט
        self.update_log_view()

        # שמירת הלוג לקובץ
        logging.info(log_message)  # שמירה של ההודעה בקובץ הלוגים

        # עכשיו רק תיעוד ההודעה, הצבע לא משתנה פה

    def log_process_action(self, process_name, action, success=True):
        """
        פונקציה שמבצעת רישום של כל פעולה הקשורה בתהליך.
        :param process_name: שם התהליך (למשל, GeoServer או WeatherServer)
        :param action: פעולה שמתבצעת (הפעלה/עצירה)
        :param success: האם הפעולה הצליחה או לא
        """
        status = "הצליחה" if success else "נכשלה"
        self.log_action(f"פעולה '{action}' על {process_name} {status}.")

    def update_log_view(self):
        """ עדכון תצוגת הלוגים בתיבת הטקסט. """
        self.log_area.setPlainText("\n".join(self.logs))  # מציג את כל הלוגים בתיבת הטקסט

    def update_bell_icon(self, color):
        """עדכון אייקון פעמון בצבע מתאים"""
        if color == "green":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_green.png"))  # אייקון ירוק
        elif color == "red":
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon_red.png"))  # אייקון אדום
        else:
            bell_icon = QIcon(os.path.join("ICONS", "bell_icon.png"))  # אייקון ברירת מחדל

        # עדכון האייקון לכפתור
        self.toggle_log_button.setIcon(bell_icon)

    def init_ui(self):
        """ יצירת ממשק המשתמש, כולל כפתורים, תצוגת המפה, ולוגים. """
        self.main_layout = QVBoxLayout()  # הגדרת Layout מרכזי עבור כל האלמנטים

        button_layout = QVBoxLayout()  # Layout אנכי עבור כפתורים

        # הוספת משתנה למעקב אחר מצב השרתים
        self.servers_running = False  # השרתים במצב כבוי בתחילה

        # "הפעל שרתים" כפתור
        self.manage_servers_button = QPushButton("הפעל שרתים")
        self.manage_servers_button.setFixedSize(120, 40)
        self.manage_servers_button.clicked.connect(self.toggle_servers)  # חיבור לפונקציה אחת
        button_layout.addWidget(self.manage_servers_button)

        # כפתור יצירת המפה
        self.load_map_button = QPushButton("יצירת/איפוס מפה")
        self.load_map_button.setFixedSize(120, 40)  # גודל מותאם אישית לכפתור
        self.load_map_button.setEnabled(False)
        self.load_map_button.clicked.connect(self.create_map_from_file)  # חיבור הכפתור לפונקציה
        button_layout.addWidget(self.load_map_button)  # הוספת הכפתור ל-Layout

        # כפתור לדקירת נ.צ
        self.Find_a_location = QPushButton("דקור נ.צ")
        self.Find_a_location.setFixedSize(120, 40)
        self.Find_a_location.clicked.connect(self.toggle_lat_lon_inputs)  # הוספת פונקציה להצגת השדות
        self.Find_a_location.setEnabled(False)  # הכפתור מנוטרל בהתחלה
        button_layout.addWidget(self.Find_a_location)

        # שדה הזנה ל-LAT (קו רוחב)
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90, 90)  # הגבלת תחום קלט ל-LAT
        self.lat_input.setPrefix("LAT: ")
        self.lat_input.setDecimals(6)  # הגדרת 6 ספרות אחרי הנקודה
        self.lat_input.setFixedSize(120, 40)  # הגדרת גודל מינימלי
        self.lat_input.setVisible(False)  # הוסתר כברירת מחדל
        button_layout.addWidget(self.lat_input)

        # שדה הזנה ל-LON (קו אורך)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180, 180)  # הגבלת תחום קלט ל-LON
        self.lon_input.setPrefix("LON: ")
        self.lon_input.setDecimals(6)  # הגדרת 6 ספרות אחרי הנקודה
        self.lon_input.setFixedSize(120, 40)  # הגדרת גודל מינימלי
        self.lon_input.setVisible(False)  # הוסתר כברירת מחדל
        button_layout.addWidget(self.lon_input)

        # כפתור "שמור ושלח"
        self.save_send_button = QPushButton("שמור ושלח", self)
        self.save_send_button.setFixedSize(80, 40)
        self.save_send_button.setVisible(False)  # הכפתור מוסתר כברירת מחדל
        self.save_send_button.clicked.connect(self.save_and_send)
        button_layout.addWidget(self.save_send_button)

        # שדה להזנת שם העיר
        self.city_name_input = QLineEdit()
        self.city_name_input.setPlaceholderText("הכנס שם עיר")
        self.city_name_input.setVisible(False)  # הוסתר כברירת מחדל
        self.city_name_input.setFixedSize(120, 40)  # הגדרת גודל מינימלי
        button_layout.addWidget(self.city_name_input)

        # כפתור "שמור ושלח" עבור שם עיר
        self.save_send_city_button = QPushButton("שמור ושלח", self)
        self.save_send_city_button.setFixedSize(80, 40)
        self.save_send_city_button.setVisible(False)  # הכפתור מוסתר כברירת מחדל
        self.save_send_city_button.clicked.connect(self.save_and_send_city)
        button_layout.addWidget(self.save_send_city_button)

        # כפתור להוספת שכבת מפת חום
        self.heatmap_button = QPushButton("הפעל מפת חום")
        self.heatmap_button.setFixedSize(120, 40)
        self.heatmap_button.setEnabled(False)  # הוסתר כברירת מחדל
        self.heatmap_button.clicked.connect(self.toggle_heatmap)
        self.heatmap_button.clicked.connect(self.enable_heatmap_layer)
        layout = QVBoxLayout()
        layout.addWidget(self.map_view)
        layout.addWidget(self.heatmap_button)
        button_layout.addWidget(self.heatmap_button)

        # יצירת Layout אופקי (Horizontal Layout)
        icon_layout = QHBoxLayout()  # Layout שמיועד לסדר אלמנטים במאוזן

        # כפתור עם אייקון פעמון
        self.toggle_log_button = QPushButton(self)  # יצירת כפתור פעמון
        self.toggle_log_button.setFixedSize(25, 25)  # גודל הכפתור
        self.toggle_log_button.setIconSize(QSize(25, 25))  # גודל האייקון
        bell_icon = QIcon(os.path.join("ICONS", "bell_icon.png"))  # טעינת אייקון הפעמון
        self.toggle_log_button.setIcon(bell_icon)  # הצמדת האייקון לכפתור
        self.toggle_log_button.clicked.connect(self.toggle_log_view)  # חיבור לפונקציה להצגת/הסתרת הלוגים
        icon_layout.addWidget(self.toggle_log_button)  # הוספת כפתור הפעמון ל-Layout האופקי

        # כפתור לשמירת הלוגים
        self.save_log_button = QPushButton(self)  # יצירת כפתור שמירת הלוגים
        self.save_log_button.setFixedSize(25, 25)  # גודל הכפתור
        self.save_log_button.setIconSize(QSize(25, 25))  # גודל האייקון
        save_icon = QIcon(os.path.join("ICONS", "save_log.png"))  # טעינת אייקון שמירת הלוגים
        self.save_log_button.setIcon(save_icon)  # הצמדת האייקון לכפתור
        self.save_log_button.clicked.connect(self.save_logs_to_file)  # חיבור לפונקציה לשמירת הלוגים
        icon_layout.addWidget(self.save_log_button)  # הוספת כפתור שמירת הלוגים ל-Layout האופקי

        # הוספת ה-Layout האופקי ל-Layout הראשי של הכפתורים
        button_layout.addLayout(icon_layout)  # שילוב ה-Layout האופקי ב-Layout האנכי (button_layout)

        # תיבת טקסט להצגת הלוגים
        self.log_area = QTextEdit()
        self.log_area.setVisible(False)  # תיבת הלוגים מוסתרת בהתחלה
        button_layout.addWidget(self.log_area)

        button_widget = QWidget()  # יצירת וידג'ט עבור הכפתורים
        button_widget.setLayout(button_layout)  # הגדרת ה-Layout עבור הוידג'ט

        main_layout = QHBoxLayout()

        # QSplitter שמחלק את החלון בין המפה לכפתורים
        self.splitter = QSplitter(Qt.Horizontal)  # יצירת QSplitter אופקי
        self.splitter.addWidget(self.map_view)  # הוספת המפה ל-QSplitter
        self.splitter.addWidget(button_widget)  # הוספת כפתורים ל-QSplitter
        self.splitter.setSizes([1300, 5])  # קביעת גודל התחלתי כך שהמפה תתפוס את רוב השטח

        # המפה תתפוס את כל השטח הפנוי
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        main_layout.addWidget(self.splitter)  # הוספת ה-QSplitter ל-Layout הראשי
        self.map_view.setStyleSheet("QWebEngineView { min-width: 100%; min-height: 100%; }")

        container = QWidget()  # יצירת וידג'ט מרכזי
        container.setLayout(main_layout)  # הגדרת ה-Layout עבור הוידג'ט המרכזי
        self.setCentralWidget(container)  # קביעת הוידג'ט המרכזי כחלק מהחלון

    def create_map_from_file(self):
        """ יצירת המפה וטעינתה לתצוגה. """
        self.log_action("יצירת המפה התחילה.")
        create_map()  # יצירת המפה מקובץ ה-MAP
        self.load_map()  # טעינת המפה
        self.log_action("המפה נוצרה בהצלחה.")
        self.Find_a_location.setEnabled(True)  # הפעלת כפתור דקירת נ.צ לאחר יצירת המפה
        self.heatmap_button.setEnabled(True)

    def load_map(self):
        """ טעינת המפה לתוך תצוגת QWebEngineView. """
        if os.path.exists(self.map_file):  # אם קובץ המפה קיים
            self.map_view.setUrl(QUrl.fromLocalFile(self.map_file))  # הצגת המפה בתצוגה
            self.log_action("המפה נטענה בהצלחה.")
        else:
            self.log_action("שגיאה: קובץ המפה לא נמצא.")

    def toggle_servers(self):
        """ ניהול הפעלת וכיבוי השרתים בכפתור אחד """
        if self.servers_running:
            # אם השרתים פעילים, נעצור אותם
            self.stop_servers()
            self.servers_running = False
            self.manage_servers_button.setText("הפעל שרתים")
            self.manage_servers_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        else:
            # אם השרתים כבויים, נפעיל אותם
            self.start_servers()
            self.servers_running = True
            self.manage_servers_button.setText("עצור שרתים")
            self.manage_servers_button.setStyleSheet("background-color: green; color: white; font-weight: bold;")

    def start_servers(self):
        """ הפעלת שרתי GeoServer ו-WeatherServer. """
        try:
            self.log_action("הפעלת GeoServer התחילה.")
            self.geo_server_process = subprocess.Popen(["python", "geo_server.py"])  # הפעלת GeoServer
            self.log_process_action("GeoServer", "הפעלת", success=True)  # התעדות לאחר הפעלת השרת
            self.log_action("GeoServer הופעל בהצלחה.")
        except Exception as e:
            self.log_process_action("GeoServer", "הפעלת", success=False)  # התעדות במקרה של שגיאה
            self.log_action(f"שגיאה בהפעלת GeoServer: {e}")

        try:
            self.log_action("הפעלת WeatherServer התחילה.")
            self.weather_server_process = subprocess.Popen(["python", "weather_server.py"])  # הפעלת WeatherServer
            self.log_action("WeatherServer הופעל בהצלחה.")
        except Exception as e:
            self.log_action(f"שגיאה בהפעלת WeatherServer: {e}")

        self.load_map_button.setEnabled(True)

    def stop_servers(self):
        """ עצירת שרתי GeoServer ו-WeatherServer. """
        try:
            if self.geo_server_process:  # אם GeoServer רץ
                self.geo_server_process.terminate()  # עצירת GeoServer
                self.geo_server_process = None
                self.log_action("GeoServer נעצר בהצלחה.")
            if self.weather_server_process:  # אם WeatherServer רץ
                self.weather_server_process.terminate()  # עצירת WeatherServer
                self.weather_server_process = None
                self.log_action("WeatherServer נעצר בהצלחה.")
        except Exception as e:
            self.log_action(f"שגיאה בעצירת השרתים: {e}")
        self.load_map_button.setEnabled(False)
        self.Find_a_location.setEnabled(False)
        self.heatmap_button.setVisible(False)

    def save_and_send(self):
        """שמור ושלח את נתוני ה-LAT ו-LON"""
        lat = self.lat_input.value()
        lon = self.lon_input.value()
        self.log_action("הנתונים נשמרו ונשלחו")

        if lat == 0 or lon == 0:
            self.log_action("נתוני קואורדינטות אינם תקינים.")
            return

        # מבנה ההודעה
        message = {"lat": lat, "lon": lon}

        # שמירת מבנה ההודעה בלוג
        try:
            with open("coordinates_log.txt", "a") as log_file:
                log_file.write(f"{message}\n")
            self.log_action(f"מבנה ההודעה נשמר: {message}")
        except Exception as e:
            self.log_action(f"שגיאה בשמירת מבנה ההודעה: {e}")
            return

        # שליחת ההודעה לשרת
        try:
            url = f"http://localhost:5002/weather?lat={lat}&lon={lon}"
            response = requests.get(url)

            if response.status_code == 200:
                weather_data = response.json()
                self.log_action(f"נתוני מזג האוויר התקבלו: {weather_data}")
                self.display_weather_on_map(lat, lon, weather_data)
            else:
                self.log_action(f"שגיאה בשליחת הבקשה: {response.status_code}")
        except Exception as e:
            self.log_action(f"שגיאה בשליחת ההודעה לשרת: {e}")

    def toggle_lat_lon_inputs(self):
        """ הצגת או הסתרת שדות ה-LAT, LON ושם עיר """
        # שינוי מצב שדות הקלט
        is_lat_lon_visible = not self.lat_input.isVisible()
        is_city_visible = not self.city_name_input.isVisible()

        # עדכון מצב שדות הקלט
        self.lat_input.setVisible(is_lat_lon_visible)
        self.lon_input.setVisible(is_lat_lon_visible)
        self.city_name_input.setVisible(is_city_visible)

        # עדכון מצב כפתור "שמור ושלח" לפי סוג הקלט
        self.save_send_button.setVisible(is_lat_lon_visible)  # כפתור עבור LAT/LON
        self.save_send_city_button.setVisible(is_city_visible)  # כפתור עבור שם עיר

        # חיבור/ניתוק פונקציה לדקירת נ.צ
        if is_lat_lon_visible:
            self.Find_a_location.clicked.connect(self.submit_coordinates)  # חיבור לפונקציה להוספת קואורדינטות
            self.log_action("בוצע חיבור לפונקציה לדקירת נ.צ.")
        else:
            self.Find_a_location.clicked.disconnect()  # ניתוק הפונקציה אם השדות מוסתרים
            self.log_action("בוצע ניתוק מפונקציה לדקירת נ.צ.")

    def save_and_send_city(self):
        """שמור ושלח את שם העיר"""
        city_name = self.city_name_input.text().strip()
        self.log_action("הוקלד ונשלח שם של עיר")

        if not city_name:
            self.log_action("שם העיר אינו תקין.")
            return

        # שמירת שם העיר בלוג
        try:
            with open("city_log.txt", "a", encoding="utf-8") as log_file:  # שמירת הלוג עם תמיכה בעברית
                log_file.write(f"City: {city_name}\n")
            self.log_action(f"שם העיר נשמר: {city_name}")
        except Exception as e:
            self.log_action(f"שגיאה בשמירת שם העיר: {e}")
            return

        # קידוד שם העיר ל-URL
        encoded_city_name = urllib.parse.quote(city_name)

        # שליחת הבקשה לשרת
        try:
            url = f"http://localhost:5002/weather?region={encoded_city_name}"
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
        מפעיל שכבת מפת חום על המפה
        """
        QMessageBox.information(self, "מפת חום", "שכבת מפת חום נוספה למפה.")

    def toggle_log_view(self):
        """ שינוי מצב תיבת הלוגים (הצגה או הסתרה). """
        if self.log_area.isVisible():  # אם תיבת הלוגים מוצגת
            self.log_area.setVisible(False)  # הסתרת תיבת הלוגים
            self.log_action("תיבת הלוגים הוסתרה.", is_success=False)
        else:
            self.log_area.setVisible(True)  # הצגת תיבת הלוגים
            self.log_action("תיבת הלוגים הוצגה.", is_success=True)

    def toggle_heatmap(self):
        # הרצת הפונקציה toggleHeatmap ב-JavaScript
        self.map_view.page().runJavaScript("toggleHeatmap();")

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

        # בניית מחרוזת מיקום (אינה בשימוש ישיר, אך נשארת לצורך תאימות)
        location = f"{lat},{lon}"

        # שליחת בקשה לשרת לקבלת נתוני מזג אוויר
        weather_data = fetch_weather_data(location)

        # אם התקבלה תשובה מהשרת
        if weather_data:
            self.log_action(f"נתוני מזג האוויר התקבלו: {weather_data}")

            # קבלת הקואורדינטות מהתשובה
            lat = weather_data.get("coord", {}).get("lat")  # קבלת קו רוחב
            lon = weather_data.get("coord", {}).get("lon")  # קבלת קו אורך

            # בדיקה אם הקואורדינטות התקבלו
            if lat is not None and lon is not None:
                self.display_weather_on_map(lat, lon, weather_data)
            else:
                self.log_action(f"לא התקבלו קואורדינטות עבור העיר {weather_data.get('name', 'לא ידוע')}",
                                is_success=False)
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
            # הכנת טקסט להצגה על גבי הסמן
            weather_info = f"Temperature: {weather_data['temperature']}°C, Weather: {weather_data['weather']}"

            # רישום בלוג של נתוני מזג האוויר שמוצגים
            self.log_action(f"מציג מזג אוויר: {weather_info}")

            # קוד JavaScript להצגת סמן (Marker) במיקום המרכזי
            js_code_marker = f"""
             var marker = new google.maps.Marker({{
                 position: {{ lat: {lat}, lng: {lon} }},
                 map: map,
                 title: "מזג אוויר: {weather_data['weather']}, טמפרטורה: {weather_data['temperature']}°C"
             }});

             var infowindow = new google.maps.InfoWindow({{
                 content: "קו רוחב: {lat}, קו אורך: {lon}<br>מזג אוויר: {weather_data['weather']}<br>טמפרטורה: {weather_data['temperature']}°C"
             }});

             infowindow.open(map, marker);
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

                # קוד JavaScript ליצירת מלבן שמייצג את גבולות העיר
                js_code_polygon = f"""
                        var cityBounds = new google.maps.Rectangle({{
                            bounds: {{
                                north: {ne['lat']},
                                south: {sw['lat']},
                                east: {ne['lng']},
                                west: {sw['lng']}
                            }},
                            editable: false,
                            draggable: false,
                            strokeColor: '#FF0000',  // צבע הקו של המלבן
                            strokeOpacity: 0.8,      // שקיפות הקו
                            strokeWeight: 2,         // עובי הקו
                            fillColor: '#FF0000',    // צבע המילוי
                            fillOpacity: 0.35,       // שקיפות המילוי
                            map: map                 // הצגת המלבן על המפה
                        }});
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

            url = f"http://localhost:5002/weather?region={location}"
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
