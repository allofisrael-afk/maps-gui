# -*- coding: utf-8 -*-
# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""בונה את .qa/findings_form.html - טופס-מילוי מקומי (לא published, dir='rtl', self-contained).
נתוני findings_data.py מוטמעים ישירות כ-JS object (לא fetch() נפרד) כדי שיעבוד גם כ-file://
בדפדפן בלי חסימות-CORS. 'שמור כ-JSON' מוריד קובץ JSON להעלאה חזרה לצ'אט.
הרצה: .venv/Scripts/python.exe .qa/build_findings_form.py (אין תלות-pip, stdlib בלבד)"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings_data import FINDINGS, SEVERITY_COLORS, OPEN_QUESTIONS, RUN_DECISIONS, by_severity  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "findings_form.html")

DATA = {
    "meta": {"date": "10/11/2026", "run_mode": "מלא (full), אוטונומי",
              "commit": "c1abf7a9 + FR-D-240 (תיקון production מאושר-בנפרד)"},
    "severity_colors": SEVERITY_COLORS,
    "findings": by_severity(),
    "open_questions": OPEN_QUESTIONS,
    "run_decisions": RUN_DECISIONS,
}
DATA_JSON = json.dumps(DATA, ensure_ascii=False)

HTML = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>טופס סימון ממצאים — maps-gui QA</title>
<style>
  :root {
    --bg: #f4f6f8; --card-bg: #ffffff; --ink: #1a1a1a; --muted: #6b7280;
    --accent: #1F4E79; --accent2: #2E74B5; --line: #d8dde3;
    --crit: #d32f2f; --high: #ed7d31; --med: #c99a00; --low: #808080;
    --edit-bg: #eaf2fb; --edit-border: #9fc3e8;
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Arial, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); }
  header { background:var(--accent); color:#fff; padding:18px 24px; position:sticky; top:0; z-index:20; }
  header h1 { margin:0 0 4px; font-size:20px; }
  header .meta { font-size:12.5px; color:#cfe0ef; }
  main { max-width: 980px; margin: 0 auto; padding: 20px 16px 140px; }
  .intro { background:#fff; border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin-bottom:20px; font-size:13.5px; line-height:1.7; }
  .intro b { color:var(--accent); }
  h2.section { font-size:17px; color:var(--accent); border-bottom:2px solid var(--accent); padding-bottom:6px; margin:28px 0 14px; }
  .card { background:var(--card-bg); border:1px solid var(--line); border-radius:10px; padding:16px 18px; margin-bottom:14px;
          border-right:6px solid var(--low); box-shadow: 0 1px 3px rgba(0,0,0,.05); }
  .card.sev-קריטי { border-right-color: var(--crit); }
  .card.sev-גבוה { border-right-color: var(--high); }
  .card.sev-בינוני { border-right-color: var(--med); }
  .card.sev-נמוך { border-right-color: var(--low); }
  .card-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
  .badge { display:inline-block; padding:2px 9px; border-radius:12px; font-size:11.5px; font-weight:bold; color:#fff; }
  .badge.cat { background:#e5e7eb; color:#374151; font-weight:normal; }
  .fid { font-weight:bold; font-size:14.5px; color:var(--accent); }
  .process { font-weight:bold; font-size:14px; }
  .legal { color:#c00000; font-weight:bold; }
  .field-row { font-size:13px; margin:4px 0; line-height:1.6; }
  .field-row .lbl { color:var(--muted); font-weight:bold; }
  .alts { margin-top:8px; padding:8px 10px; background:#fafafa; border-radius:6px; font-size:12.5px; }
  .alt { margin-bottom:6px; padding-bottom:6px; border-bottom:1px dashed #e0e0e0; }
  .alt:last-child { border-bottom:none; margin-bottom:0; }
  .rec { margin-top:8px; font-size:13px; background:#eef6ee; border-right:3px solid #4caf50; padding:6px 10px; border-radius:4px; }
  .inputs { display:flex; gap:10px; margin-top:12px; flex-wrap:wrap; align-items:flex-start; }
  .inputs > div { display:flex; flex-direction:column; gap:3px; }
  label.small { font-size:11.5px; color:var(--muted); }
  select, textarea, input[type=text] {
    font-family: inherit; font-size:13px; padding:6px 8px; border:1px solid var(--edit-border);
    border-radius:6px; background:var(--edit-bg); color:#000;
  }
  select { min-width:140px; }
  textarea { width:100%; min-height:44px; resize:vertical; }
  .notes-wrap { flex:1; min-width:220px; }
  .qcard .terms, .qcard .options { font-size:12.5px; margin:4px 0; }
  .qcard .rec { margin-top:6px; }
  footer.bar {
    position:fixed; bottom:0; right:0; left:0; background:#fff; border-top:2px solid var(--accent);
    padding:10px 20px; display:flex; align-items:center; gap:14px; z-index:30; box-shadow:0 -2px 8px rgba(0,0,0,.08);
    flex-wrap:wrap;
  }
  footer.bar button { cursor:pointer; font-size:13.5px; padding:9px 18px; border-radius:7px; border:none; font-weight:bold; }
  #saveBtn { background:var(--accent); color:#fff; }
  #loadBtn { background:#fff; color:var(--accent); border:1px solid var(--accent) !important; }
  #progress { font-size:12.5px; color:var(--muted); margin-right:auto; }
  #progress b { color:var(--accent); }
  #savedNote { font-size:11.5px; color:#2e7d32; }
  .toc { position:sticky; top:62px; z-index:10; background:#fff; border:1px solid var(--line); border-radius:8px;
         padding:8px 12px; font-size:12px; margin-bottom:14px; display:flex; gap:12px; flex-wrap:wrap; }
  .toc a { color:var(--accent2); text-decoration:none; }
  .toc a:hover { text-decoration:underline; }
</style>
</head>
<body>
<header>
  <h1>טופס סימון ממצאים — דוח QA/אבטחה maps-gui</h1>
  <div class="meta" id="metaLine"></div>
</header>
<main>
  <div class="intro">
    מלא/י את השדות הכחולים בכל כרטיס (<b>החלטה</b>, <b>עדיפות</b>, <b>הערות</b>) עבור כל ממצא, ענה/עני על 6 השאלות הפתוחות,
    וסמן/י אם לשנות החלטה כלשהי שהתקבלה אוטונומית בריצה. בסיום לחצ/י <b>"שמור כ-JSON"</b> למטה — הקובץ שיורד הוא מה שיש
    להעלות בחזרה בצ'אט. שינויים נשמרים אוטומטית בדפדפן (localStorage) כגיבוי — אבל רק קובץ ה-JSON שמורד הוא מה שמגיע אליי.
  </div>
  <div class="toc">
    <a href="#sec-findings">⇩ ממצאים (28)</a>
    <a href="#sec-questions">⇩ שאלות פתוחות (6)</a>
    <a href="#sec-decisions">⇩ החלטות בריצה (7)</a>
  </div>

  <h2 class="section" id="sec-findings">ממצאים</h2>
  <div id="findingsContainer"></div>

  <h2 class="section" id="sec-questions">שאלות פתוחות</h2>
  <div id="questionsContainer"></div>

  <h2 class="section" id="sec-decisions">החלטות שהתקבלו בריצה</h2>
  <div id="decisionsContainer"></div>
</main>

<footer class="bar">
  <div id="progress">התקדמות: <b id="progressCount">0</b>/__TOTAL__ ממולאים</div>
  <span id="savedNote"></span>
  <button id="loadBtn">טען JSON שמור קודם</button>
  <input type="file" id="loadFile" accept="application/json" style="display:none">
  <button id="saveBtn">💾 שמור כ-JSON</button>
</footer>

<script>
const DATA = __DATA_JSON__;
const LS_KEY = "maps_gui_qa_findings_draft_v1";

function el(tag, attrs, html) {
  const e = document.createElement(tag);
  if (attrs) for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function esc(s) { return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function renderFindingCard(f) {
  const card = el("div", {class: "card sev-" + f.severity, "data-finding-id": f.id});
  const head = el("div", {class:"card-head"});
  head.appendChild(el("span", {class:"fid"}, f.id));
  head.appendChild(el("span", {class:"badge", style:`background:#${DATA.severity_colors[f.severity]||'808080'}`}, f.severity));
  if (f.legal) head.appendChild(el("span", {class:"legal"}, "⚠️"));
  head.appendChild(el("span", {class:"badge cat"}, esc(f.category)));
  head.appendChild(el("span", {class:"process"}, esc(f.process)));
  card.appendChild(head);

  const rows = [
    ["תיאור", f.desc], ["צעדים לשחזור", f.repro], ["תוצאה צפויה", f.expected],
    ["תוצאה בפועל", f.actual], ["סטטוס", f.status], ["מיקום בקוד", f.location],
    ["דרישה / CWE", f.requirement], ["בדיקה משחזרת", f.test],
  ];
  for (const [lbl, val] of rows) {
    card.appendChild(el("div", {class:"field-row"}, `<span class="lbl">${esc(lbl)}:</span> ${esc(val)}`));
  }

  if (f.alts && f.alts.length) {
    const altsBox = el("div", {class:"alts"});
    const letters = ["א","ב","ג"];
    f.alts.forEach((a,i) => {
      altsBox.appendChild(el("div", {class:"alt"},
        `<b>חלופה ${letters[i]}: ${esc(a.name)}</b> — ${esc(a.desc)}<br>` +
        `<span class="lbl">יתרונות:</span> ${esc(a.pros)} &nbsp; <span class="lbl">חסרונות:</span> ${esc(a.cons)} &nbsp; <span class="lbl">היקף:</span> ${esc(a.scope)}`));
    });
    card.appendChild(altsBox);
  }
  card.appendChild(el("div", {class:"rec"}, `<b>המלצה:</b> ${esc(f.recommended)}`));

  const inputs = el("div", {class:"inputs"});
  const decWrap = el("div");
  decWrap.appendChild(el("label", {class:"small"}, "החלטה"));
  const decSel = el("select", {"data-field":"decision"});
  ["", "חלופה א","חלופה ב","חלופה ג","לפי ההמלצה","לא לתקן","לדיון"].forEach(o => {
    decSel.appendChild(el("option", {value:o}, o || "— בחר —"));
  });
  decWrap.appendChild(decSel);
  inputs.appendChild(decWrap);

  const priWrap = el("div");
  priWrap.appendChild(el("label", {class:"small"}, "עדיפות"));
  const priSel = el("select", {"data-field":"priority"});
  ["", "1 דחוף","2 רגיל","3 בהמשך"].forEach(o => {
    priSel.appendChild(el("option", {value:o}, o || "— בחר —"));
  });
  priWrap.appendChild(priSel);
  inputs.appendChild(priWrap);

  const notesWrap = el("div", {class:"notes-wrap"});
  notesWrap.appendChild(el("label", {class:"small"}, "הערות שלי"));
  const notesArea = el("textarea", {"data-field":"notes", placeholder:"טקסט חופשי..."});
  notesWrap.appendChild(notesArea);
  inputs.appendChild(notesWrap);

  card.appendChild(inputs);
  return card;
}

function renderQuestionCard(q) {
  const card = el("div", {class:"card qcard", "data-question-id": q.id});
  const head = el("div", {class:"card-head"});
  head.appendChild(el("span", {class:"fid"}, q.id));
  head.appendChild(el("span", {class:"process"}, esc(q.topic)));
  card.appendChild(head);
  card.appendChild(el("div", {class:"terms"}, `<span class="lbl">מונחים:</span> ${esc(q.terms)}`));
  card.appendChild(el("div", {class:"options"}, `<span class="lbl">אפשרויות:</span> ${esc(q.options)}`));
  card.appendChild(el("div", {class:"rec"}, `<b>המלצה:</b> ${esc(q.recommendation)}`));
  const inputs = el("div", {class:"inputs"});
  const wrap = el("div", {class:"notes-wrap"});
  wrap.appendChild(el("label", {class:"small"}, "התשובה שלי"));
  wrap.appendChild(el("textarea", {"data-field":"answer", placeholder:"טקסט חופשי..."}));
  inputs.appendChild(wrap);
  card.appendChild(inputs);
  return card;
}

function renderDecisionCard(d) {
  const card = el("div", {class:"card qcard", "data-decision-num": d.num});
  const head = el("div", {class:"card-head"});
  head.appendChild(el("span", {class:"fid"}, "#" + d.num));
  card.appendChild(head);
  card.appendChild(el("div", {class:"field-row"}, `<span class="lbl">החלטה:</span> ${esc(d.decision)}`));
  card.appendChild(el("div", {class:"field-row"}, `<span class="lbl">נימוק:</span> ${esc(d.rationale)}`));
  const inputs = el("div", {class:"inputs"});
  const changeWrap = el("div");
  changeWrap.appendChild(el("label", {class:"small"}, "לשנות?"));
  const changeSel = el("select", {"data-field":"change"});
  ["", "כן", "לא"].forEach(o => changeSel.appendChild(el("option", {value:o}, o || "— בחר —")));
  changeWrap.appendChild(changeSel);
  inputs.appendChild(changeWrap);
  const noteWrap = el("div", {class:"notes-wrap"});
  noteWrap.appendChild(el("label", {class:"small"}, "הערה"));
  noteWrap.appendChild(el("textarea", {"data-field":"note"}));
  inputs.appendChild(noteWrap);
  card.appendChild(inputs);
  return card;
}

function updateProgress() {
  let count = 0;
  document.querySelectorAll("[data-finding-id]").forEach(card => {
    const dec = card.querySelector('[data-field="decision"]');
    if (dec && dec.value) count++;
  });
  document.getElementById("progressCount").textContent = count;
}

function collectAnswers() {
  const findings = [];
  document.querySelectorAll("[data-finding-id]").forEach(card => {
    findings.push({
      id: card.getAttribute("data-finding-id"),
      decision: card.querySelector('[data-field="decision"]').value,
      priority: card.querySelector('[data-field="priority"]').value,
      notes: card.querySelector('[data-field="notes"]').value,
    });
  });
  const open_questions = [];
  document.querySelectorAll("[data-question-id]").forEach(card => {
    open_questions.push({
      id: card.getAttribute("data-question-id"),
      answer: card.querySelector('[data-field="answer"]').value,
    });
  });
  const run_decisions = [];
  document.querySelectorAll("[data-decision-num]").forEach(card => {
    run_decisions.push({
      num: card.getAttribute("data-decision-num"),
      change: card.querySelector('[data-field="change"]').value,
      note: card.querySelector('[data-field="note"]').value,
    });
  });
  return {
    generated_at: new Date().toISOString(),
    source: "findings_form.html",
    findings, open_questions, run_decisions,
  };
}

function applyAnswers(answers) {
  if (!answers) return;
  (answers.findings||[]).forEach(a => {
    const card = document.querySelector(`[data-finding-id="${a.id}"]`);
    if (!card) return;
    if (a.decision) card.querySelector('[data-field="decision"]').value = a.decision;
    if (a.priority) card.querySelector('[data-field="priority"]').value = a.priority;
    if (a.notes) card.querySelector('[data-field="notes"]').value = a.notes;
  });
  (answers.open_questions||[]).forEach(a => {
    const card = document.querySelector(`[data-question-id="${a.id}"]`);
    if (card && a.answer) card.querySelector('[data-field="answer"]').value = a.answer;
  });
  (answers.run_decisions||[]).forEach(a => {
    const card = document.querySelector(`[data-decision-num="${a.num}"]`);
    if (!card) return;
    if (a.change) card.querySelector('[data-field="change"]').value = a.change;
    if (a.note) card.querySelector('[data-field="note"]').value = a.note;
  });
  updateProgress();
}

function autosave() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(collectAnswers()));
    const n = document.getElementById("savedNote");
    n.textContent = "נשמר-אוטומטית בדפדפן " + new Date().toLocaleTimeString("he-IL");
  } catch (e) { /* localStorage עלול להיכשל ב-file:// בחלק מהדפדפנים - לא קריטי, יש JSON-export */ }
}

function restoreAutosave() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) applyAnswers(JSON.parse(raw));
  } catch (e) {}
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("metaLine").textContent =
    `תאריך: ${DATA.meta.date}  |  מצב ריצה: ${DATA.meta.run_mode}  |  נקודת ייחוס: ${DATA.meta.commit}`;

  const fc = document.getElementById("findingsContainer");
  DATA.findings.forEach(f => fc.appendChild(renderFindingCard(f)));

  const qc = document.getElementById("questionsContainer");
  DATA.open_questions.forEach(q => qc.appendChild(renderQuestionCard(q)));

  const dc = document.getElementById("decisionsContainer");
  DATA.run_decisions.forEach(d => dc.appendChild(renderDecisionCard(d)));

  restoreAutosave();
  updateProgress();

  document.body.addEventListener("input", () => { updateProgress(); autosave(); });
  document.body.addEventListener("change", () => { updateProgress(); autosave(); });

  document.getElementById("saveBtn").addEventListener("click", () => {
    const answers = collectAnswers();
    const blob = new Blob([JSON.stringify(answers, null, 2)], {type: "application/json"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "maps-gui-findings-answers.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
  });

  document.getElementById("loadBtn").addEventListener("click", () => {
    document.getElementById("loadFile").click();
  });
  document.getElementById("loadFile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try { applyAnswers(JSON.parse(reader.result)); autosave(); }
      catch (err) { alert("קובץ JSON לא תקין: " + err.message); }
    };
    reader.readAsText(file, "utf-8");
  });
});
</script>
</body>
</html>
"""

html_out = HTML.replace("__DATA_JSON__", DATA_JSON).replace("__TOTAL__", str(len(FINDINGS)))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html_out)
print(f"נכתב: {OUT}")
