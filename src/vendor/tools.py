"""업체 검증 도구: 국세청 사업자 상태 조회, 위험 보도 검색.

- 도구 이름은 evaluation/test_queries.csv의 expected_tools와 같아야 한다.
- 국세청 상태조회는 config.API_MODE가 LIVE이고 가상 번호(999...)가 아닐 때만 실제 API를 호출한다.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from ..shared import config, fixtures


def check_business_status(b_no: str) -> dict:
    """국세청 사업자등록 상태조회 → {"b_no","b_stt","tax_type","end_dt","source"}"""
    digits = re.sub(r"\D", "", b_no or "")
    fixture = fixtures.load("nts_status.json")
    if digits in fixture or config.API_MODE != "LIVE" or digits.startswith("999"):
        item = fixture.get(digits) or {
            "b_no": digits, "b_stt": "", "b_stt_cd": "",
            "tax_type": "국세청에 등록되지 않은 사업자등록번호입니다.", "end_dt": "",
        }
        return {**item, "source": "fixture"}
    key = os.getenv("DATA_GO_KR_API_KEY")
    r = requests.post(
        "https://api.odcloud.kr/api/nts-businessman/v1/status",
        params={"serviceKey": key}, json={"b_no": [digits]}, timeout=15,
    )
    r.raise_for_status()
    return {**r.json()["data"][0], "source": "live"}


def search_news(company_name: str) -> list[dict]:
    """위험 보도 검색 → 최근 3년 기사(네이버 뉴스 응답 형식 fixture). 위험 여부 분류는 에이전트(LLM)가 한다."""
    items = fixtures.load("news.json").get(company_name, [])
    today = datetime(config.TODAY.year, config.TODAY.month, config.TODAY.day)
    cutoff = today - timedelta(days=365 * config.NEWS_LOOKBACK_YEARS)
    out = []
    for it in items:
        pub = parsedate_to_datetime(it["pubDate"]).replace(tzinfo=None)
        if pub >= cutoff:
            out.append({
                "title": re.sub(r"</?b>", "", it["title"]),
                "description": re.sub(r"</?b>", "", it["description"]),
                "link": it["originallink"],
                "date": pub.strftime("%Y-%m-%d"),
            })
    return out
