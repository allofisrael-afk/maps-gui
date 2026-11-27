# תוכנית עבודה לתיקון — ריצת QA 5

נבנתה מההחלטות שנתת סעיף אחר סעיף (26/11/2026). מקור: `.qa/findings.xlsx` (גיליון 'תוכנית עבודה'). **שום שינוי לא בוצע עדיין — ממתין לאישור התוכנית.**

## סיכום ההחלטות

| ממצא | החלטה | עדיפות | הערה |
|---|---|---|---|
| F-031 | לפי ההמלצה | 1 דחוף | א' (CORS מוגבל) מיד, ואחריו ב' (טוקן לכל הפעלה). |
| F-033 | חלופה ב | 1 דחוף | כתיבה אטומית + גיבוי .bak. |
| F-032 | לפי ההמלצה | 2 רגיל | א'+ב': isfinite בקליטה + תקרת איטרציות בלולאת הסריקה. |
| F-034 | לא לתקן | — | סיכון מאושר: הדסקטופ לא מופץ (D1). F-025 נשאר פתוח. |
| F-035 | חלופה ג | — | להשאיר את saved_stations.json ב-git. ה-repo ציבורי (Q-R5-3) — סיכון מאושר. |
| F-036 | חלופה א | 1 דחוף | הבהרה בולטת בבורר ובמסך אודות. מומלץ ייעוץ משפטי לפני הפצה ציבורית. |
| F-037 | חלופה א | 1 דחוף | א'+ב': תבניות חדשות + תקרת אורך/תבנית קבועה. |
| F-038 | חלופה ב | — | להשאיר חתימת debug. |
| F-039 | לא לתקן | — | cleartext נשאר. |
| F-040 | חלופה א | 2 רגיל | min-height 24px (CSS). |
| F-041 | חלופה א | 2 רגיל | תווית טקסטואלית דינמית לכל גרף (דסקטופ + אנדרואיד). |
| F-042 | חלופה א | 2 רגיל | תקרת גודל בקשה + שם ≤100 + params ≤64KB. |
| F-043 | חלופה ב | 2 רגיל | מאגר threads קבוע עם תור (שרת + radar_android). |
| F-051 | לפי ההמלצה | 2 רגיל | א'+ב'+ג': oracle מוחלט, גבולות דופלר, ייחוס lobing. |
| F-044 | לפי ההמלצה | 3 בהמשך | — |
| F-045 | לפי ההמלצה | 3 בהמשך | — |
| F-046 | לפי ההמלצה | 3 בהמשך | — |
| F-047 | לפי ההמלצה | 1 דחוף | ⚠️ — הוצאת קבצי .dart_tool/.flutter-plugins מהמעקב + החרגה (שינוי .gitignore באישורך). .claude/settings.json ו-CLAUDE_PROMPT_NEW_CONVERSATION.md — לבירור. |
| F-048 | לפי ההמלצה | 3 בהמשך | — |
| F-049 | לפי ההמלצה | 3 בהמשך | — |
| F-050 | לפי ההמלצה | 3 בהמשך | — |

**לא יתוקנו (סיכון מאושר):** F-034 (חבילות פגיעות, הדסקטופ לא מופץ), F-035 (מיקום ב-git, repo ציבורי), F-038 (חתימת debug), F-039 (cleartext), F-009 (debug=True).

**תשובות לשאלות:** Q-R5-1 להשאיר · Q-R5-2 הבהרה בולטת · Q-R5-3 ה-repo ציבורי · Q-R5-4 התאמה חלקית (בלי יעד L1 פורמלי) · Q-R5-5 הייחוס מאושר · העברת הבדיקות ל-tests/ מאושרת.

**השפעת התשובות:** Q-R5-4 מוריד את יעד האבטחה ל'התאמה חלקית', ולכן F-034 ו-F-009 לא חוסמים יעד. Q-R5-3 משאיר את F-035/F-047 בחומרה גבוהה/נמוכה כפי שדווחו.

## משימות לפי סדר ביצוע

