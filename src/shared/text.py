"""규격 문자열 정규화 유틸 (질문 해석과 가격 검색이 함께 쓴다)."""
from __future__ import annotations

import re


def norm(text: str) -> str:
    """공백 제거 · 소문자 · 곱셈 기호와 평량 표기 통일"""
    t = (text or "").lower()
    t = re.sub(r"\s+", "", t)
    t = t.replace("x", "×").replace("*", "×")
    t = t.replace("g/㎡", "g").replace("g/m2", "g").replace("/상자", "")
    return t


def ground_spec(spec: str, question: str) -> str:
    """LLM이 질문에 없는 규격 토큰을 지어내면 버린다 (예시 문구를 베끼는 문제 방지)"""
    q = norm(question)
    kept = []
    for t in spec.split():
        if norm(t) in q:
            kept.append(t)
        elif (base := re.sub(r"\(.*?\)", "", t)) and norm(base) in q:
            kept.append(base)  # '2500매(250매×10권)' 중 질문에 있는 '2500매'만 남김
    return " ".join(kept)
