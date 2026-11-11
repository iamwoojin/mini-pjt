"""판정 규칙 · 가격 환산 · 라우팅 규칙 단위 테스트 (LLM·네트워크 호출 없음).

실행: pytest (mini-pjt 폴더에서)
기준 숫자는 SERVICE.md 4절, src/config.py, data/docs 규정 문서와 같아야 한다.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import agent, config, tools  # noqa: E402

OK_NTS = {"b_stt": "계속사업자", "tax_type": "부가가치세 일반과세자"}
OK_DOCS = {"founded": "2012-03-01", "employees": 42, "docs_complete": True}


# ---------- ① 업체 판정 ----------

@pytest.mark.parametrize("nts", [
    {"b_stt": "휴업자", "tax_type": ""},
    {"b_stt": "폐업자", "tax_type": "", "end_dt": "20250630"},
    {"b_stt": "", "tax_type": "국세청에 등록되지 않은 사업자등록번호입니다."},
])
def test_vendor_unfit_by_nts_status(nts):
    v, _ = agent.vendor_verdict(nts, OK_DOCS, [])
    assert v == "부적합"


@pytest.mark.parametrize("docs, reason", [
    ({**OK_DOCS, "founded": "2026-04-01"}, "설립 1년 미만"),
    ({**OK_DOCS, "employees": 2}, "3명 미만"),
    ({**OK_DOCS, "docs_complete": False}, "제출 서류 누락"),
])
def test_vendor_caution_by_docs(docs, reason):
    v, reasons = agent.vendor_verdict(OK_NTS, docs, [])
    assert v == "주의"
    assert any(reason in r for r in reasons)


def test_vendor_caution_by_same_company_risk_news_only():
    news = [{"title": "압수수색", "date": "2025-06-01", "link": "x", "same_company": True, "risk": True, "status": "의혹"}]
    v, reasons = agent.vendor_verdict(OK_NTS, OK_DOCS, news)
    assert v == "주의"  # 뉴스만으로는 부적합이 되지 않는다
    assert any("의혹" in r for r in reasons)


def test_vendor_ignores_same_name_other_company_news():
    news = [{"title": "횡령", "date": "2025-01-01", "link": "x", "same_company": False, "risk": True, "status": "확정"}]
    v, reasons = agent.vendor_verdict(OK_NTS, OK_DOCS, news)
    assert v == "적합"
    assert any("동명 기업" in r for r in reasons)


# ---------- ② 가격 판정 ----------

@pytest.mark.parametrize("ratio, samples, expected", [
    (1.0499, 10, "적정"),
    (1.05, 10, "검토 필요"),
    (1.1999, 10, "검토 필요"),
    (1.20, 10, "과다"),
    (0.8, 2, "판단 불가"),
    (None, 10, "판단 불가"),
])
def test_price_verdict_boundaries(ratio, samples, expected):
    assert agent.price_verdict(ratio, samples) == expected


def test_price_thresholds_match_config():
    assert (config.PRICE_REVIEW_RATIO, config.PRICE_EXCESS_RATIO, config.MIN_PRICE_SAMPLES) == (1.05, 1.20, 3)


# ---------- 권고표 ----------

@pytest.mark.parametrize("vendor, price, rec, action", [
    ("적합", "적정", "진행", None),
    ("적합", "검토 필요", "조건부", None),
    ("적합", "과다", "보류", "request_requote"),
    ("적합", "판단 불가", "조건부", None),
    ("주의", "적정", "조건부", None),
    ("주의", "검토 필요", "조건부", None),
    ("주의", "과다", "보류", "request_requote"),
    ("부적합", "적정", "보류", "hold_registration"),
    ("부적합", "과다", "보류", "hold_registration"),  # 등록 보류가 재견적보다 우선
    ("확인 불가", "적정", "조건부", None),
    ("확인 불가", "과다", "보류", "request_requote"),
])
def test_recommend_matrix(vendor, price, rec, action):
    r, a, _ = agent.recommend(vendor, price)
    assert (r, a) == (rec, action)


# ---------- 가격 정규화 · 조달 기준가 (fixture) ----------

def test_chair_benchmark_and_vat_normalization():
    found = tools.search_procurement_prices("작업용의자", "595×600×895mm")
    calc = tools.normalize_price(290000, 1, False, found["rows"])
    assert calc["benchmark"] == 216000
    assert calc["quote_vat"] == pytest.approx(319000)
    assert round(calc["ratio"], 2) == 1.48


def test_vat_unknown_is_assumed_excluded():
    found = tools.search_procurement_prices("작업용의자", "595×600×895mm")
    calc = tools.normalize_price(200000, 1, None, found["rows"])
    assert calc["vat_assumed"] is True
    assert calc["quote_vat"] == pytest.approx(220000)


def test_unit_conversion_per_volume_to_box():
    calc = tools.normalize_price(2900, 10, False, [])
    assert calc["package_price"] == pytest.approx(29000)


def test_label_paper_has_too_few_samples():
    found = tools.search_procurement_prices("라벨용지", "1칸 210×297mm")
    assert len(found["rows"]) < config.MIN_PRICE_SAMPLES


# ---------- 라우팅 규칙 (2차 개선) ----------

@pytest.mark.parametrize("q, kind", [
    ("사무실 청소 용역 월 3,000,000원", "용역"),
    ("중고 사무용 의자 10개", "중고"),
    ("회사 로고를 새긴 맞춤 회의용 탁자", "맞춤 제작"),
    ("복사기 렌탈 월 50,000원", "렌탈"),
    ("작업용의자 595×600×895mm 290,000원", None),
])
def test_rule_out_of_scope(q, kind):
    assert agent.rule_out_of_scope(q) == kind


@pytest.mark.parametrize("q, expected", [
    ("견적 가격이 시장가보다 얼마나 비싸면 재견적을 요청해야 해?", True),
    ("재견적 요청은 누가 승인할 수 있어?", True),
    ("알파상사 복사용지 23,000원 견적 기준가 대비 어때?", False),  # 견적가가 있으면 검증 요청
])
def test_rule_policy_question(q, expected):
    assert agent.rule_policy_question(q) is expected


# ---------- 국세청 fixture ----------

def test_fake_numbers_always_use_fixture():
    assert tools.check_business_status("999-99-00003")["source"] == "fixture"
    assert "등록되지 않은" in tools.check_business_status("999-99-99999")["tax_type"]


# ---------- 모델 대체 ----------

def test_llm_has_fallback_model():
    assert len(agent._models()) == 2
    assert config.LLM_FALLBACK_MODEL != config.LLM_MODEL
