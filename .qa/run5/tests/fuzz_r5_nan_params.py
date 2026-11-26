# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — fuzzing ממוקד: לכל פרמטר מספרי של בדיקת המעקב, NaN / +Inf / -Inf, בכל אחד משלושת סוגי הסריקה.
כל צירוף רץ בתהליך נפרד עם timeout של 8 שנ' — "HANG" = לולאה אינסופית (CWE-835). בלי רשת (שליפה מזויפת).
הרצה: .venv\\Scripts\\python.exe .qa/run5/tests/fuzz_r5_nan_params.py"""
import json
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

KEYS = ["range_km", "min_range_km", "h_antenna", "ridge_margin_deg", "vertical_center_deg", "vertical_width_deg", "power_kw",
        "gain_dbi", "freq_mhz", "sensitivity_dbm", "rcs_m2", "prf_hz", "mdv_kt", "boresight_deg", "max_scan_deg",
        "rot_period_s", "scan_phase_deg", "revisit_s", "track_rate_hz", "max_ang_rate_dps", "cue_delay_s", "track_m", "track_n",
        "coast_s", "rcs_nose", "rcs_side", "rcs_tail", "rain_rate_mmh", "rain_top_m"]
MODES = ["rotating", "phased", "tracker"]
VALUES = {"nan": float("nan"), "+inf": float("inf"), "-inf": float("-inf")}


def work(key, mode, vname, q):
    import radar_service as rs
    traj = [{"t": i * 0.5, "lat": 31.3 + i * 0.001, "lon": 34.8, "alt": 500 + 10 * i} for i in range(40)]
    body = {"range_km": 20, "scan_mode": mode, "antenna_type": "phased_array", "rcs_mode": "aspect", "rain_rate_mmh": 5,
            key: VALUES[vname]}
    try:
        p, cfg, ar = rs.parse_all(body)
        rs.run_check(31.25, 34.8, p, traj, cfg, ar, lambda c: [100.0] * len(c))
        q.put("ok")
    except Exception as e:  # noqa: BLE001 — מסווגים כל חריגה
        q.put("EXC:" + type(e).__name__)


if __name__ == "__main__":
    out = {}
    for mode in MODES:
        for key in KEYS:
            for vname in VALUES:
                q = mp.Queue()
                pr = mp.Process(target=work, args=(key, mode, vname, q))
                pr.start()
                pr.join(8)
                if pr.is_alive():
                    pr.kill(); pr.join()
                    res = "HANG"
                else:
                    res = q.get() if not q.empty() else f"exit{pr.exitcode}"
                if res != "ok":
                    out[f"{mode}/{key}={vname}"] = res
                    print(f"{mode:9} {key:20} {vname:5} -> {res}", flush=True)
    print(f"\nnon-ok: {len(out)} / {len(MODES) * len(KEYS) * len(VALUES)}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fuzz_nan_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
