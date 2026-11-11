"""test_queries.csv 자동 채점.

실행: python evaluation/run_eval.py --tag round1
결과: evaluation/results/{tag}.json (케이스별 답변·판정·통과 여부) + 요약 출력
규칙은 evaluation/README.md 참고.
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import agent  # noqa: E402


def parse_note(note: str) -> dict:
    head = note.split(".")[0]
    out = {}
    for part in head.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def check(item: str, res: dict) -> bool:
    item = item.strip()
    if not item:
        return True
    if item.startswith("ctx:"):
        return any(c["doc_id"].startswith(item[4:]) for c in res.get("contexts", []))
    if item.startswith("status:"):
        return res.get("status") == item[7:]
    return any(alt in res.get("answer", "") for alt in item.split("|"))


def evaluate(row: dict) -> dict:
    note = parse_note(row["note"])
    req = agent.QueryRequest(question=row["input"], role=note.get("role", "buyer"), supplier_id=note.get("supplier_id"))
    t0 = time.time()
    try:
        res = agent.run(req)
        error = None
    except Exception as e:  # 실패도 결과로 기록
        res, error = {"answer": "", "contexts": [], "trace": []}, f"{type(e).__name__}: {e}"
    elapsed = time.time() - t0
    traits = [t for t in row["expected_traits"].split(";") if t.strip()]
    forbidden = [f for f in row["forbidden"].split(";") if f.strip()]
    missing = [t for t in traits if not check(t, res)]
    violated = [f for f in forbidden if check(f, res)]
    called = {s["step"] for s in res.get("trace", [])}
    expected_tools = [t for t in row["expected_tools"].split(";") if t.strip()]
    tool_hit = sum(t in called for t in expected_tools)
    return {
        "id": row["id"], "category": row["category"], "passed": not missing and not violated and not error,
        "missing_traits": missing, "violated_forbidden": violated, "error": error,
        "tools_expected": expected_tools, "tools_called": sorted(called), "tool_hit": tool_hit,
        "elapsed_sec": round(elapsed, 1), "status": res.get("status"),
        "answer": res.get("answer"), "contexts": [c["doc_id"] for c in res.get("contexts", [])],
        "input": row["input"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--only", nargs="*", help="특정 id만 실행")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(BASE / "evaluation" / "test_queries.csv", encoding="utf-8")))
    if args.only:
        rows = [r for r in rows if r["id"] in args.only]
    results = []
    for r in rows:
        out = evaluate(r)
        results.append(out)
        mark = "PASS" if out["passed"] else "FAIL"
        print(f"{out['id']:4} {mark} {out['elapsed_sec']:5.1f}s  missing={out['missing_traits']} violated={out['violated_forbidden']} {out['error'] or ''}")

    by_cat = {}
    for r in results:
        c = by_cat.setdefault(r["category"], [0, 0])
        c[0] += r["passed"]
        c[1] += 1
    total = sum(r["passed"] for r in results)
    tool_exp = sum(len(r["tools_expected"]) for r in results)
    tool_hit = sum(r["tool_hit"] for r in results)
    times = sorted(r["elapsed_sec"] for r in results)
    summary = {
        "tag": args.tag, "passed": total, "total": len(results), "pass_rate": round(total / len(results), 3),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in by_cat.items()},
        "tool_accuracy": round(tool_hit / tool_exp, 3) if tool_exp else None,
        "median_latency_sec": times[len(times) // 2],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    out_dir = BASE / "evaluation" / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{args.tag}.json").write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
