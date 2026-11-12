"""규정 검토 에이전트: 업체 × 가격 → 권고 · 조치 · 근거 조항 → 답변 블록, 규정 질의 RAG 답변."""
from __future__ import annotations

from ..shared import llm
from ..shared.schemas import QueryRequest, QuoteItem, Trace
from . import retriever
from .citations import cite
from .prompts import POLICY_ANSWER_PROMPT
from .rules import ACTION_LABEL, recommend


def policy_review(q: QuoteItem, req: QueryRequest, vendor: dict, price: dict, trace: Trace, contexts: dict) -> tuple[str, str | None]:
    """규정 검토 에이전트: 업체 × 가격 → 권고 · 조치 · 근거 조항 → 답변 블록"""
    v, p = vendor["verdict"], price["verdict"]
    rec, action, rec_reason = recommend(v, p)
    trace.add("recommend", {"vendor": v, "price": p,
                            "rule": "업체 부적합→보류(등록 보류) / 가격 과다→보류(재견적) / 적합×적정→진행 / 그 외 조건부"},
              {"recommendation": rec, "action": action, "reason": rec_reason})
    cite(trace, contexts, *[k for k in (p,) if k in ("과다", "검토 필요", "판단 불가")])
    if action:
        cite(trace, contexts, "조치 권한")

    lines = [f"[{vendor['name']}] {q.item_text}",
             f"업체 판정: {v}", *[f"  - {r}" for r in vendor["reasons"]],
             f"가격 판정: {p}", *[f"  - {r}" for r in price["lines"]],
             f"권고: {rec} ({rec_reason})"]
    if action:
        label = ACTION_LABEL[action]
        if req.role == "buyer":
            lines.append(f"다음 조치: {label} — 구매 담당자 승인 후 실행됩니다. 승인하시겠습니까?")
        else:
            lines.append(f"다음 조치: {label}이(가) 필요합니다. 구매 담당자 승인 필요 (임직원은 직접 실행할 수 없습니다)")
    return "\n".join(lines), action


def answer_policy_question(question: str, trace: Trace, contexts: dict) -> str:
    """규정 질의: 조항 검색(RAG) → 검색된 조항만 근거로 LLM이 답변을 쓴다 (판정은 하지 않음)."""
    hits = trace.add("search_policy", question, retriever.search_policy(question, k=3))
    contexts.update({h["doc_id"]: h for h in hits})
    joined = "\n".join(f"[{h['doc_id']}] {h['text']}" for h in hits)
    msg = llm.llm().invoke(POLICY_ANSWER_PROMPT.format(joined=joined, question=question))
    answer = msg.content if isinstance(msg.content, str) else str(msg.content)
    trace.add("policy_answer", [h["doc_id"] for h in hits], answer[:200])
    return answer
