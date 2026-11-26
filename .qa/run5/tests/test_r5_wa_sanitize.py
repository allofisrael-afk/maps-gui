# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — מסנן הפרטיות של wa-status (sanitize) לפני שליחה לוואטסאפ. בלי רשת ובלי neonize: רק הפונקציה.
דוגמאות קבועות (Error Guessing) + property-based (hypothesis): סוד שמוזרק לטקסט חופשי לא יוצא בפלט.
הרצה: .qa\\.venv\\Scripts\\python.exe .qa/run5/tests/test_r5_wa_sanitize.py"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location("wa_status", os.path.join(ROOT, "wa-status", "wa_status.py"))
wa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wa)  # הייבוא לא מתחבר לרשת (neonize נטען רק ב-deliver)

from hypothesis import given, settings, strategies as st  # noqa: E402

ok = fail = 0
leaks = []


def check(name, cond, info=""):
    global ok, fail
    ok += bool(cond); fail += (not cond)
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")


CASES = {  # (קלט, הסוד שאסור שיופיע בפלט)
    "token=": ("deploy with token=ghp_AbCdEf1234567890XyZ", "ghp_AbCdEf1234567890XyZ"),
    "API key:": ("api_key: sk-live-9f8e7d6c5b4a", "sk-live-9f8e7d6c5b4a"),
    "password =": ("password = hunter2!!", "hunter2!!"),
    ".env line": ("OPENWEATHER_API_KEY=abcd1234efgh", "abcd1234efgh"),
    "long hex": ("hash 3f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a done", "3f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a"),
    "win path": (r"saved C:\Users\allof\secret\keys.txt", r"C:\Users\allof"),
    "unix path": ("see /home/user/proj/.env now", "/home/user/proj"),
    "Bearer header": ("Authorization: Bearer abcDEF123456789xyzABC", "abcDEF123456789xyzABC"),
    "aws key id": ("aws AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE"),
    "short key in Hebrew sentence": ("המפתח הוא key=Xy12 בסדר", "Xy12"),
    "phone number": ("התקשר ל-972541234567", "972541234567"),
    "email": ("נשלח ל-someone@gmail.com", "someone@gmail.com"),
    "jwt": ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig123", "eyJhbGciOiJIUzI1NiJ9"),
    "coords": ("המכ\"ם ב-31.39115, 34.80468", "31.39115"),
}
for name, (text, secret) in CASES.items():
    out = wa.sanitize(text)
    leaked = secret in out
    if leaked:
        leaks.append(name)
    print(f"[{'LEAK' if leaked else 'MASKED'}] {name}: {out[:90]!r}")


@settings(max_examples=300, deadline=None)
@given(prefix=st.text(max_size=30), word=st.sampled_from(["token", "secret", "password", "api_key", "apikey", "auth", "pwd"]),
       sep=st.sampled_from(["=", ": ", " = ", ":"]),
       secret=st.text(alphabet="ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789", min_size=8, max_size=40))
def prop_keyword_secret_masked(prefix, word, sep, secret):
    from hypothesis import assume
    assume(secret not in prefix)  # הסוד כבר מופיע בטקסט החופשי שלפניו — לא מקרה של דליפה
    out = wa.sanitize(f"{prefix} {word}{sep}{secret}")
    assert secret not in out, out


try:
    prop_keyword_secret_masked()
    check("property: '<מילת-סוד><מפריד><ערך>' — הערך לא יוצא (300 דוגמאות)", True)
except AssertionError as e:
    check("property: '<מילת-סוד><מפריד><ערך>' — הערך לא יוצא", False, str(e)[:160])


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=400))
def prop_no_crash_and_bounded(text):
    out = wa.sanitize(text)
    assert isinstance(out, str) and len(out) <= max(len(text), 1) * 4 + 50


try:
    prop_no_crash_and_bounded()
    check("property: כל טקסט Unicode — לא קורס ולא מתנפח", True)
except Exception as e:  # noqa: BLE001
    check("property: כל טקסט Unicode — לא קורס", False, repr(e)[:160])

print(f"\nleaks (Error Guessing): {leaks}")
print(f"{ok}/{ok + fail} property checks passed")
sys.exit(1 if fail else 0)
