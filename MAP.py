import os
import json  # הזרקת נתונים סטטיים (אזורי תיאום, קטגוריות NOTAM) כליטרלי JS — ר' בהמשך
from dotenv import load_dotenv  # טעינת משתני סביבה (נשמר לתאימות עתידית)
from uas_coordination_zones import UAS_COORDINATION_ZONES  # נתוני "אזורי תיאום כטב"ם" — סטטיים, לא נשלפים בזמן ריצה
from notam_categories import NOTAM_CATEGORIES  # 7 קטגוריות סיווג NOTAM (id/label/color) — סטטי, ר' notam_categories.py

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
        var elevBoundsRect  = null;   // מלבן בחירה אחרי טעינה
        var elevHandles     = [];     // 4 ידיות פינות לעריכת הבחירה
        var tempHeatLayer   = null;   // שכבת מפת חום טמפרטורה — null כשכבויה
        var tempSelectStart = null;   // נקודת תחילת בחירת אזור
        var tempPreviewRect = null;   // מלבן preview בזמן גרירה
        var tempSelecting   = false;  // האם המשתמש נמצא באמצע בחירת אזור
        var _tempMDHandler  = null;   // פניה ל-mousedown handler לצורך ביטול
        var tempBoundsRect  = null;   // מלבן בחירה אחרי טעינה
        var tempHandles     = [];     // 4 ידיות פינות לעריכת הבחירה

        // ── מצב תצוגת שכבות ──
        var elevDisplayMode = 'heat';  // 'heat' | 'grid' | 'dots'
        var _elevRawData    = [];      // {{lat, lng, v}} ערך נורמלי 0-1
        var elevGridLayer   = null;    // שכבת grid/dots לגבהים
        var tempDisplayMode = 'heat';  // 'heat' | 'grid' | 'dots'
        var _tempRawData    = [];      // {{lat, lng, v}} ערך נורמלי 0-1
        var tempGridLayer   = null;    // שכבת grid/dots לטמפרטורה
        var _elevGrad = [[0,[0,0,204]],[0.2,[0,170,255]],[0.4,[0,255,204]],[0.6,[170,255,0]],[0.8,[255,170,0]],[1,[204,0,0]]];
        var _tempGrad = [[0,[0,0,204]],[0.25,[0,170,255]],[0.5,[0,255,204]],[0.75,[255,170,0]],[1,[204,0,0]]];

        // ── מצב כלי קווי ראייה (LOS) ──
        var losActive   = false;  // האם מצב הוספת קו ראייה חדש פעיל (cursor crosshair)
        var losSessions = [];     // כל הסשנים שחושבו: [{{obsMk, tgtMk, lineLayers, data, color, idx}}]
        var losCurObs   = null;   // נקודת התצפית של הצמד הנוכחי (בין לחיצה 1 ל-2)
        var losCurObsMk = null;   // סמן תצפית זמני של הצמד הנוכחי (לפני בחירת היעד)
        var losPanelEl  = null;   // אלמנט פאנל גרפים תחתון
        var _losBtnEl   = null;   // הפניה לכפתור 👁 לצורך שינוי צבעו
        var _losObsInput = null; // שדה קלט גובה הצופה מעל הקרקע (מ')
        var _losTgtInput = null; // שדה קלט גובה היעד מעל הקרקע (מ')
        // פלטת צבעים — כל סשן מקבל צבע אחר לסמניו ולכותרת גרפו
        var _losPalette = ['#4488ff','#ffaa00','#cc44ff','#00cccc','#ff4488','#88ff44'];

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

        function _buildTempCanvas() {{
            if (_tempRawData.length < 4) return null;
            var latSet = {{}}, lngSet = {{}};
            _tempRawData.forEach(function(p) {{ latSet[p.lat.toFixed(6)] = 1; lngSet[p.lng.toFixed(6)] = 1; }});
            var lats = Object.keys(latSet).map(Number).sort(function(a,b){{return a-b;}});
            var lngs = Object.keys(lngSet).map(Number).sort(function(a,b){{return a-b;}});
            var nLat = lats.length, nLng = lngs.length;
            if (nLat < 2 || nLng < 2) return null;
            var dlat = (lats[nLat-1] - lats[0]) / (nLat - 1);
            var dlng = (lngs[nLng-1] - lngs[0]) / (nLng - 1);
            var vals = [];
            for (var i = 0; i < nLat; i++) {{ vals[i] = []; for (var j = 0; j < nLng; j++) vals[i][j] = 0.5; }}
            _tempRawData.forEach(function(p) {{
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
            var alpha = Math.round(_tempHeatOpacity * 255);
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
                    var c = _normToColorArr(v, _tempGrad);
                    var idx = (py * W + px) * 4;
                    imgData.data[idx]=c[0]; imgData.data[idx+1]=c[1]; imgData.data[idx+2]=c[2]; imgData.data[idx+3]=alpha;
                }}
            }}
            ctx.putImageData(imgData, 0, 0);
            return {{ canvas: canvas, bounds: [[minLat - dlat/2, minLng - dlng/2], [maxLat + dlat/2, maxLng + dlng/2]] }};
        }}

        var _elevHeatOpacity = 0.75;

        function _buildElevCanvas() {{
            if (_elevRawData.length < 4) return null;
            var latSet = {{}}, lngSet = {{}};
            _elevRawData.forEach(function(p) {{ latSet[p.lat.toFixed(6)] = 1; lngSet[p.lng.toFixed(6)] = 1; }});
            var lats = Object.keys(latSet).map(Number).sort(function(a,b){{return a-b;}});
            var lngs = Object.keys(lngSet).map(Number).sort(function(a,b){{return a-b;}});
            var nLat = lats.length, nLng = lngs.length;
            if (nLat < 2 || nLng < 2) return null;
            var dlat = (lats[nLat-1] - lats[0]) / (nLat - 1);
            var dlng = (lngs[nLng-1] - lngs[0]) / (nLng - 1);
            var vals = [];
            for (var i = 0; i < nLat; i++) {{ vals[i] = []; for (var j = 0; j < nLng; j++) vals[i][j] = 0.5; }}
            _elevRawData.forEach(function(p) {{
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
            var alpha = Math.round(_elevHeatOpacity * 255);
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
                    var c = _normToColorArr(v, _elevGrad);
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
                var res = _buildElevCanvas();
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
                var res = _buildTempCanvas();
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

        var UasNotamLegend = L.Control.extend({{
            options: {{ position: 'bottomleft' }},
            onAdd: function() {{
                var d = L.DomUtil.create('div', '');
                d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;padding:6px 10px;'
                    + 'border-radius:7px;font-size:11px;font-family:Arial;border:1px solid #45475a;'
                    + 'direction:rtl;max-width:230px;';
                var rows = '';  // שורת צבע+תווית לכל קטגוריה שמסומנת כרגע — מקרא דינמי, לא קבוע
                activeNotamCategories.forEach(function(id) {{
                    var cat = _notamCategoryById(id);
                    if (!cat) return;
                    rows += '<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">'
                        + '<span style="display:inline-block;width:12px;height:12px;background:' + cat.color + ';'
                        + 'border-radius:3px;flex-shrink:0;"></span><span>' + _escHtml(cat.label) + '</span></div>';
                }});
                d.innerHTML =
                    '<div style="font-weight:bold;">&#9992; אזורי פעילות טיסה (NOTAM)</div>'
                    + rows
                    + '<div style="color:#a6adc8;margin-top:4px;">אזור פעילות/הגבלה מוכרזת — להימנעות, לא לטיסה חופשית. לחץ על צורה לפרטים.</div>';
                return d;
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
                var style = {{ color: color, weight: 3, fillColor: color, fillOpacity: 0.4 }};  // weight/fillOpacity מוגברים — בולט יותר על רקע המפה הכהה
                var shape;
                if (z.geometry.type === 'circle') {{
                    shape = L.circle(z.geometry.center, Object.assign({{ radius: z.geometry.radius_m }}, style));  // מעגל: "X NM RADIUS CENTERED ON PSN"
                }} else {{
                    shape = L.polygon(z.geometry.points, style);  // פוליגון: "AN AREA BTN FLW PSN" עם 3+ קואורדינטות
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
            uasNotamLayer = L.layerGroup(shapes).addTo(map);
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
                var d = L.DomUtil.create('div', '');
                d.style.cssText = 'background:rgba(30,30,46,.92);color:#cdd6f4;padding:6px 10px;'
                    + 'border-radius:7px;font-size:11px;font-family:Arial;border:1px solid #45475a;'
                    + 'direction:rtl;max-width:230px;';
                d.innerHTML =
                    '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">'
                    + '<span style="display:inline-block;width:14px;height:14px;background:#6366f1;'
                    + 'border-radius:3px;flex-shrink:0;"></span>'
                    + '<b>&#128737; אזורי תיאום כטב"ם — דורש אישור נת"א</b></div>'
                    + '<div style="color:#a6adc8;">כל שימוש באזור מחייב תיאום ואישור מראש מיחידת הנת"א הרלוונטית — לא אזור חופשי לטיסה. לחץ על צורה לפרטים.</div>';
                return d;
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
                    shape = L.circle(z.geometry.center, Object.assign({{ radius: z.geometry.radius_m }}, style));
                }} else {{
                    shape = L.polygon(z.geometry.points, style);
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

        // ── איפוס מצב המפה ──
        function resetMapState() {{
            clearFlightRoute();
            clearAllNotamCategories();  // מנקה גם את בחירת קטגוריות ה-NOTAM עצמה, לא רק את הציור (ר' clearUasNotamLayer)
            clearUasCoordZonesLayer();
            clearTempHeatmap();
            clearRuler();  // מנקה קווי/נקודות/תוויות סרגל ומאפס rulerActive+cursor — היה חסר, קווי מדידה נשארו על המפה אחרי איפוס
            clearLosMap();   // ניקוי כל קווי הראייה, הסמנים והפאנל — LOS מאופס יחד עם שאר השכבות
            if (losActive) {{ toggleLos(); }}  // כיבוי מצב LOS אם פעיל, כדי לאפס cursor וכפתור
            // ניקוי גרירה באמצע בחירת אזור גבהים (elevSelecting=true אך elevationActive=false)
            if (elevSelecting) {{
                map.off('mousemove', _updateElevPreview);
                map.off('mouseup',   _finishElevSelection);
                if (elevPreviewRect) {{ map.removeLayer(elevPreviewRect); elevPreviewRect = null; }}
                elevSelecting   = false;
                elevSelectStart = null;
                map.dragging.enable();
                map.getContainer().style.cursor = '';
            }}
            if (elevationLayer) {{ map.removeLayer(elevationLayer); elevationLayer = null; }}
            if (elevGridLayer)  {{ map.removeLayer(elevGridLayer);  elevGridLayer  = null; }}
            elevationActive = false;
            elevationPoints = [];
            _elevRawData    = [];
            _clearElevHandles();
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
        var elevSelecting    = false; // האם המשתמש נמצא באמצע גרירה כרגע

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

            map.once('mousedown', function(e) {{           // האזנה חד-פעמית ללחיצה ראשונה בלבד
                elevSelectStart = e.latlng;                // שמירת נקודת ההתחלה
                elevSelecting   = true;                    // סימון שהגרירה החלה

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
            }});
        }}

        function _updateElevPreview(e) {{
            // עדכון גבולות המלבן לפי המיקום הנוכחי של העכבר
            if (elevPreviewRect && elevSelectStart) {{
                elevPreviewRect.setBounds([elevSelectStart, e.latlng]);  // שתי נקודות מגדירות את המלבן
            }}
        }}

        function _clearElevHandles() {{
            if (elevBoundsRect) {{ map.removeLayer(elevBoundsRect); elevBoundsRect = null; }}
            elevHandles.forEach(function(h) {{ map.removeLayer(h); }});
            elevHandles = [];
        }}

        function _drawElevHandles(bounds) {{
            _clearElevHandles();
            elevBoundsRect = L.rectangle(bounds, {{
                color: '#89b4fa', weight: 1.5, dashArray: '5,4', fillOpacity: 0, interactive: false
            }}).addTo(map);
            var sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
            var corners = [sw, L.latLng(sw.lat, ne.lng), ne, L.latLng(ne.lat, sw.lng)];
            var handleHtml = '<div style="width:12px;height:12px;background:#89b4fa;border:2px solid #fff;'
                           + 'border-radius:3px;cursor:move;box-shadow:0 1px 3px rgba(0,0,0,.4);"></div>';
            var handleIcon = L.divIcon({{ html: handleHtml, className: '', iconSize: [12,12], iconAnchor: [6,6] }});
            corners.forEach(function(corner, i) {{
                var h = L.marker(corner, {{ icon: handleIcon, draggable: true, zIndexOffset: 900 }}).addTo(map);
                h.on('drag', function(ev) {{
                    var p = ev.target.getLatLng();
                    var cur = elevBoundsRect.getBounds();
                    var s=cur.getSouth(), n=cur.getNorth(), w=cur.getWest(), e=cur.getEast();
                    if (i===0){{s=p.lat;w=p.lng;}} else if (i===1){{s=p.lat;e=p.lng;}}
                    else if (i===2){{n=p.lat;e=p.lng;}} else {{n=p.lat;w=p.lng;}}
                    var nb = L.latLngBounds([[s,w],[n,e]]);
                    elevBoundsRect.setBounds(nb);
                    var nsw=nb.getSouthWest(), nne=nb.getNorthEast();
                    var nc=[nsw,L.latLng(nsw.lat,nne.lng),nne,L.latLng(nne.lat,nsw.lng)];
                    elevHandles.forEach(function(hh,j){{ if(j!==i) hh.setLatLng(nc[j]); }});
                }});
                h.on('dragend', function() {{
                    var nb = elevBoundsRect.getBounds();
                    var sw2=nb.getSouthWest(), ne2=nb.getNorthEast();
                    if (Math.abs(ne2.lat-sw2.lat)<0.001 || Math.abs(ne2.lng-sw2.lng)<0.001) return;
                    _loadElevationForBounds(nb);
                }});
                elevHandles.push(h);
            }});
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
            // אם השכבה פעילה — כבה אותה; אחרת — פתח מצב בחירת אזור
            if (elevationActive) {{
                if (elevationLayer) {{ map.removeLayer(elevationLayer); elevationLayer = null; }}
                if (elevGridLayer)  {{ map.removeLayer(elevGridLayer);  elevGridLayer  = null; }}
                elevationActive = false;
                elevationPoints = [];
                _elevRawData    = [];
                _clearElevHandles();
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

        function _clearTempHandles() {{
            if (tempBoundsRect) {{ map.removeLayer(tempBoundsRect); tempBoundsRect = null; }}
            tempHandles.forEach(function(h) {{ map.removeLayer(h); }});
            tempHandles = [];
        }}

        function _drawTempHandles(bounds) {{
            _clearTempHandles();
            tempBoundsRect = L.rectangle(bounds, {{
                color: '#f38ba8', weight: 1.5, dashArray: '5,4', fillOpacity: 0, interactive: false
            }}).addTo(map);
            var sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
            var corners = [sw, L.latLng(sw.lat, ne.lng), ne, L.latLng(ne.lat, sw.lng)];
            var handleHtml = '<div style="width:12px;height:12px;background:#f38ba8;border:2px solid #fff;'
                           + 'border-radius:3px;cursor:move;box-shadow:0 1px 3px rgba(0,0,0,.4);"></div>';
            var handleIcon = L.divIcon({{ html: handleHtml, className: '', iconSize: [12,12], iconAnchor: [6,6] }});
            corners.forEach(function(corner, i) {{
                var h = L.marker(corner, {{ icon: handleIcon, draggable: true, zIndexOffset: 900 }}).addTo(map);
                h.on('drag', function(ev) {{
                    var p = ev.target.getLatLng();
                    var cur = tempBoundsRect.getBounds();
                    var s=cur.getSouth(), n=cur.getNorth(), w=cur.getWest(), e=cur.getEast();
                    if (i===0){{s=p.lat;w=p.lng;}} else if (i===1){{s=p.lat;e=p.lng;}}
                    else if (i===2){{n=p.lat;e=p.lng;}} else {{n=p.lat;w=p.lng;}}
                    var nb = L.latLngBounds([[s,w],[n,e]]);
                    tempBoundsRect.setBounds(nb);
                    var nsw=nb.getSouthWest(), nne=nb.getNorthEast();
                    var nc=[nsw,L.latLng(nsw.lat,nne.lng),nne,L.latLng(nne.lat,nsw.lng)];
                    tempHandles.forEach(function(hh,j){{ if(j!==i) hh.setLatLng(nc[j]); }});
                }});
                h.on('dragend', function() {{
                    var nb = tempBoundsRect.getBounds();
                    var sw2=nb.getSouthWest(), ne2=nb.getNorthEast();
                    if (Math.abs(ne2.lat-sw2.lat)<0.01 || Math.abs(ne2.lng-sw2.lng)<0.01) return;
                    _loadTempHeatmap(nb);
                }});
                tempHandles.push(h);
            }});
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
                    'border-radius:4px;cursor:pointer;flex-shrink:0;';
                btn.innerHTML = '&#128065;';  // קוד Unicode לאייקון 👁
                _losBtnEl = btn;              // שמירת הפניה לשינוי צבע ב-toggleLos
                // stopPropagation — מניעת הגעת הלחיצה ל-map.on('click') שהייתה בוחרת נקודת LOS
                L.DomEvent.on(btn, 'click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    L.DomEvent.preventDefault(e);
                    toggleLos();
                }});

                // שדות גובה הצופה/היעד — נקראים בעת יצירת כל צמד תצפית/יעד חדש (לפני התחלת מצב LOS)
                function _mkHeightField(labelText, defaultVal, tip) {{
                    var wrap = L.DomUtil.create('label', '', container);
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

                L.DomEvent.disableClickPropagation(container);  // הגנה נוספת על כל ה-Control
                L.DomEvent.disableScrollPropagation(container); // מניעת זום במפה בעת גלילה/שינוי ערך בשדה המספרי
                return container;
            }}
        }});
        new LosControl().addTo(map);  // הוספת ה-Control למפה

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
