# QA Engagement — Progress (ריצה שלישית — נוסח-פרומפט מלא ומדויק, 10/11/2026)

## מצב ריצה
**מלא (full)** — אין ארגומנט מפורש, ברירת-מחדל. **אוטונומי** (לא `interactive`) — לפי "אל תעצור ואל תשאל שאלות במהלך הריצה".

## הקשר (שתי ריצות קודמות באותו יום)
1. ריצה ראשונה (נוסח-פרומפט מוקדם) — דוח+תוכנית-5-פריטים, **נמחקו** ע"י המשתמש (הפרו 2 מגבלות: venv לא-מבודד, קריאות-רשת-אמיתיות).
2. ניסיון שני (אחרי שהמשתמש סיפק נוסח-מעודכן) — ניסיתי לייצר DOCX גנרי מהדוח הקודם (npm docx-js) — **המשתמש ביטל**, כי זה לא תאם את הדרישה האמיתית (executive-summary.docx במבנה מדויק + md + xlsx).
3. **הריצה הנוכחית** — נוסח-פרומפט מלא ומדויק, כולל מבנה-מפורט ל-3 קבצי-הפלט.

## נקודת ייחוס לקוד
commit `c1abf7a9999cbf5805a8499ab822edd1918c2862` ("balistic version") + FR-D-240 (תיקון production מאושר-בנפרד ב-Stage 0, לא תוצר-QA).

