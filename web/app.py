# -*- coding: utf-8 -*-
"""
app.py — נקודת-הכניסה היחידה שVercel מצפה לה תחת "Flask framework" (זוהה אוטומטית לפי שם
הקובץ, ר' https://vercel.com/docs/frameworks/backend/flask): "Vercel looks for a Flask
instance named app at supported entrypoints" — app.py הוא אחד מהם, בשורש web/.

נמצא בדיפלוי אמיתי (לא בתכנון): שלושה קבצים נפרדים תחת api/ שכל אחד הגדיר app משלו
גרמו ל-FLASK_ENTRYPOINT_NOT_FOUND (Vercel לא ידע איזה מהשלושה הוא "האפליקציה") — ר'
MAPS-GUI_SRS.md §3.26. הפתרון: geo.py/weather.py/flight.py תחת api/ הוסבו ל-Flask
Blueprints (geo_bp/weather_bp/flight_bp, לא Flask(__name__) עצמאי) — כל הלוגיקה/הנתיבים
שלהם נשארו זהים ב-100%, רק נרשמים כאן על app יחיד במקום להיות אפליקציות נפרדות.

הסדר כאן קריטי: create_app() (כולל load_dotenv) חייב לרוץ *לפני* ייבוא ה-blueprints,
כי flight.py קורא FR24_TOKEN/USER/PASS ברמת-המודול (בזמן הייבוא עצמו, לא בתוך פונקציה).
"""
import os
import sys

from flask import send_from_directory  # מגיש את public/index.html ישירות, ר' route '/' למטה

# מוסיף את web/lib/ ו-web/api/ ל-sys.path — כל שלושת ה-blueprint-modules מייבאים
# מודולים מ-lib/ (server_common, notam_drones וכו') בלי קידומת חבילה, כמו בדסקטופ
_WEB_DIR = os.path.dirname(os.path.abspath(__file__))
_PUBLIC_DIR = os.path.join(_WEB_DIR, 'public')  # נבנה ע"י build_web.py בזמן ה-build ב-Vercel
sys.path.insert(0, os.path.join(_WEB_DIR, 'lib'))
sys.path.insert(0, os.path.join(_WEB_DIR, 'api'))

from server_common import create_app  # noqa: E402 — אחרי שינוי sys.path, בכוונה

app = create_app(__name__)  # טוען .env (כולל מפתחות/טוקן FR24) לפני ייבוא ה-blueprints למטה

from geo import geo_bp  # noqa: E402
from weather import weather_bp  # noqa: E402
from flight import flight_bp  # noqa: E402

app.register_blueprint(geo_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(flight_bp)


@app.route('/')
def index():
    # נמצא בדיפלוי אמיתי (לא בתכנון): "/" החזיר 404 כי Vercel מנתב כל בקשה ל-function הזה
    # (ר' https://vercel.com/docs/functions/runtimes/python: "routes every request to it")
    # ול-Flask לא היה route ל-"/" בכלל — ה-public/** המובנה-ב-build מיועד ל-assets חיצוניים
    # (favicon וכו'), לא תמיד "זוכה" לעקוף את ה-function לנתיב השורש. פתרון ישיר: Flask
    # עצמו מגיש את index.html שנבנה ע"י build_web.py — קובץ נגיש כי Python functions
    # ב-Vercel מכילים כל קובץ שנוצר בזמן ה-build (ר' MAPS-GUI_SRS.md §3.26, FR-D-229).
    return send_from_directory(_PUBLIC_DIR, 'index.html')


if __name__ == "__main__":
    # הפעלה מקומית לבדיקה בלבד — כל שלושת הכלים יחד, על פורט אחד (5011), בדיוק כמו שVercel
    # יריץ בפרודקשן (function יחיד). ב-Vercel לא מגיעים לכאן בכלל — רק app מיובא ישירות.
    app.run(port=5011, debug=True, threaded=True)
