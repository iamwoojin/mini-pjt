"""RAGAS 평가 (faithfulness · context_recall).

실행: python evaluation/run_ragas.py --tag ragas_round2
결과: evaluation/results/{tag}.json (케이스별 점수 + 평균)

- 질문은 test_queries.csv, 정답(reference)은 evaluation/ragas_references.json (N04 제외)
- retrieved_contexts = 답변이 근거로 삼은 자료 전체:
  인용한 규정 조항(contexts) + 도구 출력(국세청 상태, 제출 서류, 위험 보도, 조달 기준가 계산)
  판정 답변의 숫자는 규정이 아니라 도구 출력에서 나오므로 함께 넣어야 faithfulness를 공정하게 잴 수 있다.
- 평가 LLM은 서비스와 같은 Bedrock 모델(Haiku 4.5, 실패 시 Sonnet 4.5)
"""
import argparse
import csv
import json
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

# ragas 0.4.3은 langchain_community의 VertexAI 클래스를 import하지만 최신 langchain_community에는 없다.
# 이 프로젝트는 Bedrock만 쓰므로 빈 클래스로 자리만 채운다 (설치된 패키지는 수정하지 않음).
_vertex = types.ModuleType("langchain_community.chat_models.vertexai")
_vertex.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules[_vertex.__name__] = _vertex
import langchain_community.llms as _llms  # noqa: E402

if not hasattr(_llms, "VertexAI"):
    _llms.VertexAI = type("VertexAI", (), {})

from ragas import EvaluationDataset, RunConfig, evaluate  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import context_recall, faithfulness  # noqa: E402

from evaluation.run_eval import parse_note  # noqa: E402
from src import agent  # noqa: E402
from src.shared import config  # noqa: E402

TOOL_STEPS = {"parse_query", "check_business_status", "get_supplier_docs", "classify_news", "normalize_price",
              "search_procurement_prices", "search_procurement_prices_retry", "vendor_check_skipped", "guard_G1", "route",
              "vendor_verdict", "price_verdict", "recommend"}


def tool_context(step: dict) -> str | None:
    s, out = step["step"], step["output"]
    if s not in TOOL_STEPS:
        return None
    if s in ("search_procurement_prices", "search_procurement_prices_retry"):
        out = {"matched_spec": out.get("matched_spec"), "unit": out.get("unit"), "rows": len(out.get("rows", [])),
               "excluded": out.get("excluded")}
    if s == "parse_query":  # 견적서 원문을 해석한 내용 (공급사 · 품목 · 견적가 · VAT)
        out = [{k: q.get(k) for k in ("supplier_name", "b_no", "item_text", "quoted_price", "price_unit", "vat_included")}
               for q in out.get("quotes", [])]
    if s == "classify_news":
        out = [{k: a.get(k) for k in ("title", "date", "link", "same_company", "risk", "status")} for a in out]
    text = json.dumps({"input": step["input"], "output": out}, ensure_ascii=False)
    return f"[{s}] {text[:1200]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--only", nargs="*", help="특정 id만 실행")
    args = ap.parse_args()

    refs = json.loads((BASE / "evaluation" / "ragas_references.json").read_text(encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(BASE / "evaluation" / "test_queries.csv", encoding="utf-8")) if r["id"] in refs]
    if args.only:
        rows = [r for r in rows if r["id"] in args.only]

    samples, ids = [], []
    for r in rows:
        note = parse_note(r["note"])
        res = agent.run(agent.QueryRequest(question=r["input"], role=note.get("role", "buyer"), supplier_id=note.get("supplier_id")))
        ctx = [f"[{c['doc_id']}] {c['text']}" for c in res["contexts"]]
        ctx += [t for t in (tool_context(s) for s in res["trace"]) if t]
        samples.append({"user_input": r["input"], "response": res["answer"], "retrieved_contexts": ctx or ["(근거 없음)"],
                        "reference": refs[r["id"]]})
        ids.append(r["id"])
        print(f"{r['id']} 답변 생성 완료 (근거 {len(ctx)}개)")

    # ragas가 temperature를 직접 설정하므로 대체 체인이 아닌 단일 모델을 넘긴다
    # 답변이 길면 문장별 판정 JSON도 길어져 2,000토큰에서 잘리므로 출력 한도를 늘린다
    from langchain_aws import ChatBedrockConverse
    judge = LangchainLLMWrapper(ChatBedrockConverse(model=config.LLM_MODEL, region_name=config.AWS_REGION,
                                                    temperature=0, max_tokens=8000))
    result = evaluate(EvaluationDataset.from_list(samples), metrics=[faithfulness, context_recall], llm=judge,
                      run_config=RunConfig(max_workers=4, timeout=180), show_progress=False)
    df = result.to_pandas() if hasattr(result, "to_pandas") else None
    scores = result.scores if hasattr(result, "scores") else df.to_dict("records")

    per_case = []
    for i, cid in enumerate(ids):
        s = scores[i]
        per_case.append({"id": cid, "faithfulness": s.get("faithfulness"), "context_recall": s.get("context_recall")})

    def mean(key):
        vals = [c[key] for c in per_case if isinstance(c[key], (int, float)) and c[key] == c[key]]
        return round(sum(vals) / len(vals), 3) if vals else None

    summary = {"tag": args.tag, "cases": len(per_case), "faithfulness": mean("faithfulness"), "context_recall": mean("context_recall")}
    for c in per_case:
        f, cr = c["faithfulness"], c["context_recall"]
        print(f"{c['id']:4} faithfulness={f if f is None else round(f, 2)}  context_recall={cr if cr is None else round(cr, 2)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    out = BASE / "evaluation" / "results" / f"{args.tag}.json"
    out.write_text(json.dumps({"summary": summary, "results": per_case, "samples": samples}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
