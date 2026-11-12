"""Amazon Bedrock LLM 클라이언트 (모든 도메인 공통).

기본 모델(Haiku 4.5)이 한도 초과 · 오류로 실패하면 대체 모델(Sonnet 4.5)로 자동 전환한다.
"""
from __future__ import annotations

from langchain_aws import ChatBedrockConverse

from . import config


def model(model_id: str) -> ChatBedrockConverse:
    return ChatBedrockConverse(model=model_id, region_name=config.AWS_REGION, temperature=0, max_tokens=2000)


def models() -> list[ChatBedrockConverse]:
    ids = [config.LLM_MODEL] + ([config.LLM_FALLBACK_MODEL] if config.LLM_FALLBACK_MODEL and config.LLM_FALLBACK_MODEL != config.LLM_MODEL else [])
    return [model(i) for i in ids]


def llm():
    """기본 모델 → 실패 시 대체 모델 (한도 초과 등으로 중단되지 않게)"""
    primary, *rest = models()
    return primary.with_fallbacks(rest) if rest else primary


def structured(schema):
    """구조화 출력도 모델별로 만든 뒤 대체 체인으로 묶는다"""
    primary, *rest = [m.with_structured_output(schema) for m in models()]
    return primary.with_fallbacks(rest) if rest else primary
