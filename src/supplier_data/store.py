"""사내 데이터 원본 조회 (가상 공급사 · 제출 서류 · 접수 견적).

MCP 서버(mcp_server.py)가 이 함수들을 도구로 노출하고, MCP를 쓸 수 없을 때는 client.py가 직접 호출한다.
"""
from __future__ import annotations

import re

from ..shared import fixtures


def find_supplier(name: str | None = None, b_no: str | None = None) -> dict | None:
    digits = re.sub(r"\D", "", b_no or "")
    for s in fixtures.suppliers():
        if digits and s["b_no"] == digits:
            return s
    for s in fixtures.suppliers():
        if name and s["name"] in name:
            return s
    return None


def get_supplier_docs(supplier_id: str) -> dict:
    """제출 서류 조회 → 설립일, 상시 인원, 서류 완비 여부, 소재지·업종(동명 기업 구분용)"""
    for s in fixtures.suppliers():
        if s["id"] == supplier_id:
            return {k: s[k] for k in ("id", "name", "region", "industry", "founded", "employees", "docs_complete")}
    return {"id": supplier_id, "docs_complete": False, "founded": None, "employees": None}


def get_quotes(item_keyword: str) -> list[dict]:
    """사내 견적 접수 내역 조회 (공급사 간 비교용)."""
    return [q for q in fixtures.load("quotes.json")["quotes"] if item_keyword in q["item"]]
