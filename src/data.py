"""사내 데이터(공급사 · 견적 · 제출 서류) 접근 계층.

에이전트는 이 모듈만 통해 사내 데이터를 읽는다. 데이터 출처를 바꿔도 에이전트 코드는 그대로다.
"""
from __future__ import annotations

from . import tools


def find_supplier(name: str | None = None, b_no: str | None = None) -> dict | None:
    return tools.find_supplier(name, b_no)


def get_supplier_docs(supplier_id: str) -> dict:
    return tools.get_supplier_docs(supplier_id)


def get_quotes(item_keyword: str) -> list[dict]:
    return tools.get_quotes(item_keyword)
