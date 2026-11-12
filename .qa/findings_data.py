# -*- coding: utf-8 -*-
"""מקור-אמת יחיד לממצאי ה-QA engagement - נצרך ע"י build_findings_xlsx.py ו-build_executive_docx.py
וה-detailed report (STAGE5_FINAL_REPORT.md) כדי לא לשכפל נתונים בשלושה מקומות בנפרד."""

SEVERITY_COLORS = {
    "קריטי": "FF0000",
    "גבוה": "ED7D31",
    "בינוני": "FFC000",
    "נמוך": "A6A6A6",
}
SEVERITY_ORDER = {"קריטי": 0, "גבוה": 1, "בינוני": 2, "נמוך": 3}

FINDINGS = [
    dict(
        id="F-001", severity="גבוה", legal=True, category="אבטחה/מידע-רגיש",
        process="FlightRadar24 client (Android)",
        desc="טוקן FlightRadar24 \"Gold\" קשיח בקוד המקור, חשוף בתוך ה-APK הבנוי.",
        repro="פתיחת api_service.dart בקובץ-המקור, או decompilation של ה-APK.",
        expected="סודות אינם מגיעים לקוד-לקוח שמופץ למשתמשים.",
        actual="_fr24Token='qJOskJ9Njh...' מוגדר כקבוע-string בקוד Dart.",
        status="נכשל", location="maps-gui-android-src/lib/services/api_service.dart:193",
        requirement="MASVS-CODE-4 / CWE-798 (שימוש בפרטי-גישה קשיחים)",
        test="לא רלוונטי - ממצא-סודות, לא לוגיקה בת-בדיקה-אוטומטית (ר' secrets_scan.txt)",
        alts=[
            dict(name="העברה לשרת-ביניים", desc="Android קורא ל-backend (Desktop/Web) במקום ל-FR24 ישירות",
                 pros="טוקן אף-פעם לא מגיע למכשיר", cons="דורש רשת ל-backend גם לפיצ'ר הזה (לא offline)", scope="בינוני"),
            dict(name="env-injection+obfuscation", desc="הזרקת הטוקן בזמן build מ-env-var, לא בקוד-מקור",
                 pros="נשאר on-device, offline-יכולת נשמרת", cons="עדיין ניתן-לחילוץ ב-runtime, רק קשה-יותר", scope="קטן"),
            dict(name="הסרת FR24 מ-Android", desc="הסתפקות ב-OpenSky Network (כבר fallback קיים)",
                 pros="0 סיכון", cons="פחות מידע-מסלול (FR24 עדכני יותר)", scope="קטן"),
        ],
        recommended="א (העברה לשרת-ביניים) - עקבי עם Desktop/Web שכבר לא חושפים את הטוקן ללקוח. "
        "**הוכרע (Stage 6, 11/11/2026): נשאר כמו-שהוא בינתיים** — אושר במפורש ע\"י המשתמש. החלופה המומלצת (א) לא ניתנת-ליישום כרגע: "
        "אין backend-חי זמין (Web ירד לגמרי, ו-flightServerHost של Desktop אינו שרת-ציבורי-זמין). ישוקל מחדש אם יוקם backend מתאים.",
    ),
    dict(
        id="F-002", severity="נמוך", legal=True, category="רישוי",
        process="Chaquopy (Android, מנוע הבליסטי)",
        desc="נבדק אם רישוי Chaquopy מגביל הפצה (בדיקה חוזרת/אימות, לא ממצא פתוח).",
        repro="chaquo.com/chaquopy/chaquopy-is-now-open-source/, chaquo.com/chaquopy/license/",
        expected="רישיון ברור שתואם את אופן ההפצה המתוכנן.",
        actual="מאז גרסה 12.0.1 (2022) Chaquopy הוא MIT חינמי-לגמרי. הפרויקט ב-17.2.0. אין הגבלה.",
        status="עבר", location="maps-gui-android-src/android_settings.gradle.kts",
        requirement="בדיקת-רישוי (לא ASVS/MASVS)",
        test="לא רלוונטי",
        alts=[],
        recommended="סגור - אין פעולה נדרשת. נשאר בדוח לתיעוד-עקיבות בלבד.",
    ),
    dict(
        id="F-003", severity="נמוך", legal=True, category="רישוי",
        process="PyQt5/PyQtWebEngine (Desktop)",
        desc="רישוי כפול (GPLv3/מסחרי) - תלוי אם האפליקציה תופץ לצד-ג' בעתיד.",
        repro="riverbankcomputing.com/commercial/license-faq",
        expected="בהירות לגבי חובת-רכישת-רישיון לפני הפצה.",
        actual="חובת-GPL מופעלת רק ע\"י הפצה, לא שימוש-אישי. מצב נוכחי: תואם (לא בוצעה הפצה).",
        status="עבר", location="requirements.txt (PyQt5, PyQtWebEngine)",
        requirement="בדיקת-רישוי",
        test="לא רלוונטי",
        alts=[
            dict(name="לא להפיץ", desc="להמשיך שימוש-אישי בלבד", pros="0 עלות/סיכון", cons="אין", scope="אין"),
            dict(name="רכישת רישיון מסחרי", desc="לפני הפצה ראשונה, אם רוצים קוד-סגור", pros="מאפשר הפצה closed-source", cons="עלות כספית", scope="אין (רישוי, לא קוד)"),
        ],
        recommended="לא להפיץ כרגע (ברירת-מחדל בטוחה); לבדוק מחדש אם יתוכנן שיתוף-exe עם צד-ג'.",
    ),
    dict(
        id="F-004", severity="גבוה", legal=False, category="אבטחה",
        process="כל ה-endpoints ב-web/ (Flask serverless)",
        desc="אין auth/rate-limiting על אף endpoint - חשיפת \"denial-of-wallet\" על מפתחות Google/OpenWeather/FR24, וחסימת-WAF אפשרית על brin.iaa.gov.il.",
        repro="GET חוזר-ושונה ל-/geo_data או /weather מכל כתובת.",
        expected="הגבלת-קצב (rate-limit) בסיסית לפי IP.",
        actual="0 הגנות קיימות על אף route.",
        status="נכשל (לא-רלוונטי בפועל — Web ירד, 11/11/2026)", location="web/lib/server_common.py, web/api/*.py",
        requirement="ASVS 5.0 V4.2 (lack of rate limiting)",
        test="לא רלוונטי - דורש הקמת-תשתית (Redis/WAF), לא לוגיקה-יחידה",
        alts=[
            dict(name="Upstash Redis rate-limit", desc="שימוש-חוזר ב-Redis שכבר קיים בפרויקט (job_store/stations_store)",
                 pros="שימוש-חוזר בתשתית קיימת", cons="תלוי-אימות ש-Redis מותקן בפרודקשן בפועל", scope="בינוני"),
            dict(name="Vercel/Cloudflare WAF מובנה", desc="rate-limiting ברמת-הפלטפורמה, לא בקוד",
                 pros="0 קוד", cons="תלוי-תוכנית/תשלום בפלטפורמה", scope="קטן (קונפיגורציה בלבד)"),
            dict(name="לא לתקן כרגע", desc="להשאיר פתוח", pros="0 עבודה", cons="חשיפה נמשכת", scope="אין"),
        ],
        recommended="א (Upstash Redis) - התשתית כבר קיימת בפרויקט לכלים אחרים. "
        "**הוכרע (Stage 6, 11/11/2026): לא-רלוונטי יותר** — map.yechielalaluf.com ירד לגמרי ולא יוחזר/יועלה-ל-Vercel בעתיד (אישור מפורש של המשתמש). "
        "אין תשתית-חיה להגן יותר; אין פעולה.",
    ),
    dict(
        id="F-005", severity="גבוה", legal=True, category="נגישות",
        process="map.yechielalaluf.com (Web)",
        desc="יעד-נגישות (WCAG) תלוי בסטטוס-משפטי של האתר (שירות-ציבורי לפי החוק הישראלי, או כלי-אישי) - לא הוכרע.",
        repro="בדיקת-סטטוס משפטי (לא קוד).",
        expected="החלטה מפורשת על יעד WCAG לפני שמשקיעים בתיקון.",
        actual="לא ידוע אם האתר נחשב \"שירות ציבורי\" לעניין תקנות שוויון-זכויות/ת\"י 5568.",
        status="לא נבדק (לא-רלוונטי בפועל — Web ירד, 11/11/2026)", location="N/A - שאלה משפטית",
        requirement="WCAG 2.2 AA (אם ציבורי) / יעד-מופחת (אם אישי)",
        test="לא רלוונטי",
        alts=[
            dict(name="יעד מופחת (כלי אישי)", desc="מאמץ-סביר בלבד, לא תיקון-מקיף", pros="אין חובה-חוקית ידועה", cons="סיכון אם יתברר שהאתר כן נחשב ציבורי", scope="אין"),
            dict(name="יעד WCAG 2.x AA מלא", desc="עמידה-מלאה לפי תקנות שוויון-זכויות ות\"י 5568", pros="חוסם-סיכון משפטי", cons="פער-גדול מהמצב הנוכחי, עבודה משמעותית", scope="גדול"),
        ],
        recommended="להכריע את הסטטוס המשפטי קודם (שאלה פתוחה) - אין המלצת-ברירת-מחדל אחראית כאן. "
        "**הוכרע (Q-1 + Stage 6, 11/11/2026): לא-רלוונטי יותר** — map.yechielalaluf.com ירד לגמרי, לא יוחזר (אישור מפורש של המשתמש). השאלה המשפטית התייתרה.",
    ),
    dict(
        id="F-006", severity="גבוה", legal=False, category="פונקציונלי/ארכיטקטורה",
        process="/radar_doppler/evaluate_route/start (Web)",
        desc="מבוסס thread+dict-בזיכרון-תהליך - לא-בטוח בארכיטקטורת-serverless (Vercel). ה-thread עשוי להיקטע, וה-state לא משותף בין instances.",
        repro="קריאה ל-/radar_doppler/evaluate_route/start ואז polling ל-status בפרודקשן Vercel.",
        expected="תוצאה עקבית, כמו los_radial/radar_doppler/start שכבר הומרו ל-chunked+Redis.",
        actual="סביר-מאוד שה-endpoint הזה שבור בפרודקשן (לא נבדק אמפירית - אין גישה ל-Vercel).",
        status="לא נבדק (לא-רלוונטי בפועל — Web ירד, 11/11/2026)", location="web/api/weather.py (evaluate_route)",
        requirement="ASVS V1 (secure/resilient architecture)",
        test="לא רלוונטי - דורש סביבת-Vercel אמיתית לאימות",
        alts=[
            dict(name="המרה ל-chunked+Redis", desc="אותה תבנית כמו los_radial/radar_doppler הקיימים",
                 pros="עקביות ארכיטקטונית", cons="עבודת-קוד לא-זניחה (resample+state per-point)", scope="גדול"),
            dict(name="חסימה-סינכרונית-מלאה", desc="כמו ballistics/* - בלי job, מחשב בבקשה אחת",
                 pros="פשוט יותר", cons="סיכון-timeout במסלולים-ארוכים (maxDuration=35s)", scope="בינוני"),
            dict(name="לא לתקן - Desktop-only", desc="להשאיר רק ב-Desktop שכבר עובד", pros="0 עבודה", cons="פיצ'ר-חסר ב-Web", scope="אין"),
        ],
        recommended="א (chunked+Redis) אם הפיצ'ר חשוב ל-Web; אחרת ג. "
        "**הוכרע (Stage 6, 11/11/2026): לא-רלוונטי יותר** — Web ירד לגמרי, לא יוחזר.",
    ),
    dict(
        id="F-007", severity="גבוה", legal=False, category="תשתית",
        process="Redis (Upstash) - los_radial/radar_doppler/stations ב-Web",
        desc="לא מאומת שה-אינטגרציה עם Upstash Redis הותקנה בפועל בפרויקט ה-Vercel.",
        repro="בדיקת Vercel Dashboard > Integrations.",
        expected="Redis מותקן ומוגדר, כל ה-jobs/stations עובדים.",
        actual="לא נבדק - אין גישה לחשבון Vercel של המשתמש.",
        status="חסום (לא-רלוונטי בפועל — Web ירד, 11/11/2026)", location="web/lib/job_store.py, web/lib/stations_store.py",
        requirement="N/A",
        test="לא רלוונטי - דורש גישת-חשבון",
        alts=[],
        recommended="המשתמש צריך לבדוק בעצמו ב-Vercel Dashboard. "
        "**הוכרע (Stage 6, 11/11/2026): לא-רלוונטי יותר** — Web ירד לגמרי, לא יוחזר.",
    ),
    dict(
        id="F-008", severity="בינוני", legal=False, category="אמינות",
        process="שכבת NOTAM (3 פלטפורמות)",
        desc="scraping תלוי-WAF, פענוח regex שביר מול מבנה-HTML של brin.iaa.gov.il שעלול להשתנות.",
        repro="שינוי-מבנה באתר המקור (לא ניתן לדמות ללא תלות-רשת אמיתית).",
        expected="התאוששות-חינה/דיווח-שגיאה ברור אם המבנה משתנה.",
        actual="לא נבדק מול שינוי-מבנה אמיתי (תלוי-WAF חי).",
        status="לא נבדק", location="notam_drones.py, web/lib/notam_drones.py, api_service.dart (Android)",
        requirement="ASVS V13 (API/third-party)",
        test="לא רלוונטי - דורש mock-HTML, לא נבנה בסבב זה",
        alts=[], recommended="לא נדרשת פעולה מיידית - לנטר אם scraping מתחיל להיכשל. "
        "**הוכרע (Stage 6, 11/11/2026): accepted-risk, ללא פעולה בסבב זה** — לא נכלל ברשימת התיקונים המאושרים.",
    ),
    dict(
        id="F-009", severity="בינוני", legal=False, category="אבטחה/configuration",
        process="Flask debug=True (3 שרתי-Desktop + web/*.py)",
        desc="7 מופעי debug=True (bandit B201/HIGH) - אך ההשפעה בפועל שונה: Desktop מאזין 127.0.0.1 (מנוטר ע\"י security_checks), Web מוגן ב-if __name__=='__main__' (Vercel לא מגיע לשם).",
        repro="הרצת geo_server.py/weather_server.py/flight_server.py עם bind חיצוני.",
        expected="debug כבוי בפרודקשן; מנוטר אם מופעל.",
        actual="Desktop: מנוטר ע\"י security_checks._check_bind_exposure. Web: קוד-מת בפרודקשן.",
        status="עבר (עם הסתייגות)", location="geo_server.py:83, weather_server.py:1930, flight_server.py:332, web/app.py:57, web/api/{geo,weather,flight}.py",
        requirement="ASVS V14 (configuration) / CWE-489",
        test="לא רלוונטי - התנהגות כבר מנוטרת ע\"י security_checks.py הקיים",
        alts=[], recommended="לא נדרשת פעולה - כבר מנוטר נכון. "
        "**הוכרע (Stage 6, 11/11/2026): accepted-risk, ללא פעולה.** הערה נוספת מביקורת ASVS-L1 הפורמלית (`.qa/asvs_l1_desktop_compliance.md`): "
        "debug=True אינו מתאים כלל לדרישת-L1 ספציפית בפרקי V13/V4 שאומתו מהמקור הרשמי — לא \"כשל-L1 פורמלי\", נשאר ממצא-אבטחה פרויקטלי נפרד.",
    ),
    dict(
        id="F-010", severity="בינוני", legal=False, category="פרטיות/אבטחה",
        process="SharedPreferences (Android) - מיקומים/עמדות-שמורות",
        desc="מידע-מיקום אישי נשמר ללא הצפנה (XML רגיל), חשוף ל-adb backup/גישה-פיזית/root.",
        repro="adb backup על מכשיר עם האפליקציה מותקנת.",
        expected="מידע-מיקום רגיש מוצפן ב-Keystore.",
        actual="shared_preferences רגיל, לא EncryptedSharedPreferences.",
        status="נכשל", location="maps-gui-android-src/lib/state/map_state.dart (saveStation/loadStations)",
        requirement="MASVS-STORAGE-1",
        test="לא רלוונטי - דורש הרצה-על-מכשיר לאימות",
        alts=[
            dict(name="flutter_secure_storage", desc="מעבר ל-Keystore-backed storage למפתחות-מיקום בלבד",
                 pros="הצפנה אמיתית", cons="תלות-pub חדשה + migration לנתונים-קיימים + build חדש", scope="בינוני"),
            dict(name="להשאיר, לתעד כסיכון-מקובל", desc="כלי-אישי, לא-SaaS", pros="0 עבודה", cons="לא-עומד ב-MASVS-STORAGE", scope="אין"),
        ],
        recommended="ב (להשאיר) כברירת-מחדל לכלי-אישי; א אם מתוכננת הפצה רחבה יותר. "
        "**הוכרע (Stage 6, 11/11/2026): accepted-risk, ללא פעולה בסבב זה** — לא נכלל ברשימת התיקונים המאושרים.",
    ),
    dict(
        id="F-011", severity="בינוני", legal=False, category="פונקציונלי",
        process="/radar_doppler/cancel (Web)",
        desc="הפונקציה cancel_radar_doppler לא מחזירה ערך בסוף - Flask זורק 500 על כל קריאה.",
        repro="POST /radar_doppler/cancel?job_id=<any>",
        expected="200 {'ok': True} (כמו cancel_radial_los/cancel_los_radial).",
        actual="500 Internal Server Error (\"did not return a valid response\").",
        status="תוקן (11/11/2026)", location="web/api/weather.py:1308-1315",
        requirement="CWE-252 (unchecked return value) - פונקציונלי בלבד",
        test=".qa/tests/test_f011_radar_cancel_return.py",
        alts=[dict(name="הוספת return jsonify({'ok': True})", desc="תיקון חד-שורתי, מיישר עם cancel_radial_los הקיים", pros="תיקון טריוויאלי", cons="אין", scope="קטן")],
        recommended="א - התיקון היחיד הסביר. **תוקן (Stage 6, 11/11/2026)**: `return jsonify({'ok': True})` נוסף; בדיקת-השחזור עברה מ-FAIL ל-PASS.",
    ),
    dict(
        id="F-012", severity="נמוך", legal=False, category="תחזוקתיות",
        process="web/map.html (שריד build)",
        desc="קובץ 4949-שורות tracked בגיט, שריד מריצת build_web.py עם cwd שגוי (לפני תיקון FR-D-240). לא בשימוש ע\"י שום קוד.",
        repro="git ls-files | grep web/map.html; grep-אחר שימושים ב-vercel.json/app.py.",
        expected="לא קיימים קבצי-build-artifact מיותרים ב-git.",
        actual="הקובץ tracked, לא-מאוזכר בשום מקום אחר.",
        status="תוקן (11/11/2026)", location="web/map.html",
        requirement="תחזוקתיות (ISO 25010)",
        test=".qa/tests/test_f012_no_stray_webmap.py",
        alts=[dict(name="git rm + מחיקה מהדיסק", desc="ניקוי ישיר", pros="פשוט, 0 סיכון", cons="אין", scope="קטן")],
        recommended="א. **תוקן (Stage 6, 11/11/2026)**: `git rm` + מחיקה מהדיסק; בדיקת-השחזור עברה מ-FAIL ל-PASS.",
    ),
    dict(
        id="F-013", severity="נמוך", legal=False, category="רישוי",
        process="שכבות-מפה (Leaflet tiles, Desktop+Web)",
        desc="**תוקן ל-false-positive (11/11/2026, תוך ביצוע Stage 6)**: הממצא המקורי נבדק מחדש לפני תיקון-קוד ונמצא שגוי. Leaflet כבר מציג ייחוס-ODbL תקין דרך בקרת-attribution המובנית (לא מבוטלת), ו-3 שכבות-ה-tile מגדירות attribution תקין ('OpenStreetMap</a> contributors' וכו'). הבדיקה המקורית חיפשה מחרוזת-מדויקת-מדי ('OpenStreetMap contributors' בלי תג-<a> ביניים) שלא התאימה לטקסט-האמיתי.",
        repro="פתיחת המפה, בדיקת-נוכחות ייחוס גלוי.",
        expected="קרדיט-ODbL גלוי על המפה.",
        actual="**אומת ב-render חי (QWebEngineView)**: `.leaflet-control-attribution` קיים, visible=true, מכיל 'OpenStreetMap'+'OpenTopoMap'. תקין בפועל.",
        status="עבר", location="MAP.py (הגדרת שכבות-tile, שורות ~811-837)",
        requirement="OpenStreetMap ODbL attribution requirement",
        test=".qa/tests/test_f013_osm_attribution.py (תוקן לבדיקה נכונה)",
        alts=[],
        recommended="סגור - אין פעולה נדרשת. נבדק ואומת שהדרישה כבר מתקיימת.",
    ),
    dict(
        id="F-014", severity="נמוך", legal=False, category="אבטחה/תחזוקתיות",
        process="security_checks.py - סריקת סודות",
        desc="ANOTHER_API_KEY (קיים ב-.env.example) לא כלול ברשימת _SECRET_ENV_VARS הנסרקת.",
        repro="הרצת security_checks._check_secrets_leak עם ANOTHER_API_KEY דלוף בתגובת-שרת.",
        expected="הכלי מזהה את כל מפתחות-ה-.env הידועים.",
        actual="5/6 מפתחות נסרקים, ANOTHER_API_KEY חסר.",
        status="תוקן (11/11/2026)", location="security_checks.py (_SECRET_ENV_VARS)",
        requirement="Microsoft SDL - secrets detection",
        test=".qa/tests/test_f014_secret_env_vars_coverage.py",
        alts=[dict(name="הוספת השורה החסרה", desc="הוספת 'ANOTHER_API_KEY' לרשימה", pros="תיקון חד-שורתי", cons="אין", scope="קטן")],
        recommended="א. **תוקן (Stage 6, 11/11/2026)**: `\"ANOTHER_API_KEY\"` נוסף ל-`_SECRET_ENV_VARS`; בדיקת-השחזור עברה מ-FAIL ל-PASS.",
    ),
    dict(
        id="F-015", severity="נמוך", legal=False, category="קוד/type-safety",
        process="mpm/engine.py - FireParams",
        desc="target_alt: float = None - טיפוס שגוי (צ\"ל Optional[float]), תקין פונקציונלית.",
        repro="mypy mpm/ (ר' .qa/mypy_report.txt).",
        expected="0 שגיאות-mypy על טיפוסים.",
        actual="1 שגיאת assignment.",
        status="תוקן (11/11/2026)", location="mpm/engine.py:45",
        requirement="תחזוקתיות/type-safety",
        test="כבר קיים: .qa/mypy_report.txt (mypy mpm/ mpm_api.py)",
        alts=[dict(name="שינוי ל-Optional[float]", desc="+import typing.Optional", pros="תיקון טריוויאלי", cons="אין", scope="קטן")],
        recommended="א. **תוקן (Stage 6, 11/11/2026)**: `Optional[float]` + import; mypy מאושר נקי בשורה הזו.",
    ),
    dict(
        id="F-016", severity="נמוך", legal=False, category="אבטחה",
        process="mpm_api.py - Android bridge fetchers",
        desc="urlopen(url) בלי assert מפורש על scheme (http/https). URL בנוי פנימית (lat/lon מספריים), סיכון-בפועל נמוך.",
        repro="bandit B310 (ר' bandit_report.json).",
        expected="assert מפורש על scheme לפני urlopen.",
        actual="אין בדיקת-scheme.",
        status="תוקן (11/11/2026)", location="mpm_api.py:375,395",
        requirement="CWE-918 (SSRF, סיכון תיאורטי)",
        test="לא רלוונטי - כבר מתועד ב-bandit_report.json",
        alts=[dict(name="הוספת assert url.startswith('https://')", desc="הגנת-הגנה-לעומק", pros="תיקון קטן", cons="אין", scope="קטן")],
        recommended="א - נמוך-עדיפות. **תוקן (Stage 6, 11/11/2026)**: לא `assert` (bandit B101 מסמן assert כ-stripped-תחת -O) — "
        "נוסף `if not url.startswith(('http://','https://')): raise ValueError(...)` מפורש לפני כל `urlopen`, + `# nosec B310` נקי. "
        "אומת: 0 ממצאי-bandit ב-mpm_api.py, test_ballistics_api.py עדיין 10/10.",
    ),
    dict(
        id="F-017", severity="נמוך", legal=False, category="תחזוקתיות",
        process="except Exception רחב (כלל-הקוד)",
        desc="60 מופעים (ruff BLE001) - דפוס נפוץ, חלקם לגיטימיים (עטיפת-קריאות-חיצוניות), מקשה לאתר שגיאות-תכנות.",
        repro="ruff check (ר' ruff_report.json).",
        expected="except ממוקד לסוג-השגיאה הצפוי.",
        actual="except Exception גורף ב-60 מקומות.",
        status="חלקי", location="פזור ב-weather_server.py, web/api/*.py, main.py ועוד",
        requirement="תחזוקתיות (ISO 25010)",
        test="לא רלוונטי - לא נסקרו כולם לעומק",
        alts=[], recommended="סקירה ממוקדת בעתיד בקוד-ליבה (mpm_api.py, routes) - לא בהיקף הנוכחי. "
        "**הוכרע (Stage 6, 11/11/2026): נדחה-מפורש בסבב זה** — לא נכלל ברשימת התיקונים המאושרים.",
    ),
    dict(
        id="F-018", severity="נמוך", legal=False, category="שלמות-נתונים",
        process="saved_stations.json (Desktop) / SharedPreferences (Android)",
        desc="אין שדה-גרסה בפורמט - שינוי-מבנה עתידי עלול לא להיות ניתן-לזיהוי.",
        repro="בדיקת-מבנה הקובץ/ה-keys הקיימים.",
        expected="שדה '_schema_version' או דומה.",
        actual="אין.",
        status="נכשל", location="weather_server.py (/stations/save), map_state.dart (saveStation)",
        requirement="שלמות-נתונים/תאימות-לאחור",
        test="לא רלוונטי - דורש שינוי-production לתיקון",
        alts=[dict(name="הוספת _schema_version=1", desc="לכל כתיבה חדשה, טיפול-ברירת-מחדל בקריאה של קבצים-ישנים", pros="מאפשר מיגרציות עתידיות", cons="שינוי-production", scope="בינוני")],
        recommended="א - לא דחוף, לתכנן בשינוי-production עתידי. "
        "**הוכרע (Stage 6, 11/11/2026): נדחה-מפורש בסבב זה** — לא נכלל ברשימת התיקונים המאושרים.",
    ),
    dict(
        id="F-019", severity="נמוך", legal=False, category="תחזוקתיות",
        process="קבצים יתומים",
        desc="data/met_example.csv ו-weather_data.csv אינם נקראים/נכתבים ע\"י קוד פעיל (רק ע\"י maps-gui-secure/weather_tool.py הישן).",
        repro="grep גלובלי אחר שימוש בקבצים האלה.",
        expected="אין קבצי-דוגמה יתומים בפרויקט הפעיל.",
        actual="2 קבצים יתומים נמצאו.",
        status="תוקן (11/11/2026)", location="data/met_example.csv, weather_data.csv",
        requirement="תחזוקתיות",
        test="לא רלוונטי",
        alts=[dict(name="מחיקה", desc="אם אין שימוש מתוכנן", pros="ניקוי", cons="אין", scope="קטן"),
              dict(name="השארה", desc="כתיעוד-דוגמה", pros="0 עבודה", cons="בלבול עתידי", scope="אין")],
        recommended="ב (השארה) עד שיוחלט על maps-gui-secure/ בכללותו (ר' F-020). "
        "**הוכרע (Stage 6, 11/11/2026): נמחק** — `data/met_example.csv` נמחק (`git rm`). `weather_data.csv` לא נמצא בדיסק כלל (כבר לא קיים) — אין פעולה נדרשת עבורו.",
    ),
    dict(
        id="F-020", severity="נמוך", legal=False, category="תחזוקתיות",
        process="maps-gui-secure/ (תיקייה מקבילה ישנה)",
        desc="13 קבצים tracked בגיט, גרסה-ישנה-מקבילה של הפרויקט, לא ברור אם ארכיון או בשימוש.",
        repro="git ls-files maps-gui-secure/",
        expected="בהירות לגבי מעמד התיקייה.",
        actual="לא ברור, לא נחקר בעומק (מחוץ ל-scope).",
        status="עבר (הוכרע: ארכיון היסטורי, 11/11/2026)", location="maps-gui-secure/",
        requirement="תחזוקתיות",
        test="לא רלוונטי",
        alts=[], recommended="שאלה פתוחה למשתמש - ר' פרק שאלות-פתוחות. "
        "**הוכרע (Q-2 + Stage 6, 11/11/2026): ארכיון היסטורי** — להשאיר כמו-שהוא, אין פעולה.",
    ),
    dict(
        id="F-021", severity="נמוך", legal=False, category="תיעוד",
        process="MAP.py create_map() docstring",
        desc="docstring מזכיר \"CartoDB Dark Matter\" כתבנית-עיצוב, אך שכבת-הבסיס בפועל בקוד היא \"topo\" (OpenTopoMap).",
        repro="קריאת docstring מול קוד בפועל.",
        expected="תיעוד תואם התנהגות.",
        actual="פער קוסמטי.",
        status="נכשל", location="MAP.py:177 (docstring)",
        requirement="תיעוד",
        test="לא רלוונטי",
        alts=[dict(name="עדכון ה-docstring", desc="שינוי הטקסט ל'topo'", pros="תיקון טריוויאלי", cons="אין", scope="קטן")],
        recommended="א. **הוכרע (Stage 6, 11/11/2026): נדחה-מפורש בסבב זה** — לא נכלל ברשימת התיקונים המאושרים, למרות הטריוויאליות.",
    ),
    dict(
        id="F-022", severity="בינוני", legal=False, category="כיסוי-בדיקות",
        process="test_requests.py (רגרסיה מול 3 שרתי-Flask)",
        desc="38/42 TestCase קוראים בפועל ל-APIs חיצוניים אמיתיים - לא ניתן להריץ תחת מגבלת 'mock בלבד'.",
        repro="הרצת test_requests.py תוך הפעלת 3 שרתים.",
        expected="חבילת-רגרסיה מלאה שרצה תחת מגבלות-הריצה האוטונומית.",
        actual="חסום - אין mock-layer בפרויקט.",
        status="תוקן (11/11/2026)", location="test_requests.py",
        requirement="כיסוי-בדיקות (ISO 29119)",
        test="לא רלוונטי - זו הבדיקה-עצמה שחסומה",
        alts=[
            dict(name="בניית mock-layer", desc="unittest.mock.patch על requests/FlightRadar24API, תחת .qa/tests/ בלבד", pros="מאפשר כיסוי-מלא בלי קריאות-אמיתיות", cons="עבודת-קוד נוספת", scope="בינוני"),
            dict(name="אישור חד-פעמי לקריאות-אמיתיות", desc="כמו בריצה קודמת", pros="0 עבודת-mock", cons="חורג ממגבלת-הריצה הנוכחית", scope="אין"),
        ],
        recommended="א - שומר על המגבלה, עבודה חד-פעמית. "
        "**תוקן (Stage 6, 11/11/2026)**: נבנה `.qa/tests/test_requests_mocked.py` (מייבא 37 TEST_CASES קיימים מ-`test_requests.py`, לא משכפל; "
        "`unittest.mock.patch` על requests/FlightRadar24API + מגן-socket קשיח שחוסם כל חיבור-רשת-אמיתי בפועל). "
        "**תוצאה סופית: 37/37 עברו, 0 נדלגו, 0 קריאות-רשת-אמיתיות** (אומת גם ע\"י ששכבת-ההגנה על socket.connect לא הופעלה אף פעם). "
        "`test_requests.py`/`geo_server.py`/`flight_server.py` לא שונו. "
        "**באג אמיתי נמצא ותוקן תוך-כדי**: `geo_server.py` ו-`weather_server.py` שניהם עושים `import requests` — זה אותו אובייקט-מודול יחיד ב-Python, "
        "כך ששני `mock.patch` נפרדים (אחד per-מודול) דרסו זה-את-זה; תוקן ל-patch משותף אחד עם `side_effect` שמפזר לפי URL. "
        "`.qa/tests/README.md` עודכן. רגרסיה מלאה הורצה מחדש בסוף: 2/2+4/4 ירוק, exit 0 — אין נסיגה.",
    ),
    dict(
        id="F-023", severity="נמוך", legal=False, category="כיסוי-בדיקות",
        process="Mutation Testing / Fuzzing - mpm/ (ליבה אלגוריתמית)",
        desc="לא בוצע - דורש כלים חדשים (mutmut/hypothesis) + זמן-ריצה ארוך.",
        repro="N/A", expected="mutation score+fuzzing-coverage על הליבה בסיכון-גבוה.",
        actual="לא הותקן/הורץ בסבב זה.",
        status="לא נבדק", location="mpm/",
        requirement="29119-2 Dynamic Test Processes",
        test="לא רלוונטי",
        alts=[dict(name="התקנה+הרצה מוגבלת-זמן", desc="mutmut על mpm/ בלבד, timeout סביר", pros="מודד איכות-בדיקות אמיתית", cons="זמן-ריצה, כלי-חדש", scope="בינוני")],
        recommended="שאלה פתוחה - תלוי-אישור להתקנת-כלים נוספים. "
        "**הוכרע (Q-4 + Stage 6, 11/11/2026): לדלג בסבב הזה** — לא בסבב הנוכחי, יישקל בעתיד.",
    ),
    dict(
        id="F-024", severity="נמוך", legal=False, category="שרשרת-אספקה",
        process="SBOM (Software Bill of Materials)",
        desc="לא נוצר SBOM פורמלי (CycloneDX/SPDX).",
        repro="N/A", expected="קובץ SBOM תחת .qa/.",
        actual="לא נוצר - cyclonedx-py לא הותקן.",
        status="לא נבדק", location="N/A",
        requirement="שרשרת-אספקה (ISO 25010)",
        test="לא רלוונטי",
        alts=[dict(name="התקנת cyclonedx-py בסביבה מבודדת", desc="הפקת SBOM מ-requirements.txt", pros="תיעוד-תלויות פורמלי", cons="כלי-חדש", scope="קטן")],
        recommended="להוסיף בסבב-הבא אם נדרש SBOM רשמי. **הוכרע (Q-5 + Stage 6, 11/11/2026): לדלג** — אין דרישה רגולטורית פעילה.",
    ),
    dict(
        id="F-025", severity="נמוך", legal=False, category="שרשרת-אספקה",
        process="requirements.txt (Desktop+Web)",
        desc="אין lockfile מוצמד-hash (pip-compile/poetry.lock) - רק ==, build עתידי עלול להביא גרסה שונה בלי שינוי מפורש.",
        repro="N/A", expected="lockfile עם hashes.",
        actual="רק == pinning.",
        status="חלקי", location="requirements.txt, web/requirements.txt",
        requirement="שרשרת-אספקה",
        test="לא רלוונטי",
        alts=[dict(name="מעבר ל-pip-compile", desc="hash-pinned lockfile", pros="שחזוריות-build מלאה", cons="תהליך-build נוסף", scope="בינוני")],
        recommended="לא דחוף - 0 CVE נמצא כרגע בתלויות הקיימות. "
        "**אומת מחדש (Stage 6, 11/11/2026)**: `pip-audit` על שני requirements.txt — עדיין 0 CVE. מדיניות-remediation-timeframe נכתבה כתוצר-לוואי של ביקורת ASVS-L1 "
        "(ר' `.qa/asvs_l1_desktop_compliance.md`, V15.1.1) — לא lockfile, אך סוגר פער-תיעודי קשור.",
    ),
    dict(
        id="F-026", severity="בינוני", legal=False, category="נגישות",
        process="Touch targets - Web (GPS button) ו-Android (icon buttons/ידיות)",
        desc="גדלי-מגע קטנים מ-44-48dp המומלץ (GPS 30x30px ב-Web; iconSize 19-21/ידיות 16-20 ב-Android).",
        repro="מדידת גודל-רכיב בקוד (MAP.py/map_screen.dart).",
        expected="≥44x44dp/px.",
        actual="קטן יותר בשני הצדדים.",
        status="נכשל", location="MAP.py (WebGpsControl), map_screen.dart (כפתורי-אייקון)",
        requirement="WCAG 2.5.5 / Material touch-target",
        test="לא רלוונטי - דורש מדידה חזותית",
        alts=[dict(name="הגדלת hit-area (padding) בלי לשנות אייקון חזותי", desc="שמירה על עיצוב קומפקטי + הגדלת אזור-הלחיצה", pros="לא פוגע בעיצוב", cons="דורש בדיקה חוזרת של layout", scope="בינוני")],
        recommended="תלוי בהחלטת-יעד-נגישות (F-005). "
        "**הוכרע (Stage 6, 11/11/2026)**: חלק-Web (כפתור GPS) התייתר — Web ירד לגמרי, קוד-מת כעת. חלק-Android (iconSize 19-21) **עדיין חי ופתוח** — "
        "לא אושר לתיקון בסבב הזה (לא נכלל ברשימה המאושרת), נשאר ממצא-המשך בעדיפות-נמוכה.",
    ),
    dict(
        id="F-027", severity="בינוני", legal=False, category="נגישות",
        process="Web ו-Android (ARIA/Semantics)",
        desc="0 מופעי aria-*/role/tabindex ב-MAP.py, 0 Semantics מפורש ב-Android (רק tooltip חלקי).",
        repro="grep גלובלי.", expected="תגיות-נגישות על בקרות מותאמות.",
        actual="0 נמצאו.",
        status="נכשל", location="MAP.py (כל ה-L.Control), maps-gui-android-src/lib/",
        requirement="WCAG 4.1.2 / MASVS-אין-מקביל-ישיר",
        test="לא רלוונטי",
        alts=[], recommended="תלוי בהחלטת-יעד-נגישות (F-005). "
        "**הוכרע (Stage 6, 11/11/2026)**: חלק-Web התייתר — Web ירד לגמרי. חלק-Android **נדחה-מפורש בסבב זה** — לא נכלל ברשימת התיקונים המאושרים, נשאר פתוח.",
    ),
    dict(
        id="F-028", severity="נמוך", legal=False, category="רישוי",
        process="FlightRadar24API (לא-רשמי)",
        desc="שימוש בחבילה לא-רשמית ל-FR24 - תנאי-השימוש (ToS) של FR24 לגבי שימוש-לא-רשמי לא נבדקו ישירות.",
        repro="קריאת ToS של flightradar24.com.",
        expected="בהירות-רישוי.",
        actual="לא נבדק.",
        status="לא נבדק", location="flight_server.py, web/api/flight.py",
        requirement="בדיקת-ToS",
        test="לא רלוונטי",
        alts=[], recommended="לא דחוף - שימוש קיים כבר זמן-רב בפרויקט. **הוכרע (Stage 6, 11/11/2026): ללא פעולה** — לא נכלל ברשימת התיקונים המאושרים.",
    ),
    dict(
        id="F-029", severity="נמוך", legal=False, category="תיעוד",
        process=".qa/asvs_l1_desktop_compliance.md — ביקורת ASVS-L1 (Stage 6)",
        desc="ראיית-התאמה של V13.4.1 ('אף route לא מגיש קבצים-סטטיים... כל ה-routes מחזירים JSON מחושב') אינה מדויקת: "
             "web/app.py:51 מגיש בפועל קובץ-סטטי ישירות (send_from_directory(_PUBLIC_DIR,'index.html')). "
             "המסקנה (עומד) נכונה בפועל מסיבה אחרת — שם-הקובץ קבוע-בקוד (לא מגיע מ-request), ו-_PUBLIC_DIR הוא web/public/ (לא שורש-הריפו, .git לא נגיש משם) — "
             "אבל הראיה הכתובה בביקורת סותרת את מה ש-grep מראה בפועל, מה שמחליש את מהימנות המסמך כולו עבור קורא שמאמת.",
        repro="grep -n \"send_from_directory\" web/app.py מול הראיה בשורה 70 של asvs_l1_desktop_compliance.md.",
        expected="כל ראיה בביקורת-תאימות פורמלית נבדקת ב-grep/קריאה בפועל לפני כתיבה, לא רק מוסקת-מהזיכרון.",
        actual="נמצאה סתירה אחת (V13.4.1) בין הראיה הכתובה למצב-הקוד בפועל, אותרה ע\"י סריקה-חוזרת (round 4).",
        status="נכשל (ממצא חדש, ריצה 4, 12/11/2026)", location=".qa/asvs_l1_desktop_compliance.md (שורה ~70, V13.4.1)",
        requirement="דיוק-תיעוד / מהימנות ביקורת",
        test="לא רלוונטי - תיקון-תיעוד ישיר",
        alts=[
            dict(name="תיקון טקסט-הראיה בלבד", desc="לנסח מדויק: 'route אחד (web/app.py:/) מגיש index.html, אך שם-הקובץ קבוע-בקוד ולא מגיע מקלט-משתמש, ו-_PUBLIC_DIR נפרד משורש-הריפו - .git לא נגיש משם'",
                 pros="מדויק, תיקון חד-שורתי, המסקנה (עומד) לא משתנה", cons="אין", scope="קטן"),
        ],
        recommended="א - תיקון-טקסט בלבד, לא משנה סטטוס V13.4.1.",
    ),
    dict(
        id="F-030", severity="בינוני", legal=False, category="כיסוי-בדיקות/אמינות",
        process=".qa/tests/run_regression.py",
        desc="subprocess.run() (שורה 33) ל-6 קבצי-הבדיקה נקרא בלי פרמטר timeout. זמן-ריצה כולל של החבילה נמדד "
             "לא-יציב מאוד בין הרצות חזרתיות של אותה חבילה דטרמיניסטית-ללא-רשת (47s/64s/87s, ואחת חרגה מ-120s) - "
             "סביר שמקור השונות הוא תזמון-תהליכים של Windows/סקירת-אנטי-וירוס על הרצת python.exe חדש בכל קריאה, לא קוד "
             "הבדיקה עצמו (נבדק ונפסל: FlightRadar24 login עטוף ב-FR24_TOKEN שמוגדר כרגע -> 0 קריאת-רשת באמת; "
             "לקוחות-Redis ב-job_store.py/stations_store.py/notam_drones.py כולם lazy - לא נקראים ב-import). "
             "בלי timeout, השערה ל'תקוע-אמיתי' (deadlock/hang עתידי בקוד-נבדק, לא רק תזמון-OS) לא תזוהה כלל - run_regression.py "
             "עצמו ייתקע לנצח, בניגוד מפורש לכלל-הפרומפט 'אל תתקע על רכיב אחד'.",
        repro="three repeated runs of `.venv/Scripts/python.exe .qa/tests/run_regression.py`, timed: 47s, 64s, 87s; "
              "a fourth concurrent 5x-loop run had one iteration exceed 120s before completing successfully.",
        expected="כל subprocess.run() בכלי-בדיקה מוגבל ב-timeout מפורש וסביר (למשל 60s לכל קובץ-בדיקה בודד), עם דיווח-ברור אם נחצה.",
        actual="0 timeout מוגדר - תלוי לגמרי בכך שהתהליך-המושק עצמו תמיד יחזור.",
        status="נכשל (ממצא חדש, ריצה 4, 12/11/2026)", location=".qa/tests/run_regression.py:33",
        requirement="29119-2 (אמינות-כלי-בדיקה) / ISO 25010 Reliability",
        test="לא רלוונטי - ממצא על הכלי עצמו, לא על קוד-ייצור",
        alts=[
            dict(name="הוספת timeout מפורש ל-subprocess.run", desc="timeout=90 (או ערך-נבחר), עם try/except subprocess.TimeoutExpired שמסמן את הבדיקה הספציפית [TIMEOUT] וממשיך לשאר",
                 pros="עקבי עם כלל 'אל תתקע על רכיב אחד'; מבדיל חד-משמעית בין 'נכשל' ל'תקוע'", cons="דורש בחירת-ערך-timeout סביר שלא יתפוס false-positive בהרצה אמיתית-אך-איטית", scope="קטן"),
            dict(name="ללא שינוי", desc="להשאיר כמו-שהוא, בהינתן שכל הרצה עד כה (כולל זו) בכל זאת הסתיימה בעצמה",
                 pros="0 עבודה", cons="אין רשת-הגנה אם קוד-עתידי שנבדק באמת ייתקע", scope="אין"),
        ],
        recommended="א - timeout מפורש הוא תיקון-כלי-בדיקה טריוויאלי שמתאים ישירות לדרישת-הפרומפט עצמה.",
    ),
]

