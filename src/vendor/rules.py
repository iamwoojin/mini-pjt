"""업체 판정 규칙 (LLM이 아닌 코드로 고정, 기준 숫자는 shared/config.py · vendor_criteria 규정과 같게 유지)."""
from __future__ import annotations

from datetime import date

from ..shared import config
from .schemas import VendorVerdict


def vendor_verdict(nts: dict, docs: dict, news: list[dict]) -> tuple[VendorVerdict, list[str]]:
    reasons = []
    stt = nts.get("b_stt", "")
    if "등록되지 않은" in nts.get("tax_type", ""):
        return "부적합", ["국세청 조회 결과: 국세청에 등록되지 않은 사업자등록번호"]
    if stt in ("휴업자", "폐업자"):
        return "부적합", [f"국세청 사업자 상태: {stt[:2]}" + (f" (폐업일 {nts.get('end_dt')})" if nts.get("end_dt") else "")]
    reasons.append(f"국세청 사업자 상태: {stt or '확인 불가'}")
    warn = []
    founded = docs.get("founded")
    if founded:
        age = (config.TODAY - date.fromisoformat(founded)).days / 365
        if age < config.MIN_COMPANY_AGE_YEARS:
            warn.append(f"설립 1년 미만 ({founded} 설립)")
        else:
            reasons.append(f"설립 {int(age)}년")
    if docs.get("employees") is not None and docs["employees"] < config.MIN_EMPLOYEES:
        warn.append(f"상시 인원 {docs['employees']}명 (3명 미만)")
    if not docs.get("docs_complete"):
        warn.append("제출 서류 누락")
    risky = [n for n in news if n["same_company"] and n["risk"]]
    for n in risky:
        warn.append(f"위험 보도({n['status']}): {n['title']} ({n['date']}) 출처 {n['link']}")
    excluded = [n for n in news if n["risk"] and not n["same_company"]]
    if excluded:
        reasons.append(f"동명 기업 기사 {len(excluded)}건은 소재지·업종이 달라 제외")
    if not risky:
        reasons.append(f"최근 {config.NEWS_LOOKBACK_YEARS}년 위험 보도 0건")
    if warn:
        return "주의", warn + reasons
    return "적합", reasons
