# TASKS

`SERVICE.md` 기준 구현 순서. 한 번에 하나씩 진행하고, 끝나면 확인 방법대로 실행해 본 뒤 체크하고 커밋한다.

## 1묶음 · 최소 경로 (입력 → 이중 검증 → 답변) — 완료

- [x] T01 기획: `SERVICE.md` 5개 섹션, `evaluation/test_queries.csv` 20건(positive 40% · negative 20% · edge 25% · guardrail 15%)
  - 확인: CSV 7개 컬럼, 카테고리 비율이 note와 일치
- [x] T02 데이터: 가상 공급사 8곳, 국세청·뉴스 fixture, 조달청 단가 추출(`scripts/extract_procurement.py` → 776행), 규정 문서 5종 37조항
  - 확인: `python scripts/extract_procurement.py`가 품목별 IQR 후 중앙값을 출력 (예: 작업용의자 216,000원)
- [x] T03 도구 7종 (`src/tools.py`, `src/retriever.py`)
  - 확인: `search_procurement_prices("작업용의자", "595×600×895mm")`가 같은 규격 행을 반환
- [x] T04 판정 규칙(업체 · 가격 · 권고)을 코드 순수 함수로 구현 (`src/agent.py`)
  - 확인: `pytest tests/test_rules.py` 통과
- [x] T05 `POST /query` + trace + 규정 인용 (`src/api.py`)
  - 확인: 베타산업 작업용의자 290,000원 요청 → 가격 과다 148% · 보류 · `purchase_rule#7` 인용
- [x] T06 가드레일 G1~G5, HITL 승인 흐름(`pending_approval` → `approval`)
  - 확인: 공급사 권한으로 타사 금액 요청 시 거절, 임직원 승인 시도는 거부됨
- [x] T07 테스트 화면 (`web/index.html`)
  - 확인: `uvicorn src.api:app --port 8000` 후 http://localhost:8000 에서 예시 칩 실행
- [x] T08 1차 평가 + 보고서
  - 확인: `evaluation/results/round1.json` 17/20, `evaluation/round1_report.md`
- [x] T09 2차 개선(확인 불가 판정 · 범위 밖 규칙 검사 · 규정 질의 라우팅 · `mode: policy`) + 2차 평가
  - 확인: `python evaluation/run_eval.py --tag round2` → 20/20, `evaluation/round2_report.md`

## 2묶음 · 안정성 · 재현성

- [x] T10 작업 규칙 `CLAUDE.md`(공개) / 개인 메모 `CLAUDE.local.md`(비공개) 분리, `.env.example`
  - 확인: `git status`에 `CLAUDE.local.md`, `.env`가 나오지 않음
- [x] T11 LLM 모델 자동 대체 (Haiku 4.5 실패 시 Sonnet 4.5)
  - 확인: `LLM_MODEL`을 없는 모델 ID로 바꿔 실행해도 답변이 나오고, 단위 테스트에서 대체 체인이 구성됨
- [x] T12 pytest 단위 테스트 (판정 함수 · 가격 환산 · 규칙 라우팅, LLM 호출 없음)
  - 확인: `pytest` 전체 통과, 실행 10초 이내

## 3묶음 · 평가 보강 (P1)

- [x] T13 RAGAS(faithfulness · context_recall) 측정, 정답은 `evaluation/ragas_references.json`
  - 확인: `evaluation/results/ragas_round4.json` 생성, 보고서에 점수 기록 (목표 0.8 → 결과 0.974 / 1.000)
- [x] T14 LLM-as-Judge (근거 충실성 · 이중 검증 완결성, 5점 척도)
  - 확인: 평균 점수가 보고서에 기록 (목표 4/5 → 결과 4.92)

## 4묶음 · 에이전트 구조 (P1)

- [x] T15 LangGraph 그래프로 전환 (입력 가드 → 해석 → 검증 → 답변 노드), 응답 형식은 그대로
  - 확인: `run_eval.py --tag round3`가 round2와 같은 통과율 (결과: round3·round4 20/20)
- [x] T16 HITL을 LangGraph `interrupt` + 체크포인터로 전환
  - 확인: 승인 대기 → 같은 `thread_id`로 approve 시 재개, 임직원 승인은 거부
- [ ] T17 Supervisor: 업체 검증 / 가격 검증 / 규정 검토 하위 에이전트
  - 확인: trace에 하위 에이전트별 단계가 남고 round3 통과율 유지
- [ ] T18 MCP 서버로 공급사 · 견적 · 제출 서류 제공
  - 확인: MCP 서버를 띄운 상태에서 같은 질문의 결과가 동일

## 5묶음 · 제출

- [ ] T19 README 최종화(실행 방법, 결과 요약, 시연 캡처)
  - 확인: 새 폴더에 clone → `.env` 작성 → README 순서대로 실행 성공
- [ ] T20 GitHub 공개 저장소 push, Google Form 제출 (2026-11-13 15:00 마감)
  - 확인: 로그인하지 않은 브라우저에서 저장소가 열림

## 나중에 (P2, 시간 남으면)

- [ ] 공급사 간 견적 비교(`get_quotes` 활용, P07 도구 정확도)
- [ ] 장기 메모리(SQLite): 공급사별 검증 이력, 담당자 선호
- [ ] 다품목 견적 Plan-Execute
- [ ] 국세청 LIVE 시연
