"""권고 규칙: 업체 판정 × 가격 판정 → 권고 · 조치 (LLM이 아닌 코드로 고정한 순수 함수)."""
from __future__ import annotations

from typing import Literal

from ..price.rules import PriceVerdict
from ..vendor.schemas import VendorVerdict

Recommendation = Literal["진행", "조건부", "보류"]

ACTION_LABEL = {"hold_registration": "등록 보류", "request_requote": "재견적 요청"}


def recommend(vendor: VendorVerdict, price: PriceVerdict) -> tuple[Recommendation, str | None, str]:
    """업체 × 가격 → (권고, 조치, 사유)"""
    if vendor == "부적합":
        return "보류", "hold_registration", "업체 부적합"
    if price == "과다":
        return "보류", "request_requote", "가격 과다"
    if vendor == "확인 불가":
        return "조건부", None, "사업자번호 확인 후 업체 검증 필요"
    if price == "판단 불가":
        return "조건부", None, "가격 수동 확인"
    if vendor == "적합" and price == "적정":
        return "진행", None, "업체·가격 모두 이상 없음"
    if vendor == "주의" and price == "검토 필요":
        return "조건부", None, "추가 서류 + 가격 협의"
    if vendor == "주의":
        return "조건부", None, "추가 서류 확인"
    return "조건부", None, "가격 협의"
