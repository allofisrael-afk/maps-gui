import os
import json  # הזרקת נתונים סטטיים (אזורי תיאום, קטגוריות NOTAM) כליטרלי JS — ר' בהמשך
from dotenv import load_dotenv  # טעינת משתני סביבה (נשמר לתאימות עתידית)
from uas_coordination_zones import UAS_COORDINATION_ZONES  # נתוני "אזורי תיאום כטב"ם" — סטטיים, לא נשלפים בזמן ריצה
from notam_categories import NOTAM_CATEGORIES  # 7 קטגוריות סיווג NOTAM (id/label/color) — סטטי, ר' notam_categories.py
from airport_ctr_zones import AIRPORT_CTR_ZONES  # גבולות CTR קבועים של שדות תעופה, ממקור AIP רשמי — ר' airport_ctr_zones.py

load_dotenv()

def create_map():
    """
    פונקציה ליצירת קובץ HTML של המפה עם Leaflet.js ו-OpenStreetMap.
    ערכת נושא: CartoDB Dark Matter — חינמי לחלוטין, ללא מפתח API.
    תומך בעברית מובנית לישראל, heatmap, מסלולי טיסה וסמני מזג אוויר.
    """
    map_file = "map.html"  # שם קובץ הפלט
    # JSON של אזורי התיאום וקטגוריות ה-NOTAM — מוזרקים פעם אחת כליטרלי JS קבועים (לא fetch בזמן ריצה, נתונים סטטיים)
    coord_zones_json = json.dumps(UAS_COORDINATION_ZONES, ensure_ascii=False)
    notam_categories_json = json.dumps(NOTAM_CATEGORIES, ensure_ascii=False)
    airport_ctr_zones_json = json.dumps(AIRPORT_CTR_ZONES, ensure_ascii=False)  # גבולות CTR — ר' airport_ctr_zones.py

    with open(map_file, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מפת Leaflet משולבת</title>
    <!-- Leaflet CSS — עיצוב המפה, סמנים וחלונות מידע -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{
            height: 100vh;   /* המפה תופסת את כל גובה החלון */
            width: 100%;
        }}
        /* תצוגת קואורדינטות עכבר — פינה שמאל תחתון */
        #status {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background-color: rgba(30, 30, 46, 0.88);  /* רקע כהה שקוף — מתאים לנושא */
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            color: #cdd6f4;  /* צבע טקסט תואם ל-Catppuccin Mocha */
            z-index: 1000;
            font-family: 'Segoe UI', Arial;
            border: 1px solid #313244;
        }}
        /* ── בורר שכבות מפה — פקד מרחף בפינה ימנית-עליונה ── */
        .layer-switcher {{
            display: flex;           /* סידור הכפתורים בשורה אחת */
            flex-direction: row;     /* אופקי — כפתורים זה לצד זה */
            gap: 4px;                /* רווח בין כפתורים */
            padding: 5px;            /* ריפוד פנימי של המיכל */
            background: rgba(30,30,46,0.92);  /* רקע כהה-שקוף תואם נושא */
            border: 1px solid #45475a;        /* מסגרת עדינה */
            border-radius: 8px;               /* פינות מעוגלות */
        }}
        .layer-btn {{
            padding: 5px 10px;       /* ריפוד פנימי של כל כפתור */
            background: #313244;     /* רקע כפתור — גוון כהה */
            color: #cdd6f4;          /* צבע טקסט בהיר */
            border: 1px solid #45475a;  /* מסגרת */
            border-radius: 5px;      /* פינות מעוגלות */
            cursor: pointer;         /* סמן יד בריחוף */
            font-family: 'Segoe UI', Arial;
            font-size: 12px;
            white-space: nowrap;     /* מונע שבירת שורה בתוך הכפתור */
            transition: background 0.15s;  /* אנימציית מעבר חלקה בריחוף */
        }}
        .layer-btn:hover {{ background: #45475a; }}  /* הבהרה בריחוף */
        .layer-btn.active {{         /* כפתור הנבחר — מודגש בכחול */
            background: #89b4fa;
            color: #1e1e2e;
            font-weight: bold;
            border-color: #89b4fa;
        }}

        /* עיצוב Popup — רקע כהה תואם נושא */
        .leaflet-popup-content-wrapper {{
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 8px;
        }}
        .leaflet-popup-tip {{ background-color: #1e1e2e; }}
        .leaflet-popup-content {{ margin: 10px 14px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="status">מיקום העכבר: קו רוחב: 0.0000, קו אורך: 0.0000</div>


    <!-- Leaflet JS — ספריית המפה הראשית -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <!-- Leaflet.heat — תוסף שכבת מפת חום חינמי -->
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>

    <script>
        // תיעוד שגיאות JS לא-תפוסות דרך שינוי document.title — מגיע ל-Python ב-_on_title_changed
        // (הוסף כדי לאבחן שגיאת "Cannot read property 'getSize' of null" עם מיקום מדויק)
        window.onerror = function(message, source, lineno, colno) {{
            document.title = '__jserror__:' + message + ' @ ' + source + ':' + lineno + ':' + colno;
            return false;
        }};

        var map;                      // אובייקט המפה הראשי של Leaflet
        var heatmap;                  // שכבת מפת החום (L.heatLayer)
        var heatmapData = [];         // נתוני החום: מערך [[lat, lng, intensity], ...]
        var allMarkers = [];          // מערך כל הסמנים — מאפשר ניקוי מרוכז מ-Python
        var flightPolyline = null;    // קו מסלול הטיסה — null כשאין טיסה מוצגת
        var flightMarker   = null;    // סמן מטוס במיקום הנוכחי
        var elevationLayer  = null;    // שכבת גבהים — null כשכבויה
        var elevationActive = false;  // האם שכבת הגבהים פעילה
        var elevationPoints = [];     // נקודות גובה {{lat, lng, elevation}} לפופאפ בלחיצה
        var elevHandleState = {{ rect: null, handles: [] }};  // מלבן בחירה + 4 ידיות פינות אחרי טעינה
        var tempHeatLayer   = null;   // שכבת מפת חום טמפרטורה — null כשכבויה
        var tempSelectStart = null;   // נקודת תחילת בחירת אזור
        var tempPreviewRect = null;   // מלבן preview בזמן גרירה
        var tempSelecting   = false;  // האם המשתמש נמצא באמצע בחירת אזור
        var _tempMDHandler  = null;   // פניה ל-mousedown handler לצורך ביטול
        var tempHandleState = {{ rect: null, handles: [] }};  // מלבן בחירה + 4 ידיות פינות אחרי טעינה

        // ── מצב תצוגת שכבות ──
        var elevDisplayMode = 'heat';  // 'heat' | 'grid' | 'dots'
        var _elevRawData    = [];      // {{lat, lng, v}} ערך נורמלי 0-1
        var elevGridLayer   = null;    // שכבת grid/dots לגבהים
        var tempDisplayMode = 'heat';  // 'heat' | 'grid' | 'dots'
        var _tempRawData    = [];      // {{lat, lng, v}} ערך נורמלי 0-1
        var tempGridLayer   = null;    // שכבת grid/dots לטמפרטורה
        var _elevGrad = [[0,[0,0,204]],[0.2,[0,170,255]],[0.4,[0,255,204]],[0.6,[170,255,0]],[0.8,[255,170,0]],[1,[204,0,0]]];
        var _tempGrad = [[0,[0,0,204]],[0.25,[0,170,255]],[0.5,[0,255,204]],[0.75,[255,170,0]],[1,[204,0,0]]];

        var _mapReady = false;  // האם המפה סיימה להיטען — כפתורי LOS/רדיוס-ראייה מוצגים מיד אך מנוטרלים עד אז (map.whenReady, בהמשך)

        // ── מצב כלי קווי ראייה (LOS) ──
        var losActive   = false;  // האם מצב הוספת קו ראייה חדש פעיל (cursor crosshair)
        var losSessions = [];     // כל הסשנים שחושבו: [{{obsMk, tgtMk, lineLayers, data, color, idx}}]
        var losCurObs   = null;   // נקודת התצפית של הצמד הנוכחי (בין לחיצה 1 ל-2)
        var losCurObsMk = null;   // סמן תצפית זמני של הצמד הנוכחי (לפני בחירת היעד)
        var losPanelEl  = null;   // אלמנט פאנל גרפים תחתון
        var _losBtnEl   = null;   // הפניה לכפתור 👁 לצורך שינוי צבעו
        var _losObsInput = null; // שדה קלט גובה הצופה מעל הקרקע (מ')
        var _losTgtInput = null; // שדה קלט גובה היעד מעל הקרקע (מ')
        var _losFieldsWrapEl = null; // מיכל שדות הגובה — מוסתר עד שהכלי נבחר (אותה חוויית משתמש כמו רדיוס-ראייה)
        // פלטת צבעים — כל סשן מקבל צבע אחר לסמניו ולכותרת גרפו
        var _losPalette = ['#4488ff','#ffaa00','#cc44ff','#00cccc','#ff4488','#88ff44'];

        // ── מצב כלי רדיוס-ראייה רדיאלי (Viewshed מכומת) — כלי נפרד מ-LOS הרגיל ──
        var radialLosActive    = false; // האם מצב הצבת תצפית לרדיוס-ראייה פעיל (cursor crosshair)
        var radialLosLoading   = false; // job רץ כרגע בשרת — מונע הפעלה כפולה
        var radialLosObs       = null;  // נקודת התצפית הנוכחית (L.LatLng), null אם לא הוצבה עדיין
        var radialLosObsMk     = null;  // סמן התצפית על המפה
        var radialLosStartLn   = null;  // קו תצוגה מקדימה לאזימוט ההתחלה
        var radialLosEndLn     = null;  // קו תצוגה מקדימה לאזימוט הסיום
        var radialLosStartMk   = null;  // ידית גרירה בקצה קו ההתחלה — קובעת גם זווית וגם טווח משותף
        var radialLosEndMk     = null;  // ידית גרירה בקצה קו הסיום
        var radialLosPolygon   = null;  // L.polygon עם התוצאה המחושבת (מוחלף בכל "הפעל חישוב" מוצלח)
        var radialLosSpokes    = [];    // קווי "חישור" צבעוניים (ירוק/אדום) — אחד לכל כיוון, ר' _drawRadialLosPolygon
        var radialLosJobId     = null;  // מזהה ה-job הנוכחי בשרת, לצורך polling/ביטול
        var radialLosPollTimer = null;  // מזהה ה-setInterval של ה-polling, לצורך עצירה
        var radialLosInfoEl    = null;  // תיבת הטקסט הקטנה בתוך ה-Control (מציגה מצב/התקדמות)
        var _radialLosBtnEl      = null; // הפניה לכפתור 📡 לצורך שינוי צבעו
        var _radialPanelBodyEl   = null; // גוף הפאנל (שדות+כפתורים) — מוסתר עד שהכלי נבחר (חוויית משתמש: אייקון קודם, פרמטרים אחר כך)
        var _radialCancelBtnEl   = null; // הפניה לכפתור "בטל" לצורך הצגה/הסתרה
        var _radialRangeInput    = null; // שדה קלט טווח מרחק (ק"מ)
        var _radialMinRangeInput = null; // שדה קלט טווח מינימלי/אזור עיוור (ק"מ)
        var _radialStepInput     = null; // שדה קלט צעד זווית (מעלות)
        var _radialStartInput    = null; // שדה קלט אזימוט התחלה (מעלות)
        var _radialEndInput      = null; // שדה קלט אזימוט סיום (מעלות)
        var _radialObsInput      = null; // שדה קלט גובה הצופה (מ')
        var _radialTgtInput      = null; // שדה קלט גובה היעד/מכשול (מ')
        var _radialMarginInput   = null; // שדה קלט מרווח רכס (מעלות)
        var _radialVCenterInput  = null; // שדה קלט מרכז שדה-הראייה האנכי (מעלות) — נחשף לפי בקשת המשתמש (היה קבוע)
        var _radialVWidthInput   = null; // שדה קלט רוחב שדה-הראייה האנכי הכולל (מעלות)

        // ── מצב כלי תצפית מכ"ם דופלר (רעיוני/חינוכי) — כלי שלישי, נפרד מרדיוס-הראייה ──
        // אותו רעיון בדיוק (משקיף, כל הכיוונים, תצוגה מקדימה+ידיות גרירה, job+polling+ביטול),
        // עם תוצאה בעלת 3 צבעים במקום 2 (ר' _drawRadarDopplerResult) ופאנל גדול הרבה יותר (19 שדות)
        var radarActive    = false; // האם מצב הצבת תצפית פעיל (cursor crosshair)
        var radarLoading   = false; // job רץ כרגע בשרת — מונע הפעלה כפולה
        var radarObs       = null;  // נקודת התצפית הנוכחית (L.LatLng), null אם לא הוצבה עדיין
        var radarObsMk     = null;  // סמן התצפית על המפה
        var radarStartLn   = null;  // קו תצוגה מקדימה לאזימוט ההתחלה
        var radarEndLn     = null;  // קו תצוגה מקדימה לאזימוט הסיום
        var radarStartMk   = null;  // ידית גרירה בקצה קו ההתחלה — קובעת גם זווית וגם טווח משותף
        var radarEndMk     = null;  // ידית גרירה בקצה קו הסיום
        var radarPolygon   = null;  // L.polygon עם התוצאה המחושבת
        var radarSpokes    = [];    // קווי "חישור" תלת-צבעוניים (ירוק/כתום/אדום) — אחד-שניים לכל כיוון
        var radarJobId     = null;  // מזהה ה-job הנוכחי בשרת, לצורך polling/ביטול
        var radarPollTimer = null;  // מזהה ה-setInterval של ה-polling
        var radarInfoEl    = null;  // תיבת הטקסט הקטנה בתוך ה-Control (מציגה מצב/התקדמות/סיכום)
        var _radarBtnEl        = null; // הפניה לכפתור 🎯 לצורך שינוי צבעו
        var _radarPanelBodyEl  = null; // גוף הפאנל (שדות+כפתורים) — מוסתר עד שהכלי נבחר
        var _radarCancelBtnEl  = null; // הפניה לכפתור "בטל" לצורך הצגה/הסתרה
        // קבוצת שדות גיאומטריה — זהה במהות לרדיוס-הראייה
        var _radarRangeInput    = null; // טווח מרחק לבדיקה (ק"מ)
        var _radarMinRangeInput = null; // טווח מינימלי/אזור עיוור (ק"מ)
        var _radarStepInput     = null; // צעד זווית (מעלות)
        var _radarStartInput    = null; // אזימוט התחלה (מעלות)
        var _radarEndInput      = null; // אזימוט סיום (מעלות)
        var _radarHAntInput     = null; // גובה אנטנה (מ')
        var _radarMarginInput   = null; // מרווח רכס (מעלות)
        var _radarVCenterInput  = null; // מרכז שדה-הראייה האנכי (מעלות)
        var _radarVWidthInput   = null; // רוחב שדה-הראייה האנכי הכולל (מעלות)
        // קבוצת שדות משוואת מכ"ם — חדשים, קובעים טווח גילוי לפי פיזיקה, לא רק חסימת שטח
        var _radarPowerInput    = null; // הספק שידור שיא (קילוואט)
        var _radarGainInput     = null; // רווח אנטנה (dBi)
        var _radarFreqSelect    = null; // תדר עבודה — dropdown לפי פס (L/S/X-band)
        var _radarSensInput     = null; // רגישות מקלט (dBm)
        var _radarRcsSelect     = null; // שטח חתך רדארי (RCS) — dropdown לפי סוג מטרה
        // קבוצת שדות דופלר — חדשים, קובעים אם תנועת המטרה מתגלה בכלל
        var _radarPrfInput      = null; // תדר חזרת פולסים (Hz)
        var _radarMdvInput      = null; // מהירות רדיאלית מינימלית לגילוי (קשר)
        var _radarSpeedInput    = null; // מהירות המטרה המשוערת (קשר)
        var _radarHeadingInput  = null; // כיוון תנועת המטרה המשוער (מעלות)
        // קבוצת שדות תפוצה — חדשים, אפקט "ריבוד" מהשתקפות קרקע/ים
        var _radarLobingCheck   = null; // toggle: האם להציג את אפקט הריבוד
        var _radarReflSelect    = null; // סוג משטח מחזיר — dropdown (יבשה/ים)
        // קבוצת שדות סוג אנטנה — חדשים, בחירה בין מכ"ם גנרי למערך-מופעים (phased array)
        var _radarAntennaSelect = null; // dropdown: גנרי / מערך-מופעים
        var _radarBoresightInput = null; // כיוון-פנים של המערך (מעלות) — רלוונטי רק למערך-מופעים
        var _radarMaxScanInput   = null; // זווית סריקה מקסימלית מכיוון-הפנים (מעלות) — רלוונטי רק למערך-מופעים
        var _radarAntennaWrapEl  = null; // מיכל שני השדות הנ"ל — מוסתר/מוצג לפי הבחירה ב-_radarAntennaSelect

        // בניית אייקון עגול לסמן LOS ניתן לגרירה — עיגול מלא לתצפית, מקווקו ליעד
        function _losMarkerIcon(col, dashed) {{
            var border = dashed ? 'dashed' : 'solid';
            var opac   = dashed ? 0.6 : 0.9;
            var html   = '<div style="width:16px;height:16px;border-radius:50%;' +
                         'background:' + col + ';opacity:' + opac + ';' +
                         'border:2px ' + border + ' ' + col + ';box-sizing:border-box;cursor:grab;"></div>';
            return L.divIcon({{ className: 'los-marker-icon', html: html, iconSize: [16,16], iconAnchor: [8,8] }});
        }}

        function _normToColor(n, grad) {{
            for (var i = 1; i < grad.length; i++) {{
                if (n <= grad[i][0]) {{
                    var t = (n - grad[i-1][0]) / (grad[i][0] - grad[i-1][0]);
                    var a = grad[i-1][1], b = grad[i][1];
                    return 'rgb(' + Math.round(a[0]+t*(b[0]-a[0])) + ',' + Math.round(a[1]+t*(b[1]-a[1])) + ',' + Math.round(a[2]+t*(b[2]-a[2])) + ')';
                }}
            }}
            var last = grad[grad.length-1][1];
            return 'rgb(' + last[0] + ',' + last[1] + ',' + last[2] + ')';
        }}

        function _normToColorArr(n, grad) {{
            for (var i = 1; i < grad.length; i++) {{
                if (n <= grad[i][0]) {{
                    var t = (n - grad[i-1][0]) / (grad[i][0] - grad[i-1][0]);
                    var a = grad[i-1][1], b = grad[i][1];
                    return [Math.round(a[0]+t*(b[0]-a[0])), Math.round(a[1]+t*(b[1]-a[1])), Math.round(a[2]+t*(b[2]-a[2]))];
                }}
            }}
            return grad[grad.length-1][1].slice();
        }}

        var _elevHeatOpacity = 0.75;

        // בונה קנבס-תמונה מרשת נקודות ערך (גבהים/טמפרטורה) — משותף לשתי השכבות,
        // rawData/grad/opacity מגיעים כפרמטרים כדי לשמר בדיוק את אותה התנהגות לכל שכבה.
        function _buildValueCanvas(rawData, grad, opacity) {{
            if (rawData.length < 4) return null;
            var latSet = {{}}, lngSet = {{}};
            rawData.forEach(function(p) {{ latSet[p.lat.toFixed(6)] = 1; lngSet[p.lng.toFixed(6)] = 1; }});
            var lats = Object.keys(latSet).map(Number).sort(function(a,b){{return a-b;}});
            var lngs = Object.keys(lngSet).map(Number).sort(function(a,b){{return a-b;}});
            var nLat = lats.length, nLng = lngs.length;
            if (nLat < 2 || nLng < 2) return null;
            var dlat = (lats[nLat-1] - lats[0]) / (nLat - 1);
            var dlng = (lngs[nLng-1] - lngs[0]) / (nLng - 1);
            var vals = [];
            for (var i = 0; i < nLat; i++) {{ vals[i] = []; for (var j = 0; j < nLng; j++) vals[i][j] = 0.5; }}
            rawData.forEach(function(p) {{
                var li = Math.round((p.lat - lats[0]) / dlat);
                var lj = Math.round((p.lng - lngs[0]) / dlng);
                if (li >= 0 && li < nLat && lj >= 0 && lj < nLng) vals[li][lj] = p.v;
            }});
            var pxPerCell = 12;
            var W = Math.max(60, nLng * pxPerCell), H = Math.max(60, nLat * pxPerCell);
            var canvas = document.createElement('canvas');
            canvas.width = W; canvas.height = H;
            var ctx = canvas.getContext('2d');
            var imgData = ctx.createImageData(W, H);
            var alpha = Math.round(opacity * 255);
            var minLat = lats[0], maxLat = lats[nLat-1];
            var minLng = lngs[0], maxLng = lngs[nLng-1];
            for (var py = 0; py < H; py++) {{
                var lat = maxLat - (py / (H - 1)) * (maxLat - minLat);
                var fi = Math.max(0, Math.min(nLat - 1.0001, (lat - minLat) / dlat));
                var i0 = Math.floor(fi), i1 = i0 + 1 < nLat ? i0 + 1 : i0;
                var ti = fi - i0;
                for (var px = 0; px < W; px++) {{
                    var lng = minLng + (px / (W - 1)) * (maxLng - minLng);
                    var fj = Math.max(0, Math.min(nLng - 1.0001, (lng - minLng) / dlng));
                    var j0 = Math.floor(fj), j1 = j0 + 1 < nLng ? j0 + 1 : j0;
                    var tj = fj - j0;
                    var v = vals[i0][j0]*(1-ti)*(1-tj) + vals[i0][j1]*(1-ti)*tj +
                             vals[i1][j0]*ti*(1-tj)     + vals[i1][j1]*ti*tj;
                    var c = _normToColorArr(v, grad);
                    var idx = (py * W + px) * 4;
                    imgData.data[idx]=c[0]; imgData.data[idx+1]=c[1]; imgData.data[idx+2]=c[2]; imgData.data[idx+3]=alpha;
                }}
            }}
            ctx.putImageData(imgData, 0, 0);
            return {{ canvas: canvas, bounds: [[minLat - dlat/2, minLng - dlng/2], [maxLat + dlat/2, maxLng + dlng/2]] }};
        }}

        function _rebuildElevLayer() {{
            if (elevationLayer) {{ map.removeLayer(elevationLayer); elevationLayer = null; }}
            if (elevGridLayer)  {{ map.removeLayer(elevGridLayer);  elevGridLayer  = null; }}
            if (!_elevRawData.length) return;
            if (elevDisplayMode === 'heat') {{
                var res = _buildValueCanvas(_elevRawData, _elevGrad, _elevHeatOpacity);
                if (res) {{
                    elevGridLayer = L.imageOverlay(res.canvas.toDataURL(), res.bounds,
                        {{ opacity: _elevHeatOpacity, interactive: false }}).addTo(map);
                }}
            }} else {{
                var r = elevDisplayMode === 'grid' ? 7 : 5;
                var mk = _elevRawData.map(function(p) {{
                    return L.circleMarker([p.lat, p.lng], {{
                        radius: r, fillColor: _normToColor(p.v, _elevGrad), fillOpacity: 0.85,
                        stroke: elevDisplayMode === 'grid', color: '#333', weight: 1
                    }}).bindTooltip('גובה: ' + Math.round(p.raw) + " מ'", {{direction: 'top', offset: [0, -r]}});
                }});
                elevGridLayer = L.layerGroup(mk).addTo(map);
            }}
            elevationActive = true;
        }}

        function setElevMode(mode) {{ elevDisplayMode = mode; _rebuildElevLayer(); }}

        var _tempHeatOpacity = 0.75;

        function _rebuildTempLayer() {{
            if (tempHeatLayer) {{ map.removeLayer(tempHeatLayer); tempHeatLayer = null; }}
            if (tempGridLayer)  {{ map.removeLayer(tempGridLayer);  tempGridLayer  = null; }}
            if (!_tempRawData.length) return;
            if (tempDisplayMode === 'heat') {{
                var res = _buildValueCanvas(_tempRawData, _tempGrad, _tempHeatOpacity);
                if (res) {{
                    tempGridLayer = L.imageOverlay(res.canvas.toDataURL(), res.bounds,
                        {{ opacity: _tempHeatOpacity, interactive: false }}).addTo(map);
                }}
            }} else {{
                var r2 = tempDisplayMode === 'grid' ? 7 : 5;
                var mk2 = _tempRawData.map(function(p) {{
                    return L.circleMarker([p.lat, p.lng], {{
                        radius: r2, fillColor: _normToColor(p.v, _tempGrad), fillOpacity: 0.85,
                        stroke: tempDisplayMode === 'grid', color: '#333', weight: 1
                    }}).bindTooltip('טמפרטורה: ' + p.raw.toFixed(1) + '°C', {{direction: 'top', offset: [0, -r2]}});
                }});
                tempGridLayer = L.layerGroup(mk2).addTo(map);
            }}
        }}

        function setTempMode(mode) {{ tempDisplayMode = mode; _rebuildTempLayer(); }}

        function setTempLayerOpacity(op) {{
            _tempHeatOpacity = op;
            if (tempGridLayer) {{
                if (tempDisplayMode === 'heat') {{
                    tempGridLayer.setOpacity(op);
                }} else {{
                    tempGridLayer.eachLayer(function(l) {{ l.setStyle({{ fillOpacity: op }}); }});
                }}
            }}
        }}

        // ── אתחול המפה ──
        map = L.map('map', {{
            center: [31.7683, 35.2137],  // ירושלים כנקודת מרכז ראשונית
            zoom: 8                       // רמת זום נוחה לצפייה בישראל כולה
        }});

        // ── שכבות בסיס — מוגדרות מראש ומוחלפות לפי בחירת המשתמש ──

        // מילון שכבות הבסיס הזמינות — המפתח הוא שם קצר שנשלח מ-Python
        var baseLayers = {{

            // מפה טופוגרפית — מציגה גבהים, קווי גובה ושטח טבעי
            'topo': L.tileLayer(
                'https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png',
                {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
                    subdomains: 'abc',   // 3 שרתי CDN לאיזון עומסים
                    maxZoom: 17          // OpenTopoMap מוגבל ל-zoom 17
                }}
            ),

            // מפת רחובות — OpenStreetMap רגיל, מפורט עם בניינים ורחובות עד zoom 19
            'streets': L.tileLayer(
                'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
                {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    subdomains: 'abc',   // שרתי tile.openstreetmap.org תומכים ב-a/b/c
                    maxZoom: 19          // רמת זום גבוהה יותר מ-OpenTopoMap
                }}
            ),

            // תצלום לוויין — Esri World Imagery, חינמי וללא מפתח API, רזולוציה גבוהה
            'satellite': L.tileLayer(
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
                {{
                    attribution: '&copy; <a href="https://www.esri.com">Esri</a>, Maxar, Earthstar Geographics',
                    maxZoom: 19   // Esri מספק תמונות עד zoom 19
                }}
            )
        }};

        var currentBaseLayer = baseLayers['topo'];  // שכבת ברירת המחדל — טופוגרפית
        currentBaseLayer.addTo(map);                // הוספה ראשונית למפה

        // פונקציה להחלפת שכבת הבסיס — נקראת מהפקד על המפה
        function setBaseLayer(name) {{
            if (!baseLayers[name]) return;              // בדיקת תקינות השם שהתקבל
            map.removeLayer(currentBaseLayer);          // הסרת השכבה הנוכחית מהמפה
            currentBaseLayer = baseLayers[name];        // עדכון המשתנה לשכבה החדשה
            currentBaseLayer.addTo(map);                // הוספת השכבה החדשה למפה
            currentBaseLayer.bringToBack();             // דחיפה לתחתית — שכבות חום/גבהים/טיסות/סמנים נשארות מעל
        }}

        // ── פקד בורר שכבות — בנוי כ-Leaflet Control מותאם ──
        var LayerSwitcher = L.Control.extend({{
            options: {{ position: 'topright' }},  // מיקום: פינה ימנית-עליונה של המפה

            onAdd: function(map) {{
                // יצירת מיכל הפקד — Leaflet מצרף אותו ל-DOM אוטומטית
                var container = L.DomUtil.create('div', 'layer-switcher');

                // הגדרת הכפתורים: מפתח JS + תווית עברית + אייקון
                var layers = [
                    {{ key: 'topo',      label: '🗺 טופו' }},    // מפה טופוגרפית
                    {{ key: 'streets',   label: '🏘 רחובות' }},  // OpenStreetMap
                    {{ key: 'satellite', label: '🛰 לוויין' }}   // תצלום Esri
                ];

                layers.forEach(function(layer) {{
                    var btn = L.DomUtil.create('button', 'layer-btn', container);  // יצירת כפתור בתוך המיכל
                    btn.innerHTML  = layer.label;  // תווית הכפתור
                    btn.dataset.key = layer.key;   // שמירת המפתח כ-data attribute לשימוש בclickה

                    if (layer.key === 'topo') {{
                        btn.classList.add('active');  // סימון ברירת המחדל כפעיל
                    }}

                    // מניעת הגלשת לחיצות/גלילה למפה מאחורי הפקד
                    L.DomEvent.disableClickPropagation(btn);
                    L.DomEvent.disableScrollPropagation(container);

                    L.DomEvent.on(btn, 'click', function() {{
                        setBaseLayer(layer.key);  // החלפת השכבה בפועל

                        // עדכון הסגנון: הסרת active מכולם והוספה לנלחץ
                        container.querySelectorAll('.layer-btn').forEach(function(b) {{
                            b.classList.remove('active');  // ניקוי הסימון מכל הכפתורים
                        }});
                        btn.classList.add('active');  // סימון הכפתור שנלחץ כפעיל
                    }});
                }});

                return container;  // החזרת המיכל ל-Leaflet לצורך הוספה ל-DOM
            }}
        }});

        new LayerSwitcher().addTo(map);  // יצירת מופע הפקד והוספתו למפה

        // אתחול שכבת מפת החום — לא מוצגת עד להפעלה מפורשת
        heatmap = L.heatLayer([], {{
            radius: 50,       // רדיוס נקודת חום בפיקסלים
            blur: 20,         // טשטוש להגעת רכות ויזואלית
            maxZoom: 17,      // זום מרבי שבו שכבת החום פעילה
            minOpacity: 0.4   // שקיפות מינימלית לנראות טובה
        }});

        // ── סרגל קנה-מידה כפול (ק"מ + NM) ──
        (function() {{
            var ScaleBar = L.Control.extend({{
                options: {{ position: 'bottomright' }},
                onAdd: function(m) {{
                    var d = L.DomUtil.create('div', '');
                    d.style.cssText = 'background:rgba(30,30,46,.82);color:#cdd6f4;padding:4px 8px;'
                        + 'border-radius:7px;font-size:11px;font-family:monospace;pointer-events:none;';
                    this._d = d;
                    m.on('zoomend moveend', this._upd, this);
                    this._upd();
                    return d;
                }},
                _upd: function() {{
                    var mpp = 156543.03 * Math.cos(this._map.getCenter().lat * Math.PI/180)
                              / Math.pow(2, this._map.getZoom());
                    var maxM = mpp * 110;
                    var exp  = Math.floor(Math.log(maxM) / Math.LN10);
                    var f    = maxM / Math.pow(10, exp);
                    var nice = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
                    var niceM = nice * Math.pow(10, exp);
                    var barW  = Math.round(niceM / mpp);
                    var km  = niceM / 1000;
                    var nm  = niceM / 1852;
                    var kmTxt = km >= 1 ? (km >= 10 ? km.toFixed(0) : km.toFixed(1)) + ' ק"מ'
                                       : Math.round(niceM) + " מ'";
                    var nmTxt = nm >= 1 ? (nm >= 10 ? nm.toFixed(0) : nm.toFixed(1)) + ' NM'
                                       : Math.round(niceM) + " מ'";
                    this._d.innerHTML =
                        '<div style="display:flex;align-items:center;gap:6px;">'
                        + '<div style="width:' + barW + 'px;height:3px;background:#89b4fa;'
                        + 'border-left:2px solid #cdd6f4;border-right:2px solid #cdd6f4;'
                        + 'border-top:1px solid #cdd6f4;"></div>'
                        + '<span>' + kmTxt + ' / ' + nmTxt + '</span></div>';
                }}
            }});
            new ScaleBar().addTo(map);
        }})();

        // ── כלי מדידת מרחק ──
        var rulerActive  = false;
        var rulerPoints  = [];
        var rulerLines   = [];
        var rulerDots    = [];
        var rulerLabels  = [];
        var rulerPopup   = null;

        function _haversineM(p1, p2) {{
            var R = 6371000, r = Math.PI/180;
            var f1=p1.lat*r, f2=p2.lat*r, df=(p2.lat-p1.lat)*r, dl=(p2.lng-p1.lng)*r;
            var a = Math.sin(df/2)*Math.sin(df/2)+Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)*Math.sin(dl/2);
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }}

        function _bearingDeg(p1, p2) {{
            // אזימוט התחלתי (0=צפון, בכיוון השעון) מ-p1 אל p2 — נוסחת "initial bearing" סטנדרטית.
            // משמש לחישוב הזווית בזמן גרירת ידית רדיוס-הראייה הרדיאלי — חישוב JS מקומי, לא קורא לשרת.
            var r = Math.PI/180;
            var f1=p1.lat*r, f2=p2.lat*r, dl=(p2.lng-p1.lng)*r;
            var y = Math.sin(dl) * Math.cos(f2);
            var x = Math.cos(f1)*Math.sin(f2) - Math.sin(f1)*Math.cos(f2)*Math.cos(dl);
            var brng = Math.atan2(y, x) / r;
            return (brng + 360) % 360;  // נרמול ל-[0,360)
        }}

        function _destPointJs(origin, bearingDeg, distanceM) {{
            // גרסת JS של _destination_point הפייתוני (weather_server.py) — נקודת יעד ממקור+אזימוט+מרחק,
            // קירוב כדורי. משמש לצייר את קווי התצוגה המקדימה של רדיוס-הראייה הרדיאלי בלי לקרוא לשרת.
            if (distanceM <= 0) return L.latLng(origin.lat, origin.lng);
            var r = Math.PI/180, R = 6371000;
            var phi1 = origin.lat*r, lam1 = origin.lng*r, theta = bearingDeg*r, delta = distanceM/R;
            var phi2 = Math.asin(Math.sin(phi1)*Math.cos(delta) + Math.cos(phi1)*Math.sin(delta)*Math.cos(theta));
            var lam2 = lam1 + Math.atan2(
                Math.sin(theta)*Math.sin(delta)*Math.cos(phi1),
                Math.cos(delta) - Math.sin(phi1)*Math.sin(phi2)
            );
            return L.latLng(phi2/r, ((lam2/r + 540) % 360) - 180);  // נרמול קו האורך ל-[-180,180]
        }}

        function _fmtDist(m) {{
            var km = m/1000, nm = m/1852;
            var ks = km>=10 ? km.toFixed(1) : km.toFixed(2);
            var ns = nm>=10 ? nm.toFixed(1) : nm.toFixed(2);
            return ks + ' ק"מ  /  ' + ns + ' NM';
        }}

        function _updateRulerPopup() {{
            if (rulerPoints.length < 2) return;
            var total = 0;
            for (var i=1; i<rulerPoints.length; i++) total += _haversineM(rulerPoints[i-1], rulerPoints[i]);
            if (rulerPopup) {{ map.closePopup(rulerPopup); }}
            rulerPopup = L.popup({{ closeButton: false, autoClose: false, closeOnClick: false,
                                    className: 'ruler-popup' }})
                .setLatLng(rulerPoints[rulerPoints.length-1])
                .setContent('<b>סה"כ: ' + _fmtDist(total) + '</b><br>'
                    + '<small>' + rulerPoints.length + ' נקודות</small>')
                .openOn(map);
        }}

        map.on('click', function(e) {{
            if (!rulerActive) return;
            var p = e.latlng;
            if (rulerPoints.length > 0) {{
                var prev = rulerPoints[rulerPoints.length-1];
                var line = L.polyline([prev, p], {{color:'#a6e3a1',weight:2.5,dashArray:'8,5'}}).addTo(map);
                rulerLines.push(line);
                var mid = L.latLng((prev.lat+p.lat)/2, (prev.lng+p.lng)/2);
                var seg = _haversineM(prev, p);
                var lbl = L.marker(mid, {{
                    icon: L.divIcon({{ html:'<div style="background:rgba(30,30,46,.8);color:#a6e3a1;'
                        +'padding:1px 5px;border-radius:4px;font-size:10px;white-space:nowrap;">'
                        + _fmtDist(seg) +'</div>', className:'', iconAnchor:[0,0] }}),
                    interactive: false
                }}).addTo(map);
                rulerLabels.push(lbl);
            }}
            var dot = L.circleMarker(p, {{radius:5,color:'#fff',fillColor:'#a6e3a1',
                                          fillOpacity:1,weight:2}}).addTo(map);
            rulerDots.push(dot);
            rulerPoints.push(p);
            _updateRulerPopup();
        }});

        function clearRuler() {{
            rulerActive = false;
            rulerPoints = [];
            rulerLines.forEach(function(l)  {{ map.removeLayer(l); }}); rulerLines  = [];
            rulerDots.forEach(function(d)   {{ map.removeLayer(d); }}); rulerDots   = [];
            rulerLabels.forEach(function(l) {{ map.removeLayer(l); }}); rulerLabels = [];
            if (rulerPopup) {{ map.closePopup(rulerPopup); rulerPopup = null; }}
            map.getContainer().style.cursor = '';
        }}

        function toggleRuler() {{
            rulerActive = !rulerActive;
            map.getContainer().style.cursor = rulerActive ? 'crosshair' : '';
            if (!rulerActive) clearRuler();
        }}

        // מעקב מיקום עכבר — עדכון תיבת הסטטוס בזמן אמת
        map.on('mousemove', function(e) {{
            var lat = e.latlng.lat.toFixed(4);  // קו רוחב מעוגל ל-4 ספרות עשרוניות
            var lon = e.latlng.lng.toFixed(4);  // קו אורך מעוגל ל-4 ספרות עשרוניות
            document.getElementById('status').innerHTML =
                "מיקום העכבר: קו רוחב: " + lat + ", קו אורך: " + lon;
        }});

        // ── פונקציות מסלול טיסה ──

        function drawFlightRoute(routeData) {{
            clearFlightRoute();

            var trail = routeData.trail;

            if (!trail || trail.length === 0) {{
                if (routeData.lat && routeData.lng) {{
                    trail = [{{lat: routeData.lat, lng: routeData.lng}}];
                }} else {{
                    throw new Error("אין נתוני מסלול ואין מיקום נוכחי לטיסה: " + routeData.callsign);
                }}
            }}

            // סינון נקודות חסרות — מונע שגיאת Leaflet
            var path = trail
                .filter(function(p) {{ return p.lat != null && p.lng != null; }})
                .map(function(p) {{ return [p.lat, p.lng]; }});

            if (path.length === 0) {{
                throw new Error("כל נקודות המסלול חסרות קואורדינטות");
            }}

            flightPolyline = L.polyline(path, {{
                color: '#4fc3f7',
                opacity: 0.85,
                weight: 3
            }}).addTo(map);

            var currentPos = path[path.length - 1];
            var planeIcon = L.divIcon({{
                html: '<div style="font-size:22px;color:#4fc3f7;text-shadow:0 0 3px #000;transform:rotate('
                      + (routeData.heading || 0)
                      + 'deg);line-height:1;cursor:pointer;">&#9992;</div>',
                className:  '',
                iconSize:   [28, 28],
                iconAnchor: [14, 14]
            }});

            flightMarker = L.marker(currentPos, {{
                icon:  planeIcon,
                title: routeData.callsign || ""
            }}).addTo(map);

            var alt = (routeData.altitude || 0).toLocaleString();
            var popupContent =
                '<div style="direction:rtl;font-family:Arial;font-size:13px;min-width:180px;">' +
                '<div style="font-size:15px;font-weight:bold;margin-bottom:6px;">&#9992; ' + (routeData.callsign || "") + '</div>' +
                '<div><b>חברה:</b> ' + (routeData.airline || "—") + '</div>' +
                '<div><b>מטוס:</b> ' + (routeData.aircraft || "—") + '</div>' +
                '<hr style="margin:5px 0;border-color:#45475a;">' +
                '<div><b>מוצא:</b> ' + (routeData.origin_iata || "?") + ' &mdash; ' + (routeData.origin_name || "") + '</div>' +
                '<div><b>יעד:</b> '   + (routeData.dest_iata   || "?") + ' &mdash; ' + (routeData.dest_name   || "") + '</div>' +
                '<hr style="margin:5px 0;border-color:#45475a;">' +
                '<div><b>גובה:</b> '    + alt + ' ft</div>' +
                '<div><b>מהירות:</b> ' + (routeData.speed   || 0) + ' kt</div>' +
                '<div><b>כיוון:</b> '  + (routeData.heading || 0) + '&#176;</div>' +
                '<div style="margin-top:5px;color:#6c7086;font-size:11px;">' + trail.length + ' נקודות מסלול</div>' +
                '</div>';

            flightMarker.bindPopup(popupContent).openPopup();  // קישור Popup ופתיחה מיידית

            // לחיצה חוזרת על הסמן — פתיחת ה-Popup שוב אם נסגר
            flightMarker.on('click', function() {{
                flightMarker.openPopup();
            }});

            // סימון שדות תעופה: מוצא ויעד עם תווית IATA
            _addAirportDot(path[0],         routeData.origin_iata);  // שדה מוצא
            _addAirportDot(currentPos,      routeData.dest_iata);    // שדה יעד

            // התאמת תצוגת המפה לכיסוי מלא של המסלול — זום אוטומטי
            map.fitBounds(flightPolyline.getBounds());
        }}

        function _addAirportDot(position, label) {{
            // יצירת נקודה עגולה עם תווית IATA לסימון שדות תעופה על המסלול
            var dotIcon = L.divIcon({{
                html: '<div style="background:#f38ba8;border:2px solid #fff;border-radius:50%;'
                    + 'width:22px;height:22px;display:flex;align-items:center;justify-content:center;'
                    + 'color:#fff;font-size:9px;font-weight:bold;">' + label + '</div>',
                className:  '',        // ביטול קלאס ברירת מחדל
                iconSize:   [22, 22],  // גודל תואם ה-div
                iconAnchor: [11, 11]   // עוגן במרכז הנקודה
            }});
            var dot = L.marker(position, {{
                icon:  dotIcon,
                title: label  // tooltip עם קוד IATA
            }}).addTo(map);
            allMarkers.push(dot);  // רישום ברשימה לניקוי עתידי
        }}

        function clearFlightRoute() {{
            // ניקוי מסלול טיסה קיים — polyline וסמן
            if (flightPolyline) {{ flightPolyline.remove(); flightPolyline = null; }}
            if (flightMarker)   {{ flightMarker.remove();   flightMarker   = null; }}
        }}

        // ── שכבת "אזורי פעילות טיסה (NOTAM)" — 7 קטגוריות, בהשראת מסך השכבות של DronesIL ──
        // חשוב: אלה אזורים שבהם *מישהו אחר* קיבל אישור/פעילות מוכרזת, והמרחב סגור/מוגבל
        // לתעבורה אחרת — שכבת הימנעות/מודעות, לא "מותר לך לטוס כאן". NOTAM בודד עשוי
        // להתאים ליותר מקטגוריה אחת (למשל "UAS PROHIBITED"). ר' notam_drones.py לפרטי
        // המקור ו-notam_categories.py לרשימת הקטגוריות (id/תווית/צבע).
        var NOTAM_CATEGORIES = {notam_categories_json};  // הזרקה סטטית — נתון קבוע, לא fetch בזמן ריצה
        var uasNotamZones     = [];     // המידע הגולמי מהשרת — נטען פעם אחת, משותף לכל 7 הקטגוריות
        var uasNotamLoaded    = false;  // האם הטעינה הראשונית הסתיימה בהצלחה
        var activeNotamCategories = new Set();  // אילו id-ים של קטגוריות מסומנים כרגע (מתיבות הסימון ב-toolbox)
        var uasNotamLayer  = null;   // L.layerGroup עם כל צורות ה-NOTAM הפעילות כרגע
        var uasNotamLegendControl = null;  // תיבת מקרא — מוצגת רק כשיש לפחות קטגוריה אחת פעילה

        function _notamCategoryById(id) {{
            // חיפוש רשומת קטגוריה לפי id — נעשה בלולאה כי NOTAM_CATEGORIES קטן (7 איברים), אין צורך ב-Map
            for (var i = 0; i < NOTAM_CATEGORIES.length; i++) {{
                if (NOTAM_CATEGORIES[i].id === id) return NOTAM_CATEGORIES[i];
            }}
            return null;
        }}

        function _escHtml(s) {{
            // מונע HTML injection דרך טקסט ה-NOTAM (גם אם המקור ממשלתי — הגנה בכל מקרה) בטרם הכנסה ל-innerHTML של הפופאפ
            return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }}

        // מטרים לפיקסל בזום נתון — נוסחת Web Mercator סטנדרטית, זהה לזו שבצד Android (_ScaleBar._metersPerPixel)
        function _metersPerPixel(lat, zoom) {{
            return 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, zoom);
        }}

        // רדיוס מינימלי חזותי (במטרים, בזום הנוכחי) למעגלי NOTAM/אזורי-תיאום קטנים — בלי זה, אזור
        // עם רדיוס אמיתי של כמה מאות מטרים (למשל NOTAM על מנוף בנייה, ~555מ') נעלם בזום ארצי,
        // ורואים רק צורה זעירה. תואם למנגנון המקביל ב-Android (_minVisibleRadiusM).
        function _minVisibleRadiusM(lat) {{
            var minPixels = 18;  // רדיוס מסך מינימלי רצוי — בערך גודל סמן/נקודת הקטגוריה עצמה
            return minPixels * _metersPerPixel(lat, map.getZoom());
        }}

        // מרכז כובד גס (ממוצע נקודות) — מספיק לצורך ניפוח חזותי, לא נדרשת דיוק גיאומטרי מלא
        function _polygonCentroid(points) {{
            var sumLat = 0, sumLon = 0;
            points.forEach(function(p) {{ sumLat += p[0]; sumLon += p[1]; }});
            return [sumLat / points.length, sumLon / points.length];
        }}

        // מנפח פוליגון קטן מדי (בפיקסלים, בזום הנוכחי) כלפי חוץ מסביב למרכז הכובד שלו, בלי
        // לשנות את צורתו היחסית — אותו עיקרון בדיוק כמו _minVisibleRadiusM למעגלים. בלעדיו,
        // פוליגון NOTAM אמיתי (לרוב כמה מאות מטרים עד כמה ק"מ) פשוט לא נראה בזום ארצי, בעוד
        // שמעגלים כן מנופחים ל-min — וכל השכבה נראית כאילו יש בה רק מעגלים, לא פוליגונים.
        function _scaleUpSmallPolygon(points, centroid) {{
            var maxDistM = 0;
            points.forEach(function(p) {{
                var dLatM = (p[0] - centroid[0]) * 111000;
                var dLonM = (p[1] - centroid[1]) * 111000 * Math.cos(centroid[0] * Math.PI / 180);
                var d = Math.sqrt(dLatM * dLatM + dLonM * dLonM);
                if (d > maxDistM) maxDistM = d;
            }});
            var minR = _minVisibleRadiusM(centroid[0]);
            if (maxDistM === 0 || maxDistM >= minR) return points;  // כבר גדול מספיק, או נקודות חופפות (לא אמור לקרות)
            var scale = minR / maxDistM;
            return points.map(function(p) {{
                return [centroid[0] + (p[0] - centroid[0]) * scale, centroid[1] + (p[1] - centroid[1]) * scale];
            }});
        }}

        // מצב תצוגה (מצומצם/מורחב) של כל מקרא — משתנה גלובלי כדי שהבחירה של המשתמש תישרד
        // ציור מחדש של השכבה (למשל toggle של קטגוריית NOTAM נוספת יוצר מחדש את ה-Control).
        var notamLegendExpanded = false;    // מצב מקרא ה-NOTAM — מצומצם כברירת מחדל, לא חוסם את המפה
        var uasCoordLegendExpanded = false; // מצב מקרא אזורי התיאום — מצומצם כברירת מחדל
        var airportCtrLegendExpanded = false; // מצב מקרא גבולות ה-CTR — מצומצם כברירת מחדל

        // יוצר div של מקרא הניתן לצמצום לסמל עגול קטן — משותף לשני מקראות השכבות (NOTAM/תיאום).
        // getExpanded/setExpanded הן פונקציות-גישה למשתנה הגלובלי הספציפי של המקרא הזה, כדי
        // שהמצב המורחב/מצומצם ישרוד ציור מחדש (redraw) של השכבה עצמה.
        function _makeCollapsibleLegend(iconHtml, bodyHtml, getExpanded, setExpanded) {{
            var d = L.DomUtil.create('div', '');  // אלמנט ה-div שישמש את ה-Control של Leaflet
            L.DomEvent.disableClickPropagation(d);  // מונע ממחוות עכבר/מגע על המקרא להגיע גם למפה עצמה (כלים אחרים כמו סרגל/הצבת נקודה)

            function render() {{  // בונה מחדש רק את התוכן/עיצוב של ה-div לפי המצב — לא נוגע במאזיני האירועים כלל
                if (getExpanded()) {{
                    // מצב מורחב — תיבה עם התוכן המלא וכפתור X לצמצום
                    d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;padding:6px 10px;'
                        + 'border-radius:7px;font-size:11px;font-family:Arial;border:1px solid #45475a;'
                        + 'direction:rtl;max-width:230px;cursor:default;';
                    d.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px;">'
                        + '<div style="flex:1;">' + bodyHtml + '</div>'
                        + '<span class="_legendCollapseBtn" style="cursor:pointer;opacity:.65;font-size:13px;flex-shrink:0;">&#10005;</span>'
                        + '</div>';
                }} else {{
                    // מצב מצומצם — עיגול קטן בלבד, לא חוסם את תצוגת המפה
                    d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;width:30px;height:30px;'
                        + 'border-radius:50%;border:1px solid #45475a;display:flex;align-items:center;'
                        + 'justify-content:center;font-size:15px;cursor:pointer;';
                    d.innerHTML = iconHtml;
                }}
            }}

            // מאזין יציב יחיד על d עצמו, נרשם פעם אחת בלבד (לא בתוך render) — קורא את המצב
            // הנוכחי בזמן הלחיצה עצמה, במקום להחליף מאזינים בכל render. הגישה הקודמת (קביעת
            // d.onclick/span.onclick מחדש בכל render) יצרה מירוץ: שינוי ה-DOM וההאזנות באמצע
            // הפצת (dispatch) אותה לחיצה עצמה גרם ללחיצה אחת להתפרש כפתיחה-וסגירה גם יחד,
            // ולעיתים "לדלוף" למפה (הצבת נקודה). setTimeout דוחה את השינוי בפועל לטיק הבא,
            // אחרי שהלחיצה הנוכחית סיימה להיות מטופלת במלואה על ידי הדפדפן.
            d.addEventListener('click', function(evt) {{
                L.DomEvent.stopPropagation(evt);  // הגנה מפורשת נוספת, מעבר ל-disableClickPropagation
                var expanded = getExpanded();  // המצב הנוכחי ברגע הלחיצה עצמה, לא ברגע רישום המאזין
                var clickedCollapseBtn = evt.target && evt.target.classList && evt.target.classList.contains('_legendCollapseBtn');
                if (expanded && !clickedCollapseBtn) return;  // לחיצה בתוך התוכן המורחב (לא על כפתור ה-X) — לא עושה כלום
                setExpanded(!expanded);  // הופך את המצב: פותח אם היה סגור, סוגר אם היה פתוח
                setTimeout(render, 0);  // עדכון התצוגה בפועל בטיק הבא — לא באמצע הפצת הלחיצה הנוכחית
            }});

            render();  // בנייה ראשונית לפי המצב הנוכחי (מצומצם כברירת מחדל)
            return d;
        }}

        var UasNotamLegend = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function() {{
                var rows = '';  // שורת צבע+תווית לכל קטגוריה שמסומנת כרגע — מקרא דינמי, לא קבוע
                activeNotamCategories.forEach(function(id) {{
                    var cat = _notamCategoryById(id);
                    if (!cat) return;
                    rows += '<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">'
                        + '<span style="display:inline-block;width:12px;height:12px;background:' + cat.color + ';'
                        + 'border-radius:3px;flex-shrink:0;"></span><span>' + _escHtml(cat.label) + '</span></div>';
                }});
                var bodyHtml =
                    '<div style="font-weight:bold;">&#9992; אזורי פעילות טיסה (NOTAM)</div>'
                    + rows
                    + '<div style="color:#a6adc8;margin-top:4px;">אזור פעילות/הגבלה מוכרזת — להימנעות, לא לטיסה חופשית. לחץ על צורה לפרטים.</div>';
                return _makeCollapsibleLegend('&#9992;', bodyHtml,  // סמל מטוס לעיגול המצומצם
                    function() {{ return notamLegendExpanded; }},
                    function(v) {{ notamLegendExpanded = v; }});
            }}
        }});

        // הפעלה/כיבוי קטגוריה בודדת — הטעינה מהשרת חד-פעמית ומשותפת לכל 7 הקטגוריות (לא נטען מחדש בכל תיבת-סימון)
        function toggleNotamCategory(catId) {{
            if (!uasNotamLoaded) {{
                document.title = '__uas_notam_loading__';  // איתות ל-Python (main.py) שהטעינה החלה — נתפס ב-_on_title_changed
                fetch('http://localhost:5003/uas_notams')
                    .then(function(r) {{
                        if (!r.ok) throw new Error('שגיאת שרת: ' + r.status);
                        return r.json();
                    }})
                    .then(function(data) {{
                        if (data.error && (!data.zones || !data.zones.length)) {{  // שגיאה בלי אפילו cache ישן — אין מה להציג
                            throw new Error(data.error);
                        }}
                        uasNotamZones  = data.zones || [];
                        uasNotamLoaded = true;
                        activeNotamCategories.add(catId);  // הקטגוריה שסומנה ברגע שהפעילה את הטעינה
                        _redrawNotamLayer();
                        document.title = '__uas_notam_loaded__:' + uasNotamZones.length;  // מספר האזורים מוטמע בכותרת עצמה
                    }})
                    .catch(function(err) {{
                        console.error('שגיאת שכבת NOTAM:', err);
                        document.title = '__uas_notam_error__:' + catId;  // מזהה הקטגוריה שנכשלה — כדי שרק תיבת הסימון שלה תוחזר ללא-מסומן
                    }});
                return;
            }}
            // כבר נטען בעבר — toggle סינכרוני בלבד, בלי בקשת רשת נוספת
            if (activeNotamCategories.has(catId)) {{ activeNotamCategories.delete(catId); }}
            else {{ activeNotamCategories.add(catId); }}
            _redrawNotamLayer();
        }}

        function _redrawNotamLayer() {{
            clearUasNotamLayer();  // מנקה ציור/מקרא קודמים לפני ציור מחדש — מונע כפילות שכבות
            if (activeNotamCategories.size === 0) return;  // אין קטגוריה מסומנת — אין מה לצייר
            var visible = uasNotamZones.filter(function(z) {{
                return z.categories.some(function(c) {{ return activeNotamCategories.has(c); }});  // תואם לפחות קטגוריה אחת מסומנת
            }});
            var shapes = visible.map(function(z) {{
                // צביעה לפי הקטגוריה הראשונה (בסדר NOTAM_CATEGORIES) ששייכת גם לאזור וגם מסומנת כרגע
                var primaryCat = NOTAM_CATEGORIES.filter(function(c) {{
                    return z.categories.indexOf(c.id) !== -1 && activeNotamCategories.has(c.id);
                }})[0];
                var color = primaryCat ? primaryCat.color : '#fab387';
                // גיאומטריה שמקורה ברשת הביטחון של שורת Q) (ר' _geometry_from_q_line ב-notam_drones.py)
                // היא קירוב גס — למשל רצועת גבול שלמה מוצגת כמעגל — ולא הצורה המדויקת שדווחה.
                // מסגרת מקווקוות מבדילה אותה חזותית מגיאומטריה מדויקת (מסגרת רציפה).
                var isApprox = z.geometry.source === 'q_line_approx';
                var style = {{
                    color: color, weight: 3, fillColor: color, fillOpacity: isApprox ? 0.22 : 0.4,  // מילוי חלש יותר לקירוב — פחות "בטוח בעצמו" חזותית
                    dashArray: isApprox ? '9,6' : null,  // מסגרת מקווקוות = קירוב, רציפה = מדויק מהטקסט
                }};
                var shape;
                if (z.geometry.type === 'circle') {{
                    var trueR = z.geometry.radius_m;  // הרדיוס האמיתי מה-NOTAM, לפני החלת הרצפה החזותית
                    shape = L.circle(z.geometry.center, Object.assign(
                        {{ radius: Math.max(trueR, _minVisibleRadiusM(z.geometry.center[0])) }}, style));  // מעגל: "X NM RADIUS CENTERED ON PSN"
                    shape._trueRadiusM = trueR;  // נשמר על הצורה עצמה כדי לחשב מחדש ב-zoomend (ר' המאזין למטה)
                }} else {{
                    var centroid = _polygonCentroid(z.geometry.points);  // מרכז כובד — נקודת הייחוס לניפוח החזותי
                    shape = L.polygon(_scaleUpSmallPolygon(z.geometry.points, centroid), style);  // פוליגון: "AN AREA BTN FLW PSN" עם 3+ קואורדינטות
                    shape._truePoints = z.geometry.points;  // הנקודות האמיתיות (לא מנופחות), לחישוב מחדש ב-zoomend
                    shape._centroid = centroid;
                }}
                var catLabels = z.categories.map(function(id) {{
                    var c = _notamCategoryById(id);
                    return c ? c.label : id;
                }}).join(', ');
                var popup =
                    '<div style="direction:rtl;font-family:Arial;font-size:13px;max-width:280px;">' +
                    '<div style="font-size:14px;font-weight:bold;margin-bottom:4px;color:' + color + ';">&#9992; ' + _escHtml(z.id) + ' (' + _escHtml(z.icao) + ')</div>' +
                    '<div style="font-size:11px;color:#a6adc8;margin-bottom:4px;"><b>קטגוריות:</b> ' + _escHtml(catLabels) + '</div>' +
                    '<div style="background:rgba(0,0,0,0.18);border-radius:4px;padding:4px 6px;margin-bottom:6px;font-size:11px;">' +
                    '&#9888; אזור פעילות/הגבלה מוכרזת — להימנעות, לא לטיסה חופשית</div>' +
                    (isApprox ?
                        '<div style="background:rgba(250,179,135,0.18);border-radius:4px;padding:4px 6px;margin-bottom:6px;font-size:11px;">' +
                        '&#9888; צורת האזור המוצגת היא <b>קירוב גס בלבד</b> (ממרכז ורדיוס כלליים) — הטקסט המלא לא כלל תיאור גיאומטרי מדויק. ' +
                        'האזור האמיתי עשוי להיות שונה בצורתו (למשל רצועה, לא מעגל) — ראו את הטקסט המלא למטה.</div>' : '') +
                    (z.altitude_text ? '<div><b>גובה:</b> ' + _escHtml(z.altitude_text) + '</div>' : '') +
                    (z.hebrew_gloss ?
                        '<div style="background:rgba(99,102,241,0.12);border-radius:4px;padding:4px 6px;margin-top:6px;font-size:11px;">' +
                        '<b>תרגום גס לעברית (לנוחות בלבד)</b><br>' + _escHtml(z.hebrew_gloss) +
                        '<div style="color:#a6adc8;font-size:10px;margin-top:3px;">הטקסט האנגלי המקורי הוא הקובע — התרגום הוא כלי עזר בלבד ועלול להכיל טעויות או השמטות.</div>' +
                        '</div>' : '') +
                    '<div style="margin-top:6px;color:#a6adc8;font-size:11px;">' + _escHtml(z.text) + '</div>' +
                    '</div>';
                shape.bindPopup(popup);
                return shape;
            }});
            // L.featureGroup, לא L.layerGroup — LayerGroup הרגיל לא כולל .getBounds() ב-Leaflet
            // (זו תוספת של FeatureGroup בלבד), וקריאה ל-.getBounds() כמה שורות למטה הייתה
            // זורקת TypeError בכל פעם, שנתפס ב-catch ומדווח בטעות כ"טעינה נכשלה" — למרות
            // שהצורות כן צוירו על המפה בהצלחה. addTo/removeLayer מתנהגים זהה בשתי המחלקות.
            uasNotamLayer = L.featureGroup(shapes).addTo(map);
            uasNotamLegendControl = new UasNotamLegend().addTo(map);
            // התאמת תצוגת המפה לאזורים שהוצגו — בלי זה, אזורים קטנים (500 מ'-כמה ק"מ) נראים
            // כנקודה זעירה ולא כפוליגון/מעגל בזום ארצי רגיל. maxZoom מונע התקרבות מוגזמת כשמוצג רק אזור בודד קטן.
            if (shapes.length > 0) {{
                map.fitBounds(uasNotamLayer.getBounds(), {{ padding: [40, 40], maxZoom: 14 }});
            }}
        }}

        function clearUasNotamLayer() {{
            // מנקה רק את הציור/המקרא — לא נוגע ב-activeNotamCategories (שימוש ב-_redrawNotamLayer/מצב תיבות סימון)
            if (uasNotamLayer) {{ map.removeLayer(uasNotamLayer); uasNotamLayer = null; }}
            if (uasNotamLegendControl) {{ map.removeControl(uasNotamLegendControl); uasNotamLegendControl = null; }}
        }}

        function clearAllNotamCategories() {{
            // איפוס מלא — כולל בחירת הקטגוריות עצמה, לא רק הציור. נקרא מ-resetMapState (איפוס מפה מלא)
            activeNotamCategories.clear();
            clearUasNotamLayer();
        }}

        // ── שכבת "אזורי תיאום כטב"ם" ──
        // חשוב: אלה אזורים שניתן *לבקש* לפעול בהם, לא אזורי "מותר לטוס" — כל אזור דורש
        // אישור יחידת הנת"א מראש. נתונים סטטיים (לא נשלפים בזמן ריצה) — ר' uas_coordination_zones.py.
        // uasCoordZonesData היא נקודת ההזרקה הדינמית היחידה בתבנית הזו (json.dumps בפייתון) —
        // כל שאר הקוד כאן משתמש בסוגריים מסולסלות כפולות {{ }} כליטרל JS רגיל.
        var uasCoordZonesData = {coord_zones_json};
        var uasCoordLayer = null;
        var uasCoordActive = false;
        var uasCoordLegendControl = null;

        var UasCoordLegend = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function() {{
                var bodyHtml =
                    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                    + '<span style="display:inline-block;width:14px;height:14px;background:#6366f1;'
                    + 'border-radius:3px;flex-shrink:0;"></span>'
                    + '<b>&#128737; אזורי תיאום כטב"ם — דורש אישור נת"א</b></div>'
                    + '<div style="color:#a6adc8;">כל שימוש באזור מחייב תיאום ואישור מראש מיחידת הנת"א הרלוונטית — לא אזור חופשי לטיסה. לחץ על צורה לפרטים.</div>';
                return _makeCollapsibleLegend('&#128737;', bodyHtml,  // סמל מגן לעיגול המצומצם
                    function() {{ return uasCoordLegendExpanded; }},
                    function(v) {{ uasCoordLegendExpanded = v; }});
            }}
        }});

        function toggleUasCoordZonesLayer() {{
            // סינכרוני לגמרי — הנתונים כבר בעמוד (uasCoordZonesData), אין fetch/loading/error
            if (uasCoordActive) {{
                clearUasCoordZonesLayer();
            }} else {{
                _drawUasCoordZones(uasCoordZonesData);
            }}
        }}

        function _drawUasCoordZones(zones) {{
            clearUasCoordZonesLayer();  // מנקה ציור קודם לפני ציור מחדש — מונע כפילות שכבות
            var style = {{ color: '#6366f1', weight: 2, fillColor: '#6366f1', fillOpacity: 0.18 }};
            var shapes = zones.map(function(z) {{
                var shape;
                if (z.geometry.type === 'circle') {{
                    var trueR = z.geometry.radius_m;  // הרדיוס האמיתי, לפני החלת הרצפה החזותית
                    shape = L.circle(z.geometry.center, Object.assign(
                        {{ radius: Math.max(trueR, _minVisibleRadiusM(z.geometry.center[0])) }}, style));
                    shape._trueRadiusM = trueR;  // נשמר על הצורה עצמה כדי לחשב מחדש ב-zoomend
                }} else {{
                    var centroid = _polygonCentroid(z.geometry.points);  // מרכז כובד — נקודת הייחוס לניפוח החזותי
                    shape = L.polygon(_scaleUpSmallPolygon(z.geometry.points, centroid), style);
                    shape._truePoints = z.geometry.points;  // הנקודות האמיתיות (לא מנופחות), לחישוב מחדש ב-zoomend
                    shape._centroid = centroid;
                }}
                var popup =
                    '<div style="direction:rtl;font-family:Arial;font-size:13px;max-width:280px;">' +
                    '<div style="font-size:14px;font-weight:bold;margin-bottom:4px;color:#6366f1;">&#128737; ' + _escHtml(z.name) + '</div>' +
                    '<div style="background:rgba(99,102,241,0.15);border-radius:4px;padding:4px 6px;margin-bottom:6px;font-size:11px;">' +
                    'תחילת פעילות בכל אזור דורשת אישור יחידת הנת"א. אין להיכנס לפעילות ללא תיאום מראש.</div>' +
                    '<div><b>גובה מרבי:</b> ' + _escHtml(z.altitude_label) + '</div>' +
                    (z.notes ? '<div style="margin-top:6px;color:#a6adc8;font-size:11px;">' + _escHtml(z.notes) + '</div>' : '') +
                    '</div>';
                shape.bindPopup(popup);
                return shape;
            }});
            uasCoordLayer = L.layerGroup(shapes).addTo(map);
            if (!uasCoordLegendControl) {{
                uasCoordLegendControl = new UasCoordLegend().addTo(map);
            }}
            uasCoordActive = true;
        }}

        function clearUasCoordZonesLayer() {{
            if (uasCoordLayer) {{ map.removeLayer(uasCoordLayer); uasCoordLayer = null; }}
            if (uasCoordLegendControl) {{ map.removeControl(uasCoordLegendControl); uasCoordLegendControl = null; }}
            uasCoordActive = false;
        }}

        // ── שכבת "גבולות CTR שדות תעופה" ──
        // גבול מרחב פיקוח קבוע (CTR) כפי שמפורסם רשמית ב-AIP — בשונה משכבת "אזורי פיקוח שדות
        // תעופה" (קטגוריית NOTAM "airport_control" למעלה) שמציגה רק אזכורים אד-הוק בתוך טקסט
        // הודעות NOTAM (למשל עגורן בנייה ליד השדה), לא את גבול המרחב המבוקר הקבוע עצמו.
        // נתונים סטטיים (לא נשלפים בזמן ריצה) — ר' airport_ctr_zones.py.
        var airportCtrZonesData = {airport_ctr_zones_json};
        var airportCtrLayer = null;
        var airportCtrActive = false;
        var airportCtrLegendControl = null;

        var AirportCtrLegend = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function() {{
                var bodyHtml =
                    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                    + '<span style="display:inline-block;width:14px;height:14px;background:#f72585;'
                    + 'border-radius:3px;flex-shrink:0;"></span>'
                    + '<b>&#128752; גבולות CTR שדות תעופה</b></div>'
                    + '<div style="color:#a6adc8;">גבול המרחב המבוקר הקבוע של השדה, ממקור AIP רשמי — לא נגזר מהודעות NOTAM. לחץ על צורה לפרטים.</div>';
                return _makeCollapsibleLegend('&#128752;', bodyHtml,  // סמל מטוס-ממריא לעיגול המצומצם — שונה מסמל ה-NOTAM (&#9992;) כדי לא להתבלבל בין השכבות
                    function() {{ return airportCtrLegendExpanded; }},
                    function(v) {{ airportCtrLegendExpanded = v; }});
            }}
        }});

        function toggleAirportCtrLayer() {{
            // סינכרוני לגמרי — הנתונים כבר בעמוד (airportCtrZonesData), אין fetch/loading/error
            if (airportCtrActive) {{
                clearAirportCtrLayer();
            }} else {{
                _drawAirportCtrZones(airportCtrZonesData);
            }}
        }}

        function _drawAirportCtrZones(zones) {{
            clearAirportCtrLayer();  // מנקה ציור קודם לפני ציור מחדש — מונע כפילות שכבות
            var style = {{ color: '#f72585', weight: 2, fillColor: '#f72585', fillOpacity: 0.12, dashArray: '6,4' }};
            var shapes = zones.map(function(z) {{
                // כל הרשומות כרגע פוליגונים (אין מעגלים בנתוני CTR) — עדיין מפעיל ניפוח חזותי
                // מינימלי לעקביות עם שאר השכבות, גם אם בפועל CTR תמיד גדול מספיק שלא יידרש בפועל
                var centroid = _polygonCentroid(z.geometry.points);
                var shape = L.polygon(_scaleUpSmallPolygon(z.geometry.points, centroid), style);
                shape._truePoints = z.geometry.points;  // הנקודות האמיתיות (לא מנופחות), לחישוב מחדש ב-zoomend
                shape._centroid = centroid;
                var popup =
                    '<div style="direction:rtl;font-family:Arial;font-size:13px;max-width:280px;">' +
                    '<div style="font-size:14px;font-weight:bold;margin-bottom:4px;color:#f72585;">&#128752; ' + _escHtml(z.name) + '</div>' +
                    '<div><b>גובה:</b> ' + _escHtml(z.vertical_limits) + '</div>' +
                    '<div style="margin-top:4px;color:#a6adc8;font-size:11px;">מקור: AIP רשמי (e-AIP ישראל, סעיף AD 2.17)</div>' +
                    (z.notes ? '<div style="margin-top:6px;color:#a6adc8;font-size:11px;">' + _escHtml(z.notes) + '</div>' : '') +
                    '</div>';
                shape.bindPopup(popup);
                return shape;
            }});
            airportCtrLayer = L.layerGroup(shapes).addTo(map);
            if (!airportCtrLegendControl) {{
                airportCtrLegendControl = new AirportCtrLegend().addTo(map);
            }}
            airportCtrActive = true;
        }}

        function clearAirportCtrLayer() {{
            if (airportCtrLayer) {{ map.removeLayer(airportCtrLayer); airportCtrLayer = null; }}
            if (airportCtrLegendControl) {{ map.removeControl(airportCtrLegendControl); airportCtrLegendControl = null; }}
            airportCtrActive = false;
        }}

        // מרענן את גודל כל מעגלי/פוליגוני ה-NOTAM/אזורי-תיאום/CTR לפי הזום הנוכחי — הגודל האמיתי
        // (מטרים אמיתיים, בין אם L.circle או קואורדינטות פוליגון) לא זקוק לעדכון בזום, אבל
        // הרצפה החזותית המינימלית (_minVisibleRadiusM/_scaleUpSmallPolygon) כן תלוית-זום.
        map.on('zoomend', function() {{
            [uasNotamLayer, uasCoordLayer, airportCtrLayer].forEach(function(layer) {{
                if (!layer) return;  // השכבה כבויה כרגע — אין מה לרענן
                layer.eachLayer(function(shape) {{
                    if (shape._trueRadiusM !== undefined && shape.setRadius) {{
                        var c = shape.getLatLng();
                        shape.setRadius(Math.max(shape._trueRadiusM, _minVisibleRadiusM(c.lat)));
                    }} else if (shape._truePoints !== undefined && shape.setLatLngs) {{
                        shape.setLatLngs(_scaleUpSmallPolygon(shape._truePoints, shape._centroid));
                    }}
                }});
            }});
        }});

        // ── איפוס מצב המפה ──
        function resetMapState() {{
            clearFlightRoute();
            clearAllNotamCategories();  // מנקה גם את בחירת קטגוריות ה-NOTAM עצמה, לא רק את הציור (ר' clearUasNotamLayer)
            clearUasCoordZonesLayer();
            clearAirportCtrLayer();  // מנקה גם את שכבת גבולות ה-CTR — נוספה יחד עם שאר השכבות הסטטיות
            clearTempHeatmap();
            clearRuler();  // מנקה קווי/נקודות/תוויות סרגל ומאפס rulerActive+cursor — היה חסר, קווי מדידה נשארו על המפה אחרי איפוס
            clearLosMap();   // ניקוי כל קווי הראייה, הסמנים והפאנל — LOS מאופס יחד עם שאר השכבות
            if (losActive) {{ toggleLos(); }}  // כיבוי מצב LOS אם פעיל, כדי לאפס cursor וכפתור
            clearRadialLosResult();  // ניקוי תוצאת/תצוגת רדיוס-ראייה (כולל עצירת polling וביטול job בשרת אם רץ)
            if (radialLosActive) {{ toggleRadialLos(); }}  // כיבוי מצב רדיוס-ראייה אם פעיל
            clearRadarDopplerResult();  // ניקוי תוצאת/תצוגת תצפית מכ"ם דופלר (כולל עצירת polling וביטול job בשרת אם רץ)
            if (radarActive) {{ toggleRadarDoppler(); }}  // כיבוי מצב תצפית מכ"ם דופלר אם פעיל
            clearElevationLayer();  // מנקה גם שכבה טעונה וגם בחירה באמצע ביצוע (כולל שלב ההמתנה ללחיצה הראשונה)
            heatmapData = [];
            if (map.hasLayer(heatmap)) {{ heatmap.setLatLngs([]); map.removeLayer(heatmap); }}
            allMarkers.forEach(function(m) {{ m.remove(); }});
            allMarkers = [];
            map.closePopup();
            map.setView([31.7683, 35.2137], 8);
            document.title = 'מפת Leaflet משולבת';
        }}

        // ── שכבת גבהים — בחירת אזור ידנית על ידי גרירת עכבר ──

        var elevSelectStart  = null;  // נקודת ההתחלה של סימון האזור (LatLng של Leaflet)
        var elevPreviewRect  = null;  // מלבן תצוגה מקדימה המצויר בזמן הגרירה
        var elevSelecting    = false; // האם המשתמש נמצא באמצע בחירה כרגע — כולל שלב ההמתנה ללחיצה הראשונה
        var _elevMDHandler   = null;  // פניה ל-mousedown handler הממתין, לצורך ביטול לפני שנורה

        function startElevationSelection() {{
            // אם כבר טעונים נתונים — שאל לפני איפוס
            if (elevationActive && elevationLayer) {{
                if (!confirm('שכבת גבהים טעונה. לאפס ולבחור אזור חדש?')) return;
            }}
            // כיבוי שכבה קיימת לפני תחילת בחירה חדשה
            if (elevationLayer) {{ map.removeLayer(elevationLayer); elevationLayer = null; }}
            elevationActive = false;  // איפוס דגל פעילות — השכבה תידלק מחדש אחרי הבחירה
            _clearElevHandles();

            map.dragging.disable();                        // ביטול גרירת המפה — מונע קונפליקט עם גרירת הסימון
            map.getContainer().style.cursor = 'crosshair'; // שינוי הסמן לצלב — מסמן למשתמש שהוא במצב בחירה
            elevSelecting = true;  // מסומן כבר משלב ההמתנה ללחיצה — כדי ש-clearElevationLayer יזהה ויבטל נכון גם לפני קליק

            _elevMDHandler = function(e) {{                // האזנה חד-פעמית ללחיצה ראשונה בלבד
                _elevMDHandler  = null;                    // ההאזנה כבר נורתה — אין מה לבטל יותר
                elevSelectStart = e.latlng;                // שמירת נקודת ההתחלה

                // יצירת מלבן preview ריק בנקודת ההתחלה
                elevPreviewRect = L.rectangle(
                    [e.latlng, e.latlng],  // בהתחלה שתי הפינות זהות — גודל אפס
                    {{
                        color:       '#89b4fa',  // קו כחול-בהיר לתצוגה מקדימה
                        weight:      2,           // עובי הקו
                        dashArray:   '6,4',       // קו מקווקו — מציין שזה תצוגה מקדימה ולא שכבה סופית
                        fillOpacity: 0.08         // מילוי שקוף כמעט — לא מסתיר את המפה
                    }}
                ).addTo(map);

                map.on('mousemove', _updateElevPreview);    // עדכון המלבן בכל תזוזת עכבר
                map.once('mouseup', _finishElevSelection);  // סיום הבחירה בשחרור לחצן העכבר
            }};
            map.once('mousedown', _elevMDHandler);
        }}

        function _updateElevPreview(e) {{
            // עדכון גבולות המלבן לפי המיקום הנוכחי של העכבר
            if (elevPreviewRect && elevSelectStart) {{
                elevPreviewRect.setBounds([elevSelectStart, e.latlng]);  // שתי נקודות מגדירות את המלבן
            }}
        }}

        // ── ידיות עריכת אזור (4 פינות גרירות) — משותף לגבהים ולטמפרטורה ──
        // state = {{rect, handles}} נפרד לכל שכבה (elevHandleState/tempHandleState), כדי לשמר
        // ציור/מצב עצמאיים; color/eps/onFinish הם הפרמטרים שבאמת שונים בין שתי השכבות.
        function _clearRegionHandles(state) {{
            if (state.rect) {{ map.removeLayer(state.rect); state.rect = null; }}
            state.handles.forEach(function(h) {{ map.removeLayer(h); }});
            state.handles = [];
        }}

        function _drawRegionHandles(state, color, bounds, eps, onFinish) {{
            _clearRegionHandles(state);
            state.rect = L.rectangle(bounds, {{
                color: color, weight: 1.5, dashArray: '5,4', fillOpacity: 0, interactive: false
            }}).addTo(map);
            var sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
            var corners = [sw, L.latLng(sw.lat, ne.lng), ne, L.latLng(ne.lat, sw.lng)];
            var handleHtml = '<div style="width:12px;height:12px;background:' + color + ';border:2px solid #fff;'
                           + 'border-radius:3px;cursor:move;box-shadow:0 1px 3px rgba(0,0,0,.4);"></div>';
            var handleIcon = L.divIcon({{ html: handleHtml, className: '', iconSize: [12,12], iconAnchor: [6,6] }});
            corners.forEach(function(corner, i) {{
                var h = L.marker(corner, {{ icon: handleIcon, draggable: true, zIndexOffset: 900 }}).addTo(map);
                h.on('drag', function(ev) {{
                    var p = ev.target.getLatLng();
                    var cur = state.rect.getBounds();
                    var s=cur.getSouth(), n=cur.getNorth(), w=cur.getWest(), e=cur.getEast();
                    if (i===0){{s=p.lat;w=p.lng;}} else if (i===1){{s=p.lat;e=p.lng;}}
                    else if (i===2){{n=p.lat;e=p.lng;}} else {{n=p.lat;w=p.lng;}}
                    var nb = L.latLngBounds([[s,w],[n,e]]);
                    state.rect.setBounds(nb);
                    var nsw=nb.getSouthWest(), nne=nb.getNorthEast();
                    var nc=[nsw,L.latLng(nsw.lat,nne.lng),nne,L.latLng(nne.lat,nsw.lng)];
                    state.handles.forEach(function(hh,j){{ if(j!==i) hh.setLatLng(nc[j]); }});
                }});
                h.on('dragend', function() {{
                    var nb = state.rect.getBounds();
                    var sw2=nb.getSouthWest(), ne2=nb.getNorthEast();
                    if (Math.abs(ne2.lat-sw2.lat)<eps || Math.abs(ne2.lng-sw2.lng)<eps) return;
                    onFinish(nb);
                }});
                state.handles.push(h);
            }});
        }}

        function _clearElevHandles() {{ _clearRegionHandles(elevHandleState); }}

        function _drawElevHandles(bounds) {{
            _drawRegionHandles(elevHandleState, '#89b4fa', bounds, 0.001, _loadElevationForBounds);
        }}

        function _finishElevSelection(e) {{
            map.off('mousemove', _updateElevPreview);       // ניתוק האזנת תזוזת העכבר
            map.dragging.enable();                          // החזרת גרירת המפה
            map.getContainer().style.cursor = '';           // החזרת הסמן הרגיל
            elevSelecting = false;                          // סיום מצב הגרירה

            if (!elevPreviewRect) return;  // בטיחות — לא אמור לקרות

            var bounds = elevPreviewRect.getBounds();       // שליפת הגבולות הסופיים שנבחרו
            map.removeLayer(elevPreviewRect);               // הסרת מלבן התצוגה המקדימה
            elevPreviewRect = null;                         // ניקוי הפניה

            // בדיקה שהאזור שנבחר גדול מספיק — מונע טעינה בלחיצה בלבד ללא גרירה
            var sw = bounds.getSouthWest();
            var ne = bounds.getNorthEast();
            if (Math.abs(ne.lat - sw.lat) < 0.001 || Math.abs(ne.lng - sw.lng) < 0.001) return;

            _drawElevHandles(bounds);  // הצגת מלבן וידיות עריכה
            _loadElevationForBounds(bounds);  // טעינת נתוני גבהים לאזור שנבחר
        }}

        // מנקה את שכבת הגבהים לגמרי — גם אם היא כבר טעונה וגם אם המשתמש באמצע בחירת אזור
        // (כולל שלב ההמתנה ללחיצה הראשונה, לפני mousedown). קריאה יחידה משותפת ל-resetMapState
        // ול-toggleElevationLayer, במקום שני מסלולי ניקוי חלקיים שלא כיסו את כל המצבים.
        function clearElevationLayer() {{
            if (elevationLayer) {{ map.removeLayer(elevationLayer); elevationLayer = null; }}
            if (elevGridLayer)  {{ map.removeLayer(elevGridLayer);  elevGridLayer  = null; }}
            elevationActive = false;
            elevationPoints = [];
            _elevRawData    = [];
            if (elevSelecting) {{
                if (_elevMDHandler) {{ map.off('mousedown', _elevMDHandler); _elevMDHandler = null; }}
                map.off('mousemove', _updateElevPreview);
                map.off('mouseup', _finishElevSelection);
                if (elevPreviewRect) {{ map.removeLayer(elevPreviewRect); elevPreviewRect = null; }}
                map.dragging.enable();
                map.getContainer().style.cursor = '';
                elevSelecting   = false;
                elevSelectStart = null;
            }}
            _clearElevHandles();
        }}

        function _loadElevationForBounds(bounds) {{
            var sw    = bounds.getSouthWest();  // פינה דרום-מערבית של האזור שנבחר
            var ne    = bounds.getNorthEast();  // פינה צפון-מזרחית של האזור שנבחר
            document.title = '__elev_computing__';
            var steps = 9;                      // רשת 10×10 = 100 נקודות — מגבלת Open-Meteo לבקשה אחת
            var locations = [];                 // מערך הנקודות שייבנה ויישלח לשרת

            // בניית רשת אחידה של נקודות על פני האזור שנבחר בלבד
            for (var i = 0; i <= steps; i++) {{
                for (var j = 0; j <= steps; j++) {{
                    locations.push({{
                        latitude:  sw.lat + (ne.lat - sw.lat) * i / steps,  // קו רוחב: מדרום לצפון
                        longitude: sw.lng + (ne.lng - sw.lng) * j / steps   // קו אורך: ממערב למזרח
                    }});
                }}
            }}

            // שליחת בקשה לשרת המקומי שמעביר ל-Open-Meteo
            fetch('http://localhost:5002/elevation', {{
                method:  'POST',                                    // POST — הנקודות בגוף הבקשה
                headers: {{'Content-Type': 'application/json'}},    // הצהרת סוג תוכן
                body:    JSON.stringify({{locations: locations}})    // המרת הנקודות ל-JSON
            }})
            .then(function(r) {{
                if (r.status === 429) return r.json().then(function(d) {{ throw new Error('מכסת API יומית נוצלה — נסה שוב מחר. ' + (d.reason || '')); }});
                if (!r.ok) throw new Error('שגיאת שרת: ' + r.status);  // בדיקת קוד התגובה
                return r.json();                                          // פירוק ה-JSON
            }})
            .then(function(data) {{
                var results = data.results || [];                           // רשימת הנקודות עם גבהים
                if (!results.length) throw new Error('אין נתוני גובה');   // בדיקת תוכן

                // שמירת נקודות הגובה לפופאפ בלחיצה
                elevationPoints = results.map(function(p) {{
                    return {{ lat: p.latitude, lng: p.longitude, elevation: p.elevation }};
                }});

                // נרמול הגבהים לטווח 0–1 ושמירה לשינוי מצב תצוגה
                var elevations = results.map(function(p) {{ return p.elevation; }});
                var minE  = Math.min.apply(null, elevations);
                var maxE  = Math.max.apply(null, elevations);
                var range = maxE - minE || 1;
                _elevRawData = results.map(function(p) {{
                    return {{ lat: p.latitude, lng: p.longitude, v: (p.elevation - minE) / range, raw: p.elevation }};
                }});

                _rebuildElevLayer();
                document.title = '__elev_loaded__';
            }})
            .catch(function(err) {{
                console.error('שגיאת שכבת גבהים:', err);
                elevationActive = false;
                document.title = '__elev_error__';
            }});
        }}

        function toggleElevationLayer() {{
            // אם השכבה פעילה או שהמשתמש באמצע בחירת אזור — כבה/בטל; אחרת — פתח מצב בחירת אזור.
            // הבדיקה כוללת גם elevSelecting (לא רק elevationActive) כדי שכיבוי הכפתור באמצע גרירה
            // (לפני שהנתונים נטענו) יבטל את הבחירה במקום לפתוח בחירה נוספת על גבי הקיימת.
            if (elevationActive || elevSelecting) {{
                clearElevationLayer();
            }} else {{
                startElevationSelection();
            }}
        }}

        var heatmapPickerActive = false;  // מצב בחירת נקודות חום ידנית
        var serversRunning = false;       // מסונכרן מ-Python — מונע שליפת מזג אוויר כשהשרתים כבויים

        function toggleHeatmap() {{
            if (tempHeatLayer || tempSelecting) {{
                clearTempHeatmap();
            }} else {{
                startTempHeatmap();
            }}
        }}

        function startTempHeatmap() {{
            if (tempHeatLayer) {{
                if (!confirm('שכבת טמפרטורה טעונה. לאפס ולבחור אזור חדש?')) return;
                clearTempHeatmap();
            }}
            map.dragging.disable();
            map.getContainer().style.cursor = 'crosshair';
            tempSelecting = true;

            _tempMDHandler = function(e) {{
                _tempMDHandler = null;
                tempSelectStart = e.latlng;
                tempPreviewRect = L.rectangle([e.latlng, e.latlng], {{
                    color: '#f38ba8', weight: 2, dashArray: '6,4', fillOpacity: 0.08
                }}).addTo(map);
                map.on('mousemove', _updateTempPreview);
                map.once('mouseup', _finishTempSelection);
            }};
            map.once('mousedown', _tempMDHandler);
        }}

        function _updateTempPreview(e) {{
            if (tempPreviewRect && tempSelectStart) {{
                tempPreviewRect.setBounds([tempSelectStart, e.latlng]);
            }}
        }}

        function _clearTempHandles() {{ _clearRegionHandles(tempHandleState); }}

        function _drawTempHandles(bounds) {{
            _drawRegionHandles(tempHandleState, '#f38ba8', bounds, 0.01, _loadTempHeatmap);
        }}

        function _finishTempSelection(e) {{
            map.off('mousemove', _updateTempPreview);
            map.dragging.enable();
            map.getContainer().style.cursor = '';
            tempSelecting = false;

            if (!tempPreviewRect) return;
            var bounds = tempPreviewRect.getBounds();
            map.removeLayer(tempPreviewRect);
            tempPreviewRect = null;
            tempSelectStart = null;

            var sw = bounds.getSouthWest();
            var ne = bounds.getNorthEast();
            if (Math.abs(ne.lat - sw.lat) < 0.01 || Math.abs(ne.lng - sw.lng) < 0.01) return;

            _drawTempHandles(bounds);
            _loadTempHeatmap(bounds);
        }}

        function _loadTempHeatmap(bounds) {{
            var sw = bounds.getSouthWest();
            var ne = bounds.getNorthEast();
            document.title = '__heatmap_computing__';

            fetch('http://localhost:5002/temp_grid', {{
                method:  'POST',
                headers: {{'Content-Type': 'application/json'}},
                body:    JSON.stringify({{
                    southwest: {{lat: sw.lat, lng: sw.lng}},
                    northeast: {{lat: ne.lat, lng: ne.lng}}
                }})
            }})
            .then(function(r) {{
                if (r.status === 429) return r.json().then(function(d) {{ throw new Error('מכסת API יומית נוצלה — נסה שוב מחר. ' + (d.reason || '')); }});
                if (!r.ok) throw new Error('שגיאת שרת: ' + r.status);
                return r.json();
            }})
            .then(function(data) {{
                if (!data || !data.length) throw new Error('לא התקבלו נתוני טמפרטורה');

                var temps = data.map(function(p) {{ return p.temperature; }});
                var minT  = Math.min.apply(null, temps);
                var maxT  = Math.max.apply(null, temps);
                var range = maxT - minT || 1;

                _tempRawData = data.map(function(p) {{
                    return {{ lat: p.lat, lng: p.lng, v: 0.05 + 0.9 * (p.temperature - minT) / range, raw: p.temperature }};
                }});

                _rebuildTempLayer();
                if (window.pyBridge && window.pyBridge.onHeatmapLoaded) {{
                    window.pyBridge.onHeatmapLoaded();
                }}
            }})
            .catch(function(err) {{
                console.error('שגיאת מפת חום טמפרטורה:', err);
                document.title = _tempRawData.length > 0 ? '__heatmap_edit_error__' : '__heatmap_error__';
                alert('שגיאה בטעינת נתוני טמפרטורה: ' + err.message);
            }});
        }}

        function clearTempHeatmap() {{
            if (tempHeatLayer) {{ map.removeLayer(tempHeatLayer); tempHeatLayer = null; }}
            if (tempGridLayer)  {{ map.removeLayer(tempGridLayer);  tempGridLayer  = null; }}
            _tempRawData = [];
            if (tempSelecting) {{
                if (_tempMDHandler) {{ map.off('mousedown', _tempMDHandler); _tempMDHandler = null; }}
                map.off('mousemove', _updateTempPreview);
                map.off('mouseup', _finishTempSelection);
                if (tempPreviewRect) {{ map.removeLayer(tempPreviewRect); tempPreviewRect = null; }}
                map.dragging.enable();
                map.getContainer().style.cursor = '';
                tempSelecting = false;
            }}
            _clearTempHandles();
        }}

        function _calcTempRadius() {{
            var zoom     = map.getZoom();
            var pixPerKm = 256 * Math.pow(2, zoom) / 360 / 111 * Math.cos(31.5 * Math.PI / 180);
            return Math.max(10, Math.round(5 * pixPerKm * 0.65));
        }}

        function _calcTempBlur() {{
            return Math.round(_calcTempRadius() * 0.7);
        }}

        function _calcTempMax() {{
            var zoom     = map.getZoom();
            var pixPerKm = 256 * Math.pow(2, zoom) / 360 / 111 * Math.cos(31.5 * Math.PI / 180);
            var gridPx   = 5 * pixPerKm;
            var r        = _calcTempRadius();
            return Math.max(1, Math.PI * r * r / (gridPx * gridPx));
        }}

        map.on('zoomend', function() {{
            if (!_tempRawData.length) return;
            if (tempDisplayMode === 'heat' && tempHeatLayer) {{
                tempHeatLayer.setOptions({{radius: _calcTempRadius(), blur: _calcTempBlur(), max: _calcTempMax()}});
            }}
        }});

        function startHeatmapPicker() {{
            heatmapPickerActive = !heatmapPickerActive;
            if (heatmapPickerActive) {{
                map.getContainer().style.cursor = 'crosshair';
                if (!map.hasLayer(heatmap)) {{ heatmap.addTo(map); }}
            }} else {{
                map.getContainer().style.cursor = '';
            }}
        }}

        function clearHeatmapPoints() {{
            heatmapData = [];
            heatmap.setLatLngs([]);
        }}

        // לחיצה על המפה — picker חום / גובה / מזג אוויר
        map.on('click', function(e) {{
            var lat = e.latlng.lat.toFixed(4);
            var lon = e.latlng.lng.toFixed(4);
            if (heatmapPickerActive) {{
                heatmapData.push([parseFloat(lat), parseFloat(lon), 1.0]);
                heatmap.setLatLngs(heatmapData);
            }} else if (radialLosActive) {{
                // מצב רדיוס-ראייה רדיאלי — לחיצה בודדת (לא זוג כמו LOS) ממקמת/מזיזה משקיף
                // ומציגה תצוגה מקדימה בלבד; החישוב האמיתי מופעל רק בלחיצה מפורשת על "הפעל חישוב"
                if (radialLosLoading) return;  // מתעלם מלחיצות חדשות בזמן שחישוב קודם עדיין רץ
                _placeRadialLosObserver(e.latlng);
            }} else if (radarActive) {{
                // מצב תצפית מכ"ם דופלר — אותה זרימה בדיוק כמו רדיוס-ראייה רדיאלי (לחיצה=משקיף+תצוגה מקדימה בלבד)
                if (radarLoading) return;  // מתעלם מלחיצות חדשות בזמן שחישוב קודם עדיין רץ
                _placeRadarObserver(e.latlng);
            }} else if (losActive) {{
                // losActive בודק לפני elevationActive — מצב LOS גובר על כל שכבה פעילה אחרת
                // מצב LOS פעיל — לחיצה 1 = תצפית, לחיצה 2 = יעד + חישוב + מיד מוכן לצמד הבא
                if (!losCurObs) {{
                    // לחיצה ראשונה — שמירת נקודת התצפית
                    losCurObs    = e.latlng;
                    var sIdx     = losSessions.length;                          // מספר הסשן הבא (לכותרת ולצבע)
                    var col      = _losPalette[sIdx % _losPalette.length];      // צבע ייחודי מהפלטה
                    if (losCurObsMk) {{ map.removeLayer(losCurObsMk); }}        // ניקוי סמן ביניים ישן
                    // ציור סמן עגול מוצק בצבע הסשן בנקודת התצפית — ניתן לגרירה
                    losCurObsMk = L.marker(e.latlng, {{icon: _losMarkerIcon(col, false), draggable: true}}).addTo(map);
                    losCurObsMk.bindTooltip('תצפית ' + (sIdx + 1), {{permanent:false, direction:'top'}});
                }} else {{
                    // לחיצה שנייה — שמירת היעד, יצירת הסשן ושיגור החישוב
                    var sIdx    = losSessions.length;
                    var col     = _losPalette[sIdx % _losPalette.length];       // אותו צבע כמו סמן התצפית
                    // ציור סמן יעד עם מתאר מקווקו להבחנה ויזואלית מסמן התצפית — ניתן לגרירה
                    var tgtMk   = L.marker(e.latlng, {{icon: _losMarkerIcon(col, true), draggable: true}}).addTo(map);
                    tgtMk.bindTooltip('יעד ' + (sIdx + 1), {{permanent:false, direction:'top'}});
                    // קריאת גובה הצופה/היעד משדות הקלט בעת יצירת הצמד — נשמר על הסשן ומשמש גם לחישובים חוזרים אחרי גרירה
                    var obsH = _losObsInput ? parseFloat(_losObsInput.value) : NaN;
                    var tgtH = _losTgtInput ? parseFloat(_losTgtInput.value) : NaN;
                    if (isNaN(obsH)) obsH = 11;
                    if (isNaN(tgtH)) tgtH = 0;
                    losCurObsMk.setTooltipContent('תצפית ' + (sIdx + 1) + ' (+' + obsH + 'מ\\')');
                    tgtMk.setTooltipContent('יעד ' + (sIdx + 1) + ' (+' + tgtH + 'מ\\')');
                    // יצירת אובייקט הסשן — data=null עד שהשרת יחזיר תשובה
                    var session = {{obsMk:losCurObsMk, tgtMk:tgtMk, lineLayers:[], data:null, color:col, idx:sIdx + 1, obsH:obsH, tgtH:tgtH}};
                    losSessions.push(session);               // הוספה למערך הסשנים
                    var obsPoint = losCurObs;                 // שמירת נקודת התצפית לפני האיפוס
                    losCurObs = null; losCurObsMk = null;    // איפוס — מוכן לצמד הבא מיד
                    // גרירת סמן תצפית או יעד — חישוב מחדש אוטומטי של קו הראייה, ללא צורך ביצירת קו חדש
                    session.obsMk.on('dragend', function() {{ _runLos(session.obsMk.getLatLng(), session.tgtMk.getLatLng(), session); }});
                    session.tgtMk.on('dragend', function() {{ _runLos(session.obsMk.getLatLng(), session.tgtMk.getLatLng(), session); }});
                    _runLos(obsPoint, e.latlng, session);    // הפעלת חישוב LOS עם הצמד שנבחר
                }}
            }} else if (elevationActive && elevationPoints.length > 0) {{
                // מציאת נקודת הגובה הקרובה ביותר לנקודת הלחיצה — מוצג רק כשLOS כבוי
                var nearest = null;
                var minDist = Infinity;
                elevationPoints.forEach(function(p) {{
                    var d = Math.pow(p.lat - e.latlng.lat, 2) + Math.pow(p.lng - e.latlng.lng, 2);
                    if (d < minDist) {{ minDist = d; nearest = p; }}
                }});
                if (nearest) {{
                    L.popup({{ className: 'elev-popup' }})
                        .setLatLng(e.latlng)
                        .setContent(
                            '<div style="direction:rtl;font-family:Arial;font-size:13px;text-align:right;">' +
                            '<strong>גובה:</strong> ' + nearest.elevation + " מ'" +
                            '<br><span style="font-size:11px;color:#6c7086;">' +
                            parseFloat(e.latlng.lat).toFixed(4) + ', ' + parseFloat(e.latlng.lng).toFixed(4) +
                            '</span></div>'
                        )
                        .openOn(map);
                }}
            }} else if (serversRunning && !tempSelecting) {{
                fetchWeather(lat, lon);
            }}
        }});

        function loadHeatmapData() {{
            // שליפת נתוני מפת החום משרת מזג האוויר המקומי
            const url = "http://localhost:5002/heatmap_data";

            fetch(url)
                .then(response => {{
                    if (!response.ok) {{
                        throw new Error(`HTTP error! status: ${{response.status}}`);
                    }}
                    return response.json();
                }})
                .then(data => {{
                    // Leaflet.heat מצפה למערך [[lat, lng, intensity], ...]
                    heatmapData = data.map(point => [
                        point.latitude,
                        point.longitude,
                        point.temperature  // עוצמת נקודת החום לפי ערך הטמפרטורה
                    ]);
                    heatmap.setLatLngs(heatmapData);  // עדכון נתוני שכבת החום
                }})
                .catch(error => {{
                    console.error("Error loading heatmap data:", error);
                    alert("שגיאה בטעינת נתוני מפת החום.");
                }});
        }}

        function loadHeatmapDataFromCSV(csvPath) {{
            // קריאה לטעינת נתוני מפת חום — מנותבת לשרת המקומי
            loadHeatmapData();   // נתוני ה-CSV מוגשים דרך weather_server.py
            if (!map.hasLayer(heatmap)) {{
                heatmap.addTo(map);  // הצגה אוטומטית לאחר טעינה מ-CSV
            }}
        }}

        function fetchWeather(lat, lon) {{
            // שליפת מזג אוויר וגובה במקביל — Promise.all מבטיח תצוגה אחת לאחר שתי התשובות
            var weatherPromise = fetch(`http://localhost:5002/weather?lat=${{lat}}&lon=${{lon}}`)
                .then(function(r) {{
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                }});

            var elevationPromise = fetch('http://localhost:5002/elevation', {{
                method:  'POST',
                headers: {{'Content-Type': 'application/json'}},
                body:    JSON.stringify({{locations: [{{latitude: parseFloat(lat), longitude: parseFloat(lon)}}]}})
            }})
            .then(function(r) {{ return r.ok ? r.json() : null; }})
            .catch(function() {{ return null; }});  // כשל בגובה לא מונע הצגת מזג אוויר

            Promise.all([weatherPromise, elevationPromise])
                .then(function(results) {{
                    var data    = results[0];
                    var elevRes = results[1];
                    if (!data.weather || !data.temperature) {{
                        throw new Error("הנתונים שהתקבלו אינם כוללים מזג אוויר או טמפרטורה");
                    }}
                    var elevation = null;
                    if (elevRes && elevRes.results && elevRes.results.length > 0) {{
                        elevation = elevRes.results[0].elevation;
                    }}
                    displayWeatherOnMap(lat, lon, data, elevation);
                }})
                .catch(function(error) {{
                    console.error("Error fetching weather data:", error.message);
                    alert("לא ניתן להחזיר נתוני מזג האוויר: " + error.message);
                }});
        }}

        function displayWeatherOnMap(lat, lon, data, elevation) {{
            try {{
                const weather     = data.weather     || "לא זמין";
                const temperature = data.temperature !== undefined
                    ? `${{data.temperature}}°C`
                    : "לא זמין";
                const elevText    = (elevation !== null && elevation !== undefined)
                    ? elevation + " מ'"
                    : "לא זמין";

                // תוכן Popup — נתוני מזג אוויר וגובה בעברית
                const content = `
                    <div style="text-align:right;direction:rtl;font-family:Arial;font-size:13px;">
                        <div><strong>קו רוחב:</strong>    ${{lat}}</div>
                        <div><strong>קו אורך:</strong>    ${{lon}}</div>
                        <div><strong>מזג אוויר:</strong>  ${{weather}}</div>
                        <div><strong>טמפרטורה:</strong>   ${{temperature}}</div>
                        <div><strong>גובה:</strong>        ${{elevText}}</div>
                    </div>`;

                const marker = L.marker([parseFloat(lat), parseFloat(lon)])
                    .addTo(map);             // הוספת סמן למפה
                allMarkers.push(marker);     // רישום ברשימה לניקוי עתידי
                marker.bindPopup(content).openPopup();  // קישור ופתיחת Popup מיידית

                // לחיצה חוזרת על הסמן — פתיחת ה-Popup שוב אם נסגר
                marker.on('click', function() {{
                    marker.openPopup();
                }});
            }} catch (error) {{
                console.error("Error displaying weather data on map:", error.message);
            }}
        }}

        // ════════════════════════════════════════════════════
        // כלי קווי ראייה (Line of Sight)
        // ════════════════════════════════════════════════════

        // פונקציה: הדלקה/כיבוי מצב LOS
        // הפעלה = cursor crosshair + מוכן לצמד חדש. כיבוי = cursor רגיל. הסשנים הקיימים נשארים.
        function toggleLos() {{
            losActive = !losActive;  // הפיכת המצב
            if (!losActive) {{
                map.getContainer().style.cursor = '';  // שחזור cursor רגיל
                // אם המשתמש כיבה באמצע בחירת צמד (לחץ רק על תצפית) — מנקים סמן ביניים
                if (losCurObsMk) {{ map.removeLayer(losCurObsMk); losCurObsMk = null; }}
                losCurObs = null;  // איפוס נקודת תצפית זמנית
            }} else {{
                map.getContainer().style.cursor = 'crosshair';  // cursor crosshair = מצב בחירת נקודה
            }}
            if (_losFieldsWrapEl) {{
                _losFieldsWrapEl.style.display = losActive ? 'flex' : 'none';  // חשיפה/הסתרה של שדות הגובה
            }}
            if (_losBtnEl) {{
                // עדכון מראה הכפתור: ירוק=פעיל, לבן=כבוי
                _losBtnEl.style.background = losActive ? '#2ecc40' : 'white';
                _losBtnEl.style.color      = losActive ? 'white'  : '#333';
            }}
        }}

        // פונקציה: ניקוי מוחלט — כל הסשנים, קוויהם, סמניהם והפאנל
        function clearLosMap() {{
            losSessions.forEach(function(s) {{
                if (s.obsMk) map.removeLayer(s.obsMk);                    // הסרת סמן תצפית
                if (s.tgtMk) map.removeLayer(s.tgtMk);                    // הסרת סמן יעד
                s.lineLayers.forEach(function(l) {{ map.removeLayer(l); }});  // הסרת קווי LOS
            }});
            losSessions = [];  // ריקון מערך הסשנים
            if (losCurObsMk) {{ map.removeLayer(losCurObsMk); losCurObsMk = null; }}  // ניקוי סמן ביניים
            losCurObs = null;                                               // איפוס נקודת תצפית זמנית
            if (losPanelEl) {{ losPanelEl.remove(); losPanelEl = null; }}  // הסרת הפאנל מה-DOM
        }}

        // פונקציה: הסרת סשן בודד לפי מיקומו במערך losSessions (idx הוא 0-based)
        function _removeSession(idx) {{
            var s = losSessions[idx];
            if (!s) return;  // בטיחות — אם האינדקס לא קיים
            if (s.obsMk) map.removeLayer(s.obsMk);                       // הסרת סמן תצפית
            if (s.tgtMk) map.removeLayer(s.tgtMk);                       // הסרת סמן יעד
            s.lineLayers.forEach(function(l) {{ map.removeLayer(l); }});  // הסרת קווי LOS
            losSessions.splice(idx, 1);  // הסרה מהמערך — splice מעדכן אוטומטית את האינדקסים
            // עדכון מספרי הסשנים הנותרים לשמירת רצף ויזואלי (1, 2, 3...)
            losSessions.forEach(function(s2, i2) {{ s2.idx = i2 + 1; }});
            _redrawPanel();  // ציור מחדש של הפאנל ללא הסשן שהוסר
        }}

        // פונקציה: שליחת בקשת LOS לשרת ועדכון הסשן הספציפי בתשובה
        // obs = LatLng תצפית, tgt = LatLng יעד, session = אובייקט הסשן לעדכון
        function _runLos(obs, tgt, session) {{
            document.title = '__los_loading__';  // איתות ל-Python: חישוב החל
            // בניית URL עם קואורדינטות שתי הנקודות וגבהי הצופה/היעד שנשמרו על הסשן ביצירתו
            var url = 'http://localhost:5002/los?lat1=' + obs.lat + '&lon1=' + obs.lng +
                      '&lat2=' + tgt.lat + '&lon2=' + tgt.lng +
                      '&obs_h=' + (session.obsH != null ? session.obsH : 11) +
                      '&tgt_h=' + (session.tgtH != null ? session.tgtH : 0);
            fetch(url)
            .then(function(r) {{
                if (!r.ok) throw new Error('HTTP ' + r.status);  // שגיאת HTTP
                return r.json();                                   // פענוח JSON
            }}).then(function(data) {{
                if (data.error) throw new Error(data.error);       // שגיאה מהשרת
                session.data = data;               // שמירת נתוני התשובה באובייקט הסשן
                document.title = '__los_loaded__'; // איתות ל-Python: חישוב הצליח
                _drawLosOnMap(session);            // ציור קווים על המפה עבור הסשן הזה
                _redrawPanel();                    // בניית מחדש של הפאנל עם כל הסשנים
            }}).catch(function(err) {{
                // כישלון בחישוב ראשוני (לסשן שעדיין אין לו נתונים) — הסרת הסשן כי אין לו מה להציג
                // כישלון בחישוב מחדש אחרי גרירה (יש כבר data קודם) — משאירים את הסשן והקווים הישנים במקום
                if (!session.data) {{
                    var sIdx = losSessions.indexOf(session);
                    if (sIdx !== -1) {{
                        if (session.obsMk) map.removeLayer(session.obsMk);  // ניקוי סמן תצפית
                        if (session.tgtMk) map.removeLayer(session.tgtMk);  // ניקוי סמן יעד
                        losSessions.splice(sIdx, 1);  // הסרה מהמערך
                    }}
                }}
                document.title = '__los_error__';  // איתות ל-Python: שגיאה
                console.error('LOS error:', err);
                alert('שגיאה בחישוב קו ראייה ' + session.idx + ': ' + err.message);
            }});
        }}

        // פונקציה: ציור קווי LOS של סשן אחד על המפה (ירוק=גלוי, אדום=חסום)
        // האלגוריתם: איחוד נקודות עוקבות עם אותו סטטוס לקטע בצבע אחיד
        function _drawLosOnMap(session) {{
            session.lineLayers.forEach(function(l) {{ map.removeLayer(l); }});  // ניקוי קווים ישנים של הסשן
            session.lineLayers = [];  // איפוס
            var pts = session.data.points;       // נקודות המסלול מהשרת
            if (!pts || pts.length < 2) return;  // מינימום 2 נקודות
            var seg    = [];
            var curVis = pts[0].visible;  // סטטוס ראייה של הנקודה הראשונה
            for (var i = 0; i < pts.length; i++) {{
                var p  = pts[i];
                var ll = [p.lat, p.lon];  // פורמט [lat, lon] לאובייקטי Leaflet
                if (i === 0) {{ seg.push(ll); continue; }}  // נקודה ראשונה — מתחילים קטע, אין קו עדיין
                if (p.visible === curVis) {{
                    seg.push(ll);  // אותו סטטוס — ממשיכים לאסוף לקטע הנוכחי
                }} else {{
                    // שינוי ראות — ציור הקטע שנאסף ופתיחת קטע חדש
                    var color = curVis ? '#00cc44' : '#ff3300';  // ירוק/אדום
                    session.lineLayers.push(L.polyline(seg, {{color:color, weight:4, opacity:0.85}}).addTo(map));
                    seg    = [seg[seg.length - 1], ll];  // הקטע החדש מתחיל מנקודת הגבול (חיבור חלק)
                    curVis = p.visible;                   // עדכון סטטוס הקטע הנוכחי
                }}
            }}
            if (seg.length >= 2) {{
                // ציור הקטע האחרון שנשאר לאחר סיום הלולאה
                var color = curVis ? '#00cc44' : '#ff3300';
                session.lineLayers.push(L.polyline(seg, {{color:color, weight:4, opacity:0.85}}).addTo(map));
            }}
        }}

        // פונקציה: בנייה מחדש של פאנל הגרפים — עמודה אחת לכל סשן, זו לצד זו
        function _redrawPanel() {{
            if (losPanelEl) {{ losPanelEl.remove(); losPanelEl = null; }}  // הסרת פאנל קיים
            // רק סשנים שחישובם הסתיים בהצלחה (data !== null)
            var ready = losSessions.filter(function(s) {{ return s.data !== null; }});
            if (ready.length === 0) return;  // אין נתונים — לא מציגים פאנל
            // מיכל ראשי: נצמד לתחתית, flex-column (כותרת + שורת גרפים)
            losPanelEl = document.createElement('div');
            losPanelEl.style.cssText = 'position:fixed;bottom:0;left:0;right:0;height:230px;background:#1e1e2e;' +
                'border-top:2px solid #444;z-index:9000;display:flex;flex-direction:column;';
            // שורת כותרת עליונה עם כפתור "נקה הכל"
            var header = document.createElement('div');
            header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;' +
                'padding:3px 10px;background:#181825;color:#cdd6f4;font-family:Arial;font-size:13px;' +
                'direction:rtl;flex-shrink:0;';  // flex-shrink:0 — גובה הכותרת לא מתכווץ
            header.innerHTML = '<span>קווי ראייה — חתך שטח</span>';
            var closeAll = document.createElement('button');
            closeAll.textContent = '✕ נקה הכל';  // ✕ נקה הכל
            closeAll.style.cssText = 'background:none;border:none;color:#f38ba8;font-size:12px;cursor:pointer;font-family:Arial;';
            closeAll.onclick = function() {{
                clearLosMap();                        // מחיקת כל הסשנים
                if (losActive) {{ toggleLos(); }}     // כיבוי מצב LOS
            }};
            header.appendChild(closeAll);
            losPanelEl.appendChild(header);
            // שורת גרפים — flex-row: כל סשן בעמודה נפרדת עם רוחב שווה
            var row = document.createElement('div');
            row.style.cssText = 'display:flex;flex-direction:row;flex:1;overflow:hidden;';
            ready.forEach(function(session) {{
                // עמודה לסשן אחד — flex:1 = רוחב שווה לכל הסשנים, min-width:0 מונע גלישה
                var col = document.createElement('div');
                col.style.cssText = 'flex:1;display:flex;flex-direction:column;border-left:1px solid #2a2a3e;min-width:0;';
                // כותרת הסשן: "קו ראייה N" בצבע הסשן + כפתור X להסרה בודדת
                var subHdr = document.createElement('div');
                subHdr.style.cssText = 'display:flex;justify-content:space-between;align-items:center;' +
                    'padding:1px 6px;background:#181825;flex-shrink:0;';
                var lbl = document.createElement('span');
                lbl.textContent = 'קו ראייה ' + session.idx;  // קו ראייה N
                lbl.style.cssText = 'font:11px Arial;color:' + session.color + ';';  // צבע ייחודי
                var rmBtn = document.createElement('button');
                rmBtn.textContent = '✕';  // ✕
                rmBtn.style.cssText = 'background:none;border:none;color:#666;font-size:11px;cursor:pointer;';
                // IIFE — לכידת session.idx הנכון; בלעדיה כל כפתורי ה-X ישתמשו בערך האחרון של הלולאה
                rmBtn.onclick = (function(capturedIdx) {{
                    return function() {{ _removeSession(capturedIdx - 1); }};  // capturedIdx-1 = אינדקס 0-based
                }})(session.idx);
                subHdr.appendChild(lbl);
                subHdr.appendChild(rmBtn);
                col.appendChild(subHdr);
                // canvas לגרף הסשן — flex:1 ממלא את שארית גובה העמודה
                var canvas = document.createElement('canvas');
                canvas.style.cssText = 'flex:1;width:100%;display:block;';
                col.appendChild(canvas);
                row.appendChild(col);
                // setTimeout(0) — מבטיח שה-canvas כבר ב-DOM עם גודל בפועל לפני הציור
                // (בלעדיו offsetWidth/Height = 0 כי הדפדפן טרם חישב את הפריסה)
                (function(cv, s) {{
                    setTimeout(function() {{ _drawProfileSingle(cv, s); }}, 0);
                }})(canvas, session);
            }});
            losPanelEl.appendChild(row);
            document.body.appendChild(losPanelEl);  // הוספת הפאנל ל-DOM
        }}

        // פונקציה: ציור פרופיל שטח + קו ראייה עבור סשן בודד על canvas נתון
        // canvas = אלמנט canvas, session = אובייקט הסשן (עם session.data מהשרת)
        function _drawProfileSingle(canvas, session) {{
            var data = session.data;
            if (!data || !data.points || data.points.length < 2) return;  // בטיחות
            // קביעת גודל ה-canvas לגודל ה-DOM בפועל — נחוץ כי CSS לבדו לא מגדיר pixel size
            canvas.width  = canvas.offsetWidth  || 200;
            canvas.height = canvas.offsetHeight || 180;
            var ctx = canvas.getContext('2d');  // הקשר ציור דו-ממדי
            var pts = data.points;
            var W = canvas.width, H = canvas.height;
            // שוליים: l לציר Y, r ימין, t עליון (לכותרת), b תחתון (לציר X)
            var PAD = {{l:44, r:6, t:18, b:24}};
            var cW = W - PAD.l - PAD.r;  // רוחב אזור הגרף
            var cH = H - PAD.t - PAD.b;  // גובה אזור הגרף

            // חישוב טווח גבהים — כולל גם גובה השטח וגם גובה קו הראייה
            var minE = Infinity, maxE = -Infinity;
            pts.forEach(function(p) {{
                if (p.elevation < minE) minE = p.elevation;
                if (p.elevation > maxE) maxE = p.elevation;
                if (p.los_h     < minE) minE = p.los_h;
                if (p.los_h     > maxE) maxE = p.los_h;
            }});
            var eRange = maxE - minE || 1;  // || 1 מונע חלוקה באפס

            // המרת אינדקס נקודה → X בפיקסלים
            function xOf(i)   {{ return PAD.l + (i / (pts.length - 1)) * cW; }}
            // המרת גובה → Y בפיקסלים (הפוכה: גבוה=Y קטן כי canvas מניה מלמעלה)
            function yOf(val) {{ return PAD.t + cH - (val - minE) / eRange * cH; }}

            // רקע כהה
            ctx.fillStyle = '#1e1e2e'; ctx.fillRect(0, 0, W, H);

            // ציר Y — 4 חלוקות עם קווי רשת ותוויות גובה
            ctx.fillStyle = '#666'; ctx.font = '9px Arial'; ctx.textAlign = 'right';
            for (var s = 0; s <= 3; s++) {{
                var val = minE + (eRange * s / 3);  // ערך גובה לכל חלוקה
                var y   = yOf(val);
                ctx.fillText(Math.round(val) + 'מ', PAD.l - 3, y + 3);  // תווית ציר Y
                ctx.strokeStyle = '#2a2a3e'; ctx.lineWidth = 0.5;         // קו רשת
                ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cW, y); ctx.stroke();
            }}

            // ציר X — עד 6 תוויות מרחק בק"מ
            ctx.fillStyle = '#666'; ctx.textAlign = 'center'; ctx.font = '9px Arial';
            var xSteps = Math.min(6, pts.length - 1);  // לא יותר נקודות ממה שיש
            for (var xi = 0; xi <= xSteps; xi++) {{
                var idx = Math.round(xi / xSteps * (pts.length - 1));
                ctx.fillText(pts[idx].dist_km + '', xOf(idx), PAD.t + cH + 14);  // מרחק בק"מ
            }}

            // שטח טופוגרפיה — מצולע סגור מלא בירוק-זית שקוף
            ctx.beginPath();
            ctx.moveTo(xOf(0), yOf(pts[0].elevation));
            for (var i = 1; i < pts.length; i++) {{
                ctx.lineTo(xOf(i), yOf(pts[i].elevation));  // קו לכל נקודת שטח
            }}
            ctx.lineTo(xOf(pts.length - 1), PAD.t + cH);  // ירידה לבסיס (ציר X)
            ctx.lineTo(xOf(0), PAD.t + cH);                // חזרה לנקודת ההתחלה
            ctx.closePath();
            ctx.fillStyle   = 'rgba(101,163,13,0.45)'; ctx.fill();
            ctx.strokeStyle = '#65a30d'; ctx.lineWidth = 1; ctx.stroke();

            // קו הראייה — קטע לכל זוג נקודות עוקבות, ירוק=גלוי / אדום=חסום
            // los_h = הגובה המינימלי שמאפשר ראייה לנקודה זו מנקודת התצפית
            for (var i = 1; i < pts.length; i++) {{
                ctx.beginPath();
                ctx.moveTo(xOf(i - 1), yOf(pts[i - 1].los_h));  // גובה קו ראייה בנקודה הקודמת
                ctx.lineTo(xOf(i),     yOf(pts[i].los_h));       // גובה קו ראייה בנקודה הנוכחית
                ctx.strokeStyle = pts[i].visible ? '#00cc44' : '#ff3300';
                ctx.lineWidth = 1.5; ctx.stroke();
            }}

            // שורת מידע עליונה: מרחק כולל + חסימה ראשונה (אם יש)
            var info = data.total_km + ' ק"מ';
            if (data.first_block_km !== null) {{
                info += '  ⛔ ' + data.first_block_km + 'ק';  // מרחק חסימה ראשונה
            }} else {{
                info += '  ✓';  // ✓ ראייה מלאה לאורך כל המסלול
            }}
            ctx.fillStyle = '#aaa'; ctx.font = '10px Arial'; ctx.textAlign = 'center';
            ctx.fillText(info, PAD.l + cW / 2, PAD.t - 3);  // מעל אזור הגרף
        }}

        // ── "עמדות שמורות" — UI משותף לשלושת כלי התצפית (LOS/רדיוס-ראייה/מכ"ם-דופלר) ──
        // שמירה/טעינה/מחיקה של מיקום+פרמטרים תחת שם, דרך /stations/* ב-weather_server.py.
        var _stationsCache = {{}};  // toolKey -> [{{name, params}}, ...] — מטמון הרשימה האחרונה שנשלפה, לצורך טעינה בלי fetch נוסף
        function _buildStationUI(parentEl, toolKey, fieldMap, getObsFn, placeObsFn, redrawFn) {{
            // parentEl: לאן להוסיף את ה-UI. toolKey: 'los'/'radial_los'/'radar_doppler'.
            // fieldMap: {{paramName: inputElement}} — כל שדות הכלי (חוץ ממיקום, המטופל בנפרד).
            // getObsFn: ()=>L.LatLng|null — מיקום נוכחי (null אם אין, כמו ב-LOS). placeObsFn(latlng): ממקם משקיף.
            // redrawFn: ()=>void — מצייר מחדש תצוגה מקדימה אחרי טעינת עמדה (אם רלוונטי לכלי).
            var row1 = L.DomUtil.create('div', '', parentEl);
            row1.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:2px;';
            var nameInput = L.DomUtil.create('input', '', row1);
            nameInput.type = 'text'; nameInput.placeholder = 'שם עמדה';
            nameInput.style.cssText = 'flex:1;font-size:10px;padding:2px 3px;border:1px solid #ccc;border-radius:3px;direction:rtl;min-width:0;';
            var saveBtn = L.DomUtil.create('a', '', row1);
            saveBtn.href = '#'; saveBtn.title = 'שמור עמדה נוכחית תחת השם שהוזן';
            saveBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            saveBtn.innerHTML = '&#128190;';  // 💾

            var row2 = L.DomUtil.create('div', '', parentEl);
            row2.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:2px;';
            var stationSelect = L.DomUtil.create('select', '', row2);
            stationSelect.style.cssText = 'flex:1;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;min-width:0;';
            var loadBtn = L.DomUtil.create('a', '', row2);
            loadBtn.href = '#'; loadBtn.title = 'טען עמדה נבחרת';
            loadBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            loadBtn.innerHTML = '&#128194;';  // 📂
            var delBtn = L.DomUtil.create('a', '', row2);
            delBtn.href = '#'; delBtn.title = 'מחק עמדה נבחרת';
            delBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            delBtn.innerHTML = '&#128465;';  // 🗑

            function _refreshList() {{
                fetch('http://localhost:5002/stations/list?tool=' + toolKey)
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    var stations = data.stations || [];
                    _stationsCache[toolKey] = stations;
                    stationSelect.innerHTML = '';
                    if (stations.length === 0) {{
                        var opt = L.DomUtil.create('option', '', stationSelect);
                        opt.textContent = '(אין עמדות שמורות)'; opt.disabled = true; opt.selected = true;
                        return;
                    }}
                    stations.forEach(function(s) {{
                        var opt = L.DomUtil.create('option', '', stationSelect);
                        opt.value = s.name; opt.textContent = s.name;
                    }});
                }})
                .catch(function() {{ /* כשל רשת בטעינת הרשימה — לא קריטי, אפשר לנסות שוב */ }});
            }}
            _refreshList();  // טוען את הרשימה מיד עם בניית ה-Control

            L.DomEvent.on(saveBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                var name = nameInput.value.trim();
                if (!name) {{ alert('הזן שם לעמדה'); return; }}
                var params = {{}};
                Object.keys(fieldMap).forEach(function(key) {{
                    var el = fieldMap[key];
                    params[key] = (el.type === 'checkbox') ? el.checked : el.value;
                }});
                var obs = getObsFn ? getObsFn() : null;
                if (obs) {{ params.lat = obs.lat; params.lon = obs.lng; }}
                fetch('http://localhost:5002/stations/save', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{tool: toolKey, name: name, params: params}})
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    if (data.error) throw new Error(data.error);
                    nameInput.value = '';
                    _refreshList();
                }})
                .catch(function(err) {{ alert('שגיאה בשמירת עמדה: ' + err.message); }});
            }});

            L.DomEvent.on(loadBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                var name = stationSelect.value;
                var stations = _stationsCache[toolKey] || [];
                var station = stations.filter(function(s) {{ return s.name === name; }})[0];
                if (!station) return;
                var params = station.params;
                Object.keys(fieldMap).forEach(function(key) {{
                    if (params[key] === undefined) return;
                    var el = fieldMap[key];
                    if (el.type === 'checkbox') {{ el.checked = (params[key] === true || params[key] === 'true'); }}
                    else {{ el.value = params[key]; }}
                    // עבור select/checkbox — מדמה אירוע 'change' כדי שמאזינים (כמו הצגת/הסתרת שדות מערך-מופעים) יופעלו,
                    // כי הגדרת .value/.checked ישירות בקוד לא מפעילה 'change' באופן טבעי כמו לחיצת משתמש
                    if (el.tagName === 'SELECT' || el.type === 'checkbox') {{ el.dispatchEvent(new Event('change')); }}
                }});
                if (params.lat !== undefined && params.lon !== undefined) {{
                    var latlng = L.latLng(parseFloat(params.lat), parseFloat(params.lon));
                    if (placeObsFn) placeObsFn(latlng);  // ממקם משקיף — קורא גם לציור תצוגה מקדימה עם השדות המעודכנים
                    map.panTo(latlng);
                }}
                if (redrawFn) redrawFn();  // רענון נוסף (זול, ללא נזק) — מבטיח עקביות גם אם אין מיקום לכלי הזה
            }});

            L.DomEvent.on(delBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                var name = stationSelect.value;
                if (!name) return;
                if (!confirm('למחוק את העמדה "' + name + '"?')) return;
                fetch('http://localhost:5002/stations/delete', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{tool: toolKey, name: name}})
                }})
                .then(function() {{ _refreshList(); }})
                .catch(function() {{ /* כשל רשת במחיקה — לא קריטי */ }});
            }});
        }}

        // יצירת כפתור 👁 כ-Leaflet Control בפינה הימנית עליונה
        // L.Control.extend יוצר מחלקה חדשה שיורשת מ-L.Control (מנגנון הרחבה של Leaflet)
        var LosControl = L.Control.extend({{
            options: {{ position: 'topright' }},  // מיקום על המפה
            // onAdd נקרא ע"י Leaflet כשה-Control מתווסף למפה — מחזיר אלמנט DOM
            onAdd: function() {{
                // מיכל בסגנון חופשי (לא leaflet-bar) כדי לאפשר שילוב כפתור + שדות קלט בשורה אחת
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cssText = 'display:flex;align-items:center;gap:5px;background:white;' +
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:3px 6px;font-family:Arial;';

                var btn = L.DomUtil.create('a', '', container);
                btn.href  = '#';           // ללא ניווט — מונע גלילה לראש הדף
                btn.title = 'קו ראייה';   // tooltip בעת hover
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;' +
                    'width:28px;height:28px;font-size:15px;background:white;color:#333;text-decoration:none;' +
                    'border-radius:4px;cursor:pointer;flex-shrink:0;opacity:0.4;pointer-events:none;';  // מנוטרל עד שהמפה מוכנה (map.whenReady, בהמשך)
                btn.innerHTML = '&#128065;';  // קוד Unicode לאייקון 👁
                _losBtnEl = btn;              // שמירת הפניה לשינוי צבע ב-toggleLos
                // stopPropagation — מניעת הגעת הלחיצה ל-map.on('click') שהייתה בוחרת נקודת LOS
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;  // הגנה נוספת מעבר ל-pointer-events — המפה/שרתים לא מוכנים
                    toggleLos();
                }});

                // שדות גובה הצופה/היעד — מוסתרים כברירת מחדל, נחשפים רק אחרי בחירת הכלי (toggleLos),
                // כמו כלי רדיוס-הראייה הרדיאלי — אייקון בלבד קודם, פרמטרים רק אחרי בחירה מפורשת.
                // עמודה (לא שורה כמו קודם) כדי לפנות מקום ל"עמדות שמורות" מתחת לשדות הגובה עצמם
                var losFieldsWrap = L.DomUtil.create('div', '', container);
                losFieldsWrap.style.cssText = 'display:none;flex-direction:column;gap:2px;';
                _losFieldsWrapEl = losFieldsWrap;

                var heightsRow = L.DomUtil.create('div', '', losFieldsWrap);
                heightsRow.style.cssText = 'display:flex;align-items:center;gap:5px;';

                function _mkHeightField(labelText, defaultVal, tip) {{
                    var wrap = L.DomUtil.create('label', '', heightsRow);
                    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;font-size:9px;color:#666;line-height:1.2;';
                    wrap.title = tip;
                    var lbl = L.DomUtil.create('span', '', wrap);
                    lbl.textContent = labelText;
                    var inp = L.DomUtil.create('input', '', wrap);
                    inp.type = 'number'; inp.value = defaultVal; inp.step = '1';
                    inp.style.cssText = 'width:36px;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;';
                    return inp;
                }}
                _losObsInput = _mkHeightField('צופה (מ\\')', 11, 'גובה הצופה מעל הקרקע, במטרים');
                _losTgtInput = _mkHeightField('יעד (מ\\')',  0,  'גובה היעד מעל הקרקע, במטרים');

                // "עמדה" ל-LOS = רק גובהי צופה/יעד (אין מיקום קבוע לשמור — כל שימוש מתחיל בלחיצה חדשה)
                _buildStationUI(losFieldsWrap, 'los', {{obs_h: _losObsInput, tgt_h: _losTgtInput}}, null, null, null);

                L.DomEvent.disableClickPropagation(container);  // הגנה נוספת על כל ה-Control
                L.DomEvent.disableScrollPropagation(container); // מניעת זום במפה בעת גלילה/שינוי ערך בשדה המספרי
                return container;
            }}
        }});
        new LosControl().addTo(map);  // הוספת ה-Control למפה

        // ── כלי רדיוס-ראייה רדיאלי (Viewshed מכומת) — כלי נפרד מ-LOS, פוליגון גבול יחיד ──
        function _radialLosMarkerIcon() {{
            // אייקון סמן התצפית — עיגול מלא בצבע הצהוב הייחודי לכלי הזה (לא חופף לאף שכבה אחרת)
            return L.divIcon({{
                html: '<div style="width:16px;height:16px;border-radius:50%;background:#f9e2af;border:2px solid #333;"></div>',
                className: '', iconSize: [16,16], iconAnchor: [8,8]
            }});
        }}

        function _radialHandleIcon() {{
            // אייקון ידית גרירה לזווית/טווח — עיגול קטן יותר, אותו צבע כמו סמן התצפית
            return L.divIcon({{
                html: '<div style="width:12px;height:12px;border-radius:50%;background:#f9e2af;border:2px solid #333;cursor:move;"></div>',
                className: '', iconSize: [12,12], iconAnchor: [6,6]
            }});
        }}

        function _placeRadialLosObserver(latlng) {{
            // ממקם/מזיז את סמן המשקיף — בשימוש הן ע"י לחיצה על המפה והן ע"י טעינת "עמדה שמורה"
            // (ר' _buildStationUI), כדי לא לשכפל את לוגיקת יצירת הסמן בשני מקומות
            clearRadialLosResult();  // ניקוי תוצאה/תצוגה מקדימה קודמת — משקיף חדש בכל הפעלה
            radialLosObs = latlng;
            radialLosObsMk = L.marker(latlng, {{icon: _radialLosMarkerIcon(), draggable: true}}).addTo(map);
            radialLosObsMk.bindTooltip('תצפית רדיוס ראייה', {{permanent:false, direction:'top'}});
            radialLosObsMk.on('dragend', function() {{
                radialLosObs = radialLosObsMk.getLatLng();
                _updateRadialLosPreview();  // רק מעדכן תצוגה מקדימה — לא מריץ חישוב אוטומטית
            }});
            _updateRadialLosPreview();  // מציג תצוגה מקדימה מיידית (מהשדות הנוכחיים) — לא מפעיל חישוב
        }}

        function _updateRadialLosPreview() {{
            // מצייר/מעדכן את שני קווי התצוגה המקדימה (אזימוט התחלה/סוף) + הידיות בקצותיהם,
            // לפי הערכים הנוכחיים בשדות. לא שולח שום בקשה לשרת — חישוב גיאומטרי מקומי בלבד.
            if (!radialLosObs) return;  // אין עדיין נקודת תצפית — אין מה לצייר
            var rangeKm  = _radialRangeInput ? parseFloat(_radialRangeInput.value) : NaN;
            var startDeg = _radialStartInput ? parseFloat(_radialStartInput.value) : NaN;
            var endDeg   = _radialEndInput   ? parseFloat(_radialEndInput.value)   : NaN;
            if (isNaN(rangeKm))  rangeKm  = 5;   // ברירת מחדל — תואמת לברירת המחדל בשרת
            if (isNaN(startDeg)) startDeg = 315; // ברירת מחדל — מגזר 90° סביב צפון, לא מעגל מלא חופף
            if (isNaN(endDeg))   endDeg   = 45;
            var startPt = _destPointJs(radialLosObs, startDeg, rangeKm * 1000);
            var endPt   = _destPointJs(radialLosObs, endDeg,   rangeKm * 1000);
            if (radialLosStartLn) map.removeLayer(radialLosStartLn);  // מנקה קו קודם לפני ציור מחדש
            if (radialLosEndLn)   map.removeLayer(radialLosEndLn);
            radialLosStartLn = L.polyline([radialLosObs, startPt], {{color:'#f9e2af', weight:1.5, dashArray:'4,4'}}).addTo(map);
            radialLosEndLn   = L.polyline([radialLosObs, endPt],   {{color:'#f9e2af', weight:1.5, dashArray:'4,4'}}).addTo(map);
            if (!radialLosStartMk) {{  // יוצר את הידית פעם אחת בלבד — בפעמים הבאות רק מזיז אותה
                radialLosStartMk = L.marker(startPt, {{icon: _radialHandleIcon(), draggable:true}}).addTo(map);
                radialLosStartMk.on('drag', function(ev) {{ _onRadialHandleDrag(ev, 'start'); }});
            }} else {{
                radialLosStartMk.setLatLng(startPt);
            }}
            if (!radialLosEndMk) {{
                radialLosEndMk = L.marker(endPt, {{icon: _radialHandleIcon(), draggable:true}}).addTo(map);
                radialLosEndMk.on('drag', function(ev) {{ _onRadialHandleDrag(ev, 'end'); }});
            }} else {{
                radialLosEndMk.setLatLng(endPt);
            }}
        }}

        function _onRadialHandleDrag(ev, which) {{
            // גרירת ידית — קובעת גם אזימוט (רק לידית הזו) וגם טווח משותף (שתי הידיות זזות לאותו רדיוס חדש),
            // כי כל ידית היא נקודה דו-ממדית חופשית אבל range_km הוא שדה אחד משותף למגזר כולו.
            if (!radialLosObs) return;
            var p = ev.target.getLatLng();
            var bearing = _bearingDeg(radialLosObs, p);   // הזווית של הידית הזו בלבד
            var distM   = _haversineM(radialLosObs, p);    // המרחק — משותף לשתי הידיות
            if (which === 'start' && _radialStartInput) _radialStartInput.value = bearing.toFixed(1);
            if (which === 'end'   && _radialEndInput)   _radialEndInput.value   = bearing.toFixed(1);
            if (_radialRangeInput) _radialRangeInput.value = (distM / 1000).toFixed(2);  // מעדכן את שדה הטווח המשותף
            _updateRadialLosPreview();  // מצייר מחדש את שני הקווים ברדיוס החדש + הזוויות המעודכנות
        }}

        function _runRadialLos() {{
            // מפעיל את החישוב האמיתי בשרת (בניגוד לתצוגה המקדימה, שהיא מקומית בלבד) — נקרא רק
            // בלחיצה מפורשת על "הפעל חישוב", לא אוטומטית בלחיצה על המפה או בגרירת ידית.
            if (!radialLosObs || radialLosLoading) return;
            var rangeKm    = _radialRangeInput    ? parseFloat(_radialRangeInput.value)    : NaN;
            var minRangeKm = _radialMinRangeInput ? parseFloat(_radialMinRangeInput.value) : NaN;
            var stepDeg    = _radialStepInput     ? parseFloat(_radialStepInput.value)     : NaN;
            var startDeg   = _radialStartInput    ? parseFloat(_radialStartInput.value)    : NaN;
            var endDeg     = _radialEndInput      ? parseFloat(_radialEndInput.value)      : NaN;
            var obsH       = _radialObsInput      ? parseFloat(_radialObsInput.value)      : NaN;
            var tgtH       = _radialTgtInput      ? parseFloat(_radialTgtInput.value)      : NaN;
            var marginDeg  = _radialMarginInput   ? parseFloat(_radialMarginInput.value)   : NaN;
            var vCenter    = _radialVCenterInput  ? parseFloat(_radialVCenterInput.value)  : NaN;
            var vWidth     = _radialVWidthInput   ? parseFloat(_radialVWidthInput.value)   : NaN;
            if (isNaN(rangeKm))    rangeKm = 5;
            if (isNaN(minRangeKm)) minRangeKm = 5;
            if (isNaN(stepDeg))    stepDeg = 10;
            if (isNaN(startDeg))   startDeg = 315;
            if (isNaN(endDeg))     endDeg = 45;
            if (isNaN(obsH))       obsH = 11;
            if (isNaN(tgtH))       tgtH = 0;
            if (isNaN(marginDeg))  marginDeg = 0;
            if (isNaN(vCenter))    vCenter = 0;
            if (isNaN(vWidth))     vWidth = 4;
            radialLosLoading = true;
            document.title = '__radial_los_loading__';  // איתות ל-Python — שורת לוג
            if (radialLosInfoEl) radialLosInfoEl.textContent = 'מתחיל חישוב…';
            if (_radialCancelBtnEl) _radialCancelBtnEl.style.display = 'block';  // מציג את כפתור הביטול רק בזמן ריצה
            var url = 'http://localhost:5002/los_radial/start?lat=' + radialLosObs.lat + '&lon=' + radialLosObs.lng +
                      '&range_km=' + rangeKm + '&min_range_km=' + minRangeKm + '&angle_step_deg=' + stepDeg +
                      '&start_bearing_deg=' + startDeg + '&end_bearing_deg=' + endDeg +
                      '&obs_h=' + obsH + '&tgt_h=' + tgtH + '&ridge_margin_deg=' + marginDeg +
                      '&vertical_center_deg=' + vCenter + '&vertical_width_deg=' + vWidth;
            fetch(url)
            .then(function(r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
            .then(function(data) {{
                if (data.error) throw new Error(data.error);
                radialLosJobId = data.job_id;
                radialLosPollTimer = setInterval(_pollRadialLosStatus, 1000);  // בדיקת התקדמות כל שנייה
            }})
            .catch(function(err) {{
                radialLosLoading = false;
                document.title = '__radial_los_error__';
                if (radialLosInfoEl) radialLosInfoEl.textContent = '';
                if (_radialCancelBtnEl) _radialCancelBtnEl.style.display = 'none';
                alert('שגיאה בהפעלת חישוב רדיוס ראייה: ' + err.message);
            }});
        }}

        function _pollRadialLosStatus() {{
            // נקרא כל שנייה בזמן שה-job רץ — בודק התקדמות, מצייר תוצאה סופית כשמסתיים
            if (!radialLosJobId) return;
            fetch('http://localhost:5002/los_radial/status?job_id=' + radialLosJobId)
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                if (data.status === 'running') {{
                    if (radialLosInfoEl) {{
                        var total = data.batches_total;
                        radialLosInfoEl.textContent = total
                            ? 'מחשב… ' + data.batches_done + '/' + total + ' (עד כמה דקות בטווח ארוך)'
                            : 'מתחיל…';
                    }}
                    return;  // עדיין רץ — ממתין ל-tick הבא, לא עוצר את ה-polling
                }}
                clearInterval(radialLosPollTimer);  // ה-job הסתיים (הצליח/נכשל/בוטל) — מפסיק את ה-polling
                radialLosPollTimer = null;
                radialLosLoading = false;
                if (_radialCancelBtnEl) _radialCancelBtnEl.style.display = 'none';
                if (data.status === 'done') {{
                    document.title = '__radial_los_loaded__';
                    _drawRadialLosPolygon(data.result);
                    if (radialLosInfoEl) radialLosInfoEl.textContent =
                        data.result.range_km + ' ק"מ, ' + data.result.n_bearings + ' כיוונים, ' +
                        data.result.clear_count + ' פנויים לגמרי';
                }} else if (data.status === 'error') {{
                    document.title = '__radial_los_error__';
                    if (radialLosInfoEl) radialLosInfoEl.textContent = '';
                    alert('שגיאה בחישוב רדיוס ראייה: ' + (data.error || 'לא ידועה'));
                }} else if (data.status === 'cancelled') {{
                    document.title = '__radial_los_cancelled__';
                    if (radialLosInfoEl) radialLosInfoEl.textContent = '';
                }}
                radialLosJobId = null;
            }})
            .catch(function() {{
                // כשל רשת בבדיקת סטטוס בודדת — לא עוצר את ה-polling, ה-tick הבא ינסה שוב
            }});
        }}

        function _drawRadialLosPolygon(result) {{
            // מצייר את הפוליגון הסופי (מחושב, לא תצוגה מקדימה) + קו "חישור" צבעוני לכל כיוון —
            // ירוק = הגיע פנוי עד הטווח המלא (blocked=false), אדום = נחסם לפני כן (blocked=true).
            // אותם צבעים בדיוק כמו קו-הראייה הרגיל (_drawLosOnMap) — עקביות חזותית בין שני הכלים.
            // מזיז גם את ידיות הגרירה לקצוות הקשת האמיתיים, כדי שאפשר להמשיך לכוון ולהריץ שוב.
            if (radialLosPolygon) {{ map.removeLayer(radialLosPolygon); radialLosPolygon = null; }}
            radialLosSpokes.forEach(function(s) {{ map.removeLayer(s); }});  // ניקוי חישורים מחישוב קודם
            radialLosSpokes = [];
            var pts = result.rays.map(function(r) {{ return [r.lat, r.lon]; }});
            if (result.span_deg < 360) {{
                pts.unshift([result.observer_lat, result.observer_lon]);  // פרוסת-פיצה — כולל נקודת המשקיף כקודקוד
            }}
            if (pts.length >= 3) {{  // פוליגון תקין דורש 3+ קודקודים — אם לא, מדלגים על הפוליגון (החישורים עדיין מצוירים)
                radialLosPolygon = L.polygon(pts, {{
                    color: '#f9e2af', weight: 1.5, fillColor: '#f9e2af', fillOpacity: 0.12  // רקע כללי מעומעם — הצבע העיקרי עכשיו בחישורים
                }}).addTo(map);
            }}
            var obsLatLng = L.latLng(result.observer_lat, result.observer_lon);
            var minRangeM = (result.min_range_km || 0) * 1000;  // תחילת כל חישור — גבול אזור העיוור, לא המשקיף עצמו
            var rangeM    = result.range_km * 1000;  // סוף הטווח המבוקש — הקו האדום ממשיך עד כאן, לא נעצר בנקודת החסימה
            result.rays.forEach(function(r) {{
                var nearPt  = _destPointJs(obsLatLng, r.bearing_deg, minRangeM);  // נקודת ההתחלה בפועל של הדגימה לכיוון הזה
                var clearPt = L.latLng(r.lat, r.lon);  // הנקודה הרחוקה ביותר שעדיין רואים ממנה (קודקוד הפוליגון)
                // ירוק — מתחילת הדגימה ועד הנקודה הגלויה האחרונה (תמיד מצויר, גם אם הכל גלוי)
                radialLosSpokes.push(L.polyline([nearPt, clearPt], {{color: '#00cc44', weight: 3}}).addTo(map));
                if (r.blocked) {{
                    // אדום — ממשיך מהנקודה הגלויה האחרונה עד סוף הטווח המבוקש (לא רק עד נקודת החסימה)
                    var farPt = _destPointJs(obsLatLng, r.bearing_deg, rangeM);
                    radialLosSpokes.push(L.polyline([clearPt, farPt], {{color: '#ff3300', weight: 3}}).addTo(map));
                }}
            }});
            if (result.rays.length > 0) {{  // הזזת הידיות לקצוות הקשת האמיתיים, לא לקצה התצוגה המקדימה הישן
                var firstRay = result.rays[0], lastRay = result.rays[result.rays.length - 1];
                if (radialLosStartMk) radialLosStartMk.setLatLng([firstRay.lat, firstRay.lon]);
                if (radialLosEndMk)   radialLosEndMk.setLatLng([lastRay.lat, lastRay.lon]);
            }}
        }}

        function _cancelRadialLos() {{
            // כפתור "בטל" — עוצר מיד בצד הלקוח (בלי לחכות לתשובת השרת), ומודיע גם לשרת שיפסיק
            if (radialLosPollTimer) {{ clearInterval(radialLosPollTimer); radialLosPollTimer = null; }}
            if (radialLosJobId) {{
                fetch('http://localhost:5002/los_radial/cancel?job_id=' + radialLosJobId, {{method:'POST'}});
            }}
            radialLosJobId = null;
            radialLosLoading = false;
            if (_radialCancelBtnEl) _radialCancelBtnEl.style.display = 'none';
            if (radialLosInfoEl) radialLosInfoEl.textContent = '';
        }}

        function clearRadialLosResult() {{
            // ניקוי מלא — נקרא מ-resetMapState וגם בהצבת משקיף חדש (לא נערמים תוצאות ישנות)
            _cancelRadialLos();  // עוצר polling + מבטל job בשרת אם עדיין רץ
            if (radialLosObsMk)   {{ map.removeLayer(radialLosObsMk);   radialLosObsMk   = null; }}
            if (radialLosStartLn) {{ map.removeLayer(radialLosStartLn); radialLosStartLn = null; }}
            if (radialLosEndLn)   {{ map.removeLayer(radialLosEndLn);   radialLosEndLn   = null; }}
            if (radialLosStartMk) {{ map.removeLayer(radialLosStartMk); radialLosStartMk = null; }}
            if (radialLosEndMk)   {{ map.removeLayer(radialLosEndMk);   radialLosEndMk   = null; }}
            if (radialLosPolygon) {{ map.removeLayer(radialLosPolygon); radialLosPolygon = null; }}
            radialLosSpokes.forEach(function(s) {{ map.removeLayer(s); }});  // ניקוי כל קווי החישור הצבעוניים
            radialLosSpokes = [];
            radialLosObs = null;
        }}

        function toggleRadialLos() {{
            // הפעלה/כיבוי מצב "רדיוס ראייה" — לא מחשב שום דבר, רק מכין את המפה ללחיצה הבאה.
            // חושף/מסתיר גם את פאנל הפרמטרים — לפי בקשת המשתמש, הפאנל לא מוצג עד שהכלי נבחר.
            radialLosActive = !radialLosActive;
            map.getContainer().style.cursor = radialLosActive ? 'crosshair' : '';
            if (_radialLosBtnEl) {{
                _radialLosBtnEl.style.background = radialLosActive ? '#2ecc40' : 'white';
                _radialLosBtnEl.style.color      = radialLosActive ? 'white'  : '#333';
            }}
            if (_radialPanelBodyEl) {{
                _radialPanelBodyEl.style.display = radialLosActive ? 'flex' : 'none';  // חשיפה/הסתרה של שדות הפרמטרים
            }}
            if (!radialLosActive) {{
                clearRadialLosResult();  // כיבוי הכלי מנקה גם משקיף/תצוגה מקדימה/תוצאה — לא נשאר "יתום" על המפה
            }}
        }}

        var RadialLosControl = L.Control.extend({{
            options: {{ position: 'topright' }},
            onAdd: function() {{
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cssText = 'display:flex;flex-direction:column;gap:3px;background:white;' +
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:4px 6px;font-family:Arial;max-width:230px;';

                var row1 = L.DomUtil.create('div', '', container);  // שורה 1: כפתור ההפעלה בלבד — תמיד מוצג, גם מכווץ
                row1.style.cssText = 'display:flex;align-items:center;gap:5px;';
                var btn = L.DomUtil.create('a', '', row1);
                btn.href = '#'; btn.title = 'רדיוס ראייה';  // tooltip בעת hover — התווית הטקסטואלית היחידה במצב מכווץ, כמו כפתור 👁 של LOS הרגיל
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;width:26px;height:26px;' +
                    'font-size:14px;background:white;color:#333;text-decoration:none;border-radius:4px;cursor:pointer;flex-shrink:0;' +
                    'opacity:0.4;pointer-events:none;';  // מנוטרל עד שהמפה מוכנה (map.whenReady, בהמשך)
                btn.innerHTML = '&#128225;';  // 📡 — שונה מ-👁 של כלי קו-הראייה הרגיל
                _radialLosBtnEl = btn;
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;  // הגנה נוספת מעבר ל-pointer-events — המפה/שרתים לא מוכנים
                    toggleRadialLos();
                }});

                // גוף הפאנל (שדות+כפתורים) — מוסתר כברירת מחדל, נחשף רק אחרי בחירת הכלי (toggleRadialLos)
                // כדי שהמפה לא תהיה עמוסה בשדות לפני שהמשתמש בכלל בחר להשתמש בכלי הזה.
                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;';
                _radialPanelBodyEl = panelBody;

                function _mkField(labelText, defaultVal, step, minV, maxV, tip) {{
                    // בונה שדה קלט מספרי בודד עם תווית — כל שדה מעדכן את התצוגה המקדימה בעת עריכה (דו-כיווני מול הגרירה)
                    var wrap = L.DomUtil.create('label', '', panelBody);
                    wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                    wrap.title = tip;
                    var span = L.DomUtil.create('span', '', wrap);
                    span.textContent = labelText;
                    var inp = L.DomUtil.create('input', '', wrap);
                    inp.type = 'number'; inp.value = defaultVal; inp.step = step;
                    inp.min = minV; inp.max = maxV;
                    inp.style.cssText = 'width:55px;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;';
                    L.DomEvent.on(inp, 'input', function() {{ _updateRadialLosPreview(); }});
                    return inp;
                }}
                _radialRangeInput    = _mkField('טווח (ק"מ, עד 300)',  5,   0.5, 0.5, 300, 'מרחק מרבי לבדיקת ראייה');
                _radialMinRangeInput = _mkField('טווח מינימלי (ק"מ)',  5,   0.5, 0,   300, 'אזור עיוור קרוב למשקיף שלא נבדק כלל');
                _radialStepInput     = _mkField('צעד זווית (°)',       10,  1,   3,   45,  'רווח בין כיוונים — קובע כמה קודקודים בפוליגון');
                _radialStartInput    = _mkField('אזימוט התחלה (°)',    315, 1,   0,   360, 'ניתן לגרור גם על המפה');
                _radialEndInput      = _mkField('אזימוט סיום (°)',     45,  1,   0,   360, 'ניתן לגרור גם על המפה');
                _radialObsInput      = _mkField('גובה צופה (מ\\')',     11,  1,   0,   500, 'גובה המשקיף מעל הקרקע');
                _radialTgtInput      = _mkField('גובה יעד (מ\\')',       0,  1,   0,   500, 'גובה עצם/מכשול הנבדק לאורך כל קרן');
                _radialMarginInput   = _mkField('מרווח רכס (°)',        0,  0.5, 0,   10,  'שולי ביטחון מעל הרכס הגבוה ביותר שנצפה');
                _radialVCenterInput  = _mkField('מרכז אלומה אנכי (°)',  0,  0.5, -45, 45,  'זווית עילוי/הטיה מרכזית (0=אופקי) — שדה-ראייה של "מכ"ם" רעיוני, לא כלי אמיתי');
                _radialVWidthInput   = _mkField('רוחב אלומה אנכי (°)',  4,  0.5, 1,   90,  'רוחב שדה-הראייה האנכי הכולל סביב המרכז — מוגבל בכוונה, לא כל טווח הגובה נבדק');

                _buildStationUI(panelBody, 'radial_los', {{
                    range_km: _radialRangeInput, min_range_km: _radialMinRangeInput, angle_step_deg: _radialStepInput,
                    start_bearing_deg: _radialStartInput, end_bearing_deg: _radialEndInput,
                    obs_h: _radialObsInput, tgt_h: _radialTgtInput, ridge_margin_deg: _radialMarginInput,
                    vertical_center_deg: _radialVCenterInput, vertical_width_deg: _radialVWidthInput,
                }}, function() {{ return radialLosObs; }}, _placeRadialLosObserver, _updateRadialLosPreview);

                var runBtn = L.DomUtil.create('button', '', panelBody);
                runBtn.textContent = 'הפעל חישוב';
                runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
                L.DomEvent.on(runBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runRadialLos(); }});

                var cancelBtn = L.DomUtil.create('button', '', panelBody);
                cancelBtn.textContent = 'בטל';
                cancelBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#ff8888;cursor:pointer;display:none;';
                L.DomEvent.on(cancelBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _cancelRadialLos(); }});
                _radialCancelBtnEl = cancelBtn;

                var info = L.DomUtil.create('div', '', panelBody);
                info.style.cssText = 'font-size:10px;color:#555;text-align:center;direction:rtl;min-height:12px;';
                radialLosInfoEl = info;

                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }}
        }});
        new RadialLosControl().addTo(map);  // הוספת ה-Control למפה

        // ── כלי תצפית מכ"ם דופלר (רעיוני/חינוכי) — כלי שלישי, נפרד ──
        // תצוגה מקדימה+גרירת ידיות זהה לרדיוס-הראייה (משתמש באותם _destPointJs/_bearingDeg/_haversineM),
        // בצבע ייחודי (ציאן) כדי לא להתבלבל עם הצהוב של רדיוס-הראייה. ההבדל האמיתי הוא בציור התוצאה
        // (_drawRadarDopplerResult) — 3 צבעים במקום 2, כי יש עכשיו סיבת-אי-גילוי שלישית (דופלר).
        function _radarMarkerIcon() {{
            // אייקון סמן התצפית — עיגול מלא בצבע ציאן, לא חופף לצהוב של רדיוס-הראייה או למג'נטה של ה-CTR
            return L.divIcon({{
                html: '<div style="width:16px;height:16px;border-radius:50%;background:#22d3ee;border:2px solid #333;"></div>',
                className: '', iconSize: [16,16], iconAnchor: [8,8]
            }});
        }}

        function _radarHandleIcon() {{
            // אייקון ידית גרירה לזווית/טווח — אותו צבע כמו סמן התצפית, קטן יותר
            return L.divIcon({{
                html: '<div style="width:12px;height:12px;border-radius:50%;background:#22d3ee;border:2px solid #333;cursor:move;"></div>',
                className: '', iconSize: [12,12], iconAnchor: [6,6]
            }});
        }}

        function _placeRadarObserver(latlng) {{
            // ממקם/מזיז את סמן המשקיף — בשימוש הן ע"י לחיצה על המפה והן ע"י טעינת "עמדה שמורה"
            clearRadarDopplerResult();  // ניקוי תוצאה/תצוגה מקדימה קודמת — משקיף חדש בכל הפעלה
            radarObs = latlng;
            radarObsMk = L.marker(latlng, {{icon: _radarMarkerIcon(), draggable: true}}).addTo(map);
            radarObsMk.bindTooltip('תצפית מכ"ם דופלר', {{permanent:false, direction:'top'}});
            radarObsMk.on('dragend', function() {{
                radarObs = radarObsMk.getLatLng();
                _updateRadarDopplerPreview();  // רק מעדכן תצוגה מקדימה — לא מריץ חישוב אוטומטית
            }});
            _updateRadarDopplerPreview();  // מציג תצוגה מקדימה מיידית (מהשדות הנוכחיים) — לא מפעיל חישוב
        }}

        function _updateRadarDopplerPreview() {{
            // מצייר/מעדכן את שני קווי התצוגה המקדימה (אזימוט התחלה/סוף) + הידיות בקצותיהם —
            // אותה טכניקה בדיוק כמו _updateRadialLosPreview, חישוב מקומי בלבד, בלי לקרוא לשרת
            if (!radarObs) return;  // אין עדיין נקודת תצפית — אין מה לצייר
            var rangeKm  = _radarRangeInput ? parseFloat(_radarRangeInput.value) : NaN;
            var startDeg = _radarStartInput ? parseFloat(_radarStartInput.value) : NaN;
            var endDeg   = _radarEndInput   ? parseFloat(_radarEndInput.value)   : NaN;
            if (isNaN(rangeKm))  rangeKm  = 50;  // ברירת מחדל — תואמת לברירת המחדל בשרת (שונה מרדיוס-הראייה: 50, לא 5)
            if (isNaN(startDeg)) startDeg = 315; // מגזר 90° סביב צפון כברירת מחדל — לא מעגל מלא חופף
            if (isNaN(endDeg))   endDeg   = 45;
            var startPt = _destPointJs(radarObs, startDeg, rangeKm * 1000);
            var endPt   = _destPointJs(radarObs, endDeg,   rangeKm * 1000);
            if (radarStartLn) map.removeLayer(radarStartLn);  // מנקה קו קודם לפני ציור מחדש
            if (radarEndLn)   map.removeLayer(radarEndLn);
            radarStartLn = L.polyline([radarObs, startPt], {{color:'#22d3ee', weight:1.5, dashArray:'4,4'}}).addTo(map);
            radarEndLn   = L.polyline([radarObs, endPt],   {{color:'#22d3ee', weight:1.5, dashArray:'4,4'}}).addTo(map);
            if (!radarStartMk) {{  // יוצר את הידית פעם אחת בלבד — בפעמים הבאות רק מזיז אותה
                radarStartMk = L.marker(startPt, {{icon: _radarHandleIcon(), draggable:true}}).addTo(map);
                radarStartMk.on('drag', function(ev) {{ _onRadarHandleDrag(ev, 'start'); }});
            }} else {{
                radarStartMk.setLatLng(startPt);
            }}
            if (!radarEndMk) {{
                radarEndMk = L.marker(endPt, {{icon: _radarHandleIcon(), draggable:true}}).addTo(map);
                radarEndMk.on('drag', function(ev) {{ _onRadarHandleDrag(ev, 'end'); }});
            }} else {{
                radarEndMk.setLatLng(endPt);
            }}
        }}

        function _onRadarHandleDrag(ev, which) {{
            // גרירת ידית — קובעת גם אזימוט (רק לידית הזו) וגם טווח משותף (שתי הידיות זזות לאותו רדיוס חדש)
            if (!radarObs) return;
            var p = ev.target.getLatLng();
            var bearing = _bearingDeg(radarObs, p);
            var distM   = _haversineM(radarObs, p);
            if (which === 'start' && _radarStartInput) _radarStartInput.value = bearing.toFixed(1);
            if (which === 'end'   && _radarEndInput)   _radarEndInput.value   = bearing.toFixed(1);
            if (_radarRangeInput) _radarRangeInput.value = (distM / 1000).toFixed(2);
            _updateRadarDopplerPreview();
        }}

        function _runRadarDoppler() {{
            // מפעיל את החישוב האמיתי בשרת — נקרא רק בלחיצה מפורשת על "הפעל חישוב"
            if (!radarObs || radarLoading) return;
            function num(el, def) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? def : v; }}
            var rangeKm    = num(_radarRangeInput, 50);
            var minRangeKm = num(_radarMinRangeInput, 1);
            var stepDeg    = num(_radarStepInput, 10);
            var startDeg   = num(_radarStartInput, 315);
            var endDeg     = num(_radarEndInput, 45);
            var hAnt       = num(_radarHAntInput, 15);
            var marginDeg  = num(_radarMarginInput, 0);
            var vCenter    = num(_radarVCenterInput, 0);
            var vWidth     = num(_radarVWidthInput, 10);
            var powerKw    = num(_radarPowerInput, 100);
            var gainDbi    = num(_radarGainInput, 30);
            var freqMhz    = _radarFreqSelect ? parseFloat(_radarFreqSelect.value) : 3000;
            var sensDbm    = num(_radarSensInput, -100);
            var rcsM2      = _radarRcsSelect ? parseFloat(_radarRcsSelect.value) : 2;
            var prfHz      = num(_radarPrfInput, 1000);
            var mdvKt      = num(_radarMdvInput, 20);
            var speedKt    = num(_radarSpeedInput, 250);
            var headingDeg = num(_radarHeadingInput, 0);
            var lobingOn   = _radarLobingCheck ? _radarLobingCheck.checked : false;
            var reflKey    = _radarReflSelect ? _radarReflSelect.value : 'land';
            var antennaType  = _radarAntennaSelect ? _radarAntennaSelect.value : 'generic';
            var boresightDeg = num(_radarBoresightInput, 0);
            var maxScanDeg   = num(_radarMaxScanInput, 60);
            radarLoading = true;
            document.title = '__radar_doppler_loading__';  // איתות ל-Python — שורת לוג
            if (radarInfoEl) radarInfoEl.textContent = 'מתחיל חישוב…';
            if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'block';
            var url = 'http://localhost:5002/radar_doppler/start?lat=' + radarObs.lat + '&lon=' + radarObs.lng +
                      '&range_km=' + rangeKm + '&min_range_km=' + minRangeKm + '&angle_step_deg=' + stepDeg +
                      '&start_bearing_deg=' + startDeg + '&end_bearing_deg=' + endDeg +
                      '&h_antenna=' + hAnt + '&ridge_margin_deg=' + marginDeg +
                      '&vertical_center_deg=' + vCenter + '&vertical_width_deg=' + vWidth +
                      '&power_kw=' + powerKw + '&gain_dbi=' + gainDbi + '&freq_mhz=' + freqMhz +
                      '&sensitivity_dbm=' + sensDbm + '&rcs_m2=' + rcsM2 +
                      '&prf_hz=' + prfHz + '&mdv_kt=' + mdvKt + '&target_speed_kt=' + speedKt +
                      '&target_heading_deg=' + headingDeg +
                      '&lobing_enabled=' + (lobingOn ? 'true' : 'false') + '&reflectivity=' + reflKey +
                      '&antenna_type=' + antennaType + '&boresight_deg=' + boresightDeg + '&max_scan_deg=' + maxScanDeg;
            fetch(url)
            .then(function(r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
            .then(function(data) {{
                if (data.error) throw new Error(data.error);
                radarJobId = data.job_id;
                radarPollTimer = setInterval(_pollRadarDopplerStatus, 1000);  // בדיקת התקדמות כל שנייה
            }})
            .catch(function(err) {{
                radarLoading = false;
                document.title = '__radar_doppler_error__';
                if (radarInfoEl) radarInfoEl.textContent = '';
                if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'none';
                alert('שגיאה בהפעלת חישוב תצפית מכ"ם דופלר: ' + err.message);
            }});
        }}

        function _pollRadarDopplerStatus() {{
            // נקרא כל שנייה בזמן שה-job רץ — בודק התקדמות, מצייר תוצאה סופית כשמסתיים
            if (!radarJobId) return;
            fetch('http://localhost:5002/radar_doppler/status?job_id=' + radarJobId)
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                if (data.status === 'running') {{
                    if (radarInfoEl) {{
                        var total = data.batches_total;
                        radarInfoEl.textContent = total
                            ? 'מחשב… ' + data.batches_done + '/' + total + ' (עד כמה דקות בטווח ארוך)'
                            : 'מתחיל…';
                    }}
                    return;  // עדיין רץ — ממתין ל-tick הבא
                }}
                clearInterval(radarPollTimer);  // ה-job הסתיים (הצליח/נכשל/בוטל) — מפסיק את ה-polling
                radarPollTimer = null;
                radarLoading = false;
                if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'none';
                if (data.status === 'done') {{
                    document.title = '__radar_doppler_loaded__';
                    _drawRadarDopplerResult(data.result);
                    if (radarInfoEl) radarInfoEl.textContent =
                        data.result.range_km + ' ק"מ, ' + data.result.n_bearings + ' כיוונים, ' +
                        data.result.clear_count + ' מזוהים לגמרי, ' + data.result.doppler_blocked_rays + ' חסומי-דופלר';
                }} else if (data.status === 'error') {{
                    document.title = '__radar_doppler_error__';
                    if (radarInfoEl) radarInfoEl.textContent = '';
                    alert('שגיאה בחישוב תצפית מכ"ם דופלר: ' + (data.error || 'לא ידועה'));
                }} else if (data.status === 'cancelled') {{
                    document.title = '__radar_doppler_cancelled__';
                    if (radarInfoEl) radarInfoEl.textContent = '';
                }}
                radarJobId = null;
            }})
            .catch(function() {{
                // כשל רשת בבדיקת סטטוס בודדת — לא עוצר את ה-polling, ה-tick הבא ינסה שוב
            }});
        }}

        function _drawRadarDopplerResult(result) {{
            // מצייר את הפוליגון הסופי + קטע/שני קטעים צבעוניים לכל כיוון — 3 מצבים אפשריים:
            // ירוק בלבד עד סוף הטווח = מזוהה לגמרי. ירוק+אדום = מזוהה חלקית (נחסם שטח/טווח מכ"ם בהמשך).
            // כתום (במקום ירוק) = הכיוון הזה כולו "עיוור" לדופלר (מהירות המטרה המשוערת לא מתגלה בזווית
            // הזו כלל) — גם אם השטח/טווח המכ"ם היו מאפשרים גילוי, ואז ממשיך אדום עד סוף הטווח אם נחסם.
            if (radarPolygon) {{ map.removeLayer(radarPolygon); radarPolygon = null; }}
            radarSpokes.forEach(function(s) {{ map.removeLayer(s); }});  // ניקוי חישורים מחישוב קודם
            radarSpokes = [];
            var pts = result.rays.map(function(r) {{ return [r.radar_lat, r.radar_lon]; }});
            if (result.span_deg < 360) {{
                pts.unshift([result.observer_lat, result.observer_lon]);  // פרוסת-פיצה — כולל נקודת המשקיף כקודקוד
            }}
            if (pts.length >= 3) {{
                radarPolygon = L.polygon(pts, {{
                    color: '#22d3ee', weight: 1.5, fillColor: '#22d3ee', fillOpacity: 0.10
                }}).addTo(map);
            }}
            var obsLatLng = L.latLng(result.observer_lat, result.observer_lon);
            var minRangeM = (result.min_range_km || 0) * 1000;
            var rangeM    = result.range_km * 1000;
            result.rays.forEach(function(r) {{
                var nearPt   = _destPointJs(obsLatLng, r.bearing_deg, minRangeM);  // תחילת הדגימה בפועל — גבול אזור העיוור
                var radarPt  = L.latLng(r.radar_lat, r.radar_lon);  // הנקודה הרחוקה ביותר בטווח המכ"ם (בלי קשר לדופלר)
                var nearColor = r.doppler_ok ? '#00cc44' : '#ff9500';  // ירוק אם הכיוון "נראה" לדופלר, כתום אם כל הכיוון עיוור לו
                radarSpokes.push(L.polyline([nearPt, radarPt], {{color: nearColor, weight: 3}}).addTo(map));
                if (r.blocked) {{
                    // אדום — ממשיך מהנקודה הרחוקה ביותר בטווח המכ"ם עד סוף הטווח המבוקש (שטח/טווח מכ"ם לא הספיקו)
                    var farPt = _destPointJs(obsLatLng, r.bearing_deg, rangeM);
                    radarSpokes.push(L.polyline([radarPt, farPt], {{color: '#ff3300', weight: 3}}).addTo(map));
                }}
            }});
            if (result.rays.length > 0) {{  // הזזת הידיות לקצוות הקשת האמיתיים
                var firstRay = result.rays[0], lastRay = result.rays[result.rays.length - 1];
                if (radarStartMk) radarStartMk.setLatLng([firstRay.radar_lat, firstRay.radar_lon]);
                if (radarEndMk)   radarEndMk.setLatLng([lastRay.radar_lat, lastRay.radar_lon]);
            }}
        }}

        function _cancelRadarDoppler() {{
            // כפתור "בטל" — עוצר מיד בצד הלקוח, ומודיע גם לשרת שיפסיק
            if (radarPollTimer) {{ clearInterval(radarPollTimer); radarPollTimer = null; }}
            if (radarJobId) {{
                fetch('http://localhost:5002/radar_doppler/cancel?job_id=' + radarJobId, {{method:'POST'}});
            }}
            radarJobId = null;
            radarLoading = false;
            if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'none';
            if (radarInfoEl) radarInfoEl.textContent = '';
        }}

        function clearRadarDopplerResult() {{
            // ניקוי מלא — נקרא מ-resetMapState וגם בהצבת משקיף חדש
            _cancelRadarDoppler();  // עוצר polling + מבטל job בשרת אם עדיין רץ
            if (radarObsMk)   {{ map.removeLayer(radarObsMk);   radarObsMk   = null; }}
            if (radarStartLn) {{ map.removeLayer(radarStartLn); radarStartLn = null; }}
            if (radarEndLn)   {{ map.removeLayer(radarEndLn);   radarEndLn   = null; }}
            if (radarStartMk) {{ map.removeLayer(radarStartMk); radarStartMk = null; }}
            if (radarEndMk)   {{ map.removeLayer(radarEndMk);   radarEndMk   = null; }}
            if (radarPolygon) {{ map.removeLayer(radarPolygon); radarPolygon = null; }}
            radarSpokes.forEach(function(s) {{ map.removeLayer(s); }});
            radarSpokes = [];
            radarObs = null;
        }}

        function toggleRadarDoppler() {{
            // הפעלה/כיבוי מצב "תצפית מכ"ם דופלר" — לא מחשב שום דבר, רק מכין את המפה ללחיצה הבאה
            radarActive = !radarActive;
            map.getContainer().style.cursor = radarActive ? 'crosshair' : '';
            if (_radarBtnEl) {{
                _radarBtnEl.style.background = radarActive ? '#2ecc40' : 'white';
                _radarBtnEl.style.color      = radarActive ? 'white'  : '#333';
            }}
            if (_radarPanelBodyEl) {{
                _radarPanelBodyEl.style.display = radarActive ? 'flex' : 'none';
            }}
            if (!radarActive) {{
                clearRadarDopplerResult();  // כיבוי הכלי מנקה גם משקיף/תצוגה מקדימה/תוצאה — לא נשאר "יתום" על המפה
            }}
        }}

        var RadarDopplerControl = L.Control.extend({{
            options: {{ position: 'topright' }},
            onAdd: function() {{
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cssText = 'display:flex;flex-direction:column;gap:3px;background:white;' +
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:4px 6px;font-family:Arial;max-width:250px;';

                var row1 = L.DomUtil.create('div', '', container);  // שורה 1: כפתור ההפעלה בלבד — תמיד מוצג
                row1.style.cssText = 'display:flex;align-items:center;gap:5px;';
                var btn = L.DomUtil.create('a', '', row1);
                btn.href = '#'; btn.title = 'תצפית מכ"ם דופלר';
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;width:26px;height:26px;' +
                    'font-size:14px;background:white;color:#333;text-decoration:none;border-radius:4px;cursor:pointer;flex-shrink:0;' +
                    'opacity:0.4;pointer-events:none;';  // מנוטרל עד שהמפה מוכנה
                btn.innerHTML = '&#127919;';  // 🎯 — שונה מ-📡 של רדיוס-הראייה ומ-👁 של קו-הראייה
                _radarBtnEl = btn;
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;  // הגנה נוספת מעבר ל-pointer-events — המפה/שרתים לא מוכנים
                    toggleRadarDoppler();
                }});

                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;max-height:70vh;overflow-y:auto;';
                _radarPanelBodyEl = panelBody;

                function _mkHeader(text) {{
                    // כותרת קבוצה קטנה — מפרידה חזותית בין 4 קבוצות הפרמטרים (גיאומטריה/מכ"ם/דופלר/תפוצה)
                    var h = L.DomUtil.create('div', '', panelBody);
                    h.textContent = text;
                    h.style.cssText = 'font-size:9px;font-weight:bold;color:#888;margin-top:3px;border-top:1px solid #eee;padding-top:2px;';
                    return h;
                }}
                function _mkField(labelText, defaultVal, step, minV, maxV, tip, parentEl) {{
                    // parentEl אופציונלי — ברירת המחדל panelBody עצמו; משמש לשים שדה בתוך מיכל
                    // מקונן (כמו _radarAntennaWrapEl) במקום ישירות בפאנל הראשי
                    var wrap = L.DomUtil.create('label', '', parentEl || panelBody);
                    wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                    wrap.title = tip;
                    var span = L.DomUtil.create('span', '', wrap);
                    span.textContent = labelText;
                    var inp = L.DomUtil.create('input', '', wrap);
                    inp.type = 'number'; inp.value = defaultVal; inp.step = step;
                    inp.min = minV; inp.max = maxV;
                    inp.style.cssText = 'width:55px;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;';
                    L.DomEvent.on(inp, 'input', function() {{ _updateRadarDopplerPreview(); }});
                    return inp;
                }}
                function _mkSelect(labelText, options, defaultIdx, tip) {{
                    // שדה בחירה מרשימה — למשל סוג מטרה (RCS) או פס תדרים, במקום קלט מספרי גולמי
                    var wrap = L.DomUtil.create('label', '', panelBody);
                    wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                    wrap.title = tip;
                    var span = L.DomUtil.create('span', '', wrap);
                    span.textContent = labelText;
                    var sel = L.DomUtil.create('select', '', wrap);
                    sel.style.cssText = 'width:95px;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;';
                    options.forEach(function(opt, i) {{
                        var o = L.DomUtil.create('option', '', sel);
                        o.value = opt[1]; o.textContent = opt[0];
                        if (i === defaultIdx) o.selected = true;
                    }});
                    return sel;
                }}

                _mkHeader('גיאומטריה');
                _radarRangeInput    = _mkField('טווח (ק"מ, עד 300)',  50, 1,   0.5, 300, 'מרחק מרבי לבדיקת גילוי');
                _radarMinRangeInput = _mkField('טווח מינימלי (ק"מ)',  1,  0.5, 0,   300, 'אזור עיוור קרוב למשקיף שלא נבדק כלל');
                _radarStepInput     = _mkField('צעד זווית (°)',       10, 1,   3,   45,  'רווח בין כיוונים — קובע כמה קודקודים בפוליגון');
                _radarStartInput    = _mkField('אזימוט התחלה (°)',    315, 1,  0,   360, 'ניתן לגרור גם על המפה');
                _radarEndInput      = _mkField('אזימוט סיום (°)',     45,  1,  0,   360, 'ניתן לגרור גם על המפה');
                _radarHAntInput     = _mkField('גובה אנטנה (מ\\')',    15, 1,   0,   500, 'גובה האנטנה מעל הקרקע');
                _radarMarginInput   = _mkField('מרווח רכס (°)',        0,  0.5, 0,   10,  'שולי ביטחון מעל הרכס הגבוה ביותר שנצפה');
                _radarVCenterInput  = _mkField('מרכז אלומה אנכי (°)',  0,  0.5, -45, 45,  'זווית עילוי/הטיה מרכזית (0=אופקי)');
                _radarVWidthInput   = _mkField('רוחב אלומה אנכי (°)', 10,  0.5, 1,   90,  'רוחב שדה-הראייה האנכי הכולל סביב המרכז');

                _mkHeader('משוואת מכ"ם — טווח גילוי');
                _radarPowerInput = _mkField('הספק שידור (קילוואט)', 100, 1, 0.1, 5000, 'הספק שידור שיא — יותר הספק = טווח גילוי גדול יותר');
                _radarGainInput  = _mkField('רווח אנטנה (dBi)',      30,  1, 0,   50,   'רווח האנטנה — יותר רווח = טווח גילוי גדול יותר');
                _radarFreqSelect = _mkSelect('תדר עבודה', [
                    ['L-band (1.3 GHz)', '1300'], ['S-band (3 GHz)', '3000'], ['X-band (10 GHz)', '10000']
                ], 1, 'תדר גבוה יותר = אורך גל קצר יותר, בד"כ טווח קטן יותר');
                _radarSensInput  = _mkField('רגישות מקלט (dBm)', -100, 1, -140, -60, 'רגישות טובה יותר (מספר שלילי יותר) = טווח גילוי גדול יותר');
                _radarRcsSelect  = _mkSelect('סוג מטרה (RCS)', [
                    ['רחפן קטן (0.01 מ"ר)', '0.01'], ['מל"ט בינוני (0.1 מ"ר)', '0.1'],
                    ['מטוס קל (2 מ"ר)', '2'], ['מטוס תובלה (50 מ"ר)', '50']
                ], 2, 'שטח חתך רדארי משוער — מטרה גדולה יותר מתגלה מרחוק יותר');

                _mkHeader('סוג אנטנה');
                _radarAntennaSelect = _mkSelect('סוג אנטנה', [
                    ['גנרי (רווח אחיד בכל כיוון)', 'generic'], ['מערך-מופעים (Phased Array)', 'phased_array']
                ], 0, 'מערך-מופעים: הרווח יורד ככל שמסטים מכיוון-הפנים, ומעבר לזווית סריקה מקסימלית אין כיסוי כלל');
                // מיכל שני השדות הנוספים — מוסתר כברירת מחדל, נחשף רק כש"מערך-מופעים" נבחר
                _radarAntennaWrapEl = L.DomUtil.create('div', '', panelBody);
                _radarAntennaWrapEl.style.cssText = 'display:none;flex-direction:column;gap:3px;';
                _radarBoresightInput = _mkField('כיוון-פנים (°)', 0, 1, 0, 360,
                    'הכיוון שהמערך "מסתכל" ישירות אליו (0=צפון)', _radarAntennaWrapEl);
                _radarMaxScanInput = _mkField('זווית סריקה מקסימלית (°)', 60, 1, 5, 180,
                    'עד כמה אפשר לסטות מכיוון-הפנים; טיפוסי כ-60°', _radarAntennaWrapEl);
                L.DomEvent.on(_radarAntennaSelect, 'change', function() {{
                    _radarAntennaWrapEl.style.display = _radarAntennaSelect.value === 'phased_array' ? 'flex' : 'none';
                }});

                _mkHeader('דופלר — האם התנועה מתגלה');
                _radarPrfInput     = _mkField('תדר חזרת פולסים (Hz)', 1000, 10, 50, 20000, 'PRF — קובע גם מהירויות עיוורות וגם טווח לא-חד-משמעי');
                _radarMdvInput     = _mkField('מהירות מינימלית לגילוי (קשר)', 20, 1, 0, 200, 'MDV — מטרה איטית מזה מסוננת כרקע נייח');
                _radarSpeedInput   = _mkField('מהירות המטרה (קשר)', 250, 5, 0, 1500, 'מהירות התנועה המשוערת של המטרה הנבדקת');
                _radarHeadingInput = _mkField('כיוון תנועת המטרה (°)', 0, 1, 0, 360, 'לאן המטרה טסה — קובע את המהירות הרדיאלית בכל אזימוט');

                _mkHeader('תפוצה — השתקפות קרקע/ים');
                var lobingWrap = L.DomUtil.create('label', '', panelBody);
                lobingWrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                lobingWrap.title = 'מציג "חורים" בכיסוי הנובעים מהתאבכות בין הקרן הישירה לבין ההשתקפות מהקרקע';
                var lobingSpan = L.DomUtil.create('span', '', lobingWrap);
                lobingSpan.textContent = 'הצג השפעת ריבוד (lobing)';
                _radarLobingCheck = L.DomUtil.create('input', '', lobingWrap);
                _radarLobingCheck.type = 'checkbox';
                _radarReflSelect = _mkSelect('סוג משטח מחזיר', [
                    ['יבשה מחוספסת', 'land'], ['ים חלק', 'sea']
                ], 0, 'רלוונטי רק כש"הצג השפעת ריבוד" מסומן — משטח חלק יותר מחזיר חזק יותר');

                _buildStationUI(panelBody, 'radar_doppler', {{
                    range_km: _radarRangeInput, min_range_km: _radarMinRangeInput, angle_step_deg: _radarStepInput,
                    start_bearing_deg: _radarStartInput, end_bearing_deg: _radarEndInput, h_antenna: _radarHAntInput,
                    ridge_margin_deg: _radarMarginInput, vertical_center_deg: _radarVCenterInput, vertical_width_deg: _radarVWidthInput,
                    power_kw: _radarPowerInput, gain_dbi: _radarGainInput, freq_mhz: _radarFreqSelect, sensitivity_dbm: _radarSensInput,
                    rcs_m2: _radarRcsSelect, antenna_type: _radarAntennaSelect, boresight_deg: _radarBoresightInput, max_scan_deg: _radarMaxScanInput,
                    prf_hz: _radarPrfInput, mdv_kt: _radarMdvInput, target_speed_kt: _radarSpeedInput, target_heading_deg: _radarHeadingInput,
                    lobing_enabled: _radarLobingCheck, reflectivity: _radarReflSelect,
                }}, function() {{ return radarObs; }}, _placeRadarObserver, _updateRadarDopplerPreview);

                var runBtn = L.DomUtil.create('button', '', panelBody);
                runBtn.textContent = 'הפעל חישוב';
                runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#22d3ee;cursor:pointer;margin-top:3px;';
                L.DomEvent.on(runBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runRadarDoppler(); }});

                var cancelBtn = L.DomUtil.create('button', '', panelBody);
                cancelBtn.textContent = 'בטל';
                cancelBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#ff8888;cursor:pointer;display:none;';
                L.DomEvent.on(cancelBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _cancelRadarDoppler(); }});
                _radarCancelBtnEl = cancelBtn;

                var info = L.DomUtil.create('div', '', panelBody);
                info.style.cssText = 'font-size:10px;color:#555;text-align:center;direction:rtl;min-height:12px;';
                radarInfoEl = info;

                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }}
        }});
        new RadarDopplerControl().addTo(map);  // הוספת ה-Control למפה

        // שלושת כפתורי הכלים (👁/📡/🎯) מוצגים מיד אך מנוטרלים (עמומים, לא לחיצים) עד ששני התנאים
        // מתקיימים: המפה מוכנה (_mapReady) **וגם** שרתי ה-Flask פעלים בפועל (serversRunning) —
        // בלי זה, לחיצה על הכלי לפני הפעלת השרתים "עובדת" (פותחת פאנל, מאפשרת להציב משקיף
        // ולערוך פרמטרים) עד שלוחצים "הפעל חישוב" ואז נכשל בשקט/עם alert מבלבל, כי כל שלושת
        // הכלים תלויים ב-weather_server.py (פורט 5002). מעדכן את מצב הכפתורים משני הכיוונים —
        // גם כשהמפה נטענת, גם כש-Python מדווח על הפעלה/כיבוי שרתים (ר' _setServersRunning).
        function _updateToolButtonsEnabled() {{
            var enabled = _mapReady && serversRunning;
            [_losBtnEl, _radialLosBtnEl, _radarBtnEl].forEach(function(btn) {{
                if (!btn) return;
                btn.style.opacity = enabled ? '1' : '0.4';
                btn.style.pointerEvents = enabled ? 'auto' : 'none';
            }});
        }}

        // נקרא מ-Python (main.py, start_servers/stop_servers) במקום קביעה ישירה של המשתנה —
        // כדי שעדכון הכפתורים יקרה בכל שינוי מצב שרתים, לא רק פעם אחת ב-map.whenReady
        function _setServersRunning(running) {{
            serversRunning = running;
            _updateToolButtonsEnabled();
        }}

        map.whenReady(function() {{
            _mapReady = true;
            _updateToolButtonsEnabled();
        }});

        // ── הודעת מידע — כלל טיסת VLOS ──
        // תוכן טקסטואלי סטטי בלבד, לא שכבה גיאומטרית — אין מקור geodata ל"אזור מותר" בפועל,
        // רק כלל רגולטורי כללי (פמ"ת פנים ארצי, פרק ב'-09, סעיפים 7.ד-7.ה). תמיד מוצג, לא תלוי בשכבה פעילה.
        var VlosInfoControl = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function() {{
                var d = L.DomUtil.create('div', '');
                d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;padding:6px 10px;'
                    + 'border-radius:7px;font-size:11px;font-family:Arial;border:1px solid #45475a;'
                    + 'direction:rtl;max-width:260px;cursor:pointer;';
                var header = L.DomUtil.create('div', '', d);
                header.style.cssText = 'font-weight:bold;';
                header.innerHTML = '&#8505; כלל טיסת VLOS';
                var body = L.DomUtil.create('div', '', d);
                body.style.cssText = 'display:none;color:#a6adc8;margin-top:5px;white-space:pre-line;';
                body.textContent =
                    'טיסת כטב"ם בקשר עין (VLOS) פטורה מדרישת סגירה אווירית והגשת תוכנית טיסה כאשר\\n' +
                    'מתקיימים כל התנאים הבאים:\\n' +
                    '• גובה שאינו עולה על 100 מטר מעל פני הקרקע\\n' +
                    '• מחוץ לאזורים אסורים/מוגבלים/מסוכנים (אלא אם התקבל אישור מאחראי האזור)\\n' +
                    '• במרחק הגדול מ-500 רגל מבסיס ענן\\n' +
                    '• בתנאי ראות אופקית העולים על 3 ק"מ\\n' +
                    '• מחוץ לתשתית תעופתית (נתיבים)\\n\\n' +
                    'שימו לב: הפטור מסגירה אווירית/תוכנית טיסה אינו מבטל את הצורך באישור נפרד\\n' +
                    'להפעלה באזור פיקוח שדה תעופה (CTR) או באזור מנחת (ATZ) — פירוט מלא: פמ"ת\\n' +
                    'פנים ארצי, פרק ב\\'-09.';
                L.DomEvent.on(d, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    body.style.display = body.style.display === 'none' ? 'block' : 'none';
                }});
                L.DomEvent.disableClickPropagation(d);
                return d;
            }}
        }});
        new VlosInfoControl().addTo(map);  // תמיד מוצג — לא תלוי בשכבה פעילה

    </script>
</body>
</html>
""")

    print(f"נוצרה מפה ושמה: {map_file}")


# קריאה לפונקציה ליצירת המפה
if __name__ == "__main__":
    create_map()
