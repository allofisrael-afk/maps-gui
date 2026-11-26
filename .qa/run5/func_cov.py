"""טבלת כיסוי ברמת פונקציה מתוך coverage json (ריצת QA 5)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(sys.argv[1], encoding="utf-8"))
for fn, fd in d["files"].items():
    funcs = fd.get("functions", {})
    zero = [n for n, v in funcs.items() if n and v["summary"]["covered_lines"] == 0 and v["summary"]["num_statements"] > 0]
    part = ["%s(%.0f%%)" % (n, v["summary"]["percent_covered"]) for n, v in funcs.items() if n and 0 < v["summary"]["percent_covered"] < 75]
    print(fn, "| NOT RUN:", zero, "| <75%:", part)
