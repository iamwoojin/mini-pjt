"""요청 처리 흐름 스키마: 질문 해석 결과(LLM 구조화 출력)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..shared.schemas import QuoteItem


class ParsedQuery(BaseModel):
    intent: Literal["verify", "policy_question", "other_supplier_info", "out_of_scope_item", "unrelated"] = Field(
        description="verify=견적·업체 검증 요청, policy_question=구매 규정·기준 질문, other_supplier_info=다른 공급사의 금액·순위 요청, "
                    "out_of_scope_item=용역·공사·맞춤 제작·중고 품목 견적, unrelated=서비스와 무관한 질문")
    out_of_scope_type: Literal["용역", "공사", "맞춤 제작", "중고", "렌탈"] | None = None
    requests_action: bool = Field(False, description="사용자가 재견적 요청·등록 보류 같은 조치 실행을 요구하면 true")
    quotes: list[QuoteItem] = Field(default_factory=list)