def by_severity():
    return sorted(FINDINGS, key=lambda f: SEVERITY_ORDER[f["severity"]])


OPEN_QUESTIONS = [
    dict(id="Q-1", topic="יעד-נגישות (F-005)",
         terms="WCAG = תקן-נגישות בינ\"ל. AA = רמת-עמידה נפוצה-נדרשת. 'שירות ציבורי' לפי החוק הישראלי מחייב WCAG 2.x AA.",
         options="(א) כלי-אישי → יעד מופחת, מאמץ-סביר בלבד. (ב) שירות-ציבורי → יעד WCAG 2.x AA מלא, פער-עבודה גדול מהמצב הנוכחי.",
         recommendation="תלוי בסטטוס-המשפטי בפועל של map.yechielalaluf.com - אין המלצת-ברירת-מחדל אחראית."),
    dict(id="Q-2", topic="מעמד maps-gui-secure/ (F-020)",
         terms="תיקייה מקבילה-ישנה עם 13 קבצים tracked בגיט, מבנה-דומה-לפרויקט-הראשי.",
         options="(א) ארכיון היסטורי - להשאיר כמו-שהוא. (ב) לא-בשימוש - למחוק. (ג) עדיין רלוונטי - לבדוק למה.",
         recommendation="לבדוק מה הכוונה המקורית לפני כל פעולה - לא ברור מהקוד בלבד."),
    dict(id="Q-3", topic="mock-layer ל-test_requests.py (F-022)",
         terms="mock = תחליף-מדומה לשירות-חיצוני-אמיתי, מונע קריאות-רשת-אמיתיות בבדיקות.",
         options="(א) לבנות mock-layer תחת .qa/tests/ (עבודת-קוד חד-פעמית, לא-production). (ב) אישור חד-פעמי לקריאות-אמיתיות (כמו בריצה קודמת).",
         recommendation="א - שומר על מגבלת-הריצה באופן בר-קיימא לריצות עתידיות."),
    dict(id="Q-4", topic="Mutation Testing / Fuzzing (F-023)",
         terms="Mutation Testing: משנה את הקוד בכוונה ובודק אם הבדיקות תופסות את השינוי. Fuzzing: מזין קלט-אקראי-שבור כדי לאתר קריסות.",
         options="(א) להתקין mutmut/hypothesis ב-.qa/.venv ולהריץ על mpm/ בלבד, בהגבלת-זמן. (ב) לדלג בסבב הזה.",
         recommendation="א, אם יש תקציב-זמן - mpm/ היא הליבה האלגוריתמית בסיכון-הגבוה ביותר בפרויקט."),
    dict(id="Q-5", topic="הפקת SBOM פורמלי (F-024)",
         terms="SBOM = Software Bill of Materials - רשימת-רכיבים פורמלית (CycloneDX/SPDX) לשרשרת-האספקה.",
         options="(א) להתקין cyclonedx-py ב-.qa/.venv ולהפיק. (ב) לדלג - אין דרישה רגולטורית ידועה כרגע.",
         recommendation="ב (לדלג) - אין דרישה פעילה, להוסיף רק אם יידרש."),
    dict(id="Q-6", topic="העברת .qa/tests/ לתיקיית-הבדיקות הרגילה של הפרויקט",
         terms="הפרומפט מציע כברירת-מחדל שהבדיקות נכתבות תחת .qa/tests/ בלבד, והעברה לתיקיית-הבדיקות הסטנדרטית (tests/) מוצעת בדוח אך לא מבוצעת בלי אישור.",
         options="(א) להעביר - משתלב עם tests/self_test.py הקיים. (ב) להשאיר תחת .qa/ - מבודד מקוד-הייצור.",
         recommendation="א, אם ברצונך שהבדיקות האלה יהיו חלק קבוע מהרגרסיה הרגילה של הפרויקט (יחייב commit)."),
]
# פרשנות Stage 6 (11/11/2026) ל-Q-6: המשתמש לא ענה ישירות על Q-6 בטופס, אך RUN_DECISIONS #7 (לא לשנות) נותר ללא "change" מפורש -
# פורש כהנחה-בעקיפין: הבדיקות (run_regression.py, test_f0*.py, test_requests_mocked.py) נשארות תחת .qa/tests/ בלבד, לא מועברות ל-tests/
# הרגיל ולא מחויבות כחלק מחבילת-הבדיקות הסטנדרטית של הפרויקט. דורש אישור-בדיעבד מהמשתמש אם ההנחה שגויה.

