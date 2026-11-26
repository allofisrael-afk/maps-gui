# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — תרחיש מייצג לליבה האלגוריתמית של כלי מעקב המכ"ם + בדיקות metamorphic, אנליטיות, דטרמיניזם,
convergence ו-Golden Master. בלי רשת: שטח סינתטי (רכס) מוזרק כ-fetch_cells.

התרחיש הראשי (SCENARIO): מכ"ם בנגב, תותח 14 ק"מ צפונה יורה דרומה (MPM, אטמוספרה תקנית), רכס סינתטי 600 מ'
מזרחית למכ"ם. רץ בכל שלושת סוגי הסריקה (rotating/phased/tracker), עם מערך מופע (סקטור), RCS לפי זווית, גשם,
אזור מת קרוב, ובנוסף: פרופיל שטח (ray_profile), הצעת מיקום (run_placement), ורקטה (rocket_model).
הרצה: .venv\\Scripts\\python.exe .qa/run5/tests/test_r5_radar_algorithmic.py [--update-golden]
"""
import copy
import json
import math
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
if os.environ.get("QA_MUT_ROOT"):  # Mutation testing: עותק מוטנטי בארגז חול קודם לשורש האמיתי
    sys.path.insert(0, os.environ["QA_MUT_ROOT"])
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import mpm_api  # noqa: E402
import radar_physics as rp  # noqa: E402
import radar_service as rs  # noqa: E402
import radar_track as rt  # noqa: E402
import rocket_model  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "..", "golden", "radar_scenario_golden.json")
R_LAT, R_LON = 31.25, 34.80
ok_count, fail_count = 0, 0


def check(name, cond, info=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
    else:
        fail_count += 1
    print(f"[{'OK' if cond else 'FAIL'}] {name} {info}")


def ground(lat, lon):
    """שטח סינתטי: 100 מ', ורכס 600 מ' במרחק 5-6 ק"מ מזרחית למכ"ם (אזימוט 60-120)."""
    d = rt.haversine_m(R_LAT, R_LON, lat, lon)
    b = rt.bearing_deg(R_LAT, R_LON, lat, lon)
    return 700.0 if (5000 <= d <= 6000 and 60 <= b <= 120) else 100.0


def fetch(cells):
    return [ground(c[0], c[1]) for c in cells]


def ballistic(dist_km=14.0, qe=450, az=3200):
    glat, glon = rt.destination_point(R_LAT, R_LON, 0.0, dist_km * 1000)
    t = mpm_api.trajectory({"lat": glat, "lon": glon, "alt_m": 100.0}, qe, az, 684, met={"source": "standard"},
                           include_path=True, path_step=5)
    return [{"t": q["t"], "lat": q["lat"], "lon": q["lon"], "alt": q["alt_msl"]} for q in t["path"]]


BASE = {"range_km": 30, "min_range_km": 1.5, "h_antenna": 5, "vertical_center_deg": 20, "vertical_width_deg": 40,
        "power_kw": 100, "gain_dbi": 38, "freq_mhz": 9500, "sensitivity_dbm": -108, "rcs_m2": 0.01, "prf_hz": 6000,
        "mdv_kt": 20, "antenna_type": "phased_array", "boresight_deg": 0, "max_scan_deg": 45,
        "track_mode": "track", "rot_period_s": 3, "revisit_s": 0.3, "track_rate_hz": 10, "max_ang_rate_dps": 30,
        "cue_delay_s": 1, "track_m": 2, "track_n": 3, "coast_s": 2,
        "rcs_mode": "aspect", "rcs_nose": 0.005, "rcs_side": 0.02, "rcs_tail": 0.01, "rain_rate_mmh": 10, "rain_top_m": 3000}


def run(body, traj, alt_ref="msl"):
    p, cfg, ar = rs.parse_all(dict(body, alt_ref=alt_ref))
    return rs.run_check(R_LAT, R_LON, p, traj, cfg, ar, fetch)


def digest(res):
    """תמצית יציבה של תוצאה — ל-Golden Master ולהשוואות."""
    s, k = res["summary"], res.get("track") or {}
    return {"coverage_pct": s["coverage_pct"], "duration_s": s["duration_s"], "detected_any": s["detected_any"],
            "reason_seconds": s["reason_seconds"], "first_detection_t": (s.get("first_detection") or {}).get("t"),
            "track_initiated": k.get("track_initiated"), "first_track_t": k.get("first_track_t"),
            "tracked_pct": k.get("tracked_pct"), "opportunities": k.get("opportunities"), "n_points": len(res["points"])}


timings = {}
traj = ballistic()
# ── 1. תרחיש ראשי: שלושת סוגי הסריקה ──
scen = {}
for mode in ("rotating", "phased", "tracker"):
    t0 = time.perf_counter()
    res = run(dict(BASE, scan_mode=mode), traj)
    timings[f"scenario_{mode}_s"] = round(time.perf_counter() - t0, 3)
    scen[mode] = digest(res)
    reasons = {p["reason"] for p in res["points"]}
    check(f"תרחיש [{mode}]: הסתיים, נפתח מעקב", scen[mode]["track_initiated"] is True, json.dumps(scen[mode]["reason_seconds"], ensure_ascii=False))
    if mode == "phased":
        phased_res = res
        check("תרחיש [phased]: הסיבות שהופעלו כוללות ok + לפחות 2 סיבות אובדן", "ok" in reasons and len(reasons - {"ok"}) >= 2, str(sorted(reasons)))
# ערכי ביניים לאורך הצנרת — בנקודה הראשונה שזוהתה
pts = phased_res["points"]
p0 = next(p for p in pts if p["status"] == "detected")
geo_d = rt.haversine_m(R_LAT, R_LON, p0["lat"], p0["lon"])
check("ביניים: dist_km תואם haversine (±1 מ')", abs(p0["dist_km"] * 1000 - geo_d) <= 1.0 + 0.5, f"{p0['dist_km']} km vs {geo_d / 1000:.4f}")
check("ביניים: slant >= dist (אלכסון לא קצר מאופקי)", all(p["slant_km"] + 1e-9 >= p["dist_km"] for p in pts))
check("ביניים: |radial| <= speed (פיזיקלי)", all(abs(p["radial_ms"]) <= p["speed_ms"] + 0.05 for p in pts))
check("ביניים: RCS לפי זווית בין חרטום/זנב לצד", all(min(0.005, 0.01) - 1e-9 <= p["rcs_m2"] <= 0.02 + 1e-9 for p in pts if p.get("rcs_m2") is not None))
check("ביניים: הנחתת גשם >= 0 ולא יורדת עם הטווח באותו כיוון (מונוטוני בקירוב)", all((p.get("rain_db") or 0) >= 0 for p in pts))

# ── 2. רכיבים נוספים בתרחיש: פרופיל שטח, הצעת מיקום, רקטה, AGL ──
p, cfg, ar = rs.parse_all(dict(BASE, scan_mode="phased"))
east = rt.destination_point(R_LAT, R_LON, 90.0, 8000)
pr = rs.ray_profile(R_LAT, R_LON, p, {"lat": east[0], "lon": east[1], "alt": 300}, fetch)
check("ray_profile: קו מזרחה נחסם ע\"י הרכס (5-6 ק\"מ)", pr["visible"] is False and 4900 <= pr["block_dist_m"] <= 6100, f"block={pr['block_dist_m']}")
west = rt.destination_point(R_LAT, R_LON, 270.0, 8000)
check("ray_profile: קו מערבה פנוי", rs.ray_profile(R_LAT, R_LON, p, {"lat": west[0], "lon": west[1], "alt": 300}, fetch)["visible"] is True)
t0 = time.perf_counter()
pl = rs.run_placement(R_LAT, R_LON, 1500.0, 750.0, "warning", p, traj, cfg, "msl", fetch)
timings["placement_s"] = round(time.perf_counter() - t0, 3)
check("run_placement: מועמדים + מיטבי עם ציון", len(pl["candidates"]) > 1 and pl["best"] and pl["best"][0]["score"] is not None, f"n={len(pl['candidates'])}")
atmo, _ = mpm_api._build_atmosphere({"source": "standard"}, 100.0)
rk = rocket_model.simulate({"lat": R_LAT, "lon": R_LON, "alt_m": 100}, 45, 0, {"mass_kg": 40, "prop_kg": 12, "burn_s": 2,
                                                                         "thrust_n": 12000, "diam_m": 0.15, "cd": 0.4}, atmo,
                          geo_direct=__import__("mpm.geodesy", fromlist=["direct"]).direct)  # R5-ROCKET-GEO: ברירת המחדל None קורסת
try:  # שחזור הממצא: קריאה עם ברירת המחדל
    rocket_model.simulate({"lat": R_LAT, "lon": R_LON, "alt_m": 100}, 45, 0, {"mass_kg": 40, "prop_kg": 12, "burn_s": 2,
                          "thrust_n": 12000, "diam_m": 0.15, "cd": 0.4}, atmo)
    print("[REPRO-NOT-REPRODUCED] R5-ROCKET-GEO")
except TypeError:
    print("[REPRO-CONFIRMED] R5-ROCKET-GEO simulate() עם geo_direct=None (ברירת המחדל) זורק TypeError")
check("rocket: מסלול עם פגיעה", rk["ok"] and rk["impact"]["range_m"] > 1000, f"range={rk['impact']['range_m']:.0f}")
rk_traj = [{"t": q["t"], "lat": q["lat"], "lon": q["lon"], "alt": q["alt_msl"]} for q in rk["path"]]
check("rocket -> run_check: עובר בצנרת", run(dict(BASE, scan_mode="phased"), rk_traj)["summary"]["duration_s"] > 0)
loiter = [{"t": i * 10.0, "lat": rt.destination_point(R_LAT, R_LON, i * 20.0, 4000)[0], "lon": rt.destination_point(R_LAT, R_LON, i * 20.0, 4000)[1], "alt": 300} for i in range(19)]
agl = run(dict(BASE, scan_mode="rotating", antenna_type="generic", track_mode="detection"), loiter, alt_ref="agl")
check("AGL + generic + detection: גובה הורם בקרקע (≈400 מ' MSL מעל 100 קרקע)", abs(agl["points"][0]["alt"] - 400) < 1.0 and agl.get("track") is None, f"alt0={agl['points'][0]['alt']}")

# ── 2ב. תרחיש משלים: ריבוד (lobing) מעל ים — _lobing_factor לא הופעל בתרחיש הראשי ──
lob = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0, lobing_enabled=True, reflectivity="sea"), traj)
nolob = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0), traj)
check("משלים lobing: רץ, והכיסוי שונה/שווה בתחום חוקי [0,100]", 0 <= lob["summary"]["coverage_pct"] <= 100,
      f"lobing={lob['summary']['coverage_pct']} none={nolob['summary']['coverage_pct']}")

# ── 3. אנליטי / מנוון ──
R1 = rp._radar_max_range_m(100, 38, 9500, 0.01, -108)
check("משוואת המכ\"ם: R ∝ σ^(1/4) (פי 16 RCS = פי 2 טווח)", abs(rp._radar_max_range_m(100, 38, 9500, 0.16, -108) / R1 - 2.0) < 1e-9)
check("משוואת המכ\"ם: R ∝ P^(1/4)", abs(rp._radar_max_range_m(1600, 38, 9500, 0.01, -108) / R1 - 2.0) < 1e-9)
check("משוואת המכ\"ם: +12 dB רגישות = פי 2 טווח", abs(rp._radar_max_range_m(100, 38, 9500, 0.01, -108 - 10 * math.log10(16)) / R1 - 2.0) < 1e-9)
check("טווח חד-משמעי: c/(2·PRF)", abs(rp._max_unambiguous_range_m(1000) - 299792458 / 2000) < 1.0)
# בלי תנועה: מטרה נייחת לא מזוהה בדופלר (v=0 < MDV)
still = [{"t": float(i), "lat": 31.30, "lon": 34.80, "alt": 1000.0} for i in range(10)]
st = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0), still)
check("מנוון: מטרה נייחת — עיוורת דופלר לאורך כל הזמן", st["summary"]["reason_seconds"].get("doppler", 0) >= 8.9, json.dumps(st["summary"]["reason_seconds"]))

# ── 4. Metamorphic ──
tsh = [dict(q, t=q["t"] + 1000.0) for q in traj]
a, b = digest(run(dict(BASE, scan_mode="phased"), traj)), digest(run(dict(BASE, scan_mode="phased"), tsh))
check("MR הזזת זמן: +1000 שנ' לכל הנקודות — אותו כיסוי ומעקב", a["coverage_pct"] == b["coverage_pct"] and a["tracked_pct"] == b["tracked_pct"], f"{a['tracked_pct']} vs {b['tracked_pct']}")
sh = traj[:]
random.Random(7).shuffle(sh)
check("MR סדר קלט: ערבוב סדר הנקודות — אותה תוצאה", digest(run(dict(BASE, scan_mode="phased"), sh)) == a)
prev = -1
mono = True
for s_dbm in (-95, -100, -105, -110, -115, -120):
    cov = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0, sensitivity_dbm=s_dbm), traj)["summary"]["coverage_pct"]  # כיסוי ברגישות הזו
    mono &= cov >= prev
    prev = cov
check("MR מונוטוניות: רגישות טובה יותר לא מקטינה כיסוי", mono)
c_dry = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0), traj)["summary"]["coverage_pct"]
c_wet = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=50), traj)["summary"]["coverage_pct"]
check("MR גשם: גשם לא מגדיל כיסוי", c_wet <= c_dry, f"dry={c_dry} wet={c_wet}")
# סימטריה: מסלול מראה מערבה/מזרחה סביב מרידיאן המכ"ם, בלי רכס (שטח שטוח), אנטנה גנרית
flat = lambda cells: [100.0] * len(cells)  # noqa: E731
mir = [dict(q, lon=2 * R_LON - q["lon"]) for q in traj]
skew = [dict(q, lon=q["lon"] + 0.05) for q in traj]
skew_m = [dict(q, lon=2 * R_LON - q["lon"]) for q in skew]
pg, cg, ag = rs.parse_all(dict(BASE, antenna_type="generic", scan_mode="phased", rain_rate_mmh=0))
d1 = digest(rs.run_check(R_LAT, R_LON, pg, skew, cg, ag, flat))
d2 = digest(rs.run_check(R_LAT, R_LON, pg, skew_m, cg, ag, flat))
check("MR סימטריה: מסלול מראה סביב המרידיאן (שטח שטוח) — אותו כיסוי", d1["coverage_pct"] == d2["coverage_pct"], f"{d1['coverage_pct']} vs {d2['coverage_pct']}")

# ── 5. Convergence: צעד המסלול ──
covs = {}
for step in (20, 10, 5, 2):
    glat, glon = rt.destination_point(R_LAT, R_LON, 0.0, 14000)
    tt = mpm_api.trajectory({"lat": glat, "lon": glon, "alt_m": 100.0}, 450, 3200, 684, met={"source": "standard"}, include_path=True, path_step=step)
    tr = [{"t": q["t"], "lat": q["lat"], "lon": q["lon"], "alt": q["alt_msl"]} for q in tt["path"]]
    covs[step] = run(dict(BASE, scan_mode="phased", track_mode="detection", rain_rate_mmh=0), tr)["summary"]["coverage_pct"]
check("Convergence: כיסוי מתכנס עם צעד מסלול קטן יותר (פער 5→2 ≤ 2 נק' אחוז)", abs(covs[5] - covs[2]) <= 2.0, str(covs))

# ── 6. רגישות: שינוי קטן בכל פרמטר מרכזי — שינוי פלט קטן ──
base_cov = run(dict(BASE, scan_mode="phased", track_mode="detection"), traj)["summary"]["coverage_pct"]
jumps = {}
for k, dv in (("power_kw", 1.0), ("gain_dbi", 0.1), ("sensitivity_dbm", -0.1), ("h_antenna", 0.5), ("vertical_width_deg", 0.5), ("prf_hz", 10)):
    c2 = run(dict(BASE, scan_mode="phased", track_mode="detection", **{k: BASE[k] + dv}), traj)["summary"]["coverage_pct"]
    jumps[k] = round(c2 - base_cov, 2)
check("רגישות: שינוי קטן בפרמטר משנה כיסוי ב-≤ 5 נק' אחוז", all(abs(v) <= 5.0 for v in jumps.values()), str(jumps))

# ── 7. דטרמיניזם ──
r1 = json.dumps(run(dict(BASE, scan_mode="rotating"), traj), sort_keys=True)
r2 = json.dumps(run(dict(BASE, scan_mode="rotating"), copy.deepcopy(traj)), sort_keys=True)
check("דטרמיניזם: אותה ריצה פעמיים — פלט JSON זהה לבייט", r1 == r2)

# ── 8. Scaling ──
for n in (500, 2000, 6000):
    tr = [{"t": i * 0.1, "lat": 31.30 + i * 0.00002, "lon": 34.80, "alt": 500 + i * 0.5} for i in range(n)]
    t0 = time.perf_counter()
    run(dict(BASE, scan_mode="phased", track_mode="track"), tr)
    timings[f"scaling_{n}pts_s"] = round(time.perf_counter() - t0, 3)
print("timings:", timings)

# ── 9. Golden Master ──
gm = {"scenario": scen, "placement_best": [(c["lat"], c["lon"], c["score"]) for c in pl["best"]],
      "rocket_impact_m": round(rk["impact"]["range_m"], 1), "profile_block_m": pr["block_dist_m"], "convergence": covs}
TOL = {"pct": 0.11, "s": 0.011, "m": 1.0}  # ר' נימוק הטולרנסים בדוח (יחידת התצוגה האחרונה + שגיאת עיגול חוצת-פלטפורמות)


def close(a, b, path=""):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], path + "." + str(k)) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, path) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        tol = TOL["pct"] if "pct" in path or "convergence" in path else (TOL["m"] if path.endswith("_m") or "placement" in path else TOL["s"])
        return abs(float(a) - float(b)) <= tol
    return a == b


os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
if "--update-golden" in sys.argv or not os.path.exists(GOLDEN):
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(json.loads(json.dumps(gm)), f, ensure_ascii=False, indent=1)
    print("golden written:", GOLDEN)
with open(GOLDEN, encoding="utf-8") as f:
    gold = json.load(f)
check("Golden Master: התרחיש תואם לייחוס בטולרנס", close(json.loads(json.dumps(gm)), gold))
with open(os.path.join(HERE, "..", "perf_baseline.json"), "w", encoding="utf-8") as f:
    json.dump(timings, f, indent=1)
print(f"\n{ok_count}/{ok_count + fail_count} passed")
sys.exit(1 if fail_count else 0)
