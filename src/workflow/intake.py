"""입력 가드 · 질문 해석 · 라우팅 규칙.

- 지시문(간접 인젝션) 탐지, 범위 밖 품목 · 규정 질의 판별은 코드 규칙으로 한다.
- LLM은 질문을 구조화(ParsedQuery)하는 데만 쓴다.
"""
from __future__ import annotations

import re

from ..price.tools import known_detail_names
from ..shared import llm
from ..shared.text import ground_spec
from .prompts import PARSE_PROMPT
from .schemas import ParsedQuery

INJECTION_PATTERNS = [r"시스템\s*지시", r"system\s*prompt", r"무시하고", r"반드시\s*(적정|진행)", r"판정하(고|라)", r"ignore (all|previous)"]

# 2차 개선: 범위 밖 품목은 LLM 분류 전에 규칙으로 먼저 잡는다 (1차 N02·N03 실패 원인)
OUT_OF_SCOPE_RULES = [
    ("용역", r"용역"),
    ("공사", r"공사|시공|인테리어"),
    ("맞춤 제작", r"맞춤|주문\s*제작|제작\s*견적|로고를?\s*새긴|각인"),
    ("중고", r"중고|리퍼|재생품"),
    ("렌탈", r"렌탈|임대|대여"),
]
# 2차 개선: 견적가 없이 규정·기준을 묻는 질문은 규정 질의로 본다 (1차 P08 실패 원인)
POLICY_HINT = r"규정|기준|몇\s*%|퍼센트|얼마나|이상이면|미만이면|언제|어떻게\s*해야|해야\s*(해|하나|돼|되나)|누가|권한|대상이야|조건|절차"
PRICE_IN_TEXT = r"\d[\d,]*\s*(만\s*)?원"


def detect_injection(question: str) -> bool:
    return any(re.search(p, question, flags=re.I) for p in INJECTION_PATTERNS)


def rule_out_of_scope(question: str) -> str | None:
    for kind, pattern in OUT_OF_SCOPE_RULES:
        if re.search(pattern, question):
            return kind
    return None


def rule_policy_question(question: str) -> bool:
    return bool(re.search(POLICY_HINT, question)) and not re.search(PRICE_IN_TEXT, question)


def parse_query(question: str) -> ParsedQuery:
    prompt = PARSE_PROMPT.format(names=", ".join(known_detail_names()), question=question)
    parsed = llm.structured(ParsedQuery).invoke(prompt)
    for q in parsed.quotes:
        q.spec = ground_spec(q.spec, question)
    return parsed
