"""업체 검증 입출력 스키마: 업체 판정 값, 위험 보도 분류(LLM 구조화 출력)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VendorVerdict = Literal["적합", "주의", "부적합", "확인 불가"]


class NewsJudgement(BaseModel):
    index: int
    same_company: bool = Field(description="기사의 기업이 검토 대상 공급사와 같은 회사인가 (소재지·업종으로 판단)")
    risk: bool = Field(description="부도·횡령·영업정지·담합·제재·압수수색·비리 의혹 등 위험 유형인가")
    status: Literal["의혹", "확정", "해당 없음"]


class NewsJudgements(BaseModel):
    items: list[NewsJudgement]
