"""경로 · 환경 · 판정 기준 설정 (모든 도메인 공통).

실행 위치와 무관하게 동작하도록 모든 경로는 이 파일 기준 절대 경로로 만든다
(src/shared/config.py → 저장소 루트는 parents[2]).
"""
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
FIXTURE_DIR = DATA_DIR / "fixtures"
WEB_DIR = BASE_DIR / "web"

# 키는 저장소 밖(상위 폴더)의 .env에 둔다. 저장소 안 .env가 있으면 그것도 읽는다.
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

# FIXTURE: 저장된 응답으로 실행(평가용) / LIVE: 실제 API 호출(시연용)
API_MODE = os.getenv("API_MODE", "FIXTURE").upper()

LLM_MODEL = os.getenv("LLM_MODEL", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
# 기본 모델이 한도 초과·오류로 실패하면 자동으로 이 모델로 대체한다
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "global.anthropic.claude-sonnet-4-5-20250929-v1:0")
EMBED_MODEL = os.getenv("EMBED_MODEL", "amazon.titan-embed-text-v2:0")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# 평가 재현성을 위해 판정 기준일을 고정한다 (설립 연수 · 뉴스 최근 3년 계산)
TODAY = date(2026, 11, 11)

# 판정 기준 (data/docs의 규정 문서와 같은 숫자를 유지할 것)
PRICE_REVIEW_RATIO = 1.05   # 이상이면 검토 필요
PRICE_EXCESS_RATIO = 1.20   # 이상이면 과다
MIN_PRICE_SAMPLES = 3       # 미만이면 판단 불가
VAT_RATE = 0.10
NEWS_LOOKBACK_YEARS = 3
MIN_COMPANY_AGE_YEARS = 1
MIN_EMPLOYEES = 3

# 가격 비교 가능 조건 (SERVICE.md '비교 가능 조건' 표 · price_survey 제2조와 같게 유지)
# 아래 조건을 모두 만족한 조달 표본만 기준가(IQR 후 중앙값) 계산에 넣는다.
# spec은 조달 데이터의 규격 문자열과 정확히 같아야 한다. pack은 기준 단위 하나의 포장 구성.
COMPARABLE_CONDITIONS = {
    "I01": {"detail_name": "프린트및복사용지", "spec": "일반, A4, 80g/㎡, 2500매/상자", "unit": "상자", "pack": "2,500매 (낱장 묶음)"},
    "I02": {"detail_name": "프린트및복사용지", "spec": "일반, A4, 80g/㎡, 2500매(250매×10권)/상자", "unit": "상자", "pack": "10권 (권당 250매)"},
    "I03": {"detail_name": "중질지", "spec": "A4, 70g/㎡, 2500매/상자", "unit": "상자", "pack": "2,500매"},
    "I04": {"detail_name": "작업용의자", "spec": "595×600×895mm", "unit": "개", "pack": "1개"},
    "I05": {"detail_name": "캐비닛", "spec": "800×400×800mm", "unit": "개", "pack": "1개"},
    "I06": {"detail_name": "회의용탁자", "spec": "1800×900×720mm, 사각형", "unit": "개", "pack": "1개"},
    "I07": {"detail_name": "이동형파일서랍", "spec": "400×800×720mm, 3단", "unit": "개", "pack": "1개"},
    "I08": {"detail_name": "사무실칸막이", "spec": "1200×30×1160mm", "unit": "개", "pack": "1개"},
    "I09": {"detail_name": "문서세단기", "spec": "270mm", "unit": "대", "pack": "1대"},
    "I10": {"detail_name": "전자복사기", "spec": "흑백30cpm", "unit": "대", "pack": "1대"},
}
# 모델명에 들어 있으면 비교 표본에서 제외 (신품·정품 기준 비교를 위해)
PRICE_EXCLUDE_KEYWORDS = ("호환", "재생", "리필", "중고", "렌탈", "임대")

# 입력 가드레일: 질문 최대 길이 (비용·시간 보호, 견적 여러 건도 충분한 길이)
MAX_QUESTION_CHARS = 2000
