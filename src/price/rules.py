"""가격 판정 규칙 (LLM이 아닌 코드로 고정, 기준 숫자는 shared/config.py · purchase_rule 규정과 같게 유지)."""
from __future__ import annotations

from typing import Literal

from ..shared import config

PriceVerdict = Literal["적정", "검토 필요", "과다", "판단 불가"]


def price_verdict(ratio: float | None, samples: int) -> PriceVerdict:
    if ratio is None or samples < config.MIN_PRICE_SAMPLES:
        return "판단 불가"
    if ratio >= config.PRICE_EXCESS_RATIO:
        return "과다"
    if ratio >= config.PRICE_REVIEW_RATIO:
        return "검토 필요"
    return "적정"
