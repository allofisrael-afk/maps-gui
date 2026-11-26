# CLAUDE.md — maps-gui

## Language and decisions
- Address Israel only in Hebrew.
- When a decision of his is needed, first explain the relevant terms and what each option means for the result, then ask.

## Copyright and license policy
- Own code is All Rights Reserved. Holder: Israel Alalouf. Notice: "Copyright (c) 2024-2026 Israel Alalouf. All rights reserved."
- Every new source file I create gets the standard header (see LICENSE). Never add headers to third-party, vendored, generated or minified files.
- The project is distributed to others, so assume distribution obligations apply.

## Third-party dependency rules (mandatory)
Before adding or updating ANY library, package, CDN script, font, icon, image, sound, dataset, binary, code snippet or external API/service:
1. Verify its license from a primary source (package metadata, LICENSE file, vendor page). Never from memory.
2. Check it is compatible with an All Rights Reserved, distributed project.
3. Record it in docs/DEPENDENCIES.md (name, version, license, how it is used, obligations) and update THIRD_PARTY_NOTICES.md if it ships.
4. Honor attribution duties, including attribution controls that must stay visible in the UI.
5. For external services, read and follow the terms of service and usage policy (tile servers, APIs, Waze/Google links), including rate limits and attribution.

Do NOT add without asking Israel first: anything under GPL, AGPL or LGPL (explain the effect on the project first), any CC BY-SA, CC BY-NC or CC BY-ND item, anything with no license or an unverified license, anything marked non-commercial or personal-use only.

Never copy code from an external source (Stack Overflow, gists, blogs, other repos) without recording its license and author, and never paste in code that looks lifted from a library without checking.

When a dependency is updated, re-check its license: licenses sometimes change between versions.

## Project-specific license notes
- Desktop (PyQt5, GPL-3.0) is NOT distributed (decision D1 in docs/DEPENDENCIES.md). Distributing it requires a PySide6 (LGPL) migration or a Riverbank commercial license — ask first.
- Map and data attributions (OpenStreetMap, OpenTopoMap, Esri, CARTO, Open-Meteo, OpenWeather) must stay visible in MAP.py and in the Android map (SimpleAttributionWidget, not a collapsed control).
- The Android launcher icon lives in maps-gui-android-src/android_res and is copied by build_apk.ps1; never restore the Flutter logo.
- New Android-side bundled components (Gradle libraries, native libraries) must also be registered in maps-gui-android-src/lib/legal/about.dart, because Flutter only collects Dart package licenses automatically.

## עדכוני סטטוס לוואטסאפ (wa-status)

הכלי `wa-status/wa_status.py` שולח לוואטסאפ של המשתמש עדכונים חד-כיווניים על העבודה בריפו. מריצים אותו משורש הריפו.

**מתי לשלוח:**
- `start`: בתחילת משימה משמעותית.
  `python wa-status/wa_status.py send --type start --msg "<מה מתחיל>"`
- `done`: בסיום המשימה, עם התוצאה בקצרה.
- `error`: כשיש שגיאה שלא הצלחת לפתור.
- `blocked`: כשאתה ממתין להחלטה של המשתמש. מסבירים בקצרה על מה ההחלטה.
- **עדכון מחזורי:** אין לך טיימר. לכן בנקודות טבעיות בעבודה, אחרי כל צעד משמעותי, מריצים `python wa-status/wa_status.py check-interval`. אם הפלט הוא `yes`, שולחים `send --type progress` עם שורה על המצב. אם הפלט הוא `no`, לא שולחים.
- אם המשתמש מבקש סיכום של חלון זמן, למשל "מה נעשה ב-3 השעות האחרונות": `python wa-status/wa_status.py summary --since 3h`.

**איך לכתוב את ההודעות:**
- קצר: שורה או שתיים, עובדתי, בעברית.
- בלי סודות, טוקנים, מפתחות, תוכן `.env`, תוכן של קבצים רגישים ונתיבים מלאים.

**אם השליחה נכשלת:**
- ממשיכים לעבוד. לא עוצרים ולא מנסים שוב ושוב. הכלי מחזיר תמיד קוד יציאה 0 ורושם את הכשל ב-`wa-status/state/wa_status.log`.
- אם קיים הקובץ `wa-status/state/failed.flag`, מדווחים למשתמש **פעם אחת** בעברית בצ'אט שעדכוני הוואטסאפ הפסיקו, ושצריך להריץ `python wa-status/wa_status.py setup` מחדש. אחרי הדיווח ממשיכים לעבוד.

(ההוראות הקבועות, עברית בלבד והסבר לפני כל החלטה, כבר מופיעות למעלה תחת "Language and decisions".)

## Audit trail
- Re-run the license audit whenever dependencies change materially and before any release, APK build or public publishing.