## מה הושלם
- **Stage 0** — נעשה שימוש-חוזר (לא הורץ מחדש, החלטה אוטונומית מתועדת #1 בגיליון "החלטות בריצה").
- **Stage 1-4** — ניתוח-סיכונים, STRIDE, טולרנסים/דטרמיניזם, כלים-סטטיים (bandit/ruff/mypy/pip-audit ב-`.qa/.venv` מבודד), רגרסיה (`self_test.py`+`test_ballistics_api.py`, 20/20), **4 בדיקות-שחזור חדשות** ל-F-011/012/013/014 (כולן מדגימות-כשל כצפוי).
- **Stage 5 — שלושת הקבצים הושלמו ואומתו בפועל**:
  - `STAGE5_FINAL_REPORT.md` — הדוח המפורט.
  - `findings.xlsx` — 28 ממצאים (F-001…F-028) + 6 שאלות-פתוחות + 7 החלטות-ריצה. אומת: נפתח בהצלחה ב-Microsoft Excel אמיתי (COM), 5 גיליונות, RTL, dropdowns, locked/editable-columns תקינים.
  - `executive-summary.docx` — 3 עמודים. אומת: נפתח ב-Microsoft Word אמיתי (COM), הומר ל-PDF, נבדק חזותית (RTL נכון, טבלאות-RTL, גרף-matplotlib עם bidi תקין, צבעי-חומרה נכונים).

## התקנות-כלים (כולן ב-`.qa/.venv` המבודד, לפי המגבלה)
bandit, pip-audit, mypy, ruff (מהריצה הקודמת) + **openpyxl, python-docx, matplotlib, python-bidi** (חדשות בריצה הזו, נדרשות-במפורש לפי הפרומפט להפקת ה-Excel/Word/גרף).

## מה חסום
- `test_requests.py` — F-022/Q-3 (38/42 TestCase דורשים קריאות-רשת-אמיתיות, אין mock).
- Vercel dashboard/logs — F-007 (אין גישת-חשבון).
- מכשיר/אמולטור Android אמיתי.
- Mutation Testing/Fuzzing — F-023/Q-4 (כלים-חדשים+זמן, לא אושר).
- Visual Regression/axe-core/Lighthouse — Node/npm לא מותקן.
- maps-gui-secure/ — F-020/Q-2 (מעמד לא ברור, לא נחקר).

## שאלות פתוחות (מרוכזות ב-findings.xlsx, גיליון "שאלות פתוחות")
Q-1 יעד-נגישות | Q-2 מעמד maps-gui-secure/ | Q-3 mock-layer ל-test_requests.py | Q-4 Mutation/Fuzzing | Q-5 SBOM | Q-6 העברת .qa/tests/→tests/ הרגיל.

## תוספת: גרסאות HTML מקומיות (לפי בקשת המשתמש, אחרי הגשת שלושת הקבצים)
המשתמש ביקש חלופה מקומית (לא Artifact מתפרסם) ל-Excel+Word, לקריאות ולמילוי נוח יותר בדפדפן:
- **`findings_form.html`** — טופס-מילוי אינטראקטיבי (vanilla JS, 0 תלויות-חיצוניות, נתוני findings_data.py מוטמעים ישירות כ-JS object כדי לעבוד תחת `file://` בלי חסימות-CORS). כפתור "שמור כ-JSON" מוריד `maps-gui-findings-answers.json` — **זה הקובץ שהמשתמש יעלה בחזרה בצ'אט**. autosave ל-localStorage כגיבוי. כפתור "טען JSON" לשחזור-טיוטה. אומת ב-render חי (Chrome headless screenshot) — RTL תקין, 28 כרטיסי-ממצאים+6 שאלות+7 החלטות נטענו נכון, מונה-התקדמות עובד.
- **`executive-summary.html`** — גרסה מקומית קריאה-בלבד של סיכום-המנהלים (לא מחליפה את ה-docx, משלימה אותו). גרף-ה-severity_chart.png מוטמע כ-base64 כדי שהקובץ יהיה עצמאי-לחלוטין (ניתן-להעתקה כקובץ בודד). אומת ב-render חי — זהה-במהות ל-docx, מעוצב לקריאה בדפדפן.
- **רפקטור**: `OPEN_QUESTIONS`/`RUN_DECISIONS` הועברו מ-`build_findings_xlsx.py` (היו מוגדרים inline, משוכפלים) ל-`findings_data.py` כמקור-אמת יחיד — נצרכים כעת גם ע"י `export_data_json.py`, `build_findings_form.py`, ו-`build_executive_html.py`.

## Stage 6 — הושלם (11-12/11/2026)

המשתמש מילא את `findings_form.html`, החזיר `maps-gui-findings-answers.json`. תוך-כדי-קריאה התגלה ש-map.yechielalaluf.com (Web) ירד לגמרי ולא יוחזר — הופך F-004/005/006/007 ל-לא-רלוונטיים. תוכנית-תיקון מלאה נכתבה ואושרה (plan mode), ובוצעה בשלמותה:

- **שלב א' (תיקוני-קוד)**: F-011, F-012, F-014, F-015, F-016, F-019 תוקנו; F-013 אומת כ-false-positive (רק תיקון-בדיקה); תיקון-נוסף ש-RUN_DECISIONS #4 חייב — OpenWeatherMap HTTP→HTTPS ב-`weather_server.py`+`web/api/weather.py`. **אומת**: רגרסיה 2/2 + 4/4 בדיקות-שחזור התהפכו FAIL→PASS, bandit/ruff/mypy/pip-audit נקיים מחדש.
- **שלב ב' (ASVS 5.0 L1 פורמלי ל-Desktop)**: `.qa/asvs_l1_desktop_compliance.md` נכתב — 30 דרישות-L1 (מאומתות מהמקור הרשמי), 14 עומד / 13 לא-רלוונטי / 2 מגבלה-חיצונית / 1 נסגר-כתוצר-לוואי (מדיניות V15.1.1). 0 ממצאי-L1 פתוחים.
- **שלב ג' (F-022, mock-layer)**: `.qa/tests/test_requests_mocked.py` — 37/37 TEST_CASES עברו תחת mock מלא, 0 קריאות-רשת-אמיתיות (אומת גם ע"י מגן-socket). `test_requests.py`/`geo_server.py`/`flight_server.py` לא שונו.
- **שלב ד' (תיעוד)**: `MAPS-GUI_SRS.md` (FR-D-241…244), `MAPS-GUI_README.md` (§11), `.qa/findings_data.py`+`.qa/findings.xlsx` (סטטוס-הכרעה מפורש לכל 28 הממצאים + 7 החלטות-ריצה), `.qa/progress.md` (כאן).

**לא בוצע (לפי זיכרון-הפרויקט, לא התבקש)**: `git add`/`commit`/`push`. כל התיקונים קיימים רק ב-working-tree, מאומתים מקומית.

## צעד הבא (Stage 6)
Stage 6 סגור. שאלות-פתוחות שנותרו (Q-4/Mutation-Fuzzing, Q-5/SBOM) נדחו-מפורש לסבב עתידי. F-026/F-027 (חלק-Android, נגישות) נשארים ממצאי-המשך בעדיפות-נמוכה, לא אושרו בסבב הזה.

## ריצה רביעית — Stage 5 הושלם (12/11/2026)

**הקשר**: המשתמש הפעיל שוב את פרומפט ה-QA-engagement המלא, "לאחר שסיימת" (אחרי Stage 6). זו **לא** ריצת-מיפוי-מאפס — Stage 0 נעשה שימוש-חוזר (החלטת-ריצה #8), והריצה התמקדה באימות-בפועל (לא הנחה) של כל מה ש-Stage 6 טען, סריקה-סטטית-טרייה על כל העץ, והרצה-חזרתית-מרובה (8+ פעמים) של כל חבילת-הרגרסיה+המוק.

**תוצאה**: Stage 6 מאומת-לגמרי — כל 6 קבצי-production תואמים בדיוק את מה שתועד (`git diff` ישיר), הרגרסיה+37 בדיקות-המוק עברו בעקביות-מלאה בכל ריצה. ניתוח-סטטי טרי (bandit/ruff/mypy/pip-audit) **0 רגרסיה אמיתית** — ה"גידול" הגולמי ב-ruff (260→370) התפרק-ואומת כ-108 מתוכו הוא קוד-QA-tooling-חדש (לא היה קיים ב-baseline), לא production.

**2 ממצאים חדשים אמיתיים נמצאו** (שניהם על כלי-ה-QA עצמו, לא production):
- **F-029** (נמוך) — ראיה שגויה ב-`asvs_l1_desktop_compliance.md` (V13.4.1): נטען "0 routes מגישים קבצים-סטטיים" אך `web/app.py:51` עושה זאת (עם `send_from_directory`). המסקנה (עומד) נכונה בפועל מסיבה אחרת (שם-קובץ קבוע-בקוד) — טעות-ניסוח, לא כשל-אבטחה.
- **F-030** (בינוני) — `.qa/tests/run_regression.py` קורא `subprocess.run` בלי `timeout`. נמדדה שונות-זמן-ריצה גבוהה (47s/64s/87s, אחת חרגה מ-120s) על חבילה דטרמיניסטית-ללא-רשת — נבדק-ונפסל כל מקור-רשת-אמיתי (FR24 token-gated, Redis lazy-everywhere) — סביר תזמון-OS, לא קוד-נבדק. אך בלי timeout, תקיעה-אמיתית-עתידית לא תיתפס.

**תוצרים**: `STAGE5_FINAL_REPORT.md` נדרס (ריצה רביעית, כולל סעיף-אימות-Stage-6 + ניתוח-delta מדויק). `findings.xlsx`/`findings_data.py` עודכנו ל-**30 ממצאים** (F-029/F-030 חדשים) + **9 החלטות-ריצה** (#8/#9 חדשות, מתעדות את שיטת-האימות-הממוקד). `asvs_l1_desktop_compliance.md` **לא שונה** (F-029 מדווח-עליו, לא מתוקן — Stage 5 הוא דוח, לא תיקון). `executive-summary.docx/html` **לא עודכנו** (עדיין משקפים נכונה את 28 הממצאים המקוריים; הדיספוזיציות המעודכנות חיות ב-findings.xlsx/SRS).

**0 שינוי-production בריצה הזו** — לפי הפרומפט (Stage 5 = דוח בלבד). **0 commit/push** — ללא שינוי ממדיניות-הפרויקט.

## צעד הבא (ריצה רביעית)
ממתין שהמשתמש יסמן את `findings.xlsx` (בפרט F-029/F-030) ויחזיר אותו — Stage 6 הבא יתקן את שניהם (שני תיקונים טריוויאליים, המלצת-ברירת-המחדל: לתקן את שניהם) בתוספת לכל דבר אחר שיסומן.

## Stage 7 — תוכנית-עבודה חדשה לפי מילוי-תשובות (14/11/2026)

המשתמש מילא טופס-תשובות חדש על 30 הממצאים (לא חזרה על Stage 6 — כמה הכרעות חדשות הופכות פריטים שנדחו-במפורש ב-Stage 6 לעבודה מאושרת: F-021/F-023/F-024/F-026/F-027, והרחבת-יעד-נגישות קריטית ב-Q-1 ל-WCAG 2.x AA על Android **וגם** Desktop). תוכנית מלאה נכתבה ואושרה (plan mode, `C:\Users\allof\.claude\plans\compiled-gliding-wren.md`).

**הושלם עד כה (שלב א'+ב'+ה' מהתוכנית, בוצעו ע"י fork נפרד — Python בלבד)**:
- שלב א': F-021 (docstring MAP.py), F-029 (ניסוח-ראיה ב-asvs_l1_desktop_compliance.md), F-030 (`timeout=120` ל-subprocess.run), F-018-Desktop (`_schema_version` ל-saved_stations).
- שלב ב' (F-017, עדיפות-1-דחוף של המשתמש): 9 אתרי `except Exception` רחב צומצמו לסוגי-שגיאה ספציפיים ב-`weather_server.py`+`web/api/weather.py`. 10 אתרים אחרים (גבול-bridge ל-Android, 3 background-job safety-nets, כל קריאות-FlightRadar24API) נשארו כ-catch-all מוצדק, לפי בדיקה מוקדמת.
- **שלב ה' (Q-6 — הופכת ישירות את ההחלטה הקודמת של Stage 6): `.qa/tests/` הועבר במלואו ל-`tests/`** הראשית (`run_regression.py`, 4 בדיקות-F0xx, `test_requests_mocked.py`, `README.md`) — נתיבי-`PROJECT_ROOT` תוקנו בכל קובץ שהועבר. `.qa/tests/` לא קיים יותר. **מעכשיו: כל פקודת-הרצה מתייחסת ל-`tests/...`, לא `.qa/tests/...`** (למשל `python tests/run_regression.py`). היסטוריה קודמת ב-SRS/README וב-progress.md שלמעלה שמזכירה `.qa/tests/` נשארת כמו-שהיא בכוונה — מתארת נכון את המצב-שהיה-אז; FR-D חדש מלא לכל שינויי Stage 7 (כולל ההעברה הזו) יתועד בשלב ט' (סגירה) של התוכנית, לא כאן.
- **אומת**: רגרסיה 2/2 + 4/4 בדיקות-שחזור + 37/37 mock-tests — ירוק מלא מהמיקום החדש; bandit חזר נקי (רק F-009 הקיים-והמוכר, 0 חדש).

**הושלם — שלב ג' (Android, fork נפרד)**: F-010 (התראת-אחסון-לא-מוצפן, widget משותף, 3 פאנלים), F-018-Android (schema-version בנקודת-מחנק יחידה), F-026 (טרגטי-מגע ≥44×44 בכל האתרים מהתוכנית, padding/hit-box בלבד, 0 שינוי ויזואלי), F-027-Android (18 עטיפות `Semantics`). אומת: `flutter analyze` 0 חדש.

**הושלם — שלב ד' (Desktop accessibility, fork נפרד)**: `main.py` — ~23 `setAccessibleName()`, אומת חי. `MAP.py` — 12/16 בקרות-Leaflet קיבלו role/aria-label (54 aria-label, 29 role="button" ב-DOM, אומת חי). ⚠️ מגבלת-QtWebEngine-לקוראי-מסך תועדה במפורש (לא הונחה) ב-`asvs_l1_desktop_compliance.md` — "יושם, לא-מאומת", לא "עומד".

**הושלם — שלבים ו'-ח' (כלי-QA, fork נפרד)**: F-023 Mutation Testing חלקי (atmosphere.py בלבד, 7 שורדים+הצעת-תיקון; תקרית-timeout נמצאה-ותוקנה, mpm/ אומת-נקי). F-024 SBOM (שני קבצים, CycloneDX 1.6). F-028 דוח-FR24-licensing (MIT החבילה, אך ToS-FR24 אוסר scraping — accepted-risk בהקשר הפצה-מוגבלת).

**הושלם — שלב ט' (תיעוד וסגירה, ישירות)**: `.qa/findings_data.py` — כל 30 הממצאים עודכנו עם הכרעת-Stage-7 (22 תוקנו/נסגרו, 4 התייתרו-Web-ירד, 4 נשארו-פתוחים-באישור: F-001/F-008/F-023/F-025). F-006/F-009 ("לדיון") נסגרו-ללא-פעולה לפי פרק-לבירור של התוכנית. `findings.xlsx`/`findings_form.html`/`executive-summary.html` נרגנרו (האחרון תוקן גם מבחינת-לוגיקה — ניסוח "הצעד הבא" הפך data-driven לגמרי, לא רשימת-F-ID קשיחה שתתיישן בסבב הבא). `MAPS-GUI_SRS.md` (FR-D-245 עד FR-D-251), `MAPS-GUI_README.md` (§11) עודכנו.

**אימות-סופי עצמאי (לא רק דיווחי-forks)**: `git status`/`diff` אישרו שכל 4 ה-forks נשארו בתוך ה-scope שהוקצה להם (0 חפיפה/התנגשות). `tests/run_regression.py` הורץ ישירות — 2/2+4/4 ירוק. `py_compile` על כל קובצי-Python שנערכו. `maps-gui-android/` (עותק-build מיוצר) אומת זהה-בייט ל-`maps-gui-android-src/` (סנכרון-בלבד לצורך flutter-analyze, לא ערך-נוסף).

**0 git commit/push** (לפי מדיניות-הפרויקט — אישור נשאל בנפרד תמיד).

## צעד הבא (Stage 7)
Stage 7 סגור. 4 ממצאים נשארים פתוחים-באישור: F-001 (טוקן FR24, אין backend חליפי זמין), F-008 (NOTAM-scraping fragility, accepted-risk), F-023 (mutation testing חלקי — 2043 מוטנטים לא נוסו, ממצא-המשך לסבב עתידי אם רלוונטי), F-025 (lockfile, לא דחוף). שום פעולה נוספת לא נדרשת כרגע אלא אם המשתמש מסמן אחרת ב-`findings_form.html`/`findings.xlsx`.

## ריצה חמישית — full, אוטונומי (26/11/2026)
- **מצב ריצה**: full (אין ארגומנט), אוטונומי.
- **נקודת ייחוס**: HEAD `bfdd312da` + working tree לא-מחויב (FR-D-286/287: פרופיל פעיל, ELM-2311). ההשוואה היא לריצה 4 / Stage 7 (`2f693f7df`).
- **פיצול לפי סיכון (החלטה R5-1)**: Stage 0 של הקוד שלא השתנה מאז Stage 7 נלקח מחדש מ-stage0_*.md. כל העומק הולך ל-delta: radar_track/radar_placement/rocket_model/radar_physics/radar_service/radar_android, נקודות הקצה החדשות בשרת, ממשק המעקב (MAP.py + Android), wa-status, ספריית הפרופילים ו-saved_stations ב-git.
- **תוצרים**: `.qa/run5/` (דוח, כלים, בדיקות, צילומים) + `.qa/findings.xlsx` (נדרס, ריצה 5).
- **שלב נוכחי**: 0 (מיפוי delta).
- **התקדמות (ריצה 5)**: שלבים 0–4 בוצעו על ה-delta. בדיקות חדשות ב-`.qa/run5/tests/`: server_security (15 OK + 8 REPRO), radar_algorithmic (30/30, Golden Master + metamorphic), wa_sanitize (2/2 property, 5 דליפות), fuzz NaN (2 HANG), ui_visual (4 צילומי ייחוס). Flaky: 0/50. כיסוי ענפים radar: 90%. mutmut 2.5.1 חסום ב-Py3.14 → מוטטור ast עצמי (ריצה ברקע). חסום: mypy.exe (Application Control) → הורץ דרך `python -m mypy`; מכשיר Android/APK; axe/Lighthouse (אין Node).
- **צעד הבא**: תוצאות המוטציה → findings + דוח `.qa/run5/QA_REPORT_RUN5.md` + `.qa/findings.xlsx`.
- **Stage 5 הושלם (ריצה 5)**: `.qa/run5/QA_REPORT_RUN5.md` + `.qa/findings.xlsx` (21 ממצאים F-031…F-051, 5 שאלות, 8 החלטות; אומת ב-openpyxl וב-Excel אמיתי). הגיבוי של ריצה 4: `.qa/findings_run4.xlsx`. נקודת ייחוס סופית: `dea3a1b9d` (המשתמש עשה commit לאותו קוד במהלך הריצה). 0 שינוי בקוד ייצור.
- **צעד הבא (Stage 6)**: ממתין שהמשתמש יסמן את `.qa/findings.xlsx` ויחזיר אותו → תוכנית תיקון (`.qa/fix-plan.md` + גיליון "תוכנית עבודה").
- **Stage 6 (ריצה 5)**: ההחלטות נאספו סעיף אחר סעיף בשיחה ונכתבו ל-findings.xlsx (21/21). נבנו `.qa/fix-plan.md` + גיליון "תוכנית עבודה" (21 משימות T0–T20, 4 אבני דרך). **ממתין לאישור התוכנית** (כולה או חלק). בניית APK (T20) — רק באישור מפורש נפרד.
