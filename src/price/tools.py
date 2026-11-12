"""가격 검증 도구: 조달청 단가 검색(비교 가능 조건 필터), VAT · 포장 단위 정규화.

- 도구 이름은 evaluation/test_queries.csv의 expected_tools와 같아야 한다.
- 비교 가능 조건 · 판정 기준 숫자는 shared/config.py · price_survey 규정과 같게 유지한다.
"""
from __future__ import annotations

import csv
import statistics as st
from functools import lru_cache

from ..shared import config
from ..shared.text import norm

_OPTIONAL_TOKENS = {"일반"}


@lru_cache
def _procurement_rows() -> list[dict]:
    with open(config.FIXTURE_DIR / "procurement_prices.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def known_detail_names() -> list[str]:
    return sorted({r["세부품명"] for r in _procurement_rows()})


def search_procurement_prices(detail_name: str, spec: str) -> dict:
    """조달청 나라장터쇼핑몰 단가 검색.

    세부품명이 같은 품목 중 규격 토큰이 질의 규격에 모두 들어 있는 규격 묶음을 찾는다(가장 구체적인 묶음 우선).
    반환: {"detail_name","matched_spec","unit","rows":[{"모델","단가","업체키"}],"candidates":[...]}
    """
    rows = [r for r in _procurement_rows() if r["세부품명"] == detail_name]
    q = norm(spec)
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["규격"], []).append(r)
    best, best_score = None, -1
    candidates = []
    for g_spec, g_rows in groups.items():
        tokens = [norm(t) for t in g_spec.split(",") if t.strip()]
        required = [t for t in tokens if t not in _OPTIONAL_TOKENS]
        if required and all(t in q for t in required):
            score = sum(len(t) for t in required)
            candidates.append(g_spec)
            if score > best_score:
                best, best_score = g_spec, score
    if best is None:
        return {"detail_name": detail_name, "matched_spec": None, "unit": None, "rows": [], "candidates": [],
                "condition": None, "excluded": {"count": 0, "reasons": {}}}
    kept, condition, excluded = _apply_comparable_condition(detail_name, best, groups[best])
    return {
        "detail_name": detail_name,
        "matched_spec": best,
        "unit": condition["unit"],
        "rows": [{"모델": r["모델"], "단가": float(r["단가"]), "업체키": r["업체키"]} for r in kept],
        "candidates": candidates,
        "condition": condition,
        "excluded": excluded,
    }


def _apply_comparable_condition(detail_name: str, spec: str, rows: list[dict]) -> tuple[list[dict], dict, dict]:
    """규격이 일치한 묶음에서 비교 가능 조건(config.COMPARABLE_CONDITIONS)을 만족한 표본만 남긴다.

    - 고정 조건이 있는 품목: 그 기준 단위와 다른 단가 단위는 제외
    - 고정 조건이 없는 품목: 묶음 안에서 가장 많은 단위를 기준 단위로 삼고 나머지는 제외
    - 모델명에 호환·재생·리필·중고·렌탈·임대가 들어 있으면 제외
    반환: (남은 행, 적용 조건, {"count": 제외 수, "reasons": {사유: 건수}})
    """
    fixed = next((dict(c, item_id=k) for k, c in config.COMPARABLE_CONDITIONS.items()
                  if c["detail_name"] == detail_name and c["spec"] == spec), None)
    if fixed:
        condition = {"item_id": fixed["item_id"], "detail_name": detail_name, "spec": spec,
                     "unit": fixed["unit"], "pack": fixed["pack"], "fixed": True}
    else:
        units = [r["단위"] for r in rows]
        unit = max(dict.fromkeys(units), key=units.count)  # 동률이면 먼저 나온 단위
        condition = {"item_id": None, "detail_name": detail_name, "spec": spec, "unit": unit, "pack": None, "fixed": False}

    kept, reasons = [], {}
    for r in rows:
        keyword = next((k for k in config.PRICE_EXCLUDE_KEYWORDS if k in r["모델"]), None)
        if r["단위"] != condition["unit"]:
            reason = f"단가 단위 불일치({r['단위']})"
        elif keyword:
            reason = f"제외 품목({keyword})"
        else:
            kept.append(r)
            continue
        reasons[reason] = reasons.get(reason, 0) + 1
    return kept, condition, {"count": len(rows) - len(kept), "reasons": reasons}


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
