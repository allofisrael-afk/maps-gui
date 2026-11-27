# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
import os
import json  # הזרקת נתונים סטטיים (אזורי תיאום, קטגוריות NOTAM) כליטרלי JS — ר' בהמשך
from dotenv import load_dotenv  # טעינת משתני סביבה (נשמר לתאימות עתידית)
from uas_coordination_zones import UAS_COORDINATION_ZONES  # נתוני "אזורי תיאום כטב"ם" — סטטיים, לא נשלפים בזמן ריצה
from notam_categories import NOTAM_CATEGORIES  # 7 קטגוריות סיווג NOTAM (id/label/color) — סטטי, ר' notam_categories.py
from airport_ctr_zones import AIRPORT_CTR_ZONES  # גבולות CTR קבועים של שדות תעופה, ממקור AIP רשמי — ר' airport_ctr_zones.py

load_dotenv()


def _build_web_mobile_css():
    """CSS רספונסיבי לגרסת ה-web בלבד — לא נוגע בכלל בדסקטופ (שם אין target='web').
    מצמצם גודל-גופן/ריפוד של בקרות ה-Leaflet במסכים צרים, כדי שלא יחפפו/ייחתכו במובייל.
    לא f-string (אין צורך בהכפלת סוגריים מסולסלים) — טקסט CSS פשוט."""
    return """
        @media (max-width: 600px) {
            .leaflet-control { font-size: 11px !important; }
            #status { font-size: 11px !important; padding: 5px 8px !important; }
        }
    """


def _build_web_controls_js(api_base):
    """
    בקרות UI נוספות לגרסת ה-web בלבד — ממירות widgets שבדסקטופ הם Qt (main.py, לא קיימים
    כאן בכלל) לבקרות Leaflet בתוך הדף עצמו: NOTAM toggles, מצב-תצוגה גבהים/טמפרטורה,
    חיפוש עיר, חיפוש טיסה, GPS. כולן קוראות לפונקציות JS *קיימות* (toggleNotamCategory/
    setElevMode/setTempMode/drawFlightRoute) ולא כופלות לוגיקה — ר' MAPS-GUI_SRS.md §3.24.
    כל בקרה מוגבלת ל-max-width יחסי ל-viewport (calc(100vw - 20px)) לתמיכה במובייל.
    """
    return f"""
        // ══════════ בקרות web-בלבד (לא קיימות בדסקטופ — שם אלה widgets של Qt ב-main.py) ══════════
        var WebNotamControl = L.Control.extend({{
            options: {{ position: 'topleft' }},
            onAdd: function() {{
                var c = L.DomUtil.create('div', 'leaflet-control');
                c.style.cssText = 'background:rgba(30,30,46,.92);border-radius:8px;padding:5px 7px;'
                    + 'font-family:Arial;max-width:min(230px, calc(100vw - 20px));direction:rtl;max-height:150px;overflow-y:auto;';
                var title = L.DomUtil.create('div', '', c);
                title.textContent = 'NOTAM רחפנים';
                title.style.cssText = 'color:#cdd6f4;font-size:10px;font-weight:bold;margin-bottom:3px;';
                NOTAM_CATEGORIES.forEach(function(cat) {{
                    var row = L.DomUtil.create('label', '', c);
                    row.style.cssText = 'display:flex;align-items:center;gap:4px;font-size:10px;color:#cdd6f4;padding:1px 0;';
                    var cb = L.DomUtil.create('input', '', row);
                    cb.type = 'checkbox';
                    L.DomEvent.on(cb, 'change', function() {{ toggleNotamCategory(cat.id); }});
                    var span = L.DomUtil.create('span', '', row);
                    span.textContent = cat.label;
                    span.style.color = cat.color;
                }});
                L.DomEvent.disableClickPropagation(c);
                return c;
            }}
        }});
        new WebNotamControl().addTo(map);

        // factory לשתי בקרות-מצב זהות במבנה (גבהים/טמפרטורה) — נמנע משכפול הקוד פעמיים
        function _webHeatmapControl(title, setModeFn) {{
            return L.Control.extend({{
                options: {{ position: 'topleft' }},
                onAdd: function() {{
                    var c = L.DomUtil.create('div', 'leaflet-control');
                    c.style.cssText = 'background:rgba(30,30,46,.92);border-radius:8px;padding:5px 7px;'
                        + 'font-family:Arial;direction:rtl;margin-top:6px;';
                    var t = L.DomUtil.create('div', '', c);
                    t.textContent = title;
                    t.style.cssText = 'color:#cdd6f4;font-size:10px;font-weight:bold;margin-bottom:3px;';
                    var row = L.DomUtil.create('div', '', c);
                    row.style.cssText = 'display:flex;gap:3px;';
                    ['heat', 'grid', 'dots'].forEach(function(mode) {{
                        var b = L.DomUtil.create('a', '', row);
                        b.href = '#'; b.textContent = mode;
                        b.style.cssText = 'font-size:9px;padding:2px 5px;background:#313244;color:#cdd6f4;'
                            + 'border-radius:4px;text-decoration:none;cursor:pointer;';
                        L.DomEvent.on(b, 'click', function(e) {{
                            L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                            setModeFn(mode);
                        }});
                    }});
                    L.DomEvent.disableClickPropagation(c);
                    return c;
                }}
            }});
        }}
        new (_webHeatmapControl('מצב גבהים', setElevMode))().addTo(map);
        new (_webHeatmapControl('מצב טמפרטורה', setTempMode))().addTo(map);

        var WebSearchControl = L.Control.extend({{
            options: {{ position: 'topleft' }},
            onAdd: function() {{
                var c = L.DomUtil.create('div', 'leaflet-control');
                c.style.cssText = 'background:rgba(30,30,46,.92);border-radius:8px;padding:5px 7px;'
                    + 'font-family:Arial;direction:rtl;margin-top:6px;width:min(200px, calc(100vw - 20px));';

                var cityRow = L.DomUtil.create('div', '', c);
                cityRow.style.cssText = 'display:flex;gap:3px;margin-bottom:4px;';
                var cityInput = L.DomUtil.create('input', '', cityRow);
                cityInput.type = 'text'; cityInput.placeholder = 'חיפוש עיר/אזור';
                cityInput.style.cssText = 'flex:1;font-size:10px;padding:3px;border-radius:4px;border:1px solid #45475a;min-width:0;';
                var cityBtn = L.DomUtil.create('a', '', cityRow);
                cityBtn.href = '#'; cityBtn.innerHTML = '&#128269;';
                cityBtn.style.cssText = 'flex-shrink:0;cursor:pointer;color:#cdd6f4;';
                function _doCitySearch() {{
                    var q = cityInput.value.trim();
                    if (!q) return;
                    fetch('{api_base}/geo_data?location=' + encodeURIComponent(q))
                        .then(function(r) {{ return r.json(); }})
                        .then(function(data) {{
                            if (data.error) {{ alert(data.error); return; }}
                            map.setView([data.latitude, data.longitude], 11);
                        }})
                        .catch(function() {{ alert('שגיאה בחיפוש מיקום'); }});
                }}
                L.DomEvent.on(cityBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e); _doCitySearch(); }});
                L.DomEvent.on(cityInput, 'keydown', function(e) {{ if (e.key === 'Enter') _doCitySearch(); }});

                var flightRow = L.DomUtil.create('div', '', c);
                flightRow.style.cssText = 'display:flex;gap:3px;';
                var flightInput = L.DomUtil.create('input', '', flightRow);
                flightInput.type = 'text'; flightInput.placeholder = 'מספר טיסה';
                flightInput.style.cssText = 'flex:1;font-size:10px;padding:3px;border-radius:4px;border:1px solid #45475a;min-width:0;direction:ltr;';
                var flightBtn = L.DomUtil.create('a', '', flightRow);
                flightBtn.href = '#'; flightBtn.innerHTML = '&#9992;';
                flightBtn.style.cssText = 'flex-shrink:0;cursor:pointer;color:#cdd6f4;';
                function _doFlightSearch() {{
                    var q = flightInput.value.trim().toUpperCase();
                    if (!q) return;
                    fetch('{api_base}/flight_route?flight=' + encodeURIComponent(q))
                        .then(function(r) {{ return r.json(); }})
                        .then(function(data) {{
                            if (data.error) {{ alert(data.error); return; }}
                            drawFlightRoute(data);
                        }})
                        .catch(function() {{ alert('שגיאה בחיפוש טיסה'); }});
                }}
                L.DomEvent.on(flightBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e); _doFlightSearch(); }});
                L.DomEvent.on(flightInput, 'keydown', function(e) {{ if (e.key === 'Enter') _doFlightSearch(); }});

                L.DomEvent.disableClickPropagation(c);
                L.DomEvent.disableScrollPropagation(c);
                return c;
            }}
        }});
        new WebSearchControl().addTo(map);

        var WebGpsControl = L.Control.extend({{
            options: {{ position: 'topleft' }},
            onAdd: function() {{
                var btn = L.DomUtil.create('a', 'leaflet-control leaflet-bar');
                btn.href = '#'; btn.innerHTML = '&#128205;'; btn.title = 'מיקום עצמי (GPS)';
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;width:30px;height:30px;'
                    + 'background:rgba(30,30,46,.92);color:#cdd6f4;text-decoration:none;border-radius:8px;'
                    + 'font-size:15px;margin-top:6px;cursor:pointer;';
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!navigator.geolocation) {{ alert('הדפדפן לא תומך באיתור מיקום'); return; }}
                    navigator.geolocation.getCurrentPosition(function(pos) {{
                        var p = L.latLng(pos.coords.latitude, pos.coords.longitude);
                        map.setView(p, 13);
                        var dot = L.circleMarker(p, {{radius:7,color:'#fff',fillColor:'#89b4fa',fillOpacity:1,weight:2}}).addTo(map);
                        allMarkers.push(dot);
                    }}, function(err) {{
                        alert('שגיאה באיתור מיקום: ' + err.message);
                    }}, {{enableHighAccuracy: true, timeout: 10000}});
                }});
                return btn;
            }}
        }});
        new WebGpsControl().addTo(map);
    """


def create_map(target='desktop', api_base='', output_path=None):
    """
    פונקציה ליצירת קובץ HTML של המפה עם Leaflet.js ו-OpenStreetMap.
    ערכת נושא: topo (OpenTopoMap) — חינמי לחלוטין, ללא מפתח API.
    תומך בעברית מובנית לישראל, heatmap, מסלולי טיסה וסמני מזג אוויר.

    target: 'desktop' (ברירת מחדל, התנהגות זהה-ביט למה שהיה תמיד) או 'web' — מוסיף
        בקרות UI נוספות (ר' _build_web_controls_js) ו-CSS רספונסיבי למובייל, ומחליף את
        כתובות ה-API הקשיחות (http://localhost:5002/5003) ב-api_base (ר' MAPS-GUI_SRS.md §3.24).
    api_base: בסיס-URL לקריאות API כש-target='web' (ריק = נתיבים יחסיים לאותו origin).
    output_path: נתיב קובץ-פלט מפורש (למשל web/public/index.html) — None משתמש בברירת
        המחדל הקיימת "map.html" בתיקיית העבודה הנוכחית, בדיוק כמו תמיד.
    """
    map_file = output_path or "map.html"  # שם קובץ הפלט
    # JSON של אזורי התיאום וקטגוריות ה-NOTAM — מוזרקים פעם אחת כליטרלי JS קבועים (לא fetch בזמן ריצה, נתונים סטטיים)
    coord_zones_json = json.dumps(UAS_COORDINATION_ZONES, ensure_ascii=False)
    notam_categories_json = json.dumps(NOTAM_CATEGORIES, ensure_ascii=False)
    airport_ctr_zones_json = json.dumps(AIRPORT_CTR_ZONES, ensure_ascii=False)  # גבולות CTR — ר' airport_ctr_zones.py

    html_content = f"""<!DOCTYPE html>
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

        /* ── פקד Undo/Redo — פינה שמאלית-עליונה, מעל פקד הזום ── */
        .undo-redo-ctrl {{
            display: flex;
            flex-direction: row;
            gap: 4px;
            padding: 5px;
            background: rgba(30,30,46,0.92);
            border: 1px solid #45475a;
            border-radius: 8px;
            margin-top: 8px;   /* רווח מפקד הזום שמעליו */
        }}
        .undo-redo-btn {{
            padding: 5px 10px;
            background: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 5px;
            cursor: pointer;
            font-family: 'Segoe UI', Arial;
            font-size: 14px;
            transition: background 0.15s, opacity 0.15s;
        }}
        .undo-redo-btn:hover {{ background: #45475a; }}

        /* עיצוב Popup — רקע כהה תואם נושא */
        .leaflet-popup-content-wrapper {{
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #45475a;
            border-radius: 8px;
        }}
        .leaflet-popup-tip {{ background-color: #1e1e2e; }}
        .leaflet-popup-content {{ margin: 10px 14px; }}
        /* T11 (F-040, WCAG 2.5.8): יעד לחיצה של לפחות 24×24 לכל כפתור בפאנלים (טאבים, ✏️ תותח, כפתורי עמדות ועוד) */
        .leaflet-control button {{ min-height: 24px; min-width: 24px; box-sizing: border-box; }}
        .leaflet-control a[role=button] {{ min-height: 24px; min-width: 24px; display: inline-flex; align-items: center; justify-content: center; box-sizing: border-box; }}  /* T11: גם קישורים-כפתורים (💾 📂 🗑 בעמדות שמורות) */
        {_build_web_mobile_css() if target == 'web' else ''}
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
        var _lastFlightRouteData = null;  // routeData המלא (כולל trail עם alt/spd/hd) של הטיסה האחרונה שנטענה — לשימוש בהערכת מסלול מול מכ"ם-דופלר
        var _routeEvalLayers = [];    // קטעי הפוליליין הצבעוניים של הערכת המסלול האחרונה (לא flightPolyline הרגיל)
        var _routeEvalRcsUsed = null; // ה-RCS שנגזר אוטומטית וששימש בהערכה האחרונה — מוצג ב-radarInfoEl בסיום, לשקיפות
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

        // ── Undo/Redo גנרי — מחסנית פעולות משותפת לכל הכלים, לא ספציפית לכלי אחד ──
        // כל "פעולה" (עריכת שדה, מיקום משקיף, הרצת חישוב, הצבת/איפוס שכבה) נרשמת כזוג
        // get/set + הערך הקודם. undo/redo זהים למעשה — כל אחד רק מחליף כיוון על אותה מחסנית.
        var _undoStack = [];  // [{{label, restore}}, ...] — restore() משחזר אחורה ומחזיר בתמורה פונקציית הפוך ל-redo
        var _redoStack = [];
        var _UNDO_MAX = 50;  // תקרה סבירה — מונע צריכת זיכרון בלתי מוגבלת בסשן ארוך
        var _undoBtnEl = null, _redoBtnEl = null;  // הפניות לכפתורי הסרגל, לעדכון enabled/disabled
        var _isRestoringUndo = false;  // true תוך כדי ביצוע undo/redo עצמו — מונע ממאזיני 'change'/'blur'
        // (שמותקנים כדי *לרשום* פעולות חדשות) לתפוס את השינוי התכנותי-שלנו-עצמנו כפעולה חדשה,
        // מה שהיה יוצר לולאה/מציף את המחסניות בכל undo יחיד

        function _pushUndo(label, restoreFn) {{
            if (_isRestoringUndo) return;  // הגנה נוספת — לא אמור לקרות, אבל עדיף לא לרשום undo בתוך undo
            _undoStack.push({{label: label, restore: restoreFn}});
            if (_undoStack.length > _UNDO_MAX) _undoStack.shift();  // מוחק את הישן ביותר אם עברנו את התקרה
            _redoStack = [];  // כל פעולה חדשה מבטלת redo קודם — התנהגות סטנדרטית בכל תוכנה
            _updateUndoRedoButtons();
        }}

        // הליבה הגנרית: setFn/getFn מתארים "איך לקרוא/לכתוב" את הערך (שדה DOM, מיקום משקיף,
        // דגל שכבה וכו') — לא תלוי בסוג הפעולה. מחזיר פונקציה שכשנקראת: קוראת את הערך הנוכחי
        // (לפני שהיא דורסת אותו — זה מה ש-redo/undo הבא יצטרך), כותבת את targetValue, ומחזירה
        // עצמה-מחדש (closure רקורסיבי) עבור הכיוון ההפוך — כך undo ו-redo משתמשים באותה פונקציה.
        function _makeValueRestore(setFn, getFn, targetValue, onApply) {{
            return function() {{
                var current = getFn();
                setFn(targetValue);
                if (onApply) onApply();
                return _makeValueRestore(setFn, getFn, current, onApply);
            }};
        }}

        // גרסה גנרית ל"הזזת" סמן קיים (למשל גרירת משקיף/יעד) — לא יוצרת/מוחקת דבר, רק מזיזה חזרה
        function _makeMarkerMoveRestore(setPosFn, getPosFn, updateFn, targetLatLng) {{
            return function() {{
                var current = getPosFn();
                setPosFn(targetLatLng);
                if (updateFn) updateFn();
                return _makeMarkerMoveRestore(setPosFn, getPosFn, updateFn, current);
            }};
        }}

        // גרסה גנרית ל"הצבה" מלאה (למשל לחיצה על המפה שממקמת/מחליפה משקיף) —
        // אם אין ערך קודם (null) קוראת ל-clearFn (מחזירה למצב "אין עדיין הצבה")
        function _makePlacementRestore(placeFn, clearFn, getPosFn, targetLatLngOrNull) {{
            return function() {{
                var current = getPosFn();
                if (targetLatLngOrNull) {{ placeFn(targetLatLngOrNull); }} else {{ clearFn(); }}
                return _makePlacementRestore(placeFn, clearFn, getPosFn, current);
            }};
        }}

        // ── עזרי Undo ייעודיים לכלי קו-הראייה (LOS) — מבנה שונה משאר הכלים: כל צמד לחיצות יוצר
        // סשן חדש במערך losSessions (לא מצב יחיד שמוחלף), ולכן דרוש היפוך "קיים/לא-קיים" ולא "ערך קודם"
        function _addLosSessionToMap(session) {{
            if (losSessions.indexOf(session) === -1) losSessions.push(session);
            if (session.obsMk) session.obsMk.addTo(map);
            if (session.tgtMk) session.tgtMk.addTo(map);
            session.lineLayers.forEach(function(l) {{ l.addTo(map); }});
        }}

        function _removeLosSessionFromMap(session) {{
            var idx = losSessions.indexOf(session);
            if (idx !== -1) losSessions.splice(idx, 1);
            if (session.obsMk) map.removeLayer(session.obsMk);
            if (session.tgtMk) map.removeLayer(session.tgtMk);
            session.lineLayers.forEach(function(l) {{ map.removeLayer(l); }});
        }}

        function _makeLosSessionRestore(session, isPresent) {{
            return function() {{
                if (isPresent) {{ _removeLosSessionFromMap(session); }} else {{ _addLosSessionToMap(session); }}
                return _makeLosSessionRestore(session, !isPresent);
            }};
        }}

        // "הצבעה" זמנית — נקודת התצפית שנקבעה בלחיצה הראשונה, לפני שנבחר יעד (עדיין אין סשן)
        function _makeLosPendingObsRestore(mk, latlng, isPresent) {{
            return function() {{
                if (isPresent) {{
                    map.removeLayer(mk); losCurObs = null; losCurObsMk = null;
                }} else {{
                    losCurObs = latlng; losCurObsMk = mk; mk.addTo(map);
                }}
                return _makeLosPendingObsRestore(mk, latlng, !isPresent);
            }};
        }}

        // גרסה גנרית ל"תיבת-סימון לוגית" (בוליאני שנקבע ע"י פונקציית toggle קיימת, לא ע"י setter ישיר) —
        // בשימוש עבור שכבות NOTAM/אזורי-תיאום/CTR, שתיבות הסימון שלהן הן ווידג'טים של Qt (לא DOM),
        // ולכן לא ניתן לחווט אותן ישירות עם _attachCheckboxUndo הרגיל — ה-toggle עצמו נקרא במקום.
        function _makeSimpleToggleRestore(toggleFn, getFn, targetBool) {{
            return function() {{
                var current = getFn();
                if (current !== targetBool) toggleFn();  // קורא ל-toggle המקורי רק אם המצב בפועל אכן שונה מהיעד
                return _makeSimpleToggleRestore(toggleFn, getFn, current);
            }};
        }}

        function _performUndo() {{
            if (!_undoStack.length || _isRestoringUndo) return;
            var entry = _undoStack.pop();
            _isRestoringUndo = true;
            var forward;
            try {{ forward = entry.restore(); }} finally {{ _isRestoringUndo = false; }}  // מבצע את השחזור בפועל, מקבל בתמורה פונקציית הפוך
            _redoStack.push({{label: entry.label, restore: forward}});
            _updateUndoRedoButtons();
            // מאותת ל-Python (main.py, ר' _on_title_changed) ליישר תיבות/כפתורי שכבות NOTAM/תיאום/CTR —
            // אלה ווידג'טים של Qt מחוץ לדף, ולכן לא מתעדכנים אוטומטית כשה-JS משנה מצב ישירות (בלי לחיצה על הכפתור עצמו)
            document.title = '__sync_layer_checkboxes__';
        }}

        function _performRedo() {{
            if (!_redoStack.length || _isRestoringUndo) return;
            var entry = _redoStack.pop();
            _isRestoringUndo = true;
            var backward;
            try {{ backward = entry.restore(); }} finally {{ _isRestoringUndo = false; }}
            _undoStack.push({{label: entry.label, restore: backward}});
            _updateUndoRedoButtons();
            document.title = '__sync_layer_checkboxes__';  // ר' הערה מקבילה ב-_performUndo
        }}

        function _updateUndoRedoButtons() {{
            if (_undoBtnEl) _undoBtnEl.style.opacity = _undoStack.length ? '1' : '0.35';
            if (_redoBtnEl) _redoBtnEl.style.opacity = _redoStack.length ? '1' : '0.35';
        }}

        // עוזר נפוץ: רושם undo לשינוי ערך שדה DOM בודד (input/select) — el.value לפני/אחרי.
        // לא רושם אם הערך בפועל לא השתנה (מונע פקודות undo מיותרות, למשל focus+blur בלי עריכה).
        function _recordFieldUndo(el, beforeValue, label, onApply) {{
            if (_isRestoringUndo || el.value === beforeValue) return;
            _pushUndo(label, _makeValueRestore(
                function(v) {{ el.value = v; }},
                function() {{ return el.value; }},
                beforeValue, onApply
            ));
        }}

        // מצרף לשדה DOM מעקב focus→blur לרישום undo אוטומטי — נקרא פעם אחת לכל שדה בזמן בנייתו
        // (מתוך _mkField של כל כלי), כדי לא לשכפל את לוגיקת ה-focus/blur הזו בכל כלי בנפרד.
        function _attachFieldUndo(el, label, onApply) {{
            var focusValue = null;
            L.DomEvent.on(el, 'focus', function() {{ focusValue = el.value; }});
            L.DomEvent.on(el, 'blur', function() {{
                if (focusValue !== null) _recordFieldUndo(el, focusValue, label, onApply);
                focusValue = null;
            }});
        }}

        // מקביל ל-_attachFieldUndo, אבל ל-<select> (משתנה אטומית ב-'change', אין focus/blur
        // הדרגתי כמו בטקסט) — בשחזור גם משגר אירוע 'change' אמיתי, כדי שכל מאזין חיצוני
        // שתלוי בבחירה הזו (למשל חשיפת שדות מערך-מופעים) יתעדכן ממילא, בלי שנצטרך להכיר אותו.
        function _attachSelectUndo(sel, label) {{
            var prevValue = sel.value;
            L.DomEvent.on(sel, 'change', function() {{
                if (_isRestoringUndo) {{ prevValue = sel.value; return; }}
                var before = prevValue;
                if (sel.value !== before) {{
                    _pushUndo(label, _makeValueRestore(
                        function(v) {{ sel.value = v; sel.dispatchEvent(new Event('change')); }},
                        function() {{ return sel.value; }},
                        before, null
                    ));
                }}
                prevValue = sel.value;
            }});
        }}

        // מקביל ל-_attachSelectUndo, אבל ל-checkbox (.checked בוליאני, לא .value מחרוזת)
        function _attachCheckboxUndo(chk, label) {{
            var prevChecked = chk.checked;
            L.DomEvent.on(chk, 'change', function() {{
                if (_isRestoringUndo) {{ prevChecked = chk.checked; return; }}
                var before = prevChecked;
                if (chk.checked !== before) {{
                    _pushUndo(label, _makeValueRestore(
                        function(v) {{ chk.checked = v; chk.dispatchEvent(new Event('change')); }},
                        function() {{ return chk.checked; }},
                        before, null
                    ));
                }}
                prevChecked = chk.checked;
            }});
        }}

        // קיצורי מקלדת גלובליים — Ctrl+Z (undo), Ctrl+Y או Ctrl+Shift+Z (redo, שני המוסכמות
        // הנפוצות). מוגדר ברמת document כדי לעבוד מכל מקום בעמוד, גם כששדה קלט ממוקד.
        document.addEventListener('keydown', function(e) {{
            if (!(e.ctrlKey || e.metaKey)) return;
            var key = e.key ? e.key.toLowerCase() : '';
            if (key === 'z' && !e.shiftKey) {{ e.preventDefault(); _performUndo(); }}
            else if (key === 'y' || (key === 'z' && e.shiftKey)) {{ e.preventDefault(); _performRedo(); }}
        }});

        // ── מצב כלי קווי ראייה (LOS) ──
        var losActive   = false;  // האם מצב הוספת קו ראייה חדש פעיל (cursor crosshair)
        var losSessions = [];     // כל הסשנים שחושבו: [{{obsMk, tgtMk, lineLayers, data, color, idx}}]
        var losCurObs   = null;   // נקודת התצפית של הצמד הנוכחי (בין לחיצה 1 ל-2)
        var losCurObsMk = null;   // סמן תצפית זמני של הצמד הנוכחי (לפני בחירת היעד)
        var losPanelEl  = null;   // אלמנט פאנל גרפים תחתון
        var _losBtnEl   = null;   // הפניה לכפתור 👁 לצורך שינוי צבעו
        var _losObsInput = null; // שדה קלט גובה הצופה מעל הקרקע (מ')
        var _losTgtInput = null; // שדה קלט גובה היעד מעל הקרקע (מ')
        // ── FR-D-290: גובה בחינה (מ'/רגל/א"ר, AGL/MSL) וגזרת מכ"ם לכלי קווי הראייה ──
        var _losTgtUnitSel = null, _losTgtRefSel = null, _losStartInput = null, _losEndInput = null;  // קו ראייה נקודתי: יחידות, ייחוס, גזרה
        var _radialTgtUnitSel = null, _radialTgtRefSel = null;  // רדיוס ראייה: יחידות וייחוס
        var _losMarginInput = null;  // קו ראייה נקודתי: מרווח רכס (°)

        function _rsHeightM(v, unit) {{ return unit === 'kft' ? v * 304.8 : (unit === 'ft' ? v * 0.3048 : v); }}  // המרה למטרים (א"ר = אלפי רגל)

        function _rsHeightText(inp, unitSel, refSel) {{
            // תיאור גובה הבחינה לתוצאה, למשל "32 א"ר (9754 מ') מעל פני הים"
            var v = inp ? parseFloat(inp.value) : 0; if (isNaN(v)) v = 0;  // הערך
            var u = unitSel ? unitSel.value : 'm', r = refSel ? refSel.value : 'agl';  // יחידות וייחוס
            var lbl = {{m: " מ'", ft: ' רגל', kft: ' א"ר'}}[u] || '';  // שם היחידה
            return v + lbl + (u !== 'm' ? ' (' + Math.round(_rsHeightM(v, u)) + " מ')" : '') + (r === 'msl' ? ' מעל פני הים' : ' מעל הקרקע');  // הטקסט
        }}

        function _rsBuildHeightRow(parent, onChange) {{
            // שורת יחידות (מטר/רגל/א"ר) וייחוס (AGL/MSL) לגובה הבחינה
            var row = L.DomUtil.create('div', '', parent); row.style.cssText = 'display:flex;align-items:center;gap:3px;font-size:9px;color:#666;flex-wrap:wrap;';  // שורה
            function sel(opts, tip) {{  // בורר קטן
                var s = L.DomUtil.create('select', '', row); s.title = tip; s.setAttribute('aria-label', tip); s.style.cssText = 'font-size:9px;min-height:24px;max-width:110px;';  // T11 (F-040): יעד לחיצה ≥24px (היה 22)
                opts.forEach(function(o) {{ var e = L.DomUtil.create('option', '', s); e.value = o[0]; e.textContent = o[1]; }});  // אפשרויות
                if (onChange) L.DomEvent.on(s, 'change', onChange); return s;  // שינוי
            }}
            var unit = sel([['m', 'מטר'], ['ft', 'רגל'], ['kft', 'א"ר (אלפי רגל)']], 'יחידות גובה הבחינה');  // יחידות
            var ref = sel([['agl', 'מעל הקרקע (AGL)'], ['msl', 'מעל פני הים (MSL)']], 'ייחוס: AGL עוקב אחרי השטח; MSL — גובה קבוע מעל פני הים (כמו מטוס בגובה שיוט)');  // ייחוס
            L.DomEvent.disableClickPropagation(row);  // לא מגיע למפה
            return {{unit: unit, ref: ref}};  // שני הבוררים
        }}

        function _rsBuildSectorButton(parent, startIn, endIn, after) {{
            // "📐 גזרה מהמכ"ם": כיוון הפנים ± זווית הסריקה (מערך מופע), או 0–360 (אנטנה גנרית)
            var b = L.DomUtil.create('button', '', parent); b.textContent = '📐 גזרה מהמכ"ם';  // הכפתור
            b.title = 'ממלא את הגזרה מכיוון הפנים ± זווית הסריקה של המכ"ם (מערך מופע), או 0–360 (אנטנה גנרית)'; b.setAttribute('aria-label', b.title);  // הסבר
            b.style.cssText = 'font-size:9px;min-height:24px;padding:1px 4px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';  // T11 (F-040): ≥24px (היה 22); עיצוב
            L.DomEvent.on(b, 'click', function(e) {{
                L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);  // לא מגיע למפה
                var bo = _radarBoresightInput ? (parseFloat(_radarBoresightInput.value) || 0) : 0;  // כיוון הפנים
                var ms = _radarMaxScanInput ? (parseFloat(_radarMaxScanInput.value) || 180) : 180;  // זווית הסריקה
                var ph = _radarAntennaSelect && _radarAntennaSelect.value === 'phased_array';  // מערך מופע?
                startIn.value = ph ? (((bo - ms) % 360 + 360) % 360).toFixed(1) : 0;  // התחלה
                endIn.value = ph ? (((bo + ms) % 360 + 360) % 360).toFixed(1) : 360;  // סיום
                startIn.dispatchEvent(new Event('input')); endIn.dispatchEvent(new Event('input'));  // סנכרון (מכ"ם פעיל) ותצוגה מקדימה
                if (after) after();  // ציור מחדש
            }});
            return b;  // הכפתור
        }}

        function _rsSectorSpan(start, end) {{ return ((end - start) % 360 + 360) % 360; }}  // רוחב הגזרה במעלות (0 = מעגל מלא)

        function _rsInSector(brg, start, end) {{
            // האם אזימוט בתוך הגזרה (כולל גזרה שעוברת דרך הצפון, למשל 315→45)
            var span = _rsSectorSpan(start, end); if (span === 0) return true;  // מעגל מלא
            return ((brg - start) % 360 + 360) % 360 <= span;  // בתוך הגזרה
        }}

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

        // ── כלי מסלול בליסטי (MPM) — כלי שישי, Stage 3 (FR-D-234/235) — gun+target+5 טאבים ──
        var ballisticsActive   = false; // האם מצב-הצבה פעיל (cursor crosshair) — דומה ל-radarActive וכו'
        var _ballisticsSetActive = function() {{}};  // פתיחה/סגירה של הכלי הבליסטי — מוגדר ב-BallisticsControl (תיקון תקלה 26/11/2026)
        var _rtMapPickActive = false;  // בחירה מהמפה מטאב "מעקב מכ"ם" (מכ"ם / מרכז שיוט) — הלחיצה לא מזיזה תותח/מטרה
        var _fitPanelEls = [];  // פאנלים בעמודה הימנית שהגובה המרבי שלהם מותאם למקום שנשאר על המסך

        function _fitTopRightPanels() {{
            // לכל פאנל פתוח: גובה מרבי = מתחילת הפאנל ועד תחתית המפה, פחות שוליים לסרגל הקנה-מידה ולייחוס.
            // מתעדכן רק בשינוי של יותר מ-2 פיקסלים — כדי שמעקב הגודל (ResizeObserver) לא ייכנס ללולאה
            var bottom = map.getContainer().getBoundingClientRect().bottom;  // תחתית המפה
            _fitPanelEls.forEach(function(el) {{  // כל פאנל רשום
                if (el.style.display === 'none') return;  // סגור — לא רלוונטי
                var mh = Math.max(120, Math.floor(bottom - el.getBoundingClientRect().top - 62));  // המקום שנשאר (לפחות 120); 62 = מעל סרגל קנה-המידה ושורת הייחוס
                if (Math.abs((parseFloat(el.style.maxHeight) || 0) - mh) > 2) el.style.maxHeight = mh + 'px';  // עדכון
            }});
        }}
        var ballisticsEditing  = 'gun'; // 'gun'|'target' — איזו נקודה הלחיצה הבאה על המפה קובעת
        var ballisticsGun      = null;  // {{lat,lng,alt}} — נקודת התותח; alt מתמלא אוטומטית מהגובה בשרת
        var ballisticsTarget   = null;  // {{lat,lng,alt}} — נקודת המטרה
        var ballisticsGunMk    = null;  // סמן התותח על המפה (ניתן לגרירה)
        var ballisticsTgtMk    = null;  // סמן המטרה על המפה (ניתן לגרירה)
        var ballisticsPathLn   = null;  // L.polyline — המסלול המחושב האחרון (קו-על-קרקע, לא תלת-ממדי)
        var ballisticsImpactMk = null;  // סמן נקודת-הפגיעה
        var ballisticsApexMk   = null;  // סמן הקודקוד (הנקודה הגבוהה ביותר במסלול)
        var ballisticsCollMk   = null;  // סמן נקודת-התנגשות-בקרקע (אם terrain_check מזהה חסימה), null אם אין
        var ballisticsLoading  = false; // חישוב רץ כרגע (fetch) — מונע הפעלה כפולה
        var ballisticsLastPath = null;  // path מהחישוב האחרון — נצרך ע"י terrain_check/min_qe_for_crest בלי לחשב מסלול מחדש
        var ballisticsInfoEl   = null;  // תיבת-הטקסט בתוך ה-Control (תוצאות/שגיאות/טעינה)
        var ballisticsProfileCanvas = null; // קנבס פרופיל-צד (גובה-קרקע מתחת למסלול), בתוך הפאנל
        var ballisticsPanelBodyEl  = null;  // גוף הפאנל — מוסתר עד בחירת הכלי (כמו שאר הכלים)
        var _ballisticsBtnEl       = null;  // הפניה לכפתור 💥 לצורך שינוי-צבע
        // "גשרים" בין onAdd (שמגדיר אותם) לפונקציות הטאבים (שנקראות ממנו, אבל גם מ-event handlers
        // חוץ ל-onAdd, למשל כפתורי-חישוב) — מוצהרים כאן כ-var כדי שלא יהיו global משתמע (sloppy-mode)
        var _ballisticsSyncFields = function() {{}};      // מעדכן שדות lat/lon/alt מהמצב הפנימי
        var _ballisticsGetCommonParams = function() {{}}; // אוסף mv/met/fitting/units/coriolis/curvature
        var _ballisticsGetGunTarget = function() {{}};    // {{gun,target}} בפורמט ל-fetch
        var _ballisticsAltUi = function() {{}};           // T21 (F-053): מעדכן שדות גובה + אזהרת "שליפת גובה נכשלה" לפי מצב הנקודות (מוגדר בבניית הפאנל)
        function _ballisticsAltGuard(needTarget) {{       // T21 (F-053): מחזיר הודעה אם גובה התותח/המטרה לא ידוע, אחרת '' — חוסם חישוב מגובה 0 בשקט
            function unknown(pt) {{ return !pt || pt.alt === null || pt.alt === undefined || !isFinite(pt.alt); }}  // T21: גובה חסר/לא מספרי
            function msg(name, pt) {{                      // T21: הודעה לפי מצב השליפה
                if (pt && pt.altState === 'pending') return 'גובה ' + name + ' עדיין נטען — נסה שוב בעוד רגע';  // T21: השליפה עוד רצה
                return 'גובה ' + name + ' לא ידוע (שליפת הגובה נכשלה). הזן גובה ידנית בשדה, או לחץ "🔄 נסה שוב לשלוף גובה".';  // T21: נכשל/נמחק
            }}
            if (ballisticsGun && unknown(ballisticsGun)) return msg('התותח', ballisticsGun);  // T21: התותח בלי גובה ידוע
            if (needTarget && ballisticsTarget && unknown(ballisticsTarget)) return msg('המטרה', ballisticsTarget);  // T21: המטרה בלי גובה (רק בחישובים שצריכים מטרה)
            return '';  // T21: הכול ידוע — אפשר לחשב
        }}
        var _ballisticsSelectTab = function() {{}};       // מחליף טאב פעיל
        var _ballisticsTabBodies = {{}};                  // key->DOM element של כל טאב
        var _ballisticsMkField = null, _ballisticsMkSelect = null, _ballisticsMkHeader = null;  // "מפעל" רכיבים, משותף לכל הטאבים
        var _ballisticsMetStatusEl = null;  // תווית סטטוס-מטאו בפאנל הראשי (לא בתוך טאב)
        var _ballisticsMetTabStatusEl = null;  // תווית סטטוס-מטאו בתוך טאב "מטאו" עצמו
        var _ballisticsSolveSetQeMin = function() {{}};  // מציב qe_min בטאב "פתרון ירי" מתוך תוצאת min_qe_for_crest

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
        var _radarJobKind  = null;  // 'sweep' (ברירת מחדל, /radar_doppler/start) או 'route_eval' — קובע מה _pollRadarDopplerStatus מצייר בסיום
        var radarInfoEl    = null;  // תיבת הטקסט הקטנה בתוך ה-Control (מציגה מצב/התקדמות/סיכום)
        var _radarProfilePanelEl = null;  // פאנל חתך-הצד לקרן בודדת בלחיצה — נפרד מ-losPanelEl (לא שייך סמנטית ל-losSessions)
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
        var _radarRcsInput      = null; // שטח חתך רדארי (RCS, מ"ר) — שדה מספרי חופשי (לא dropdown קשיח) לדרגות חופש מלאות; dropdown ליד זה למילוי מהיר בלבד
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
                    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',  // ייחוס מלא לפי opentopomap.org/about — כולל SRTM ורישיון CC-BY-SA (ביקורת רישוי)
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

            // תצלום לוויין — Esri World Imagery (רישיון Esri Master License Agreement), רזולוציה גבוהה
            'satellite': L.tileLayer(
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
                {{
                    attribution: 'Source: <a href="https://www.esri.com">Esri</a>, Vantor, Earthstar Geographics, and the GIS User Community',  // נוסח הייחוס הרשמי מה-copyrightText של שירות Esri (ביקורת רישוי)
                    maxZoom: 19   // Esri מספק תמונות עד zoom 19
                }}
            )
        }};

        var currentBaseLayer = baseLayers['topo'];  // שכבת ברירת המחדל — טופוגרפית
        currentBaseLayer.addTo(map);                // הוספה ראשונית למפה
        // ייחוס קבוע לנתוני Open-Meteo (גבהים/טמפרטורות/מטאו) — חובה לפי רישיון CC BY 4.0 של Open-Meteo (ביקורת רישוי)
        map.attributionControl.addAttribution('Elevation &amp; weather data by <a href="https://open-meteo.com/">Open-Meteo.com</a>');
        map.attributionControl.addAttribution('SRTM data courtesy of the <a href="https://registry.opendata.aws/terrain-tiles/">U.S. Geological Survey</a>');  // גבהים מקומיים (srtm_dem.py) — ייחוס נדרש לפי tilezen/joerd attribution.md

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
                    btn.setAttribute('aria-label', 'שכבת בסיס: ' + layer.label.replace(/^[^\\s]+\\s/, ''));  // נגישות — הסרת אייקון-emoji מהתווית המוקראת (F-027, Q-1)

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

        // ── פקד Undo/Redo — שני כפתורים קבועים למעלה-שמאל, מעל פקד הזום ──
        var UndoRedoControl = L.Control.extend({{
            options: {{ position: 'topleft' }},  // אותה פינה כמו פקד הזום — יופיע מתחתיו

            onAdd: function(map) {{
                var container = L.DomUtil.create('div', 'undo-redo-ctrl');

                _undoBtnEl = L.DomUtil.create('button', 'undo-redo-btn', container);
                _undoBtnEl.innerHTML = '↶';           // חץ חזרה — Undo
                _undoBtnEl.title = 'בטל פעולה (Ctrl+Z)';
                _undoBtnEl.setAttribute('aria-label', 'בטל פעולה');  // נגישות (F-027, Q-1)

                _redoBtnEl = L.DomUtil.create('button', 'undo-redo-btn', container);
                _redoBtnEl.innerHTML = '↷';           // חץ קדימה — Redo
                _redoBtnEl.title = 'בצע שוב (Ctrl+Y)';
                _redoBtnEl.setAttribute('aria-label', 'בצע פעולה שוב');  // נגישות (F-027, Q-1)

                // מניעת הגלשת לחיצות/גלילה למפה מאחורי הפקד
                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);

                L.DomEvent.on(_undoBtnEl, 'click', _performUndo);
                L.DomEvent.on(_redoBtnEl, 'click', _performRedo);

                _updateUndoRedoButtons();  // קביעת מצב עמעום ראשוני (שני המחסניות ריקות)

                return container;
            }}
        }});

        new UndoRedoControl().addTo(map);  // יצירת מופע הפקד והוספתו למפה

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
                    d.setAttribute('role', 'status');  // נגישות — תצוגת-מידע בלבד, לא כפתור (F-027, Q-1)
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
                    this._d.setAttribute('aria-label', 'קנה מידה: ' + kmTxt + ' / ' + nmTxt);  // נגישות — מתעדכן עם המפה (F-027, Q-1)
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
            _lastFlightRouteData = routeData;  // נשמר לשימוש מאוחר יותר בהערכת מסלול מול מכ"ם-דופלר (כולל alt/spd/hd לכל נקודה)

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
            _lastFlightRouteData = null;  // אין יותר מסלול לטעון — מונע הערכה מול מסלול שכבר לא מוצג
            _clearRouteEvaluation();  // מנקה גם קטעי-הערכה צבעוניים, אם היו
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
        function _makeCollapsibleLegend(iconHtml, bodyHtml, getExpanded, setExpanded, ariaLabel) {{
            // ariaLabel: נגישות (F-027, Q-1) — תווית-מקרא לקורא-מסך, מועברת ע"י כל קורא (NOTAM/תיאום-כטב"ם/CTR)
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
                    d.setAttribute('role', 'region');  // נגישות (F-027, Q-1) — מצב מורחב: אזור-תוכן, לא כפתור
                    d.setAttribute('aria-label', ariaLabel || 'מקרא');
                    var collapseBtn = d.querySelector('._legendCollapseBtn');  // כפתור ה-X בפועל במצב מורחב
                    if (collapseBtn) {{
                        collapseBtn.setAttribute('role', 'button');
                        collapseBtn.setAttribute('aria-label', 'סגור מקרא');
                    }}
                }} else {{
                    // מצב מצומצם — עיגול קטן בלבד, לא חוסם את תצוגת המפה
                    d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;width:30px;height:30px;'
                        + 'border-radius:50%;border:1px solid #45475a;display:flex;align-items:center;'
                        + 'justify-content:center;font-size:15px;cursor:pointer;';
                    d.innerHTML = iconHtml;
                    d.setAttribute('role', 'button');  // נגישות (F-027, Q-1) — מצב מצומצם: לחיצה מרחיבה את המקרא
                    d.setAttribute('aria-label', ariaLabel || 'מקרא');
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
                    function(v) {{ notamLegendExpanded = v; }},
                    'מקרא אזורי פעילות טיסה NOTAM');  // נגישות (F-027, Q-1)
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
                        if (!_isRestoringUndo) {{  // בטעינה ראשונה הקטגוריה תמיד עברה מ-false ל-true
                            _pushUndo('קטגוריית NOTAM: ' + catId, _makeSimpleToggleRestore(
                                function() {{ toggleNotamCategory(catId); }},
                                function() {{ return activeNotamCategories.has(catId); }}, false));
                        }}
                    }})
                    .catch(function(err) {{
                        console.error('שגיאת שכבת NOTAM:', err);
                        document.title = '__uas_notam_error__:' + catId;  // מזהה הקטגוריה שנכשלה — כדי שרק תיבת הסימון שלה תוחזר ללא-מסומן
                    }});
                return;
            }}
            // כבר נטען בעבר — toggle סינכרוני בלבד, בלי בקשת רשת נוספת
            var _prevCatActive = activeNotamCategories.has(catId);  // מצב קודם — לפני ה-toggle, לצורך Undo
            if (activeNotamCategories.has(catId)) {{ activeNotamCategories.delete(catId); }}
            else {{ activeNotamCategories.add(catId); }}
            _redrawNotamLayer();
            if (!_isRestoringUndo) {{
                _pushUndo('קטגוריית NOTAM: ' + catId, _makeSimpleToggleRestore(
                    function() {{ toggleNotamCategory(catId); }},
                    function() {{ return activeNotamCategories.has(catId); }}, _prevCatActive));
            }}
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
                    function(v) {{ uasCoordLegendExpanded = v; }},
                    'מקרא אזורי תיאום כטבם');  // נגישות (F-027, Q-1)
            }}
        }});

        function toggleUasCoordZonesLayer() {{
            // סינכרוני לגמרי — הנתונים כבר בעמוד (uasCoordZonesData), אין fetch/loading/error
            var _prevCoordActive = uasCoordActive;  // מצב קודם — לפני ה-toggle, לצורך Undo
            if (uasCoordActive) {{
                clearUasCoordZonesLayer();
            }} else {{
                _drawUasCoordZones(uasCoordZonesData);
            }}
            if (!_isRestoringUndo) {{
                _pushUndo('שכבת אזורי-תיאום כטב"ם', _makeSimpleToggleRestore(
                    toggleUasCoordZonesLayer, function() {{ return uasCoordActive; }}, _prevCoordActive));
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
                    function(v) {{ airportCtrLegendExpanded = v; }},
                    'מקרא גבולות CTR שדות תעופה');  // נגישות (F-027, Q-1)
            }}
        }});

        function toggleAirportCtrLayer() {{
            // סינכרוני לגמרי — הנתונים כבר בעמוד (airportCtrZonesData), אין fetch/loading/error
            var _prevCtrActive = airportCtrActive;  // מצב קודם — לפני ה-toggle, לצורך Undo
            if (airportCtrActive) {{
                clearAirportCtrLayer();
            }} else {{
                _drawAirportCtrZones(airportCtrZonesData);
            }}
            if (!_isRestoringUndo) {{
                _pushUndo('שכבת גבולות CTR', _makeSimpleToggleRestore(
                    toggleAirportCtrLayer, function() {{ return airportCtrActive; }}, _prevCtrActive));
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
            _clearCustomRoute();  // ניקוי מסלול הטיסה המותאם (נקודות/קו/סמנים)
            if (customRouteActive) {{ toggleCustomRoute(); }}  // כיבוי מצב הוספת נקודות אם פעיל
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
        // Desktop: false בהתחלה, מסונכרן מ-main.py (start_servers/stop_servers קוראים ל-_setServersRunning)
        // כי שלושת שרתי ה-Flask המקומיים צריכים להיות מופעלים-בפועל לפני שהכלים התלויים בהם (LOS/
        // רדיוס-ראייה/מכ"ם-דופלר/בליסטי) פעילים. Web: תמיד true מההתחלה — אין main.py שמפעיל/מכבה
        // שרת מקומי, ה-backend (Vercel) כבר פעיל תמיד; בלי זה כל הכפתורים האלה נשארים מנוטרלים-לנצח
        // (opacity:0.4;pointer-events:none) ב-Web, כי שום דבר לעולם לא קורא ל-_setServersRunning(true)
        // שם — נמצא בדיווח אמיתי של המשתמש ("אין יכולת להפעיל שרתים וכל התפריט... לא קיים").
        var serversRunning = {'true' if target == 'web' else 'false'};

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
            if (_rsPickClick(e.latlng)) return;  // FR-D-288: מצב "📍 מקם" של הבורר הגלובלי — הלחיצה קובעת את מיקום המכ"ם הפעיל
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
                var _rsObs = !losCurObs ? _rsSharedObs('los') : null;  // FR-D-288: מכ"ם פעיל ומחובר — הצופה הוא המכ"ם, והלחיצה היא היעד
                if (_rsObs) {{
                    var _rsIdx = losSessions.length, _rsCol = _losPalette[_rsIdx % _losPalette.length];  // מספר וצבע הסשן
                    losCurObs = _rsObs;  // נקודת התצפית = מיקום המכ"ם
                    losCurObsMk = L.marker(_rsObs, {{icon: _losMarkerIcon(_rsCol, false), draggable: false}}).addTo(map);  // לא נגרר — מזיזים את המכ"ם עצמו
                    losCurObsMk.bindTooltip('תצפית ' + (_rsIdx + 1) + ' (המכ"ם הפעיל)', {{permanent:false, direction:'top'}});  // הסבר
                }}
                if (!losCurObs) {{
                    // לחיצה ראשונה — שמירת נקודת התצפית
                    losCurObs    = e.latlng;
                    var sIdx     = losSessions.length;                          // מספר הסשן הבא (לכותרת ולצבע)
                    var col      = _losPalette[sIdx % _losPalette.length];      // צבע ייחודי מהפלטה
                    if (losCurObsMk) {{ map.removeLayer(losCurObsMk); }}        // ניקוי סמן ביניים ישן
                    // ציור סמן עגול מוצק בצבע הסשן בנקודת התצפית — ניתן לגרירה
                    losCurObsMk = L.marker(e.latlng, {{icon: _losMarkerIcon(col, false), draggable: true}}).addTo(map);
                    losCurObsMk.bindTooltip('תצפית ' + (sIdx + 1), {{permanent:false, direction:'top'}});
                    if (!_isRestoringUndo) {{
                        _pushUndo('קו ראייה: נקודת תצפית ראשונה', _makeLosPendingObsRestore(losCurObsMk, e.latlng, true));
                    }}
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
                    var tgtTxt = _rsHeightText(_losTgtInput, _losTgtUnitSel, _losTgtRefSel);  // FR-D-290: תיאור גובה הבחינה (לפני ההמרה)
                    tgtH = _rsHeightM(tgtH, _losTgtUnitSel ? _losTgtUnitSel.value : 'm');  // FR-D-290: המרה למטרים (מ'/רגל/א"ר)
                    var tgtRef = _losTgtRefSel ? _losTgtRefSel.value : 'agl';  // FR-D-290: AGL / MSL
                    var mrg = _losMarginInput ? parseFloat(_losMarginInput.value) : 0; if (isNaN(mrg)) mrg = 0;  // FR-D-290: מרווח רכס
                    var sec = {{start: parseFloat(_losStartInput && _losStartInput.value) || 0, end: _losEndInput ? (parseFloat(_losEndInput.value)) : 360}};  // FR-D-290: גזרה
                    if (isNaN(sec.end)) sec.end = 360;  // ריק = בלי הגבלה
                    losCurObsMk.setTooltipContent('תצפית ' + (sIdx + 1) + ' (+' + obsH + 'מ\\')');
                    tgtMk.setTooltipContent('יעד ' + (sIdx + 1) + ' (' + tgtTxt + ')');  // FR-D-290: גובה הבחינה ביחידות ובייחוס שנבחרו
                    // יצירת אובייקט הסשן — data=null עד שהשרת יחזיר תשובה
                    var session = {{obsMk:losCurObsMk, tgtMk:tgtMk, lineLayers:[], data:null, color:col, idx:sIdx + 1, obsH:obsH, tgtH:tgtH,
                                    rs: _rsLosSnapshot(),  // FR-D-288: מגבלות המכ"ם הפעיל ברגע יצירת הצמד (null = ידני / צופה נפרד)
                                    tgtRef: tgtRef, tgtTxt: tgtTxt, margin: mrg, sec: sec}};  // FR-D-290: ייחוס, תיאור גובה, מרווח רכס, גזרה
                    losSessions.push(session);               // הוספה למערך הסשנים
                    var obsPoint = losCurObs;                 // שמירת נקודת התצפית לפני האיפוס
                    losCurObs = null; losCurObsMk = null;    // איפוס — מוכן לצמד הבא מיד
                    // גרירת סמן תצפית או יעד — חישוב מחדש אוטומטי של קו הראייה, ללא צורך ביצירת קו חדש
                    var _obsDragFrom = null, _tgtDragFrom = null;  // מיקום לפני גרירה — נלכד ב-dragstart, נצרך ב-dragend
                    session.obsMk.on('dragstart', function() {{ _obsDragFrom = session.obsMk.getLatLng(); }});
                    session.obsMk.on('dragend', function() {{
                        _runLos(session.obsMk.getLatLng(), session.tgtMk.getLatLng(), session);
                        if (!_isRestoringUndo && _obsDragFrom) {{
                            _pushUndo('קו ראייה: הזזת תצפית ' + session.idx, _makeMarkerMoveRestore(
                                function(v) {{ session.obsMk.setLatLng(v); _runLos(v, session.tgtMk.getLatLng(), session); }},
                                function() {{ return session.obsMk.getLatLng(); }}, null, _obsDragFrom));
                        }}
                    }});
                    session.tgtMk.on('dragstart', function() {{ _tgtDragFrom = session.tgtMk.getLatLng(); }});
                    session.tgtMk.on('dragend', function() {{
                        _runLos(session.obsMk.getLatLng(), session.tgtMk.getLatLng(), session);
                        if (!_isRestoringUndo && _tgtDragFrom) {{
                            _pushUndo('קו ראייה: הזזת יעד ' + session.idx, _makeMarkerMoveRestore(
                                function(v) {{ session.tgtMk.setLatLng(v); _runLos(session.obsMk.getLatLng(), v, session); }},
                                function() {{ return session.tgtMk.getLatLng(); }}, null, _tgtDragFrom));
                        }}
                    }});
                    _runLos(obsPoint, e.latlng, session);    // הפעלת חישוב LOS עם הצמד שנבחר
                    if (!_isRestoringUndo) {{
                        // ה-lineLayers עוד ריק כרגע (_runLos עדיין רץ ברקע) — אבל זה אותו מערך בהפניה, ולכן
                        // בזמן שה-Undo בפועל יופעל (מאוחר יותר, ע"י המשתמש) הוא כבר יכיל את הקווים המחושבים
                        _pushUndo('קו ראייה: צמד תצפית-יעד ' + (sIdx + 1), _makeLosSessionRestore(session, true));
                    }}
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
                        <div style="direction:ltr;text-align:left;font-size:10px;color:#777;margin-top:4px;">Weather data &copy; <a href="https://openweathermap.org/" target="_blank">OpenWeather</a> &middot; Elevation: <a href="https://open-meteo.com/" target="_blank">Open-Meteo.com</a></div> <!-- ייחוס גלוי לנתוני מזג אוויר (ODbL, OpenWeather) וגובה (CC BY 4.0, Open-Meteo) — ביקורת רישוי -->
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
                      '&tgt_h=' + (session.tgtH != null ? session.tgtH : 0) +
                      '&tgt_ref=' + (session.tgtRef || 'agl') + '&ridge_margin_deg=' + (session.margin || 0);  // FR-D-290: ייחוס גובה ומרווח רכס (ברירות המחדל = כמו קודם)
            fetch(url)
            .then(function(r) {{
                // FR-D-288 (תיקון): הודעת השרת מוצגת (למשל "מכסת נתוני הגובה נוצלה") — ולא רק "HTTP 500"
                return r.json().catch(function() {{ return {{}}; }}).then(function(d) {{ if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }});
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
                var _rsLim = _rsLosLimitsText(session);  // FR-D-288: מגבלות המכ"ם (סקטור/טווח/שדה אנכי) לצמד הזה
                if (_rsLim) {{
                    var limEl = document.createElement('div');  // שורה מתחת לכותרת
                    limEl.textContent = _rsLim;  // טקסט בלבד (שם מכ"ם הוא טקסט חופשי של המשתמש)
                    limEl.style.cssText = 'font:10px Arial;color:#cdd6f4;padding:1px 6px;background:#181825;direction:rtl;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0;';  // שורה אחת
                    limEl.title = _rsLim;  // הטקסט המלא בריחוף
                    col.appendChild(limEl);
                }}
                // canvas לגרף הסשן — flex:1 ממלא את שארית גובה העמודה
                var canvas = document.createElement('canvas');
                canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'גרף קו ראייה: גובה השטח, קו הראייה וגובה היעד לאורך המרחק');  // T12 (F-041): שם נגיש לגרף
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

            // קו אנכי מקווקו ציאן — רק כשמגיע מפרופיל מכ"ם-דופלר (typeof, לא !==, כי /los הרגיל
            // לא שולח את השדה הזה בכלל): מסמן היכן המכ"ם/דופלר הפסיקו לזהות, גם אם זה *לפני*
            // שהשטח עצמו חסם (קו הראייה הירוק ממשיך אחריו) — בדיוק ההבחנה שהמשתמש רצה לראות
            if (typeof data.radar_dist_km !== 'undefined' && data.radar_dist_km < pts[pts.length - 1].dist_km) {{
                var idxAtRadar = pts.length - 1;
                for (var ri = 0; ri < pts.length; ri++) {{  // מוצא את אינדקס הנקודה הקרוב ביותר למרחק הזה, לצורך מיקום ה-X
                    if (pts[ri].dist_km >= data.radar_dist_km) {{ idxAtRadar = ri; break; }}
                }}
                var xRadar = xOf(idxAtRadar);
                ctx.beginPath();
                ctx.setLineDash([4, 3]);
                ctx.moveTo(xRadar, PAD.t); ctx.lineTo(xRadar, PAD.t + cH);
                ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 1.5; ctx.stroke();
                ctx.setLineDash([]);
            }}

            // שורת מידע עליונה: מרחק כולל + חסימה ראשונה (אם יש) + סטטוס דופלר (רק בפרופיל מכ"ם-דופלר)
            var info = data.total_km + ' ק"מ';
            if (data.first_block_km !== null) {{
                info += '  ⛔ ' + data.first_block_km + 'ק';  // מרחק חסימה ראשונה
            }} else {{
                info += '  ✓';  // ✓ ראייה מלאה לאורך כל המסלול
            }}
            if (typeof data.doppler_ok !== 'undefined' && !data.doppler_ok) {{
                info += '  〰️ חסום-דופלר';  // כל הכיוון הזה עיוור לדופלר, ללא קשר לשטח
            }}
            ctx.fillStyle = '#aaa'; ctx.font = '10px Arial'; ctx.textAlign = 'center';
            ctx.fillText(info, PAD.l + cW / 2, PAD.t - 3);  // מעל אזור הגרף
        }}

        // ── "עמדות שמורות" — UI משותף לשלושת כלי התצפית (LOS/רדיוס-ראייה/מכ"ם-דופלר) ──
        // שמירה/טעינה/מחיקה של מיקום+פרמטרים תחת שם, דרך /stations/* ב-weather_server.py.
        var _stationsCache = {{}};  // toolKey -> [{{name, params}}, ...] — מטמון הרשימה האחרונה שנשלפה, לצורך טעינה בלי fetch נוסף
        function _buildStationUI(parentEl, toolKey, fieldMap, getObsFn, placeObsFn, redrawFn, label) {{
            // parentEl: לאן להוסיף את ה-UI. toolKey: 'los'/'radial_los'/'radar_doppler', או
            // 'radial_los_settings'/'radar_doppler_settings' ל"הגדרות שמורות" בלי מיקום (getObsFn=null אז).
            // fieldMap: {{paramName: inputElement}} — כל שדות הכלי (חוץ ממיקום, המטופל בנפרד).
            // getObsFn: ()=>L.LatLng|null — מיקום נוכחי (null אם אין, כמו ב-LOS, או ב"הגדרות שמורות" במכוון). placeObsFn(latlng): ממקם משקיף.
            // redrawFn: ()=>void — מצייר מחדש תצוגה מקדימה אחרי טעינה (אם רלוונטי לכלי).
            // label: אופציונלי — כותרת קטנה מעל הבלוק, נחוצה כשמוצגים שני בלוקים (עמדות+הגדרות) זה מתחת לזה באותו פאנל.
            if (label) {{
                var headerEl = L.DomUtil.create('div', '', parentEl);
                headerEl.style.cssText = 'font-size:9px;font-weight:bold;color:#666;margin-top:4px;border-top:1px solid #ddd;padding-top:2px;';
                headerEl.textContent = label;
            }}
            var row1 = L.DomUtil.create('div', '', parentEl);
            row1.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:2px;';
            var nameInput = L.DomUtil.create('input', '', row1);
            nameInput.type = 'text'; nameInput.placeholder = 'שם עמדה';
            nameInput.style.cssText = 'flex:1;font-size:10px;padding:2px 3px;border:1px solid #ccc;border-radius:3px;direction:rtl;min-width:0;';
            nameInput.setAttribute('aria-label', 'שם עמדה שמורה');  // נגישות — שדה עם placeholder בלבד (F-027, Q-1)
            var saveBtn = L.DomUtil.create('a', '', row1);
            saveBtn.href = '#'; saveBtn.title = 'שמור עמדה נוכחית תחת השם שהוזן';
            saveBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            saveBtn.innerHTML = '&#128190;';  // 💾
            saveBtn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
            saveBtn.setAttribute('aria-label', 'שמור עמדה נוכחית תחת השם שהוזן');

            var row2 = L.DomUtil.create('div', '', parentEl);
            row2.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:2px;';
            var stationSelect = L.DomUtil.create('select', '', row2);
            stationSelect.style.cssText = 'flex:1;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;min-width:0;';
            stationSelect.setAttribute('aria-label', 'עמדה שמורה לטעינה/מחיקה');  // נגישות (F-027, Q-1)
            var loadBtn = L.DomUtil.create('a', '', row2);
            loadBtn.href = '#'; loadBtn.title = 'טען עמדה נבחרת';
            loadBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            loadBtn.innerHTML = '&#128194;';  // 📂
            loadBtn.setAttribute('role', 'button');  // נגישות (F-027, Q-1)
            loadBtn.setAttribute('aria-label', 'טען עמדה נבחרת');
            var delBtn = L.DomUtil.create('a', '', row2);
            delBtn.href = '#'; delBtn.title = 'מחק עמדה נבחרת';
            delBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
            delBtn.innerHTML = '&#128465;';  // 🗑
            delBtn.setAttribute('role', 'button');  // נגישות (F-027, Q-1)
            delBtn.setAttribute('aria-label', 'מחק עמדה נבחרת');

            function _refreshList() {{
                fetch('http://localhost:5002/stations/list?tool=' + toolKey)
                .then(function(r) {{ return r.json(); }})
                .then(function(data) {{
                    var stations = data.stations || [];
                    _stationsCache[toolKey] = stations;
                    if (toolKey === 'radar_profile') _rtOnMyProfilesChanged(stations);  // FR-D-286: בורר הפרופיל הפעיל מתעדכן עם כל שמירה/מחיקה
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
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:3px 6px;font-family:Arial;max-width:280px;';  // FR-D-288 (תיקון): רוחב מרבי — פס המכ"ם בפנים הרחיב את הכלי עד שעלה על תפריטים אחרים

                var btn = L.DomUtil.create('a', '', container);
                btn.href  = '#';           // ללא ניווט — מונע גלילה לראש הדף
                btn.title = 'קו ראייה';   // tooltip בעת hover
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;' +
                    'width:28px;height:28px;font-size:15px;background:white;color:#333;text-decoration:none;' +
                    'border-radius:4px;cursor:pointer;flex-shrink:0;opacity:0.4;pointer-events:none;';  // מנוטרל עד שהמפה מוכנה (map.whenReady, בהמשך)
                btn.innerHTML = '&#128065;';  // קוד Unicode לאייקון 👁
                btn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
                btn.setAttribute('aria-label', 'כלי קו ראייה');
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
                losFieldsWrap.style.cssText = 'display:none;flex-direction:column;gap:2px;min-width:0;max-width:240px;';  // FR-D-288 (תיקון): לא מתרחב לפי טקסט ארוך בבורר
                _losFieldsWrapEl = losFieldsWrap;
                _rtBuildActiveBar(losFieldsWrap, {{detach: 'los', notes: false}});  // FR-D-288: פס המכ"ם הפעיל + "צופה נפרד" (מחובר: הלחיצה היא היעד)

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
                _losTgtInput = _mkHeightField('יעד', 0, 'גובה הבחינה של היעד — ביחידות ובייחוס שבשורה מתחת (FR-D-290)');
                _losTgtInput.style.width = '48px';  // FR-D-290: מקום לערכים כמו 32 (א"ר) או 9754 (מ')
                _losMarginInput = _mkHeightField('רכס°', 0, 'מרווח רכס (°) — שולי ביטחון מעל הרכס הגבוה; משפיע על הטווח. עם מכ"ם פעיל — של ההצבה (FR-D-290)');  // מרווח רכס
                var _losTgtRow = _rsBuildHeightRow(losFieldsWrap, null);  // FR-D-290: יחידות (מ'/רגל/א"ר) + ייחוס (AGL/MSL)
                _losTgtUnitSel = _losTgtRow.unit; _losTgtRefSel = _losTgtRow.ref;  // לחישוב ולשמירה
                var _losSecRow = L.DomUtil.create('div', '', losFieldsWrap);  // FR-D-290: גזרת המכ"ם לבדיקת המגבלות
                _losSecRow.style.cssText = 'display:flex;align-items:center;gap:3px;font-size:9px;color:#666;';  // שורה
                L.DomUtil.create('span', '', _losSecRow).textContent = 'גזרה°';  // תווית
                function _mkSecIn(v, tip) {{ var i = L.DomUtil.create('input', '', _losSecRow); i.type = 'number'; i.value = v; i.step = '1'; i.title = tip;
                    i.setAttribute('aria-label', tip); i.style.cssText = 'width:42px;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;'; return i; }}  // שדה
                _losStartInput = _mkSecIn(0, 'גזרה — אזימוט התחלה (°)'); L.DomUtil.create('span', '', _losSecRow).textContent = '–';
                _losEndInput = _mkSecIn(360, 'גזרה — אזימוט סיום (°). 0–360 = בלי הגבלת גזרה');
                _rsBuildSectorButton(_losSecRow, _losStartInput, _losEndInput, null);  // "📐 מהמכ"ם"

                // "עמדה" ל-LOS = רק גובהי צופה/יעד (אין מיקום קבוע לשמור — כל שימוש מתחיל בלחיצה חדשה)
                _buildStationUI(losFieldsWrap, 'los', {{obs_h: _losObsInput, tgt_h: _losTgtInput, tgt_unit: _losTgtUnitSel, tgt_ref: _losTgtRefSel,
                    start_bearing_deg: _losStartInput, end_bearing_deg: _losEndInput, ridge_margin_deg: _losMarginInput}}, null, null, null);  // FR-D-290: גם יחידות, ייחוס, גזרה ומרווח רכס

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
            var _prevRadialObs = radialLosObs;  // מיקום קודם (או null) — נשמר להיסטוריית Undo לפני הניקוי
            clearRadialLosResult();  // ניקוי תוצאה/תצוגה מקדימה קודמת — משקיף חדש בכל הפעלה
            radialLosObs = latlng;
            radialLosObsMk = L.marker(latlng, {{icon: _radialLosMarkerIcon(), draggable: true}}).addTo(map);
            radialLosObsMk.bindTooltip('תצפית רדיוס ראייה', {{permanent:false, direction:'top'}});
            radialLosObsMk.on('dragend', function() {{
                var _prevDrag = radialLosObs;  // מיקום לפני הגרירה — לצורך Undo
                radialLosObs = radialLosObsMk.getLatLng();
                _updateRadialLosPreview();  // רק מעדכן תצוגה מקדימה — לא מריץ חישוב אוטומטית
                _rsOnObserverMoved('radial', radialLosObs);  // FR-D-288: אם מחובר למכ"ם הפעיל — המכ"ם וכל הכלים זזים איתו
                if (!_isRestoringUndo) {{
                    _pushUndo('רדיוס ראייה: הזזת משקיף', _makeMarkerMoveRestore(
                        function(v) {{ radialLosObs = v; if (radialLosObsMk) radialLosObsMk.setLatLng(v); }},
                        function() {{ return radialLosObs; }},
                        _updateRadialLosPreview, _prevDrag));
                }}
            }});
            _updateRadialLosPreview();  // מציג תצוגה מקדימה מיידית (מהשדות הנוכחיים) — לא מפעיל חישוב
            _rsOnObserverMoved('radial', latlng);  // FR-D-288: אם מחובר למכ"ם הפעיל — המכ"ם וכל הכלים זזים איתו
            if (!_isRestoringUndo) {{
                _pushUndo('רדיוס ראייה: מיקום משקיף', _makePlacementRestore(
                    _placeRadialLosObserver, clearRadialLosResult,
                    function() {{ return radialLosObs; }}, _prevRadialObs));
            }}
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
            _rsSyncFrom(which === 'start' ? _radialStartInput : _radialEndInput); _rsSyncFrom(_radialRangeInput);  // FR-D-288: הסקטור והטווח נשמרים במכ"ם הפעיל ובשאר הכלים
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
            tgtH = _rsHeightM(tgtH, _radialTgtUnitSel ? _radialTgtUnitSel.value : 'm');  // FR-D-290: המרה למטרים (מ'/רגל/א"ר)
            var tgtRef = _radialTgtRefSel ? _radialTgtRefSel.value : 'agl';  // FR-D-290: AGL / MSL
            if (isNaN(marginDeg))  marginDeg = 0;
            if (isNaN(vCenter))    vCenter = 0;
            if (isNaN(vWidth))     vWidth = 4;
            radialLosLoading = true;
            _radialRunLbl = (_rs && _rs.detached.radial) ? 'צופה נפרד (לא לפי מכ"ם)' : _rtActiveLabel();  // FR-D-288: לפי איזה מכ"ם חושב — נלכד בתחילת החישוב
            _radialRunLbl += ' · גובה בחינה ' + _rsHeightText(_radialTgtInput, _radialTgtUnitSel, _radialTgtRefSel);  // FR-D-290: באיזה גובה נבדק
            document.title = '__radial_los_loading__';  // איתות ל-Python — שורת לוג
            if (radialLosInfoEl) radialLosInfoEl.textContent = 'מתחיל חישוב…';
            if (_radialCancelBtnEl) _radialCancelBtnEl.style.display = 'block';  // מציג את כפתור הביטול רק בזמן ריצה
            var url = 'http://localhost:5002/los_radial/start?lat=' + radialLosObs.lat + '&lon=' + radialLosObs.lng +
                      '&range_km=' + rangeKm + '&min_range_km=' + minRangeKm + '&angle_step_deg=' + stepDeg +
                      '&start_bearing_deg=' + startDeg + '&end_bearing_deg=' + endDeg +
                      '&obs_h=' + obsH + '&tgt_h=' + tgtH + '&tgt_ref=' + tgtRef + '&ridge_margin_deg=' + marginDeg +  // tgt_ref — FR-D-290
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

        var _radialRunLbl = '';  // FR-D-288: תווית המכ"ם שהיה פעיל בתחילת חישוב רדיוס הראייה האחרון

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
                    if (radialLosInfoEl) {{
                        radialLosInfoEl.textContent =
                            data.result.range_km + ' ק"מ, ' + data.result.n_bearings + ' כיוונים, ' +
                            data.result.clear_count + ' פנויים לגמרי' + '\\n📡 ' + _radialRunLbl;  // FR-D-288: לפי איזה מכ"ם (שורה נפרדת)
                        radialLosInfoEl.style.whiteSpace = 'pre-line';  // מכבד את מעבר השורה
                    }}
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

        var _radialLosLastResult = null;  // תוצאת החישוב האחרונה שצוירה — נשמרת כדי לאפשר Redo בלי קריאה חוזרת לשרת

        function _clearRadialLosResultOnly() {{
            // מנקה רק את ציור התוצאה (פוליגון+חישורים) בלי לגעת במשקיף עצמו — בשימוש ע"י Undo של "הפעל חישוב"
            if (radialLosPolygon) {{ map.removeLayer(radialLosPolygon); radialLosPolygon = null; }}
            radialLosSpokes.forEach(function(s) {{ map.removeLayer(s); }});
            radialLosSpokes = [];
            _radialLosLastResult = null;
            _updateRadialLosPreview();  // מחזיר את הידיות למיקומן לפי השדות הנוכחיים, לא לפי קצוות הקרניים האחרונות
        }}

        function _drawRadialLosPolygon(result) {{
            // מצייר את הפוליגון הסופי (מחושב, לא תצוגה מקדימה) + קו "חישור" צבעוני לכל כיוון —
            // ירוק = הגיע פנוי עד הטווח המלא (blocked=false), אדום = נחסם לפני כן (blocked=true).
            // אותם צבעים בדיוק כמו קו-הראייה הרגיל (_drawLosOnMap) — עקביות חזותית בין שני הכלים.
            // מזיז גם את ידיות הגרירה לקצוות הקשת האמיתיים, כדי שאפשר להמשיך לכוון ולהריץ שוב.
            var _prevRadialLosResult = _radialLosLastResult;  // תוצאה קודמת (או null) — נשמרת להיסטוריית Undo
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
            _radialLosLastResult = result;  // שמירת התוצאה הנוכחית — משמשת גם ל-Redo וגם כ"ערך קודם" בהרצה הבאה
            if (!_isRestoringUndo) {{
                _pushUndo('רדיוס ראייה: הפעלת חישוב', _makePlacementRestore(
                    _drawRadialLosPolygon, _clearRadialLosResultOnly,
                    function() {{ return _radialLosLastResult; }}, _prevRadialLosResult));
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
            _radialLosLastResult = null;  // אין יותר תוצאה מצוירת — מונע היסטוריית Undo "רפאים" מתוצאה שכבר לא קיימת
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
            }} else {{
                _rsOnToolOpened('radial');  // FR-D-288: מחובר למכ"ם הפעיל — המשקיף מוצב מיד במיקום המכ"ם
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
                btn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
                btn.setAttribute('aria-label', 'כלי רדיוס ראייה רדיאלי');
                _radialLosBtnEl = btn;
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;  // הגנה נוספת מעבר ל-pointer-events — המפה/שרתים לא מוכנים
                    toggleRadialLos();
                }});

                // גוף הפאנל (שדות+כפתורים) — מוסתר כברירת מחדל, נחשף רק אחרי בחירת הכלי (toggleRadialLos)
                // כדי שהמפה לא תהיה עמוסה בשדות לפני שהמשתמש בכלל בחר להשתמש בכלי הזה.
                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;overflow-y:auto;';  // overflow — נוסף בתיקון התאמת הגובה (26/11/2026)
                _radialPanelBodyEl = panelBody;
                _fitPanelEls.push(panelBody);  // הגובה המרבי מותאם למקום שנשאר מתחת לפאנל
                _rtBuildActiveBar(panelBody, {{detach: 'radial', notes: false}});  // FR-D-288: פס המכ"ם הפעיל + "צופה נפרד"

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
                    _attachFieldUndo(inp, 'רדיוס ראייה: ' + labelText, _updateRadialLosPreview);  // רישום Undo בעת יציאה מהשדה (blur) — לא בכל הקשה
                    return inp;
                }}
                _radialRangeInput    = _mkField('טווח (ק"מ, עד 300)',  5,   0.5, 0.5, 300, 'מרחק מרבי לבדיקת ראייה');
                _radialMinRangeInput = _mkField('טווח מינימלי (ק"מ)',  5,   0.5, 0,   300, 'אזור עיוור קרוב למשקיף שלא נבדק כלל');
                _radialStepInput     = _mkField('צעד זווית (°)',       10,  1,   3,   45,  'רווח בין כיוונים — קובע כמה קודקודים בפוליגון');
                _radialStartInput    = _mkField('אזימוט התחלה (°)',    315, 1,   0,   360, 'ניתן לגרור גם על המפה');
                _radialEndInput      = _mkField('אזימוט סיום (°)',     45,  1,   0,   360, 'ניתן לגרור גם על המפה');
                _radialObsInput      = _mkField('גובה צופה (מ\\')',     11,  1,   0,   500, 'גובה המשקיף מעל הקרקע');
                _radialTgtInput      = _mkField('גובה בחינה',           0,  1,   0,   100000, 'גובה המטרה הנבדק לאורך כל קרן — ביחידות ובייחוס שנבחרו בשורה מתחת (FR-D-290)');
                var _radialTgtRow = _rsBuildHeightRow(panelBody, function() {{ _updateRadialLosPreview(); }});  // FR-D-290: יחידות (מ'/רגל/א"ר) + ייחוס (AGL/MSL)
                _radialTgtUnitSel = _radialTgtRow.unit; _radialTgtRefSel = _radialTgtRow.ref;  // לחישוב ולשמירה
                _rsBuildSectorButton(panelBody, _radialStartInput, _radialEndInput, _updateRadialLosPreview);  // FR-D-290: "📐 גזרה מהמכ"ם"
                _radialMarginInput   = _mkField('מרווח רכס (°)',        0,  0.5, 0,   10,  'שולי ביטחון מעל הרכס הגבוה ביותר שנצפה');
                _radialVCenterInput  = _mkField('מרכז אלומה אנכי (°)',  0,  0.5, -45, 45,  'זווית עילוי/הטיה מרכזית (0=אופקי) — שדה-ראייה של "מכ"ם" רעיוני, לא כלי אמיתי');
                _radialVWidthInput   = _mkField('רוחב אלומה אנכי (°)',  4,  0.5, 1,   90,  'רוחב שדה-הראייה האנכי הכולל סביב המרכז — מוגבל בכוונה, לא כל טווח הגובה נבדק');

                // מקור-אמת יחיד למפת השדות — משמש גם ל"עמדות שמורות" (עם מיקום) וגם ל"הגדרות שמורות" (בלעדיו) מיד למטה
                var _radialFieldMap = {{
                    range_km: _radialRangeInput, min_range_km: _radialMinRangeInput, angle_step_deg: _radialStepInput,
                    start_bearing_deg: _radialStartInput, end_bearing_deg: _radialEndInput,
                    obs_h: _radialObsInput, tgt_h: _radialTgtInput, ridge_margin_deg: _radialMarginInput,
                    vertical_center_deg: _radialVCenterInput, vertical_width_deg: _radialVWidthInput,
                    tgt_unit: _radialTgtUnitSel, tgt_ref: _radialTgtRefSel,  // FR-D-290: יחידות וייחוס גובה הבחינה
                }};
                _buildStationUI(panelBody, 'radial_los', _radialFieldMap,
                    function() {{ return radialLosObs; }}, _placeRadialLosObserver, _updateRadialLosPreview,
                    'עמדות שמורות (מיקום+הגדרות):');
                // בלוק שני — "הגדרות שמורות" בלי מיקום: getObsFn/placeObsFn null כדי ש-lat/lon לעולם לא יישמרו/יוחלו
                _buildStationUI(panelBody, 'radial_los_settings', _radialFieldMap,
                    null, null, _updateRadialLosPreview,
                    'הגדרות שמורות (ללא מיקום):');

                var runBtn = L.DomUtil.create('button', '', panelBody);
                runBtn.textContent = 'הפעל חישוב';
                runBtn.setAttribute('aria-label', 'הפעל חישוב רדיוס ראייה רדיאלי');  // נגישות — מבדיל מכפתורי "הפעל חישוב" של כלים אחרים (F-027, Q-1)
                runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
                L.DomEvent.on(runBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runRadialLos(); }});

                var cancelBtn = L.DomUtil.create('button', '', panelBody);
                cancelBtn.textContent = 'בטל';
                cancelBtn.setAttribute('aria-label', 'בטל חישוב רדיוס ראייה רדיאלי');  // נגישות (F-027, Q-1)
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
            var _prevRadarObs = radarObs;  // מיקום קודם (או null) — נשמר להיסטוריית Undo לפני הניקוי
            clearRadarDopplerResult();  // ניקוי תוצאה/תצוגה מקדימה קודמת — משקיף חדש בכל הפעלה
            radarObs = latlng;
            radarObsMk = L.marker(latlng, {{icon: _radarMarkerIcon(), draggable: true}}).addTo(map);
            radarObsMk.bindTooltip('תצפית מכ"ם דופלר', {{permanent:false, direction:'top'}});
            radarObsMk.on('dragend', function() {{
                var _prevDrag = radarObs;  // מיקום לפני הגרירה — לצורך Undo
                radarObs = radarObsMk.getLatLng();
                _updateRadarDopplerPreview();  // רק מעדכן תצוגה מקדימה — לא מריץ חישוב אוטומטית
                _radarTrackOnRadarMoved();  // בדיקת מעקב מכ"ם (אם מוצגת) רצה מחדש מהמיקום החדש — FR-D-261 שלב א1
                _rsOnObserverMoved('radar', radarObs);  // FR-D-288: מיקום המכ"ם הפעיל מתעדכן, ושאר הכלים זזים איתו
                if (!_isRestoringUndo) {{
                    _pushUndo('מכ"ם דופלר: הזזת משקיף', _makeMarkerMoveRestore(
                        function(v) {{ radarObs = v; if (radarObsMk) radarObsMk.setLatLng(v); }},
                        function() {{ return radarObs; }},
                        _updateRadarDopplerPreview, _prevDrag));
                }}
            }});
            _updateRadarDopplerPreview();  // מציג תצוגה מקדימה מיידית (מהשדות הנוכחיים) — לא מפעיל חישוב
            _radarTrackOnRadarMoved();  // מכ"ם הוצב מחדש — בדיקת מעקב מכ"ם (אם מוצגת) רצה מחדש מהמיקום החדש
            _rsOnObserverMoved('radar', latlng);  // FR-D-288: מיקום המכ"ם הפעיל מתעדכן, ושאר הכלים זזים איתו
            if (!_isRestoringUndo) {{
                _pushUndo('מכ"ם דופלר: מיקום משקיף', _makePlacementRestore(
                    _placeRadarObserver, clearRadarDopplerResult,
                    function() {{ return radarObs; }}, _prevRadarObs));
            }}
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
            _rsSyncFrom(which === 'start' ? _radarStartInput : _radarEndInput); _rsSyncFrom(_radarRangeInput);  // FR-D-288: הסקטור והטווח נשמרים במכ"ם הפעיל ובשאר הכלים
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
            var rcsM2      = num(_radarRcsInput, 2);
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
            _radarRunProfileLbl = _rtActiveLabel();  // FR-D-286: הפרופיל שהיה פעיל בתחילת החישוב — לשורת התוצאה
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
                var jobKind = _radarJobKind;  // נשמר לפני האיפוס — קובע איזו תוצאה זו ואיך לצייר אותה
                _radarJobKind = null;
                if (data.status === 'done') {{
                    document.title = '__radar_doppler_loaded__';
                    if (jobKind === 'route_eval') {{
                        _drawRouteEvaluation(data.result);
                        if (radarInfoEl) {{
                            var c = data.result.counts;
                            // מציג גם את ה-RCS שנגזר אוטומטית מסוג כלי-הטיס — שקיפות: המשתמש לא הזין אותו ידנית
                            radarInfoEl.textContent = c.detected + ' מזוהות, ' + c.doppler_blind + ' עיוורות-דופלר, ' +
                                c.blocked + ' חסומות, ' + c.out_of_range + ' מחוץ-לטווח (מתוך ' + data.result.points_total + ') — ' +
                                'RCS משוער: ' + _routeEvalRcsUsed + ' מ"ר (' + (_lastFlightRouteData.aircraft || '?') + ')' +
                                '\\n📡 ' + _radarRunProfileLbl;  // FR-D-286: לפי איזה פרופיל (שורה נפרדת)
                            radarInfoEl.style.whiteSpace = 'pre-line';  // FR-D-286: מכבד את מעבר השורה
                        }}
                    }} else {{
                        _drawRadarDopplerResult(data.result);
                        if (radarInfoEl) {{
                            radarInfoEl.textContent =
                                data.result.range_km + ' ק"מ, ' + data.result.n_bearings + ' כיוונים, ' +
                                data.result.clear_count + ' מזוהים לגמרי, ' + data.result.doppler_blocked_rays + ' חסומי-דופלר' +
                                '\\n📡 ' + _radarRunProfileLbl;  // FR-D-286: לפי איזה פרופיל (שורה נפרדת)
                            radarInfoEl.style.whiteSpace = 'pre-line';  // FR-D-286: מכבד את מעבר השורה
                        }}
                    }}
                }} else if (data.status === 'error') {{
                    document.title = '__radar_doppler_error__';
                    if (radarInfoEl) radarInfoEl.textContent = '';
                    alert('שגיאה ב' + (jobKind === 'route_eval' ? 'הערכת מסלול טיסה' : 'חישוב תצפית מכ"ם דופלר') +
                          ': ' + (data.error || 'לא ידועה'));
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

        // מיפוי גס (חינוכי בלבד, לא נתון הנדסי מדויק) מקידומת קוד ICAO של כלי-הטיס ל-RCS משוער, מ"ר —
        // FR24 לא מספק RCS בעצמו (זה לא שדה שמשודר ע"י מטוסים בכלל), רק את סוג כלי-הטיס — לכן
        // מסווגים גס לפי גודל פיזי כללי. כל רשומה: [רשימת קידומות קוד-ICAO, RCS משוער]. נבדק לפי
        // "מתחיל ב-" (לא שוויון מדויק) כדי לכסות משפחות שלמות (B77W/B772/B77L וכו') בקידומת אחת.
        var _AIRCRAFT_RCS_TABLE = [
            [['B74', 'A38'], 150],                                          // ג'מבו/ענק (747, A380)
            [['B77', 'B78', 'A33', 'A34', 'A35', 'MD1', 'DC1'], 80],        // רחב-גוף (777/787/A330/A340/A350)
            [['B73', 'B75', 'B76', 'A31', 'A32', 'MD8', 'MD9'], 30],        // צר-גוף (737/757/767/A320)
            [['CRJ', 'E17', 'E19', 'E29', 'SU9', 'AT4', 'AT7', 'DH8', 'F70'], 8],  // אזורי (סילון/טורבו-פרופ)
            [['C1', 'C2', 'C5', 'PA', 'SR2', 'BE', 'DA4'], 1.5],            // מטוס קל פרטי
        ];
        var _AIRCRAFT_RCS_DEFAULT = 30;  // ברירת מחדל לסוג לא-מזוהה — "מטוס נוסעים ממוצע" (צר-גוף)

        function _rcsForAircraftType(icaoCode) {{
            if (!icaoCode) return _AIRCRAFT_RCS_DEFAULT;
            var code = String(icaoCode).toUpperCase();
            for (var i = 0; i < _AIRCRAFT_RCS_TABLE.length; i++) {{
                var prefixes = _AIRCRAFT_RCS_TABLE[i][0];
                for (var j = 0; j < prefixes.length; j++) {{
                    if (code.indexOf(prefixes[j]) === 0) return _AIRCRAFT_RCS_TABLE[i][1];
                }}
            }}
            return _AIRCRAFT_RCS_DEFAULT;
        }}

        function _runRouteEvaluation() {{
            // מפעיל הערכת מסלול טיסה מלא (FR24) מול תצורת המכ"ם הנוכחית — דורש גם משקיף מוצב
            // וגם מסלול טיסה טעון; משתמש באותם radarLoading/radarJobId/radarPollTimer של הסריקה
            // הרגילה (שני סוגי החישוב לא יכולים לרוץ בו-זמנית) — _radarJobKind מבדיל ביניהם בסיום.
            if (!radarObs) {{ alert('יש להציב תחילה משקיף מכ"ם על המפה'); return; }}
            if (!_lastFlightRouteData || !_lastFlightRouteData.trail || !_lastFlightRouteData.trail.length) {{
                alert('יש לחפש תחילה מסלול טיסה (FR24)'); return;
            }}
            if (radarLoading) return;  // חישוב אחר (סריקה או הערכת מסלול) כבר רץ
            function num(el, def) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? def : v; }}
            // RCS נגזר אוטומטית מסוג כלי-הטיס בפועל (FR24) — לא משדה הקלט הידני, שרלוונטי רק לסריקה
            // הרגילה (שם אין מטרה אמיתית לגזור ממנה). מוצג גם ב-radarInfoEl בסיום, לשקיפות.
            var _rcsUsed = _rcsForAircraftType(_lastFlightRouteData.aircraft_icao);
            _routeEvalRcsUsed = _rcsUsed;  // נשמר גלובלית — נצרך ב-_pollRadarDopplerStatus בסיום (פונקציה אחרת, אסינכרונית)
            var body = {{
                lat: radarObs.lat, lon: radarObs.lng,
                range_km: num(_radarRangeInput, 50), min_range_km: num(_radarMinRangeInput, 1),
                h_antenna: num(_radarHAntInput, 15), ridge_margin_deg: num(_radarMarginInput, 0),
                vertical_center_deg: num(_radarVCenterInput, 0), vertical_width_deg: num(_radarVWidthInput, 10),
                power_kw: num(_radarPowerInput, 100), gain_dbi: num(_radarGainInput, 30),
                freq_mhz: (_radarFreqSelect ? parseFloat(_radarFreqSelect.value) : 3000),
                sensitivity_dbm: num(_radarSensInput, -100), rcs_m2: _rcsUsed,
                prf_hz: num(_radarPrfInput, 1000), mdv_kt: num(_radarMdvInput, 20),
                lobing_enabled: !!(_radarLobingCheck && _radarLobingCheck.checked),
                reflectivity: (_radarReflSelect ? _radarReflSelect.value : 'land'),
                antenna_type: (_radarAntennaSelect ? _radarAntennaSelect.value : 'generic'),
                boresight_deg: num(_radarBoresightInput, 0), max_scan_deg: num(_radarMaxScanInput, 60),
                // מסנן נקודות חסרות-קואורדינטות — אותו סינון בדיוק כמו drawFlightRoute עבור path
                trail: _lastFlightRouteData.trail.filter(function(p) {{ return p.lat != null && p.lng != null; }}),
            }};
            radarLoading = true;
            _radarJobKind = 'route_eval';
            document.title = '__radar_doppler_loading__';  // איתות ל-Python — שורת לוג, אותו איתות כמו סריקה רגילה
            _radarRunProfileLbl = _rtActiveLabel();  // FR-D-286: הפרופיל שהיה פעיל בתחילת ההערכה
            if (radarInfoEl) radarInfoEl.textContent = 'מעריך מסלול טיסה מול המכ"ם…';
            if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'block';
            fetch('http://localhost:5002/radar_doppler/evaluate_route/start', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(body)
            }})
            .then(function(r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
            .then(function(data) {{
                if (data.error) throw new Error(data.error);
                radarJobId = data.job_id;
                radarPollTimer = setInterval(_pollRadarDopplerStatus, 1000);  // אותו polling בדיוק כמו סריקה רגילה
            }})
            .catch(function(err) {{
                radarLoading = false;
                _radarJobKind = null;
                document.title = '__radar_doppler_error__';
                if (radarInfoEl) radarInfoEl.textContent = '';
                if (_radarCancelBtnEl) _radarCancelBtnEl.style.display = 'none';
                alert('שגיאה בהערכת מסלול טיסה: ' + err.message);
            }});
        }}

        function _drawRouteEvaluation(result) {{
            // מצייר את המסלול כסדרת קטעים צבעוניים (במקום flightPolyline החד-צבעי הרגיל) —
            // צבע כל קטע נקבע לפי סטטוס הנקודה בקצהו (לא ממוצע/אינטרפולציה בין שתי הנקודות)
            _clearRouteEvaluation();  // מנקה הערכה קודמת, אם הייתה
            var pts = result.points;
            if (!pts || pts.length === 0) {{
                alert('לא התקבלו נתוני הערכה עבור מסלול הטיסה'); return;
            }}
            var statusColor = {{  // אותם צבעים בדיוק כמו הסריקה הרגילה (ירוק/כתום/אדום), ועוד אפור למחוץ-לטווח
                detected: '#00cc44', doppler_blind: '#ff9500', blocked: '#ff3300', out_of_range: '#6c7086'
            }};
            var reasonText = {{
                ok: 'מזוהה', terrain: 'חסום ע"י שטח', radar_range: 'מעבר לטווח המכ"ם (משוואת מכ"ם/ריבוד)',
                doppler: 'עיוור לדופלר', out_of_range: 'מחוץ לטווח המכ"ם כלל', no_elevation_data: 'נתוני גובה חסרים לנקודה זו'
            }};
            function popupFor(p) {{
                return '<div style="direction:rtl;font-family:Arial;font-size:12px;min-width:150px;">' +
                    '<div style="font-weight:bold;margin-bottom:3px;">' + (reasonText[p.reason] || p.status) + '</div>' +
                    '<div>מרחק מהמשקיף: ' + p.dist_km + ' ק"מ</div>' +
                    (p.alt_ft != null ? '<div>גובה: ' + Math.round(p.alt_ft) + ' ft</div>' : '') +
                    (p.spd_kt != null ? '<div>מהירות: ' + Math.round(p.spd_kt) + ' kt</div>' : '') +
                    '</div>';
            }}
            if (pts.length === 1) {{
                // נקודה בודדת בלבד (למשל טיסה חיה בלי היסטוריית מסלול עדיין) — אין מה לצייר כקו,
                // מציג סמן עגול צבעוני יחיד במקום להיכשל בשקט כמו קודם (pts.length<2 היה פשוט מדלג על הכל)
                var p0 = pts[0];
                var color0 = statusColor[p0.status] || '#6c7086';
                var mk = L.circleMarker([p0.lat, p0.lng], {{radius: 9, color: '#fff', weight: 2, fillColor: color0, fillOpacity: 0.95}}).addTo(map);
                mk.bindPopup(popupFor(p0)).openPopup();  // פתיחה מיידית — עם קטע יחיד המשתמש עלול לא לשים לב אחרת
                _routeEvalLayers.push(mk);
            }} else {{
                for (var i = 1; i < pts.length; i++) {{
                    var p0 = pts[i - 1], p1 = pts[i];
                    var color = statusColor[p1.status] || '#6c7086';
                    var seg = L.polyline([[p0.lat, p0.lng], [p1.lat, p1.lng]], {{color: color, weight: 4, opacity: 0.9}}).addTo(map);
                    seg.bindPopup(popupFor(p1));
                    _routeEvalLayers.push(seg);
                }}
            }}
            if (flightPolyline && map.hasLayer(flightPolyline)) {{ map.removeLayer(flightPolyline); }}  // מסתיר את הקו הרגיל — לא מוחק אותו, רק חבוי מאחורי ההערכה
        }}

        function _clearRouteEvaluation() {{
            // מסיר את קטעי ההערכה הצבעוניים ומחזיר את flightPolyline הרגיל לתצוגה, אם קיים —
            // נקרא גם מ-clearFlightRoute (מסלול חדש/ניקוי) וגם לפני ציור הערכה חדשה
            _routeEvalLayers.forEach(function(l) {{ map.removeLayer(l); }});
            _routeEvalLayers = [];
            if (flightPolyline && !map.hasLayer(flightPolyline)) {{ flightPolyline.addTo(map); }}
        }}

        // ══════════════════════════════════════════════════════════════════
        // ── כלי שביעי: בדיקת מעקב מכ"ם אחרי מסלול בליסטי (SRS FR-D-259.., שלב א1) ──
        // משתמש במכ"ם שהוצב בכלי הדופלר (🎯) ובכל הפרמטרים שלו, ובמסלול הבליסטי האחרון שחושב
        // (ballisticsLastPath — מסלול בודד או פתרון ירי). החישוב בשרת (/radar_track/start), ה-polling
        // דרך /radar_doppler/status הקיים. job נפרד מזה של כלי הדופלר — שני הכלים לא מפריעים זה לזה.
        // ══════════════════════════════════════════════════════════════════
        var _radarTrackLayers    = [];    // קטעי המסלול הצבועים לפי סטטוס
        var _radarTrackLastPath  = null;  // המסלול שנבדק לאחרונה — לחישוב מחדש בגרירת המכ"ם
        var _radarTrackInfoEl    = null;  // אלמנט הסיכום בפאנל (נקבע ע"י מי שהפעיל את הבדיקה)
        var _radarTrackJobId     = null;  // ה-job הפעיל בשרת (null = אין)
        var _radarTrackPollTimer = null;  // טיימר ה-polling
        var _radarTrackTimelineEl = null; // ה-canvas של ציר הזמן (שלב א2)
        var _rtScanInputs = {{}};          // שדות הגדרות הסריקה והמעקב בטאב הבליסטי (שלב א2) — שם -> אלמנט
        var _rtViewEls = {{}};             // שלב א3: מתג המניפה, גרף הצד, פרופיל השטח וכותרתו (נקבעים בבניית הטאב)
        var _radarTrackFanLayers = [];    // קווי ה-LOS של המניפה
        var _radarTrackLastResult = null; // התוצאה האחרונה — למניפה, לגרף הצד ולייצוא
        var _radarTrackLastOpts = null;   // שלב א4: מקור המסלול שנבדק לאחרונה ({{source, alt_ref, rcs_m2, label}})
        var _radarTrackProfileLbl = '';   // FR-D-286: תווית הפרופיל שהיה פעיל כשהבדיקה האחרונה התחילה
        var _radarRunProfileLbl = '';     // FR-D-286: אותו דבר לכיסוי הדופלר ולהערכת מסלול הטיסה (פאנל המכ"ם)
        function _escapeHtmlRt(s) {{
            // FR-D-286: מנטרל HTML בשם פרופיל לפני הכנסה לפופאפ — שם של "הפרופילים שלי" הוא טקסט חופשי של המשתמש
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');  // התווים המסוכנים
        }}
        var _RT_R_EARTH = 6371000.0, _RT_K = 0.13;  // רדיוס כדור הארץ ומקדם הרפרקציה — זהים למנוע (radar_track.py)
        function _rtDrop(d) {{ return d * d / (2 * _RT_R_EARTH) * (1 - _RT_K); }}  // ירידת קו הראייה בגלל עקמומיות+רפרקציה

        function _radarTrackDrawFan(res) {{
            // מניפת LOS: קו מהמכ"ם לכל נקודה (מדולל עד ~60 קווים), בצבע המצב; לחיצה פותחת פרופיל שטח
            _radarTrackFanLayers.forEach(function(l) {{ map.removeLayer(l); }});  // ניקוי מניפה קודמת
            _radarTrackFanLayers = [];  // איפוס
            if (!res || !_rtViewEls.fan || !_rtViewEls.fan.checked) return;  // אין תוצאה, או שהמתג כבוי
            var pts = res.points, step = Math.max(1, Math.ceil(pts.length / 60));  // דילול — מפה קריאה
            for (var i = 0; i < pts.length; i += step) {{  // כל נקודה n-ית
                (function(p) {{  // סגירה — p קבוע לכל קו
                    var ln = L.polyline([[res.radar.lat, res.radar.lon], [p.lat, p.lon]],
                        {{color: _RADAR_TRACK_COLORS[p.track_state || p.status] || '#6c7086', weight: 1, opacity: 0.45}}).addTo(map);  // קו דק ושקוף
                    ln.bindTooltip('שנ\\' ' + p.t + ' — לחץ לפרופיל שטח', {{sticky: true}});  // רמז
                    ln.on('click', function() {{ _radarTrackShowProfile(p); }});  // פרופיל
                    _radarTrackFanLayers.push(ln);  // לניקוי
                }})(pts[i]);
            }}
        }}

        function _radarTrackDrawSide(canvas, res) {{
            // גרף צד: מרחק קרקעי מהמכ"ם (ציר אופקי, מימין לשמאל) מול גובה מעל פני הים. מצייר את גובה השטח
            // החוסם בכיוון של כל נקודה (אפור), את גבולות שדה-הראייה האנכי (תכלת מקווקו), את תקרת המכ"ם
            // (סגול מקווקו), את המכ"ם עצמו ואת נקודות המסלול בצבע המצב — רואים במבט אחד היכן המסלול יוצא מהכיסוי
            if (!canvas || !res) return;  // אין מה לצייר
            canvas.style.display = 'block';  // מציגים
            var W = 250, H = 120, dpr = window.devicePixelRatio || 1;  // מידות
            canvas.width = W * dpr; canvas.height = H * dpr;  // רזולוציה
            var ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);  // הכנה
            var pts = res.points, Hm = res.radar.h_msl, beam = res.beam;  // נתונים
            var dmax = 0, amax = Hm, amin = Hm;  // טווחי הצירים
            pts.forEach(function(p) {{ dmax = Math.max(dmax, p.dist_km * 1000); amax = Math.max(amax, p.alt); amin = Math.min(amin, p.alt); }});  // מהמסלול
            dmax = Math.max(1000, dmax * 1.08); amax = amax + (amax - amin) * 0.1 + 50; amin = Math.max(-100, amin - (amax - amin) * 0.05 - 50);  // שוליים
            var L0 = 30, R0 = W - 6, T0 = 6, B0 = H - 16;  // שולי האזור המצויר (משאירים מקום לתוויות)
            function X(d) {{ return R0 - d / dmax * (R0 - L0); }}  // מרחק -> פיקסל (0 בימין)
            function Y(a) {{ return B0 - (a - amin) / (amax - amin) * (B0 - T0); }}  // גובה -> פיקסל
            ctx.save(); ctx.beginPath(); ctx.rect(L0, T0, R0 - L0, B0 - T0); ctx.clip();  // ציור רק בתוך האזור
            pts.forEach(function(p) {{  // גובה השטח החוסם בכיוון של כל נקודה
                if (p.horizon_deg == null) return;  // אין נתון (מחוץ לטווח וכו')
                var d = p.dist_km * 1000, hm = Hm + d * Math.tan(p.horizon_deg * Math.PI / 180) + _rtDrop(d);  // גובה קו האופק במרחק הנקודה
                ctx.fillStyle = 'rgba(120,100,80,0.35)'; ctx.fillRect(X(d) - 1, Y(hm), 2, B0 - Y(hm));  // עמודה חומה
            }});
            ctx.setLineDash([3, 3]);  // קווים מקווקווים לאזור הכיסוי
            [beam.v_lo_deg, beam.v_hi_deg].forEach(function(e) {{  // שני גבולות שדה הראייה
                ctx.strokeStyle = '#22d3ee'; ctx.beginPath();  // תכלת
                for (var k = 0; k <= 40; k++) {{  // לאורך המרחק
                    var d = dmax * k / 40, a = Hm + d * Math.tan(Math.max(-89, Math.min(89, e)) * Math.PI / 180) + _rtDrop(d);  // גובה הקרן
                    if (k === 0) ctx.moveTo(X(d), Y(a)); else ctx.lineTo(X(d), Y(a));  // קו
                }}
                ctx.stroke();  // ציור
            }});
            var C = beam.ceiling_km * 1000;  // תקרת המכ"ם
            ctx.strokeStyle = '#a855f7'; ctx.beginPath();  // סגול
            for (var k = 0; k <= 40; k++) {{  // קשת התקרה בין שני גבולות שדה הראייה
                var e = (beam.v_lo_deg + (beam.v_hi_deg - beam.v_lo_deg) * k / 40) * Math.PI / 180;  // זווית
                var d = C * Math.cos(e), a = Hm + C * Math.sin(e) + _rtDrop(d);  // נקודה על הקשת
                if (k === 0) ctx.moveTo(X(d), Y(a)); else ctx.lineTo(X(d), Y(a));  // קו
            }}
            ctx.stroke(); ctx.setLineDash([]);  // ציור, וחזרה לקו רציף
            pts.forEach(function(p) {{  // נקודות המסלול
                ctx.fillStyle = _RADAR_TRACK_COLORS[p.track_state || p.status] || '#6c7086';  // צבע המצב
                ctx.fillRect(X(p.dist_km * 1000) - 1, Y(p.alt) - 1, 3, 3);  // נקודה
            }});
            ctx.restore();  // סוף החיתוך
            ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(X(0), Y(Hm), 3, 0, 2 * Math.PI); ctx.fill();  // המכ"ם
            ctx.fillStyle = '#333'; ctx.font = '9px Arial';  // תוויות
            ctx.textAlign = 'right'; ctx.fillText('0', R0, H - 4);  // מרחק אפס (ימין)
            ctx.textAlign = 'left'; ctx.fillText((dmax / 1000).toFixed(1) + ' ק"מ', L0, H - 4);  // המרחק המרבי (שמאל)
            ctx.textAlign = 'right'; ctx.fillText(Math.round(amax) + ' מ\\'', L0 - 2, T0 + 8); ctx.fillText(Math.round(amin) + ' מ\\'', L0 - 2, B0);  // גבהים
        }}

        function _radarTrackShowProfile(p) {{
            // פרופיל שטח בין המכ"ם לנקודה שנלחצה: שטח "אפקטיבי" (גובה פחות ירידת העקמומיות), קו הראייה
            // (ירוק = פנוי, אדום = חסום) וסימון המקום שבו הוא נחסם — מסביר לעין למה נקודה חסומה
            var res = _radarTrackLastResult, els = _rtViewEls;  // התוצאה והאלמנטים
            if (!res || !els.profile) return;  // אין תוצאה או שהטאב לא נבנה
            els.profInfo.textContent = 'פרופיל שטח לשנ\\' ' + p.t + '…';  // משוב מיידי
            var body = Object.assign(_radarCommonBody(), {{lat: res.radar.lat, lon: res.radar.lon, point: {{lat: p.lat, lon: p.lon, alt: p.alt}}}});  // הבקשה
            fetch('http://localhost:5002/radar_track/profile', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(body)}})
            .then(function(r) {{ return r.json().then(function(d) {{ if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }}); }})  // שגיאה עם הסבר
            .then(function(pr) {{
                els.profInfo.textContent = 'LOS לשנ\\' ' + p.t + ' (' + (pr.dist_m / 1000).toFixed(2) + ' ק"מ): ' +
                    (pr.visible ? 'פנוי ✔' : 'חסום ע"י שטח ב-' + (pr.block_dist_m / 1000).toFixed(2) + ' ק"מ ✖');  // כותרת
                var c = els.profile; c.style.display = 'block';  // מציגים
                var W = 250, H = 90, dpr = window.devicePixelRatio || 1;  // מידות
                c.width = W * dpr; c.height = H * dpr;  // רזולוציה
                var ctx = c.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);  // הכנה
                var eff = pr.elevs.map(function(e, i) {{ return e == null ? null : e - pr.drops[i]; }});  // שטח אפקטיבי
                var tgtEff = pr.target_alt - _rtDrop(pr.dist_m);  // הנקודה, באותה מערכת
                var vals = eff.filter(function(v) {{ return v != null; }}).concat([pr.radar_h_msl, tgtEff]);  // כל הערכים
                var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.1 + 10;  // טווח הציר האנכי
                lo -= pad; hi += pad;  // שוליים
                function X(d) {{ return W - 4 - d / pr.dist_m * (W - 8); }}  // מרחק -> פיקסל (המכ"ם מימין)
                function Y(a) {{ return H - 4 - (a - lo) / (hi - lo) * (H - 8); }}  // גובה -> פיקסל
                ctx.fillStyle = '#c8b28a'; ctx.beginPath(); ctx.moveTo(X(0), H);  // שטח חום
                pr.dists.forEach(function(d, i) {{ if (eff[i] != null) ctx.lineTo(X(d), Y(eff[i])); }});  // פני השטח
                ctx.lineTo(X(pr.dist_m), H); ctx.closePath(); ctx.fill();  // סגירה
                ctx.strokeStyle = pr.visible ? '#00cc44' : '#ff3300'; ctx.lineWidth = 2;  // צבע קו הראייה
                ctx.beginPath(); ctx.moveTo(X(0), Y(pr.radar_h_msl)); ctx.lineTo(X(pr.dist_m), Y(tgtEff)); ctx.stroke();  // קו הראייה
                if (pr.block_dist_m != null) {{  // נקודת החסימה
                    ctx.fillStyle = '#ff3300'; ctx.beginPath(); ctx.arc(X(pr.block_dist_m), Y(pr.radar_h_msl + (tgtEff - pr.radar_h_msl) * pr.block_dist_m / pr.dist_m), 3, 0, 2 * Math.PI); ctx.fill();  // עיגול אדום
                }}
                ctx.lineWidth = 1;  // חזרה לעובי רגיל
            }})
            .catch(function(e) {{ els.profInfo.textContent = 'פרופיל: ' + e.message; }});  // שגיאה
        }}

        function _radarTrackExportCsv() {{
            // ייצוא שורה לכל נקודה — אותו מנגנון כמו טבלת הירי (Blob + הורדה); בדסקטופ main.py שואל היכן לשמור
            var res = _radarTrackLastResult;  // התוצאה האחרונה
            if (!res) {{ alert('הרץ קודם בדיקת מעקב מכ"ם'); return; }}  // אין מה לייצא
            var cols = ['t', 'lat', 'lon', 'alt', 'dist_km', 'slant_km', 'bearing_deg', 'elev_deg', 'horizon_deg',
                        'radial_ms', 'speed_ms', 'ceiling_km', 'ang_rate_dps', 'aspect_deg', 'rcs_m2', 'rain_db',
                        'status', 'reason', 'track_state'];  // העמודות (aspect/rcs/rain — שלב א5)
            var prof = '"' + String(_radarTrackProfileLbl || '').replace(/"/g, '""') + '"';  // FR-D-286: עמודת הפרופיל — במירכאות, כי השם עלול לכלול פסיק
            var rows = res.points.map(function(p) {{ return cols.map(function(c) {{ return p[c] != null ? p[c] : ''; }}).concat([prof]).join(','); }});  // שורה לכל נקודה + הפרופיל
            var csv = '\\ufeff' + cols.concat(['profile']).join(',') + '\\n' + rows.join('\\n');  // BOM — כדי ש-Excel יזהה UTF-8
            var blob = new Blob([csv], {{type: 'text/csv;charset=utf-8'}});  // הקובץ
            var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'radar_track.csv';  // קישור הורדה
            document.body.appendChild(a); a.click(); document.body.removeChild(a);  // הפעלה וניקוי
        }}
        var _RADAR_TRACK_COLORS = {{  // אותם צבעים כמו הערכת המסלול הקיימת, לעקביות חזותית, ועוד מצבי המעקב
            detected: '#00cc44', doppler_blind: '#ff9500', blocked: '#ff3300', out_of_range: '#6c7086',
            tracked: '#00cc44', coasting: '#86efac', detected_untracked: '#3b82f6'  // במעקב / דעיכה / גילוי בלי מעקב
        }};
        var _RADAR_TRACK_REASONS = {{  // סיבה -> טקסט בעברית, לפופאפ ולסיכום
            ok: 'מזוהה', terrain: 'חסום ע"י שטח', elevation: 'מחוץ לשדה-הראייה האנכי',
            sector: 'מחוץ לסקטור המערך', radar_range: 'מעבר לתקרת המכ"ם', min_range: 'בתוך אזור העיוור הקרוב',
            doppler: 'עיוור לדופלר', out_of_range: 'מחוץ לטווח הבדיקה',
            angular_rate: 'מהיר מדי לאנטנת המעקב', end: 'עד סוף המסלול',  // סיבות של שלב א2
            rain: 'נחלש בגשם מעבר לטווח'  // שלב א5: בטווח ביבש, מחוץ לטווח בגשם
        }};
        var _RADAR_TRACK_STATES = {{  // מצב מעקב -> טקסט בעברית
            tracked: 'במעקב', coasting: 'דעיכה (מעקב בלי גילוי)', detected_untracked: 'גילוי בלי מעקב'
        }};
        var _RADAR_SCAN_NAMES = {{ rotating: 'אנטנה מסתובבת', phased: 'מערך-מופע', tracker: 'מכ"ם מעקב ייעודי' }};  // לסיכום

        function _radarTrackScanBody() {{
            // אוסף את הגדרות הסריקה והמעקב מהטאב הבליסטי; אם הטאב עוד לא נבנה — השרת ישתמש בברירות המחדל
            var out = {{}};  // התוצאה
            Object.keys(_rtScanInputs).forEach(function(k) {{  // כל שדה
                var el = _rtScanInputs[k];  // האלמנט
                if (el.tagName === 'SELECT') {{ out[k] = el.value; return; }}  // בחירה — כטקסט
                var v = parseFloat(el.value);  // מספר
                if (!isNaN(v)) out[k] = v;  // רק ערך תקין; אחרת השרת משתמש בברירת המחדל
            }});
            return out;  // לגוף הבקשה
        }}

        function _radarTrackDrawTimeline(canvas, res) {{
            // ציר זמן: פס צבעוני לאורך שניות המעוף לפי מצב, קו לבן בפתיחת המעקב, ומספרי זמן בקצוות
            if (!canvas) return;  // אין canvas
            if (!res.track) {{ canvas.style.display = 'none'; return; }}  // מצב "גילוי" — אין ציר זמן
            canvas.style.display = 'block';  // מציגים
            var W = 250, H = 40, dpr = window.devicePixelRatio || 1;  // מידות, וחדות במסכים צפופים
            canvas.width = W * dpr; canvas.height = H * dpr;  // רזולוציה פנימית
            var ctx = canvas.getContext('2d');  // הקשר הציור
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);  // ציור ביחידות CSS
            ctx.clearRect(0, 0, W, H);  // ניקוי
            var tl = res.track.timeline;  // המקטעים
            var t0 = tl[0].t0, t1 = tl[tl.length - 1].t1, span = Math.max(1e-6, t1 - t0);  // טווח הזמן
            function x(t) {{ return W - 4 - (t - t0) / span * (W - 8); }}  // זמן -> פיקסל; מימין לשמאל, כמו כיוון הקריאה בעברית
            tl.forEach(function(s) {{  // כל מקטע
                ctx.fillStyle = _RADAR_TRACK_COLORS[s.state] || '#6c7086';  // צבע המצב
                ctx.fillRect(x(s.t1), 6, Math.max(1, x(s.t0) - x(s.t1)), 16);  // הפס
            }});
            if (res.track.first_track_t != null) {{  // נפתח מעקב
                var xf = x(res.track.first_track_t);  // מיקום הפתיחה
                ctx.fillStyle = '#111'; ctx.fillRect(xf - 1, 2, 2, 24);  // קו כהה
            }}
            ctx.fillStyle = '#333'; ctx.font = '9px Arial';  // טקסט
            ctx.textAlign = 'right'; ctx.fillText(t0.toFixed(0) + ' שנ\\'', W - 2, 36);  // התחלה (ימין)
            ctx.textAlign = 'left'; ctx.fillText(t1.toFixed(1) + ' שנ\\'', 2, 36);  // סוף (שמאל)
            if (res.track.warning_time_s != null) {{  // זמן התרעה
                ctx.textAlign = 'center'; ctx.fillText('התרעה: ' + res.track.warning_time_s.toFixed(1) + ' שנ\\'', W / 2, 36);  // באמצע, ספרה אחת
            }}
        }}

        function _radarCommonBody() {{
            // אוסף את פרמטרי המכ"ם מהפאנל של כלי הדופלר — אותם שדות כמו _runRouteEvaluation, אבל ה-RCS
            // נלקח מהשדה הידני (_radarRcsInput): למסלול בליסטי אין "סוג כלי טיס" לגזור ממנו RCS
            function num(el, def) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? def : v; }}  // ערך מספרי או ברירת-מחדל
            return {{
                range_km: num(_radarRangeInput, 50), min_range_km: num(_radarMinRangeInput, 1),  // טווח ואזור עיוור
                h_antenna: num(_radarHAntInput, 15), ridge_margin_deg: num(_radarMarginInput, 0),  // גובה אנטנה ומרווח רכס
                vertical_center_deg: num(_radarVCenterInput, 0), vertical_width_deg: num(_radarVWidthInput, 10),  // שדה ראייה אנכי
                power_kw: num(_radarPowerInput, 100), gain_dbi: num(_radarGainInput, 30),  // הספק ורווח
                freq_mhz: (_radarFreqSelect ? parseFloat(_radarFreqSelect.value) : 3000),  // תדר
                sensitivity_dbm: num(_radarSensInput, -100), rcs_m2: num(_radarRcsInput, 2),  // רגישות ו-RCS
                prf_hz: num(_radarPrfInput, 1000), mdv_kt: num(_radarMdvInput, 20),  // PRF ו-MDV
                lobing_enabled: !!(_radarLobingCheck && _radarLobingCheck.checked),  // ריבוד
                reflectivity: (_radarReflSelect ? _radarReflSelect.value : 'land'),  // סוג משטח
                antenna_type: (_radarAntennaSelect ? _radarAntennaSelect.value : 'generic'),  // סוג אנטנה
                boresight_deg: num(_radarBoresightInput, 0), max_scan_deg: num(_radarMaxScanInput, 60),  // מערך-מופעים
            }};
        }}

        function _clearRadarTrack() {{
            // מסיר את ציור הבדיקה ועוצר job פעיל — נקרא לפני בדיקה חדשה ובכל חישוב מסלול חדש
            _radarTrackLayers.forEach(function(l) {{ map.removeLayer(l); }});  // הסרת הקטעים
            _radarTrackLayers = [];  // איפוס
            _radarTrackLastResult = null;  // שלב א3: אין תוצאה תקפה
            _radarTrackDrawFan(null);  // מסיר את מניפת ה-LOS
            ['side', 'profile'].forEach(function(k) {{ if (_rtViewEls[k]) _rtViewEls[k].style.display = 'none'; }});  // מסתיר גרפים ישנים
            if (_rtViewEls.profInfo) _rtViewEls.profInfo.textContent = '';  // מנקה את כותרת הפרופיל
            if (_radarTrackPollTimer) {{ clearInterval(_radarTrackPollTimer); _radarTrackPollTimer = null; }}  // עצירת polling
            if (_radarTrackJobId) {{  // job שעדיין רץ בשרת — מבקשים ביטול כדי לא לבזבז מכסת גבהים
                fetch('http://localhost:5002/radar_doppler/cancel?job_id=' + _radarTrackJobId, {{method: 'POST'}}).catch(function() {{}});
                _radarTrackJobId = null;  // כבר לא פעיל
            }}
        }}

        function _radarTrackRun(path, infoEl, timelineEl, opts) {{
            // מפעיל בדיקת מעקב מכ"ם על מסלול נתון — דורש מכ"ם מוצב (כלי 🎯) ומסלול עם זמן.
            // opts (שלב א4): source/alt_ref/rcs_m2/label — מקור המסלול, ייחוס הגובה, RCS מיוחד ותווית לסיכום
            if (!radarObs) {{ alert('הצב קודם מכ"ם על המפה עם כלי "תצפית מכ\\"ם דופלר" (🎯) — הפרמטרים שלו ישמשו לבדיקה'); return; }}
            if (!path || path.length < 2) {{ alert('אין מסלול לבדיקה — בחר מקור מסלול בטאב "מעקב מכ\\"ם"'); return; }}
            _clearRadarTrack();  // בדיקה קודמת (אם יש) מבוטלת ונמחקת
            _radarTrackLastPath = path;  // לחישוב מחדש בגרירה
            _radarTrackLastOpts = opts || {{source: 'ballistic', alt_ref: 'msl'}};  // המקור — לגרירה, לסיכום ולניקוי
            _radarTrackProfileLbl = _rtActiveLabel();  // FR-D-286: הפרופיל שהיה פעיל כשהבדיקה התחילה — לסיכום, לפופאפ ול-CSV
            _radarTrackInfoEl = infoEl;  // לשם נכתוב את הסיכום
            _radarTrackTimelineEl = timelineEl || _radarTrackTimelineEl;  // ציר הזמן (שלב א2) — נשמר גם לחישוב מחדש בגרירה
            var body = Object.assign(_radarCommonBody(), _radarTrackScanBody(), _rtEnvBody(), {{  // פרמטרי המכ"ם + סריקה ומעקב + RCS וגשם (א5) + מיקום + מסלול
                lat: radarObs.lat, lon: radarObs.lng,  // מיקום המכ"ם
                trajectory: path.map(function(p) {{ return {{t: p.t, lat: p.lat, lon: p.lon, alt: (p.alt != null ? p.alt : p.alt_msl)}}; }}),  // רק השדות הדרושים; הגובה לפי alt_ref
                alt_ref: _radarTrackLastOpts.alt_ref || 'msl',  // שלב א4: מעל פני הים / מעל הקרקע
            }});
            if (_radarTrackLastOpts.rcs_m2) body.rcs_m2 = _radarTrackLastOpts.rcs_m2;  // שלב א4: RCS לפי סוג המטוס (FR24) גובר על השדה הידני
            if (infoEl) infoEl.textContent = '🎯 בודק מעקב מכ"ם…';  // משוב מיידי
            fetch('http://localhost:5002/radar_track/start', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(body)
            }})
            .then(function(r) {{ return r.json().then(function(d) {{ if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }}); }})  // שגיאת קלט מגיעה עם הסבר
            .then(function(d) {{
                _radarTrackJobId = d.job_id;  // ה-job החדש
                _radarTrackPollTimer = setInterval(_radarTrackPoll, 1000);  // בדיקת סטטוס כל שנייה
            }})
            .catch(function(e) {{ if (infoEl) infoEl.textContent = '🎯 שגיאה: ' + e.message; }});  // הודעה בפאנל
        }}

        function _rtEtaText(d) {{  // T23 (F-055): " · נותרו כ-X" לפי הערכת השרת (eta_s), או '' כשאין
            var s = d && typeof d.eta_s === 'number' ? d.eta_s : 0;  // שניות שנותרו
            if (s <= 0) return '';  // אין הערכה / הסתיים
            return ' · נותרו כ-' + (s < 90 ? Math.max(1, Math.round(s)) + " שנ'" : Math.round(s / 60) + " דק'");  // עד דקה וחצי בשניות, אחר כך בדקות (גרשיים כפולים — בלי escape בתוך ה-f-string)
        }}
        function _rtRevealResult(el) {{  // T23: גלילה לסיכום בתוך הפאנל — שלא יישאר מתחת לתחתית החלון
            if (el && el.scrollIntoView) el.scrollIntoView({{block: 'nearest', behavior: 'smooth'}});  // רק כמה שצריך
        }}

        function _radarTrackPoll() {{
            // בודק את מצב ה-job; מצייר ומסכם בסיום
            if (!_radarTrackJobId) return;  // אין job פעיל
            var jobId = _radarTrackJobId;  // נשמר — אם בינתיים התחילה בדיקה חדשה, מתעלמים מתשובה ישנה
            fetch('http://localhost:5002/radar_doppler/status?job_id=' + jobId)
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                if (jobId !== _radarTrackJobId) return;  // תשובה ל-job שכבר הוחלף
                var el = _radarTrackInfoEl;  // אלמנט הסיכום
                if (d.status === 'running') {{  // עדיין רץ — מציג התקדמות
                    if (el) el.textContent = '🎯 ' + (d.note || (d.batches_total ? ('שולף גבהי שטח… ' + d.batches_done + '/' + d.batches_total + _rtEtaText(d)) : 'מחשב…'));  // T23: + הערכת זמן
                    return;  // ממתין ל-tick הבא
                }}
                clearInterval(_radarTrackPollTimer); _radarTrackPollTimer = null;  // הסתיים — עוצרים polling
                _radarTrackJobId = null;  // אין job פעיל
                if (d.status === 'done') {{  // הצליח
                    _radarTrackDraw(d.result);  // ציור
                    if (el) el.textContent = _radarTrackSummaryText(d.result);  // סיכום
                    _radarTrackDrawTimeline(_radarTrackTimelineEl, d.result);  // ציר הזמן (רק במצב מעקב)
                    _radarTrackLastResult = d.result;  // שלב א3: למניפה, לגרף הצד ולייצוא
                    _radarTrackDrawFan(d.result);  // מניפת LOS (אם המתג פעיל)
                    _radarTrackDrawSide(_rtViewEls.side, d.result);  // גרף הצד
                    _rtRevealResult(el);  // T23 (F-055): גלילה לסיכום — גם בחישוב הבליסטי
                }} else if (d.status === 'error') {{  // נכשל
                    if (el) el.textContent = '🎯 שגיאה: ' + (d.error || 'לא ידועה');  // הסיבה
                    _rtRevealResult(el);  // T23: גם שגיאה צריכה להיראות
                }} else if (el) {{  // בוטל
                    el.textContent = '';  // מנקה
                }}
            }})
            .catch(function() {{}});  // כשל רשת בבדיקה בודדת — ה-tick הבא ינסה שוב
        }}

        function _radarTrackSummaryText(res) {{
            // טקסט הסיכום לפאנל: נצפה?, כיסוי, גילוי ראשון, זמן אובדן לפי סיבה, ונתוני דגימת השטח
            var s = res.summary;  // הסיכום מהשרת
            var lines = [];  // שורות הסיכום
            if (_radarTrackProfileLbl) lines.push('📡 ' + _radarTrackProfileLbl);  // FR-D-286: לפי איזה פרופיל חושב
            if (_radarTrackLastOpts && _radarTrackLastOpts.label) lines.push('מקור: ' + _radarTrackLastOpts.label);  // שלב א4: מה נבדק
            if (res.track) {{  // מצב מעקב (שלב א2) — המדדים של המעקב קודם
                var k = res.track, sc = res.scan;  // מדדי המעקב והתצורה
                lines.push('🎯 ' + (_RADAR_SCAN_NAMES[sc.mode] || sc.mode) + ', ' + sc.m + ' מתוך ' + sc.n + ': ' +
                    (k.track_initiated ? 'מעקב נפתח ✔ בשנ\\' ' + k.first_track_t.toFixed(1) + ' — זמן התרעה ' + k.warning_time_s.toFixed(1) + ' שנ\\''
                                       : 'מעקב לא נפתח ✖'));  // השורה הראשית
                lines.push('במעקב ' + k.tracked_pct + '% מזמן המעוף | ' + k.opportunities + ' הזדמנויות, ' + k.opp_detected + ' גילויים');  // היקף
                if (k.tracks.length) lines.push('מעקבים: ' + k.tracks.map(function(tr) {{  // כל מעקב
                    return tr.t_start.toFixed(1) + '–' + tr.t_end.toFixed(1) + ' שנ\\' (' + (_RADAR_TRACK_REASONS[tr.end_reason] || tr.end_reason) + ')';  // טווח זמן (ספרה אחת) וסיבת סיום
                }}).join(' · '));
            }}
            var env = res.env || {{}}, envParts = [];  // שלב א5: תנאים שבהם חושב
            if (env.rcs_mode === 'aspect') envParts.push('RCS לפי זווית (' + env.rcs_nose + '/' + env.rcs_side + '/' + env.rcs_tail + ' מ"ר)');  // חרטום/צד/זנב
            if (env.rain_rate_mmh > 0) envParts.push('גשם ' + env.rain_rate_mmh + ' מ"מ/שעה עד ' + env.rain_top_m + ' מ\\' (ITU-R P.838-3)');  // גשם + ציון מקור
            if (envParts.length) lines.push(envParts.join(' · '));  // שורה אחת
            lines.push((res.track ? 'פיזיקה: ' : '🎯 מכ"ם: ') + (s.detected_any ? 'נצפה ✔' : 'לא נצפה כלל ✖') +
                         ' | כיסוי ' + s.coverage_pct + '% מזמן המעוף (' + s.duration_s + ' שנ\\')');  // הכיסוי הפיזיקלי (שלב א1)
            if (s.first_detection) {{  // נצפה לפחות פעם אחת
                var f = s.first_detection;  // הגילוי הראשון
                lines.push('גילוי ראשון: שנ\\' ' + f.t + ', טווח ' + f.slant_km + ' ק"מ, גובה ' + Math.round(f.alt) + ' מ\\'');  // מתי ואיפה
            }}
            var lost = [];  // סיבות אובדן
            Object.keys(s.reason_seconds).forEach(function(k) {{  // כל סיבה
                if (k !== 'ok' && s.reason_seconds[k] > 0) lost.push([k, s.reason_seconds[k]]);  // רק סיבות כישלון
            }});
            lost.sort(function(a, b) {{ return b[1] - a[1]; }});  // מהגדולה לקטנה
            if (lost.length) lines.push('אובדן: ' + lost.map(function(x) {{ return (_RADAR_TRACK_REASONS[x[0]] || x[0]) + ' ' + x[1].toFixed(1) + ' שנ\\''; }}).join(' · '));  // לפי סיבה
            var t = res.terrain;  // נתוני דגימת השטח
            lines.push('שטח: ' + t.cells + ' תאי-גובה (' + t.cached + ' מהמטמון' + (t.missing ? ', ' + t.missing + ' חסרים' : '') + ')');  // שקיפות
            return lines.join('\\n');  // הטקסט המלא
        }}

        function _radarTrackDraw(res) {{
            // מצייר את המסלול בקטעים צבועים לפי סטטוס הנקודה בקצה כל קטע, עם פופאפ מפורט
            _radarTrackLayers.forEach(function(l) {{ map.removeLayer(l); }});  // ניקוי ציור קודם
            _radarTrackLayers = [];  // איפוס
            var pts = res.points;  // נקודות ההערכה
            function popupFor(p) {{  // תוכן הפופאפ לנקודה
                return '<div style="direction:rtl;font-family:Arial;font-size:12px;min-width:170px;">' +
                    (p.track_state ? '<div style="font-weight:bold;">' + (_RADAR_TRACK_STATES[p.track_state] || '') + '</div>' : '') +  // מצב המעקב (שלב א2)
                    '<div style="font-weight:bold;margin-bottom:3px;">' + (_RADAR_TRACK_REASONS[p.reason] || p.status) + '</div>' +
                    (p.ang_rate_dps != null ? '<div>קצב זוויתי: ' + p.ang_rate_dps + '°/שנ\\'</div>' : '') +  // שלב א2
                    '<div>זמן: ' + p.t + ' שנ\\' | גובה: ' + Math.round(p.alt) + ' מ\\'</div>' +
                    '<div>טווח אלכסוני: ' + p.slant_km + ' ק"מ | עילוי: ' + p.elev_deg + '°</div>' +
                    '<div>מהירות רדיאלית: ' + p.radial_ms + ' מ\\'/ש\\' (מתוך ' + p.speed_ms + ')</div>' +
                    (p.ceiling_km != null ? '<div>תקרת מכ"ם בכיוון: ' + p.ceiling_km + ' ק"מ</div>' : '') +
                    (p.rcs_m2 != null ? '<div>זווית הסתכלות: ' + p.aspect_deg + '° | RCS: ' + p.rcs_m2 + ' מ"ר</div>' : '') +  // שלב א5
                    (p.rain_db != null ? '<div>הנחתת גשם (הלוך-חזור): ' + p.rain_db + ' dB</div>' : '') +  // שלב א5
                    (_radarTrackProfileLbl ? '<div style="color:#666;margin-top:2px;">' + _escapeHtmlRt(_radarTrackProfileLbl) + '</div>' : '') +  // FR-D-286: הפרופיל (שם משתמש — מנוטרל HTML)
                    '</div>';
            }}
            for (var i = 1; i < pts.length; i++) {{  // קטע בין כל שתי נקודות עוקבות
                var a = pts[i - 1], b = pts[i];  // קצוות הקטע
                var key = b.track_state || b.status;  // במצב מעקב — לפי מצב המעקב; אחרת לפי הסטטוס הפיזיקלי
                var seg = L.polyline([[a.lat, a.lon], [b.lat, b.lon]],
                    {{color: _RADAR_TRACK_COLORS[key] || '#6c7086', weight: 6, opacity: 0.9}}).addTo(map);  // מעל קו המסלול הכתום
                seg.bindPopup(popupFor(b));  // פופאפ לפי הנקודה בקצה
                (function(pt) {{ seg.on('click', function() {{ _radarTrackShowProfile(pt); }}); }})(b);  // שלב א3: לחיצה גם מציירת פרופיל שטח לנקודה
                _radarTrackLayers.push(seg);  // לניקוי
            }}
        }}

        function _radarTrackOnRadarMoved() {{
            // נקרא כשהמכ"ם זז (גרירה/הצבה מחדש): אם יש בדיקה מוצגת או רצה — מריצים אותה מחדש מהמיקום החדש
            if (_radarTrackLastPath && (_radarTrackLayers.length || _radarTrackJobId)) {{  // יש מה לעדכן
                _radarTrackRun(_radarTrackLastPath, _radarTrackInfoEl, _radarTrackTimelineEl, _radarTrackLastOpts);  // אותו מסלול ואותו מקור, מיקום מכ"ם חדש
            }}
        }}

        // ── שלב א4: מקורות מסלול — בליסטי, FR24, מסלול מצויר, שיוט במעגל, קובץ CSV ──
        var _rtSrc = {{loiterCenter: null, loiterLayer: null, csvPoints: null}};  // שדות הטאב ומצב המקורות
        var _KT_MS = 0.514444;  // קשר -> מ'/ש'
        var _FT_M = 0.3048;     // רגל -> מטר

        function _rtHav(a, b) {{  // מרחק במטרים בין שתי נקודות {{lat, lon}} — אותה נוסחה כמו בשרת
            var r = Math.PI / 180, dlat = (b.lat - a.lat) * r, dlon = (b.lon - a.lon) * r;  // הפרשים ברדיאנים
            var h = Math.sin(dlat / 2) * Math.sin(dlat / 2) + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dlon / 2) * Math.sin(dlon / 2);  // Haversine
            return 2 * _RT_R_EARTH * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));  // מטרים
        }}

        function _rtTimesBySpeed(verts, speedMs) {{
            // נותן זמן לכל קודקוד לפי מרחק מצטבר ומהירות קבועה — למקורות בלי זמן (מסלול מצויר, FR24 בלי ts)
            var t = 0;  // זמן מצטבר
            return verts.map(function(v, i) {{  // כל קודקוד
                if (i > 0) t += _rtHav(verts[i - 1], v) / Math.max(0.1, v.spd_ms || speedMs);  // זמן הקטע לפי מהירות הקודקוד או הקבועה
                return {{t: t, lat: v.lat, lon: v.lon, alt: v.alt}};  // נקודה עם זמן
            }});
        }}

        function _rtParseCsv(text) {{
            // קורא CSV של מסלול: עמודות זמן [שנ'], רוחב, אורך, גובה [מ']. שורת כותרת מזוהה לפי שמות
            // (t/time, lat, lon/lng, alt/alt_m/alt_msl), ובלעדיה הסדר הוא t,lat,lon,alt. נקודה לא תקינה מדולגת.
            var rows = text.replace(/\\r/g, '').split('\\n').map(function(l) {{ return l.trim(); }}).filter(function(l) {{ return l.length; }});  // שורות לא ריקות
            if (!rows.length) return [];  // קובץ ריק
            var idx = {{t: 0, lat: 1, lon: 2, alt: 3}};  // ברירת המחדל
            var first = rows[0].replace(/^\\ufeff/, '').split(/[,;\\t]/).map(function(h) {{ return h.trim().toLowerCase(); }});  // הכותרת האפשרית
            if (first.some(function(h) {{ return /[a-z]/.test(h); }})) {{  // יש אותיות — זו כותרת
                function find(names) {{ for (var i = 0; i < first.length; i++) if (names.indexOf(first[i]) >= 0) return i; return -1; }}  // חיפוש עמודה
                idx = {{t: find(['t', 'time', 't_s', 'time_s']), lat: find(['lat', 'latitude']), lon: find(['lon', 'lng', 'longitude']),
                        alt: find(['alt', 'alt_m', 'alt_msl', 'altitude', 'height'])}};  // מיפוי לפי שם
                rows = rows.slice(1);  // בלי הכותרת
                if (idx.t < 0 || idx.lat < 0 || idx.lon < 0 || idx.alt < 0) return null;  // חסרה עמודה — שגיאה
            }}
            var pts = [];  // הנקודות
            rows.forEach(function(r) {{  // כל שורה
                var c = r.split(/[,;\\t]/);  // עמודות
                var q = {{t: parseFloat(c[idx.t]), lat: parseFloat(c[idx.lat]), lon: parseFloat(c[idx.lon]), alt: parseFloat(c[idx.alt])}};  // ערכים
                if ([q.t, q.lat, q.lon, q.alt].every(function(v) {{ return isFinite(v); }})) pts.push(q);  // רק שורה תקינה
            }});
            return pts;  // המסלול
        }}

        function _rtPickRadar(labelEl) {{
            // תיקון תקלה: מציב/מזיז את המכ"ם ישירות מטאב "מעקב מכ"ם", בלי לסגור את הכלי הבליסטי ובלי לפתוח את פאנל 🎯.
            // הפרמטרים נשארים מכלי הדופלר. הדגל מונע מאותה לחיצה להזיז גם תותח/מטרה (ה-handler הבליסטי רץ לפני זה)
            _rtMapPickActive = true;  // הלחיצה הבאה שייכת לבחירה הזו
            labelEl.textContent = 'לחץ על המפה…';  // הוראה
            map.once('click', function(e) {{  // לחיצה אחת בלבד
                _rtMapPickActive = false;  // הבחירה הסתיימה
                _placeRadarObserver(e.latlng);  // הצבה — אם מוצגת בדיקה, היא רצה מחדש מהמיקום (FR-D-266)
                labelEl.textContent = e.latlng.lat.toFixed(4) + ', ' + e.latlng.lng.toFixed(4);  // הצגה
            }});
        }}

        function _rtPickLoiterCenter(labelEl) {{
            // הלחיצה הבאה על המפה קובעת את מרכז השיוט; מציג מעגל תצוגה מקדימה ברדיוס שבשדה
            _rtMapPickActive = true;  // תיקון תקלה: הלחיצה לא תזיז גם תותח/מטרה כשהכלי הבליסטי פעיל
            labelEl.textContent = 'לחץ על המפה…';  // הוראה
            map.once('click', function(e) {{  // לחיצה אחת בלבד
                _rtMapPickActive = false;  // הבחירה הסתיימה
                _rtSrc.loiterCenter = e.latlng;  // המרכז
                labelEl.textContent = e.latlng.lat.toFixed(4) + ', ' + e.latlng.lng.toFixed(4);  // הצגה
                _rtDrawLoiterPreview();  // מעגל
            }});
        }}

        function _rtDrawLoiterPreview() {{
            // מעגל מקווקו שמראה את מסלול השיוט לפני הבדיקה
            if (_rtSrc.loiterLayer) {{ map.removeLayer(_rtSrc.loiterLayer); _rtSrc.loiterLayer = null; }}  // ניקוי קודם
            if (!_rtSrc.loiterCenter || !_rtSrc.loiterRadius) return;  // אין מרכז או שהטאב לא נבנה
            _rtSrc.loiterLayer = L.circle(_rtSrc.loiterCenter, {{radius: parseFloat(_rtSrc.loiterRadius.value) || 1000,
                color: '#14b8a6', weight: 2, dashArray: '5,5', fill: false}}).addTo(map);  // התצוגה המקדימה
        }}

        function _rtBuildTrajectory() {{
            // בונה את המסלול לפי המקור שנבחר. מחזיר {{points, opts}} או null (אחרי הודעה למשתמש)
            var src = _rtSrc.sel ? _rtSrc.sel.value : 'ballistic';  // המקור
            var altRef = _rtSrc.altRef ? _rtSrc.altRef.value : 'msl';  // גובה מעל הקרקע/הים — רק למקורות שבהם זה רלוונטי
            function num(el, d) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? d : v; }}  // ערך מספרי או ברירת מחדל
            if (src === 'ballistic') {{  // המסלול האחרון שחושב (מסלול בודד או פתרון ירי)
                if (!ballisticsLastPath || ballisticsLastPath.length < 2) {{ alert('חשב קודם מסלול בטאב "מסלול בודד" או "פתרון ירי"'); return null; }}  // אין
                return {{points: ballisticsLastPath.map(function(p) {{ return {{t: p.t, lat: p.lat, lon: p.lon, alt: p.alt_msl}}; }}),
                         opts: {{source: 'ballistic', alt_ref: 'msl', label: 'מסלול בליסטי'}}}};  // תמיד מעל פני הים
            }}
            if (src === 'fr24') {{  // טיסה שנטענה בכלי מעקב הטיסות
                var fr = _lastFlightRouteData;  // נתוני הטיסה האחרונה
                var tr = fr && fr.trail ? fr.trail.filter(function(p) {{ return p.lat != null && p.lng != null; }}) : [];  // נקודות תקינות
                if (tr.length < 2) {{ alert('חפש קודם טיסה עם מסלול בכלי מעקב הטיסות (FR24)'); return null; }}  // אין
                var pts;  // הנקודות עם זמן
                var withTs = tr.filter(function(p) {{ return p.ts != null; }});  // נקודות עם זמן אמיתי
                if (withTs.length >= 2) {{  // יש זמנים — משתמשים בהם
                    var ts0 = Math.min.apply(null, withTs.map(function(p) {{ return p.ts; }}));  // הזמן הראשון
                    pts = withTs.map(function(p) {{ return {{t: p.ts - ts0, lat: p.lat, lon: p.lng, alt: (p.alt || 0) * _FT_M}}; }});  // רגל -> מטר
                }} else {{  // אין זמנים — לפי מרחק ומהירות כל נקודה
                    pts = _rtTimesBySpeed(tr.map(function(p) {{ return {{lat: p.lat, lon: p.lng, alt: (p.alt || 0) * _FT_M, spd_ms: (p.spd || 0) * _KT_MS}}; }}), 120);  // 120 מ'/ש' אם אין מהירות
                }}
                var rcs = _rtSrc.frRcs && _rtSrc.frRcs.checked ? _rcsForAircraftType(fr.aircraft_icao) : null;  // RCS לפי סוג המטוס, כמו בהערכת המסלול הקיימת
                return {{points: pts, opts: {{source: 'fr24', alt_ref: 'msl', rcs_m2: rcs,
                         label: 'טיסה ' + (fr.callsign || fr.flight || '') + (rcs ? ' (RCS ' + rcs + ' מ"ר לפי ' + (fr.aircraft || fr.aircraft_icao || '?') + ')' : '') +
                                (withTs.length >= 2 ? '' : ' — בלי זמני FR24, הזמן חושב לפי מהירות')}}}};  // שקיפות
            }}
            if (src === 'custom') {{  // מסלול שצויר בכלי "מסלול טיסה מותאם"
                if (customRoutePoints.length < 2) {{ alert('צייר קודם מסלול (לפחות 2 נקודות) בכלי "מסלול טיסה מותאם"'); return null; }}  // אין
                var defAlt = num(_rtSrc.customAlt, 300);  // גובה לנקודות בלי גובה
                var verts = customRoutePoints.map(function(p) {{ return {{lat: p.lat, lon: p.lng, alt: p.alt != null ? p.alt : defAlt}}; }});  // הקודקודים
                verts.push(verts[0]);  // סגירת הלולאה — כמו שהכלי מצייר אותה
                return {{points: _rtTimesBySpeed(verts, num(_rtSrc.customSpeed, 90) * _KT_MS),
                         opts: {{source: 'custom', alt_ref: altRef, label: 'מסלול מצויר, ' + num(_rtSrc.customSpeed, 90) + ' קשר'}}}};  // זמן לפי מהירות קבועה
            }}
            if (src === 'loiter') {{  // שיוט במעגל
                if (!_rtSrc.loiterCenter) {{ alert('בחר קודם מרכז לשיוט (כפתור "בחר מרכז על המפה")'); return null; }}  // אין מרכז
                var R = num(_rtSrc.loiterRadius, 1500), alt = num(_rtSrc.loiterAlt, 300), laps = Math.max(1, Math.round(num(_rtSrc.loiterLaps, 2)));  // פרמטרים
                var dir = _rtSrc.loiterDir && _rtSrc.loiterDir.value === 'ccw' ? -1 : 1;  // כיוון
                var c = _rtSrc.loiterCenter, vs = [];  // מרכז וקודקודים
                for (var k = 0; k <= laps * 36; k++) {{  // קודקוד כל 10°
                    var pt = _destPointJs(c, (dir * k * 10 + 360000) % 360, R);  // נקודה על המעגל
                    vs.push({{lat: pt.lat, lon: pt.lng, alt: alt}});  // קודקוד
                }}
                return {{points: _rtTimesBySpeed(vs, num(_rtSrc.loiterSpeed, 60) * _KT_MS),
                         opts: {{source: 'loiter', alt_ref: altRef, label: 'שיוט: רדיוס ' + R + ' מ\\', ' + laps + ' סיבובים'}}}};  // זמן לפי מהירות
            }}
            if (src === 'csv') {{  // קובץ שנטען
                if (!_rtSrc.csvPoints || _rtSrc.csvPoints.length < 2) {{ alert('טען קודם קובץ CSV של מסלול'); return null; }}  // אין
                return {{points: _rtSrc.csvPoints, opts: {{source: 'csv', alt_ref: altRef, label: 'קובץ CSV (' + _rtSrc.csvPoints.length + ' נקודות)'}}}};  // כמו שהוא
            }}
            return null;  // לא אמור לקרות
        }}

        // ── שלב א5: RCS לפי זווית, גשם ופרופילי מכ"ם ──
        var _rtEnvInputs = {{}};     // שדות ה-RCS והגשם בטאב
        var _rtProfileFields = {{}}; // שם פרמטר -> אלמנט, לכל מה שנכנס לפרופיל מכ"ם

        function _rtEnvBody() {{
            // אוסף את שדות ה-RCS והגשם לגוף הבקשה (ערך לא תקין — השרת משתמש בברירת המחדל)
            var out = {{}};  // התוצאה
            Object.keys(_rtEnvInputs).forEach(function(k) {{  // כל שדה
                var el = _rtEnvInputs[k];  // האלמנט
                if (el.tagName === 'SELECT') {{ out[k] = el.value; return; }}  // בחירה
                var v = parseFloat(el.value); if (!isNaN(v)) out[k] = v;  // מספר תקין בלבד
            }});
            return out;  // לגוף הבקשה
        }}

        function _rtBuildProfileFieldMap() {{
            // כל השדות של פרופיל מכ"ם: פרמטרי המכ"ם מכלי הדופלר, הסריקה והמעקב, ומודל ה-RCS. הגשם לא נכלל —
            // הוא תנאי סביבה, לא תכונה של המכ"ם. שמות המפתחות זהים לשמות בגוף הבקשה לשרת
            var m = {{
                range_km: _radarRangeInput, min_range_km: _radarMinRangeInput, h_antenna: _radarHAntInput, ridge_margin_deg: _radarMarginInput,
                vertical_center_deg: _radarVCenterInput, vertical_width_deg: _radarVWidthInput, power_kw: _radarPowerInput, gain_dbi: _radarGainInput,
                freq_mhz: _radarFreqSelect, sensitivity_dbm: _radarSensInput, rcs_m2: _radarRcsInput, prf_hz: _radarPrfInput, mdv_kt: _radarMdvInput,
                lobing_enabled: _radarLobingCheck, reflectivity: _radarReflSelect, antenna_type: _radarAntennaSelect,
                boresight_deg: _radarBoresightInput, max_scan_deg: _radarMaxScanInput,
                rcs_mode: _rtEnvInputs.rcs_mode, rcs_nose: _rtEnvInputs.rcs_nose, rcs_side: _rtEnvInputs.rcs_side, rcs_tail: _rtEnvInputs.rcs_tail
            }};  // מכ"ם + RCS
            Object.keys(_rtScanInputs).forEach(function(k) {{ m[k] = _rtScanInputs[k]; }});  // סריקה ומעקב
            Object.keys(m).forEach(function(k) {{ if (!m[k]) delete m[k]; }});  // שדה שלא נבנה (פאנל שלא נטען) — לא נכלל
            return m;  // המפה
        }}

        function _rtExportProfileJson() {{
            // מייצא את הפרופיל הנוכחי לקובץ JSON — כך אפשר להחזיק נתונים מחוץ לפרויקט, ולא בקוד שמופץ (החלטה 6)
            var params = {{}};  // הערכים
            Object.keys(_rtProfileFields).forEach(function(k) {{  // כל שדה
                var el = _rtProfileFields[k];  // האלמנט
                params[k] = el.type === 'checkbox' ? el.checked : el.value;  // תיבה או ערך
            }});
            var doc = {{format: 'maps-gui-radar-profile', version: 1, params: params}};  // מבנה הקובץ
            var blob = new Blob([JSON.stringify(doc, null, 2)], {{type: 'application/json'}});  // הקובץ
            var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'radar_profile.json';  // קישור
            document.body.appendChild(a); a.click(); document.body.removeChild(a);  // הורדה (בדסקטופ — חלון שמירה, FR-D-270)
        }}

        function _rtImportProfileJson(text) {{
            // טוען פרופיל מקובץ JSON לשדות. מחזיר הודעה לתצוגה. שדה לא מוכר — מתעלמים; תדר שלא ברשימה — מתווסף
            var doc;  // התוכן
            try {{ doc = JSON.parse(text); }} catch (e) {{ return 'הקובץ אינו JSON תקין'; }}  // פענוח
            if (!doc || doc.format !== 'maps-gui-radar-profile' || !doc.params) return 'זה לא קובץ פרופיל מכ"ם של maps-gui';  // סוג הקובץ
            if (typeof _rsActiveSite === 'function' && _rsActiveSite()) {{  // FR-D-288: יש מכ"ם פעיל — לא דורסים את שדותיו; הפרופיל נוסף כסוג ונוצר ממנו מכ"ם
                _rsImport(text, function(m) {{ _rsMsg(m); }}, '');  // אותו ייבוא כמו בבורר הגלובלי
                return 'הפרופיל נוסף כסוג ב"הפרופילים שלי" ונוצר ממנו מכ"ם מוצב (ר\\' הבורר העליון)';  // הודעה
            }}
            var n = _rtApplyParams(doc.params);  // FR-D-286: אותה החלה כמו בבורר הפרופיל הפעיל
            if (radarObs) _updateRadarDopplerPreview();  // תצוגה מקדימה מעודכנת
            _rtRefreshActiveStatus();  // FR-D-286: הייבוא משנה שדות — הבורר יציג "שונה ידנית" אם היה פרופיל פעיל
            return 'נטענו ' + n + ' שדות מהפרופיל ✔';  // הודעה
        }}

        function _rtApplyParams(params) {{
            // FR-D-286: מחיל ערכי פרופיל על השדות (הוצא מ-_rtImportProfileJson כדי שגם הבורר ישתמש בו). מחזיר כמה שדות הוחלו
            var fields = _rtBuildProfileFieldMap();  // השדות שקיימים כרגע (מפה טרייה — גם אם טאב נבנה אחרי הקריאה הקודמת)
            var n = 0;  // כמה שדות נטענו
            Object.keys(params).forEach(function(k) {{  // כל ערך בקובץ
                var el = fields[k], v = params[k];  // השדה והערך
                if (!el) return;  // לא מוכר — מדלגים
                if (el.type === 'checkbox') {{ el.checked = (v === true || v === 'true'); }}  // תיבה
                else {{
                    if (el.tagName === 'SELECT' && !Array.from(el.options).some(function(o) {{ return o.value === String(v); }})) {{  // ערך שאינו ברשימה
                        if (k !== 'freq_mhz') return;  // רק תדר מותר להוסיף; בחירה אחרת לא מוכרת — מדלגים
                        var o = document.createElement('option'); o.value = String(v); o.textContent = v + ' MHz'; el.appendChild(o);  // תדר חדש
                    }}
                    el.value = v;  // הערך
                }}
                if (el.tagName === 'SELECT' || el.type === 'checkbox') el.dispatchEvent(new Event('change'));  // מפעיל מאזינים (הצגת שדות)
                n++;  // נספר
            }});
            return n;  // FR-D-286: מספר השדות שהוחלו — ההודעה והתצוגה המקדימה אצל הקורא
        }}

        // ── FR-D-288: מכ"מים מוצבים — מכ"ם פעיל אחד שכל הכלים עובדים עליו (מחליף את "פרופיל פעיל" של FR-D-286) ──
        // סוג מכ"ם = פרופיל (ספרייה מובנית / הפרופילים שלי). מכ"ם מוצב = סוג + פרמטרים של הצבה: מיקום, כיוון פנים, גובה אנטנה,
        // סקטור, טווח, משטח מחזיר וריבוד. נתוני המטרה (RCS, גובה יעד, מהירות) נשארים בכל כלי ולא נדרסים.
        // שדות הסוג נעולים כשהסוג מהספרייה ("⧉ שכפל לעריכה" יוצר עותק פתוח ב"הפרופילים שלי"). מיקום משותף לכל הכלים,
        // ורדיוס הראייה וקו הראייה יכולים להתנתק ("צופה נפרד"). "ללא מכ"ם (ידני)" = התנהגות הכלים כמו קודם.
        var _rtLib = [];  // סוגי מכ"ם מהספרייה המובנית (radar-profiles/, לקריאה בלבד): [{{name, file, params, notes}}]
        var _rtMyProfiles = [];  // סוגי מכ"ם של המשתמש (radar_profile בעמדות השמורות): [{{name, params}}]
        var _rtLibRequested = false;  // הספרייה נטענת מהשרת פעם אחת
        var _rtActiveBars = _rtActiveBars || [];  // כל הפסים המסונכרנים — "|| []" כי כלי LOS ורדיוס הראייה נבנים לפני השורה הזו ורושמים פסים מוקדם
        // שדות שמגיעים מסוג המכ"ם (נעולים לסוג מהספרייה)
        var _RT_TYPE_KEYS = ['min_range_km', 'vertical_center_deg', 'vertical_width_deg', 'power_kw', 'gain_dbi', 'freq_mhz', 'sensitivity_dbm',
                             'prf_hz', 'mdv_kt', 'antenna_type', 'max_scan_deg', 'scan_mode', 'rot_period_s', 'revisit_s', 'track_rate_hz',
                             'max_ang_rate_dps', 'cue_delay_s', 'track_m', 'track_n', 'coast_s'];
        // שדות של ההצבה (נשמרים עם המכ"ם המוצב, מסונכרנים בין הכלים, ניתנים לעריכה)
        var _RT_SITE_KEYS = ['boresight_deg', 'h_antenna', 'start_bearing_deg', 'end_bearing_deg', 'angle_step_deg', 'range_km',
                             'reflectivity', 'lobing_enabled', 'ridge_margin_deg'];
        var _rs = {{sites: [], active: '', detached: {{los: false, radial: false}}, applying: false, saveTimer: null, typeSaveTimer: null,
                   pick: false, global: null, editing: null}};  // מצב המכ"מים המוצבים

        function _rtNotesText(n) {{
            // טקסט המקורות של סוג מהספרייה: מה פורסם (עם הקישור) ומה הונח. קישורים כטקסט ולא כ-<a> — לחיצה על קישור
            // בתוך QtWebEngine הייתה מעבירה את כל המפה לאתר אחר
            var lines = [];  // השורות
            if (n.system) lines.push(n.system);  // תיאור המערכת
            if (n.published) {{ lines.push('', 'פורסם:'); Object.keys(n.published).forEach(function(k) {{ lines.push('• ' + k, '   ' + n.published[k]); }}); }}  // נתון + מקור
            if (n.assumed_not_published) {{ lines.push('', 'הונח (לא פורסם):'); Object.keys(n.assumed_not_published).forEach(function(k) {{ lines.push('• ' + k + ': ' + n.assumed_not_published[k]); }}); }}  // הנחה + סיבה
            return lines.join('\\n');  // הטקסט
        }}

        function _rsAdd(m, k, el) {{ if (el) (m[k] = m[k] || []).push(el); }}  // מוסיף אלמנט לרשימת השדות של מפתח

        function _rsTypeFields(all) {{
            // שדות הסוג בכל הכלים: מפתח -> [אלמנטים]. all=true כולל גם כלים מנותקים (לחיבור מאזינים)
            var m = {{}}, pf = _rtBuildProfileFieldMap();  // שדות המכ"ם, הסריקה וה-RCS
            _RT_TYPE_KEYS.forEach(function(k) {{ _rsAdd(m, k, pf[k]); }});  // פאנל הדופלר + טאב המעקב
            if (all || !_rs.detached.radial) {{  // רדיוס הראייה — רק כשמחובר למכ"ם
                _rsAdd(m, 'min_range_km', _radialMinRangeInput); _rsAdd(m, 'vertical_center_deg', _radialVCenterInput);
                _rsAdd(m, 'vertical_width_deg', _radialVWidthInput);
            }}
            return m;  // המפה
        }}

        function _rsSiteFields(all) {{
            // שדות ההצבה בכל הכלים: מפתח -> [אלמנטים]
            var m = {{}}, rad = all || !_rs.detached.radial, los = all || !_rs.detached.los;  // אילו כלים מחוברים
            _rsAdd(m, 'h_antenna', _radarHAntInput); if (rad) _rsAdd(m, 'h_antenna', _radialObsInput); if (los) _rsAdd(m, 'h_antenna', _losObsInput);  // גובה אנטנה = גובה צופה
            _rsAdd(m, 'start_bearing_deg', _radarStartInput); if (rad) _rsAdd(m, 'start_bearing_deg', _radialStartInput);  // סקטור
            _rsAdd(m, 'end_bearing_deg', _radarEndInput); if (rad) _rsAdd(m, 'end_bearing_deg', _radialEndInput);
            _rsAdd(m, 'angle_step_deg', _radarStepInput); if (rad) _rsAdd(m, 'angle_step_deg', _radialStepInput);
            _rsAdd(m, 'range_km', _radarRangeInput); if (rad) _rsAdd(m, 'range_km', _radialRangeInput);  // טווח הבדיקה
            _rsAdd(m, 'ridge_margin_deg', _radarMarginInput); if (rad) _rsAdd(m, 'ridge_margin_deg', _radialMarginInput); if (los) _rsAdd(m, 'ridge_margin_deg', _losMarginInput);  // מרווח רכס — גם בקו הראייה (FR-D-290)
            if (los) {{ _rsAdd(m, 'start_bearing_deg', _losStartInput); _rsAdd(m, 'end_bearing_deg', _losEndInput); }}  // FR-D-290: גזרת המכ"ם גם בקו הראייה הנקודתי
            _rsAdd(m, 'boresight_deg', _radarBoresightInput); _rsAdd(m, 'reflectivity', _radarReflSelect); _rsAdd(m, 'lobing_enabled', _radarLobingCheck);
            return m;  // המפה
        }}

        function _rsGet(el) {{ return el.type === 'checkbox' ? el.checked : el.value; }}  // ערך שדה

        function _rsVal(el) {{ var v = _rsGet(el); return (el.type === 'number' && !isNaN(parseFloat(v))) ? parseFloat(v) : v; }}  // ערך לשמירה (מספר כמספר)

        function _rsSet(el, v) {{
            // כותב ערך לשדה; תדר שאינו ברשימה מתווסף כאפשרות (כמו בייבוא פרופיל)
            if (el.type === 'checkbox') {{ el.checked = (v === true || v === 'true'); return; }}  // תיבה
            if (el.tagName === 'SELECT' && !Array.from(el.options).some(function(o) {{ return o.value === String(v); }})) {{  // לא ברשימה
                var o = document.createElement('option'); o.value = String(v); o.textContent = v + (el === _radarFreqSelect ? ' MHz' : ''); el.appendChild(o);  // מתווסף
            }}
            el.value = v;  // הערך
        }}

        function _rsApplyToFields(m, params) {{
            // מחיל ערכים על שדות; בחירות ותיבות מפעילות change (הצגת שדות תלויים, למשל מערך מופע)
            Object.keys(m).forEach(function(k) {{
                if (params[k] === undefined || params[k] === null || params[k] === '') return;  // אין ערך — לא נוגעים
                m[k].forEach(function(el) {{ _rsSet(el, params[k]); if (el.tagName === 'SELECT' || el.type === 'checkbox') el.dispatchEvent(new Event('change')); }});
            }});
        }}

        function _rsTypeOf(key) {{
            // סוג מכ"ם לפי מפתח: 'lib:<קובץ>' (יציב גם אם הספרייה ממוינת אחרת) או 'my:<שם>'
            if (!key) return null;  // אין
            if (key.indexOf('lib:') === 0) {{  // מהספרייה
                var f = key.substr(4), p = _rtLib.filter(function(x) {{ return x.file === f; }})[0];
                return p ? {{key: key, name: p.name, params: p.params, notes: p.notes, lib: true}} : null;
            }}
            if (key.indexOf('my:') === 0) {{  // שלי
                var n = key.substr(3), q = _rtMyProfiles.filter(function(x) {{ return x.name === n; }})[0];
                return q ? {{key: key, name: q.name, params: q.params, notes: null, lib: false}} : null;
            }}
            return null;  // לא מוכר
        }}

        function _rsActiveSite() {{ var a = _rs.active; return _rs.sites.filter(function(s) {{ return s.name === a; }})[0] || null; }}  // המכ"ם הפעיל

        function _rsTypeName(site) {{ var t = _rsTypeOf(site.params.type_key); return t ? t.name : (site.params.type_name || '?'); }}  // שם הסוג לתצוגה

        function _rtActiveLabel() {{
            // התווית שנכתבת על כל תוצאה: המכ"ם הפעיל וסוגו, או "ידני"
            var s = _rsActiveSite();  // הפעיל
            return s ? 'מכ"ם: ' + s.name + ' (' + _rsTypeName(s) + ')' : 'מכ"ם: ידני (ללא מכ"ם)';  // התווית
        }}

        function _rsSaveSite(site) {{
            // שמירת מכ"ם מוצב לשרת (אותו מנגנון "עמדות שמורות", מפתח radar_sites)
            return fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{tool: 'radar_sites', name: site.name, params: site.params}})}}).catch(function() {{}});
        }}

        function _rsSaveSoon() {{ clearTimeout(_rs.saveTimer); _rs.saveTimer = setTimeout(function() {{ var s = _rsActiveSite(); if (s) _rsSaveSite(s); }}, 600); }}  // שמירה מושהית (בזמן הקלדה/גרירה)

        function _rsLoadSites(then) {{
            // טוען את רשימת המכ"מים המוצבים מהשרת
            fetch('http://localhost:5002/stations/list?tool=radar_sites').then(function(r) {{ return r.json(); }})
            .then(function(d) {{ _rs.sites = d.stations || []; if (then) then(); _rsRefreshBars(); }})
            .catch(function() {{}});
        }}

        function _rsApplyLock() {{
            // נעילת שדות הסוג כשהמכ"ם הפעיל מסוג מהספרייה; כל השאר פתוחים
            document.querySelectorAll('[data-rs-locked]').forEach(function(el) {{ el.disabled = false; el.removeAttribute('data-rs-locked'); }});  // שחרור קודם
            var s = _rsActiveSite(), t = s ? _rsTypeOf(s.params.type_key) : null;  // הפעיל וסוגו
            if (!(t && t.lib)) return;  // ידני / סוג שלי — פתוח
            var tf = _rsTypeFields(false);  // רק כלים מחוברים
            Object.keys(tf).forEach(function(k) {{ tf[k].forEach(function(el) {{ el.disabled = true; el.setAttribute('data-rs-locked', '1'); }}); }});  // נעילה
        }}

        function _rsMoveObservers(ll, source) {{
            // מיקום משותף: מזיז את המכ"ם (דופלר + מעקב) ואת רדיוס הראייה אם מחובר ופתוח. source = הכלי שממנו הגיע השינוי
            _rs.applying = true;  // מונע לולאת עדכונים
            try {{
                if (source !== 'radar' && (!radarObs || !radarObs.equals(ll))) _placeRadarObserver(ll);  // המכ"ם
                if (source !== 'radial' && !_rs.detached.radial && radialLosActive && (!radialLosObs || !radialLosObs.equals(ll))) _placeRadialLosObserver(ll);  // רדיוס הראייה
            }} finally {{ _rs.applying = false; }}
        }}

        function _rsOnObserverMoved(source, ll) {{
            // נקרא מהכלים אחרי הצבה/גרירה של הצופה: מעדכן את מיקום המכ"ם הפעיל ומזיז את שאר הכלים
            if (_rs.applying || !ll) return;  // שינוי שאנחנו עצמנו גרמנו לו
            if (source === 'radial' && _rs.detached.radial) return;  // רדיוס ראייה מנותק — עצמאי
            var s = _rsActiveSite(); if (!s) return;  // ידני — הכלים עצמאיים כמו קודם
            s.params.lat = ll.lat; s.params.lon = ll.lng; _rsSaveSoon();  // המיקום החדש
            _rsMoveObservers(ll, source); _rsRefreshBars();  // שאר הכלים + תצוגה
        }}

        function _rsOnToolOpened(tool) {{
            // כלי נפתח: אם מחובר למכ"ם פעיל עם מיקום — הצופה שלו מוצב במיקום המכ"ם
            var ll = _rsSharedObs(tool); if (!ll) return;  // מנותק / ידני / בלי מיקום
            if (tool === 'radial' && (!radialLosObs || !radialLosObs.equals(ll))) {{ _rs.applying = true; try {{ _placeRadialLosObserver(ll); }} finally {{ _rs.applying = false; }} }}
        }}

        function _rsSharedObs(tool) {{
            // מיקום הצופה המשותף לכלי (null = ידני / מנותק / המכ"ם עוד לא הוצב)
            var s = _rsActiveSite(); if (!s || _rs.detached[tool] || s.params.lat == null || s.params.lon == null) return null;
            return L.latLng(s.params.lat, s.params.lon);  // המיקום
        }}

        function _rsSyncFrom(el) {{
            // שדה השתנה בכלי — אם הוא שדה הצבה: לעדכן את המכ"ם הפעיל ואת אותו שדה בשאר הכלים; אם שדה סוג "שלי" — לשמור לפרופיל
            if (_rs.applying || !el) return;  // שינוי פנימי
            var s = _rsActiveSite(); if (!s) return;  // ידני
            var sf = _rsSiteFields(false), tf = _rsTypeFields(false), v = _rsVal(el), hit = false;  // שדות מחוברים והערך
            Object.keys(sf).forEach(function(k) {{
                if (sf[k].indexOf(el) < 0) return;  // לא השדה הזה
                hit = true; s.params[k] = v;  // נשמר במכ"ם המוצב
                _rs.applying = true; try {{ sf[k].forEach(function(o) {{ if (o !== el) _rsSet(o, v); }}); }} finally {{ _rs.applying = false; }}  // שאר הכלים
            }});
            if (hit) _rsSaveSoon();  // שמירה מושהית
            var t = _rsTypeOf(s.params.type_key);  // הסוג
            if (t && !t.lib) Object.keys(tf).forEach(function(k) {{  // סוג שלי — עריכה חופשית שנשמרת לפרופיל
                if (tf[k].indexOf(el) < 0) return;  // לא השדה הזה
                t.params[k] = v;  // נשמר בפרופיל
                _rs.applying = true; try {{ tf[k].forEach(function(o) {{ if (o !== el) _rsSet(o, v); }}); }} finally {{ _rs.applying = false; }}  // שאר הכלים
                clearTimeout(_rs.typeSaveTimer);  // שמירה מושהית לפרופיל
                _rs.typeSaveTimer = setTimeout(function() {{
                    fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{tool: 'radar_profile', name: t.name, params: t.params}})}}).catch(function() {{}});
                }}, 800);
            }});
            if (radarObs) _updateRadarDopplerPreview();  // תצוגות מקדימות
            if (radialLosObs) _updateRadialLosPreview();
        }}

        function _rtHookActiveFields() {{
            // מחבר מאזין אחד לכל שדה הצבה/סוג בכל הכלים (אידמפוטנטי); השייכות נבדקת בזמן השינוי (ניתוק יכול להשתנות)
            var groups = [_rsSiteFields(true), _rsTypeFields(true)];  // כל השדות, כולל כלים מנותקים
            groups.forEach(function(m) {{ Object.keys(m).forEach(function(k) {{ m[k].forEach(function(el) {{
                if (el._rsHooked) return; el._rsHooked = true;  // פעם אחת לשדה
                el.addEventListener('input', function() {{ _rsSyncFrom(el); }}); el.addEventListener('change', function() {{ _rsSyncFrom(el); }});  // הקלדה ובחירה
            }}); }}); }});
        }}

        function _rsActivate(name) {{
            // בחירת מכ"ם פעיל: שדות הסוג מהפרופיל, שדות ההצבה מהמכ"ם המוצב, וכל הצופים למיקום שלו. '' = ידני
            var s = _rs.sites.filter(function(x) {{ return x.name === name; }})[0] || null;  // המכ"ם
            _rs.active = s ? s.name : '';  // הפעיל
            // T22 (F-054, החלטה Q-R5-6 א'): הבחירה לא נשמרת בין הפעלות — כל הפעלה מתחילה ב"ללא מכ"ם (ידני)"
            if (s) {{
                var t = _rsTypeOf(s.params.type_key);  // הסוג
                _rs.applying = true;  // מונע לולאת עדכונים
                try {{
                    if (t) {{ var tp = {{}}; _RT_TYPE_KEYS.forEach(function(k) {{ if (t.params[k] !== undefined) tp[k] = t.params[k]; }}); _rsApplyToFields(_rsTypeFields(false), tp); }}  // הסוג (בלי RCS — המטרה בכל כלי)
                    _rsApplyToFields(_rsSiteFields(false), s.params);  // ההצבה
                }} finally {{ _rs.applying = false; }}
                if (s.params.lat != null && s.params.lon != null) _rsMoveObservers(L.latLng(s.params.lat, s.params.lon), null);  // המיקום
            }}
            _rsApplyLock(); _rsRefreshBars();  // נעילה ותצוגה
            if (radarObs) _updateRadarDopplerPreview();  // תצוגות מקדימות
            if (radialLosObs) _updateRadialLosPreview();
        }}

        function _rsSetDetached(tool, on) {{
            // "צופה נפרד" בכלי: מנותק = עצמאי לגמרי (מיקום ושדות); חיבור מחדש מחיל שוב את המכ"ם הפעיל על הכלי
            _rs.detached[tool] = !!on;  // המצב
            try {{ localStorage.setItem('rs_detached', JSON.stringify(_rs.detached)); }} catch (e) {{}}  // לזכור
            if (!on && _rsActiveSite()) _rsActivate(_rs.active);  // חיבור מחדש — מחילים שוב
            else {{ _rsApplyLock(); _rsRefreshBars(); }}  // ניתוק — משחררים נעילה בכלי
        }}

        function _rsSiteDefaults(typeKey, ll) {{
            // ברירות מחדל למכ"ם מוצב חדש: גובה אנטנה וטווח מהסוג; סקטור = כיוון פנים ± זווית הסריקה (מערך מופע) או 360°
            var t = _rsTypeOf(typeKey), tp = (t && t.params) || {{}};  // הסוג
            var phased = tp.antenna_type === 'phased_array', ms = parseFloat(tp.max_scan_deg) || 60;  // מערך מופע
            return {{type_key: typeKey, type_name: t ? t.name : '', lat: ll ? ll.lat : null, lon: ll ? ll.lng : null, boresight_deg: 0,
                    h_antenna: tp.h_antenna != null ? tp.h_antenna : 10, range_km: tp.range_km != null ? tp.range_km : 50,
                    start_bearing_deg: phased ? (360 - ms) % 360 : 0, end_bearing_deg: phased ? ms : 360, angle_step_deg: 10,
                    reflectivity: tp.reflectivity || 'land', lobing_enabled: false, ridge_margin_deg: 0}};
        }}

        function _rsUniqueName(base) {{ var n = base, i = 2; while (_rs.sites.some(function(s) {{ return s.name === n; }})) {{ n = base + ' ' + i; i++; }} return n; }}  // שם פנוי

        function _rsTypeOptions(sel, current) {{
            // ממלא בורר סוג: הספרייה המובנית והפרופילים שלי
            sel.innerHTML = '';  // ניקוי
            if (_rtLib.length) {{ var g1 = L.DomUtil.create('optgroup', '', sel); g1.label = 'ספרייה מובנית — נתונים פומביים (נעול)';
                _rtLib.forEach(function(p) {{ var o = L.DomUtil.create('option', '', g1); o.value = 'lib:' + p.file; o.textContent = p.name; }}); }}
            if (_rtMyProfiles.length) {{ var g2 = L.DomUtil.create('optgroup', '', sel); g2.label = 'הפרופילים שלי (ניתן לעריכה)';
                _rtMyProfiles.forEach(function(p) {{ var o = L.DomUtil.create('option', '', g2); o.value = 'my:' + p.name; o.textContent = p.name; }}); }}
            if (current) sel.value = current;  // הנוכחי
            else {{  // T22 (F-054): בלי ברירת מחדל — המשתמש בוחר סוג בעצמו (קודם הסוג הפעיל מולא מראש וכך נשמר סוג שגוי)
                var ph = L.DomUtil.create('option', '', sel); ph.value = ''; ph.textContent = '— בחר סוג מכ"ם —'; ph.disabled = true;  // שורת הנחיה
                sel.insertBefore(ph, sel.firstChild); sel.value = '';  // ראשונה ונבחרת
            }}
        }}

        function _rsFillSiteSelect(sel) {{
            // ממלא בורר מכ"ם פעיל: "ידני", המכ"מים המוצבים, וכל הסוגים ("➕ מכ"ם חדש מסוג…" — בחירה יוצרת מכ"ם מוצב בלחיצה אחת)
            sel.innerHTML = '';  // ניקוי
            var o0 = L.DomUtil.create('option', '', sel); o0.value = ''; o0.textContent = '— ללא מכ"ם (ידני) —';  // ידני
            if (_rs.sites.length) {{ var gs = L.DomUtil.create('optgroup', '', sel); gs.label = 'המכ"מים המוצבים';  // קבוצה
                _rs.sites.forEach(function(s) {{ var o = L.DomUtil.create('option', '', gs); o.value = s.name; o.textContent = s.name + ' — ' + _rsTypeName(s); }}); }}  // כל מכ"ם
            if (_rtLib.length) {{ var gl = L.DomUtil.create('optgroup', '', sel); gl.label = '➕ מכ"ם חדש מסוג — ספרייה מובנית';  // כל סוגי הספרייה
                _rtLib.forEach(function(p) {{ var o = L.DomUtil.create('option', '', gl); o.value = 'new:lib:' + p.file; o.textContent = '➕ ' + p.name; }}); }}
            if (_rtMyProfiles.length) {{ var gm = L.DomUtil.create('optgroup', '', sel); gm.label = '➕ מכ"ם חדש מסוג — הפרופילים שלי';  // הסוגים שלי
                _rtMyProfiles.forEach(function(p) {{ var o = L.DomUtil.create('option', '', gm); o.value = 'new:my:' + p.name; o.textContent = '➕ ' + p.name; }}); }}
            if (!_rtLib.length) {{ var ow = L.DomUtil.create('option', '', sel); ow.disabled = true; ow.textContent = '(ספריית הסוגים נטענת…)'; }}  // עדיין לא נטען — לא רשימה ריקה בשקט
            sel.value = _rs.active;  // הפעיל
        }}

        function _rsMsg(t) {{ if (_rs.global) _rs.global.msg.textContent = t; }}  // הודעה בבורר הגלובלי

        function _rsQuickCreate(typeKey) {{
            // יצירת מכ"ם מוצב מסוג בלחיצה אחת: שם = שם הסוג (ייחודי), מיקום = המכ"ם הנוכחי, או לחיצה על המפה
            var t = _rsTypeOf(typeKey); if (!t) {{ _rsMsg('הסוג לא נמצא'); return; }}  // אין סוג
            var name = _rsUniqueName(t.name.replace(' (נתונים פומביים)', '').slice(0, 90)), params = _rsSiteDefaults(typeKey, radarObs);  // שם וברירות מחדל
            _rsSaveSite({{name: name, params: params}}).then(function() {{ _rsLoadSites(function() {{
                _rsActivate(name);  // הפעלה
                if (params.lat == null) {{ _rs.pick = true; map.getContainer().style.cursor = 'crosshair'; _rsMsg('נוצר "' + name + '" — לחץ על המפה למיקום המכ"ם'); }}  // בלי מיקום
                else _rsMsg('נוצר "' + name + '" במיקום המכ"ם הנוכחי (📍 מקם — להזזה)');  // עם מיקום
            }}); }});
        }}

        function _rsStatusText() {{
            // שורת המצב: סוג, נעילה, ומיקום
            var s = _rsActiveSite(); if (!s) return {{text: 'ידני: כל כלי עובד עם השדות שלו, כמו קודם.', color: '#555'}};  // ידני
            var t = _rsTypeOf(s.params.type_key);  // הסוג
            var where = (s.params.lat != null) ? Number(s.params.lat).toFixed(4) + ', ' + Number(s.params.lon).toFixed(4) : 'לא הוצב — "📍 מקם" או הצב בכלי המכ"ם';  // מיקום
            return {{text: (t && t.lib ? '🔒 ' : '✎ ') + 'סוג: ' + _rsTypeName(s) + (t && t.lib ? ' (ספרייה, נעול)' : t ? ' (שלי, ניתן לעריכה)' : ' (סוג חסר!)') + ' · מיקום: ' + where,
                    color: t ? '#15803d' : '#b91c1c'}};  // ירוק-כהה / אדום-כהה — עם סימן, לא רק צבע
        }}

        function _rsRefreshBars() {{
            // מעדכן את כל הפסים: הבורר, שורת המצב, "צופה נפרד", ואזור המקורות
            var st = _rsStatusText(), s = _rsActiveSite(), t = s ? _rsTypeOf(s.params.type_key) : null;  // המצב
            _rtActiveBars.forEach(function(b) {{
                _rsFillSiteSelect(b.sel);  // הבורר
                var det = b.detach && _rs.detached[b.detach];  // הכלי מנותק?
                b.status.textContent = det ? 'צופה נפרד: הכלי הזה עובד עם השדות והמיקום שלו.' : st.text;  // מצב
                b.status.style.color = det ? '#555' : st.color;  // צבע
                if (b.detachCb) b.detachCb.checked = !!det;  // תיבת הניתוק
                if (b.src) {{ var n = t && t.notes; if (n && (n.published || n.assumed_not_published)) {{ b.src.style.display = 'block'; b.srcBody.textContent = _rtNotesText(n); }} else b.src.style.display = 'none'; }}  // מקורות
                if (b.cloneBtn) b.cloneBtn.style.display = (t && t.lib) ? 'inline-block' : 'none';  // שכפל לעריכה — רק לסוג נעול
            }});
        }}

        function _rtRefreshActiveStatus() {{ _rsRefreshBars(); }}  // תאימות לאחור (נקרא מייבוא פרופיל)

        function _rtLoadLibrary(then) {{
            // טוען את ספריית הסוגים מהשרת פעם אחת
            if (_rtLibRequested) {{ if (then) then(); return; }} _rtLibRequested = true;  // פעם אחת
            fetch('http://localhost:5002/radar_profiles/library').then(function(r) {{ return r.json(); }})
            .then(function(d) {{ _rtLib = d.profiles || []; if (then) then(); _rsRefreshBars(); }})
            .catch(function() {{ _rtLibRequested = false; if (then) then(); }});  // כשל רשת — ינסה שוב
        }}

        function _rtOnMyProfilesChanged(stations) {{
            // נקרא מ-_buildStationUI בכל רענון של רשימת radar_profile — הסוגים "שלי" מתעדכנים
            _rtMyProfiles = stations || [];  // הרשימה
            _rsRefreshBars(); if (_rs.global && _rs.global.typeSel) _rsTypeOptions(_rs.global.typeSel, _rs.global.typeSel.value);  // תצוגה
        }}

        function _rsReloadMyTypes(then) {{
            // טוען מחדש את "הפרופילים שלי" (אחרי שכפול/ייבוא)
            fetch('http://localhost:5002/stations/list?tool=radar_profile').then(function(r) {{ return r.json(); }})
            .then(function(d) {{ _rtMyProfiles = d.stations || []; if (then) then(); }}).catch(function() {{ if (then) then(); }});
        }}

        function _rtBuildActiveBar(parent, opts) {{
            // פס מכ"ם פעיל בכלי (מסונכרן עם הבורר הגלובלי). opts.detach = 'los'/'radial' מוסיף "צופה נפרד"
            opts = opts || {{}};  // אפשרויות
            var wrap = L.DomUtil.create('div', '', parent);  // מסגרת
            wrap.style.cssText = 'border:1px solid #2ecc40;border-radius:3px;padding:2px 4px;background:#f3fcf5;display:flex;flex-direction:column;gap:2px;';  // בצבע כלי המכ"ם
            var row = L.DomUtil.create('label', '', wrap);  // שורת הבחירה
            row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#333;font-weight:bold;';  // פריסה
            row.title = 'המכ"ם הפעיל — כל הכלים עובדים עליו (פרט לנתוני המטרה ולשדות של ההצבה). ניהול הרשימה: בבורר העליון';  // הסבר
            L.DomUtil.create('span', '', row).textContent = '📡 מכ"ם פעיל';  // תווית
            var sel = L.DomUtil.create('select', '', row);  // הבורר
            sel.style.cssText = 'flex:1;min-width:0;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;min-height:24px;';  // T11 (F-040): ≥24px (היה 22); רוחב גמיש
            sel.setAttribute('aria-label', 'מכ"ם פעיל לכל הכלים');  // נגישות
            var status = L.DomUtil.create('div', '', wrap); status.style.cssText = 'font-size:8.5px;color:#555;';  // שורת המצב
            var b = {{sel: sel, status: status, detach: opts.detach || null}};  // המופע
            if (opts.detach) {{  // "צופה נפרד"
                var dl = L.DomUtil.create('label', '', wrap); dl.style.cssText = 'display:flex;align-items:center;gap:3px;font-size:8.5px;color:#555;';  // שורה
                var cb = L.DomUtil.create('input', '', dl); cb.type = 'checkbox';  // התיבה
                L.DomUtil.create('span', '', dl).textContent = 'צופה נפרד (לא לפי המכ"ם הפעיל)';  // תווית
                L.DomEvent.on(cb, 'change', function() {{ _rsSetDetached(opts.detach, cb.checked); }});  // ניתוק/חיבור
                b.detachCb = cb;  // לסנכרון
            }}
            if (opts.notes !== false) {{  // מה פורסם ומה הונח
                var src = L.DomUtil.create('details', '', wrap); src.style.cssText = 'font-size:8.5px;color:#555;display:none;';  // מקורות
                var ss = L.DomUtil.create('summary', '', src); ss.textContent = 'מה פורסם ומה הונח'; ss.style.cursor = 'pointer';  // כותרת
                var sb = L.DomUtil.create('div', '', src); sb.style.cssText = 'white-space:pre-wrap;direction:ltr;text-align:left;max-height:140px;overflow-y:auto;user-select:text;font-size:8px;';  // תוכן
                b.src = src; b.srcBody = sb;  // לסנכרון
            }}
            L.DomEvent.on(sel, 'change', function() {{  // בחירה
                if (sel.value.indexOf('new:') === 0) {{ var k = sel.value.substr(4); sel.value = _rs.active; _rsQuickCreate(k); return; }}  // סוג — יצירת מכ"ם חדש ממנו
                _rsActivate(sel.value);  // מכ"ם מוצב / ידני
            }});
            _rtActiveBars = _rtActiveBars || []; _rtActiveBars.push(b);  // רישום (גם אם נבנה לפני אתחול המשתנים)
            if (typeof _rs !== 'undefined' && _rs) _rsRefreshBars();  // תצוגה — אם המצב כבר אותחל; אחרת _rsInit ירענן
            return b;  // המופע
        }}

        function _rsDownload(name, text) {{
            // הורדת קובץ (בדסקטופ main.py פותח חלון שמירה)
            var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {{type: 'application/json'}})); a.download = name;  // קישור
            document.body.appendChild(a); a.click(); document.body.removeChild(a);  // הורדה
        }}

        function _rsExport() {{
            // ייצוא כל המכ"מים המוצבים + הסוגים "שלי" שהם משתמשים בהם (כדי שהקובץ יעבוד גם במכשיר אחר)
            var mine = {{}};  // סוגים שלי בשימוש
            _rs.sites.forEach(function(s) {{ var t = _rsTypeOf(s.params.type_key); if (t && !t.lib) mine[t.name] = t.params; }});
            var doc = {{format: 'maps-gui-radar-sites', version: 1, active: _rs.active, sites: _rs.sites.map(function(s) {{ return {{name: s.name, params: s.params}}; }}),
                       my_types: Object.keys(mine).map(function(n) {{ return {{name: n, params: mine[n]}}; }})}};  // המבנה
            _rsDownload('radar_sites.json', JSON.stringify(doc, null, 2));  // הורדה
        }}

        function _rsImport(text, done, fileName) {{
            // ייבוא: (1) קובץ פרופיל מכ"ם (maps-gui-radar-profile) — נוסף כסוג "שלי" ונוצר ממנו מכ"ם מוצב;
            // (2) קובץ מכ"מים מוצבים (maps-gui-radar-sites) — סוגים "שלי" ואז המכ"מים (שם קיים — מוחלף). מחזיר הודעה
            var doc; try {{ doc = JSON.parse(text); }} catch (e) {{ done('הקובץ אינו JSON תקין'); return; }}  // פענוח
            if (doc && doc.format === 'maps-gui-radar-profile' && doc.params && typeof doc.params === 'object') {{  // פרופיל בודד
                var nm = String(doc.name || (fileName || '').replace(/\\.json$/i, '') || 'פרופיל מיובא').trim().slice(0, 100);  // שם הסוג
                fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{tool: 'radar_profile', name: nm, params: doc.params}})}})
                .then(function() {{ _rsReloadMyTypes(function() {{ _rsRefreshBars(); _rsQuickCreate('my:' + nm); done('נוסף הסוג "' + nm + '" ל"הפרופילים שלי" ונוצר ממנו מכ"ם ✔'); }}); }})
                .catch(function() {{ done('שמירת הסוג נכשלה (השרת לא זמין?)'); }});
                return;
            }}
            if (!doc || doc.format !== 'maps-gui-radar-sites' || !Array.isArray(doc.sites)) {{ done('זה לא קובץ מכ"ם של maps-gui (פרופיל או מכ"מים מוצבים)'); return; }}  // סוג
            var jobs = [];  // שמירות
            (doc.my_types || []).forEach(function(t) {{ if (t && t.name && t.params) jobs.push(fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{tool: 'radar_profile', name: t.name, params: t.params}})}})); }});
            var n = 0;  // כמה מכ"מים
            doc.sites.forEach(function(s) {{ if (s && s.name && s.params && s.params.type_key) {{ n++; jobs.push(_rsSaveSite({{name: String(s.name).slice(0, 100), params: s.params}})); }} }});
            Promise.all(jobs).then(function() {{ _rsReloadMyTypes(function() {{ _rsLoadSites(function() {{ done('נטענו ' + n + ' מכ"מים ✔'); }}); }}); }});  // רענון
        }}

        function _rsClone() {{
            // "שכפל לעריכה": עותק של סוג מהספרייה תחת "הפרופילים שלי", והמכ"ם הפעיל עובר אליו (שדות פתוחים)
            var s = _rsActiveSite(), t = s ? _rsTypeOf(s.params.type_key) : null; if (!t || !t.lib) return;  // רק סוג נעול
            var name = prompt('שם לעותק הניתן לעריכה:', t.name.replace(' (נתונים פומביים)', '') + ' (עותק)'); if (!name) return;  // שם
            name = name.trim().slice(0, 100); if (!name) return;  // תקין
            var params = JSON.parse(JSON.stringify(t.params));  // עותק מלא של הסוג
            fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{tool: 'radar_profile', name: name, params: params}})}})
            .then(function() {{ _rsReloadMyTypes(function() {{ s.params.type_key = 'my:' + name; s.params.type_name = name; _rsSaveSite(s); _rsActivate(s.name); }}); }});  // מעבר לעותק
        }}

        function _rsBuildGlobalBar() {{
            // הבורר הגלובלי הקבוע בראש המפה: מכ"ם פעיל + ניהול הרשימה (חדש/עריכה/מחיקה/שכפול/ייצוא/ייבוא)
            // FR-D-288 (תיקון): פקד Leaflet בפינה השמאלית-עליונה (מתחת לזום ול-Undo) — Leaflet מסדר את הפקדים בעמודה,
            // ולכן אין חפיפה עם הזום או עם הפאנלים בצד ימין (קודם: div צף במרכז, שעלה על פקדים אחרים)
            var box = L.DomUtil.create('div', 'leaflet-control');  // מיכל
            box.style.cssText = 'background:white;border:1px solid #2ecc40;border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,0.35);padding:3px 6px;' +
                'font-family:Arial;direction:rtl;width:300px;max-width:300px;display:flex;flex-direction:column;gap:2px;';  // רוחב קבוע — לא מתרחב לפי טקסט ארוך
            var RsCtl = L.Control.extend({{options: {{position: 'topleft'}}, onAdd: function() {{ return box; }}}});  // הפקד
            new RsCtl().addTo(map);  // מתחת לפקדים הקיימים בפינה
            L.DomEvent.disableClickPropagation(box); L.DomEvent.disableScrollPropagation(box);  // לא מגיע למפה
            var bar = _rtBuildActiveBar(box, {{notes: true}});  // אותו פס כמו בכלים
            var disc = L.DomUtil.create('div', '', box);  // T1 (F-036, Q-R5-2): הבהרה בולטת ליד בורר המכ"מים
            disc.textContent = 'ℹ️ שמות המוצרים שייכים לבעליהם; אין קשר ליצרנים ואין אישור מהם. הערכים משוערים מנתונים פומביים, ואינם מפרט רשמי.';  // T1: נוסח ההבהרה
            disc.style.cssText = 'font-size:9px;color:#6b4f00;background:#fff8e1;border:1px solid #ffe08a;border-radius:3px;padding:1px 4px;line-height:1.3;';  // T1: רקע צהוב עדין — בולט אבל לא מפריע
            var btns = L.DomUtil.create('div', '', box); btns.style.cssText = 'display:flex;gap:3px;flex-wrap:wrap;';  // כפתורים
            function mk(txt, tip, fn) {{ var x = L.DomUtil.create('button', '', btns); x.textContent = txt; x.title = tip; x.setAttribute('aria-label', tip);
                x.style.cssText = 'font-size:10px;min-height:24px;padding:1px 6px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
                L.DomEvent.on(x, 'click', function(e) {{ L.DomEvent.stopPropagation(e); fn(); }}); return x; }}  // כפתור
            var msg = L.DomUtil.create('div', '', box); msg.style.cssText = 'font-size:9px;color:#555;';  // הודעות
            var ed = L.DomUtil.create('div', '', box); ed.style.cssText = 'display:none;flex-direction:column;gap:3px;border-top:1px solid #ddd;padding-top:3px;';  // עורך
            var nameIn = L.DomUtil.create('input', '', ed); nameIn.type = 'text'; nameIn.placeholder = 'שם המכ"ם המוצב'; nameIn.setAttribute('aria-label', 'שם המכ"ם המוצב');  // שם
            nameIn.style.cssText = 'font-size:11px;padding:2px 4px;border:1px solid #ccc;border-radius:3px;direction:rtl;min-height:24px;';  // T11 (F-040): יעד לחיצה ≥24px (היה 22)
            var typeSel = L.DomUtil.create('select', '', ed); typeSel.setAttribute('aria-label', 'סוג המכ"ם'); typeSel.style.cssText = 'font-size:10px;min-height:24px;';  // T11 (F-040): ≥24px (היה 22); סוג
            var edRow = L.DomUtil.create('div', '', ed); edRow.style.cssText = 'display:flex;gap:3px;';  // שמירה/ביטול
            var saveB = L.DomUtil.create('button', '', edRow), cancelB = L.DomUtil.create('button', '', edRow);  // הכפתורים
            saveB.textContent = '✔ שמור'; cancelB.textContent = 'ביטול';
            [saveB, cancelB].forEach(function(x) {{ x.style.cssText = 'flex:1;font-size:10px;min-height:24px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;'; }});
            var fileIn = L.DomUtil.create('input', '', box); fileIn.type = 'file'; fileIn.accept = '.json'; fileIn.style.display = 'none';  // בורר קבצים לייבוא
            function openEditor(site) {{  // עורך: חדש (site=null) או עריכה
                _rs.editing = site; ed.style.display = 'flex'; _rsTypeOptions(typeSel, site ? site.params.type_key : '');  // T22 (F-054): מכ"ם חדש — סוג ריק, חובה לבחור (עריכה — הסוג הקיים)
                nameIn.value = site ? site.name : _rsUniqueName('מכ"ם ' + (_rs.sites.length + 1)); nameIn.focus();
            }}
            mk('➕ חדש', 'הוספת מכ"ם מוצב: שם וסוג. המיקום — המכ"ם הנוכחי, או לחיצה על המפה', function() {{ _rtLoadLibrary(function() {{ openEditor(null); }}); }});
            mk('✏️ עריכה', 'שינוי שם או סוג של המכ"ם הפעיל', function() {{ var s = _rsActiveSite(); if (!s) {{ msg.textContent = 'בחר קודם מכ"ם פעיל'; return; }} openEditor(s); }});
            mk('📍 מקם', 'הלחיצה הבאה על המפה קובעת את מיקום המכ"ם הפעיל', function() {{ if (!_rsActiveSite()) {{ msg.textContent = 'בחר קודם מכ"ם פעיל'; return; }}
                _rs.pick = true; map.getContainer().style.cursor = 'crosshair'; msg.textContent = 'לחץ על המפה למיקום המכ"ם'; }});
            bar.cloneBtn = mk('⧉ שכפל לעריכה', 'יוצר עותק פתוח לעריכה של הסוג (תחת "הפרופילים שלי") ומעביר אליו את המכ"ם הפעיל', _rsClone);
            mk('🗑 מחק', 'מחיקת המכ"ם הפעיל מהרשימה', function() {{ var s = _rsActiveSite(); if (!s) return; if (!confirm('למחוק את "' + s.name + '"?')) return;
                fetch('http://localhost:5002/stations/delete', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{tool: 'radar_sites', name: s.name}})}})
                .then(function() {{ _rsLoadSites(function() {{ _rsActivate(''); }}); }}); }});
            mk('⬇ ייצוא', 'ייצוא כל המכ"מים המוצבים לקובץ JSON (גם לאנדרואיד)', _rsExport);
            mk('⬆ ייבוא', 'ייבוא JSON: קובץ פרופיל מכ"ם (נוסף כסוג ונוצר ממנו מכ"ם) או קובץ מכ"מים מוצבים. אפשר כמה קבצים', function() {{ fileIn.click(); }});
            fileIn.multiple = true;  // אפשר לבחור כמה קבצי פרופיל בבת אחת
            L.DomEvent.on(fileIn, 'change', function() {{
                var files = Array.from(fileIn.files || []); fileIn.value = ''; if (!files.length) return;  // הקבצים שנבחרו
                var msgs = [];  // הודעה לכל קובץ
                (function next(i) {{  // אחד אחרי השני — כדי שהשמירות לא יתנגשו
                    if (i >= files.length) {{ msg.textContent = msgs.join(' | '); return; }}  // סיום
                    var rd = new FileReader();
                    rd.onload = function() {{ _rtLoadLibrary(function() {{ _rsImport(String(rd.result), function(m) {{ msgs.push(files[i].name + ': ' + m); next(i + 1); }}, files[i].name); }}); }};
                    rd.readAsText(files[i]);  // קריאה
                }})(0);
            }});
            L.DomEvent.on(cancelB, 'click', function(e) {{ L.DomEvent.stopPropagation(e); ed.style.display = 'none'; _rs.editing = null; }});
            L.DomEvent.on(saveB, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                var name = nameIn.value.trim().slice(0, 100), key = typeSel.value; if (!name || !key) {{ msg.textContent = 'נדרשים שם וסוג'; return; }}  // ולידציה
                var old = _rs.editing;  // עריכה או חדש
                if (!old && _rs.sites.some(function(s) {{ return s.name === name; }})) {{ msg.textContent = 'השם כבר קיים'; return; }}  // כפילות
                var params = old ? JSON.parse(JSON.stringify(old.params)) : _rsSiteDefaults(key, radarObs);  // פרמטרים
                if (old && old.params.type_key !== key) {{ var t = _rsTypeOf(key); params.type_key = key; params.type_name = t ? t.name : ''; }}  // סוג חדש — ההצבה נשמרת
                var after = function() {{ _rsLoadSites(function() {{ _rsActivate(name); if (params.lat == null) {{ _rs.pick = true; map.getContainer().style.cursor = 'crosshair'; msg.textContent = 'לחץ על המפה למיקום המכ"ם'; }} else msg.textContent = '✔ נשמר'; }}); }};
                var save = function() {{ _rsSaveSite({{name: name, params: params}}).then(after); }};  // שמירה
                if (old && old.name !== name) fetch('http://localhost:5002/stations/delete', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{tool: 'radar_sites', name: old.name}})}}).then(save); else save();  // שינוי שם = מחיקה + שמירה
                ed.style.display = 'none'; _rs.editing = null;  // סגירת העורך
            }});
            _rs.global = {{box: box, msg: msg, typeSel: typeSel}};  // לסנכרון
        }}

        function _rsPickClick(latlng) {{
            // לחיצה על המפה במצב "📍 מקם": מיקום המכ"ם הפעיל. מחזיר true אם הלחיצה טופלה כאן
            if (!_rs.pick) return false;  // לא במצב מיקום
            _rs.pick = false; map.getContainer().style.cursor = '';  // יציאה מהמצב
            var s = _rsActiveSite(); if (!s) return true;  // אין פעיל
            s.params.lat = latlng.lat; s.params.lon = latlng.lng; _rsSaveSite(s);  // המיקום
            _rsMoveObservers(latlng, null); _rsRefreshBars();  // הצופים + תצוגה
            if (_rs.global) _rs.global.msg.textContent = '✔ המכ"ם הוצב';  // משוב
            return true;  // טופל
        }}

        function _rsLosSnapshot() {{
            // מגבלות המכ"ם לקו ראייה נקודתי (נלכד ביצירת הצמד): סקטור, טווח, טווח מינימלי, שדה ראייה אנכי
            var s = _rsActiveSite(); if (!s || _rs.detached.los) return null;  // ידני / מנותק
            var t = _rsTypeOf(s.params.type_key), tp = (t && t.params) || {{}};  // הסוג
            return {{label: s.name + ' (' + _rsTypeName(s) + ')', boresight: parseFloat(s.params.boresight_deg) || 0, antenna: tp.antenna_type || 'generic',
                    maxScan: parseFloat(tp.max_scan_deg) || 180, range: parseFloat(s.params.range_km) || 0, minRange: parseFloat(tp.min_range_km) || 0,
                    vc: parseFloat(tp.vertical_center_deg) || 0, vw: tp.vertical_width_deg != null ? parseFloat(tp.vertical_width_deg) : 180}};
        }}

        function _rsLosLimitsText(session) {{
            // שורת מגבלות המכ"ם לצמד קו-ראייה: בסקטור? בטווח? מעל הטווח המינימלי? בשדה האנכי? (גיאומטריה — משוואת המכ"ם בכלי הדופלר)
            // FR-D-290: הגזרה נלקחת מהשדות (גזרת המכ"ם שהמשתמש הגדיר) — גם בלי מכ"ם פעיל; גובה הבחינה ומרווח הרכס מוצגים
            var r = session.rs, d = session.data, sec = session.sec; if (!d) return '';  // אין תוצאה
            var hasSec = sec && _rsSectorSpan(sec.start, sec.end) !== 0;  // הוגדרה גזרה (לא 360°)
            if (!r && !hasSec && !session.tgtTxt) return '';  // ידני בלי גזרה — אין מה להציג
            var km = d.total_km, parts = [], brg = (_bearingDeg(session.obsMk.getLatLng(), session.tgtMk.getLatLng()) + 360) % 360;  // מרחק וכיוון
            if (hasSec) parts.push(_rsInSector(brg, sec.start, sec.end) ? 'בגזרה ✔' : 'מחוץ לגזרה ✖ (' + brg.toFixed(0) + '°, גזרה ' + sec.start + '°–' + sec.end + '°)');  // גזרה
            else if (r && r.antenna === 'phased_array') {{ var off = Math.abs(((brg - r.boresight + 540) % 360) - 180);  // בלי גזרה — סטייה מכיוון הפנים
                parts.push(off <= r.maxScan ? 'בסקטור ✔' : 'מחוץ לסקטור ✖ (' + off.toFixed(0) + '°)'); }}
            var tail = ' | גובה בחינה ' + (session.tgtTxt || '') + (session.margin ? ' · מרווח רכס ' + session.margin + '°' : '');  // גובה ומרווח
            if (!r) return '📐 ' + (parts.length ? parts.join(' · ') : 'ללא מכ"ם') + tail;  // ידני — גזרה וגובה בלבד
            parts.push(km <= r.range ? 'בטווח ✔' : 'מעבר לטווח ✖ (' + km + ' > ' + r.range + ' ק"מ)');  // טווח
            if (km < r.minRange) parts.push('בתוך הטווח המינימלי ✖');  // אזור מת
            var dM = km * 1000, drop = dM * dM / (2 * 6371000) * (1 - 0.13);  // עקמומיות פחות שבירה — אותה נוסחה כמו radar_track.curvature_drop_m
            var el = Math.atan2((d.target_h - d.observer_h) - drop, Math.max(dM, 1)) * 180 / Math.PI;  // זווית העילוי ליעד
            var lo = r.vc - r.vw / 2, hi = r.vc + r.vw / 2;  // גבולות השדה האנכי
            parts.push((el >= lo && el <= hi ? 'עילוי ' + el.toFixed(1) + '° בשדה ✔' : 'עילוי ' + el.toFixed(1) + '° מחוץ לשדה האנכי ✖'));  // שדה אנכי
            return '📡 ' + r.label + ': ' + parts.join(' · ') + tail;  // השורה (+ גובה הבחינה ומרווח הרכס, FR-D-290)
        }}

        function _rsInit() {{
            // אתחול אחרי שכל הכלים נבנו: הספרייה, הסוגים שלי, המכ"מים המוצבים, ושחזור המכ"ם הפעיל מההפעלה הקודמת
            try {{ var d = JSON.parse(localStorage.getItem('rs_detached') || 'null'); if (d) _rs.detached = {{los: !!d.los, radial: !!d.radial}}; }} catch (e) {{}}  // ניתוק שמור
            _rsBuildGlobalBar(); _rtHookActiveFields();  // הבורר הגלובלי + מאזינים
            _rsInitLoad(0);  // טעינה (עם ניסיונות חוזרים)
        }}

        function _rsInitLoad(attempt) {{
            // טוען ספרייה, סוגים שלי ומכ"מים מוצבים. השרת המקומי עולה במקביל למפה — אם עוד לא ענה, מנסים שוב כל 2 שנ' (עד 30 פעם)
            _rtLoadLibrary(function() {{ _rsReloadMyTypes(function() {{ _rsLoadSites(function() {{
                _rs.sitesLoaded = true;  // הרשימה נטענה
                try {{ localStorage.removeItem('rs_active'); }} catch (e) {{}}  // T22 (F-054): מוחקים בחירה שנשמרה בגרסאות קודמות — לא משחזרים אותה
                _rsRefreshBars();  // T22: תמיד מתחילים ב"ללא מכ"ם (ידני)"; בחירה בסשן הזה נשארת עד סגירה
            }}); }}); }});
            setTimeout(function() {{  // בדיקה: האם הכל נטען?
                if ((!_rtLib.length || !_rs.sitesLoaded) && attempt < 30) {{ _rtLibRequested = false; _rsInitLoad(attempt + 1); }}  // עוד לא — שוב
                else if (_rs.active) _rsActivate(_rs.active);  // נטען — מחילים שוב את המכ"ם הפעיל (אם נבחר לפני שהסוג נטען)
            }}, 2000);
        }}
        setTimeout(_rsInit, 0);  // אחרי שכל הסקריפט רץ וכל הכלים נבנו

        // ── שלב ב': הצעת מיקום עם מפת חום ──
        var _rtPlace = {{layers: [], jobId: null, timer: null}};  // שדות, שכבות ומצב ה-job
        // סולם רציף בגוון אחד (כחול), בהיר = נמוך, כהה = גבוה — הצעדים 100..700 של הפלטה הרציפה (dataviz)
        var _RT_SEQ = ['#cce3fd', '#9dc8f7', '#6aabf1', '#338ced', '#2370cd', '#1757ac', '#0e3d7e'];

        function _rtSeqColor(t) {{
            // צבע לערך מנורמל t∈[0,1] — אינטרפולציה ליניארית בין צעדי הסולם
            t = Math.max(0, Math.min(1, t));  // צמידה
            var x = t * (_RT_SEQ.length - 1), i = Math.min(_RT_SEQ.length - 2, Math.floor(x)), f = x - i;  // מיקום בסולם
            function rgb(h) {{ return [parseInt(h.substr(1, 2), 16), parseInt(h.substr(3, 2), 16), parseInt(h.substr(5, 2), 16)]; }}  // hex -> rgb
            var a = rgb(_RT_SEQ[i]), b = rgb(_RT_SEQ[i + 1]);  // שני הצעדים
            return 'rgb(' + a.map(function(v, k) {{ return Math.round(v + f * (b[k] - v)); }}).join(',') + ')';  // הצבע
        }}

        function _rtPlacementClear() {{
            // מסיר את מפת החום והסימונים, ומסתיר את המקרא
            _rtPlace.layers.forEach(function(l) {{ map.removeLayer(l); }});  // הסרה
            _rtPlace.layers = [];  // איפוס
            if (_rtPlace.legend) _rtPlace.legend.style.display = 'none';  // מקרא
        }}

        function _rtPlacementCancel() {{
            // מבטל חישוב שרץ (השרת עוצר בין בקשות/מיקומים)
            if (_rtPlace.timer) {{ clearInterval(_rtPlace.timer); _rtPlace.timer = null; }}  // polling
            if (_rtPlace.jobId) fetch('http://localhost:5002/radar_doppler/cancel?job_id=' + _rtPlace.jobId, {{method: 'POST'}}).catch(function() {{}});  // ביטול בשרת
            _rtPlace.jobId = null;  // אין job
            if (_rtPlace.info) _rtPlace.info.textContent = 'בוטל.';  // משוב
        }}

        function _rtPlacementRun() {{
            // מפעיל הצעת מיקום: מרכז = המכ"ם הנוכחי, מסלול = של הבדיקה האחרונה (כולל המקור וייחוס הגובה)
            if (!radarObs) {{ alert('הצב קודם מכ"ם על המפה עם כלי "תצפית מכ\\"ם דופלר" (🎯) — החיפוש סביבו'); return; }}  // אין מרכז
            if (!_radarTrackLastPath) {{ alert('הרץ קודם "🎯 בדוק מעקב מכ\\"ם" — מפת החום נבנית על המסלול של הבדיקה האחרונה'); return; }}  // אין מסלול
            _rtPlacementCancel(); _rtPlacementClear();  // מנקה הרצה קודמת
            function num(el, d) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? d : v; }}  // ערך או ברירת מחדל
            var opts = _radarTrackLastOpts || {{}};  // המקור של הבדיקה האחרונה
            var body = Object.assign(_radarCommonBody(), _radarTrackScanBody(), _rtEnvBody(), {{  // אותם פרמטרים כמו בבדיקה
                lat: radarObs.lat, lon: radarObs.lng, radius_km: num(_rtPlace.radius, 3), step_m: num(_rtPlace.step, 500),
                metric: _rtPlace.metric ? _rtPlace.metric.value : 'warning', alt_ref: opts.alt_ref || 'msl',
                trajectory: _radarTrackLastPath.map(function(p) {{ return {{t: p.t, lat: p.lat, lon: p.lon, alt: (p.alt != null ? p.alt : p.alt_msl)}}; }})
            }});
            if (opts.rcs_m2) body.rcs_m2 = opts.rcs_m2;  // RCS לפי סוג מטוס (FR24), כמו בבדיקה
            _rtPlace.profileLbl = _rtActiveLabel();  // FR-D-286: הפרופיל שהיה פעיל בתחילת החישוב — לסיכום ולפופאפים
            _rtPlace.info.textContent = '🗺 מתחיל…';  // משוב
            fetch('http://localhost:5002/radar_track/placement/start', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(body)}})
            .then(function(r) {{ return r.json().then(function(d) {{ if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }}); }})  // שגיאה עם הסבר
            .then(function(d) {{
                _rtPlace.jobId = d.job_id;  // ה-job
                _rtPlace.info.textContent = '🗺 ' + d.candidates + ' מיקומים — מתחיל…';  // משוב
                _rtPlace.timer = setInterval(_rtPlacementPoll, 1000);  // polling
            }})
            .catch(function(e) {{ _rtPlace.info.textContent = '🗺 שגיאה: ' + e.message; }});  // הודעה
        }}

        function _rtPlacementPoll() {{
            // מצב ה-job: הודעת התקדמות, ובסיום — ציור
            if (!_rtPlace.jobId) return;  // אין job
            var jobId = _rtPlace.jobId;  // נשמר — מתעלמים מתשובה ל-job שהוחלף
            fetch('http://localhost:5002/radar_doppler/status?job_id=' + jobId)
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                if (jobId !== _rtPlace.jobId) return;  // הוחלף
                if (d.status === 'running') {{  // עדיין רץ
                    var prog = d.batches_total ? ' (' + d.batches_done + '/' + d.batches_total + ')' + _rtEtaText(d) : '';  // שליפה + הערכת זמן (T23)
                    _rtPlace.info.textContent = '🗺 ' + (d.note || 'מחשב…') + (d.note && d.note.indexOf('שולף') === 0 ? prog : '');  // הודעה
                    return;  // ממתין
                }}
                clearInterval(_rtPlace.timer); _rtPlace.timer = null; _rtPlace.jobId = null;  // הסתיים
                if (d.status === 'done') _rtPlacementDraw(d.result);  // ציור
                else if (d.status === 'error') _rtPlace.info.textContent = '🗺 שגיאה: ' + (d.error || 'לא ידועה');  // שגיאה
                _rtRevealResult(_rtPlace.info);  // T23: גלילה לתוצאה/לשגיאה
            }})
            .catch(function() {{}});  // כשל רשת בבדיקה בודדת — ה-tick הבא ינסה שוב
        }}

        function _rtPlacementDraw(res) {{
            // מפת חום: תא לכל מיקום בצבע הציון (סולם כחול רציף), ריחוף = ציון, לחיצה = "הצב מכ"ם כאן";
            // המיקום המיטבי מסומן בכוכב עם תווית, ו-2..5 בטבעת ממוספרת — הזיהוי לא נשען על צבע בלבד
            _rtPlacementClear();  // ניקוי
            var unit = res.metric === 'coverage' ? '%' : ' שנ\\'';  // יחידת הציון
            var name = res.metric === 'coverage' ? (res.track_mode === 'track' ? 'במעקב' : 'כיסוי') : 'זמן התרעה';  // שם הציון
            var ok = res.candidates.filter(function(c) {{ return c.score != null; }});  // מחושבים
            if (!ok.length) {{ _rtPlace.info.textContent = '🗺 אין מיקומים מחושבים (חסרים נתוני גובה)'; return; }}  // אין
            var lo = Math.min.apply(null, ok.map(function(c) {{ return c.score; }}));  // מינימום
            var hi = Math.max.apply(null, ok.map(function(c) {{ return c.score; }}));  // מקסימום
            var half = res.step_m / 2, cosLat = Math.cos(res.center.lat * Math.PI / 180);  // חצי תא, ותיקון אורך
            ok.forEach(function(c) {{  // כל מיקום
                var dLat = half / 111194.9, dLon = half / (111194.9 * cosLat);  // חצי תא במעלות
                var rect = L.rectangle([[c.lat - dLat, c.lon - dLon], [c.lat + dLat, c.lon + dLon]], {{
                    color: '#ffffff', weight: 1, fillColor: _rtSeqColor(hi > lo ? (c.score - lo) / (hi - lo) : 1), fillOpacity: 0.6}}).addTo(map);  // תא, עם מרווח לבן דק בין תאים
                rect.bindTooltip(name + ': ' + c.score + unit + ' | קרקע ' + c.ground_m + ' מ\\'', {{sticky: true}});  // ריחוף
                var pop = L.DomUtil.create('div', '');  // פופאפ עם כפתור
                pop.style.cssText = 'direction:rtl;font-family:Arial;font-size:12px;';  // עיצוב
                L.DomUtil.create('div', '', pop).textContent = name + ': ' + c.score + unit;  // הציון
                L.DomUtil.create('div', '', pop).textContent = 'כיסוי פיזיקלי: ' + c.coverage_pct + '% | גובה קרקע: ' + c.ground_m + ' מ\\'';  // פרטים
                var pl = L.DomUtil.create('div', '', pop); pl.textContent = _rtPlace.profileLbl || ''; pl.style.color = '#666';  // FR-D-286: הפרופיל (textContent — בלי HTML)
                var b = L.DomUtil.create('button', '', pop); b.textContent = '📍 הצב מכ"ם כאן ובדוק';  // פעולה
                b.style.cssText = 'margin-top:4px;font-size:11px;cursor:pointer;';  // עיצוב
                L.DomEvent.on(b, 'click', function() {{ map.closePopup(); _placeRadarObserver(L.latLng(c.lat, c.lon)); }});  // הצבה — הבדיקה הרגילה רצה מחדש מהמיקום (FR-D-266)
                rect.bindPopup(pop);  // לחיצה
                _rtPlace.layers.push(rect);  // לניקוי
            }});
            res.best.forEach(function(c, i) {{  // המיקומים הטובים
                var mk = i === 0
                    ? L.marker([c.lat, c.lon], {{icon: L.divIcon({{html: '<div style="font-size:20px;line-height:20px;">⭐</div>', className: '', iconSize: [20, 20], iconAnchor: [10, 10]}})}})  // המיטבי
                    : L.circleMarker([c.lat, c.lon], {{radius: 8, color: '#111', weight: 2, fill: false}});  // 2..5
                mk.bindTooltip((i === 0 ? '⭐ מיטבי: ' : '#' + (i + 1) + ': ') + c.score + unit, {{permanent: i === 0, direction: 'top'}});  // תווית
                mk.on('click', function() {{ _placeRadarObserver(L.latLng(c.lat, c.lon)); }});  // הצבה ישירה
                mk.addTo(map); _rtPlace.layers.push(mk);  // לניקוי
            }});
            var dem = res.dem, b0 = res.best[0];  // נתונים לסיכום
            _rtPlace.info.textContent = '📡 ' + (_rtPlace.profileLbl || '') + '\\n' +  // FR-D-286: לפי איזה פרופיל
                '🗺 ' + ok.length + ' מיקומים | המיטבי: ' + name + ' ' + b0.score + unit +
                ' (קרקע ' + b0.ground_m + ' מ\\')\\nרשת גבהים: ' + dem.nodes + ' נקודות, ~' + dem.res_m + ' מ\\' (' + dem.cached + ' מהמטמון)' +
                '\\nלחץ על תא או על ⭐ כדי להציב שם את המכ"ם ולהריץ בדיקה מדויקת.';  // סיכום
            var cv = _rtPlace.legend; cv.style.display = 'block';  // מקרא
            var W = 250, H = 30, dpr = window.devicePixelRatio || 1;  // מידות
            cv.width = W * dpr; cv.height = H * dpr;  // רזולוציה
            var ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);  // הכנה
            for (var x = 0; x < W - 8; x++) {{ ctx.fillStyle = _rtSeqColor(1 - x / (W - 9)); ctx.fillRect(4 + x, 2, 1, 12); }}  // פס הסולם: נמוך מימין, גבוה משמאל (RTL)
            ctx.fillStyle = '#333'; ctx.font = '9px Arial';  // טקסט בצבע טקסט, לא בצבע הסדרה
            ctx.textAlign = 'right'; ctx.fillText(lo + unit, W - 4, 26);  // מינימום (ימין)
            ctx.textAlign = 'left'; ctx.fillText(hi + unit, 4, 26);  // מקסימום (שמאל)
            ctx.textAlign = 'center'; ctx.fillText(name, W / 2, 26);  // שם הציון
        }}

        function _rtRunRocket(infoEl, timelineEl) {{
            // שלב א6: מחשב קודם מסלול רקטה בשרת (/ballistics/rocket), מצייר אותו, ואז מריץ עליו את בדיקת המעקב
            if (!radarObs) {{ alert('הצב קודם מכ"ם על המפה עם כלי "תצפית מכ\\"ם דופלר" (🎯)'); return; }}  // אין מכ"ם
            var gt = _ballisticsGetGunTarget();  // המשגר (התותח שהוצב)
            if (!gt || !gt.gun) {{ alert('הצב קודם משגר — "✏️ תותח" בכלי הבליסטי'); return; }}  // אין משגר
            var altMsg = _ballisticsAltGuard(false);  // T21 (F-053): גובה המשגר חייב להיות ידוע
            if (altMsg) {{ alert(altMsg); return; }}  // T21: אין חישוב רקטה מגובה 0 בשקט
            function num(el, d) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? d : v; }}  // ערך או ברירת מחדל
            var rocket = {{mass_kg: num(_rtSrc.rkMass, 40), prop_kg: num(_rtSrc.rkProp, 12), burn_s: num(_rtSrc.rkBurn, 2),
                          thrust_n: num(_rtSrc.rkThrust, 12000), diam_m: num(_rtSrc.rkDiam, 0.15), cd: num(_rtSrc.rkCd, 0.4)}};  // הפרמטרים
            var common = _ballisticsGetCommonParams() || {{}};  // המטאו שנבחר בפאנל
            if (infoEl) infoEl.textContent = '🚀 מחשב מסלול רקטה…';  // משוב
            fetch('http://localhost:5002/ballistics/rocket', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{gun: gt.gun, elev_deg: num(_rtSrc.rkElev, 45), azimuth_deg: num(_rtSrc.rkAz, 0), rocket: rocket, met: common.met}})}})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                if (!d.ok) {{ if (infoEl) infoEl.textContent = '🚀 ' + (d.message || d.error || 'שגיאה'); return; }}  // שגיאה מהמודל
                if (_rtSrc.rocketLayer) map.removeLayer(_rtSrc.rocketLayer);  // מסלול רקטה קודם
                _rtSrc.rocketLayer = L.polyline(d.path.map(function(p) {{ return [p.lat, p.lon]; }}), {{color: '#cba6f7', weight: 3, dashArray: '6,4'}}).addTo(map);  // המסלול, מקווקו סגול
                var label = 'רקטה: טווח ' + (d.impact.range_m / 1000).toFixed(1) + ' ק"מ, שיא ' + Math.round(d.apex ? d.apex.alt_m : 0) + ' מ\\', ' +
                            'סוף בעירה בשנ\\' ' + d.burnout.t + ' ב-' + Math.round(d.burnout.v_ms) + ' מ\\'/ש\\'';  // תיאור לסיכום
                _radarTrackRun(d.path.map(function(p) {{ return {{t: p.t, lat: p.lat, lon: p.lon, alt: p.alt_msl}}; }}), infoEl, timelineEl,
                               {{source: 'rocket', alt_ref: 'msl', label: label}});  // בדיקת המעקב
            }})
            .catch(function(e) {{ if (infoEl) infoEl.textContent = '🚀 שגיאת רשת: ' + e.message; }});  // רשת
        }}

        function _rtRunFromSource(infoEl, timelineEl) {{
            // כפתור "בדוק מעקב מכ"ם": בונה את המסלול מהמקור שנבחר ומריץ
            if (_rtSrc.sel && _rtSrc.sel.value === 'rocket') {{ _rtRunRocket(infoEl, timelineEl); return; }}  // רקטה — אסינכרוני (חישוב בשרת)
            var b = _rtBuildTrajectory();  // המסלול
            if (!b) return;  // T29: אין מסלול (ההודעה כבר הוצגה)
            if (radarObs && _rtFarWarning(b.points, infoEl)) return;  // T29 (החלטה 5): המכ"ם רחוק מכל המסלול — המשתמש בחר לא להמשיך
            _radarTrackRun(b.points, infoEl, timelineEl, b.opts);  // הרצה
        }}

        function _rtFarWarning(points, infoEl) {{  // T29: אזהרה לפני בדיקה כשהמכ"ם רחוק מכל נקודה במסלול יותר מהטווח שלו. true = לא להמשיך
            var rk = parseFloat(_radarRangeInput && _radarRangeInput.value);  // טווח המכ"ם [ק"מ] מכלי הדופלר (או מהמכ"ם הפעיל)
            if (!(rk > 0) || !points || !points.length) return false;  // אין טווח/מסלול — לא מזהירים
            var dmin = Infinity;  // המרחק הקרוב ביותר
            points.forEach(function(p) {{ var d = map.distance(radarObs, L.latLng(p.lat, p.lon)); if (d < dmin) dmin = d; }});  // לכל נקודה
            if (dmin <= rk * 1000) return false;  // יש נקודה בטווח — בלי אזהרה
            var go = confirm('⚠️ המכ"ם רחוק מכל נקודה במסלול: ' + (dmin / 1000).toFixed(1) + ' ק"מ, והטווח שלו ' + rk + ' ק"מ. הבדיקה כנראה תסתיים בלי גילוי (ושליפת השטח לוקחת זמן). להמשיך בכל זאת?');  // שאלה
            if (!go && infoEl) infoEl.textContent = '🎯 לא הורץ — המכ"ם רחוק מהמסלול. הזז את המכ"ם, בחר מכ"ם אחר, או השתמש ב"📊 השווה את כל המכ"מים".';  // הסבר
            return !go;  // true = לא להמשיך
        }}

        var _rtCmp = {{jobId: null, timer: null, el: null}};  // T30: מצב ההשוואה

        function _rtCompareAll() {{  // T30 (החלטה 5): המסלול מול כל המכ"מים המוצבים — טבלה מי רואה את הפגז ומתי
            if (_rtSrc.sel && _rtSrc.sel.value === 'rocket') {{ alert('ההשוואה זמינה למסלול בליסטי, לטיסה ולשיוט — לרקטה הרץ קודם "בדוק מעקב" ואז בחר "מסלול בליסטי"'); return; }}  // רקטה — מחושבת בנפרד
            var b = _rtBuildTrajectory();  // המסלול מהמקור שנבחר
            if (!b) return;  // אין
            var el = _rtCmp.el; el.innerHTML = ''; el.textContent = '📊 מתחיל השוואה…';  // משוב
            if (_rtCmp.timer) {{ clearInterval(_rtCmp.timer); _rtCmp.timer = null; }}  // השוואה קודמת
            fetch('http://localhost:5002/radar_track/compare', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{trajectory: b.points, alt_ref: (b.opts && b.opts.alt_ref) || 'msl'}})}})
            .then(function(r) {{ return r.json().then(function(d) {{ if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status)); return d; }}); }})  // שגיאה עם הסבר
            .then(function(d) {{
                _rtCmp.jobId = d.job_id;  // ה-job
                _rtCmp.timer = setInterval(function() {{  // polling
                    fetch('http://localhost:5002/radar_doppler/status?job_id=' + d.job_id).then(function(r) {{ return r.json(); }}).then(function(st) {{
                        if (st.status === 'running') {{ el.textContent = '📊 ' + (st.note || 'משווה…') + (st.batches_total ? ' (' + st.batches_done + '/' + st.batches_total + ')' + _rtEtaText(st) : ''); return; }}  // התקדמות
                        clearInterval(_rtCmp.timer); _rtCmp.timer = null;  // הסתיים
                        if (st.status === 'done') _rtCompareRender(st.result);  // הטבלה
                        else el.textContent = st.status === 'error' ? '📊 שגיאה: ' + (st.error || '') : '📊 בוטל.';  // שגיאה/ביטול
                        _rtRevealResult(el);  // גלילה לתוצאה
                    }}).catch(function() {{}});  // ה-tick הבא
                }}, 1000);
            }})
            .catch(function(e) {{ el.textContent = '📊 ' + e.message; }});  // שגיאת קלט/רשת
        }}

        function _rtCompareRender(res) {{  // T30: טבלת ההשוואה (מי שרואה ראשון — למעלה)
            var el = _rtCmp.el; el.innerHTML = '';  // ניקוי
            var s = res.summary || {{}};  // סיכום
            var head = document.createElement('div'); head.style.cssText = 'font-size:9.5px;margin-bottom:2px;';  // שורת סיכום
            head.textContent = '📊 ' + (s.seeing || 0) + ' מתוך ' + (s.radars || 0) + ' מכ"מים רואים את המסלול' + (s.first ? ' · ראשון: ' + s.first + ' (אחרי ' + s.first_t + " ש')" : '');  // הטקסט
            el.appendChild(head);  // הוספה
            var rows = (res.rows || []).slice().sort(function(a, b) {{  // מיון: רואים לפי זמן גילוי, אחריהם לא רואים, ואחרונים שגיאות
                function k(r) {{ return !r.ok ? 3e9 : (r.detected ? (r.first_detection_t == null ? 1e9 : r.first_detection_t) : 2e9); }}  // מפתח
                return k(a) - k(b);  // השוואה
            }});
            var t = document.createElement('table'); t.style.cssText = 'border-collapse:collapse;font-size:9px;width:100%;direction:rtl;';  // הטבלה
            t.setAttribute('aria-label', 'השוואת המכ"מים המוצבים על המסלול');  // נגישות
            var hr = t.insertRow();  // כותרת
            ['מכ"ם', 'רואה', "גילוי [ש']", 'מרחק [ק"מ]', 'כיסוי', 'מעקב', "התרעה [ש']"].forEach(function(h) {{ var th = document.createElement('th'); th.textContent = h; th.style.cssText = 'background:#f5f5f5;padding:1px 3px;border-bottom:1px solid #ddd;'; hr.appendChild(th); }});  // עמודות
            rows.forEach(function(r) {{  // כל מכ"ם
                var tr = t.insertRow();  // שורה
                var cells = !r.ok ? [r.name, '⚠️ ' + (r.error || 'שגיאה'), '', '', '', '', ''] :  // שגיאה במכ"ם הזה
                    [r.name, r.detected ? '✔ כן' : '✖ לא', r.first_detection_t == null ? '—' : r.first_detection_t,  // רואה + מתי
                     r.first_detection_km == null ? (r.min_dist_km == null ? '—' : r.min_dist_km.toFixed(1)) : r.first_detection_km.toFixed(1),  // מרחק
                     r.coverage_pct == null ? '—' : r.coverage_pct + '%', r.tracked ? '✔' : '—', r.warning_time_s == null ? '—' : r.warning_time_s];  // כיסוי, מעקב, התרעה
                cells.forEach(function(v, i) {{ var td = tr.insertCell(); td.textContent = String(v); td.style.cssText = 'padding:1px 3px;border-bottom:1px solid #f0f0f0;white-space:nowrap;' + (i === 1 && r.ok ? (r.detected ? 'color:#1e7e34;' : 'color:#b00020;') : ''); if (!r.ok && i === 1) td.colSpan = 6; }});  // תאים (טקסט + צבע, לא רק צבע)
            }});
            el.appendChild(t);  // הוספה
            var note = document.createElement('div'); note.style.cssText = 'font-size:8.5px;color:#666;margin-top:2px;';  // הערה
            note.textContent = 'כל מכ"ם נבדק עם פרמטרי הסוג וההצבה שלו (טווח, גזרה, גובה אנטנה) — לא עם השדות שבכלי הדופלר.';  // הסבר
            el.appendChild(note);  // הוספה
        }}

        var _radarLastResult = null;  // תוצאת החישוב האחרונה שצוירה — נשמרת כדי לאפשר Redo בלי קריאה חוזרת לשרת

        function _clearRadarResultOnly() {{
            // מנקה רק את ציור התוצאה (פוליגון+חישורים) בלי לגעת במשקיף עצמו — בשימוש ע"י Undo של "הפעל חישוב"
            if (radarPolygon) {{ map.removeLayer(radarPolygon); radarPolygon = null; }}
            radarSpokes.forEach(function(s) {{ map.removeLayer(s); }});
            radarSpokes = [];
            _radarLastResult = null;
            _updateRadarDopplerPreview();  // מחזיר את הידיות למיקומן לפי השדות הנוכחיים, לא לפי קצוות הקרניים האחרונות
        }}

        function _drawRadarDopplerResult(result) {{
            // מצייר את הפוליגון הסופי + קטע/שני קטעים צבעוניים לכל כיוון — 3 מצבים אפשריים:
            // ירוק בלבד עד סוף הטווח = מזוהה לגמרי. ירוק+אדום = מזוהה חלקית (נחסם שטח/טווח מכ"ם בהמשך).
            // כתום (במקום ירוק) = הכיוון הזה כולו "עיוור" לדופלר (מהירות המטרה המשוערת לא מתגלה בזווית
            // הזו כלל) — גם אם השטח/טווח המכ"ם היו מאפשרים גילוי, ואז ממשיך אדום עד סוף הטווח אם נחסם.
            var _prevRadarResult = _radarLastResult;  // תוצאה קודמת (או null) — נשמרת להיסטוריית Undo
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
                var seg1 = L.polyline([nearPt, radarPt], {{color: nearColor, weight: 3}}).addTo(map);
                seg1.bindTooltip('לחץ לחתך-צד', {{sticky:true}});
                // L.DomEvent.stopPropagation(e) חיוני כאן — בלעדיו הלחיצה "מבעבעת" גם ל-map.on('click', ...)
                // הרגיל, שרואה radarActive===true ומפרש את זה כהצבת משקיף חדש (מוחק את כל החישורים!) —
                // בדיוק התקלה שדווחה: לחיצה על דגימה אחת מחקה את כל הדגימות מהמסך.
                seg1.on('click', (function(ray) {{ return function(e) {{ L.DomEvent.stopPropagation(e); _showRadarRayProfile(ray); }}; }})(r));
                radarSpokes.push(seg1);
                if (r.blocked) {{
                    // אדום — ממשיך מהנקודה הרחוקה ביותר בטווח המכ"ם עד סוף הטווח המבוקש (שטח/טווח מכ"ם לא הספיקו)
                    var farPt = _destPointJs(obsLatLng, r.bearing_deg, rangeM);
                    var seg2 = L.polyline([radarPt, farPt], {{color: '#ff3300', weight: 3}}).addTo(map);
                    seg2.bindTooltip('לחץ לחתך-צד', {{sticky:true}});
                    seg2.on('click', (function(ray) {{ return function(e) {{ L.DomEvent.stopPropagation(e); _showRadarRayProfile(ray); }}; }})(r));
                    radarSpokes.push(seg2);
                }}
            }});
            if (result.rays.length > 0) {{  // הזזת הידיות לקצוות הקשת האמיתיים
                var firstRay = result.rays[0], lastRay = result.rays[result.rays.length - 1];
                if (radarStartMk) radarStartMk.setLatLng([firstRay.radar_lat, firstRay.radar_lon]);
                if (radarEndMk)   radarEndMk.setLatLng([lastRay.radar_lat, lastRay.radar_lon]);
            }}
            _radarLastResult = result;  // שמירת התוצאה הנוכחית — משמשת גם ל-Redo וגם כ"ערך קודם" בהרצה הבאה
            if (!_isRestoringUndo) {{
                _pushUndo('מכ"ם דופלר: הפעלת חישוב', _makePlacementRestore(
                    _drawRadarDopplerResult, _clearRadarResultOnly,
                    function() {{ return _radarLastResult; }}, _prevRadarResult));
            }}
        }}

        function _showRadarRayProfile(ray) {{
            // נקרא בלחיצה על חישור בתוצאת מכ"ם-דופלר — שולף מחדש את כל 19 הפרמטרים הנוכחיים
            // מהשדות בפאנל (בדיוק כמו _runRadarDoppler) ועוד bearing_deg הספציפי של הקרן הזו,
            // ומבקש מ-/radar_doppler/profile את כל נקודות הדגימה לאורך הקרן (לא רק את הסיכום)
            if (!radarObs) return;
            function num(el, def) {{ var v = el ? parseFloat(el.value) : NaN; return isNaN(v) ? def : v; }}
            var url = 'http://localhost:5002/radar_doppler/profile?lat=' + radarObs.lat + '&lon=' + radarObs.lng +
                      '&bearing_deg=' + ray.bearing_deg +
                      '&range_km=' + num(_radarRangeInput, 50) + '&min_range_km=' + num(_radarMinRangeInput, 1) +
                      '&h_antenna=' + num(_radarHAntInput, 15) + '&ridge_margin_deg=' + num(_radarMarginInput, 0) +
                      '&vertical_center_deg=' + num(_radarVCenterInput, 0) + '&vertical_width_deg=' + num(_radarVWidthInput, 10) +
                      '&power_kw=' + num(_radarPowerInput, 100) + '&gain_dbi=' + num(_radarGainInput, 30) +
                      '&freq_mhz=' + (_radarFreqSelect ? parseFloat(_radarFreqSelect.value) : 3000) +
                      '&sensitivity_dbm=' + num(_radarSensInput, -100) +
                      '&rcs_m2=' + num(_radarRcsInput, 2) +
                      '&prf_hz=' + num(_radarPrfInput, 1000) + '&mdv_kt=' + num(_radarMdvInput, 20) +
                      '&target_speed_kt=' + num(_radarSpeedInput, 250) + '&target_heading_deg=' + num(_radarHeadingInput, 0) +
                      '&lobing_enabled=' + (_radarLobingCheck && _radarLobingCheck.checked ? 'true' : 'false') +
                      '&reflectivity=' + (_radarReflSelect ? _radarReflSelect.value : 'land') +
                      '&antenna_type=' + (_radarAntennaSelect ? _radarAntennaSelect.value : 'generic') +
                      '&boresight_deg=' + num(_radarBoresightInput, 0) + '&max_scan_deg=' + num(_radarMaxScanInput, 60);
            fetch(url)
            .then(function(r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
            .then(function(data) {{
                if (data.error) throw new Error(data.error);
                _drawRadarProfilePanel(data);
            }})
            .catch(function(err) {{ alert('שגיאה בטעינת חתך-צד: ' + err.message); }});
        }}

        function _drawRadarProfilePanel(data) {{
            // פאנל נפרד מ-losPanelEl בכוונה — לא שייך סמנטית ל-losSessions (אין כאן "סשן LOS"
            // אמיתי עם סמנים על המפה), רק שימוש חוזר בפונקציית הציור הגנרית _drawProfileSingle
            if (_radarProfilePanelEl) {{ _radarProfilePanelEl.remove(); _radarProfilePanelEl = null; }}
            _radarProfilePanelEl = document.createElement('div');
            _radarProfilePanelEl.style.cssText = 'position:fixed;bottom:0;left:0;right:0;height:230px;background:#1e1e2e;' +
                'border-top:2px solid #22d3ee;z-index:9000;display:flex;flex-direction:column;';
            var header = document.createElement('div');
            header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;' +
                'padding:3px 10px;background:#181825;color:#cdd6f4;font-family:Arial;font-size:13px;direction:rtl;flex-shrink:0;';
            header.innerHTML = '<span>מכ"ם דופלר — חתך-צד לאזימוט ' + data.bearing_deg.toFixed(0) + '°</span>';
            var closeBtn = document.createElement('button');
            closeBtn.textContent = '✕ סגור';
            closeBtn.style.cssText = 'background:none;border:none;color:#f38ba8;font-size:12px;cursor:pointer;font-family:Arial;';
            closeBtn.onclick = function() {{ _radarProfilePanelEl.remove(); _radarProfilePanelEl = null; }};
            header.appendChild(closeBtn);
            _radarProfilePanelEl.appendChild(header);
            var canvas = document.createElement('canvas');
            canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'חתך-צד של קרן מכ"ם: שטח, קו ראייה ואלומה לפי מרחק');  // T12 (F-041): שם נגיש לגרף
            canvas.style.cssText = 'flex:1;width:100%;display:block;';
            _radarProfilePanelEl.appendChild(canvas);
            document.body.appendChild(_radarProfilePanelEl);
            // setTimeout(0) — מבטיח שה-canvas כבר ב-DOM עם גודל בפועל לפני הציור, כמו ב-_redrawPanel הקיים
            setTimeout(function() {{ _drawProfileSingle(canvas, {{color: '#22d3ee', data: data}}); }}, 0);
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
            _radarLastResult = null;  // אין יותר תוצאה מצוירת — מונע היסטוריית Undo "רפאים" מתוצאה שכבר לא קיימת
            if (_radarProfilePanelEl) {{ _radarProfilePanelEl.remove(); _radarProfilePanelEl = null; }}  // סוגר גם חתך-צד פתוח, אם יש — לא רלוונטי לתוצאה שנמחקת
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
            if (radarActive && ballisticsActive) _ballisticsSetActive(false);  // תיקון תקלה: פאנל אחד בכל פעם — אחרת לחיצה אחת על המפה מציבה גם מכ"ם וגם תותח/מטרה
            _fitTopRightPanels();  // הגובה המרבי לפי המקום שנשאר בפועל
            if (!radarActive) {{
                // כיבוי/צמצום הפאנל בלבד — לא מוחק את התוצאה מהמפה (משקיף/פוליגון/חישורים/חתך-צד פתוח).
                // רק עוצר job שעדיין רץ ברקע, אם יש (בדיוק כמו כפתור "בטל"). המשתמש שם דגש על כך:
                // סגירת הפאנל לא אמורה "לפגוע בנתונים" — תוצאה חדשה נמחקת רק בהצבת משקיף חדש בפועל
                // (_placeRadarObserver) או באיפוס מפה מלא (resetMapState), לא בכיבוי הפאנל עצמו.
                _cancelRadarDoppler();
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
                btn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
                btn.setAttribute('aria-label', 'כלי תצפית מכם דופלר');
                _radarBtnEl = btn;
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;  // הגנה נוספת מעבר ל-pointer-events — המפה/שרתים לא מוכנים
                    toggleRadarDoppler();
                }});

                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;max-height:70vh;overflow-y:auto;';
                _radarPanelBodyEl = panelBody;
                _fitPanelEls.push(panelBody);  // תיקון תקלה: הגובה המרבי מותאם למקום שנשאר מתחת לפאנל
                _rtBuildActiveBar(panelBody);  // FR-D-286: בורר "פרופיל פעיל" בראש הפאנל — קובע את הפרמטרים לכל תהליכי המכ"ם

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
                    _attachFieldUndo(inp, 'מכ"ם דופלר: ' + labelText, _updateRadarDopplerPreview);  // רישום undo אוטומטי (focus→blur) לכל שדה בכלי
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
                    _attachSelectUndo(sel, 'מכ"ם דופלר: ' + labelText);  // רישום undo אוטומטי לכל dropdown בכלי
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
                    ['L-band (1.3 GHz)', '1300'], ['S-band (3 GHz)', '3000'], ['C-band (5 GHz)', '5000'], ['X-band (10 GHz)', '10000']
                ], 1, 'תדר גבוה יותר = אורך גל קצר יותר, בד"כ טווח קטן יותר');
                _radarSensInput  = _mkField('רגישות מקלט (dBm)', -100, 1, -140, -60, 'רגישות טובה יותר (מספר שלילי יותר) = טווח גילוי גדול יותר');
                _radarRcsInput = _mkField('שטח חתך רדארי (RCS, מ"ר)', 2, 0.01, 0.001, 1000,
                    'שטח חתך רדארי בפועל — ניתן להזין כל ערך; הרשימה מתחת ממלאת ערך טיפוסי במקום להקליד');
                var _radarRcsPreset = _mkSelect('סוג מטרה (מילוי מהיר)', [
                    ['רחפן קטן (0.01 מ"ר)', '0.01'], ['מל"ט בינוני (0.1 מ"ר)', '0.1'],
                    ['מטוס קל (2 מ"ר)', '2'], ['מטוס תובלה (50 מ"ר)', '50']
                ], 2, 'בחירה כאן רק ממלאת את השדה למעלה — אפשר גם להקליד ישירות כל ערך אחר');
                L.DomEvent.on(_radarRcsPreset, 'change', function() {{
                    _radarRcsInput.value = _radarRcsPreset.value;  // מילוי מהיר בלבד — לא מקור-האמת; ריצה/פרופיל תמיד קוראים מהשדה עצמו
                }});

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
                _attachCheckboxUndo(_radarLobingCheck, 'מכ"ם דופלר: הצג השפעת ריבוד');
                _radarReflSelect = _mkSelect('סוג משטח מחזיר', [
                    ['יבשה מחוספסת', 'land'], ['ים חלק', 'sea']
                ], 0, 'רלוונטי רק כש"הצג השפעת ריבוד" מסומן — משטח חלק יותר מחזיר חזק יותר');

                // מקור-אמת יחיד למפת השדות — משמש גם ל"עמדות שמורות" (עם מיקום) וגם ל"הגדרות שמורות" (בלעדיו) מיד למטה
                var _radarFieldMap = {{
                    range_km: _radarRangeInput, min_range_km: _radarMinRangeInput, angle_step_deg: _radarStepInput,
                    start_bearing_deg: _radarStartInput, end_bearing_deg: _radarEndInput, h_antenna: _radarHAntInput,
                    ridge_margin_deg: _radarMarginInput, vertical_center_deg: _radarVCenterInput, vertical_width_deg: _radarVWidthInput,
                    power_kw: _radarPowerInput, gain_dbi: _radarGainInput, freq_mhz: _radarFreqSelect, sensitivity_dbm: _radarSensInput,
                    rcs_m2: _radarRcsInput, antenna_type: _radarAntennaSelect, boresight_deg: _radarBoresightInput, max_scan_deg: _radarMaxScanInput,
                    prf_hz: _radarPrfInput, mdv_kt: _radarMdvInput, target_speed_kt: _radarSpeedInput, target_heading_deg: _radarHeadingInput,
                    lobing_enabled: _radarLobingCheck, reflectivity: _radarReflSelect,
                }};
                _buildStationUI(panelBody, 'radar_doppler', _radarFieldMap,
                    function() {{ return radarObs; }}, _placeRadarObserver, _updateRadarDopplerPreview,
                    'עמדות שמורות (מיקום+הגדרות):');
                // בלוק שני — "הגדרות שמורות" בלי מיקום: getObsFn/placeObsFn null כדי ש-lat/lon לעולם לא יישמרו/יוחלו
                _buildStationUI(panelBody, 'radar_doppler_settings', _radarFieldMap,
                    null, null, _updateRadarDopplerPreview,
                    'הגדרות שמורות (ללא מיקום):');
                _rtHookActiveFields();  // FR-D-286: שינוי ידני בשדות המכ"ם מסומן בבורר הפרופיל הפעיל

                var runBtn = L.DomUtil.create('button', '', panelBody);
                runBtn.textContent = 'הפעל חישוב';
                runBtn.setAttribute('aria-label', 'הפעל חישוב תצפית מכם דופלר');  // נגישות — מבדיל מכפתורי "הפעל חישוב" של כלים אחרים (F-027, Q-1)
                runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#22d3ee;cursor:pointer;margin-top:3px;';
                L.DomEvent.on(runBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runRadarDoppler(); }});

                var cancelBtn = L.DomUtil.create('button', '', panelBody);
                cancelBtn.textContent = 'בטל';
                cancelBtn.setAttribute('aria-label', 'בטל חישוב תצפית מכם דופלר');  // נגישות (F-027, Q-1)
                cancelBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#ff8888;cursor:pointer;display:none;';
                L.DomEvent.on(cancelBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _cancelRadarDoppler(); }});
                _radarCancelBtnEl = cancelBtn;

                var routeEvalBtn = L.DomUtil.create('button', '', panelBody);
                routeEvalBtn.textContent = 'הערך מסלול טיסה מול המכ"ם';
                routeEvalBtn.title = 'דורש משקיף מוצב וגם מסלול טיסה טעון (חיפוש FR24) — מעריך כל נקודה לאורך המסלול לפי הנתונים האמיתיים שלה';
                routeEvalBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#cba6f7;cursor:pointer;margin-top:3px;';
                L.DomEvent.on(routeEvalBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runRouteEvaluation(); }});

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
            // _ballisticsBtnEl נוסף כאן (FR-D-235 תיקון) — הכלי הבליסטי גם הוא תלוי ב-weather_server.py
            // (/ballistics/*), אבל נבנה עם opacity:0.4;pointer-events:none כברירת-מחדל (כמו שלושת האלה)
            // בלי שנרשם כאן — לכן נשאר "תקוע" מנוטרל לנצח ל-לחיצת-עכבר אמיתית (נמצא ע"י המשתמש בפועל:
            // בדיקה אוטומטית עם element.click() לא תפסה את זה, כי pointer-events:none לא חוסם .click()
            // פרוגרמטי, רק קלט-עכבר/מגע אמיתי — ר' MAPS-GUI_SRS.md §3.27)
            [_losBtnEl, _radialLosBtnEl, _radarBtnEl, _ballisticsBtnEl].forEach(function(btn) {{
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

        // ══════════════════════════════════════════════════════════════════
        // ── כלי "מסלול טיסה מותאם" — המשתמש מזין רשימת נקודות (הקלדה/הדבקה/קליק
        // על המפה) ומקבל מסלול סגור מצויר על המפה. בשונה מ-LOS/רדיוס-ראייה/מכ"ם-
        // דופלר — אין כאן שום חישוב פיזיקלי ואין תלות בשרת כלל (חיבור-נקודות גרפי
        // טהור); שמירה/טעינה בלבד משתמשות ב-/stations הקיים (tool='custom_route').
        // ══════════════════════════════════════════════════════════════════
        var customRouteActive     = false; // האם מצב הוספת נקודות למסלול פעיל (קליק על המפה מוסיף נקודה)
        var customRoutePoints     = [];     // מערך {{lat, lng, alt}} לכל נקודה — alt הוא null אם לא הוזן גובה
        var customRoutePolyline   = null;   // הקו הסגור המצויר על המפה (null אם פחות מ-2 נקודות)
        var customRouteMarkers    = [];     // סמן ממוספר לכל נקודה — מאפשר לוודא ויזואלית שהמיקום/הסדר נכונים
        var _customRouteBtnEl     = null;
        var _customRoutePanelBodyEl = null;
        var _customRouteListEl    = null;   // מיכל ה-DOM לרשימת הנקודות הממוספרת בפאנל
        var _customRouteSelect    = null;
        var _customRouteCache     = [];     // מטמון רשימת המסלולים השמורים שנשלפה לאחרונה

        // מפצל שורה לטוקנים לפי פסיקים/רווחים — בכוונה בלי regex (רק split/join/filter פשוטים),
        // כדי לא לגעת בכלל בסיכון ה-escaping הכפול שקיים בתוך ה-f-string הזה (ר' CLAUDE_PROMPT).
        function _splitCoordTokens(line) {{
            return line.split(',').join(' ').split(' ').filter(function(t) {{ return t.length > 0; }});
        }}

        // מפרק טוקן עם אות-כיוון מובילה לערך עשרוני — תומך בשתי צורות: (א) דחוס DDMM.mmm/
        // DDDMM.mmm (4-5 ספרות שלמות, כמו "N3127.551") ו-(ב) מעלות עשרוניות ישירות (1-3 ספרות
        // שלמות, כמו "N35.19" = 35.19°). ההבחנה לפי מספר הספרות השלמות בלבד — בלי regex בכלל.
        function _parseHemisphereToken(tok, hemiChars) {{
            if (hemiChars.indexOf(tok.charAt(0)) === -1) return null;  // האות המובילה לא מתאימה (לא N/S או לא E/W)
            var body = tok.slice(1);                                   // כל מה שאחרי אות-הכיוון
            if (body === '' || isNaN(Number(body))) return null;       // חייב להיות מספר תקין (עם עד נקודה עשרונית אחת)
            var dotIdx  = body.indexOf('.');
            var intPart = dotIdx === -1 ? body : body.slice(0, dotIdx);
            var fracPart = dotIdx === -1 ? '' : body.slice(dotIdx);
            var val;
            if (intPart.length === 4 || intPart.length === 5) {{
                // דחוס: 2 הספרות האחרונות הן תמיד דקות, השאר מעלות
                var degLen = intPart.length - 2;
                var deg = Number(intPart.slice(0, degLen));
                var min = Number(intPart.slice(degLen) + fracPart);
                val = deg + min / 60;
            }} else if (intPart.length >= 1 && intPart.length <= 3) {{
                // מעלות עשרוניות ישירות — בלי מבנה DDMM בכלל, האות-כיוון פשוט מצורפת למספר רגיל
                val = Number(intPart + fracPart);
            }} else {{
                return null;  // אורך לא-תקין (0 או 6+ ספרות שלמות) — לא פורמט מוכר
            }}
            var c = tok.charAt(0);
            var negative = (c === 'S' || c === 's' || c === 'W' || c === 'w');
            return negative ? -val : val;
        }}

        // ניסיון פורמט (1): שני טוקנים דחוסים עם אות-כיוון, בכל סדר (האות מזהה lat/lon, לא המיקום
        // בשורה) + עד טוקן מספרי נוסף אחד = גובה אופציונלי במטרים. מחזיר {{lat,lng,alt}} או null.
        function _tryParseDdmLine(tokens) {{
            var lat = null, lon = null, extra = [];
            for (var i = 0; i < tokens.length; i++) {{
                var t = tokens[i];
                var asLat = _parseHemisphereToken(t, 'NSns');
                var asLon = _parseHemisphereToken(t, 'EWew');
                if (asLat !== null) {{ lat = asLat; }}
                else if (asLon !== null) {{ lon = asLon; }}
                else if (t !== '' && !isNaN(Number(t))) {{ extra.push(Number(t)); }}
                else {{ return null; }}  // טוקן לא מזוהה — הפורמט הזה לא מתאים לשורה כולה
            }}
            if (lat === null || lon === null || extra.length > 1) return null;
            if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;  // ערך חסר-פיזיקה — כנראה טעות הקלדה
            return {{ lat: lat, lng: lon, alt: extra.length ? extra[0] : null }};
        }}

        // ניסיון פורמט (2): מעלות/דקות/שניות עם סמלים (למשל 31°11'24"N 34°48'36"E) — regex יחיד
        // בכל הכלי, ובכוונה בלי אף backslash (משתמש ב-[0-9] במקום ד'-הספרה, [.] במקום נקודה-מוסקפת) כדי
        // להימנע לגמרי מסיכון ה-escaping הכפול בתוך ה-f-string הזה.
        function _tryParseDmsLine(line) {{
            var dmsRe = /([0-9]{{1,3}})[°ºo][ ]*([0-9]{{1,2}})['′][ ]*([0-9]{{1,2}}(?:[.][0-9]+)?)["″]?[ ]*([NSEWnsew])/g;
            var matches = [], m;
            while ((m = dmsRe.exec(line)) !== null) {{ matches.push(m); }}
            if (matches.length !== 2) return null;  // בדיוק זוג אחד (קו-רוחב+קו-אורך) נדרש
            var lat = null, lon = null;
            for (var i = 0; i < matches.length; i++) {{
                var deg = Number(matches[i][1]), min = Number(matches[i][2]), sec = Number(matches[i][3]);
                var val = deg + min / 60 + sec / 3600;
                var h = matches[i][4];
                if (h === 'N' || h === 'n' || h === 'S' || h === 's') {{ lat = (h === 'S' || h === 's') ? -val : val; }}
                else {{ lon = (h === 'W' || h === 'w') ? -val : val; }}
            }}
            if (lat === null || lon === null) return null;
            if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
            // בדיקת מספר-גובה שנותר בשורה אחרי הסרת שני ביטויי ה-DMS (ל-dmsRe דגל g, ולכן
            // lastIndex כבר התאפס ל-0 מעצמו לאחר ה-exec האחרון שהחזיר null בלולאה למעלה)
            var rest = line.replace(dmsRe, ' ');
            var restTokens = _splitCoordTokens(rest);
            var alt = (restTokens.length === 1 && !isNaN(Number(restTokens[0]))) ? Number(restTokens[0]) : null;
            return {{ lat: lat, lng: lon, alt: alt }};
        }}

        // ניסיון פורמט (3): זוג/שלישיית מספרים עשרוניים פשוטים ("34.33 31.19" או עם גובה שלישי).
        // אם אחד הערכים חורג מטווח קו-רוחב (±90) בעוד השני בתוכו — מזוהה אוטומטית כקו-האורך
        // (בלי תלות בסדר בשורה). אם שניהם בטווח (עמום) — ברירת המחדל: קו-רוחב ואז קו-אורך,
        // עקבי עם כל שאר הכלי (LAT/LON בפאנל המיקום, pinCoordinate וכו').
        function _tryParseDecimalLine(tokens) {{
            if (tokens.length !== 2 && tokens.length !== 3) return null;
            for (var i = 0; i < tokens.length; i++) {{
                if (tokens[i] === '' || isNaN(Number(tokens[i]))) return null;
            }}
            var a = Number(tokens[0]), b = Number(tokens[1]);
            var alt = tokens.length === 3 ? Number(tokens[2]) : null;
            if (Math.abs(a) > 90 && Math.abs(b) <= 90) return {{ lat: b, lng: a, alt: alt }};
            if (Math.abs(b) > 90 && Math.abs(a) <= 90) return {{ lat: a, lng: b, alt: alt }};
            // עמום (שני הערכים בטווח ±90) — נמצא ותוקן (28/09/2026): אומת מול נתוני-אמת גיאוגרפיים
            // אמיתיים (אזור אילת/סיני) שברירת המחדל הנכונה היא **קו-אורך קודם, קו-רוחב אחריו**
            // (הפוך ממה שהוחלט קודם בשיחה לפי תשובה מילולית) — הראשון בשורה הוא lng, השני lat.
            if (Math.abs(a) <= 90 && Math.abs(b) <= 90) return {{ lat: b, lng: a, alt: alt }};
            return null;  // שני הערכים מעל 90 — אף אחד מהם לא יכול להיות קו-רוחב תקין
        }}

        // מנסה את שלושת הפורמטים על שורה נתונה (בלי טיפול בתווית מובילה) — פונקציית עזר משותפת
        // בין הניסיון הרגיל לבין הניסיון השני שמדלג על טוקן ראשון שאינו קואורדינטה (ר' למטה).
        function _tryAllCoordFormats(line) {{
            var tokens = _splitCoordTokens(line);
            var ddm = _tryParseDdmLine(tokens);
            if (ddm) return ddm;
            var dms = _tryParseDmsLine(line);
            if (dms) return dms;
            return _tryParseDecimalLine(tokens);
        }}

        function _parseCustomRouteLine(line) {{
            line = line.trim();
            if (!line) return null;
            var direct = _tryAllCoordFormats(line);
            if (direct) return direct;
            // נכשל — ייתכן שהטוקן הראשון הוא תווית/שם-נקודה (למשל "C" לפני הקואורדינטה עצמה,
            // כמו בקבצי תכנון-מסלול צבאיים) ולא חלק מהקואורדינטה. מדלגים עליו ומנסים שוב;
            // התווית עצמה לא נשמרת (לפי בחירת המשתמש) — משמשת רק לזיהוי/דילוג.
            var firstSpaceIdx = line.indexOf(' ');
            if (firstSpaceIdx > 0) {{
                var rest = line.slice(firstSpaceIdx + 1).trim();
                if (rest) {{ return _tryAllCoordFormats(rest); }}
            }}
            return null;
        }}

        // מצייר מחדש את כל שכבת המסלול (קו סגור + סמנים ממוספרים) מאפס — פשוט מספיק לכמות
        // הנקודות הצפויה (עשרות, לא אלפים). מרענן גם את הרשימה בפאנל בסוף.
        function _redrawCustomRoute() {{
            if (customRoutePolyline) {{ map.removeLayer(customRoutePolyline); customRoutePolyline = null; }}
            customRouteMarkers.forEach(function(mk) {{ map.removeLayer(mk); }});
            customRouteMarkers = [];

            customRoutePoints.forEach(function(p, i) {{
                var mk = L.marker([p.lat, p.lng], {{
                    icon: L.divIcon({{
                        html: '<div style="background:#14b8a6;color:white;border-radius:50%;width:18px;height:18px;'
                            + 'display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:bold;'
                            + 'border:2px solid white;box-shadow:0 0 3px rgba(0,0,0,.5);">' + (i + 1) + '</div>',
                        className: '', iconSize: [18, 18], iconAnchor: [9, 9]
                    }})
                }}).addTo(map);
                customRouteMarkers.push(mk);
            }});

            if (customRoutePoints.length >= 2) {{
                var latlngs = customRoutePoints.map(function(p) {{ return [p.lat, p.lng]; }});
                latlngs.push(latlngs[0]);  // סגירת המסלול — קטע חוזר לנקודה הראשונה
                customRoutePolyline = L.polyline(latlngs, {{ color: '#14b8a6', weight: 3, opacity: 0.85 }}).addTo(map);
            }}

            _renderCustomRouteList();
        }}

        // מרענן את רשימת הנקודות הממוספרת בפאנל — שדה גובה ניתן-לעריכה וכפתור מחיקה לכל שורה
        function _renderCustomRouteList() {{
            if (!_customRouteListEl) return;
            _customRouteListEl.innerHTML = '';
            customRoutePoints.forEach(function(p, i) {{
                var row = L.DomUtil.create('div', '', _customRouteListEl);
                row.style.cssText = 'display:flex;align-items:center;gap:3px;font-size:9px;padding:1px 0;';
                var label = L.DomUtil.create('span', '', row);
                label.style.cssText = 'flex:1;';
                label.textContent = (i + 1) + '. ' + p.lat.toFixed(5) + ', ' + p.lng.toFixed(5);
                var altInput = L.DomUtil.create('input', '', row);
                altInput.type = 'number'; altInput.placeholder = 'גובה (מ\\')';
                altInput.value = (p.alt !== null && p.alt !== undefined) ? p.alt : '';
                altInput.style.cssText = 'width:55px;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;';
                altInput.setAttribute('aria-label', 'גובה נקודה ' + (i + 1));  // נגישות — placeholder בלבד, לכל נקודה בנפרד (F-027, Q-1)
                L.DomEvent.on(altInput, 'change', function() {{
                    var v = parseFloat(altInput.value);
                    customRoutePoints[i].alt = isNaN(v) ? null : v;  // עדכון גובה ידני לנקודה — לא גורר ציור מחדש (רק המספר משתנה)
                }});
                var delBtn = L.DomUtil.create('a', '', row);
                delBtn.href = '#'; delBtn.innerHTML = '&#10005;'; delBtn.title = 'הסר נקודה זו';
                delBtn.style.cssText = 'flex-shrink:0;cursor:pointer;color:#e74c3c;font-size:11px;';
                delBtn.setAttribute('role', 'button');  // נגישות (F-027, Q-1)
                delBtn.setAttribute('aria-label', 'הסר נקודה ' + (i + 1));
                L.DomEvent.on(delBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    customRoutePoints.splice(i, 1);
                    _redrawCustomRoute();
                }});
            }});
        }}

        function _addCustomRoutePoint(lat, lng, alt) {{
            customRoutePoints.push({{ lat: lat, lng: lng, alt: (alt === undefined ? null : alt) }});
            _redrawCustomRoute();
        }}

        function _removeLastCustomRoutePoint() {{
            if (customRoutePoints.length === 0) return;
            customRoutePoints.pop();
            _redrawCustomRoute();
        }}

        function _clearCustomRoute() {{
            customRoutePoints = [];
            _redrawCustomRoute();
        }}

        // ממקד את המפה על כל נקודות המסלול — נקרא רק אחרי הוספה מרובה (טקסט) או טעינת מסלול
        // שמור, לא אחרי כל קליק בודד על המפה (שם המשתמש כבר מסתכל על האזור הרלוונטי ממילא).
        // בלי זה, נקודות שהוזנו כטקסט באזור רחוק מהתצוגה הנוכחית "נעלמות" (מצוירות אך מחוץ למסך).
        function _fitCustomRouteView() {{
            if (customRoutePoints.length === 0) return;
            var bounds = customRoutePoints.map(function(p) {{ return [p.lat, p.lng]; }});
            if (bounds.length === 1) {{ map.setView(bounds[0], 10); }}
            else {{ map.fitBounds(bounds, {{ padding: [40, 40] }}); }}
        }}

        // מרענן את רשימת "המסלולים השמורים" בפאנל — GET גנרי, tool='custom_route'
        function _refreshCustomRouteList() {{
            fetch('http://localhost:5002/stations/list?tool=custom_route')
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                var routes = data.stations || [];
                _customRouteCache = routes;
                if (!_customRouteSelect) return;
                _customRouteSelect.innerHTML = '';
                if (routes.length === 0) {{
                    var opt = L.DomUtil.create('option', '', _customRouteSelect);
                    opt.textContent = '(אין מסלולים שמורים)'; opt.disabled = true; opt.selected = true;
                    return;
                }}
                routes.forEach(function(r) {{
                    var opt = L.DomUtil.create('option', '', _customRouteSelect);
                    opt.value = r.name;
                    opt.textContent = r.name + ' (' + ((r.params && r.params.points) ? r.params.points.length : 0) + ' נק\\')';
                }});
            }})
            .catch(function() {{ /* כשל רשת בטעינת הרשימה — לא קריטי, אפשר לנסות שוב */ }});
        }}

        function toggleCustomRoute() {{
            customRouteActive = !customRouteActive;
            map.getContainer().style.cursor = customRouteActive ? 'crosshair' : '';
            if (_customRouteBtnEl) {{
                _customRouteBtnEl.style.background = customRouteActive ? '#14b8a6' : 'white';
                _customRouteBtnEl.style.color      = customRouteActive ? 'white'  : '#333';
            }}
            if (_customRoutePanelBodyEl) {{
                _customRoutePanelBodyEl.style.display = customRouteActive ? 'flex' : 'none';
            }}
            // כיבוי הפאנל בלבד — לא מוחק את המסלול המצויר, עקבי עם כל שאר הכלים (LOS/רדיוס-ראייה/
            // מכ"ם-דופלר): רק "נקה מסלול" המפורש או resetMapState מוחקים בפועל
        }}

        var CustomRouteControl = L.Control.extend({{
            options: {{ position: 'topright' }},
            onAdd: function() {{
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cssText = 'display:flex;flex-direction:column;gap:3px;background:white;' +
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:4px 6px;font-family:Arial;max-width:250px;';

                var row1 = L.DomUtil.create('div', '', container);
                row1.style.cssText = 'display:flex;align-items:center;gap:5px;';
                var btn = L.DomUtil.create('a', '', row1);
                btn.href = '#'; btn.title = 'מסלול טיסה מותאם';
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;width:26px;height:26px;' +
                    'font-size:14px;background:white;color:#333;text-decoration:none;border-radius:4px;cursor:pointer;flex-shrink:0;';
                btn.innerHTML = '&#129517;';  // 🧭 מצפן — אייקון ייחודי, לא בשימוש בשום כלי אחר בפרויקט
                btn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
                btn.setAttribute('aria-label', 'כלי מסלול טיסה מותאם');
                _customRouteBtnEl = btn;
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    toggleCustomRoute();
                }});

                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;max-height:70vh;overflow-y:auto;';
                _customRoutePanelBodyEl = panelBody;
                _fitPanelEls.push(panelBody);  // תיקון תקלה: הגובה המרבי מותאם למקום שנשאר מתחת לפאנל

                var hint = L.DomUtil.create('div', '', panelBody);
                hint.style.cssText = 'font-size:9px;color:#666;';
                hint.textContent = 'שורה אחת לכל נקודה, למשל: N3127.551 E3359.569 3000 (גובה אופציונלי בסוף). אפשר גם ללחוץ על המפה.';

                var textarea = L.DomUtil.create('textarea', '', panelBody);
                textarea.rows = 3; textarea.placeholder = 'N3127.551 E3359.569';
                textarea.style.cssText = 'font-size:10px;padding:3px;border:1px solid #ccc;border-radius:3px;direction:ltr;resize:vertical;';
                textarea.setAttribute('aria-label', 'נקודות מסלול, שורה אחת לכל נקודה');  // נגישות — placeholder בלבד (F-027, Q-1)

                var addFromTextBtn = L.DomUtil.create('button', '', panelBody);
                addFromTextBtn.textContent = 'הוסף מטקסט';
                addFromTextBtn.style.cssText = 'font-size:10px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f0f0f0;cursor:pointer;';
                L.DomEvent.on(addFromTextBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    var lines = textarea.value.split('\\n');  // כל שורה = נקודה אחת בתיבת הטקסט
                    var errorLines = [];
                    lines.forEach(function(line, idx) {{
                        if (!line.trim()) return;
                        var pt = _parseCustomRouteLine(line);
                        if (pt) {{ customRoutePoints.push(pt); }}
                        else {{ errorLines.push(idx + 1); }}
                    }});
                    _redrawCustomRoute();
                    _fitCustomRouteView();  // ממקד את המפה על הנקודות שנוספו — לא נשארות "מחוץ למסך" בשקט
                    textarea.value = '';
                    if (errorLines.length) {{ alert('שורות ' + errorLines.join(', ') + ' לא זוהו כקואורדינטה תקינה ודולגו.'); }}
                }});

                // כפתור "טען מקובץ" — input type=file מוסתר, נפתח בלחיצה על הכפתור הנראה (תבנית סטנדרטית)
                var fileInput = L.DomUtil.create('input', '', panelBody);
                fileInput.type = 'file'; fileInput.accept = '.txt,.csv';
                fileInput.style.display = 'none';
                var loadFileBtn = L.DomUtil.create('button', '', panelBody);
                loadFileBtn.textContent = 'טען מקובץ...';
                loadFileBtn.style.cssText = 'font-size:10px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f0f0f0;cursor:pointer;';
                L.DomEvent.on(loadFileBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    fileInput.click();
                }});
                L.DomEvent.on(fileInput, 'change', function() {{
                    var file = fileInput.files[0];
                    if (!file) return;
                    var reader = new FileReader();
                    reader.onload = function(ev) {{
                        // מציב את תוכן הקובץ בתיבת הטקסט — המשתמש עדיין לוחץ "הוסף מטקסט" בעצמו כדי לאשר/לבדוק שגיאות
                        textarea.value = ev.target.result;
                    }};
                    reader.readAsText(file);
                    fileInput.value = '';  // מאפשר לבחור שוב את אותו קובץ בפעם הבאה
                }});

                var listWrap = L.DomUtil.create('div', '', panelBody);
                listWrap.style.cssText = 'font-size:9px;color:#333;margin-top:3px;';
                var listTitle = L.DomUtil.create('div', '', listWrap);
                listTitle.style.cssText = 'font-weight:bold;color:#666;';
                listTitle.textContent = 'נקודות המסלול:';
                var listEl = L.DomUtil.create('div', '', listWrap);
                _customRouteListEl = listEl;

                var actionsRow = L.DomUtil.create('div', '', panelBody);
                actionsRow.style.cssText = 'display:flex;gap:4px;';
                var undoBtn = L.DomUtil.create('button', '', actionsRow);
                undoBtn.textContent = 'הסר אחרונה';
                undoBtn.style.cssText = 'flex:1;font-size:9px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f0f0f0;cursor:pointer;';
                L.DomEvent.on(undoBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _removeLastCustomRoutePoint(); }});
                var clearBtn = L.DomUtil.create('button', '', actionsRow);
                clearBtn.textContent = 'נקה מסלול';
                clearBtn.style.cssText = 'flex:1;font-size:9px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#ffdddd;cursor:pointer;';
                L.DomEvent.on(clearBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _clearCustomRoute(); }});

                // שמירה/טעינה/מחיקה — נבנה ידנית (לא _buildStationUI, כי אין fieldMap של שדות בודדים,
                // כל התוכן הוא מערך נקודות אחד) אך משתמש באותם /stations/* בדיוק, tool='custom_route'
                var saveRow = L.DomUtil.create('div', '', panelBody);
                saveRow.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:4px;border-top:1px solid #ddd;padding-top:3px;';
                var nameInput = L.DomUtil.create('input', '', saveRow);
                nameInput.type = 'text'; nameInput.placeholder = 'שם מסלול';
                nameInput.style.cssText = 'flex:1;font-size:10px;padding:2px 3px;border:1px solid #ccc;border-radius:3px;direction:rtl;min-width:0;';
                nameInput.setAttribute('aria-label', 'שם מסלול שמור');  // נגישות — placeholder בלבד (F-027, Q-1)
                var saveBtn = L.DomUtil.create('a', '', saveRow);
                saveBtn.href = '#'; saveBtn.title = 'שמור מסלול נוכחי תחת השם שהוזן'; saveBtn.innerHTML = '&#128190;';
                saveBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
                saveBtn.setAttribute('role', 'button'); saveBtn.setAttribute('aria-label', 'שמור מסלול נוכחי תחת השם שהוזן');  // נגישות (F-027, Q-1)
                L.DomEvent.on(saveBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    var name = nameInput.value.trim();
                    if (!name) {{ alert('הזן שם למסלול'); return; }}
                    if (customRoutePoints.length < 2) {{ alert('נדרשות לפחות 2 נקודות במסלול כדי לשמור'); return; }}
                    fetch('http://localhost:5002/stations/save', {{
                        method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{tool: 'custom_route', name: name, params: {{points: customRoutePoints}}}})
                    }})
                    .then(function(r) {{ return r.json(); }})
                    .then(function(data) {{
                        if (data.error) throw new Error(data.error);
                        nameInput.value = '';
                        _refreshCustomRouteList();
                    }})
                    .catch(function(err) {{ alert('שגיאה בשמירת מסלול: ' + err.message); }});
                }});

                var loadRow = L.DomUtil.create('div', '', panelBody);
                loadRow.style.cssText = 'display:flex;align-items:center;gap:3px;margin-top:2px;';
                var routeSelect = L.DomUtil.create('select', '', loadRow);
                routeSelect.style.cssText = 'flex:1;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;min-width:0;';
                routeSelect.setAttribute('aria-label', 'מסלול שמור לטעינה/מחיקה');  // נגישות (F-027, Q-1)
                _customRouteSelect = routeSelect;
                var loadBtn = L.DomUtil.create('a', '', loadRow);
                loadBtn.href = '#'; loadBtn.title = 'טען מסלול נבחר'; loadBtn.innerHTML = '&#128194;';
                loadBtn.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
                loadBtn.setAttribute('role', 'button'); loadBtn.setAttribute('aria-label', 'טען מסלול נבחר');  // נגישות (F-027, Q-1)
                L.DomEvent.on(loadBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    var name = routeSelect.value;
                    var route = _customRouteCache.filter(function(r) {{ return r.name === name; }})[0];
                    if (!route || !route.params || !route.params.points) return;
                    customRoutePoints = route.params.points.map(function(p) {{
                        return {{ lat: p.lat, lng: p.lng, alt: (p.alt === undefined ? null : p.alt) }};
                    }});
                    _redrawCustomRoute();
                    _fitCustomRouteView();  // ממקד על כל המסלול הטעון, לא רק על הנקודה הראשונה
                }});
                var delBtn2 = L.DomUtil.create('a', '', loadRow);
                delBtn2.href = '#'; delBtn2.title = 'מחק מסלול נבחר'; delBtn2.innerHTML = '&#128465;';
                delBtn2.style.cssText = 'flex-shrink:0;cursor:pointer;font-size:13px;';
                delBtn2.setAttribute('role', 'button'); delBtn2.setAttribute('aria-label', 'מחק מסלול נבחר');  // נגישות (F-027, Q-1)
                L.DomEvent.on(delBtn2, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    var name = routeSelect.value;
                    if (!name) return;
                    if (!confirm('למחוק את המסלול "' + name + '"?')) return;
                    fetch('http://localhost:5002/stations/delete', {{
                        method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{tool: 'custom_route', name: name}})
                    }})
                    .then(function() {{ _refreshCustomRouteList(); }})
                    .catch(function() {{ /* כשל רשת במחיקה — לא קריטי */ }});
                }});

                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }}
        }});
        new CustomRouteControl().addTo(map);  // הוספת ה-Control למפה
        _refreshCustomRouteList();  // טעינת רשימת המסלולים השמורים מיד עם בניית ה-Control

        // לחיצה על המפה בעת מצב "מסלול טיסה מותאם" — מוסיפה נקודה בלי גובה (ניתן להזין גובה
        // ידנית אח"כ ברשימה). handler עצמאי לגמרי, בדיוק כמו כלי המדידה — לא נוגע בשום מצב אחר.
        map.on('click', function(e) {{
            if (!customRouteActive) return;
            _addCustomRoutePoint(e.latlng.lat, e.latlng.lng, null);
        }});

        // ══════════════════════════════════════════════════════════════════
        // כלי מסלול בליסטי (MPM) — Stage 3 (FR-D-235). עזרים: הצבת תותח/מטרה,
        // קריאות ל-/ballistics/* (mpm_api.py דרך weather_server.py), ציור פרופיל.
        // ══════════════════════════════════════════════════════════════════

        function _ballisticsMarkerIcon(color) {{
            // אייקון סמן — עיגול מלא בצבע נתון, אותו דפוס בדיוק כמו _radialLosMarkerIcon
            return L.divIcon({{
                html: '<div style="width:16px;height:16px;border-radius:50%;background:' + color + ';border:2px solid #333;"></div>',
                className: '', iconSize: [16,16], iconAnchor: [8,8]
            }});
        }}

        function _ballisticsFetchAlt(which) {{
            // משלים גובה-קרקע אוטומטית מ-/elevation הקיים (לא ballistics-ספציפי) — "נמשך אוטומטית
            // ממקור הגובה הקיים, וניתן לעריכה ידנית" לפי בקשת שלב 3
            var pt = which === 'gun' ? ballisticsGun : ballisticsTarget;
            if (!pt) return;
            pt.altState = 'pending';  // T21 (F-053): השליפה רצה — חישוב ייחסם עד שיהיה גובה
            var reqLat = pt.lat, reqLng = pt.lng;  // T21: המיקום שעבורו נשלחה הבקשה — תשובה ישנה (אחרי גרירה) לא תדרוס
            function current() {{ return pt === (which === 'gun' ? ballisticsGun : ballisticsTarget) && pt.lat === reqLat && pt.lng === reqLng; }}  // T21: הנקודה לא הוחלפה/הוזזה מאז
            function fail() {{ if (current() && pt.altState === 'pending') {{ pt.altState = 'failed'; _ballisticsAltUi(); }} }}  // T21: סימון כשל גלוי במקום שקט
            _ballisticsAltUi();  // T21: מציג "טוען גובה…" בשדה
            fetch('http://localhost:5002/elevation', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{locations: [{{latitude: pt.lat, longitude: pt.lng}}]}})
            }})
            .then(function(r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})  // T21: 500/502 הוא כשל, לא "אין נתון"
            .then(function(d) {{
                var e = d && d.results && d.results[0] ? d.results[0].elevation : null;
                if (!current()) return;  // T21: הנקודה זזה בינתיים — בקשה חדשה כבר אחראית עליה
                if (e === null || e === undefined || !isFinite(e)) {{ fail(); return; }}  // T21: תשובה בלי גובה = כשל גלוי
                if (pt.altState === 'manual') return;  // T21: המשתמש הקליד גובה בזמן ההמתנה — הערך שלו נשאר
                pt.alt = e; pt.altState = 'ok';  // T21: גובה אמיתי מהשרת
                _ballisticsSyncFields(); _ballisticsAltUi();  // T21: עדכון השדה והסרת האזהרה
            }})
            .catch(fail);  // T21 (F-053): כשל רשת/שרת — אזהרה + ניסיון חוזר, לא גובה 0 בשקט
        }}

        function _placeBallisticsPoint(latlng) {{
            // ממקם לפי ballisticsEditing ('gun'/'target') — נקרא מלחיצה-על-מפה או מ"עריכה ידנית"
            var which = ballisticsEditing;
            var icon = which === 'gun' ? '#f9e2af' : '#cba6f7';  // תותח=צהוב (כמו רדיוס-ראייה), מטרה=סגול (כמו הערכת-מסלול)
            var tip  = which === 'gun' ? 'תותח' : 'מטרה';
            if (which === 'gun') {{
                if (ballisticsGunMk) map.removeLayer(ballisticsGunMk);
                ballisticsGun = {{lat: latlng.lat, lng: latlng.lng, alt: null}};
                ballisticsGunMk = L.marker(latlng, {{icon: _ballisticsMarkerIcon(icon), draggable: true}}).addTo(map);
                ballisticsGunMk.bindTooltip(tip, {{permanent:false, direction:'top'}});
                ballisticsGunMk.on('dragend', function() {{
                    var p = ballisticsGunMk.getLatLng();
                    ballisticsGun.lat = p.lat; ballisticsGun.lng = p.lng;
                    _ballisticsFetchAlt('gun'); _ballisticsSyncFields();
                }});
                _ballisticsFetchAlt('gun');
                if (!ballisticsTarget) ballisticsEditing = 'target';  // לחיצה ראשונה=תותח, הבאה=מטרה (ברירת מחדל)
            }} else {{
                if (ballisticsTgtMk) map.removeLayer(ballisticsTgtMk);
                ballisticsTarget = {{lat: latlng.lat, lng: latlng.lng, alt: null}};
                ballisticsTgtMk = L.marker(latlng, {{icon: _ballisticsMarkerIcon(icon), draggable: true}}).addTo(map);
                ballisticsTgtMk.bindTooltip(tip, {{permanent:false, direction:'top'}});
                ballisticsTgtMk.on('dragend', function() {{
                    var p = ballisticsTgtMk.getLatLng();
                    ballisticsTarget.lat = p.lat; ballisticsTarget.lng = p.lng;
                    _ballisticsFetchAlt('target'); _ballisticsSyncFields();
                }});
                _ballisticsFetchAlt('target');
            }}
            _ballisticsSyncFields();
        }}

        function _ballisticsClearResult() {{
            // מנקה תוצאה-חזותית קודמת (מסלול/פגיעה/קודקוד/התנגשות) — לפני חישוב חדש
            if (ballisticsPathLn)   {{ map.removeLayer(ballisticsPathLn);   ballisticsPathLn   = null; }}
            if (ballisticsImpactMk) {{ map.removeLayer(ballisticsImpactMk); ballisticsImpactMk = null; }}
            if (ballisticsApexMk)   {{ map.removeLayer(ballisticsApexMk);   ballisticsApexMk   = null; }}
            if (ballisticsCollMk)   {{ map.removeLayer(ballisticsCollMk);   ballisticsCollMk   = null; }}
            ballisticsLastPath = null;
            if (!_radarTrackLastOpts || _radarTrackLastOpts.source === 'ballistic') {{  // שלב א4: רק בדיקה של מסלול בליסטי שייכת למסלול הקודם
                _clearRadarTrack();  // בדיקת מעקב מכ"ם שייכת למסלול הקודם — לא רלוונטית יותר
                _radarTrackLastPath = null;  // גרירת המכ"ם לא תריץ אותה מחדש
                if (_radarTrackInfoEl) _radarTrackInfoEl.textContent = '';  // מנקה את הסיכום הישן
                if (_radarTrackTimelineEl) _radarTrackTimelineEl.style.display = 'none';  // מסתיר את ציר הזמן הישן
            }}
        }}

        function _ballisticsDrawPath(path, impact) {{
            // מצייר את המסלול (קו + סמני פגיעה/קודקוד) על המפה — נקרא אחרי trajectory/solve מוצלח
            _ballisticsClearResult();
            if (!path || path.length < 2) return;
            ballisticsLastPath = path;
            var latlngs = path.map(function(p) {{ return [p.lat, p.lon]; }});
            ballisticsPathLn = L.polyline(latlngs, {{color: '#fab387', weight: 3}}).addTo(map);
            var last = path[path.length - 1];
            ballisticsImpactMk = L.marker([last.lat, last.lon], {{icon: _ballisticsMarkerIcon('#f38ba8')}})
                .bindTooltip('פגיעה', {{permanent:false, direction:'top'}}).addTo(map);
            if (impact && impact.apex_range_m !== undefined) {{
                // מאתר את נקודת-המסלול הקרובה ביותר למרחק-הקודקוד שדווח, לסימון על המפה
                var apexDist = impact.apex_range_m;
                var best = path[0], bestDiff = Infinity;
                path.forEach(function(p) {{
                    var diff = Math.abs(p.ground_dist - apexDist);
                    if (diff < bestDiff) {{ bestDiff = diff; best = p; }}
                }});
                ballisticsApexMk = L.marker([best.lat, best.lon], {{icon: _ballisticsMarkerIcon('#89b4fa')}})
                    .bindTooltip('קודקוד (' + Math.round(impact.apex_height_m) + ' מ\\' מעל הלוע)', {{permanent:false, direction:'top'}}).addTo(map);
            }}
        }}

        function _ballisticsShowCollision(coll) {{
            // מסמן נקודת-התנגשות-בקרקע (מ-terrain_check) — אדום בולט, שונה מסמן-הפגיעה הרגיל
            if (ballisticsCollMk) {{ map.removeLayer(ballisticsCollMk); ballisticsCollMk = null; }}
            if (!coll) return;
            ballisticsCollMk = L.marker([coll.lat, coll.lon], {{
                icon: L.divIcon({{html: '<div style="width:18px;height:18px;border-radius:50%;background:#f38ba8;' +
                    'border:3px solid #fff;box-shadow:0 0 4px #f38ba8;"></div>', className:'', iconSize:[18,18], iconAnchor:[9,9]}})
            }}).bindTooltip('התנגשות בקרקע — ' + Math.round(coll.ground_dist) + ' מ\\'', {{permanent:false, direction:'top'}}).addTo(map);
        }}

        // ציור פרופיל-צד: גובה-קרקע + גובה-מסלול לפי מרחק — אותו דפוס בדיוק כמו _drawProfileSingle (קו-ראייה)
        function _drawBallisticsProfile(canvas, path, terrainProfile) {{
            if (!canvas || !path || path.length < 2) return;
            canvas.width = canvas.offsetWidth || 260; canvas.height = canvas.offsetHeight || 110;
            var ctx = canvas.getContext('2d');
            var W = canvas.width, H = canvas.height;
            var PAD = {{l:40, r:6, t:6, b:18}};
            var cW = W - PAD.l - PAD.r, cH = H - PAD.t - PAD.b;
            var maxDist = path[path.length - 1].ground_dist || 1;
            var minE = Infinity, maxE = -Infinity;
            path.forEach(function(p) {{ if (p.alt_msl < minE) minE = p.alt_msl; if (p.alt_msl > maxE) maxE = p.alt_msl; }});
            if (terrainProfile) terrainProfile.forEach(function(p) {{
                if (p.ground_alt_msl < minE) minE = p.ground_alt_msl; if (p.ground_alt_msl > maxE) maxE = p.ground_alt_msl;
            }});
            var eRange = (maxE - minE) || 1;
            function xOf(d) {{ return PAD.l + (d / maxDist) * cW; }}
            function yOf(v) {{ return PAD.t + cH - (v - minE) / eRange * cH; }}
            ctx.fillStyle = '#1e1e2e'; ctx.fillRect(0, 0, W, H);
            ctx.fillStyle = '#666'; ctx.font = '9px Arial'; ctx.textAlign = 'right';
            for (var s = 0; s <= 2; s++) {{
                var val = minE + eRange * s / 2, y = yOf(val);
                ctx.fillText(Math.round(val) + 'מ', PAD.l - 3, y + 3);
                ctx.strokeStyle = '#2a2a3e'; ctx.lineWidth = 0.5;
                ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l + cW, y); ctx.stroke();
            }}
            if (terrainProfile && terrainProfile.length) {{
                ctx.beginPath(); ctx.strokeStyle = '#a6adc8'; ctx.fillStyle = 'rgba(166,173,200,0.15)'; ctx.lineWidth = 1.5;
                terrainProfile.forEach(function(p, i) {{
                    var x = xOf(p.ground_dist), y = yOf(p.ground_alt_msl);
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                }});
                ctx.stroke();
                ctx.lineTo(xOf(terrainProfile[terrainProfile.length - 1].ground_dist), PAD.t + cH);
                ctx.lineTo(xOf(terrainProfile[0].ground_dist), PAD.t + cH); ctx.closePath(); ctx.fill();
            }}
            ctx.beginPath(); ctx.strokeStyle = '#fab387'; ctx.lineWidth = 2;
            path.forEach(function(p, i) {{
                var x = xOf(p.ground_dist), y = yOf(p.alt_msl);
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }});
            ctx.stroke();
        }}

        function _ballisticsFmtAngle(a) {{
            // מציג זווית בשתי היחידות — אותו רעיון כמו fmt_angle ב-gui.py המקורי
            if (!a) return '-';
            return a.mils.toFixed(1) + ' מיל (' + a.deg.toFixed(3) + '°)';
        }}

        function _ballisticsImpactLines(imp) {{
            // אותו תוכן/סדר/ניסוח בדיוק כמו _impact_lines ב-gui.py המקורי (לפי בקשת שלב 3)
            var lines = [];
            lines.push('טווח אופקי: ' + imp.ground_range_m.toLocaleString() + ' מ\\'');
            lines.push('סטייה צידית: ' + Math.abs(imp.drift_z_m).toFixed(1) + ' מ\\' ' +
                (imp.drift_z_m >= 0 ? 'ימינה' : 'שמאלה') + ' = ' + _ballisticsFmtAngle(imp.deviation));
            lines.push('זמן מעוף: ' + imp.time_of_flight_s.toFixed(2) + ' ש\\'');
            lines.push('קודקוד: ' + Math.round(imp.apex_height_m) + ' מ\\' מעל הלוע (' + Math.round(imp.max_ordinate_msl_m) + ' מ\\' מעל פני הים)');
            lines.push('מהירות פגיעה: ' + imp.impact_velocity_mps.toFixed(1) + ' מ\\'/ש\\' (מאך ' + imp.impact_mach.toFixed(2) + ')');
            lines.push('זווית נפילה: ' + _ballisticsFmtAngle(imp.angle_of_fall));
            lines.push('ספין: ' + Math.round(imp.spin_muzzle_rps) + ' ← ' + Math.round(imp.spin_impact_rps) + ' סל\\'/ש\\'');
            lines.push('Sg בלוע: ' + imp.sg_muzzle.toFixed(2) + '  |  Sg מינימלי: ' + imp.sg_min.toFixed(2));
            lines.push('זווית מנוחה מרבית: ' + _ballisticsFmtAngle(imp.max_yaw_repose));
            return lines;
        }}

        function _ballisticsRunTerrainCheck(path, infoEl, onDone) {{
            // מריץ terrain_check על מסלול קיים ומציג שורת-סטטוס — נקרא אוטומטית אחרי כל trajectory/solve מוצלח
            fetch('http://localhost:5002/ballistics/terrain_check', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{path: path, safety_margin_m: 10.0, resolution_m: 75.0}})
            }})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                if (!d.ok) {{ if (onDone) onDone(null); return; }}
                _ballisticsShowCollision(d.clear ? null : d.first_collision);
                if (onDone) onDone(d);
            }})
            .catch(function() {{ if (onDone) onDone(null); }});
        }}

        // ═══════════════ A5: ירי מאזור לאזור (docs/PLAN_BALLISTICS_AREA_FIRE.md) ═══════════════
        var _af = {{mode: false, areas: [], draw: null, drawPts: [], drawLayer: null, jobId: null, timer: null,  // מצב הכלי
                   result: null, resultJob: null, visJob: null, vis: null, visSig: null, layers: null, estTimer: null, els: {{}}}};  // תוצאות ושכבות
        var _afRenderer = null;  // Canvas renderer — אלפי קווים בלי להאט את המפה
        var AF_GREEN = '#1e9e3a', AF_RED = '#d93025', AF_LAUNCH = '#e8710a', AF_TARGET = '#8e44ad';  // צבעים: נצפה / לא נצפה / שיגור / מטרה
        var AF_MAX_DRAW = 2000;  // דילול תצוגה מעל המספר הזה (החלטה 15)
        var AF_REJECT_NAMES = {{out_of_range: 'מחוץ לטווח', qe_limits: 'מחוץ לגבולות ההגבהה', min_range: 'קרוב מטווח מינימלי', max_tof: 'זמן מעוף ארוך', terrain: 'פוגע בשטח (רכס)'}};  // שמות סיבות הפסילה

        function _afSites() {{  // חתימה של המכ"מים המוצבים — לזיהוי "הצביעה ישנה" (החלטה 16)
            return JSON.stringify((_rs.sites || []).map(function(s) {{ var p = s.params || {{}}; return [s.name, p.lat, p.lon, p.h_antenna, p.range_km, p.start_bearing_deg, p.end_bearing_deg, p.ridge_margin_deg]; }}));  // שם, מיקום, אנטנה, טווח, גזרה, מרווח
        }}

        function _afLayers() {{  // שכבות המפה של הכלי (נוצרות פעם אחת)
            if (!_af.layers) {{  // עוד לא נוצרו
                _afRenderer = L.canvas({{padding: 0.5}});  // ציור על canvas
                _af.layers = {{areas: L.layerGroup().addTo(map), paths: L.layerGroup().addTo(map), heatL: L.layerGroup(), heatT: L.layerGroup(), sel: L.layerGroup().addTo(map)}};  // אזורים, מסלולים, מפות חום, בחירה
            }}
            return _af.layers;  // השכבות
        }}

        function _afSetMode(on) {{  // מתג "מסלול בודד | מאזור לאזור"
            _af.mode = on;  // המצב
            var body = _af.els.panelBody, sw = _af.els.switchRow, box = _af.els.box;  // הרכיבים
            Array.prototype.forEach.call(body.children, function(ch) {{  // כל רכיבי הפאנל
                if (ch === sw || ch === box) return;  // המתג והכלי החדש — מטופלים בנפרד
                if (on) {{ ch.dataset.afDisp = ch.style.display; ch.style.display = 'none'; }}  // מסתירים את המסלול הבודד, זוכרים את המצב
                else if (ch.dataset.afDisp !== undefined) {{ ch.style.display = ch.dataset.afDisp; delete ch.dataset.afDisp; }}  // מחזירים בדיוק כמו שהיה
            }});
            box.style.display = on ? 'flex' : 'none';  // הכלי החדש
            _af.els.btnSingle.style.background = on ? '#f5f5f5' : '#fab387';  // הדגשת המצב
            _af.els.btnArea.style.background = on ? '#fab387' : '#f5f5f5';  // כנ"ל
            var ly = _afLayers();  // השכבות
            [ly.areas, ly.paths, ly.sel].forEach(function(l) {{ if (on) {{ if (!map.hasLayer(l)) l.addTo(map); }} else map.removeLayer(l); }});  // השכבות גלויות רק במצב הזה
            if (!on) {{ map.removeLayer(ly.heatL); map.removeLayer(ly.heatT); _afCancelDraw(); }}  // יציאה מהמצב — מפות חום וציור
            else {{ _afApplyLayerToggles(); _afCheckStale(); }}  // חזרה — השכבות לפי הבחירה, ובדיקת צביעה ישנה
        }}

        function _afMk(parent, tag, text, css) {{  // יצירת רכיב קטן
            var el = L.DomUtil.create(tag, '', parent);  // הרכיב
            if (text) el.textContent = text;  // טקסט
            if (css) el.style.cssText = css;  // עיצוב
            return el;  // הרכיב
        }}
        function _afBtn(parent, text, tip, fn, css) {{  // כפתור ≥24px עם שם נגיש
            var b = _afMk(parent, 'button', text, 'font-size:10px;min-height:24px;padding:1px 6px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;' + (css || ''));  // הכפתור
            b.title = tip; b.setAttribute('aria-label', tip);  // נגישות
            L.DomEvent.on(b, 'click', function(e) {{ L.DomEvent.stopPropagation(e); fn(); }});  // לחיצה
            return b;  // הכפתור
        }}
        function _afNum(parent, label, val, tip) {{  // שדה מספר עם תווית (ריק = בלי גבול)
            var w = _afMk(parent, 'label', '', 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#555;');  // השורה
            w.title = tip || '';  // הסבר
            _afMk(w, 'span', label, 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;');  // תווית
            var i = _afMk(w, 'input', '', 'width:58px;flex-shrink:0;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;');  // השדה
            i.type = 'number'; i.value = val; i.setAttribute('aria-label', label);  // ערך ונגישות
            L.DomEvent.on(i, 'change', _afScheduleEstimate);  // שינוי = הערכה מחדש
            return i;  // השדה
        }}
        function _afChk(parent, label, checked) {{  // תיבת סימון
            var w = _afMk(parent, 'label', '', 'display:flex;align-items:center;gap:4px;font-size:9px;color:#555;cursor:pointer;');  // השורה
            var c = _afMk(w, 'input'); c.type = 'checkbox'; c.checked = checked;  // התיבה
            _afMk(w, 'span', label);  // תווית
            return c;  // התיבה
        }}

        function _afBuild(panelBody) {{  // בניית מתג המצבים והכלי — נקרא בסוף בניית הפאנל הבליסטי
            _af.els.panelBody = panelBody;  // הפאנל
            var sw = L.DomUtil.create('div', '');  // שורת המתג
            sw.style.cssText = 'display:flex;gap:2px;margin-bottom:3px;';  // עיצוב
            panelBody.insertBefore(sw, panelBody.firstChild);  // בראש הפאנל
            _af.els.switchRow = sw;  // נשמר
            _af.els.btnSingle = _afBtn(sw, 'מסלול בודד', 'מצב מסלול בודד — הכלי הקיים, בלי שינוי', function() {{ _afSetMode(false); }}, 'flex:1;font-weight:bold;background:#fab387;');  // מצב רגיל
            _af.els.btnArea = _afBtn(sw, '🗺 מאזור לאזור', 'מצב חדש: אזורי שיגור ואזורי מטרה, ספירת כל המסלולים האפשריים', function() {{ _afSetMode(true); }}, 'flex:1;font-weight:bold;');  // המצב החדש
            var box = _afMk(panelBody, 'div', '', 'display:none;flex-direction:column;gap:3px;');  // מכל הכלי
            _af.els.box = box;  // נשמר
            _afMk(box, 'div', 'סמן אזורי שיגור (רשת כל 500 מ\\') ואזורי מטרה (כל 200 מ\\'). מהירות הלוע, המטאו והפגז נלקחים מהגדרות הכלי הבליסטי.', 'font-size:9px;color:#555;line-height:1.35;');  // הסבר קצר
            var drawRow = _afMk(box, 'div', '', 'display:flex;gap:2px;flex-wrap:wrap;');  // כפתורי ציור
            _afBtn(drawRow, '✏️ מצולע שיגור', 'ציור מצולע שיגור: לחיצות על המפה, ואז "סיים"', function() {{ _afStartDraw('launch', 'poly'); }}, 'border-color:' + AF_LAUNCH + ';');  // מצולע שיגור
            _afBtn(drawRow, '▭ מלבן שיגור', 'מלבן שיגור: שתי לחיצות — פינה ופינה נגדית', function() {{ _afStartDraw('launch', 'rect'); }}, 'border-color:' + AF_LAUNCH + ';');  // מלבן שיגור
            _afBtn(drawRow, '✏️ מצולע מטרה', 'ציור מצולע מטרה: לחיצות על המפה, ואז "סיים"', function() {{ _afStartDraw('target', 'poly'); }}, 'border-color:' + AF_TARGET + ';');  // מצולע מטרה
            _afBtn(drawRow, '▭ מלבן מטרה', 'מלבן מטרה: שתי לחיצות — פינה ופינה נגדית', function() {{ _afStartDraw('target', 'rect'); }}, 'border-color:' + AF_TARGET + ';');  // מלבן מטרה
            var drawCtl = _afMk(box, 'div', '', 'display:none;gap:3px;align-items:center;font-size:9px;color:#333;');  // מצב ציור פעיל
            _af.els.drawMsg = _afMk(drawCtl, 'span', '');  // הודעת הציור
            _af.els.drawDone = _afBtn(drawCtl, '✔ סיים', 'סיום המצולע (לפחות 3 נקודות)', _afFinishDraw);  // סיום
            _afBtn(drawCtl, 'בטל', 'ביטול הציור', _afCancelDraw);  // ביטול
            _af.els.drawCtl = drawCtl;  // נשמר
            _af.els.list = _afMk(box, 'div', '', 'display:flex;flex-direction:column;gap:2px;');  // רשימת האזורים
            var saveRow = _afMk(box, 'div', '', 'display:flex;gap:2px;flex-wrap:wrap;align-items:center;');  // שמירה וטעינה של סט אזורים
            _af.els.setSel = _afMk(saveRow, 'select', '', 'font-size:10px;min-height:24px;max-width:120px;');  // סטים שמורים
            _af.els.setSel.setAttribute('aria-label', 'סטים שמורים של אזורים');  // נגישות
            _afBtn(saveRow, '📂 טען', 'טעינת סט האזורים שנבחר', _afLoadSet);  // טעינה
            _afBtn(saveRow, '💾 שמור', 'שמירת האזורים הנוכחיים בשם', _afSaveSet);  // שמירה
            _afBtn(saveRow, '🗑', 'מחיקת הסט שנבחר', _afDeleteSet);  // מחיקה
            _afMk(box, 'div', 'אפשרויות', 'font-size:9px;font-weight:bold;color:#888;border-top:1px solid #eee;padding-top:2px;');  // כותרת
            var gr = _afMk(box, 'div', '', 'display:flex;gap:8px;');  // ענפים
            _af.els.low = _afChk(gr, 'ענף נמוך', true); _af.els.high = _afChk(gr, 'ענף גבוה', true);  // שני הענפים (החלטה 2)
            L.DomEvent.on(_af.els.low, 'change', _afScheduleEstimate); L.DomEvent.on(_af.els.high, 'change', _afScheduleEstimate);  // הערכה מחדש
            _af.els.qeMin = _afNum(box, 'הגבהה מינימלית [מיל]', '', 'ריק = בלי גבול');  // גבול תחתון
            _af.els.qeMax = _afNum(box, 'הגבהה מרבית [מיל]', '', 'ריק = בלי גבול');  // גבול עליון
            _af.els.minRange = _afNum(box, 'טווח מינימלי [מ\\']', '', 'ריק = בלי');  // טווח מינימלי
            _af.els.maxTof = _afNum(box, 'זמן מעוף מרבי [ש\\']', '', 'ריק = בלי');  // זמן מעוף מרבי
            _af.els.crest = _afChk(box, 'בדיקת מעבר מעל השטח (רכס)', true);  // רכס
            L.DomEvent.on(_af.els.crest, 'change', _afScheduleEstimate);  // הערכה מחדש
            _af.els.margin = _afNum(box, 'מרווח בטיחות מעל השטח [מ\\']', 0, 'כמה מטרים מעל הקרקע המסלול חייב לעבור');  // מרווח
            _af.els.est = _afMk(box, 'div', 'סמן לפחות אזור שיגור אחד ואזור מטרה אחד.', 'font-size:9px;color:#555;');  // הערכה
            var runRow = _afMk(box, 'div', '', 'display:flex;gap:3px;');  // הרצה
            _af.els.run = _afBtn(runRow, '▶ חשב מסלולים', 'חישוב כל המסלולים האפשריים מכל נקודת שיגור לכל נקודת מטרה', _afRun, 'flex:1;background:#f9e2af;font-weight:bold;');  // הרצה
            _af.els.cancel = _afBtn(runRow, '⏹ בטל', 'ביטול החישוב', _afCancel);  // ביטול
            _af.els.cancel.style.display = 'none';  // רק בזמן ריצה
            _af.els.info = _afMk(box, 'div', '', 'font-size:9.5px;color:#222;white-space:pre-line;line-height:1.35;');  // התקדמות וסיכום
            _af.els.info.setAttribute('role', 'status');  // קוראי מסך מכריזים
            var res = _afMk(box, 'div', '', 'display:none;flex-direction:column;gap:3px;border-top:1px solid #eee;padding-top:3px;');  // אזור התוצאות
            _af.els.res = res;  // נשמר
            var vrow = _afMk(res, 'div', '', 'display:flex;gap:3px;align-items:center;flex-wrap:wrap;');  // צביעה
            _af.els.recolor = _afBtn(vrow, '🎨 עדכן צביעה', 'צביעה מחדש לפי כל המכ"מים המוצבים: ירוק = נצפה, אדום = לא נצפה', _afRecolor, 'background:#e8f5e9;');  // עדכן צביעה (החלטה 16)
            _af.els.stale = _afMk(vrow, 'span', '', 'font-size:9px;color:#b00020;');  // הודעת "ישנה"
            _afMk(res, 'div', '🟩 ירוק = לפחות מכ"ם מוצב אחד רואה את הקטע · 🟥 אדום = אף מכ"ם לא רואה. "רואה" = בטווח, בגזרה ולא מוסתר ע"י השטח (קו ראייה — קירוב; בדיקת מעקב מלאה למסלול שנבחר).', 'font-size:8.5px;color:#555;line-height:1.35;');  // מקרא (טקסט + אייקון, לא רק צבע)
            var lrow = _afMk(res, 'div', '', 'display:flex;gap:8px;flex-wrap:wrap;');  // שכבות
            _af.els.showPaths = _afChk(lrow, 'מסלולים', true); _af.els.showHeatL = _afChk(lrow, 'מפת חום שיגור', false); _af.els.showHeatT = _afChk(lrow, 'מפת חום מטרה', false);  // מתגי שכבות
            [_af.els.showPaths, _af.els.showHeatL, _af.els.showHeatT].forEach(function(c) {{ L.DomEvent.on(c, 'change', _afApplyLayerToggles); }});  // החלפה
            var frow = _afMk(res, 'div', '', 'display:flex;gap:3px;flex-wrap:wrap;align-items:center;font-size:9px;');  // סינון
            _af.els.fBranch = _afMk(frow, 'select', '', 'font-size:10px;min-height:24px;');  // ענף
            [['all', 'כל הענפים'], ['low', 'נמוך'], ['high', 'גבוה']].forEach(function(o) {{ var op = _afMk(_af.els.fBranch, 'option', o[1]); op.value = o[0]; }});  // אפשרויות
            _af.els.fBranch.setAttribute('aria-label', 'סינון לפי ענף');  // נגישות
            _af.els.fLaunch = _afMk(frow, 'select', '', 'font-size:10px;min-height:24px;max-width:110px;'); _af.els.fLaunch.setAttribute('aria-label', 'סינון לפי אזור שיגור');  // אזור שיגור
            _af.els.fTarget = _afMk(frow, 'select', '', 'font-size:10px;min-height:24px;max-width:110px;'); _af.els.fTarget.setAttribute('aria-label', 'סינון לפי אזור מטרה');  // אזור מטרה
            _af.els.fUnseen = _afChk(frow, 'רק לא נצפים', false);  // רק לא נצפים
            [_af.els.fBranch, _af.els.fLaunch, _af.els.fTarget, _af.els.fUnseen].forEach(function(el) {{ L.DomEvent.on(el, 'change', _afRender); }});  // סינון = ציור מחדש
            _af.els.drawNote = _afMk(res, 'div', '', 'font-size:9px;color:#555;');  // הודעת דילול
            var trow = _afMk(res, 'div', '', 'display:flex;gap:3px;');  // ייצוא
            _afBtn(trow, '⬇ CSV', 'ייצוא כל המסלולים האפשריים לקובץ CSV (כולל הנראות)', _afCsv);  // CSV
            _af.els.table = _afMk(res, 'div', '', 'max-height:180px;overflow:auto;border:1px solid #eee;');  // טבלה
            _af.els.selInfo = _afMk(res, 'div', '', 'font-size:9px;color:#222;white-space:pre-line;');  // פרטי מסלול שנבחר
            _afRefreshSets();  // רשימת הסטים השמורים
            _afRenderAreas();  // רשימה ריקה
        }}

        // ── ציור אזורים ──
        function _afStartDraw(kind, shape) {{  // התחלת ציור
            _afCancelDraw();  // ציור קודם
            _af.draw = {{kind: kind, shape: shape}}; _af.drawPts = [];  // המצב
            _af.els.drawCtl.style.display = 'flex';  // הודעה + כפתורים
            _af.els.drawDone.style.display = shape === 'poly' ? '' : 'none';  // "סיים" רק במצולע
            _af.els.drawMsg.textContent = shape === 'poly' ? 'לחץ על המפה להוספת נקודות…' : 'לחץ על פינה ראשונה…';  // הנחיה
            map.getContainer().style.cursor = 'crosshair';  // סמן
        }}
        function _afCancelDraw() {{  // ביטול ציור
            _af.draw = null; _af.drawPts = [];  // ניקוי
            if (_af.drawLayer) {{ map.removeLayer(_af.drawLayer); _af.drawLayer = null; }}  // הקו הזמני
            if (_af.els.drawCtl) _af.els.drawCtl.style.display = 'none';  // הסתרה
            map.getContainer().style.cursor = '';  // סמן רגיל
        }}
        function _afMapClick(latlng) {{  // לחיצה על המפה במצב מאזור לאזור
            if (!_af.draw) return;  // לא בציור — לא עושים כלום (לא מזיזים תותח)
            _af.drawPts.push([latlng.lat, latlng.lng]);  // נקודה
            var col = _af.draw.kind === 'launch' ? AF_LAUNCH : AF_TARGET;  // צבע
            if (_af.drawLayer) map.removeLayer(_af.drawLayer);  // הקו הקודם
            if (_af.draw.shape === 'rect') {{  // מלבן
                if (_af.drawPts.length === 1) {{ _af.drawLayer = L.circleMarker(latlng, {{radius: 4, color: col}}).addTo(map); _af.els.drawMsg.textContent = 'לחץ על הפינה הנגדית…'; return; }}  // פינה ראשונה
                var a = _af.drawPts[0], b = _af.drawPts[1];  // שתי הפינות
                _afAddArea(_af.draw.kind, [[a[0], a[1]], [a[0], b[1]], [b[0], b[1]], [b[0], a[1]]]);  // ארבע הפינות
                _afCancelDraw(); return;  // סיום
            }}
            _af.drawLayer = L.polyline(_af.drawPts, {{color: col, dashArray: '4 4', weight: 2}}).addTo(map);  // קו זמני
            _af.els.drawMsg.textContent = _af.drawPts.length + ' נקודות — המשך, או "סיים"';  // הנחיה
        }}
        function _afFinishDraw() {{  // סיום מצולע
            if (!_af.draw || _af.drawPts.length < 3) {{ _af.els.drawMsg.textContent = 'צריך לפחות 3 נקודות'; return; }}  // מעט מדי
            _afAddArea(_af.draw.kind, _af.drawPts.slice());  // הוספה
            _afCancelDraw();  // סיום
        }}
        function _afAddArea(kind, poly) {{  // הוספת אזור לרשימה
            var n = _af.areas.filter(function(a) {{ return a.kind === kind; }}).length + 1;  // מספור לפי סוג
            _af.areas.push({{kind: kind, polygon: poly, name: (kind === 'launch' ? 'שיגור ' : 'מטרה ') + n}});  // האזור
            _afRenderAreas(); _afScheduleEstimate();  // ציור והערכה
        }}
        function _afRenderAreas() {{  // רשימת האזורים בפאנל + על המפה
            var ly = _afLayers(); ly.areas.clearLayers();  // ניקוי המפה
            var list = _af.els.list; list.innerHTML = '';  // ניקוי הרשימה
            _af.areas.forEach(function(a, i) {{  // כל אזור
                var col = a.kind === 'launch' ? AF_LAUNCH : AF_TARGET;  // צבע לפי סוג
                L.polygon(a.polygon, {{color: col, weight: 2, fillOpacity: 0.08, dashArray: a.kind === 'target' ? '6 3' : null}}).bindTooltip(a.name).addTo(ly.areas);  // על המפה (מטרה מקווקו — לא רק צבע)
                var row = _afMk(list, 'div', '', 'display:flex;gap:3px;align-items:center;font-size:9px;');  // שורה
                _afMk(row, 'span', a.kind === 'launch' ? '🚀' : '🎯', 'color:' + col + ';');  // סמל סוג
                var nm = _afMk(row, 'input', '', 'flex:1;min-width:0;font-size:10px;padding:1px 3px;border:1px solid #ddd;border-radius:3px;direction:rtl;');  // שם
                nm.value = a.name; nm.setAttribute('aria-label', 'שם האזור');  // ערך ונגישות
                L.DomEvent.on(nm, 'change', function() {{ a.name = nm.value.trim().slice(0, 80) || a.name; _afRenderAreas(); }});  // עדכון שם
                _afBtn(row, '🔍', 'התמקד באזור', function() {{ map.fitBounds(L.latLngBounds(a.polygon), {{maxZoom: 14}}); }});  // זום
                _afBtn(row, '✕', 'מחיקת האזור', function() {{ _af.areas.splice(i, 1); _afRenderAreas(); _afScheduleEstimate(); }});  // מחיקה
            }});
            if (!_af.areas.length) _afMk(list, 'div', 'אין עדיין אזורים.', 'font-size:9px;color:#888;');  // ריק
        }}

        // ── סטים שמורים (עמדות שמורות, כלי ballistics_areas) ──
        function _afRefreshSets() {{  // רשימת הסטים מהשרת
            fetch('http://localhost:5002/stations/list?tool=ballistics_areas').then(function(r) {{ return r.json(); }}).then(function(list) {{
                var sel = _af.els.setSel; sel.innerHTML = '';  // ניקוי
                (Array.isArray(list) ? list : []).forEach(function(s) {{ var o = _afMk(sel, 'option', s.name); o.value = s.name; }});  // אפשרויות
                if (!sel.options.length) {{ var o = _afMk(sel, 'option', '(אין סטים שמורים)'); o.value = ''; }}  // ריק
            }}).catch(function() {{}});  // שרת לא זמין — לא קריטי
        }}
        function _afSaveSet() {{  // שמירת האזורים בשם
            if (!_af.areas.length) {{ _af.els.est.textContent = 'אין אזורים לשמירה'; return; }}  // ריק
            var name = prompt('שם לסט האזורים:', 'אזורים ' + new Date().toLocaleDateString('he-IL'));  // שם
            if (!name) return;  // בוטל
            fetch('http://localhost:5002/stations/save', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{tool: 'ballistics_areas', name: name.slice(0, 100), params: {{areas: _af.areas.map(function(a) {{ return {{name: a.name, kind: a.kind, polygon: a.polygon}}; }})}}}})}})  // הנתונים
                .then(function() {{ _afRefreshSets(); _af.els.est.textContent = 'נשמר: ' + name; }}).catch(function(e) {{ _af.els.est.textContent = 'שמירה נכשלה: ' + e.message; }});  // תוצאה
        }}
        function _afLoadSet() {{  // טעינת סט
            var name = _af.els.setSel.value; if (!name) return;  // לא נבחר
            fetch('http://localhost:5002/stations/list?tool=ballistics_areas').then(function(r) {{ return r.json(); }}).then(function(list) {{
                var s = (list || []).filter(function(x) {{ return x.name === name; }})[0];  // הסט
                if (!s || !s.params || !Array.isArray(s.params.areas)) return;  // לא תקין
                _af.areas = s.params.areas.filter(function(a) {{ return Array.isArray(a.polygon) && a.polygon.length >= 3; }}).map(function(a) {{ return {{name: String(a.name || ''), kind: a.kind === 'target' ? 'target' : 'launch', polygon: a.polygon}}; }});  // אזורים תקינים בלבד
                _afRenderAreas(); _afScheduleEstimate();  // ציור והערכה
                if (_af.areas.length) map.fitBounds(L.latLngBounds([].concat.apply([], _af.areas.map(function(a) {{ return a.polygon; }}))), {{maxZoom: 13}});  // התמקדות
            }}).catch(function() {{}});  // כשל — לא קריטי
        }}
        function _afDeleteSet() {{  // מחיקת סט
            var name = _af.els.setSel.value; if (!name || !confirm('למחוק את "' + name + '"?')) return;  // אישור
            fetch('http://localhost:5002/stations/delete', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{tool: 'ballistics_areas', name: name}})}}).then(_afRefreshSets);  // מחיקה
        }}

        // ── בקשה, הערכה והרצה ──
        function _afRequest() {{  // בניית בקשת החישוב מהאזורים, מהאפשרויות ומהגדרות הכלי הבליסטי
            var c = _ballisticsGetCommonParams() || {{}};  // מהירות לוע, מטאו, פגז, יחידות
            function v(el) {{ return el.value === '' ? null : parseFloat(el.value); }}  // ערך או null
            var groups = []; if (_af.els.low.checked) groups.push('low'); if (_af.els.high.checked) groups.push('high');  // ענפים
            return {{launch_areas: _af.areas.filter(function(a) {{ return a.kind === 'launch'; }}).map(function(a) {{ return {{name: a.name, polygon: a.polygon}}; }}),  // אזורי שיגור
                     target_areas: _af.areas.filter(function(a) {{ return a.kind === 'target'; }}).map(function(a) {{ return {{name: a.name, polygon: a.polygon}}; }}),  // אזורי מטרה
                     mv: c.mv, met: c.met, fitting: c.fitting, dt: c.dt, coriolis: c.coriolis, earth_curvature: c.earth_curvature,  // פרמטרי ירי
                     angle_unit: 'mils', groups: groups, qe_min: v(_af.els.qeMin), qe_max: v(_af.els.qeMax),  // גבולות במילים
                     min_range_m: v(_af.els.minRange), max_tof_s: v(_af.els.maxTof), crest: _af.els.crest.checked, safety_margin_m: v(_af.els.margin) || 0}};  // סינונים
        }}
        function _afFmtTime(s) {{  // שניות → טקסט קריא
            if (s == null) return '';  // אין
            return s < 90 ? Math.max(1, Math.round(s)) + " שנ'" : (s < 5400 ? Math.round(s / 60) + " דק'" : (s / 3600).toFixed(1) + ' שעות');  // שניות/דקות/שעות
        }}
        function _afScheduleEstimate() {{  // הערכה מחדש (debounce) אחרי שינוי
            clearTimeout(_af.estTimer); _af.estTimer = setTimeout(_afEstimate, 400);  // 0.4 שנ'
        }}
        function _afEstimate() {{  // הערכה לפני הרצה (החלטה 11: בלי תקרה, אבל עם הערכה)
            var req = _afRequest();  // הבקשה
            if (!req.launch_areas.length || !req.target_areas.length) {{ _af.els.est.textContent = 'סמן לפחות אזור שיגור אחד ואזור מטרה אחד.'; return; }}  // חסר
            fetch('http://localhost:5002/ballistics/area/estimate', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(req)}})
            .then(function(r) {{ return r.json(); }}).then(function(d) {{
                if (d.error) {{ _af.els.est.textContent = '⚠️ ' + d.error; return; }}  // שגיאה
                _af.els.est.textContent = d.launch_points.toLocaleString() + ' נקודות שיגור × ' + d.target_points.toLocaleString() + ' נקודות מטרה = ' + d.pairs.toLocaleString() + ' זוגות (' + d.trajectories_max.toLocaleString() + ' מסלולים לבדיקה). זמן משוער: ' + _afFmtTime(d.eta_s) + (d.cells_missing ? ' (מתוכו שליפת שטח: ' + _afFmtTime(d.eta_parts_s.terrain) + ', בפעם הבאה מהמטמון)' : '');  // ההערכה
            }}).catch(function() {{ _af.els.est.textContent = 'השרת לא זמין להערכה'; }});  // כשל
        }}
        function _afRun() {{  // התחלת חישוב
            var req = _afRequest();  // הבקשה
            if (!req.launch_areas.length || !req.target_areas.length) {{ _af.els.info.textContent = 'סמן לפחות אזור שיגור אחד ואזור מטרה אחד.'; return; }}  // חסר
            if (!req.groups.length) {{ _af.els.info.textContent = 'בחר לפחות ענף אחד.'; return; }}  // בלי ענפים
            _afCancel(true);  // job קודם
            _af.result = null; _af.vis = null; _af.visJob = null;  // ניקוי תוצאה קודמת
            _afLayers().paths.clearLayers(); _af.els.res.style.display = 'none';  // ניקוי המפה
            _af.els.info.textContent = 'מתחיל…';  // משוב
            fetch('http://localhost:5002/ballistics/area/start', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(req)}})
            .then(function(r) {{ return r.json(); }}).then(function(d) {{
                if (d.error || !d.job_id) {{ _af.els.info.textContent = '⚠️ ' + (d.error || 'שגיאה'); return; }}  // שגיאה
                _af.jobId = d.job_id; _af.els.cancel.style.display = ''; _af.els.run.disabled = true;  // מצב ריצה
                _af.timer = setInterval(function() {{ _afPoll(d.job_id, false); }}, 1000);  // polling
            }}).catch(function(e) {{ _af.els.info.textContent = '⚠️ ' + e.message; }});  // כשל
        }}
        function _afCancel(silent) {{  // ביטול job פעיל
            if (_af.timer) {{ clearInterval(_af.timer); _af.timer = null; }}  // עצירת polling
            var id = _af.jobId; _af.jobId = null;  // ה-job
            if (id) fetch('http://localhost:5002/ballistics/area/cancel?job_id=' + id, {{method: 'POST'}}).catch(function() {{}});  // ביטול בשרת
            _af.els.cancel.style.display = 'none'; _af.els.run.disabled = false;  // מצב רגיל
            if (id && silent !== true) _af.els.info.textContent = 'בוטל.';  // משוב
        }}
        function _afPoll(jobId, isVis) {{  // מצב job (חישוב או צביעה)
            fetch('http://localhost:5002/ballistics/area/status?job_id=' + jobId).then(function(r) {{ return r.json(); }}).then(function(d) {{
                if (isVis ? jobId !== _af.visJob : jobId !== _af.jobId) return;  // job שהוחלף
                var el = _af.els.info;  // שורת המצב
                if (d.status === 'running') {{  // עדיין רץ
                    var prog = d.batches_total ? ' (' + d.batches_done + '/' + d.batches_total + ')' : '';  // שליפה
                    el.textContent = (isVis ? '🎨 ' : '⏳ ') + (d.note || 'מחשב…') + prog + (d.eta_s ? ' · נותרו כ-' + _afFmtTime(d.eta_s) : '');  // התקדמות + הערכה
                    return;  // ממתין
                }}
                if (isVis) {{ clearInterval(_af.visTimer); _af.visTimer = null; }} else {{ clearInterval(_af.timer); _af.timer = null; _af.jobId = null; _af.els.cancel.style.display = 'none'; _af.els.run.disabled = false; }}  // עצירה
                if (d.status === 'done') {{  // הצליח
                    if (isVis) {{ _af.vis = d.result; _af.visSig = _af.visSigPending; _afCheckStale(); _afRender(); _afSummary(); }}  // צביעה
                    else {{ _af.result = d.result; _af.resultJob = jobId; _af.visJob = _af.vis = null; _af.visSig = null; _afShowResult(); }}  // תוצאה חדשה (מזהה ה-job נשמר — לצביעה ול-CSV)
                }} else el.textContent = d.status === 'error' ? '⚠️ ' + (d.error || 'שגיאה') : (isVis ? 'הצביעה בוטלה.' : 'בוטל.');  // שגיאה/ביטול
                if (el.scrollIntoView) el.scrollIntoView({{block: 'nearest', behavior: 'smooth'}});  // T23: גלילה לתוצאה
            }}).catch(function() {{}});  // כשל רשת — ה-tick הבא
        }}

        // ── תוצאות ──
        function _afShowResult() {{  // אחרי חישוב: מילוי מסננים, ציור, סיכום, וצביעה ראשונה אוטומטית
            var r = _af.result;  // התוצאה
            _af.els.res.style.display = 'flex';  // אזור התוצאות
            [['fLaunch', r.areas.launch, 'כל אזורי השיגור'], ['fTarget', r.areas.target, 'כל אזורי המטרה']].forEach(function(x) {{  // מסנני אזורים
                var sel = _af.els[x[0]]; sel.innerHTML = '';  // ניקוי
                var o = _afMk(sel, 'option', x[2]); o.value = '-1';  // הכול
                x[1].forEach(function(nm, i) {{ var op = _afMk(sel, 'option', nm); op.value = String(i); }});  // כל אזור
            }});
            _afDrawHeat(); _afRender(); _afSummary();  // ציור וסיכום
            if ((_rs.sites || []).length) _afRecolor();  // יש מכ"מים — צביעה ראשונה אוטומטית
            else {{ _af.visSig = _afSites(); _afCheckStale(); }}  // אין מכ"מים — הכול אדום (החלטה 14)
        }}
        function _afSummary() {{  // טקסט הסיכום
            var r = _af.result; if (!r) return;  // אין
            var s = r.summary, v = r.verification || {{}};  // קיצורים
            var lines = ['✅ ' + s.pairs_feasible.toLocaleString() + ' מתוך ' + s.pairs.toLocaleString() + ' זוגות אפשריים · ' + s.trajectories_feasible.toLocaleString() + ' מסלולים אפשריים (מתוך ' + s.trajectories_checked.toLocaleString() + ' שנבדקו).'];  // ספירות (החלטה 10)
            var rej = Object.keys(s.rejected).filter(function(k) {{ return s.rejected[k]; }}).map(function(k) {{ return AF_REJECT_NAMES[k] + ': ' + s.rejected[k].toLocaleString(); }});  // פסילות
            if (rej.length) lines.push('נפסלו: ' + rej.join(' · '));  // פירוט
            if (v.checked) lines.push('דיוק (מדגם ' + v.checked + ' מסלולים, מסלול אמיתי מכל נקודת שיגור): החטאה מרבית ' + v.miss_max_m + ' מ\\', RMS ' + v.miss_rms_m + ' מ\\'; שגיאת הגבהה עד ' + v.qe_err_max_mils + ' מיל.');  // אימות (החלטה 1)
            if (_af.vis) {{ var vs = _af.vis.summary; lines.push('🎨 ' + vs.radars + ' מכ"מים: ' + vs.trajectories_seen_any.toLocaleString() + ' מסלולים נצפים בחלקם, ' + vs.trajectories_seen_full.toLocaleString() + ' במלואם, ' + vs.trajectories_unseen.toLocaleString() + ' לא נצפים כלל.'); }}  // נראות
            lines.push('זמן חישוב: ' + _afFmtTime(s.elapsed_s) + '.');  // זמן
            _af.els.info.textContent = lines.join(String.fromCharCode(10));  // שורות
        }}
        function _afMask(i) {{  // מסיכת הנראות של מסלול (או null אם לא חושבה)
            return _af.vis && _af.vis.masks ? _af.vis.masks[i] : null;  // המסיכה
        }}
        function _afFiltered() {{  // אינדקסים של מסלולים אחרי הסינון
            var r = _af.result, out = [];  // התוצאה
            var fb = _af.els.fBranch.value, fl = parseInt(_af.els.fLaunch.value || '-1', 10), ft = parseInt(_af.els.fTarget.value || '-1', 10), fu = _af.els.fUnseen.checked;  // המסננים
            r.rows.forEach(function(row, i) {{  // כל מסלול
                if (fb !== 'all' && row.group !== fb) return;  // ענף
                if (fl >= 0 && row.la !== fl) return;  // אזור שיגור
                if (ft >= 0 && row.ta !== ft) return;  // אזור מטרה
                if (fu) {{ var m = _afMask(i); if (m && m.some(function(x) {{ return x; }})) return; }}  // רק לא נצפים
                out.push(i);  // עבר
            }});
            return out;  // הרשימה
        }}
        function _afRender() {{  // ציור המסלולים (ירוק/אדום לפי קטע) + טבלה
            var r = _af.result; if (!r) return;  // אין
            var ly = _afLayers(); ly.paths.clearLayers(); ly.sel.clearLayers();  // ניקוי
            var idx = _afFiltered(), shown = idx;  // אחרי סינון
            if (idx.length > AF_MAX_DRAW) {{ var step = idx.length / AF_MAX_DRAW; shown = []; for (var k = 0; k < AF_MAX_DRAW; k++) shown.push(idx[Math.floor(k * step)]); }}  // דילול שווה (החלטה 15)
            _af.els.drawNote.textContent = idx.length > AF_MAX_DRAW ? 'מוצגים ' + AF_MAX_DRAW.toLocaleString() + ' מתוך ' + idx.length.toLocaleString() + ' מסלולים (דילול תצוגה — כולם נספרים). צמצם בסינון כדי לראות הכול.' : idx.length.toLocaleString() + ' מסלולים מוצגים.';  // הודעה
            if (_af.els.showPaths.checked) shown.forEach(function(i) {{  // ציור
                var row = r.rows[i], m = _afMask(i), p = row.path;  // המסלול
                var seg = [p[0]], cur = m ? !!m[0] : false;  // קטע נוכחי וצבעו
                function flush() {{ if (seg.length > 1) L.polyline(seg.map(function(q) {{ return [q[0], q[1]]; }}), {{renderer: _afRenderer, color: cur ? AF_GREEN : AF_RED, weight: 2, opacity: 0.75}}).on('click', function() {{ _afSelect(i); }}).addTo(ly.paths); }}  // קטע בצבע אחד
                for (var k = 1; k < p.length; k++) {{  // כל נקודה
                    var vis = m ? !!m[k] : false;  // נראות הנקודה
                    if (vis !== cur) {{ seg.push(p[k]); flush(); seg = [p[k]]; cur = vis; }}  // מעבר צבע — סוגרים קטע
                    else seg.push(p[k]);  // ממשיכים
                }}
                flush();  // הקטע האחרון
            }});
            _afTable(idx);  // טבלה
        }}
        function _afTable(idx) {{  // טבלת המסלולים (200 ראשונים אחרי סינון)
            var r = _af.result, t = _af.els.table; t.innerHTML = '';  // ניקוי
            var tbl = _afMk(t, 'table', '', 'border-collapse:collapse;font-size:9px;width:100%;direction:rtl;');  // הטבלה
            var hr = _afMk(tbl, 'tr');  // כותרת
            ['שיגור', 'מטרה', 'ענף', 'הגבהה [מיל]', 'אזימוט [מיל]', 'מעוף [ש\\']', 'נצפה'].forEach(function(h) {{ _afMk(hr, 'th', h, 'position:sticky;top:0;background:#f5f5f5;padding:1px 3px;border-bottom:1px solid #ddd;'); }});  // עמודות
            idx.slice(0, 200).forEach(function(i) {{  // שורות
                var row = r.rows[i], m = _afMask(i);  // המסלול
                var seen = m ? Math.round(100 * m.filter(function(x) {{ return x; }}).length / m.length) + '%' : '—';  // אחוז נצפה
                var tr = _afMk(tbl, 'tr', '', 'cursor:pointer;');  // שורה
                [r.areas.launch[row.la] + ' #' + (row.lp + 1), r.areas.target[row.ta] + ' #' + (row.tp + 1), row.group === 'low' ? 'נמוך' : 'גבוה', row.qe.mils, row.fire_azimuth.mils, row.tof_s, seen].forEach(function(v) {{ _afMk(tr, 'td', String(v), 'padding:1px 3px;border-bottom:1px solid #f0f0f0;white-space:nowrap;'); }});  // תאים
                L.DomEvent.on(tr, 'click', function() {{ _afSelect(i); }});  // בחירה
            }});
            if (idx.length > 200) _afMk(t, 'div', 'מוצגות 200 שורות ראשונות — הכול ב-CSV.', 'font-size:9px;color:#888;padding:2px;');  // הערה
        }}
        function _afSelect(i) {{  // מסלול שנבחר: הדגשה, פרטים, ופתיחה במסלול בודד
            var r = _af.result, row = r.rows[i], ly = _afLayers(); ly.sel.clearLayers();  // ניקוי
            L.polyline(row.path.map(function(q) {{ return [q[0], q[1]]; }}), {{color: '#1565c0', weight: 5, opacity: 0.9}}).addTo(ly.sel);  // הדגשה בכחול
            var m = _afMask(i), who = [];  // מי רואה
            if (m && _af.vis) {{ var bits = 0; m.forEach(function(x) {{ bits |= x; }}); (_af.vis.radars || []).forEach(function(rd, b) {{ if (bits & (1 << b)) who.push(rd.name); }}); }}  // איחוד הביטים
            _af.els.selInfo.innerHTML = '';  // ניקוי
            _afMk(_af.els.selInfo, 'div', '🔵 ' + r.areas.launch[row.la] + ' #' + (row.lp + 1) + ' → ' + r.areas.target[row.ta] + ' #' + (row.tp + 1) + ' · ענף ' + (row.group === 'low' ? 'נמוך' : 'גבוה') + String.fromCharCode(10) +
                'טווח ' + Math.round(row.range_m).toLocaleString() + ' מ\\' · הגבהה ' + row.qe.mils + ' מיל · אזימוט ירי ' + row.fire_azimuth.mils + ' מיל · מעוף ' + row.tof_s + ' ש\\' · קודקוד ' + Math.round(row.apex_msl_m) + ' מ\\'' + String.fromCharCode(10) +
                (m ? 'נצפה ע"י: ' + (who.length ? who.join(', ') : 'אף מכ"ם') : 'הצביעה עוד לא חושבה'));  // הפרטים
            _afBtn(_af.els.selInfo, '🔍 פתח במסלול בודד (חישוב מדויק + מעקב מכ"ם)', 'מציב את התותח והמטרה של המסלול הזה בכלי הבודד, לחישוב מדויק ובדיקת מעקב מכ"ם מלאה', function() {{  // מעבר לכלי הבודד
                _afSetMode(false);  // מצב בודד
                ballisticsEditing = 'gun'; _placeBallisticsPoint(L.latLng(row.launch[0], row.launch[1]));  // תותח (הגובה נשלף מחדש — T21)
                ballisticsEditing = 'target'; _placeBallisticsPoint(L.latLng(row.target[0], row.target[1]));  // מטרה
                _ballisticsSelectTab('solve');  // טאב פתרון ירי
            }}, 'margin-top:2px;');  // סוף הכפתור
        }}
        function _afDrawHeat() {{  // מפות חום: תא לכל נקודה, צבע לפי מספר המסלולים (סולם רציף, גוון אחד)
            var r = _af.result, ly = _afLayers(); ly.heatL.clearLayers(); ly.heatT.clearLayers();  // ניקוי
            [['launch', ly.heatL, r.resolution_m.launch, [222, 235, 247], [8, 81, 156], 'מסלולים מנקודת השיגור'], ['target', ly.heatT, r.resolution_m.target, [242, 240, 247], [84, 39, 143], 'מסלולים אל נקודת המטרה']].forEach(function(x) {{  // שיגור בכחול, מטרה בסגול
                var pts = r.heat[x[0]], mx = Math.max(1, Math.max.apply(null, pts.map(function(p) {{ return p.count; }})));  // המרבי
                pts.forEach(function(p) {{  // כל נקודה
                    var t = p.count / mx, c = x[3].map(function(a, j) {{ return Math.round(a + t * (x[4][j] - a)); }});  // צבע בסולם
                    var dLat = x[2] / 2 / 111320, dLon = dLat / Math.cos(p.lat * Math.PI / 180);  // חצי תא
                    L.rectangle([[p.lat - dLat, p.lon - dLon], [p.lat + dLat, p.lon + dLon]], {{renderer: _afRenderer, weight: 0, fillColor: 'rgb(' + c.join(',') + ')', fillOpacity: p.count ? 0.7 : 0.25}}).bindTooltip(p.count + ' ' + x[5]).addTo(x[1]);  // תא + ריחוף עם המספר
                }});
            }});
        }}
        function _afApplyLayerToggles() {{  // הצגת/הסתרת השכבות לפי המתגים
            if (!_af.els.showPaths || !_af.mode) return;  // לא במצב
            var ly = _afLayers();  // השכבות
            if (_af.els.showHeatL.checked) ly.heatL.addTo(map); else map.removeLayer(ly.heatL);  // חום שיגור
            if (_af.els.showHeatT.checked) ly.heatT.addTo(map); else map.removeLayer(ly.heatT);  // חום מטרה
            _afRender();  // מסלולים
        }}
        function _afRecolor() {{  // "עדכן צביעה" — נראות מול כל המכ"מים המוצבים
            if (!_af.resultJob) return;  // אין תוצאה בשרת
            _af.visSigPending = _afSites();  // המכ"מים ברגע הבקשה
            _af.els.stale.textContent = '';  // מנקים הודעה
            fetch('http://localhost:5002/ballistics/area/visibility', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{job_id: _af.resultJob}})}})
            .then(function(rsp) {{ return rsp.json(); }}).then(function(d) {{
                if (d.error || !d.job_id) {{ _af.els.stale.textContent = '⚠️ ' + (d.error || 'שגיאה'); return; }}  // שגיאה
                _af.visJob = d.job_id;  // ה-job
                if (_af.visTimer) clearInterval(_af.visTimer);  // קודם
                _af.visTimer = setInterval(function() {{ _afPoll(d.job_id, true); }}, 1000);  // polling
            }}).catch(function(e) {{ _af.els.stale.textContent = '⚠️ ' + e.message; }});  // כשל
        }}
        function _afCheckStale() {{  // האם המכ"מים השתנו מאז הצביעה (החלטה 16: הודעה + כפתור, בלי עדכון אוטומטי)
            if (!_af.result || !_af.els.stale) return;  // אין תוצאה
            var changed = _af.visSig !== null && _af.visSig !== _afSites();  // השוואה
            _af.els.stale.textContent = changed ? '⚠️ המכ"מים המוצבים השתנו — הצביעה ישנה. לחץ "עדכן צביעה".' : '';  // הודעה
        }}
        setInterval(function() {{ if (_af.mode && _af.result) _afCheckStale(); }}, 3000);  // בדיקה תקופתית קלה (השוואת מחרוזת)
        function _afCsv() {{  // ייצוא CSV (דרך fetch כדי שטוקן ההפעלה יישלח)
            if (!_af.resultJob) return;  // אין תוצאה
            fetch('http://localhost:5002/ballistics/area/csv?job_id=' + _af.resultJob + (_af.visJob && _af.vis ? '&vis_job=' + _af.visJob : ''))  // הבקשה
            .then(function(r) {{ return r.blob(); }}).then(function(blob) {{
                var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'area_fire.csv';  // קישור הורדה
                document.body.appendChild(a); a.click(); setTimeout(function() {{ URL.revokeObjectURL(a.href); a.remove(); }}, 1000);  // הורדה וניקוי
            }}).catch(function(e) {{ _af.els.info.textContent = '⚠️ ייצוא נכשל: ' + e.message; }});  // כשל
        }}

        function _ballisticsBuildTrajTab(body) {{
            var top = L.DomUtil.create('div', '', body);
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            var azInput   = _ballisticsMkField('אזימוט ירי', 600, 1, 0, 6400, '', top, null);
            var taltInput = _ballisticsMkField('גובה פגיעה [מ\\'] (ריק=גובה התותח)', '', 1, null, null, '', top, null);

            // ---- הגבהה: שדה-מספר + סליידר מסונכרנים + כפתורי-צעד ±1/±10 מיל (לפי בקשת שלב 3) ----
            var qeRow = L.DomUtil.create('div', '', top);
            qeRow.style.cssText = 'display:flex;align-items:center;gap:3px;';
            var qeLabel = L.DomUtil.create('span', '', qeRow); qeLabel.textContent = 'הגבהה'; qeLabel.style.cssText = 'font-size:9px;color:#666;';
            var qeNum = L.DomUtil.create('input', '', qeRow);
            qeNum.type = 'number'; qeNum.value = 450; qeNum.style.cssText = 'width:52px;font-size:11px;padding:1px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;';
            var qeSlider = L.DomUtil.create('input', '', top);
            qeSlider.type = 'range'; qeSlider.min = 5; qeSlider.max = 1350; qeSlider.step = 1; qeSlider.value = 450;
            qeSlider.style.cssText = 'width:100%;';
            var qeStepRow = L.DomUtil.create('div', '', top);
            qeStepRow.style.cssText = 'display:flex;gap:2px;';
            [['-10', -10], ['-1', -1], ['+1', 1], ['+10', 10]].forEach(function(s) {{
                var b = L.DomUtil.create('button', '', qeStepRow);
                b.textContent = s[0]; b.style.cssText = 'flex:1;font-size:9px;padding:1px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
                L.DomEvent.on(b, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    var v = (parseFloat(qeNum.value) || 0) + s[1];
                    qeNum.value = v; qeSlider.value = Math.max(5, Math.min(1350, v));
                }});
            }});
            L.DomEvent.on(qeNum, 'input', function() {{ qeSlider.value = Math.max(5, Math.min(1350, parseFloat(qeNum.value) || 0)); }});
            L.DomEvent.on(qeSlider, 'input', function() {{ qeNum.value = qeSlider.value; }});

            var runBtn = L.DomUtil.create('button', '', top);
            runBtn.textContent = 'חשב מסלול'; runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
            var crestBtn = L.DomUtil.create('button', '', top);
            crestBtn.textContent = 'הגבהה מינימלית לכיסוי שטח'; crestBtn.title = 'דורש תותח+מטרה מוצבים — מחשב ומציב כ-qe_min בטאב פתרון-ירי';
            crestBtn.style.cssText = 'font-size:10px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#cba6f7;cursor:pointer;';

            var info = L.DomUtil.create('div', '', top);
            info.style.cssText = 'font-size:9.5px;color:#333;white-space:pre-wrap;direction:rtl;text-align:right;max-height:140px;overflow-y:auto;';
            var canvas = document.createElement('canvas');
            // נמצא בבדיקה חיה אמיתית (לא בבדיקה אוטומטית): "הגרף נחתך" — הסיבה האמיתית הייתה
            // ש-width:100% על canvas בתוך עמודת-flex (top) בלי רוחב-מוחלט לאף אב בשרשרת (panelBody/
            // tabsHolder/body גם הם ללא width מפורש, רק max-width על ה-container החיצוני) מתכנס
            // ל-0 בפועל — canvas הוא replaced-element, ו-% על replaced-element בלי רוחב-אב-מוחלט
            // לא מתפתר כמו ב-div רגיל. אומת ישירות: getBoundingClientRect() החזיר {{w:0,h:0}} ממש.
            // תוקן ברוחב-פיקסלים מוחלט (לא %) — עוקף את כל הבעיה, לא רק מטפל בתזמון
            canvas.style.cssText = 'width:250px;height:90px;display:block;margin-top:3px;';
            canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'גרף המסלול הבליסטי: גובה לפי טווח (הערכים המדויקים בטקסט מתחת)');  // T12 (F-041): שם נגיש לגרף
            top.appendChild(canvas);

            function _runTraj() {{
                if (!ballisticsGun) {{ alert('הצב תותח על המפה קודם'); return; }}
                var altMsg = _ballisticsAltGuard(false);  // T21 (F-053): מסלול ישיר — צריך רק את גובה התותח
                if (altMsg) {{ alert(altMsg); return; }}  // T21: לפני ballisticsLoading, כדי לא להיתקע במצב "טוען"
                if (ballisticsLoading) return;
                ballisticsLoading = true; info.textContent = 'מחשב...';
                var common = _ballisticsGetCommonParams();
                var gt = _ballisticsGetGunTarget();
                fetch('http://localhost:5002/ballistics/trajectory', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(Object.assign({{}}, common, {{
                        gun: gt.gun, qe: parseFloat(qeNum.value), azimuth: parseFloat(azInput.value),
                        target_alt: taltInput.value === '' ? null : parseFloat(taltInput.value),
                        include_path: true, path_step: 5,
                    }})),
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    ballisticsLoading = false;
                    if (_ballisticsMetStatusEl && d.met_used) {{
                        var metTxt = 'מטאו: ' + (d.met_used.description || d.met_used.source || '');
                        _ballisticsMetStatusEl.textContent = metTxt;
                        if (_ballisticsMetTabStatusEl) _ballisticsMetTabStatusEl.textContent = metTxt;  // גם בטאב "מטאו" עצמו
                    }}
                    if (!d.ok) {{ info.textContent = d.message || d.error || 'שגיאה'; return; }}
                    var lines = ['הגבהה ' + _ballisticsFmtAngle(d.qe) + ' | אזימוט ' + _ballisticsFmtAngle(d.fire_azimuth)];
                    lines = lines.concat(_ballisticsImpactLines(d.impact));
                    (d.warnings || []).forEach(function(w) {{ lines.push('⚠ ' + w); }});
                    info.textContent = lines.join('\\n');
                    _ballisticsDrawPath(d.path, d.impact);
                    if (d.path) {{
                        _ballisticsRunTerrainCheck(d.path, info, function(tc) {{
                            _drawBallisticsProfile(canvas, d.path, tc ? tc.profile : null);
                            if (tc && !tc.clear) info.textContent += '\\n\\n⚠ המסלול חוסם ע"י השטח (מרווח מינימלי ' + tc.min_margin_m + ' מ\\')';
                        }});
                    }}
                }})
                .catch(function(e) {{ ballisticsLoading = false; info.textContent = 'שגיאת רשת: ' + e.message; }});
            }}
            L.DomEvent.on(runBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _runTraj(); }});

            L.DomEvent.on(crestBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                if (!ballisticsGun || !ballisticsTarget) {{ alert('הצב תותח ומטרה קודם'); return; }}
                var altMsg = _ballisticsAltGuard(true);  // T21 (F-053): הגבהה מינימלית מעל רכס — צריך גובה תותח ומטרה
                if (altMsg) {{ alert(altMsg); return; }}  // T21: חסימה עם הסבר
                var common = _ballisticsGetCommonParams();
                var gt = _ballisticsGetGunTarget();
                info.textContent = 'מחשב הגבהה-מינימלית...';
                fetch('http://localhost:5002/ballistics/min_qe_for_crest', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(Object.assign({{}}, common, {{gun: gt.gun, target: gt.target}})),
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    if (!d.ok) {{ info.textContent = d.error || 'לא נמצאה הגבהה מתאימה'; return; }}
                    if (_ballisticsSolveSetQeMin) _ballisticsSolveSetQeMin(d.qe_min);
                    info.textContent = 'הגבהה מינימלית לכיסוי שטח: ' + _ballisticsFmtAngle(d.qe_min) + ' — הוצבה כ-qe_min בטאב "פתרון ירי"';
                }})
                .catch(function(e) {{ info.textContent = 'שגיאת רשת: ' + e.message; }});
            }});
        }}

        function _ballisticsBuildRadarTab(body) {{
            // טאב "🎯 מעקב מכ"ם" (כלי שביעי, SRS FR-D-259..): בורר מקור המסלול (שלב א4), הגדרות סריקה ומעקב,
            // הפעלה ותוצאות. הממשק של שלבים א1-א3 הועבר לכאן מטאב "מסלול בודד", כי חלק מהמקורות אינם בליסטיים
            var top = L.DomUtil.create('div', '', body);  // עמודת התוכן
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';  // כמו שאר הטאבים
            var note = L.DomUtil.create('div', '', top);  // הסבר קצר
            note.style.cssText = 'font-size:8.5px;color:#888;';  // טקסט משני
            note.textContent = 'הפרמטרים של המכ"ם נלקחים מכלי "תצפית מכ"ם דופלר" (🎯) או מהפרופיל הפעיל. פרופילי הספרייה מבוססים על נתונים פומביים בלבד — רעיוניים/חינוכיים, לא מפרט אמיתי.';  // הבהרה (FR-D-286)
            _rtBuildActiveBar(top);  // FR-D-286: אותו בורר "פרופיל פעיל" כמו בפאנל המכ"ם, מסונכרן איתו
            var radarRow = L.DomUtil.create('div', '', top);  // תיקון תקלה: הצבת מכ"ם מכאן, בלי לסגור את הכלי הבליסטי
            radarRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';  // פריסה
            var radarPickBtn = L.DomUtil.create('button', '', radarRow);  // הכפתור
            radarPickBtn.textContent = '📍 הצב/הזז מכ"ם במפה';  // תווית
            radarPickBtn.title = 'הלחיצה הבאה על המפה מציבה את המכ"ם. לשינוי הפרמטרים שלו — כלי 🎯 (פתיחתו סוגרת את הפאנל הזה)';  // הסבר
            radarPickBtn.style.cssText = 'font-size:9px;padding:1px 4px;border-radius:3px;border:1px solid #2ecc40;background:#eafbee;cursor:pointer;';  // בצבע כלי המכ"ם
            var radarPosLbl = L.DomUtil.create('span', '', radarRow);  // מיקום המכ"ם
            radarPosLbl.textContent = radarObs ? radarObs.lat.toFixed(4) + ', ' + radarObs.lng.toFixed(4) : 'לא הוצב';  // מצב התחלתי
            L.DomEvent.on(radarPickBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtPickRadar(radarPosLbl); }});  // בחירה
            _rtSrc.sel = _ballisticsMkSelect('מקור המסלול', [['מסלול בליסטי אחרון', 'ballistic'], ['רקטה (מודל דחיפה)', 'rocket'], ['טיסה מ-FR24 שנטענה', 'fr24'],
                ['מסלול מצויר', 'custom'], ['שיוט במעגל', 'loiter'], ['קובץ CSV', 'csv']], 0,
                'בליסטי: המסלול האחרון מטאב "מסלול בודד" או "פתרון ירי". מצויר: מהכלי "מסלול טיסה מותאם"', top);  // בורר המקור (החלטות 3-4)
            _rtSrc.altRef = _ballisticsMkSelect('גובה המסלול', [['מעל פני הים', 'msl'], ['מעל הקרקע', 'agl']], 1,
                'למסלול מצויר, לשיוט ול-CSV. "מעל הקרקע" מוסיף לכל קודקוד את גובה הקרקע שלו (עד 600 קודקודים)', top);  // ייחוס הגובה
            // ---- מסלול מצויר ----
            _rtSrc.customSpeed = _ballisticsMkField('מהירות [קשר]', 90, 1, 1, 2000, 'מהירות קבועה לאורך כל המסלול המצויר', top, null);  // מהירות
            _rtSrc.customAlt = _ballisticsMkField('גובה לנקודות בלי גובה [מ\\']', 300, 10, -400, 20000, 'נקודה שלא הוזן לה גובה בכלי המסלול מקבלת את הגובה הזה', top, null);  // גובה ברירת מחדל
            // ---- רקטה (שלב א6) — המשגר הוא התותח שהוצב בכלי הבליסטי, והמטאו לפי הבחירה בפאנל ----
            var rkNote = L.DomUtil.create('div', '', top);  // הסבר
            rkNote.style.cssText = 'font-size:8.5px;color:#888;';  // טקסט משני
            rkNote.textContent = 'המשגר = התותח שהוצב (✏️ תותח). דחף קבוע ואחריו מעוף בליסטי — מודל רעיוני, לא מערכת אמיתית.';  // הבהרה
            _rtSrc.rkElev = _ballisticsMkField('זווית שיגור [°]', 45, 1, 5, 89, 'זווית ההגבהה של המשגר', top, null);  // הגבהה
            _rtSrc.rkAz = _ballisticsMkField('אזימוט [°]', 0, 1, 0, 360, 'כיוון השיגור (0 = צפון)', top, null);  // כיוון
            _rtSrc.rkMass = _ballisticsMkField('מסה בשיגור [ק"ג]', 40, 1, 1, 100000, 'כולל הדלק', top, null);  // מסה
            _rtSrc.rkProp = _ballisticsMkField('מסת דלק [ק"ג]', 12, 0.5, 0.1, 100000, 'נשרפת באופן אחיד לאורך זמן הבעירה', top, null);  // דלק
            _rtSrc.rkBurn = _ballisticsMkField('זמן בעירה [שנ\\']', 2, 0.1, 0.05, 600, 'כמה זמן המנוע דוחף', top, null);  // בעירה
            _rtSrc.rkThrust = _ballisticsMkField('דחף [N]', 12000, 100, 1, 1e8, 'דחף קבוע בזמן הבעירה', top, null);  // דחף
            _rtSrc.rkDiam = _ballisticsMkField('קוטר [מ\\']', 0.15, 0.01, 0.01, 5, 'לחישוב שטח החתך בגרר', top, null);  // קוטר
            _rtSrc.rkCd = _ballisticsMkField('מקדם גרר Cd', 0.4, 0.05, 0, 3, 'קבוע לאורך כל המעוף (פישוט)', top, null);  // Cd
            // ---- שיוט במעגל ----
            var loiterRow = L.DomUtil.create('div', '', top);  // שורת המרכז
            loiterRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';  // פריסה
            var loiterBtn = L.DomUtil.create('button', '', loiterRow);  // כפתור בחירת מרכז
            loiterBtn.textContent = '📍 בחר מרכז על המפה';  // תווית
            loiterBtn.style.cssText = 'font-size:9px;padding:1px 4px;border-radius:3px;border:1px solid #14b8a6;background:#e6fffb;cursor:pointer;';  // עיצוב
            var loiterLbl = L.DomUtil.create('span', '', loiterRow); loiterLbl.textContent = 'לא נבחר';  // המרכז שנבחר
            L.DomEvent.on(loiterBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtPickLoiterCenter(loiterLbl); }});  // בחירה
            _rtSrc.loiterRadius = _ballisticsMkField('רדיוס [מ\\']', 1500, 50, 50, 100000, 'רדיוס מעגל השיוט', top, _rtDrawLoiterPreview);  // רדיוס (מעדכן את התצוגה המקדימה)
            _rtSrc.loiterAlt = _ballisticsMkField('גובה [מ\\']', 300, 10, -400, 20000, 'גובה השיוט', top, null);  // גובה
            _rtSrc.loiterSpeed = _ballisticsMkField('מהירות [קשר]', 60, 1, 1, 2000, 'מהירות לאורך המעגל', top, null);  // מהירות
            _rtSrc.loiterLaps = _ballisticsMkField('מספר סיבובים', 2, 1, 1, 50, 'כמה פעמים להקיף את המרכז', top, null);  // סיבובים
            _rtSrc.loiterDir = _ballisticsMkSelect('כיוון', [['עם כיוון השעון', 'cw'], ['נגד כיוון השעון', 'ccw']], 0, '', top);  // כיוון
            // ---- קובץ CSV ----
            var csvRow = L.DomUtil.create('div', '', top);  // שורת הקובץ
            csvRow.style.cssText = 'display:flex;flex-direction:column;gap:2px;font-size:9px;color:#666;';  // פריסה
            var csvInput = L.DomUtil.create('input', '', csvRow); csvInput.type = 'file'; csvInput.accept = '.csv,.txt';  // בחירת קובץ
            csvInput.style.cssText = 'font-size:9px;max-width:240px;';  // עיצוב
            var csvLbl = L.DomUtil.create('span', '', csvRow);  // מצב הטעינה
            csvLbl.textContent = 'עמודות: t [שנ\\'], lat, lon, alt [מ\\'] — עם שורת כותרת או בסדר הזה';  // הוראה
            L.DomEvent.on(csvInput, 'change', function() {{  // קובץ נבחר
                var f = csvInput.files && csvInput.files[0]; if (!f) return;  // אין קובץ
                var rd = new FileReader();  // קורא מקומי — הקובץ לא נשלח לשום מקום חוץ מהשרת המקומי
                rd.onload = function() {{  // נקרא
                    var pts = _rtParseCsv(String(rd.result));  // פענוח
                    _rtSrc.csvPoints = pts && pts.length >= 2 ? pts : null;  // רק מסלול תקין
                    csvLbl.textContent = pts === null ? 'חסרה עמודה (t, lat, lon, alt) בשורת הכותרת' :
                        (pts.length >= 2 ? 'נטענו ' + pts.length + ' נקודות ✔' : 'לא נמצאו מספיק נקודות תקינות');  // תוצאה
                }};
                rd.readAsText(f);  // קריאה כטקסט
            }});
            // ---- FR24 ----
            var frRow = L.DomUtil.create('label', '', top);  // שורת ה-RCS האוטומטי
            frRow.style.cssText = 'display:flex;align-items:center;gap:3px;font-size:9px;color:#666;cursor:pointer;';  // תיבה + טקסט
            _rtSrc.frRcs = L.DomUtil.create('input', '', frRow); _rtSrc.frRcs.type = 'checkbox'; _rtSrc.frRcs.checked = true;  // מופעל כברירת מחדל
            L.DomUtil.create('span', '', frRow).textContent = 'RCS לפי סוג המטוס (במקום השדה בכלי הדופלר)';  // הסבר
            function _rtRefreshSource() {{  // מציג רק את השדות של המקור שנבחר
                var s = _rtSrc.sel.value;  // המקור
                function show(el, on) {{ (el.tagName === 'INPUT' || el.tagName === 'SELECT' ? el.parentElement : el).style.display = on ? 'flex' : 'none'; }}  // שורה שלמה
                show(_rtSrc.altRef, s === 'custom' || s === 'loiter' || s === 'csv');  // ייחוס גובה
                show(_rtSrc.customSpeed, s === 'custom'); show(_rtSrc.customAlt, s === 'custom');  // מסלול מצויר
                rkNote.style.display = s === 'rocket' ? 'block' : 'none';  // הסבר הרקטה
                [_rtSrc.rkElev, _rtSrc.rkAz, _rtSrc.rkMass, _rtSrc.rkProp, _rtSrc.rkBurn, _rtSrc.rkThrust, _rtSrc.rkDiam, _rtSrc.rkCd]
                    .forEach(function(el) {{ show(el, s === 'rocket'); }});  // שדות הרקטה
                [loiterRow].forEach(function(el) {{ el.style.display = s === 'loiter' ? 'flex' : 'none'; }});  // שורת המרכז
                [_rtSrc.loiterRadius, _rtSrc.loiterAlt, _rtSrc.loiterSpeed, _rtSrc.loiterLaps, _rtSrc.loiterDir].forEach(function(el) {{ show(el, s === 'loiter'); }});  // שדות השיוט
                csvRow.style.display = s === 'csv' ? 'flex' : 'none';  // קובץ
                frRow.style.display = s === 'fr24' ? 'flex' : 'none';  // FR24
                if (s !== 'loiter' && _rtSrc.loiterLayer) {{ map.removeLayer(_rtSrc.loiterLayer); _rtSrc.loiterLayer = null; }}  // התצוגה המקדימה רק בשיוט
                if (s === 'loiter') _rtDrawLoiterPreview();  // חזרה לשיוט — מציגים שוב
            }}
            L.DomEvent.on(_rtSrc.sel, 'change', _rtRefreshSource);  // שינוי מקור
            _rtRefreshSource();  // מצב התחלתי
            // כפתור בדיקת מעקב מכ"ם (כלי שביעי, שלב א1) — בודק את המסלול האחרון שחושב מול המכ"ם של כלי 🎯
            var rtBtn = L.DomUtil.create('button', '', top);  // הכפתור
            rtBtn.textContent = '🎯 בדוק מעקב מכ"ם';  // תווית
            rtBtn.title = 'משתמש במכ"ם ובפרמטרים מכלי "תצפית מכ"ם דופלר" (🎯) ובמקור המסלול שנבחר למעלה';  // הסבר בריחוף
            rtBtn.style.cssText = 'font-size:10px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#94e2d5;cursor:pointer;';  // עיצוב כמו שאר הכפתורים
            var rtCmpBtn = L.DomUtil.create('button', '', top);  // T30: השוואת כל המכ"מים המוצבים
            rtCmpBtn.textContent = '📊 השווה את כל המכ"מים המוצבים';  // תווית
            rtCmpBtn.title = 'בודק את המסלול מול כל מכ"ם ברשימה (עם הפרמטרים שלו) ומציג טבלה: מי רואה את הפגז, מתי, ומאיזה מרחק';  // הסבר
            rtCmpBtn.style.cssText = 'font-size:10px;padding:3px;min-height:24px;border-radius:3px;border:1px solid #ccc;background:#e8f5e9;cursor:pointer;';  // עיצוב
            L.DomEvent.on(rtCmpBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtCompareAll(); }});  // לחיצה
            _rtCmp.el = L.DomUtil.create('div', '', top);  // T30: אזור התוצאה
            _rtCmp.el.style.cssText = 'font-size:9.5px;color:#222;max-height:200px;overflow:auto;';  // עיצוב
            _rtCmp.el.setAttribute('role', 'status');  // קוראי מסך
            // ---- הגדרות סריקה ומעקב (שלב א2) — מקופלות כברירת מחדל, כדי לא להעמיס על הטאב ----
            var rtCfg = L.DomUtil.create('details', '', top);  // אזור מתקפל
            rtCfg.style.cssText = 'font-size:9px;border:1px solid #ddd;border-radius:3px;padding:2px 4px;';  // מסגרת עדינה
            var rtCfgSum = L.DomUtil.create('summary', '', rtCfg);  // כותרת האזור
            rtCfgSum.textContent = '⚙ הגדרות סריקה ומעקב';  // הטקסט
            rtCfgSum.style.cssText = 'cursor:pointer;color:#555;';  // סמן לחיצה
            _rtScanInputs.track_mode = _ballisticsMkSelect('מצב בדיקה', [['מעקב (סריקה + M מתוך N)', 'track'], ['גילוי לכל נקודה', 'detection']], 0,
                'מעקב: המכ"ם רואה רק כשהאלומה עוברת על המטרה, ומעקב נפתח אחרי M גילויים מתוך N. גילוי: כל נקודה נבדקת בנפרד', rtCfg);  // מתג המצב (החלטה 1)
            _rtScanInputs.scan_mode = _ballisticsMkSelect('סוג סריקה', [['אנטנה מסתובבת', 'rotating'], ['מערך-מופע (סקטור)', 'phased'], ['מכ"ם מעקב ייעודי', 'tracker']], 0,
                'הסקטור של מערך-מופע נלקח מכלי הדופלר (כיוון פנים וזווית סריקה מרבית)', rtCfg);  // שלושת מצבי הסריקה (החלטה 7)
            _rtScanInputs.rot_period_s = _ballisticsMkField('זמן סיבוב [שנ\\']', 4, 0.1, 0.2, 60, 'כמה שניות לוקח לאנטנה סיבוב מלא', rtCfg, null);  // אנטנה מסתובבת
            _rtScanInputs.scan_phase_deg = _ballisticsMkField('כיוון אלומה בהתחלה [°]', 0, 1, 0, 360, 'לאן מכוונת האלומה ברגע הירי (0 = צפון). משפיע על זמן הגילוי', rtCfg, null);  // פאזה
            _rtScanInputs.revisit_s = _ballisticsMkField('זמן ביקור [שנ\\']', 0.5, 0.05, 0.02, 30, 'כל כמה שניות מערך-המופע חוזר לכל כיוון בסקטור', rtCfg, null);  // מערך-מופע
            _rtScanInputs.track_rate_hz = _ballisticsMkField('קצב עדכון מעקב [Hz]', 10, 1, 0.5, 100, 'כמה עדכונים בשנייה אחרי שהמכ"ם ננעל', rtCfg, null);  // מעקב ייעודי
            _rtScanInputs.max_ang_rate_dps = _ballisticsMkField('קצב סיבוב מרבי [°/שנ\\']', 30, 1, 0.1, 360, 'מטרה שזזה זוויתית מהר מזה "בורחת" מהאלומה', rtCfg, null);  // מעקב ייעודי
            _rtScanInputs.cue_delay_s = _ballisticsMkField('השהיית הכוונה [שנ\\']', 1, 0.1, 0, 30, 'הזמן מגילוי המטרה ועד שמכ"ם המעקב מתחיל לעקוב', rtCfg, null);  // מעקב ייעודי
            _rtScanInputs.track_m = _ballisticsMkField('M — גילויים לפתיחה', 2, 1, 1, 10, 'כמה גילויים נדרשים כדי לפתוח מעקב', rtCfg, null);  // M
            _rtScanInputs.track_n = _ballisticsMkField('N — מתוך הזדמנויות', 3, 1, 1, 10, 'בתוך כמה הזדמנויות אחרונות צריכים להיות M הגילויים', rtCfg, null);  // N
            _rtScanInputs.coast_s = _ballisticsMkField('זמן דעיכה [שנ\\']', 8, 0.5, 0.1, 120, 'כמה שניות בלי גילוי המעקב שורד לפני שהוא נשבר', rtCfg, null);  // coast
            function _rtRefreshScanFields() {{  // מציג רק את השדות שרלוונטיים לסוג הסריקה ולמצב
                var mode = _rtScanInputs.scan_mode.value, isTrack = _rtScanInputs.track_mode.value === 'track';  // הבחירות
                var show = {{  // שדה -> האם להציג
                    scan_mode: isTrack, rot_period_s: isTrack && mode === 'rotating', scan_phase_deg: isTrack && mode === 'rotating',
                    revisit_s: isTrack && mode === 'phased', track_rate_hz: isTrack && mode === 'tracker',
                    max_ang_rate_dps: isTrack && mode === 'tracker', cue_delay_s: isTrack && mode === 'tracker',
                    track_m: isTrack, track_n: isTrack, coast_s: isTrack
                }};
                Object.keys(show).forEach(function(k) {{ _rtScanInputs[k].parentElement.style.display = show[k] ? 'flex' : 'none'; }});  // הסתרה/הצגה של השורה כולה
            }}
            L.DomEvent.on(_rtScanInputs.scan_mode, 'change', _rtRefreshScanFields);  // שינוי סוג סריקה
            L.DomEvent.on(_rtScanInputs.track_mode, 'change', _rtRefreshScanFields);  // שינוי מצב
            _rtRefreshScanFields();  // מצב התחלתי
            // ---- שלב א5: RCS לפי זווית וגשם ----
            var rtEnv = L.DomUtil.create('details', '', top);  // אזור מתקפל
            rtEnv.style.cssText = 'font-size:9px;border:1px solid #ddd;border-radius:3px;padding:2px 4px;';  // מסגרת עדינה
            var rtEnvSum = L.DomUtil.create('summary', '', rtEnv); rtEnvSum.textContent = '⚙ RCS וגשם';  // כותרת
            rtEnvSum.style.cssText = 'cursor:pointer;color:#555;';  // סמן לחיצה
            _rtEnvInputs.rcs_mode = _ballisticsMkSelect('RCS', [['קבוע (השדה בכלי הדופלר)', 'fixed'], ['לפי זווית הסתכלות', 'aspect']], 0,
                'לפי זווית: RCS שונה כשרואים את המטרה מהחרטום, מהצד או מהזנב — מעבר הדרגתי ביניהם', rtEnv);  // החלטה 5
            var rcsPreset = _ballisticsMkSelect('מילוי מהיר (משוער)', [['—', ''], ['פגז', '0.005,0.02,0.01'], ['רקטה', '0.02,0.3,0.05'],
                ['רחפן קטן', '0.01,0.03,0.01'], ['מטוס קל', '0.5,3,1']], 0, 'ערכים משוערים לצורך המחשה בלבד — לא נתוני מערכת אמיתית', rtEnv);  // נוחות בלבד
            _rtEnvInputs.rcs_nose = _ballisticsMkField('חרטום [מ"ר]', 0.01, 0.001, 0.0001, 10000, 'RCS כשהמטרה מתקרבת ישר אל המכ"ם', rtEnv, null);  // 0°
            _rtEnvInputs.rcs_side = _ballisticsMkField('צד [מ"ר]', 0.05, 0.001, 0.0001, 10000, 'RCS כשהמטרה חוצה בניצב', rtEnv, null);  // 90°
            _rtEnvInputs.rcs_tail = _ballisticsMkField('זנב [מ"ר]', 0.02, 0.001, 0.0001, 10000, 'RCS כשהמטרה מתרחקת מהמכ"ם', rtEnv, null);  // 180°
            L.DomEvent.on(rcsPreset, 'change', function() {{  // מילוי שלושת השדות
                if (!rcsPreset.value) return;  // "—"
                var v = rcsPreset.value.split(',');  // חרטום,צד,זנב
                _rtEnvInputs.rcs_nose.value = v[0]; _rtEnvInputs.rcs_side.value = v[1]; _rtEnvInputs.rcs_tail.value = v[2];  // מילוי
            }});
            var rainPreset = _ballisticsMkSelect('גשם — מילוי מהיר', [['יבש', '0'], ['קל (2.5)', '2.5'], ['בינוני (10)', '10'], ['כבד (25)', '25'], ['סוער (50)', '50']], 0, '', rtEnv);  // נוחות
            _rtEnvInputs.rain_rate_mmh = _ballisticsMkField('עוצמת גשם [מ"מ/שעה]', 0, 0.5, 0, 200, '0 = יבש. ההשפעה משמעותית בעיקר בתדרים גבוהים (פס X ומעלה)', rtEnv, null);  // החלטה 10
            L.DomEvent.on(rainPreset, 'change', function() {{ _rtEnvInputs.rain_rate_mmh.value = rainPreset.value; }});  // מילוי
            _rtEnvInputs.rain_top_m = _ballisticsMkField('תקרת הגשם [מ\\']', 3000, 100, 100, 10000, 'הגשם מניחים אחיד מהקרקע ועד הגובה הזה', rtEnv, null);  // גובה
            _rtEnvInputs.polarization = _ballisticsMkSelect('קיטוב', [['אופקי', 'h'], ['אנכי', 'v'], ['מעגלי', 'c']], 0, 'הקיטוב משנה את הנחתת הגשם (ITU-R P.838-3)', rtEnv);  // τ
            var ituNote = L.DomUtil.create('div', '', rtEnv);  // ציון מקור — חובה לפי החלטת הבעלים D8
            ituNote.style.cssText = 'font-size:8px;color:#888;direction:ltr;text-align:left;';  // טקסט משני
            ituNote.textContent = 'Rain attenuation model: Recommendation ITU-R P.838-3 (ITU)';  // הייחוס
            function _rtRefreshEnv() {{  // שדות ה-RCS לפי זווית רק כשהמצב הזה נבחר
                var on = _rtEnvInputs.rcs_mode.value === 'aspect';  // המצב
                [rcsPreset, _rtEnvInputs.rcs_nose, _rtEnvInputs.rcs_side, _rtEnvInputs.rcs_tail].forEach(function(el) {{ el.parentElement.style.display = on ? 'flex' : 'none'; }});  // הצגה/הסתרה
            }}
            L.DomEvent.on(_rtEnvInputs.rcs_mode, 'change', _rtRefreshEnv); _rtRefreshEnv();  // מאזין + מצב התחלתי
            // ---- שלב א5: פרופילי מכ"ם — שמירה/טעינה (רכיב "עמדות שמורות" הקיים) וייבוא/ייצוא JSON ----
            var rtProf = L.DomUtil.create('details', '', top);  // אזור מתקפל
            rtProf.style.cssText = 'font-size:9px;border:1px solid #ddd;border-radius:3px;padding:2px 4px;';  // מסגרת
            var rtProfSum = L.DomUtil.create('summary', '', rtProf); rtProfSum.textContent = '💾 פרופילי מכ"ם';  // כותרת
            rtProfSum.style.cssText = 'cursor:pointer;color:#555;';  // סמן לחיצה
            _rtProfileFields = _rtBuildProfileFieldMap();  // כל השדות שנכנסים לפרופיל
            _rtHookActiveFields();  // FR-D-286: גם שדות הסריקה וה-RCS מסמנים "שונה ידנית" בבורר
            _buildStationUI(rtProf, 'radar_profile', _rtProfileFields, null, null,
                function() {{ if (radarObs) _updateRadarDopplerPreview(); }}, 'פרופילים שמורים (פרמטרי מכ"ם + סריקה + RCS):');  // שמירה/טעינה/מחיקה
            var jsonRow = L.DomUtil.create('div', '', rtProf);  // ייבוא/ייצוא
            jsonRow.style.cssText = 'display:flex;gap:3px;margin-top:3px;';  // פריסה
            var expJson = L.DomUtil.create('button', '', jsonRow); expJson.textContent = '⬇ ייצוא JSON';  // ייצוא
            var impJson = L.DomUtil.create('button', '', jsonRow); impJson.textContent = '⬆ ייבוא JSON';  // ייבוא
            [expJson, impJson].forEach(function(b) {{ b.style.cssText = 'flex:1;font-size:9px;padding:1px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;'; }});  // עיצוב
            var impFile = L.DomUtil.create('input', '', jsonRow); impFile.type = 'file'; impFile.accept = '.json'; impFile.style.display = 'none';  // בורר קבצים נסתר
            L.DomEvent.on(expJson, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtExportProfileJson(); }});  // ייצוא
            L.DomEvent.on(impJson, 'click', function(e) {{ L.DomEvent.stopPropagation(e); impFile.click(); }});  // פותח בחירת קובץ
            var profStatus = L.DomUtil.create('div', '', rtProf);  // תוצאת הייבוא — טקסט ולא alert, כדי לא לחסום
            profStatus.style.cssText = 'font-size:8.5px;color:#555;margin-top:2px;';  // טקסט משני
            L.DomEvent.on(impFile, 'change', function() {{  // קובץ נבחר
                var f = impFile.files && impFile.files[0]; if (!f) return;  // אין
                var rd = new FileReader();  // קריאה מקומית
                rd.onload = function() {{ profStatus.textContent = _rtImportProfileJson(String(rd.result)); impFile.value = ''; }};  // החלה + הודעה, ואיפוס הבורר לבחירה חוזרת
                rd.readAsText(f);  // טקסט
            }});
            // ---- שלב ב': הצעת מיקום עם מפת חום — סביב המכ"ם הנוכחי, על המסלול של הבדיקה האחרונה ----
            var rtPl = L.DomUtil.create('details', '', top);  // אזור מתקפל
            rtPl.style.cssText = 'font-size:9px;border:1px solid #ddd;border-radius:3px;padding:2px 4px;';  // מסגרת
            var rtPlSum = L.DomUtil.create('summary', '', rtPl); rtPlSum.textContent = '🗺 הצעת מיקום (מפת חום)';  // כותרת
            rtPlSum.style.cssText = 'cursor:pointer;color:#555;';  // סמן לחיצה
            var rtPlNote = L.DomUtil.create('div', '', rtPl);  // הסבר
            rtPlNote.style.cssText = 'font-size:8.5px;color:#888;';  // טקסט משני
            rtPlNote.textContent = 'בודק מיקומים סביב המכ"ם הנוכחי על המסלול של הבדיקה האחרונה. רשת גבהים גסה — סינון ראשוני; את המיקום שנבחר מאמתים בבדיקה הרגילה.';  // הבהרה
            _rtPlace.radius = _ballisticsMkField('רדיוס חיפוש [ק"מ]', 3, 0.5, 0.2, 30, 'עד כמה רחוק מהמכ"ם הנוכחי לחפש', rtPl, null);  // רדיוס
            _rtPlace.step = _ballisticsMkField('מרווח בין מיקומים [מ\\']', 500, 50, 50, 10000, 'עד 400 מיקומים בסך הכל', rtPl, null);  // מרווח
            _rtPlace.metric = _ballisticsMkSelect('מה נחשב טוב', [['זמן התרעה מרבי', 'warning'], ['אחוז כיסוי מרבי', 'coverage']], 0,
                'במצב מעקב: זמן מפתיחת המעקב עד הסוף / אחוז הזמן במעקב. במצב גילוי: מהגילוי הראשון / אחוז הזמן בגילוי', rtPl);  // הציון (החלטה 11)
            var plRow = L.DomUtil.create('div', '', rtPl);  // כפתורים
            plRow.style.cssText = 'display:flex;gap:3px;margin-top:2px;';  // פריסה
            var plRun = L.DomUtil.create('button', '', plRow); plRun.textContent = '🗺 חשב מפת חום';  // הפעלה
            var plCancel = L.DomUtil.create('button', '', plRow); plCancel.textContent = 'בטל';  // ביטול
            var plClear = L.DomUtil.create('button', '', plRow); plClear.textContent = 'נקה';  // ניקוי
            [plRun, plCancel, plClear].forEach(function(b) {{ b.style.cssText = 'flex:1;font-size:9px;padding:1px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;'; }});  // עיצוב
            plRun.style.background = '#cce3fd';  // הכפתור הראשי — בגוון הסולם
            _rtPlace.info = L.DomUtil.create('div', '', rtPl);  // התקדמות ותוצאה
            _rtPlace.info.style.cssText = 'font-size:9px;color:#333;white-space:pre-wrap;direction:rtl;text-align:right;';  // טקסט
            _rtPlace.legend = document.createElement('canvas');  // מקרא הסולם
            _rtPlace.legend.setAttribute('role', 'img'); _rtPlace.legend.setAttribute('aria-label', 'מקרא מפת החום: צבע בהיר = ציון נמוך, כהה = גבוה');  // T12 (F-041)
            _rtPlace.legend.style.cssText = 'width:250px;height:30px;display:none;';  // מוסתר עד שיש תוצאה
            rtPl.appendChild(_rtPlace.legend);  // לאזור
            L.DomEvent.on(plRun, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtPlacementRun(); }});  // הפעלה
            L.DomEvent.on(plCancel, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtPlacementCancel(); }});  // ביטול
            L.DomEvent.on(plClear, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _rtPlacementClear(); _rtPlace.info.textContent = ''; }});  // ניקוי
            var rtInfo = L.DomUtil.create('div', '', top);  // שורת הסיכום של הבדיקה — נפרדת מ-info כדי שלא תידרס
            rtInfo.style.cssText = 'font-size:9.5px;color:#333;white-space:pre-wrap;direction:rtl;text-align:right;';  // כמו info
            var rtTimeline = document.createElement('canvas');  // ציר הזמן של המעקב (שלב א2)
            rtTimeline.setAttribute('role', 'img'); rtTimeline.setAttribute('aria-label', 'ציר זמן המעקב: מצב הגילוי והמעקב לאורך זמן המעוף (הפירוט בטקסט הסיכום)');  // T12 (F-041)
            rtTimeline.style.cssText = 'width:250px;height:40px;display:none;margin-top:2px;';  // רוחב בפיקסלים — ר' ההערה על canvas למטה; מוסתר עד שיש תוצאה
            top.appendChild(rtTimeline);  // לטאב
            // ---- שלב א3: מניפת LOS, ייצוא CSV, גרף צד ופרופיל שטח לנקודה ----
            var rtViewRow = L.DomUtil.create('div', '', top);  // שורה: מתג המניפה + כפתור ייצוא
            rtViewRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#555;';  // פריסה
            var rtFanLbl = L.DomUtil.create('label', '', rtViewRow);  // תווית המתג
            rtFanLbl.style.cssText = 'display:flex;align-items:center;gap:3px;cursor:pointer;';  // תיבה + טקסט
            var rtFanChk = L.DomUtil.create('input', '', rtFanLbl); rtFanChk.type = 'checkbox'; rtFanChk.checked = true;  // מופעל כברירת מחדל (החלטה 2)
            L.DomUtil.create('span', '', rtFanLbl).textContent = 'קווי LOS מהמכ"ם';  // הטקסט
            var rtCsvBtn = L.DomUtil.create('button', '', rtViewRow);  // ייצוא
            rtCsvBtn.textContent = '⬇ CSV'; rtCsvBtn.title = 'ייצוא שורה לכל נקודה: זמן, מיקום, גובה, טווח, זווית, מצב וסיבה';  // תווית והסבר
            rtCsvBtn.style.cssText = 'font-size:9px;padding:1px 6px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';  // עיצוב
            var rtSide = document.createElement('canvas');  // גרף צד: מרחק × גובה
            rtSide.setAttribute('role', 'img'); rtSide.setAttribute('aria-label', 'גרף צד: גובה המסלול והשטח לפי מרחק מהמכ"ם, צבוע לפי מצב הגילוי');  // T12 (F-041)
            rtSide.style.cssText = 'width:250px;height:120px;display:none;margin-top:2px;border:1px solid #eee;';  // מוסתר עד שיש תוצאה
            top.appendChild(rtSide);  // לטאב
            var rtProfInfo = L.DomUtil.create('div', '', top);  // כותרת פרופיל השטח
            rtProfInfo.style.cssText = 'font-size:9px;color:#333;direction:rtl;text-align:right;';  // כמו שאר הטקסטים
            var rtProfile = document.createElement('canvas');  // פרופיל שטח לנקודה שנלחצה
            rtProfile.setAttribute('role', 'img'); rtProfile.setAttribute('aria-label', 'פרופיל שטח בין המכ"ם לנקודה שנבחרה במסלול');  // T12 (F-041)
            rtProfile.style.cssText = 'width:250px;height:90px;display:none;border:1px solid #eee;';  // מוסתר עד לחיצה
            top.appendChild(rtProfile);  // לטאב
            _rtViewEls = {{fan: rtFanChk, side: rtSide, profile: rtProfile, profInfo: rtProfInfo}};  // הפניות גלובליות לפונקציות הציור
            L.DomEvent.on(rtFanChk, 'change', function() {{ _radarTrackDrawFan(_radarTrackLastResult); }});  // הצגה/הסתרה מיידית
            L.DomEvent.on(rtCsvBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _radarTrackExportCsv(); }});  // ייצוא
            L.DomEvent.on(rtBtn, 'click', function(e) {{  // לחיצה
                L.DomEvent.stopPropagation(e);  // לא להעביר את הלחיצה למפה
                _rtRunFromSource(rtInfo, rtTimeline);  // שלב א4: הבדיקה על המקור שנבחר בראש הטאב
            }});
        }}

        function _ballisticsBuildSolveTab(body) {{
            var top = L.DomUtil.create('div', '', body);
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            var note = L.DomUtil.create('div', '', top);
            note.style.cssText = 'font-size:8.5px;color:#888;';
            note.textContent = 'משתמש במיקום המטרה שהוצב על המפה (לחצן "✏️ מטרה")';

            var modeRow = L.DomUtil.create('div', '', top);
            modeRow.style.cssText = 'display:flex;gap:4px;font-size:9px;';
            var groupSel = _ballisticsMkSelect('קבוצת זוויות', [['נמוכה', 'low'], ['גבוהה', 'high'], ['שתיהן', 'both']], 0, '', top);

            var qeMinInput = _ballisticsMkField('הגבהה מינימלית מותרת (ריק=אין)', '', 1, null, null, '', top, null);
            var qeMaxInput = _ballisticsMkField('הגבהה מקסימלית מותרת (ריק=אין)', '', 1, null, null, '', top, null);
            _ballisticsSolveSetQeMin = function(qeBoth) {{ qeMinInput.value = qeBoth.mils.toFixed(1); }};

            var fixedWrap = L.DomUtil.create('label', '', top);
            fixedWrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
            var fixedSpan = L.DomUtil.create('span', '', fixedWrap); fixedSpan.textContent = 'הגבהה קבועה, V0 מחושב';
            fixedSpan.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';  // ר' הערה ב-_mkField למעלה — מונע חריגת-רוחב של הפאנל
            var fixedChk = L.DomUtil.create('input', '', fixedWrap); fixedChk.type = 'checkbox'; fixedChk.style.flexShrink = '0';
            var fixedQeInput = _ballisticsMkField('הגבהה קבועה', 450, 1, 5, 1350, '', top, null);
            var mvMinInput = _ballisticsMkField('מהירות-לוע מינ\\' [מ\\'/ש\\']', 400, 1, 1, null, '', top, null);
            var mvMaxInput = _ballisticsMkField('מהירות-לוע מקס\\' [מ\\'/ש\\']', 900, 1, 1, null, '', top, null);
            var fixedRowEls = [fixedQeInput.parentElement, mvMinInput.parentElement, mvMaxInput.parentElement];
            function _syncFixedMode() {{
                fixedRowEls.forEach(function(e) {{ e.style.display = fixedChk.checked ? 'flex' : 'none'; }});
                groupSel.parentElement.style.display = fixedChk.checked ? 'none' : 'flex';
                qeMinInput.parentElement.style.display = fixedChk.checked ? 'none' : 'flex';
                qeMaxInput.parentElement.style.display = fixedChk.checked ? 'none' : 'flex';
            }}
            L.DomEvent.on(fixedChk, 'change', _syncFixedMode); _syncFixedMode();

            var runBtn = L.DomUtil.create('button', '', top);
            runBtn.textContent = 'חשב פתרון ירי'; runBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
            var info = L.DomUtil.create('div', '', top);
            info.style.cssText = 'font-size:9.5px;color:#333;white-space:pre-wrap;direction:rtl;text-align:right;max-height:160px;overflow-y:auto;';

            function _showOne(r, titlePrefix) {{
                if (!r || !r.ok) return [titlePrefix + ': ' + (r ? r.error : 'שגיאה')];
                var lines = [titlePrefix, 'הגבהה: ' + _ballisticsFmtAngle(r.qe), 'אזימוט ירי: ' + _ballisticsFmtAngle(r.fire_azimuth)];
                if (r.target_azimuth) lines.push('אזימוט למטרה: ' + _ballisticsFmtAngle(r.target_azimuth));
                if (r.deflection_correction) lines.push('תיקון כיוון: ' + _ballisticsFmtAngle(r.deflection_correction) + ' (שלילי=שמאלה)');
                if (r.muzzle_velocity_mps !== undefined) lines.push('מהירות לוע נדרשת: ' + r.muzzle_velocity_mps.toFixed(1) + ' מ\\'/ש\\'');
                lines.push('טווח למטרה: ' + r.target_range_m.toLocaleString() + ' מ\\' | שארית: ' + r.residual_range_error_m + ' מ\\'');
                lines = lines.concat(_ballisticsImpactLines(r.impact));
                (r.warnings || []).forEach(function(w) {{ lines.push('⚠ ' + w); }});
                return lines;
            }}

            L.DomEvent.on(runBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                if (!ballisticsGun || !ballisticsTarget) {{ alert('הצב תותח ומטרה קודם'); return; }}
                var altMsg = _ballisticsAltGuard(true);  // T21 (F-053): פתרון ירי — צריך גובה תותח ומטרה
                if (altMsg) {{ alert(altMsg); return; }}  // T21: לפני ballisticsLoading
                if (ballisticsLoading) return;
                ballisticsLoading = true; info.textContent = 'מחשב...';
                var common = _ballisticsGetCommonParams();
                var gt = _ballisticsGetGunTarget();
                var path = fixedChk.checked
                    ? fetch('http://localhost:5002/ballistics/solve_mv', {{
                        method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(Object.assign({{}}, common, {{gun: gt.gun, target: gt.target,
                            qe: parseFloat(fixedQeInput.value), mv_min: parseFloat(mvMinInput.value), mv_max: parseFloat(mvMaxInput.value),
                            include_path: true, path_step: 5}})),
                    }})
                    : fetch('http://localhost:5002/ballistics/solve', {{
                        method: 'POST', headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(Object.assign({{}}, common, {{gun: gt.gun, target: gt.target, group: groupSel.value,
                            qe_min: qeMinInput.value === '' ? null : parseFloat(qeMinInput.value),
                            qe_max: qeMaxInput.value === '' ? null : parseFloat(qeMaxInput.value),
                            include_path: true, path_step: 5}})),
                    }});
                path.then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    ballisticsLoading = false;
                    if (_ballisticsMetStatusEl && d.met_used) {{
                        var metTxt = 'מטאו: ' + (d.met_used.description || d.met_used.source || '');
                        _ballisticsMetStatusEl.textContent = metTxt;
                        if (_ballisticsMetTabStatusEl) _ballisticsMetTabStatusEl.textContent = metTxt;  // גם בטאב "מטאו" עצמו
                    }}
                    if (groupSel.value === 'both' && !fixedChk.checked) {{
                        var lines = _showOne(d.low, 'זווית נמוכה').concat(['']).concat(_showOne(d.high, 'זווית גבוהה'));
                        info.textContent = lines.join('\\n');
                        var best = (d.low && d.low.ok) ? d.low : d.high;
                        if (best && best.ok && best.path) {{ _ballisticsDrawPath(best.path, best.impact); _ballisticsRunTerrainCheck(best.path, info); }}
                    }} else {{
                        info.textContent = _showOne(d, 'פתרון ירי').join('\\n');
                        if (d.ok && d.path) {{ _ballisticsDrawPath(d.path, d.impact); _ballisticsRunTerrainCheck(d.path, info); }}
                    }}
                }})
                .catch(function(e) {{ ballisticsLoading = false; info.textContent = 'שגיאת רשת: ' + e.message; }});
            }});
        }}

        function _ballisticsBuildTableTab(body) {{
            var top = L.DomUtil.create('div', '', body);
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            var azInput = _ballisticsMkField('אזימוט ירי', 0, 1, 0, 6400, '', top, null);
            var startInput = _ballisticsMkField('הגבהה מ-', 100, 1, 5, 1350, '', top, null);
            var endInput   = _ballisticsMkField('עד', 1200, 1, 5, 1350, '', top, null);
            var stepInput  = _ballisticsMkField('צעד', 50, 1, 1, null, '', top, null);
            var btnRow = L.DomUtil.create('div', '', top); btnRow.style.cssText = 'display:flex;gap:3px;';
            var runBtn = L.DomUtil.create('button', '', btnRow);
            runBtn.textContent = 'חשב טבלה'; runBtn.style.cssText = 'flex:1;font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
            var expBtn = L.DomUtil.create('button', '', btnRow);
            expBtn.textContent = 'ייצוא CSV'; expBtn.style.cssText = 'flex:1;font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
            var warnEl = L.DomUtil.create('div', '', top); warnEl.style.cssText = 'font-size:9px;color:#b00020;white-space:pre-wrap;';
            var tableWrap = L.DomUtil.create('div', '', top); tableWrap.style.cssText = 'max-height:160px;overflow:auto;';
            var lastRows = null;
            var heads = {{qe_mils:'הגבהה [מיל]', qe_deg:'הגבהה [°]', range_m:'טווח [מ\\']', drift_mils:'סחיפה [מיל]',
                drift_m:'סחיפה [מ\\']', tof_s:'זמן מעוף [ש\\']', apex_m:'קודקוד [מ\\']', impact_vel_mps:'מהירות פגיעה',
                fall_angle_mils:'זווית נפילה [מיל]', fall_angle_deg:'זווית נפילה [°]', sg_min:'Sg מינ\\''}};
            L.DomEvent.on(runBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                if (!ballisticsGun) {{ alert('הצב תותח קודם'); return; }}
                var altMsg = _ballisticsAltGuard(false);  // T21 (F-053): טבלת ירי — צריך גובה תותח
                if (altMsg) {{ alert(altMsg); return; }}  // T21: חסימה עם הסבר
                var common = _ballisticsGetCommonParams();
                var gt = _ballisticsGetGunTarget();
                fetch('http://localhost:5002/ballistics/table', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(Object.assign({{}}, common, {{gun: gt.gun, azimuth: parseFloat(azInput.value),
                        qe_start: parseFloat(startInput.value), qe_end: parseFloat(endInput.value), qe_step: parseFloat(stepInput.value)}})),
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    if (!d.ok) {{ warnEl.textContent = d.error || 'שגיאה'; return; }}
                    lastRows = d.rows;
                    warnEl.textContent = (d.warnings || []).slice(0, 6).join('\\n');
                    var html = '<table style="font-size:8.5px;border-collapse:collapse;width:100%;"><tr>';
                    d.columns.forEach(function(c) {{ html += '<th style="border:1px solid #ddd;padding:1px;">' + heads[c] + '</th>'; }});
                    html += '</tr>';
                    d.rows.forEach(function(r) {{
                        html += '<tr>';
                        d.columns.forEach(function(c) {{ html += '<td style="border:1px solid #ddd;padding:1px;text-align:center;">' + (r[c] !== undefined ? r[c] : (r.error || '')) + '</td>'; }});
                        html += '</tr>';
                    }});
                    html += '</table>';
                    tableWrap.innerHTML = html;
                }})
                .catch(function(e) {{ warnEl.textContent = 'שגיאת רשת: ' + e.message; }});
            }});
            L.DomEvent.on(expBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                if (!lastRows) {{ alert('חשב טבלה קודם'); return; }}
                var cols = Object.keys(heads);
                var csv = cols.join(',') + '\\n' + lastRows.map(function(r) {{ return cols.map(function(c) {{ return r[c] !== undefined ? r[c] : ''; }}).join(','); }}).join('\\n');
                var blob = new Blob([csv], {{type: 'text/csv'}});
                var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'firing_table.csv';
                document.body.appendChild(a); a.click(); document.body.removeChild(a);
            }});
        }}

        function _ballisticsBuildCalTab(body) {{
            var top = L.DomUtil.create('div', '', body);
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            var explain = L.DomUtil.create('div', '', top);
            explain.style.cssText = 'font-size:8.5px;color:#666;';
            explain.textContent = 'הזן נקודות פגיעה שנמדדו בירי אמיתי. מחשב fD (גרר, לפי טווח) ו-fL (עילוי, לפי סחיפה).';
            var qeInput = _ballisticsMkField('הגבהה', 300, 1, 5, 1350, '', top, null);
            var azInput = _ballisticsMkField('אזימוט', 1600, 1, 0, 6400, '', top, null);
            var rngInput = _ballisticsMkField('טווח שנמדד [מ\\']', '', 1, null, null, '', top, null);
            var drInput = _ballisticsMkField('סחיפה שנמדדה (ריק=אין)', '', 0.1, null, null, '', top, null);
            var addBtn = L.DomUtil.create('button', '', top);
            addBtn.textContent = 'הוסף נקודה'; addBtn.style.cssText = 'font-size:10px;padding:2px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
            var tableWrap = L.DomUtil.create('div', '', top); tableWrap.style.cssText = 'max-height:100px;overflow:auto;font-size:8.5px;';
            var pts = [];
            function _renderPts() {{
                var html = '<table style="border-collapse:collapse;width:100%;"><tr><th>הגבהה</th><th>אזימוט</th><th>טווח</th><th>סחיפה</th><th></th></tr>';
                pts.forEach(function(p, i) {{
                    html += '<tr><td>' + p.qe + '</td><td>' + p.azimuth + '</td><td>' + p.range_m + '</td><td>' + (p.drift === null ? '-' : p.drift) +
                        '</td><td><a href="#" data-i="' + i + '" class="bcal-del" style="color:#b00020;">✕</a></td></tr>';
                }});
                html += '</table>';
                tableWrap.innerHTML = html;
                tableWrap.querySelectorAll('.bcal-del').forEach(function(a) {{
                    L.DomEvent.on(a, 'click', function(e) {{ L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e); pts.splice(parseInt(a.dataset.i), 1); _renderPts(); }});
                }});
            }}
            L.DomEvent.on(addBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                var rng = parseFloat(rngInput.value);
                if (isNaN(rng)) {{ alert('הזן טווח שנמדד'); return; }}
                pts.push({{qe: parseFloat(qeInput.value), azimuth: parseFloat(azInput.value), range_m: rng,
                    drift: drInput.value === '' ? null : parseFloat(drInput.value)}});
                rngInput.value = ''; drInput.value = ''; _renderPts();
            }});
            var calBtn = L.DomUtil.create('button', '', top);
            calBtn.textContent = 'כייל'; calBtn.style.cssText = 'font-size:11px;padding:3px;border-radius:3px;border:1px solid #ccc;background:#f9e2af;cursor:pointer;';
            var resultEl = L.DomUtil.create('div', '', top); resultEl.style.cssText = 'font-size:9.5px;font-weight:bold;color:#333;';
            L.DomEvent.on(calBtn, 'click', function(e) {{
                L.DomEvent.stopPropagation(e);
                if (!ballisticsGun) {{ alert('הצב תותח קודם'); return; }}
                if (!pts.length) {{ alert('הוסף לפחות נקודה אחת'); return; }}
                var altMsg = _ballisticsAltGuard(false);  // T21 (F-053): כיול — צריך גובה תותח
                if (altMsg) {{ alert(altMsg); return; }}  // T21: חסימה עם הסבר
                var common = _ballisticsGetCommonParams();
                var gt = _ballisticsGetGunTarget();
                fetch('http://localhost:5002/ballistics/calibrate', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(Object.assign({{}}, common, {{gun: gt.gun, points: pts}})),
                }})
                .then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    if (!d.drag_factor) {{ resultEl.textContent = d.error || 'שגיאה'; return; }}
                    resultEl.textContent = 'fD = ' + d.drag_factor + '   fL = ' + d.lift_factor + '   RMS שגיאת טווח: ' + d.rms_range_error_m + ' מ\\'';
                }})
                .catch(function(e) {{ resultEl.textContent = 'שגיאת רשת: ' + e.message; }});
            }});
        }}

        function _ballisticsBuildMetTab(body) {{
            var top = L.DomUtil.create('div', '', body);
            top.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            var note = L.DomUtil.create('div', '', top);
            note.style.cssText = 'font-size:8.5px;color:#888;';
            note.textContent = 'מוצג אוטומטית אחרי חישוב מסלול/פתרון-ירי ראשון. גרף שכבות-גובה — בתוספת עתידית.';
            var statusEl = L.DomUtil.create('div', '', top); statusEl.style.cssText = 'font-size:9.5px;white-space:pre-wrap;';
            _ballisticsMetTabStatusEl = statusEl;
        }}

        var BallisticsControl = L.Control.extend({{
            options: {{ position: 'topright' }},
            onAdd: function() {{
                var container = L.DomUtil.create('div', 'leaflet-control');
                container.style.cssText = 'display:flex;flex-direction:column;gap:3px;background:white;' +
                    'border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,0.4);padding:4px 6px;font-family:Arial;max-width:270px;';

                var row1 = L.DomUtil.create('div', '', container);
                row1.style.cssText = 'display:flex;align-items:center;gap:5px;';
                var btn = L.DomUtil.create('a', '', row1);
                btn.href = '#'; btn.title = 'מסלול בליסטי (MPM)';
                btn.style.cssText = 'display:flex;align-items:center;justify-content:center;width:26px;height:26px;' +
                    'font-size:14px;background:white;color:#333;text-decoration:none;border-radius:4px;cursor:pointer;flex-shrink:0;' +
                    'opacity:0.4;pointer-events:none;';
                btn.innerHTML = '&#128165;';  // 💥 — לא חופף לאייקוני הכלים האחרים (👁📡🎯🧭)
                btn.setAttribute('role', 'button');  // נגישות — <a> ברירת-מחדל role="link" (F-027, Q-1)
                btn.setAttribute('aria-label', 'כלי מסלול בליסטי');
                _ballisticsBtnEl = btn;
                _ballisticsSetActive = function(on) {{
                    // פתיחה/סגירה של הכלי הבליסטי — פונקציה (ולא רק מטפל לחיצה) כדי שכלי המכ"ם יוכל לסגור אותו
                    ballisticsActive = on;  // המצב
                    btn.style.background = on ? '#fab387' : 'white';  // צבע הכפתור
                    ballisticsPanelBodyEl.style.display = on ? 'flex' : 'none';  // הפאנל
                    map.getContainer().style.cursor = on ? 'crosshair' : '';  // סמן
                    if (on && radarActive) toggleRadarDoppler();  // תיקון תקלה: שני הפאנלים יחד לא נכנסים בגובה המסך ודוחפים את 💥 החוצה — המכ"ם עצמו נשאר על המפה
                    _fitTopRightPanels();  // הגובה המרבי לפי המקום שנשאר בפועל
                }};
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e); L.DomEvent.preventDefault(e);
                    if (!_mapReady || !serversRunning) return;
                    _ballisticsSetActive(!ballisticsActive);  // החלפת מצב
                }});

                var panelBody = L.DomUtil.create('div', '', container);
                panelBody.style.cssText = 'display:none;flex-direction:column;gap:3px;max-height:75vh;overflow-y:auto;';
                ballisticsPanelBodyEl = panelBody;
                _fitPanelEls.push(panelBody);  // תיקון תקלה: הגובה המרבי מותאם למקום שנשאר מתחת לפאנל (לא 75% מכל החלון)

                function _mkHeader(text) {{
                    var h = L.DomUtil.create('div', '', panelBody);
                    h.textContent = text;
                    h.style.cssText = 'font-size:9px;font-weight:bold;color:#888;margin-top:3px;border-top:1px solid #eee;padding-top:2px;';
                    return h;
                }}
                function _mkField(labelText, defaultVal, step, minV, maxV, tip, parentEl, onInput) {{
                    // min-width:0 הוא הדבר הקריטי כאן — נמצא בבדיקה חיה אמיתית: "הפאנל רחב מדי,
                    // חורג מהמסך". שורש-הבעיה: flex-item ברירת-מחדל הוא min-width:auto (לא 0!),
                    // כלומר לא מתכווץ מתחת לרוחב-התוכן הטבעי שלו — תווית ארוכה (כמו "גובה לוע
                    // מעל פני הים [מ']") הרחיבה את כל השורה, ולכן את כל הפאנל (max-width לא עוזר
                    // כשתוכן-בפועל חורג ממנו), מעבר לקצה-המסך בפועל. עם min-width:0+ellipsis
                    // התווית מתקצרת בנקודות במקום לדחוף את הפאנל לרוחב — ר' MAPS-GUI_SRS.md §3.27
                    var wrap = L.DomUtil.create('label', '', parentEl || panelBody);
                    wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                    wrap.title = tip || '';
                    var span = L.DomUtil.create('span', '', wrap); span.textContent = labelText;
                    span.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
                    var inp = L.DomUtil.create('input', '', wrap);
                    inp.type = 'number'; inp.value = defaultVal; inp.step = step;
                    if (minV !== null) inp.min = minV; if (maxV !== null) inp.max = maxV;
                    inp.style.cssText = 'width:58px;flex-shrink:0;font-size:11px;padding:1px 2px;border:1px solid #ccc;border-radius:3px;direction:ltr;text-align:center;';
                    if (onInput) L.DomEvent.on(inp, 'input', onInput);
                    _attachFieldUndo(inp, 'מסלול בליסטי: ' + labelText, onInput || function() {{}});
                    return inp;
                }}
                function _mkSelect(labelText, options, defaultIdx, tip, parentEl) {{
                    var wrap = L.DomUtil.create('label', '', parentEl || panelBody);
                    wrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                    wrap.title = tip || '';
                    var span = L.DomUtil.create('span', '', wrap); span.textContent = labelText;
                    span.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';  // ר' הערה ב-_mkField למעלה
                    var sel = L.DomUtil.create('select', '', wrap);
                    sel.style.cssText = 'width:110px;flex-shrink:0;font-size:9px;padding:1px;border:1px solid #ccc;border-radius:3px;';
                    options.forEach(function(opt, i) {{
                        var o = L.DomUtil.create('option', '', sel); o.value = opt[1]; o.textContent = opt[0];
                        if (i === defaultIdx) o.selected = true;
                    }});
                    _attachSelectUndo(sel, 'מסלול בליסטי: ' + labelText);
                    return sel;
                }}

                // ---- מיקום התותח/המטרה ----
                _mkHeader('מיקום התותח והמטרה');
                var editRow = L.DomUtil.create('div', '', panelBody);
                editRow.style.cssText = 'display:flex;gap:3px;font-size:9px;';
                var editGunBtn = L.DomUtil.create('button', '', editRow);
                editGunBtn.textContent = '✏️ תותח'; editGunBtn.style.cssText = 'flex:1;font-size:9px;padding:2px;border-radius:3px;border:1px solid #f9e2af;background:#fff8e1;cursor:pointer;';
                var editTgtBtn = L.DomUtil.create('button', '', editRow);
                editTgtBtn.textContent = '✏️ מטרה'; editTgtBtn.style.cssText = 'flex:1;font-size:9px;padding:2px;border-radius:3px;border:1px solid #cba6f7;background:#f3e8ff;cursor:pointer;';
                function _refreshEditButtons() {{
                    editGunBtn.style.fontWeight = ballisticsEditing === 'gun' ? 'bold' : 'normal';
                    editTgtBtn.style.fontWeight = ballisticsEditing === 'target' ? 'bold' : 'normal';
                }}
                L.DomEvent.on(editGunBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); ballisticsEditing = 'gun'; _refreshEditButtons(); }});
                L.DomEvent.on(editTgtBtn, 'click', function(e) {{ L.DomEvent.stopPropagation(e); ballisticsEditing = 'target'; _refreshEditButtons(); }});
                _refreshEditButtons();

                var gpsBtn = L.DomUtil.create('button', '', panelBody);
                gpsBtn.textContent = '📍 GPS לתותח'; gpsBtn.style.cssText = 'font-size:9px;padding:2px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
                L.DomEvent.on(gpsBtn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    if (!navigator.geolocation) {{ alert('GPS לא נתמך בדפדפן זה'); return; }}
                    navigator.geolocation.getCurrentPosition(function(pos) {{
                        var ll = L.latLng(pos.coords.latitude, pos.coords.longitude);
                        ballisticsEditing = 'gun'; _refreshEditButtons(); _placeBallisticsPoint(ll);
                        map.panTo(ll);
                    }}, function() {{ alert('לא ניתן היה לקבל מיקום GPS'); }});
                }});

                var gLat = _mkField('קו רוחב תותח [°]', 31.2520, 0.0001, -90, 90, '', null, null);
                var gLon = _mkField('קו אורך תותח [°]', 34.7915, 0.0001, -180, 180, '', null, null);
                var gAlt = _mkField('גובה לוע מעל פני הים [מ\\']', 280, 1, null, null, 'נמשך אוטומטית, ניתן לעריכה ידנית', null, null);
                var tLat = _mkField('קו רוחב מטרה [°]', 31.3600, 0.0001, -90, 90, '', null, null);
                var tLon = _mkField('קו אורך מטרה [°]', 34.8900, 0.0001, -180, 180, '', null, null);
                var tAlt = _mkField('גובה מטרה מעל פני הים [מ\\']', 310, 1, null, null, 'נמשך אוטומטית, ניתן לעריכה ידנית', null, null);
                // T21 (F-053): שורת אזהרה + ניסיון חוזר, מוצגת רק כששליפת גובה נכשלה
                var altWarn = L.DomUtil.create('div', '', panelBody);  // T21: מכל האזהרה
                altWarn.style.cssText = 'display:none;font-size:9px;color:#b00020;background:#fdecea;border:1px solid #f5c2c0;border-radius:3px;padding:2px 4px;';  // T21: אדום בולט, נסתר כברירת מחדל
                altWarn.setAttribute('role', 'alert');  // T21: קוראי מסך מכריזים על האזהרה
                var altWarnTxt = L.DomUtil.create('span', '', altWarn);  // T21: טקסט האזהרה
                var altRetry = L.DomUtil.create('button', '', altWarn);  // T21: כפתור ניסיון חוזר
                altRetry.textContent = '🔄 נסה שוב לשלוף גובה';  // T21: תווית הכפתור
                altRetry.style.cssText = 'margin-inline-start:4px;font-size:10px;min-height:24px;cursor:pointer;';  // T21: יעד לחיצה ≥24px (F-040)
                L.DomEvent.on(altRetry, 'click', function(e) {{  // T21: שולף מחדש רק את הנקודות שנכשלו
                    L.DomEvent.stopPropagation(e);  // T21: הלחיצה לא מגיעה למפה
                    if (ballisticsGun && ballisticsGun.altState === 'failed') _ballisticsFetchAlt('gun');  // T21: תותח
                    if (ballisticsTarget && ballisticsTarget.altState === 'failed') _ballisticsFetchAlt('target');  // T21: מטרה
                }});
                _ballisticsAltUi = function() {{  // T21: מסנכרן שדות גובה ואזהרה עם מצב הנקודות
                    var failed = [];  // T21: שמות הנקודות שהשליפה שלהן נכשלה
                    [[ballisticsGun, gAlt, 'התותח'], [ballisticsTarget, tAlt, 'המטרה']].forEach(function(x) {{  // T21: אותו טיפול לשתי הנקודות
                        var pt = x[0], fld = x[1];  // T21: הנקודה והשדה שלה
                        if (!pt) return;  // T21: נקודה שעוד לא הוצבה
                        if (pt.alt === null || pt.alt === undefined) fld.value = '';  // T21: לא מציגים גובה ישן/ברירת מחדל לנקודה שגובהה לא ידוע
                        fld.placeholder = pt.altState === 'pending' ? 'טוען…' : (pt.alt === null || pt.alt === undefined ? 'הזן ידנית' : '');  // T21: רמז במקום ערך מטעה
                        if (pt.altState === 'failed' && (pt.alt === null || pt.alt === undefined)) failed.push(x[2]);  // T21: לאזהרה
                    }});
                    altWarn.style.display = failed.length ? 'block' : 'none';  // T21: האזהרה רק כשיש כשל
                    altWarnTxt.textContent = '⚠️ שליפת גובה ' + failed.join(' ו') + ' נכשלה — אין חישוב עד שיהיה גובה. הזן ידנית או נסה שוב.';  // T21: הסבר ומה לעשות
                }};
                function _manualAlt(pt, fld) {{  // T21: המשתמש ערך את שדה הגובה בעצמו
                    if (!pt) return;  // T21: אין נקודה — אין מה לעדכן
                    var v = parseFloat(fld.value);  // T21: הערך שהוקלד
                    pt.alt = isFinite(v) ? v : null;  // T21: שדה ריק/לא מספרי = גובה לא ידוע (לא 0)
                    pt.altState = isFinite(v) ? 'manual' : 'failed';  // T21: ידני גובר על תשובת שרת מאוחרת
                    _ballisticsAltUi();  // T21: עדכון האזהרה
                }}
                function _applyManualGun() {{
                    var la = parseFloat(gLat.value), lo = parseFloat(gLon.value);
                    if (isNaN(la) || isNaN(lo)) return;
                    var a = parseFloat(gAlt.value);  // T21: הגובה שבשדה לפני ההצבה (ההצבה מנקה את השדה)
                    ballisticsEditing = 'gun'; _placeBallisticsPoint(L.latLng(la, lo));
                    if (isFinite(a)) {{ ballisticsGun.alt = a; _ballisticsSyncFields(); _ballisticsAltUi(); }}  // T21: ערך זמני שמוצג בשדה; השליפה האוטומטית עדיין מעדנת אותו
                }}
                function _applyManualTarget() {{
                    var la = parseFloat(tLat.value), lo = parseFloat(tLon.value);
                    if (isNaN(la) || isNaN(lo)) return;
                    var a = parseFloat(tAlt.value);  // T21: הגובה שבשדה לפני ההצבה
                    ballisticsEditing = 'target'; _placeBallisticsPoint(L.latLng(la, lo));
                    if (isFinite(a)) {{ ballisticsTarget.alt = a; _ballisticsSyncFields(); _ballisticsAltUi(); }}  // T21: כמו בתותח
                }}
                L.DomEvent.on(gLat, 'change', _applyManualGun); L.DomEvent.on(gLon, 'change', _applyManualGun);
                L.DomEvent.on(gAlt, 'change', function() {{ _manualAlt(ballisticsGun, gAlt); }});  // T21: עריכה ידנית מסומנת 'manual'; שדה ריק = לא ידוע
                L.DomEvent.on(tLat, 'change', _applyManualTarget); L.DomEvent.on(tLon, 'change', _applyManualTarget);
                L.DomEvent.on(tAlt, 'change', function() {{ _manualAlt(ballisticsTarget, tAlt); }});  // T21: כמו בתותח
                _ballisticsSyncFields = function() {{
                    // מעדכן את כל שדות הקלט (lat/lon/alt של תותח+מטרה) מהמצב הפנימי — נקרא אחרי כל הצבה/גרירה/GPS
                    if (ballisticsGun) {{
                        gLat.value = ballisticsGun.lat.toFixed(5); gLon.value = ballisticsGun.lng.toFixed(5);
                        if (ballisticsGun.alt !== null) gAlt.value = Math.round(ballisticsGun.alt);
                    }}
                    if (ballisticsTarget) {{
                        tLat.value = ballisticsTarget.lat.toFixed(5); tLon.value = ballisticsTarget.lng.toFixed(5);
                        if (ballisticsTarget.alt !== null) tAlt.value = Math.round(ballisticsTarget.alt);
                    }}
                }};

                // ---- מטאו ----
                _mkHeader('מטאו');
                var metSrcSel = _mkSelect('מקור', [['תחזית חיה (Open-Meteo)', 'live'], ['אטמוספרה סטנדרטית', 'standard']], 0,
                    'קובץ CSV/JSON — טרם ממומש בגרסה זו, ר\\' README');
                var metTemp = _mkField('טמפ\\' בקרקע [°C] (ריק=סטנדרט)', '', 1, null, null, '', null, null);
                var metPres = _mkField('לחץ בקרקע [hPa] (ריק=סטנדרט)', '', 1, null, null, '', null, null);
                var metWspd = _mkField('מהירות רוח [מ\\'/ש\\']', 0, 0.5, 0, null, '', null, null);
                var metWdir = _mkField('כיוון רוח, נושבת מ- [°]', 0, 1, 0, 360, '', null, null);
                var metRow = [metTemp.parentElement, metPres.parentElement, metWspd.parentElement, metWdir.parentElement];
                function _metSrcChanged() {{
                    var std = metSrcSel.value === 'standard';
                    metRow.forEach(function(r) {{ r.style.display = std ? 'flex' : 'none'; }});
                }}
                L.DomEvent.on(metSrcSel, 'change', _metSrcChanged); _metSrcChanged();
                var metStatus = L.DomUtil.create('div', '', panelBody);
                metStatus.style.cssText = 'font-size:9px;color:#888;text-align:center;';
                metStatus.textContent = 'מטאו נטען אוטומטית בחישוב הראשון';
                _ballisticsMetStatusEl = metStatus;

                // ---- פגז ותותח ----
                _mkHeader('פגז ותותח');
                var projLabel = L.DomUtil.create('div', '', panelBody);
                projLabel.style.cssText = 'font-size:9px;color:#b00020;text-align:center;';
                projLabel.textContent = '⚠ Generic 155mm HE — להדגמה בלבד, לא לירי אמיתי';
                var mvInput = _mkField('מהירות לוע [מ\\'/ש\\']', 684, 1, 1, null, '', null, null);

                // ---- מקדמי התאמה וחישוב ----
                _mkHeader('מקדמי התאמה וחישוב');
                var fdInput = _mkField('מקדם גרר fD', 1.0, 0.01, 0.1, 5, '', null, null);
                var flInput = _mkField('מקדם עילוי fL', 1.0, 0.01, 0, 5, '', null, null);
                var dtInput = _mkField('צעד אינטגרציה [ש\\']', 0.02, 0.01, 0.005, 0.2, '', null, null);
                var unitSel = _mkSelect('יחידות קלט', [['מילים', 'mils'], ['מעלות', 'deg']], 0, '');
                var coriolisWrap = L.DomUtil.create('label', '', panelBody);
                coriolisWrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                var coriolisSpan = L.DomUtil.create('span', '', coriolisWrap); coriolisSpan.textContent = 'קוריוליס';
                coriolisSpan.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';  // ר' הערה ב-_mkField למעלה
                var coriolisChk = L.DomUtil.create('input', '', coriolisWrap); coriolisChk.type = 'checkbox'; coriolisChk.checked = true;
                coriolisChk.style.flexShrink = '0';
                _attachCheckboxUndo(coriolisChk, 'מסלול בליסטי: קוריוליס');
                var curvWrap = L.DomUtil.create('label', '', panelBody);
                curvWrap.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:4px;font-size:9px;color:#666;';
                var curvSpan = L.DomUtil.create('span', '', curvWrap); curvSpan.textContent = 'עקמומיות כדור הארץ';
                curvSpan.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
                var curvChk = L.DomUtil.create('input', '', curvWrap); curvChk.type = 'checkbox'; curvChk.checked = true;
                _attachCheckboxUndo(curvChk, 'מסלול בליסטי: עקמומיות כדור הארץ');

                function _ballisticsCommonParams() {{
                    // אוסף את כל הפרמטרים המשותפים (לא ספציפי-לטאב) — נקרא מכל פעולת-חישוב
                    return {{
                        angle_unit: unitSel.value, coriolis: coriolisChk.checked, earth_curvature: curvChk.checked,
                        dt: parseFloat(dtInput.value) || 0.02,
                        fitting: {{drag_factor: parseFloat(fdInput.value) || 1.0, lift_factor: parseFloat(flInput.value) || 1.0}},
                        mv: parseFloat(mvInput.value) || 684,
                        met: metSrcSel.value === 'standard'
                            ? {{source: 'standard', surface_temp_c: metTemp.value === '' ? null : parseFloat(metTemp.value),
                                surface_pressure_hpa: metPres.value === '' ? null : parseFloat(metPres.value),
                                wind_speed_mps: parseFloat(metWspd.value) || 0, wind_dir_deg: parseFloat(metWdir.value) || 0}}
                            : {{source: 'live'}},
                    }};
                }}
                _ballisticsGetCommonParams = _ballisticsCommonParams;
                _ballisticsGetGunTarget = function() {{
                    if (!ballisticsGun) return null;
                    var gun = {{lat: ballisticsGun.lat, lon: ballisticsGun.lng, alt_m: ballisticsGun.alt}};  // T21 (F-053): בלי "|| 0" — גובה לא ידוע לא הופך לגובה פני הים
                    var tgt = ballisticsTarget ? {{lat: ballisticsTarget.lat, lon: ballisticsTarget.lng, alt_m: ballisticsTarget.alt}} : null;  // T21: כנ"ל למטרה
                    return {{gun: gun, target: tgt}};
                }};

                // ---- עמדות שמורות (עקביות עם שאר הכלים) ----
                var _ballisticsFieldMap = {{
                    mv: mvInput, drag_factor: fdInput, lift_factor: flInput, dt: dtInput,
                    angle_unit: unitSel, coriolis: coriolisChk, earth_curvature: curvChk,
                }};
                _buildStationUI(panelBody, 'ballistics', _ballisticsFieldMap,
                    function() {{ return ballisticsGun ? L.latLng(ballisticsGun.lat, ballisticsGun.lng) : null; }},
                    function(latlng) {{ ballisticsEditing = 'gun'; _placeBallisticsPoint(latlng); }},
                    function() {{}}, 'עמדות שמורות (תותח+הגדרות):');

                // ---- טאבים ----
                var tabsRow = L.DomUtil.create('div', '', panelBody);
                tabsRow.style.cssText = 'display:flex;gap:2px;margin-top:4px;flex-wrap:wrap;';
                var tabNames = [['traj', 'מסלול בודד'], ['solve', 'פתרון ירי'], ['table', 'טבלת ירי'], ['cal', 'כיול'], ['met', 'מטאו'], ['radar', '🎯 מעקב מכ"ם']];  // הטאב האחרון: כלי בדיקת מעקב מכ"ם (שלב א4)
                var tabBtns = {{}}, tabBodies = {{}};
                var tabsHolder = L.DomUtil.create('div', '', panelBody);
                function _selectTab(key) {{
                    tabNames.forEach(function(t) {{
                        tabBtns[t[0]].style.background = t[0] === key ? '#fab387' : '#f5f5f5';
                        tabBodies[t[0]].style.display = t[0] === key ? 'flex' : 'none';
                    }});
                }}
                tabNames.forEach(function(t) {{
                    var tb = L.DomUtil.create('button', '', tabsRow);
                    tb.textContent = t[1]; tb.style.cssText = 'flex:1 1 auto;font-size:8.5px;padding:2px 3px;border-radius:3px;border:1px solid #ccc;background:#f5f5f5;cursor:pointer;';
                    L.DomEvent.on(tb, 'click', function(e) {{ L.DomEvent.stopPropagation(e); _selectTab(t[0]); }});
                    tabBtns[t[0]] = tb;
                    var body = L.DomUtil.create('div', '', tabsHolder);
                    body.style.cssText = 'display:none;flex-direction:column;gap:3px;padding-top:3px;';
                    tabBodies[t[0]] = body;
                }});
                _ballisticsSelectTab = _selectTab;
                _ballisticsTabBodies = tabBodies;
                _ballisticsMkField = _mkField; _ballisticsMkSelect = _mkSelect; _ballisticsMkHeader = _mkHeader;

                _ballisticsBuildTrajTab(tabBodies['traj']);
                _ballisticsBuildSolveTab(tabBodies['solve']);
                _ballisticsBuildTableTab(tabBodies['table']);
                _ballisticsBuildCalTab(tabBodies['cal']);
                _ballisticsBuildMetTab(tabBodies['met']);
                _ballisticsBuildRadarTab(tabBodies['radar']);  // כלי בדיקת מעקב מכ"ם — מקור מסלול, הגדרות ותוצאות
                _selectTab('traj');
                _afBuild(panelBody);  // A5: מתג "מסלול בודד | מאזור לאזור" בראש הפאנל + הכלי החדש (המסלול הבודד לא משתנה)

                L.DomEvent.disableClickPropagation(container);
                L.DomEvent.disableScrollPropagation(container);
                return container;
            }}
        }});
        new BallisticsControl().addTo(map);  // הוספת ה-Control למפה

        // באג אמיתי שנמצא בבדיקה חיה (10/11/2026): קביעת "var serversRunning = true" ישירות
        // (למעלה) לא מספיקה כדי להפעיל בפועל את כפתורי LOS/רדיוס-ראייה/מכ"ם-דופלר/בליסטי ב-Web.
        // _updateToolButtonsEnabled() (שמעדכן את opacity/pointer-events של הכפתורים) נקרא פעם
        // אחת מ-map.whenReady - אבל זה קורה *לפני* שהכפתורים האלה נוצרים כלל (הם נוצרים כאן,
        // בהמשך הסקריפט, ע"י new ...Control().addTo(map)) - אז הלולאה-שם מדלגת עליהם (עדיין null).
        // ב-Desktop זה עובד כי main.py קורא ל-_setServersRunning(true) הרבה יותר מאוחר (רק כש
        // המשתמש מפעיל שרתים בפועל, אחרי שהעמוד כולו כבר נטען) - אז כל הכפתורים כבר קיימים.
        // ב-Web אין קריאה שנייה כזו בכלל - נדרשת קריאה מפורשת כאן, במקום הזה בדיוק (אחרי שכל
        // ארבעת הכפתורים כבר קיימים, כי BallisticsControl הוא האחרון מביניהם שנוסף).
        {'_setServersRunning(true);' if target == 'web' else ''}

        // לחיצה על המפה בעת מצב "מסלול בליסטי" — ממקמת תותח/מטרה לפי ballisticsEditing.
        // handler עצמאי (כמו custom-route), לא בתוך הדיספצ'ר המשולב של LOS/רדיוס-ראייה/מכ"ם
        map.on('click', function(e) {{
            if (!ballisticsActive) return;
            if (_rtMapPickActive) return;  // תיקון תקלה: הלחיצה שייכת לבחירה מטאב "מעקב מכ"ם" (מכ"ם / מרכז שיוט) — לא להזיז תותח/מטרה
            if (_af.mode) {{ _afMapClick(e.latlng); return; }}  // A5: במצב "מאזור לאזור" הלחיצה מציירת אזור (או לא עושה כלום) — לא מזיזה תותח/מטרה
            _placeBallisticsPoint(e.latlng);
        }});

        // ── התאמת גובה הפאנלים בעמודה הימנית (תיקון תקלה, 26/11/2026) ──
        // הפאנלים הוגבלו ב-70-75% מגובה החלון כולו, אבל הם מתחילים מתחת לכמה כפתורי כלים, ולכן התחתית שלהם
        // (כולל פס הגלילה) יצאה מתחת למסך — "לא ניתן לראות את כל פתרון הירי". כאן הגובה המרבי של כל פאנל פתוח
        // מחושב מתחילתו ועד תחתית המפה, ומתעדכן כשפאנל אחר בעמודה משנה גובה או כשהחלון משנה גודל.
        var _fitCorner = map._controlCorners && map._controlCorners.topright;  // העמודה הימנית-עליונה
        if (_fitCorner && window.ResizeObserver) {{ new ResizeObserver(function() {{ _fitTopRightPanels(); }}).observe(_fitCorner); }}  // כל שינוי גובה בעמודה
        map.on('resize', _fitTopRightPanels);  // שינוי גודל החלון/המפה

        {_build_web_controls_js(api_base) if target == 'web' else ''}

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
                d.setAttribute('role', 'button');  // נגישות — div לחיץ-להרחבה, לא כפתור native (F-027, Q-1)
                d.setAttribute('aria-label', 'הסבר כלל טיסת VLOS, לחץ להרחבה');
                d.setAttribute('aria-expanded', 'false');
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
                    var nowExpanded = body.style.display === 'none';  // המצב *אחרי* הלחיצה הזו
                    body.style.display = nowExpanded ? 'block' : 'none';
                    d.setAttribute('aria-expanded', nowExpanded ? 'true' : 'false');  // נגישות (F-027, Q-1)
                }});
                L.DomEvent.disableClickPropagation(d);
                return d;
            }}
        }});
        new VlosInfoControl().addTo(map);  // תמיד מוצג — לא תלוי בשכבה פעילה

    </script>
</body>
</html>
"""

    if target == 'web':
        # מחליף כתובות API קשיחות (http://localhost:5002/5003, קיימות רק כדי לשרת את גרסת-
        # הדסקטופ) בבסיס-URL הדינמי — ב-web זה בד"כ ריק (api_base='') כי vercel.json מנתב
        # כל נתיב (/weather, /geo_data וכו') לפונקציה המתאימה מאותו origin, בלי port קשיח.
        # 21 המופעים כולם בתוך fetch(...) בלבד (לא טקסט-תצוגה) — אומת ב-MAPS-GUI_SRS.md §3.24.
        html_content = html_content.replace('http://localhost:5002', api_base).replace('http://localhost:5003', api_base)

    with open(map_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"נוצרה מפה ושמה: {map_file}")


# קריאה לפונקציה ליצירת המפה
if __name__ == "__main__":
    create_map()
