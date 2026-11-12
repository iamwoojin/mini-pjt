"""판정 → 근거 조항 매핑과 인용.

판정 규칙이 코드로 고정되어 있으므로 근거 조항도 코드로 고정한다 (3차 개선). 업체 · 가격 · 규정 검토 에이전트가 함께 쓴다.
"""
from __future__ import annotations

from ..shared.schemas import Trace
from . import retriever

CLAUSE = {
    "부적합": ["vendor_criteria#2"],
    "주의": ["vendor_criteria#7"],
    "설립": ["vendor_criteria#3"],
    "인원": ["vendor_criteria#4"],
    "서류": ["vendor_criteria#5"],
    "위험 보도": ["vendor_criteria#6", "news_guide#4", "news_guide#5"],
    "동명": ["news_guide#3"],
    "가격 판정": ["purchase_rule#5", "price_survey#5"],
    "과다": ["purchase_rule#7"],
    "검토 필요": ["purchase_rule#8"],
    "판단 불가": ["purchase_rule#6", "price_survey#6"],
    "VAT 가정": ["purchase_rule#10"],
    "VAT 별도": ["price_survey#3"],
    "단위": ["price_survey#4"],
    "비교 조건": ["price_survey#2"],
    "조치 권한": ["purchase_rule#9"],
    "범위 밖": ["purchase_rule#2"],
    "공급사 비공개": ["security_policy#2"],
    "지시문": ["security_policy#4"],
}


def cite(trace: Trace, contexts: dict, *keys: str) -> None:
    """판정 키에 연결된 조항을 정확히 가져와 근거로 붙인다"""
    ids = [i for k in keys for i in CLAUSE.get(k, []) if i not in contexts]
    if not ids:
        return
    hits = trace.add("search_policy", {"doc_ids": ids, "for": list(keys)}, retriever.get_clauses(ids))
    contexts.update({h["doc_id"]: h for h in hits})
