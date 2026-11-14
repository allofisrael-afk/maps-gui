"""F-011: /radar_doppler/cancel (Web) לא מחזיר ערך - Flask זורק 500.
משחזר דרך Flask test_client (in-process WSGI, 0 רשת אמיתית) - לא דורש שרת חי/קריאות-חוץ.
צפוי להיכשל (מדגים את הבאג) עד שהתיקון המאושר יבוצע (הוספת return jsonify({'ok': True}))."""
import os
import sys

_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')  # Q-6: tests/ - רמה אחת למעלה, לא שתיים
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'web'))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'web', 'lib'))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'web', 'api'))

os.environ.setdefault('ALLOWED_ORIGIN', 'http://localhost')

try:
    import app as web_app  # web/app.py
except Exception as e:
    print(f"[BLOCKED] לא ניתן לייבא את web/app.py: {e}")
    sys.exit(2)

client = web_app.app.test_client()
resp = client.post('/radar_doppler/cancel?job_id=does-not-exist')

if resp.status_code == 200:
    print("[OK] F-011: /radar_doppler/cancel מחזיר 200 - הבאג תוקן.")
    sys.exit(0)
else:
    print(f"[FAIL] F-011 משוחזר: /radar_doppler/cancel החזיר {resp.status_code} (צפוי 200). "
          f"גוף: {resp.get_data(as_text=True)[:300]}")
    sys.exit(1)
