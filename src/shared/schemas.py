"""여러 도메인이 함께 쓰는 입출력 스키마: API 요청, 견적 1건, trace 기록."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["buyer", "employee", "supplier"]


class QueryRequest(BaseModel):
    question: str
    role: Role = "buyer"
    supplier_id: str | None = None
    thread_id: str | None = None
    approval: Literal["approve", "reject"] | None = None
    mode: Literal["auto", "policy"] = "auto"  # policy: 화면의 [규정 질문하기] → 견적 해석 없이 규정 질의로 처리


class QuoteItem(BaseModel):
    supplier_name: str | None = Field(None, description="견적을 낸 공급사 이름")
    b_no: str | None = Field(None, description="사업자등록번호 (숫자와 하이픈 그대로)")
    item_text: str = Field(description="견적 품목 원문 표현")
    detail_name: str | None = Field(None, description="조달 세부품명 목록 중 가장 맞는 값. 맞는 것이 없으면 null")
    spec: str = Field("", description="질문에 적힌 규격 표현을 빠짐없이 그대로 옮긴다: 등급·용지 크기·평량·매수와 괄호 속 포장 구성, 치수, 형태, 성능. "
                                     "품목명·수량·가격은 빼고, 질문에 없는 규격은 추가하지 않는다 "
                                     "(예: 'B4 75g 1000매(500매×2권)', '600×500×900mm', '원형', '컬러20cpm', '2칸 99×38mm')")
    quoted_price: float | None = Field(None, description="견적서에 적힌 단가 숫자 (price_unit 1단위당)")
    price_unit: str | None = Field(None, description="견적 단가의 단위 (개, 상자, 권, 대 등)")
    units_per_benchmark: float = Field(1, description="기준 단위(상자/개/대) 하나에 들어가는 price_unit 수. 예: 권당 가격이고 1상자=10권이면 10, 같은 단위면 1")
    vat_included: bool | None = Field(None, description="VAT 포함이면 true, 별도면 false, 표시가 없으면 null")


class Trace:
    """응답의 trace: [{"step","input","output"}]"""

    def __init__(self):
        self.steps: list[dict] = []

    def add(self, step: str, inp, out):
        self.steps.append({"step": step, "input": inp, "output": out})
        return out