| משימה | ממצאים | חלופה | קבצים | שינוי | היקף | עדיפות | תלוי ב- | אימות | APK |
|---|---|---|---|---|---|---|---|---|---|
| T0 | תשתית | העברת בדיקות (אושר) | tests/ (חדש: 3 קבצים), tests/run_regression.py | העברת test_r5_server_security / test_r5_radar_algorithmic / test_r5_wa_sanitize ל-tests/ (+golden). שורות REPRO → BUG_REPRO_TESTS. | קטן | 1 | — | run_regression ירוק; REPRO מדווחים 'פתוח' | לא |
| T1 | F-036 ⚠️ | א' | MAP.py (_rtBuildActiveBar), radar_track_panel.dart (ActiveProfileBar), lib/legal/about.dart | שורת הבהרה: 'שמות מוצרים שייכים לבעליהם; אין קשר/אישור; ערכים משוערים מנתונים פומביים'. | קטן | 1 | — | render דסקטופ (הטקסט מוצג), flutter analyze | כן |
| T2 | F-047 ⚠️ | א' | .gitignore, git rm --cached (maps-gui-android-src/.dart_tool/, .flutter-plugins-dependencies) | הוצאת קבצים מיוצרים מהמעקב והחרגה. לא נוגעים ב-.claude/settings.json (לבירור). | קטן | 1 | — | git grep לנתיבים מקומיים = 0 בקבצים מיוצרים | לא |
| T3 | F-037 ⚠️ | א'+ב' | wa-status/wa_status.py (sanitize) | תבניות: טלפון, אימייל, קואורדינטות, AKIA…, eyJ…; תקרת אורך גוף ההודעה. | קטן | 1 | T0 | test_r5_wa_sanitize: 0 דליפות | לא |
| T4 | F-031 | א' | server_common.py (create_app) | CORS רק למקורות הממשק (Origin null/file של QtWebEngine — לאמת קודם). | קטן | 1 | T0 | REPRO-CORS → נסגר; render מלא (כל ה-fetch עובדים) | לא |
| T5 | F-031 | ב' | main.py, MAP.py (עטיפת fetch), server_common.py (before_request) | טוקן אקראי לכל הפעלה, נדרש בכותרת X-App-Token. | בינוני | 1 | T4 | render מלא + בקשה בלי טוקן = 403 | לא |
| T6 | F-033 | ב' | weather_server.py (_save_stations/_load_stations) | כתיבה ל-.tmp + os.replace; גיבוי .bak; טעינה מה-.bak אם הראשי פגום. | קטן | 1 | T0 | REPRO-ATOMIC → נסגר; test_radar_service | לא |
| T7 | F-032 | א'+ב' | radar_service.py (_clamp_getter), radar_physics.py (_parse_radar_common_params), radar_track.py (scan_opportunities) | math.isfinite → ברירת מחדל; תקרת איטרציות בלולאות. | קטן | 2 | T0 | fuzz_r5_nan_params: 0 HANG / 0 EXC; Golden Master | לא (Python ב-APK מתעדכן בבנייה הבאה) |
| T8 | F-042 | א' | weather_server.py | MAX_CONTENT_LENGTH + שם ≤100 + params ≤64KB. | קטן | 2 | T6 | REPRO-SIZE → נסגר; מסלול 6000 נקודות עדיין עובר | לא |
| T9 | F-043 | ב' | weather_server.py (jobs), radar_android.py (_start) | ThreadPoolExecutor קבוע עם תור; סטטוס 'queued'. | בינוני | 2 | T8 | REPRO-JOBS → נסגר; test_radar_service, test_radar_android, ביטול job בתור | כן (radar_android) |
| T10 | F-051 | א'+ב'+ג' | tests/test_radar_physics.py | oracle מוחלט (TPQ-36 = 18,000 מ'), גבולות דופלר, ייחוס lobing. | קטן | 2 | — | ast_mutate: ציון ≥ 80% | לא |
| T11 | F-040 | א' | MAP.py (CSS כפתורים) | min-height/min-width 24px לכפתורים שנמצאו. | קטן | 2 | — | ui_r5_visual_and_controls: tiny=0; עדכון baseline חזותי באישורך | לא |
| T12 | F-041 | א' | MAP.py (4 canvas), radar_track_panel.dart (Semantics) | role=img + aria-label דינמי; Semantics באנדרואיד. | קטן | 2 | — | בדיקת DOM ל-aria-label; flutter analyze | כן |
| T13 | F-044 | א' | radar_track.py (normalize_trajectory), radar_service.py | דחיית קואורדינטות מחוץ לטווח. | קטן | 3 | T7 | REPRO-RANGE → נסגר | לא |
| T14 | F-045 | א' | weather_server.py | ruff --fix F401; HTTPError רק בסעיף אחד. | קטן | 3 | T9 | ruff F401/B025 = 0; test_requests_mocked | לא |
| T15 | F-046 | א' | rocket_model.py | ברירת מחדל geo_direct = mpm.geodesy.direct. | קטן | 3 | — | REPRO-ROCKET-GEO → נסגר; test_rocket_model | לא |
| T16 | F-048 | א' | weather_server.py, radar_android.py | הודעה אחידה בעברית לכשל רשת. | קטן | 3 | T14 | סימולציית offline (שרת + מתאם) | כן |
| T17 | F-049 | א' | android_MainActivity.kt, radar_track_controller.dart | תקרת גודל ב-openText; מאגר {'v':1,'profiles':{…}} עם מיגרציה. | קטן | 3 | — | flutter analyze; בדיקה על מכשיר (חסום) | כן |
| T18 | F-050 | א' | tests/README.md | שורה לכל חבילת מכ"ם (וגם לחבילות שהועברו ב-T0). | קטן | 3 | T0 | — | לא |
| T19 | תיעוד | חובה (כללי הפרויקט) | MAPS-GUI_SRS.md, MAPS-GUI_README.md, docs/DEPENDENCIES.md (אם רלוונטי) | FR-D חדש לכל תיקון. | קטן | 3 | כל המשימות | — | לא |
| T20 | בניית APK | דורש אישור מפורש נפרד | build_apk.ps1 | בנייה אחת שמכילה את T1, T7, T9, T12, T16, T17. | — | 3 | T1,T7,T9,T12,T16,T17 | התקנה על מכשיר (חסום עד מכשיר) | כן |

