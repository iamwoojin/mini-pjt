"""LLM-as-Judge 평가 (5점 척도).

실행: python evaluation/run_judge.py --from ragas_round2 --tag judge_round2
- 입력: run_ragas.py가 저장한 samples(질문 · 답변 · 근거 · 정답)를 그대로 쓴다 (같은 답변을 두 방식으로 채점)
- 채점 모델: 답변 생성 모델(Haiku)과 다른 모델(Sonnet 4.5)로 자기 채점 편향을 줄인다
- 기준
  1) grounding (근거 충실성): 답변의 사실·숫자·판정이 근거 자료와 일치하고 지어낸 내용이 없는가
  2) completeness (이중 검증 완결성): 견적 검증 요청이면 업체 판정 · 가격 판정 · 권고 · 근거를 모두 제시했는가.
     견적 검증이 아닌 질문(규정 질의 · 범위 밖 · 권한 거절)이면 그 상황에 맞는 처리를 빠짐없이 했는가
"""
import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src import agent, config  # noqa: E402


class Judgement(BaseModel):
    grounding: int = Field(ge=1, le=5, description="근거 충실성 1~5")
    completeness: int = Field(ge=1, le=5, description="이중 검증 완결성 1~5")
    reason: str = Field(description="감점 이유를 한두 문장으로. 감점이 없으면 '감점 없음'")


PROMPT = """너는 기업 구매 검증 에이전트의 답변을 채점하는 평가자다. 아래 기준으로 1~5점을 매겨라.

[grounding 근거 충실성]
5: 모든 사실·숫자·판정이 근거 자료와 일치 / 3: 사소한 불일치나 근거 없는 표현 1개 / 1: 근거와 다른 숫자·판정이나 지어낸 내용

[completeness 이중 검증 완결성]
- 견적 검증 요청: 업체 판정, 가격 판정(기준가·비율), 권고, 근거 규정, 필요 시 승인 안내를 모두 제시하면 5
- 규정 질의: 질문에 직접 답하고 조항을 인용하면 5
- 범위 밖 · 권한 거절: 왜 처리할 수 없는지와 대안을 안내하면 5
- 빠진 요소 하나당 1~2점 감점

정답 예시는 참고용이다. 정답과 표현이 달라도 근거 자료와 일치하면 감점하지 않는다.

[질문]
{question}

[근거 자료]
{contexts}

[정답 예시]
{reference}

[답변]
{answer}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True, help="run_ragas.py 결과 태그")
    ap.add_argument("--tag", required=True)
    args = ap.parse_args()

    data = json.loads((BASE / "evaluation" / "results" / f"{args.src}.json").read_text(encoding="utf-8"))
    judge = agent._model(config.LLM_FALLBACK_MODEL).with_structured_output(Judgement)
    results = []
    for case, s in zip(data["results"], data["samples"]):
        j = judge.invoke(PROMPT.format(question=s["user_input"], contexts="\n".join(s["retrieved_contexts"]),
                                       reference=s["reference"], answer=s["response"]))
        results.append({"id": case["id"], **j.model_dump()})
        print(f"{case['id']:4} grounding={j.grounding} completeness={j.completeness}  {j.reason}")

    def mean(k):
        return round(sum(r[k] for r in results) / len(results), 2)

    summary = {"tag": args.tag, "from": args.src, "judge_model": config.LLM_FALLBACK_MODEL, "cases": len(results),
               "grounding": mean("grounding"), "completeness": mean("completeness"),
               "overall": round((mean("grounding") + mean("completeness")) / 2, 2)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    (BASE / "evaluation" / "results" / f"{args.tag}.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
