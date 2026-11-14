# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""נתוני פגז: מאפיינים פיזיקליים וטבלאות מקדמים אווירודינמיים כפונקציה של מאך.

קובץ פגז (JSON):
{
  "name": "...",
  "mass_kg": 43.0,
  "diameter_m": 0.15475,
  "ix_kgm2": 0.1444,        # מומנט התמד צירי
  "iy_kgm2": 1.162,         # מומנט התמד רוחבי (לחישוב יציבות ג'ירוסקופית)
  "twist_calibers": 20.0,   # פיתול קנה: סיבוב אחד לכל N קליברים
  "aero_csv": "generic_155_aero.csv"   # נתיב יחסי לקובץ ה-JSON
}

קובץ המקדמים (CSV) — עמודות חובה:
  mach, cd0, cd_a2, cl_a, cm_a, cnp_a, cl_p
  cd0   – גרר בזווית אפס
  cd_a2 – גרר מושרה מהטיה (מוכפל ב-α²)
  cl_a  – שיפוע מקדם עילוי
  cm_a  – שיפוע מומנט הטיה (חיובי = מומנט מהפך, פגז מיוצב-ספין)
  cnp_a – שיפוע כוח מגנוס (חיובי בקונבנציה של התוכנה = כוח כלפי מעלה בסחיפה ימנית)
  cl_p  – מקדם דעיכת ספין (שלילי)
"""
import bisect
import csv
import json
import os
from dataclasses import dataclass, field

AERO_COLUMNS = ("cd0", "cd_a2", "cl_a", "cm_a", "cnp_a", "cl_p")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "projectiles")
DEFAULT_PROJECTILE = os.path.join(DATA_DIR, "generic_155.json")


@dataclass
class Projectile:
    name: str
    mass: float
    diameter: float
    ix: float
    iy: float
    twist_calibers: float
    mach: list = field(default_factory=list)
    table: dict = field(default_factory=dict)  # col -> list
    source: str = ""

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if self.mass <= 0 or self.diameter <= 0 or self.ix <= 0 or self.iy <= 0:
            raise ValueError("מסה, קוטר ומומנטי התמד חייבים להיות חיוביים")
        if self.twist_calibers <= 0:
            raise ValueError("פיתול הקנה חייב להיות חיובי")
        if len(self.mach) < 2:
            raise ValueError("טבלת המקדמים חייבת לכלול לפחות שתי שורות")
        if any(b <= a for a, b in zip(self.mach, self.mach[1:])):
            raise ValueError("עמודת mach חייבת להיות עולה ממש")
        for c in AERO_COLUMNS:
            if c not in self.table or len(self.table[c]) != len(self.mach):
                raise ValueError(f"עמודה חסרה או באורך שגוי בטבלת המקדמים: {c}")

    def coeffs(self, m):
        """אינטרפולציה לינארית של כל המקדמים במאך m (נצמד לקצוות הטבלה)."""
        xs = self.mach
        if m != m:
            raise ValueError("מספר מאך לא תקין (NaN)")
        if m <= xs[0]:
            return tuple(self.table[c][0] for c in AERO_COLUMNS)
        if m >= xs[-1]:
            return tuple(self.table[c][-1] for c in AERO_COLUMNS)
        i = bisect.bisect_right(xs, m) - 1
        f = (m - xs[i]) / (xs[i + 1] - xs[i])
        return tuple(self.table[c][i] + f * (self.table[c][i + 1] - self.table[c][i]) for c in AERO_COLUMNS)

    def muzzle_spin(self, mv):
        """קצב ספין בלוע [rad/s] לפי הפיתול: p = 2π·V / (n·d)."""
        import math
        return 2.0 * math.pi * mv / (self.twist_calibers * self.diameter)

    def summary(self):
        return {
            "name": self.name, "mass_kg": self.mass, "diameter_m": self.diameter,
            "ix_kgm2": self.ix, "iy_kgm2": self.iy, "twist_calibers": self.twist_calibers,
            "mach_range": [self.mach[0], self.mach[-1]], "source": self.source,
        }


def load_aero_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"קובץ המקדמים ריק: {path}")
    keys = {k.strip().lower(): k for k in rows[0].keys()}
    missing = [c for c in ("mach",) + AERO_COLUMNS if c not in keys]
    if missing:
        raise ValueError(f"עמודות חסרות בקובץ {os.path.basename(path)}: {', '.join(missing)}")
    rows.sort(key=lambda r: float(r[keys["mach"]]))
    mach = [float(r[keys["mach"]]) for r in rows]
    table = {c: [float(r[keys[c]]) for r in rows] for c in AERO_COLUMNS}
    return mach, table


def load_projectile(path=None):
    path = path or DEFAULT_PROJECTILE
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    aero = d.get("aero_csv")
    if not aero:
        raise ValueError("בקובץ הפגז חסר השדה aero_csv")
    if not os.path.isabs(aero):
        aero = os.path.join(os.path.dirname(os.path.abspath(path)), aero)
    mach, table = load_aero_csv(aero)
    return Projectile(
        name=d.get("name", os.path.splitext(os.path.basename(path))[0]),
        mass=float(d["mass_kg"]), diameter=float(d["diameter_m"]),
        ix=float(d["ix_kgm2"]), iy=float(d["iy_kgm2"]),
        twist_calibers=float(d["twist_calibers"]),
        mach=mach, table=table, source=os.path.abspath(path),
    )