RUN_DECISIONS = [
    dict(num="1", decision="Stage 0 (מיפוי) לא הורץ מחדש בריצה זו - נעשה שימוש חוזר בדוחות מהריצה הקודמת.",
         rationale="המתודולוגיה שלהם (קריאת-קוד בלבד, 0 רשת-חיצונית, 0 התקנת-כלים) עמדה כבר בכל המגבלות; הקוד לא השתנה."),
    dict(num="2", decision="יעד-אבטחה Web: ASVS L1 מעשי, L2 שאיפה (לא L3).",
         rationale="אין משתמשים/הזדהות כיום; יש מפתחות-API משולמים וחשיפת-scraping שמצדיקים מעבר ל-L1 בסיסי. "
         "**התייתר (Stage 6, 11/11/2026): map.yechielalaluf.com ירד לגמרי ולא יוחזר/יועלה-ל-Vercel בעתיד (אישור מפורש של המשתמש) — אין יותר תשתית-Web חיה שהחלטה הזו חלה עליה.**"),
    dict(num="3", decision="יעד-אבטחה Android: MASVS-L1+P (לא L2/R).",
         rationale="אפליקציה צרכנית, מידע-מיקום אישי מצדיק +P; אין יריב-עם-גישה-פיזית-מתוחכם בסבירות גבוהה שמצדיק L2/R."),
    dict(num="4", decision="יעד-אבטחה Desktop: אימוץ-חלקי של ASVS + Microsoft SDL, לא עמידה פורמלית.",
         rationale="ASVS/MASVS לא נועדו ל-desktop-tool מקומי מטבעם. "
         "**שונה (Stage 6, 11/11/2026, בקשה מפורשת של המשתמש): הורחב לעמידה פורמלית מלאה ב-ASVS 5.0 Level 1.** "
         "ביקורת שיטתית בוצעה מול 30 דרישות-L1 רלוונטיות (פרקים V1,V2,V4,V5,V11,V12,V13,V14,V15, מאומתות ישירות מהמקור הרשמי) — "
         "תוצאה: 14 עומד, 13 לא-רלוונטי-לארכיטקטורה, 2 מגבלה-חיצונית-מתועדת, 1 נסגר כתוצר-לוואי (מדיניות-תיעוד). 0 ממצאי-L1 פתוחים "
         "שדורשים תיקון-קוד (הפער היחיד שנמצא, HTTP→HTTPS ל-OpenWeatherMap, תוקן ב-Stage 6 עצמו). ר' `.qa/asvs_l1_desktop_compliance.md`."),
    dict(num="5", decision="הנחת-פרסום: כן, יש היבט-פרסום (לפי כלל-ברירת-המחדל 'אם אין ודאות, הנח שכן').",
         rationale="Web פרוס פומבית בדומיין אמיתי; APK עשוי להיות משותף."),
    dict(num="6", decision="test_requests.py סומן 'חסום' ולא הורץ עם קריאות-רשת-אמיתיות.",
         rationale="38/42 מה-TestCase קוראים בפועל ל-APIs חיצוניים - מפר את מגבלת 'mock בלבד' של הריצה הזו."),
    dict(num="7", decision="4 בדיקות-שחזור (F-011/012/013/014) נכתבו ונבדקו תחת .qa/tests/ - לא הועברו ל-tests/ הרגיל.",
         rationale="לפי ברירת-המחדל המפורשת בפרומפט - העברה מוצעת בדוח, לא מבוצעת בלי אישור (ר' Q-6)."),
    dict(num="8", decision="ריצה רביעית (12/11/2026): Stage 0 לא מופה מחדש מאפס - נעשה שימוש-חוזר במיפוי הקיים "
         "(MAPS-GUI_SRS.md/README.md + stage0_*.md), עם אימות-ממוקד של כל מה שהשתנה מאז Stage 6 בלבד "
         "(6 קבצי-production ששונו, 2 קבצים שנמחקו, 2 תוצרי-QA חדשים).",
         rationale="Stage 6 היה סבב-תיקונים ממוקד (8 תיקוני-באג טריוויאליים + 2 תוצרי-QA), לא הוספת-פיצ'ר/תהליך חדש - "
         "אין משטח-תקיפה/UI/third-party-inventory חדש שדורש מיפוי-מלא-חזרה. אומת בפועל (לא רק הונח): git diff מלא על כל "
         "קובץ-production ששונה, grep-ים ישירים לאימות כל טענת-F-029/F-030, הרצה-חוזרת 8+ פעמים של כל חבילת-הרגרסיה."),
    dict(num="9", decision="ריצה רביעית: bandit/ruff/mypy/pip-audit הורצו מחדש על כל העץ (לא רק על הקבצים-ששונו), "
         "עם השוואת-delta מדויקת (לא רק 'מספר כולל') מול דוחות-ה-baseline של ריצה 3.",
         rationale="מספר כולל גולמי (למשל ruff 260→370) יכול להטעות אם לא מפרקים לפי קובץ/שורה - בפועל כל ה-370 "
         "מתפרש: 262 production (כולל 2 נ pretty-תמימים שנגרמו ע\"י התיקון של F-015 עצמו - I001/UP045, 0 ממצאים אמיתיים-חדשים) "
         "+ 108 בקבצי .qa/*.py שלא היו קיימים בזמן ה-baseline המקורי של ריצה 3 (קוד-QA-tooling, לא production)."),
]
