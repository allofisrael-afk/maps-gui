# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — ממשק Desktop (map.html ב-QtWebEngine): צילומי ייחוס ל-Visual Regression (3 מסכים, 2 גדלי חלון),
השוואה לייחוס קיים (סף 1% פיקסלים שונים), ומלאי כפתורים: שם נגיש, מאזין, וכפתורים מחוץ לתצוגה. השרת המקומי
צריך לרוץ (5002) רק לרשימות; שום בקשה חיצונית לא נשלחת ע"י הבדיקה עצמה.
הרצה: .venv\\Scripts\\python.exe .qa/run5/tests/ui_r5_visual_and_controls.py [--update-baseline]"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PyQt5.QtCore import QTimer, QUrl  # noqa: E402
from PyQt5.QtGui import QImage  # noqa: E402
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VIS = os.path.join(HERE, "..", "visual")
os.makedirs(os.path.join(VIS, "baseline"), exist_ok=True)
os.makedirs(os.path.join(VIS, "current"), exist_ok=True)
MAP = r"D:\PY-IS\maps-gui\map.html"
UPDATE = "--update-baseline" in sys.argv
errors, report = [], {"screens": {}, "controls": None}


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, msg, line, src):
        if level >= 2:
            errors.append(f"{msg} (line {line})")


app = QApplication(sys.argv)
view = QWebEngineView()
page = Page(view)
view.setPage(page)
view.move(-3000, -3000)
view.show()

INVENTORY_JS = r"""(function(){
  var out = {total:0, no_name:[], hidden_offscreen:[], tiny:[]};
  var els = Array.from(document.querySelectorAll('button, a[role=button], [role=button], select, input'));
  els.forEach(function(el){
    var r = el.getBoundingClientRect(); var vis = el.offsetParent !== null;
    if (!vis) return;
    out.total++;
    var name = (el.getAttribute('aria-label') || el.title || el.textContent || (el.labels && el.labels[0] && el.labels[0].textContent) || el.placeholder || '').trim();
    if (!name && el.tagName !== 'INPUT') out.no_name.push(el.tagName + ':' + (el.className||'').toString().slice(0,30) + ':' + el.outerHTML.slice(0,80));
    if (el.tagName === 'INPUT' && !name && !(el.closest('label'))) out.no_name.push('INPUT:' + el.type + ':' + el.outerHTML.slice(0,80));
    if (r.right > window.innerWidth + 1 || r.bottom > window.innerHeight + 1) out.hidden_offscreen.push(el.tagName + ':' + (name||'').slice(0,30));
    if ((el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') && (r.width < 24 || r.height < 24)) out.tiny.push((name||el.outerHTML.slice(0,40)).slice(0,40) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  });
  out.no_name = out.no_name.slice(0, 25); out.tiny_count = out.tiny.length; out.tiny = out.tiny.slice(0, 15);
  out.hidden_offscreen = out.hidden_offscreen.slice(0, 15);
  return JSON.stringify(out);
})()"""

STEPS = [  # (שם מסך, JS להכנה, גודל חלון)
    ("map_default", "map.setView([31.3, 34.8], 9); 'ok'", (1000, 620)),
    ("radar_panel", "if (!radarActive) toggleRadarDoppler(); 'ok'", (1000, 620)),
    ("radar_panel_small", "'ok'", (800, 500)),
    ("ballistic_radar_tab", "if (radarActive) toggleRadarDoppler(); if (!ballisticsActive) _ballisticsSetActive(true); _ballisticsSelectTab('radar'); 'ok'", (1000, 620)),
]
state = {"i": 0}


def diff_ratio(a_path, b_path):
    a, b = QImage(a_path), QImage(b_path)
    if a.size() != b.size():
        return 1.0
    w, h, diff = a.width(), a.height(), 0
    for y in range(0, h, 2):  # דגימה כל פיקסל שני — מהיר מספיק
        for x in range(0, w, 2):
            pa, pb = a.pixel(x, y), b.pixel(x, y)
            if abs(((pa >> 16) & 255) - ((pb >> 16) & 255)) + abs(((pa >> 8) & 255) - ((pb >> 8) & 255)) + abs((pa & 255) - (pb & 255)) > 30:
                diff += 1
    return diff / ((w // 2) * (h // 2))


def next_step():
    if state["i"] >= len(STEPS):
        page.runJavaScript(INVENTORY_JS, done_inventory)
        return
    name, js, (w, h) = STEPS[state["i"]]
    view.resize(w, h)
    page.runJavaScript(js, lambda _r: QTimer.singleShot(3500, lambda: shoot(name)))


def shoot(name):
    cur = os.path.join(VIS, "current", name + ".png")
    view.grab().save(cur)
    base = os.path.join(VIS, "baseline", name + ".png")
    if UPDATE or not os.path.exists(base):
        view.grab().save(base)
        report["screens"][name] = "baseline-created"
    else:
        r = diff_ratio(base, cur)
        report["screens"][name] = f"diff={r:.4f} {'PASS' if r <= 0.01 else 'DIFF>1%'}"
    print(name, report["screens"][name])
    state["i"] += 1
    next_step()


def done_inventory(raw):
    report["controls"] = json.loads(raw)
    report["console_errors"] = errors
    with open(os.path.join(HERE, "..", "ui_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    c = report["controls"]
    print("controls visible:", c["total"], "| no accessible name:", len(c["no_name"]), "| tiny(<24px):", c["tiny_count"],
          "| off-screen:", len(c["hidden_offscreen"]))
    for x in c["no_name"][:10]:
        print("   no-name:", x)
    print("console errors:", errors or "none")
    QTimer.singleShot(300, app.quit)


view.loadFinished.connect(lambda ok: QTimer.singleShot(4000, next_step))
view.load(QUrl.fromLocalFile(MAP))
app.exec_()
