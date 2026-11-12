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
- [x] T17 Supervisor: 업체 검증 / 가격 검증 / 규정 검토 하위 에이전트
  - 확인: trace에 하위 에이전트별 단계가 남고 round3 통과율 유지 (결과: round5 20/20)
- [x] T18 MCP 서버로 공급사 · 견적 · 제출 서류 제공
  - 확인: MCP 서버를 띄운 상태에서 같은 질문의 결과가 동일 (결과: trace에 `via: mcp`, round5 20/20)

## 5묶음 · 보완 (2026-11-12, 위에서부터 하나씩)

- [x] T24 가격 비교 조건 고정 (강사 피드백 반영, 2026-11-11 SERVICE.md 검토)
  - 피드백: "같은 제품명이어도 규격과 포장 수량이 다르면 기준가가 달라질 수 있으니 테스트 품목 10종부터 비교 가능한 조건을 고정하고, 그 조건을 만족한 표본만 중앙값 계산에 넣으면 가격 판정 근거가 더 분명해진다"
  - 점검 결과: 세부품명+규격 일치는 이미 적용됨. 다만 같은 규격 묶음 안의 단위 혼입(예: 라벨용지 168×107mm에 '매' 4건 + '롤' 1건)이 걸러지지 않고, 품목별 비교 조건이 문서에 없으며, 조건 미충족 제외 사유가 trace에 남지 않음
  - 할 일: SERVICE.md·`price_survey` 제2조에 품목 10종 비교 조건표(세부품명 · 규격 · 기준 단위 · 포장 수량 · 제외 조건) → `config.py` 상수화 → `tools.py`에서 기준 단위가 다른 행 제외 + 사유 반환 → trace에 "조건 충족 n건 / 제외 m건(사유)" 기록
  - 확인: 단위 혼입 묶음에서 다른 단위 표본이 제외되고 사유가 남음, 고정 조건 10종은 표본 수 변화 없음, I01·I02 분리 유지 단위 테스트 추가 → `pytest` 통과 → `run_eval.py --tag round6` 20/20 유지, round2_report.md에 "강사 피드백 반영" 항목으로 기록 (결과: pytest 59건, round6 20/20, 답변 20건 round5와 동일, 라벨용지 '롤' 1건 제외 확인)
- [x] T21 Judge 감점 2건 보완: P08 답변에 105~120% 구간 설명, N01 규정 답변에 조항 번호 표시
  - 확인: `pytest` 통과 → `run_eval.py --tag round7` 20/20 유지 → `run_judge.py` 점수가 4.92 이상, round2_report.md에 기록
  - 진행(2026-11-12): 수정 · pytest 59건 · round7 20/20 · RAGAS 0.972/1.000 완료. Judge 재측정 완료: 4.92 → **5.00** (Sonnet 4.5, us-east-1 한도로 us-west-2에서 실행, `judge_round7.json`)
- [x] T22 개인정보 마스킹: 질문·답변·trace의 전화번호·이메일·주민번호 형태를 가림
  - 확인: 단위 테스트 추가, 마스킹 질문 1건이 응답과 trace 모두에서 가려짐, `--tag round8` 통과율 유지 (결과: 입구(LLM 전)·출구 마스킹, 사업자번호 예외, pytest 72건, round8 20/20 · 답변 round7과 동일, 종단 확인 원본 0건)
- [x] T25 코드 폴더를 도메인별로 재구성 (`src/workflow · vendor · price · policy · supplier_data · shared`)
  - 확인: 판정 로직은 위치만 옮김, `src/agent.py` · `tools.py` · `retriever.py` · `api.py`는 산출물 구조(4-1) 진입 파일로 유지, CLAUDE.md에 폴더 역할 · 배치 규칙 정의 → `pytest` 72건 → `run_eval.py --tag round9` 20/20, 답변 · trace 단계가 round8과 같음 → 다른 폴더에서 실행해도 MCP 연결 → 서버 승인 흐름 (결과: 모두 통과, 2026-11-12)
- [ ] T23 (시간 남으면) 장기 메모리(SQLite): 공급사별 검증 이력 저장 · 조회 (판정은 바꾸지 않고 참고 근거로만 표시, supplier는 자사 이력만)
  - 확인: 같은 공급사를 두 번 검증하면 두 번째 답변에 이전 이력이 표시됨, 평가 전 리셋, 새 태그로 통과율 유지

## 6묶음 · 제출 (2026-11-13 오전)

- [ ] T19 README 최종화(실행 방법, 결과 요약, 시연 캡처)
  - 확인: 새 폴더에 clone → `.env` 작성 → README 순서대로 실행 성공
  - 진행(2026-11-12): README 초안 · `docs/DEMO.md` 시연 체크리스트 완료. clone 검증 통과(새 venv 설치 → pytest 72건 → 서버 · 화면 · 승인 흐름 → run_eval 20/20 재현). 검증 중 README 보완: venv 생성 단계, Windows 한글 curl 인코딩 오류 안내 + PowerShell 예시, 승인 요청에 `question` 필요. **남은 것: 시연 캡처 5장** (Judge 점수는 README 반영 완료)
- [ ] T20 GitHub 공개 저장소 push, Google Form 제출 (2026-11-13 15:00 마감)
  - 확인: 로그인하지 않은 브라우저에서 저장소가 열림
  - 키는 올리지 않는다: 공개 전 `git log -p` 전체에서 AWS · 국세청 · LangSmith 키 패턴이 없는지 다시 검사, `.env`가 추적되지 않는지 확인, 시연 캡처에 `.env` · 키가 찍힌 화면이 없는지 확인. 강사가 실행에 키가 필요하면 저장소가 아닌 별도 경로로 전달하고 과정 종료 후 폐기. 실수로 올라가면 이력 삭제가 아니라 **키 폐기 · 재발급**이 우선
  - 제출물: Git URL + ZIP. ZIP은 최종 커밋 후 `git archive --format=zip -o ../mini-pjt.zip HEAD`로 만든다(커밋된 파일만, 약 180KB). 폴더 통째 압축 금지(`CLAUDE.local.md`, `data/raw/` 193MB, `.git` 포함됨)

## 나중에 (P2, 시간 남으면)

- [ ] 공급사 간 견적 비교(`get_quotes` 활용, P07 도구 정확도)
- [ ] 장기 메모리 확장: 담당자 선호(품목군 · 답변 형식)
- [ ] 다품목 견적 Plan-Execute
- [ ] 국세청 LIVE 시연
