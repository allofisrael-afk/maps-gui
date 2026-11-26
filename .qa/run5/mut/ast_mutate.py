# Copyright (c) 2024-2026 Israel Alalouf. All rights reserved.
# See LICENSE in the project root.
"""ריצת QA 5 — Mutation testing מינימלי (stdlib ast) על עותק של radar_physics.py בארגז החול בלבד.
mutmut 2.5.1 לא מייצר מוטנטים תחת Python 3.14 (נבדק פעמיים) — זו החלופה. לכל מוטנט: כותב את הקובץ המוטנטי
לארגז החול, מריץ run_tests.bat עם timeout, ומסווג killed / survived / timeout. הקובץ המקורי בשורש לא נוגעים בו.
הרצה (מתוך .qa/run5/mut): python ast_mutate.py"""
import ast
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "radar_physics.py")
ORIG = open(SRC, encoding="utf-8").read()
SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
        ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult, ast.Pow: ast.Mult,
        ast.And: ast.Or, ast.Or: ast.And}


def targets(tree):
    """כל נקודות המוטציה: (סוג, lineno, col, תיאור) — רק בתוך פונקציות (לא קבועי מודול)."""
    out = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Compare):
                for i, op in enumerate(node.ops):
                    if type(op) in SWAP:
                        out.append(("cmp", node.lineno, node.col_offset, i, f"{type(op).__name__}->{SWAP[type(op)].__name__}", fn.name))
            elif isinstance(node, (ast.BinOp, ast.BoolOp)) and type(node.op) in SWAP:
                out.append(("op", node.lineno, node.col_offset, 0, f"{type(node.op).__name__}->{SWAP[type(node.op)].__name__}", fn.name))
            elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                out.append(("const", node.lineno, node.col_offset, 0, f"{node.value}->{node.value + 1}", fn.name))
    return out


def mutate(tree, t):
    kind, line, col, idx, _, _ = t
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) == line and getattr(node, "col_offset", None) == col:
            if kind == "cmp" and isinstance(node, ast.Compare):
                node.ops[idx] = SWAP[type(node.ops[idx])]()
                return True
            if kind == "op" and isinstance(node, (ast.BinOp, ast.BoolOp)):
                node.op = SWAP[type(node.op)]()
                return True
            if kind == "const" and isinstance(node, ast.Constant):
                node.value = node.value + 1
                return True
    return False


def run_tests(timeout):
    try:
        r = subprocess.run(["cmd", "/c", os.path.join(HERE, "run_tests.bat")], cwd=HERE, timeout=timeout,
                           capture_output=True)
        return "killed" if r.returncode != 0 else "survived"
    except subprocess.TimeoutExpired:
        return "timeout"


if __name__ == "__main__":
    budget_s = float(sys.argv[1]) if len(sys.argv) > 1 else 900  # תקציב זמן כולל
    t0 = time.time()
    base = run_tests(120)
    assert base == "survived", "baseline must pass"
    base_t = time.time() - t0
    ts = targets(ast.parse(ORIG))
    res = []
    try:
        for t in ts:
            if time.time() - t0 > budget_s:
                res.append({"line": t[1], "fn": t[5], "mut": t[4], "status": "not-run (time budget)"})
                continue
            tree = ast.parse(ORIG)
            if not mutate(tree, t):
                continue
            open(SRC, "w", encoding="utf-8").write(ast.unparse(tree))
            st = run_tests(max(30, base_t * 10))
            res.append({"line": t[1], "fn": t[5], "mut": t[4], "status": st})
            print(f"{st:9} L{t[1]:<4} {t[5]:28} {t[4]}", flush=True)
    finally:
        open(SRC, "w", encoding="utf-8").write(ORIG)  # שחזור העותק בארגז החול
    done = [r for r in res if r["status"] in ("killed", "survived", "timeout")]
    killed = sum(1 for r in done if r["status"] in ("killed", "timeout"))
    summary = {"mutants_total": len(ts), "executed": len(done), "killed_or_timeout": killed,
               "survived": [r for r in done if r["status"] == "survived"],
               "score": round(killed / len(done) * 100, 1) if done else None, "elapsed_s": round(time.time() - t0)}
    json.dump({"summary": summary, "all": res}, open(os.path.join(HERE, "..", "mutation_radar_physics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "survived"}), "survived:", len(summary["survived"]))
