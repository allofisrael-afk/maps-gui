"""F-014: ANOTHER_API_KEY (קיים ב-.env.example) לא נכלל ב-security_checks._SECRET_ENV_VARS -
משמעות: אם המפתח הזה ידלוף בתגובת-שרת, הכלי הפנימי לא יזהה זאת. 0 רשת/שינוי-production."""
import os
import sys

_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')  # Q-6: tests/ - רמה אחת למעלה, לא שתיים
sys.path.insert(0, _PROJECT_ROOT)

import security_checks  # noqa: E402

if "ANOTHER_API_KEY" in security_checks._SECRET_ENV_VARS:
    print("[OK] F-014: ANOTHER_API_KEY כלול ברשימת-הסריקה - הפער נסגר.")
    sys.exit(0)
else:
    print(f"[FAIL] F-014 משוחזר: ANOTHER_API_KEY חסר מ-_SECRET_ENV_VARS "
          f"(כרגע: {security_checks._SECRET_ENV_VARS}).")
    sys.exit(1)
