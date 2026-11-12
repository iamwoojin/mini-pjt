"""가격 검증 에이전트: 조달 기준가 검색(실패 시 재검색) · VAT·단위 정규화 → 가격 판정 (Supervisor가 견적별로 실행)."""
from __future__ import annotations

from ..policy.citations import cite
from ..shared.schemas import QueryRequest, QuoteItem, Trace
from ..shared.text import ground_spec
from . import tools
from .rules import price_verdict


def _fmt(n: float | None) -> str:
    return "-" if n is None else f"{n:,.0f}원"


def price_check(q: QuoteItem, req: QueryRequest, trace: Trace, contexts: dict) -> dict:
    """가격 검증 에이전트: 조달 기준가 검색(실패 시 재검색) · VAT·단위 정규화 → 가격 판정"""
    if not (q.detail_name and q.quoted_price):
        return {"verdict": "판단 불가", "lines": ["품목 규격이나 견적가를 확인할 수 없어 기준가와 비교하지 못함"]}
    lines = []
    found = trace.add("search_procurement_prices", {"detail_name": q.detail_name, "spec": q.spec},
                      tools.search_procurement_prices(q.detail_name, q.spec))
    if not found["matched_spec"] and q.item_text:
        # 재검색: 해석된 규격으로 못 찾으면 질문 원문의 품목 표현(질문에 있는 토큰만)으로 다시 찾는다
        retry_spec = ground_spec(q.item_text, req.question)
        found = trace.add("search_procurement_prices_retry", {"detail_name": q.detail_name, "spec": retry_spec},
                          tools.search_procurement_prices(q.detail_name, retry_spec))
    calc = trace.add("normalize_price",
                     {"quoted_price": q.quoted_price, "price_unit": q.price_unit, "units_per_benchmark": q.units_per_benchmark,
                      "vat_included": q.vat_included, "matched_spec": found["matched_spec"],
                      "condition": found.get("condition"),
                      "samples_filter": {"matched": len(found["rows"]) + found["excluded"]["count"],
                                         "kept": len(found["rows"]), "excluded": found["excluded"]["count"],
                                         "reasons": found["excluded"]["reasons"]} if found["matched_spec"] else None,
                      "method": "비교 가능 조건(세부품명·규격·기준 단위·포장 구성, 호환·재생·중고·렌탈 제외)을 만족한 표본만 사용. "
                                "VAT 포함 환산(별도면 ×1.1) · 포장 단위 환산 후, IQR 이상값 제거 중앙값을 기준가로 비교"},
                     tools.normalize_price(q.quoted_price, q.units_per_benchmark, q.vat_included, found["rows"]))
    p = price_verdict(calc["ratio"], calc["samples"])
    trace.add("price_verdict", {"ratio": calc["ratio"], "samples": calc["samples"],
                                "rule": "105% 미만 적정 / 105~120% 검토 필요 / 120% 이상 과다 / 표본 3건 미만 판단 불가"}, p)
    if calc["benchmark"]:
        cite(trace, contexts, "가격 판정")
    if q.units_per_benchmark and q.units_per_benchmark != 1:
        lines.append(f"{q.price_unit}당 {_fmt(q.quoted_price)} × {q.units_per_benchmark:g}{q.price_unit} = {found['unit'] or '기준 단위'}당 {_fmt(calc['package_price'])}로 환산")
        cite(trace, contexts, "단위")
    vat_note = " (견적서에 VAT 표시가 없어 VAT 별도로 가정)" if calc["vat_assumed"] else (" (VAT 별도 → 10% 가산)" if q.vat_included is False else "")
    if calc["vat_assumed"]:
        cite(trace, contexts, "VAT 가정")
    elif q.vat_included is False:
        cite(trace, contexts, "VAT 별도")
    if calc["benchmark"]:
        lines.append(f"견적 VAT 포함 {_fmt(calc['quote_vat'])}{vat_note} / 기준가 {_fmt(calc['benchmark'])} "
                     f"(조달청 쇼핑몰 '{found['matched_spec']}' {calc['samples']}건·{calc['vendors']}개 업체 중앙값) = {calc['ratio']:.0%}")
    else:
        lines.append(f"같은 규격의 조달 표본이 {calc['samples']}건이라 기준가를 정할 수 없음{vat_note}")
    if found["matched_spec"] and found["excluded"]["count"]:
        reasons = ", ".join(f"{r} {n}건" for r, n in found["excluded"]["reasons"].items())
        lines.append(f"비교 조건(기준 단위 '{found['unit']}')에 맞지 않는 표본 제외: {reasons}")
        cite(trace, contexts, "비교 조건")
    return {"verdict": p, "lines": lines}
