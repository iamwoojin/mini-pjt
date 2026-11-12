"""에이전트 진입점 (산출물 구조 `src/agent.py`).

실제 구현은 도메인 폴더에 있다. 이 파일은 외부(API · 평가 스크립트 · 테스트)가 쓰는 이름만 모아 둔다.

    workflow/  요청 처리 흐름: 입력 가드 → 개인정보 마스킹 → 질문 해석 → LangGraph(Supervisor · HITL)
    vendor/    업체 검증 에이전트: 국세청 상태 · 위험 보도 · 제출 서류 → 업체 판정
    price/     가격 검증 에이전트: 조달 기준가 · 비교 조건 · VAT/단위 환산 → 가격 판정
    policy/    규정 검토 에이전트: 규정 RAG · 근거 조항 · 업체×가격 권고
    supplier_data/  사내 데이터(공급사 · 견적 · 제출 서류) MCP 서버 · 클라이언트
    shared/    설정 · Bedrock LLM 클라이언트 · 공통 스키마 · 유틸

- 판정 규칙(업체 · 가격 · 권고)은 LLM이 아닌 코드(rules.py)로 고정한다.
- LLM은 질문 해석, 위험 보도 분류, 규정 질의 답변에만 쓴다.
"""
from .policy.agent import policy_review
from .policy.rules import ACTION_LABEL, recommend
from .price.agent import price_check
from .price.rules import price_verdict
from .shared.schemas import QueryRequest, QuoteItem, Trace
from .shared.text import ground_spec
from .vendor.agent import classify_news, vendor_check
from .vendor.rules import vendor_verdict
from .workflow.graph import run
from .workflow.intake import parse_query, rule_out_of_scope, rule_policy_question
from .workflow.middleware import mask_pii
from .workflow.schemas import ParsedQuery

__all__ = [
    "run", "QueryRequest", "QuoteItem", "ParsedQuery", "Trace", "ACTION_LABEL",
    "parse_query", "rule_out_of_scope", "rule_policy_question", "ground_spec", "mask_pii",
    "vendor_check", "classify_news", "vendor_verdict",
    "price_check", "price_verdict",
    "policy_review", "recommend",
]
