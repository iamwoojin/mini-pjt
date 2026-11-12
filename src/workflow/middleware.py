"""개인정보 마스킹 미들웨어 (security_policy 제5조): LLM에 보내기 전에 가리고, 응답 출구에서 한 번 더 가린다.

사업자번호(3-2-5자리, 첫 자리 0 아님)와 금액(쉼표 구분)은 패턴에 걸리지 않는다.
"""
from __future__ import annotations

import re

PII_RULES = [
    ("주민번호", "[주민번호]", re.compile(r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\s?-?\s?[1-4]\d{6}(?!\d)")),
    ("전화번호", "[전화번호]", re.compile(r"(?<![\d-])0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?![\d-])")),
    ("이메일", "[이메일]", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
]


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """주민번호 · 전화번호 · 이메일을 가린다. 반환: (가린 문자열, {유형: 건수})"""
    if not isinstance(text, str) or not text:
        return text, {}
    counts = {}
    for kind, label, pattern in PII_RULES:
        text, n = pattern.subn(label, text)
        if n:
            counts[kind] = n
    return text, counts