**אפשר במקביל:** T1, T2, T3, T10, T11, T12, T15 (קבצים נפרדים). **ברצף בגלל אותו קובץ:** T6 → T8 → T9 → T14 → T16 (weather_server.py); T7 → T13 (radar_service/radar_track); T4 → T5.

## סיכונים

| משימה | מה עלול להישבר | איך זה ייבדק |
|---|---|---|
| T4/T5 | אם QtWebEngine שולח Origin שונה מהצפוי, כל ה-fetch בממשק ייחסמו | בודקים את ה-Origin בפועל לפני השינוי; render מלא של כל הכלים אחרי |
| T9 | שינוי מחזור החיים של jobs (תור) עלול לשבור ביטול/סטטוס | test_radar_service, test_radar_android, ביטול job בתור ובריצה |
| T7/T13 | דחיית ערכים שהיו מתקבלים קודם | Golden Master + 70 בדיקות radar_track |
| T8 | תקרת גודל גלובלית עלולה לחסום מסלולים ארוכים | בדיקה עם 6000 נקודות (הגבול הקיים) |
| T6 | קובץ .bak נוסף בתיקייה (ו-git?) | להחריג *.bak או לשמור מחוץ ל-repo — יוצג לפני ביצוע |

## אבני דרך

- **M1** (אחרי T0–T6): כל ה-⚠️ והקריטיים; רגרסיה מלאה + render + REPRO של CORS/ATOMIC נסגרים
- **M2** (אחרי T7–T12): גבוה/בינוני; fuzz NaN נקי, mutation ≥80%, ui tiny=0, Golden Master
- **M3** (אחרי T13–T19): נמוכים + תיעוד; רגרסיה מלאה + כל .qa/run5/tests
- **M4** (T20): בניית APK — רק באישור מפורש; flutter analyze 0 שגיאות

## מצב צפוי בסיום
- **ייסגרו 17 ממצאים:** F-031, F-032, F-033, F-036, F-037, F-040, F-041, F-042, F-043, F-044, F-045, F-046, F-047 (קבצים מיוצרים), F-048, F-049, F-050, F-051.
- **אבטחה (התאמה חלקית):** כל ה-REPRO של השרת נסגרים (CORS, NaN, אטומיות, גודל, jobs, טווח). נשארים בסיכון מאושר: F-034, F-009.
- **נגישות (WCAG 2.x AA):** הבדיקות האוטומטיות עוברות (tiny=0, חלופה לגרפים). קורא מסך — עדיין דורש בדיקה ידנית.
- **פרטיות:** F-037 נסגר; F-035 נשאר בהחלטתך.
- **איכות הבדיקות:** mutation ≥ 80% ב-radar_physics; החבילות החדשות חלק מהרגרסיה הקבועה.

## לבירור

- F-047: האם לגעת ב-.claude/settings.json (נתיבים מקומיים בהרשאות של Claude Code) וב-CLAUDE_PROMPT_NEW_CONVERSATION.md? ההמלצה: להשאיר את settings, ולהחליף נתיבים בקובץ הפרומפט.
- F-036: ייעוץ משפטי לגבי שמות מסחריים ובקרת יצוא — מחוץ לתוכנית הקוד.
- F-009 (debug=True) נשאר לפי החלטתך. אחרי T4/T5 אתר זר כבר לא יוכל להגיע לדף ה-debug, ולכן הסיכון יורד משמעותית.
- T11 משנה את המראה — צילומי הייחוס יעודכנו רק אחרי שתאשר את המראה החדש.

## אישור
אפשר לאשר את כל התוכנית או חלק ממנה (למשל רק M1). בגיליון 'תוכנית עבודה' יש עמודת 'לאשר?' (כן / לא / לדיון). בניית APK (T20) תיעשה רק באישור מפורש נפרד.

## עדכון אחרי FR-D-288 (מכ"מים מוצבים, 27/11/2026)
- **T1 (F-036, הבהרה):** הבורר "פרופיל פעיל" הוחלף בבורר "מכ"ם פעיל" — הגלובלי, והפסים בכל כלי, בדסקטופ ובאנדרואיד. ההבהרה תיכנס לבורר הגלובלי (`_rsBuildGlobalBar` / `GlobalRadarBar`) ולמסך אודות.
- **T5 (F-031, טוקן):** נוספו קריאות fetch חדשות ב-MAP.py (`_rsSaveSite`, `_rsLoadSites`, `_rsImport`, `_rsClone`). עטיפת ה-fetch צריכה לכסות גם אותן.
- **T12 (F-041):** ללא שינוי.
- **צילומי ייחוס חזותיים (ריצה 5):** ישתנו בגלל הבורר הגלובלי. העדכון ייעשה רק באישורך.
- **F-042 (גודל):** חל גם על המפתח החדש `radar_sites`.
