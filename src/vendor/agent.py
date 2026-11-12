"""업체 검증 에이전트: 국세청 상태 · 제출 서류 · 위험 보도 → 업체 판정 (Supervisor가 견적별로 실행)."""
from __future__ import annotations

from ..policy.citations import cite
from ..shared import config, llm
from ..shared.schemas import QueryRequest, QuoteItem, Trace
from ..supplier_data import client as data
from . import tools
from .prompts import NEWS_CLASSIFY_PROMPT
from .rules import vendor_verdict
from .schemas import NewsJudgements


def classify_news(supplier: dict, articles: list[dict]) -> list[dict]:
    """LLM이 기사별로 같은 회사인지 · 위험 보도인지 · 의혹/확정인지 분류한다 (판정은 하지 않음)."""
    if not articles:
        return []
    listing = "\n".join(f"[{i}] {a['date']} {a['title']} / {a['description']}" for i, a in enumerate(articles))
    prompt = NEWS_CLASSIFY_PROMPT.format(name=supplier.get("name"), region=supplier.get("region"),
                                         industry=supplier.get("industry"), listing=listing)
    res = llm.structured(NewsJudgements).invoke(prompt)
    by_idx = {j.index: j for j in res.items}
    out = []
    for i, a in enumerate(articles):
        j = by_idx.get(i)
        out.append({**a, "same_company": bool(j and j.same_company), "risk": bool(j and j.risk),
                    "status": j.status if j else "해당 없음"})
    return out


def vendor_check(q: QuoteItem, req: QueryRequest, trace: Trace, contexts: dict) -> dict:
    """업체 검증 에이전트: 국세청 상태 · 제출 서류 · 위험 보도 → 업체 판정"""
    supplier = trace.add("find_supplier", {"name": q.supplier_name, "b_no": q.b_no, "via": data.source()},
                         data.find_supplier(q.supplier_name, q.b_no)) or {}
    b_no = q.b_no or supplier.get("b_no", "")
    name = supplier.get("name") or q.supplier_name or "공급사 미상"

    # 사업자번호가 없으면 '미등록'과 구분해 '확인 불가'로 둔다 (2차 개선, G4)
    if not b_no:
        trace.add("vendor_check_skipped", {"supplier_name": q.supplier_name}, "사업자번호·등록 공급사 정보 없음")
        return {"name": name, "verdict": "확인 불가",
                "reasons": ["사업자번호와 등록된 공급사 정보가 없어 업체를 확인할 수 없음 (사업자번호를 알려 주시면 국세청 상태를 조회합니다)"]}

    nts = trace.add("check_business_status", b_no, tools.check_business_status(b_no))
    docs = trace.add("get_supplier_docs", {"supplier_id": supplier.get("id"), "via": data.source()},
                     data.get_supplier_docs(supplier.get("id", "")))
    articles = trace.add("search_news", name, tools.search_news(name))
    news = trace.add("classify_news", name, classify_news({**docs, "name": name}, articles)) if articles else []
    v, v_reasons = vendor_verdict(nts, docs, news)
    trace.add("vendor_verdict", {"today": config.TODAY.isoformat(), "b_stt": nts.get("b_stt"), "tax_type": nts.get("tax_type"),
                                 "founded": docs.get("founded"), "employees": docs.get("employees"),
                                 "docs_complete": docs.get("docs_complete"),
                                 "rule": "휴업·폐업·미등록=부적합 / 위험 보도·설립 1년 미만·인원 3명 미만·서류 누락=주의 / 그 외 적합"},
              {"verdict": v, "reasons": v_reasons})
    reason_text = " ".join(v_reasons)
    keys = ["부적합"] if v == "부적합" else []
    keys += [k for k, word in [("설립", "설립 1년 미만"), ("인원", "3명 미만"), ("서류", "서류 누락"),
                               ("위험 보도", "위험 보도("), ("동명", "동명 기업")] if word in reason_text]
    if v == "주의":
        keys.append("주의")
    cite(trace, contexts, *keys)
    return {"name": name, "verdict": v, "reasons": v_reasons}
