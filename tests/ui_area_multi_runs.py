# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""28/11: בדיקת ממשק ל"מאזור לאזור" עם כמה חישובים במקביל (דסקטופ), בדפדפן אמיתי (QtWebEngine, מחוץ למסך).
בלי שרת: ה-fetch של המפה מוחלף בשרת מדומה בתוך הדף, ולכן הבדיקה רצה גם כשהאפליקציה פתוחה (לא נוגעת ב-5002).
בודק: חישוב שני לא מבטל את הראשון; שניהם ברשימה ועל המפה; ביטול של אחד לא נוגע באחר; בחירה מהרשימה מחליפה
את הסיכום; לחיצה על מסלול של חישוב אחר בוחרת אותו; הסתרה והסרה. הרצה: .venv\\Scripts\\python.exe tests/ui_area_multi_runs.py"""
import json  # פענוח תוצאות ה-JS
import os  # נתיבים
import sys  # sys.path וקוד יציאה
import tempfile  # קובץ המפה הזמני
import time  # זמני המתנה

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # פלט עברית
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # שורש הפרויקט
sys.path.insert(0, ROOT)  # ייבוא MAP
# 28/11: בלי QT_QPA_PLATFORM=offscreen — QtWebEngine קורס במצב הזה ב-Windows; חלון רגיל מחוץ למסך (כמו e2e_all_tools.py)
from PyQt5.QtCore import QTimer, QUrl  # noqa: E402  # לולאת אירועים
from PyQt5.QtWebEngineWidgets import QWebEngineScript, QWebEngineView  # noqa: E402  # דפדפן
from PyQt5.QtWidgets import QApplication  # noqa: E402  # אפליקציית Qt
import MAP  # noqa: E402  # יצירת map.html

TMP = tempfile.mkdtemp(prefix="ui_area_multi_")  # תיקייה זמנית
HTML = os.path.join(TMP, "map.html")  # המפה
MAP.create_map(output_path=HTML)  # יצירה

MOCK = r"""(function(){
  window.__jobs = {}; window.__n = 0; window.__calls = [];  // מצב השרת המדומה
  window.__errs = []; window.addEventListener('error', function(e){ window.__errs.push(String(e.message) + ' @' + e.lineno); });  // שגיאות JS שלא נתפסו
  function row(i, la){ var p = []; for (var k = 0; k < 21; k++) p.push([31.20 + k * 0.005, 34.75 + k * 0.005 + i * 0.0003, 300 + k]);  // מסלול סינתטי
    return {la: la, lp: 0, ta: 0, tp: i, group: 'low', launch: [31.2, 34.75, 300], target: [31.3, 34.86 + i * 0.0003, 310], range_m: 15000, qe: {mils: 400, deg: 22.5},
            fire_azimuth: {mils: 900, deg: 50.6}, target_azimuth: {mils: 900, deg: 50.6}, tof_s: 40, apex_msl_m: 3000, min_terrain_margin_m: 50, path: p}; }
  function result(n){ var rows = []; for (var i = 0; i < n; i++) rows.push(row(i, 0));
    return {summary: {launch_points: 1, target_points: n, pairs: n, pairs_feasible: n, trajectories_feasible: n, trajectories_checked: n * 2, rejected: {out_of_range: 0, qe_limits: 0, min_range: 0, max_tof: 0, terrain: 0}, groups: ['low'], elapsed_s: 3, met: '', met_stale: false},
            verification: {checked: 0}, tables: [], resolution_m: {launch: 500, target: 200, terrain: 150}, areas: {launch: ['שיגור 1'], target: ['מטרה 1']},
            heat: {launch: [{area: 0, lat: 31.2, lon: 34.75, count: n}], target: [{area: 0, lat: 31.3, lon: 34.86, count: 1}]}, rows: rows}; }
  window.__resultFor = function(kind){  // 28/11: תוצאה סינתטית לרדיאלי
    var rays = []; for (var b = 0; b < 4; b++) rays.push({bearing_deg: b * 10, lat: 31.3 + b * 0.01, lon: 34.8 + b * 0.01, blocked: b % 2 === 1});  // 4 קרניים
    if (kind === 'D') rays.forEach(function(r, b){ r.radar_lat = r.lat; r.radar_lon = r.lon; r.doppler_ok = b !== 2; });  // 28/11: שדות דופלר
    return {range_km: 10, min_range_km: 0, n_bearings: 4, clear_count: 2, doppler_blocked_rays: 1, span_deg: 30, observer_lat: 31.25, observer_lon: 34.79, rays: rays,  // רדיאלי/סריקה
            points: [{lat: 31.3, lng: 34.8, status: 'detected', reason: 'ok', dist_km: 5}, {lat: 31.32, lng: 34.83, status: 'blocked', reason: 'terrain', dist_km: 8}],  // 28/11: הערכת מסלול
            counts: {detected: 1, doppler_blind: 0, blocked: 1, out_of_range: 0}, points_total: 2}; };
  function resp(d){ return Promise.resolve({ok: true, status: 200, json: function(){ return Promise.resolve(d); }, blob: function(){ return Promise.resolve(new Blob(['x'])); }, clone: function(){ return this; }}); }
  window.fetch = function(u, opt){ u = String(u); window.__calls.push(u.replace('http://localhost:5002', ''));
    if (u.indexOf('/ballistics/area/estimate') >= 0) return resp({launch_points: 1, target_points: 5, pairs: 5, trajectories_max: 10, eta_s: 5, cells_missing: 0, eta_parts_s: {}});
    if (u.indexOf('/ballistics/area/start') >= 0) { var id = 'J' + (++window.__n); window.__jobs[id] = {state: 'running', n: 3 + window.__n}; return resp({job_id: id}); }
    if (u.indexOf('/ballistics/area/cancel') >= 0) { var c = u.split('job_id=')[1]; if (window.__jobs[c]) window.__jobs[c].state = 'cancelled'; return resp({ok: true}); }
    if (u.indexOf('/ballistics/area/visibility') >= 0) { var vid = 'V' + (++window.__n); window.__jobs[vid] = {state: 'done', vis: true}; return resp({job_id: vid, radars: []}); }
    if (u.indexOf('/ballistics/area/status') >= 0) { var j = window.__jobs[u.split('job_id=')[1]] || {state: 'error'};
      if (j.vis) return resp({status: 'done', result: {masks: [], radars: [], summary: {radars: 0, points: 0, points_seen: 0, trajectories_seen_any: 0, trajectories_seen_full: 0, trajectories_unseen: 0}}});
      if (j.state === 'running') return resp({status: 'running', note: 'מחשב', eta_s: 60});
      if (j.state === 'done') return resp({status: 'done', result: result(j.n)});
      return resp({status: j.state, error: j.state === 'error' ? 'x' : null}); }
    // 28/11: רדיוס ראייה רדיאלי ודופלר מכ"ם — אותו מנגנון: start → job, status → running/done, cancel
    var kinds = [['/los_radial/', 'R'], ['/radar_doppler/', 'D']];  // נתיב וקידומת מזהה
    for (var q = 0; q < kinds.length; q++) { var base = kinds[q][0];
      if (u.indexOf(base + 'start') >= 0 || u.indexOf('/radar_doppler/evaluate_route') >= 0) { var rid = kinds[q][1] + (++window.__n); window.__jobs[rid] = {state: 'running'}; return resp({job_id: rid}); }
      if (u.indexOf(base + 'cancel') >= 0) { var cr = u.split('job_id=')[1]; if (window.__jobs[cr]) window.__jobs[cr].state = 'cancelled'; return resp({ok: true}); }
      if (u.indexOf(base + 'status') >= 0) { var jr = window.__jobs[u.split('job_id=')[1]] || {state: 'error'};
        if (jr.state === 'running') return resp({status: 'running', batches_done: 1, batches_total: 4});
        if (jr.state === 'done') return resp({status: 'done', result: window.__resultFor(kinds[q][1])});
        return resp({status: jr.state}); } }
    return resp({});  // שאר הקריאות של המפה (תחנות, פרופילים...) — תשובה ריקה
  };
})();"""  # שרת מדומה בתוך הדף

app = QApplication(sys.argv)  # אפליקציה
view = QWebEngineView()  # דפדפן
sc = QWebEngineScript(); sc.setSourceCode(MOCK); sc.setInjectionPoint(QWebEngineScript.DocumentCreation); sc.setWorldId(QWebEngineScript.MainWorld)  # השרת המדומה לפני סקריפטי המפה
view.page().scripts().insert(sc)  # הזרקה
view.resize(1300, 900); view.move(-3000, -3000); view.show()  # גודל, מחוץ למסך כדי לא להפריע
results, ok = [], [0, 0]  # תוצאות


def check(name, cond, info=""):  # רישום
    ok[0 if cond else 1] += 1  # מונה
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")  # פלט


def js(code):  # הרצת JS וקבלת ערך (סינכרוני דרך לולאת אירועים)
    box = {}  # תוצאה
    view.page().runJavaScript(code, lambda v: box.setdefault("v", v))  # קריאה
    t0 = time.time()  # זמן
    while "v" not in box and time.time() - t0 < 10:  # המתנה
        app.processEvents(); time.sleep(0.01)  # אירועים
    return box.get("v")  # הערך


def wait(cond, secs=10):  # המתנה לתנאי JS
    t0 = time.time()  # זמן
    while time.time() - t0 < secs:  # עד הזמן
        if js(cond):  # התקיים
            return True  # כן
        for _ in range(20):  # אירועים
            app.processEvents(); time.sleep(0.01)  # המתנה קצרה
    return False  # לא


def run():  # התרחיש
    if not wait("typeof _afSetMode === 'function' && !!_af.els.runs", 30):  # המפה נטענה והפאנל נבנה
        check("המפה נטענה", False); return  # כשל
    js("""_afSetMode(true);
          _af.areas = [{name: 'שיגור 1', kind: 'launch', polygon: [[31.2, 34.75], [31.2, 34.76], [31.21, 34.76], [31.21, 34.75]]},
                       {name: 'מטרה 1', kind: 'target', polygon: [[31.3, 34.86], [31.3, 34.87], [31.31, 34.87], [31.31, 34.86]]}];
          _afRun(); 'ok'""")  # חישוב ראשון
    wait("_af.runs.length === 1 && _af.runs[0].status === 'running'")  # רץ
    js("_afRun(); 'ok'")  # חישוב שני בזמן שהראשון רץ
    check("חישוב שני לא מבטל את הראשון — שניהם רצים", wait("_af.runs.length === 2 && _af.runs.every(function(r){ return r.status === 'running'; })"), str(js("JSON.stringify(_af.runs.map(function(r){ return r.status; }))")))  # שניהם רצים
    check("לא נשלח ביטול לשרת", not js("__calls.some(function(c){ return c.indexOf('/cancel') >= 0; })"))  # בלי ביטול
    check("כפתור החישוב לא מנוטרל בזמן ריצה", js("!_af.els.run.disabled") is True)  # אפשר להתחיל עוד
    js("__jobs.J1.state = 'done'; 'ok'")  # הראשון מסתיים
    check("הראשון הסתיים, השני עדיין רץ", wait("_af.runs[0].status === 'done' && _af.runs[1].status === 'running'"))  # מצב
    check("התוצאה של הראשון מוצגת (סיכום + מסלולים במפה)", wait("_af.cur === _af.runs[0] && _af.els.info.textContent.indexOf('4 מתוך 4') >= 0 && _af.runs[0].layers.paths.getLayers().length > 0"), str(js("_af.els.info.textContent.slice(0,60)")))  # תוצאה 1
    js("__jobs.J2.state = 'done'; 'ok'")  # השני מסתיים
    check("השני הסתיים ונבחר; המסלולים של שניהם על המפה", wait("_af.runs[1].status === 'done' && _af.cur === _af.runs[1] && map.hasLayer(_af.runs[0].layers.paths) && map.hasLayer(_af.runs[1].layers.paths) && _af.runs[0].layers.paths.getLayers().length > 0 && _af.runs[1].layers.paths.getLayers().length > 0"))  # שניהם במפה
    check("הסיכום של השני (5 מסלולים)", js("_af.els.info.textContent.indexOf('5 מתוך 5') >= 0") is True, str(js("_af.els.info.textContent.slice(0,60)")))  # סיכום 2
    js("_afSelectRun(_af.runs[0]); 'ok'")  # בחירה מהרשימה
    check("בחירה מהרשימה מחליפה את הסיכום לראשון", wait("_af.cur === _af.runs[0] && _af.els.info.textContent.indexOf('4 מתוך 4') >= 0"))  # בחירה
    js("_af.runs[1].layers.paths.getLayers()[0].fire('click'); 'ok'")  # לחיצה על מסלול של השני
    check("לחיצה על מסלול של חישוב אחר בוחרת אותו", wait("_af.cur === _af.runs[1] && _af.runs[1].layers.sel.getLayers().length === 1"))  # בחירה דרך מסלול
    js("_af.runs[0].row.el.querySelector('input').click(); 'ok'")  # הסתרת הראשון
    check("הסתרת חישוב מסירה רק אותו מהמפה", wait("!map.hasLayer(_af.runs[0].layers.paths) && map.hasLayer(_af.runs[1].layers.paths)"))  # הסתרה
    js("_afRun(); 'ok'")  # חישוב שלישי
    wait("_af.runs.length === 3 && _af.runs[2].status === 'running'")  # רץ
    check("חישוב חדש בזמן שתוצאה מוצגת — הסיכום המוצג לא מתחלף", js("_af.cur === _af.runs[1]") is True)  # לא מפריע
    js("_afCancelRun(_af.runs[2]); 'ok'")  # ביטול השלישי
    check("ביטול חישוב אחד: נשלח ביטול רק עבורו, האחרים נשארים", wait("_af.runs[2].status === 'cancelled'") and js("__calls.filter(function(c){ return c.indexOf('/cancel') >= 0; }).length === 1 && __calls.filter(function(c){ return c.indexOf('/cancel') >= 0; })[0].indexOf('J3') >= 0 && _af.runs[0].status === 'done' && _af.runs[1].status === 'done'") is True)  # ביטול
    js("_afRemoveRun(_af.runs[1]); 'ok'")  # הסרת הנבחר
    check("הסרת החישוב הנבחר: יורד מהמפה, אחר נבחר במקומו", wait("_af.runs.length === 2 && _af.cur === _af.runs[0] && _af.els.info.textContent.indexOf('4 מתוך 4') >= 0") and js("document.querySelectorAll('#map *').length > 0") is True)  # הסרה
    run_radial()  # 28/11: שלב 2 — רדיוס ראייה רדיאלי
    run_doppler()  # 28/11: שלב 3 — דופלר מכ"ם
    errs = js("JSON.stringify(window.__errs || [])")  # שגיאות JS
    check("אין שגיאות JavaScript", errs in ("[]", None), str(errs))  # קונסולה


def run_radial():  # 28/11: רדיוס ראייה — שני חישובים במקביל, הזזת צופה לא מבטלת, ביטול/הסרה/Undo לחישוב אחד
    js("""_rsActivate(''); _afSetMode(false); toggleRadialLos();
          map.fire('click', {latlng: L.latLng(31.25, 34.79), originalEvent: {}}); _runRadialLos(); 'ok'""")  # צופה + חישוב ראשון
    wait("_radialRuns.length === 1 && _radialRuns[0].status === 'running'")  # רץ
    js("map.fire('click', {latlng: L.latLng(31.40, 34.90), originalEvent: {}}); _runRadialLos(); 'ok'")  # צופה חדש + חישוב שני בזמן שהראשון רץ
    check("רדיאלי: הצבת צופה חדש והפעלה נוספת לא מבטלות את הראשון", wait("_radialRuns.length === 2 && _radialRuns.every(function(r){ return r.status === 'running'; })") and not js("__calls.some(function(c){ return c.indexOf('/los_radial/cancel') >= 0; })"), str(js("JSON.stringify(_radialRuns.map(function(r){ return r.status; }))")))  # שניהם רצים
    js("__jobs[_radialRuns[0].jobId].state = 'done'; 'ok'")  # הראשון מסתיים
    check("רדיאלי: הראשון צויר בשכבה שלו, השני עדיין רץ", wait("_radialRuns[0].status === 'done' && _radialRuns[0].layer.getLayers().length > 4 && map.hasLayer(_radialRuns[0].layer) && _radialRuns[1].status === 'running'"))  # תוצאה 1
    js("__jobs[_radialRuns[1].jobId].state = 'done'; 'ok'")  # השני מסתיים
    check("רדיאלי: שתי התוצאות על המפה יחד", wait("_radialRuns[1].status === 'done' && map.hasLayer(_radialRuns[0].layer) && map.hasLayer(_radialRuns[1].layer) && _radialRuns[1].layer.getLayers().length > 4"))  # שתיהן
    js("_performUndo(); 'ok'")  # Undo — הפונקציה של כפתור הביטול במפה
    check("רדיאלי: Undo מסתיר רק את התוצאה האחרונה", wait("!map.hasLayer(_radialRuns[1].layer) && map.hasLayer(_radialRuns[0].layer)"))  # Undo
    js("_runRadialLos(); 'ok'")  # שלישי
    wait("_radialRuns.length === 3 && _radialRuns[2].status === 'running'")  # רץ
    js("_cancelRadialRun(_radialRuns[2]); 'ok'")  # ביטול השלישי
    check("רדיאלי: ביטול חישוב אחד שולח ביטול רק עבורו", wait("_radialRuns[2].status === 'cancelled'") and js("__calls.filter(function(c){ return c.indexOf('/los_radial/cancel') >= 0; }).length === 1 && map.hasLayer(_radialRuns[0].layer)") is True)  # ביטול
    js("_removeRadialRun(_radialRuns[0]); 'ok'")  # הסרת הראשון
    check("רדיאלי: הסרה מורידה מהמפה ומהרשימה", wait("_radialRuns.length === 2 && _radialRunsEl.children.length === 2"))  # הסרה
    js("toggleRadialLos(); 'ok'")  # כיבוי הכלי
    check("רדיאלי: כיבוי הכלי מנקה את כל החישובים", wait("_radialRuns.length === 0"))  # כיבוי


def run_doppler():  # 28/11: דופלר — שתי סריקות והערכת מסלול במקביל, הזזת צופה לא מבטלת, סגירת הפאנל עוצרת בלי למחוק
    js("""toggleRadarDoppler(); map.fire('click', {latlng: L.latLng(31.25, 34.79), originalEvent: {}}); _runRadarDoppler(); 'ok'""")  # צופה + סריקה ראשונה
    wait("_radarRuns.length === 1 && _radarRuns[0].status === 'running'")  # רצה
    js("""map.fire('click', {latlng: L.latLng(31.35, 34.85), originalEvent: {}}); _runRadarDoppler();
          _lastFlightRouteData = {trail: [{lat: 31.3, lng: 34.8}, {lat: 31.32, lng: 34.83}], aircraft: 'B738', aircraft_icao: 'B738', flight: 'TST1'};
          _runRouteEvaluation(); 'ok'""")  # סריקה שנייה + הערכת מסלול
    check("דופלר: סריקה שנייה והערכת מסלול רצות יחד עם הראשונה", wait("_radarRuns.length === 3 && _radarRuns.every(function(r){ return r.status === 'running'; }) && _radarRuns[2].kind === 'route_eval'") and not js("__calls.some(function(c){ return c.indexOf('/radar_doppler/cancel') >= 0; })"), str(js("JSON.stringify(_radarRuns.map(function(r){ return r.kind + ':' + r.status; }))")))  # שלושה רצים
    js("_radarRuns.forEach(function(r){ __jobs[r.jobId].state = 'done'; }); 'ok'")  # כולם מסתיימים
    check("דופלר: שלוש התוצאות על המפה יחד (שתי סריקות + מסלול)", wait("_radarRuns.every(function(r){ return r.status === 'done' && map.hasLayer(r.layer) && r.layer.getLayers().length > 0; })"))  # כולן
    check("דופלר: שורת הסיכום של הערכת המסלול כוללת RCS וכלי טיס", "B738" in (js("_radarRuns[2].note") or ""), str(js("_radarRuns[2].note")))  # פרטי הערכה
    js("_runRadarDoppler(); 'ok'")  # רביעית
    wait("_radarRuns.length === 4 && _radarRuns[3].status === 'running'")  # רצה
    js("toggleRadarDoppler(); 'ok'")  # סגירת הפאנל
    check("דופלר: סגירת הפאנל עוצרת את מה שרץ ולא מוחקת תוצאות", wait("_radarRuns[3].status === 'cancelled'") and js("_radarRuns.length === 4 && map.hasLayer(_radarRuns[0].layer) && map.hasLayer(_radarRuns[2].layer)") is True)  # עצירה בלי מחיקה
    js("_clearRouteEvaluation(); 'ok'")  # ניקוי מסלול הטיסה
    check("דופלר: ניקוי מסלול הטיסה מסיר רק את הערכות המסלול", wait("_radarRuns.length === 3 && _radarRuns.every(function(r){ return r.kind === 'scan'; })"))  # הערכות בלבד
    js("clearRadarDopplerResult(); 'ok'")  # איפוס
    check("דופלר: איפוס מנקה את כל החישובים", wait("_radarRuns.length === 0"))  # איפוס


def main():  # הפעלה
    view.load(QUrl.fromLocalFile(HTML))  # טעינה
    QTimer.singleShot(0, lambda: (run(), print(f"\n{ok[0]}/{ok[0] + ok[1]} passed"), app.exit(1 if ok[1] else 0)))  # התרחיש
    sys.exit(app.exec_())  # לולאה


if __name__ == "__main__":  # הרצה ישירה
    main()  # התחלה
