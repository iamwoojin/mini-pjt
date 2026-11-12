"""저장된 API 응답 · 가상 데이터(data/fixtures, data/suppliers.json) 읽기 (도메인 공통)."""
from __future__ import annotations

import json
from functools import lru_cache

from . import config


@lru_cache
def load(name: str) -> dict:
    """data/fixtures/<name> JSON"""
    return json.loads((config.FIXTURE_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def suppliers() -> list[dict]:
    """가상 공급사 8곳 (data/suppliers.json)"""
    return json.loads((config.DATA_DIR / "suppliers.json").read_text(encoding="utf-8"))["suppliers"]
