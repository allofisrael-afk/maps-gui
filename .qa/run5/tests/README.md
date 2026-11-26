# חבילת הבדיקות של ריצת QA 5 (`.qa/run5/tests/`)

בדיקות שנכתבו בריצת QA 5, ולא שינו קוד ייצור. הן רצות מהשורש. פירוט ב-`../QA_REPORT_RUN5.md`, נספח יב'.

| קובץ | מה בודק | פייתון |
|---|---|---|
| `test_r5_server_security.py` | CORS, ולידציה, NaN, שמירה אטומית, גבולות, תקרת jobs. השורות שמסומנות `[REPRO-CONFIRMED]` משחזרות ממצא פתוח | `.venv` |
| `test_r5_radar_algorithmic.py` | תרחיש מייצג, ערכי ביניים, בדיקות אנליטיות, metamorphic, convergence, דטרמיניזם, Golden Master | `.venv` |
| `fuzz_r5_nan_params.py` | NaN ו-±Inf בכל פרמטר × 3 סוגי סריקה, עם timeout (מזהה HANG) | `.venv` |
| `test_r5_wa_sanitize.py` | מסנן הפרטיות של wa-status (hypothesis) | `.qa/.venv` |
| `ui_r5_visual_and_controls.py` | צילומי ייחוס, השוואה חזותית (סף 1%) ומלאי רכיבים | `.venv` (PyQt5) |

עדכון ייחוס (רק באישור): `--update-golden` / `--update-baseline`.
