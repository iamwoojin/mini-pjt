"""경로·환경 설정. 실행 위치와 무관하게 동작하도록 모든 경로는 이 파일 기준 절대 경로로 만든다."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
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

# 판정 기준 (data/docs의 규정 문서와 같은 숫자를 유지할 것)
PRICE_REVIEW_RATIO = 1.05   # 이상이면 검토 필요
PRICE_EXCESS_RATIO = 1.20   # 이상이면 과다
MIN_PRICE_SAMPLES = 3       # 미만이면 판단 불가
VAT_RATE = 0.10
NEWS_LOOKBACK_YEARS = 3
MIN_COMPANY_AGE_YEARS = 1
MIN_EMPLOYEES = 3

# 입력 가드레일: 질문 최대 길이 (비용·시간 보호, 견적 여러 건도 충분한 길이)
MAX_QUESTION_CHARS = 2000
