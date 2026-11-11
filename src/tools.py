"""에이전트가 쓰는 도구.

- 도구 이름은 evaluation/test_queries.csv의 expected_tools와 같아야 한다.
- 국세청 상태조회는 config.API_MODE가 LIVE이고 가상 번호(999...)가 아닐 때만 실제 API를 호출한다.
"""
from __future__ import annotations

import csv
import json
import os
import re
import statistics as st
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache

import requests

from . import config

TODAY = datetime(2026, 11, 11)  # 평가 재현성을 위해 기준일 고정


# ---------- 데이터 로드 ----------

@lru_cache
def _suppliers() -> list[dict]:
    return json.loads((config.DATA_DIR / "suppliers.json").read_text(encoding="utf-8"))["suppliers"]


@lru_cache
def _fixture(name: str) -> dict:
    return json.loads((config.FIXTURE_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def _procurement_rows() -> list[dict]:
    with open(config.FIXTURE_DIR / "procurement_prices.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def known_detail_names() -> list[str]:
    return sorted({r["세부품명"] for r in _procurement_rows()})


def find_supplier(name: str | None = None, b_no: str | None = None) -> dict | None:
    digits = re.sub(r"\D", "", b_no or "")
    for s in _suppliers():
        if digits and s["b_no"] == digits:
            return s
    for s in _suppliers():
        if name and s["name"] in name:
            return s
    return None


# ---------- 업체 검증 도구 ----------

def check_business_status(b_no: str) -> dict:
    """국세청 사업자등록 상태조회 → {"b_no","b_stt","tax_type","end_dt","source"}"""
    digits = re.sub(r"\D", "", b_no or "")
    fixture = _fixture("nts_status.json")
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
    items = _fixture("news.json").get(company_name, [])
    cutoff = TODAY - timedelta(days=365 * config.NEWS_LOOKBACK_YEARS)
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


def get_supplier_docs(supplier_id: str) -> dict:
    """제출 서류 조회 → 설립일, 상시 인원, 서류 완비 여부, 소재지·업종(동명 기업 구분용)"""
    for s in _suppliers():
        if s["id"] == supplier_id:
            return {k: s[k] for k in ("id", "name", "region", "industry", "founded", "employees", "docs_complete")}
    return {"id": supplier_id, "docs_complete": False, "founded": None, "employees": None}


def get_quotes(item_keyword: str) -> list[dict]:
    """사내 견적 접수 내역 조회 (공급사 간 비교용)."""
    return [q for q in _fixture("quotes.json")["quotes"] if item_keyword in q["item"]]


# ---------- 가격 검증 도구 ----------

_OPTIONAL_TOKENS = {"일반"}


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", "", t)
    t = t.replace("x", "×").replace("*", "×")
    t = t.replace("g/㎡", "g").replace("g/m2", "g").replace("/상자", "")
    return t


def search_procurement_prices(detail_name: str, spec: str) -> dict:
    """조달청 나라장터쇼핑몰 단가 검색.

    세부품명이 같은 품목 중 규격 토큰이 질의 규격에 모두 들어 있는 규격 묶음을 찾는다(가장 구체적인 묶음 우선).
    반환: {"detail_name","matched_spec","unit","rows":[{"모델","단가","업체키"}],"candidates":[...]}
    """
    rows = [r for r in _procurement_rows() if r["세부품명"] == detail_name]
    q = _norm(spec)
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["규격"], []).append(r)
    best, best_score = None, -1
    candidates = []
    for g_spec, g_rows in groups.items():
        tokens = [_norm(t) for t in g_spec.split(",") if t.strip()]
        required = [t for t in tokens if t not in _OPTIONAL_TOKENS]
        if required and all(t in q for t in required):
            score = sum(len(t) for t in required)
            candidates.append(g_spec)
            if score > best_score:
                best, best_score = g_spec, score
    if best is None:
        return {"detail_name": detail_name, "matched_spec": None, "unit": None, "rows": [], "candidates": []}
    g = groups[best]
    return {
        "detail_name": detail_name,
        "matched_spec": best,
        "unit": g[0]["단위"],
        "rows": [{"모델": r["모델"], "단가": float(r["단가"]), "업체키": r["업체키"]} for r in g],
        "candidates": candidates,
    }


def _iqr_filter(prices: list[float]) -> tuple[list[float], list[float]]:
    if len(prices) < 4:
        return prices, []
    q1, _, q3 = st.quantiles(prices, n=4)
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return [p for p in prices if lo <= p <= hi], [p for p in prices if not lo <= p <= hi]


def normalize_price(quoted_price: float, units_per_benchmark: float, vat_included: bool | None, rows: list[dict]) -> dict:
    """VAT·포장 단위 정규화 후 기준가(IQR 제거 후 중앙값) 대비 비율 계산. 조달 단가는 VAT 포함으로 본다."""
    package_price = quoted_price * (units_per_benchmark or 1)
    vat_assumed = vat_included is None
    quote_vat = package_price if vat_included else package_price * (1 + config.VAT_RATE)
    prices = [r["단가"] for r in rows]
    kept, dropped = _iqr_filter(prices)
    vendors = len({r["업체키"] for r in rows if r["단가"] in kept})
    if len(kept) < config.MIN_PRICE_SAMPLES:
        return {"package_price": package_price, "quote_vat": quote_vat, "vat_assumed": vat_assumed,
                "benchmark": None, "ratio": None, "samples": len(kept), "vendors": vendors, "dropped": len(dropped)}
    median = st.median(kept)
    return {
        "package_price": package_price,
        "quote_vat": round(quote_vat),
        "vat_assumed": vat_assumed,
        "benchmark": median,
        "ratio": quote_vat / median,
        "samples": len(kept),
        "vendors": vendors,
        "dropped": len(dropped),
    }
