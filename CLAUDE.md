# 작업 규칙 (Claude Code가 매 대화 자동으로 읽음)

구매 업체·가격 검증 에이전트 미니 프로젝트. 개인 작업 메모는 `CLAUDE.local.md`(gitignore)에 있다.

## 기준 문서
- 무엇을 만드는지는 `SERVICE.md`가 기준이다. 애매하면 추측하지 말고 물어본다.
- 작업 순서와 완료 확인 방법은 `TASKS.md`를 따른다. 한 번에 TASKS.md의 작업 하나만 한다.
- 기획이 바뀌면 코드보다 `SERVICE.md`·`TASKS.md`를 먼저 고친다. 코드를 먼저 고쳤다면 같은 작업 안에서 문서도 맞춘다.

## 스택
- Python, LangChain/LangGraph, Amazon Bedrock (기본 Claude Haiku 4.5, 실패 시 Sonnet 4.5로 자동 대체), 임베딩 Titan Embed v2, Chroma, FastAPI
- 사용자 허락 없이 새 프레임워크·라이브러리를 들이지 않는다. 새 패키지가 필요하면 먼저 묻는다.

## 원칙
- 계산과 규칙 판정(업체 판정 · 가격 판정 · 권고 · 가격 환산)은 LLM이 아니라 파이썬 코드로 한다. LLM은 질문 해석 · 뉴스 분류 · 규정 답변 작성에만 쓴다.
- 판정 기준 숫자는 `src/shared/config.py`와 `data/docs/*.md` 규정 문서를 같게 유지한다.
- API 키는 `.env`에서 읽는다(`.env.example` 참고). 키·`.env`는 커밋하지 않는다.
- 파일 경로와 하위 프로세스 경로는 실행 위치와 무관하게 `__file__` 기준 절대 경로로 만든다.
- 공개 저장소다. 실제 사내 데이터 · 고객사명 · 공급사명 · 단가를 쓰지 않고, 부적합 사례는 가상 기업으로만 만든다.

## 코드 폴더 구조 (`src/`, 도메인별)
모든 소스 코드는 `src/` 안에 둔다. 폴더는 기술 역할(utils, models)이 아니라 에이전트의 도메인으로 나눈다.

| 폴더 | 역할 |
|---|---|
| `src/workflow/` | 요청 처리 흐름: 입력 가드 · 질문 해석 · 라우팅 규칙(`intake.py`), 개인정보 마스킹(`middleware.py`), LangGraph 그래프 · Supervisor · HITL(`graph.py`) |
| `src/vendor/` | 업체 검증: 국세청 · 뉴스 도구, 뉴스 분류 프롬프트, 업체 판정 규칙, 업체 검증 에이전트 |
| `src/price/` | 가격 검증: 조달 단가 검색 · 비교 조건 · VAT/단위 환산 도구, 가격 판정 규칙, 가격 검증 에이전트 |
| `src/policy/` | 규정 검토: 규정 RAG(`retriever.py`), 판정→근거 조항(`citations.py`), 권고표(`rules.py`), 규정 답변 |
| `src/supplier_data/` | 사내 데이터(공급사 · 견적 · 제출 서류): 원본 조회(`store.py`), MCP 서버 · 클라이언트, 접근 계층(`client.py`) |
| `src/shared/` | 여러 도메인이 함께 쓰는 것만: 설정 · 판정 기준(`config.py`), Bedrock LLM 클라이언트(`llm.py`), 공통 스키마(`schemas.py`), 유틸 |
| `src/api.py` · `agent.py` · `tools.py` · `retriever.py` | 진입 파일(산출물 구조). 구현을 두지 않고 도메인 폴더의 이름만 모아 둔다 |

파일 배치 규칙
- 도메인 폴더 안에는 그 도메인의 실행 로직 · 프롬프트 · 입출력 스키마를 함께 둔다. 파일 이름은 `tools.py`(외부 조회 · 계산 도구), `rules.py`(LLM 없는 판정 규칙, 순수 함수), `agent.py`(도구 → 규칙 → trace를 묶는 하위 에이전트), `prompts.py`, `schemas.py`를 따른다.
- 한 도메인에서만 쓰는 코드는 그 도메인에 둔다. 두 개 이상 도메인이 쓰는 LLM 클라이언트 · 설정 · 유틸만 `shared/`로 올린다. `shared/`는 다른 도메인을 import하지 않는다.
- 도메인 사이 import는 `from ..price.rules import ...`처럼 상대 경로로 하고, 순환 import가 생기면 공통 부분을 `shared/`로 옮긴다.
- 새 도구를 추가하면 도메인의 `tools.py`에 구현하고 `src/tools.py`에서 이름을 다시 내보낸다. 도구 이름은 `evaluation/test_queries.csv`의 expected_tools와 같아야 한다.

## 평가
- `python evaluation/run_eval.py --tag <이름>`으로 `evaluation/test_queries.csv`를 자동 채점한다. 평가는 fixture 모드로 고정한다.
- 1차 결과(`round1`)는 수정하지 않는다. 개선 후에는 새 태그로 다시 돌리고 보고서에 변화를 기록한다.
- 판정 함수를 바꾸면 `pytest`로 단위 테스트를 먼저 돌린다.

## 막혔을 때
- 고치기 전에 원인과 바꿀 파일을 먼저 설명한다.
- 같은 에러를 두세 번 못 고치면 마지막 커밋으로 되돌리고 다시 접근한다.
