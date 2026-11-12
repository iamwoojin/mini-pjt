"""사내 데이터(공급사 · 견적 · 제출 서류) 접근 계층.

에이전트는 이 모듈만 통해 사내 데이터를 읽는다.
- DATA_SOURCE=mcp (기본): 사내 데이터 MCP 서버(src/supplier_data/mcp_server.py)를 통해 조회
- DATA_SOURCE=local: 같은 함수를 직접 호출 (MCP 서버를 띄울 수 없는 환경용)
MCP 연결에 실패하면 local로 자동 전환하고 source()에 사유를 남긴다.
"""
from __future__ import annotations

import os
import threading

from . import store

_client = None
_source = os.getenv("DATA_SOURCE", "mcp").lower()
_lock = threading.Lock()


def _mcp():
    global _client, _source
    if _source != "mcp":
        return None
    with _lock:
        if _client is None:
            try:
                from .mcp_client import MCPClient
                _client = MCPClient()
            except Exception as e:  # MCP 서버를 띄울 수 없으면 직접 호출로 전환
                _source = f"local (MCP 연결 실패: {type(e).__name__})"
                return None
    return _client


def source() -> str:
    _mcp()
    return _source


def find_supplier(name: str | None = None, b_no: str | None = None) -> dict | None:
    c = _mcp()
    return c.call("find_supplier", {"name": name or "", "b_no": b_no or ""}) if c else store.find_supplier(name, b_no)


def get_supplier_docs(supplier_id: str) -> dict:
    c = _mcp()
    return c.call("get_supplier_docs", {"supplier_id": supplier_id or ""}) if c else store.get_supplier_docs(supplier_id)


def get_quotes(item_keyword: str, supplier_id: str = "") -> list[dict]:
    c = _mcp()
    if c:
        return c.call("get_quotes", {"item_keyword": item_keyword, "supplier_id": supplier_id})
    quotes = store.get_quotes(item_keyword)
    return [q for q in quotes if not supplier_id or q.get("supplier_id") == supplier_id]
