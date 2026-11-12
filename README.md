# 구매 업체·가격 검증 에이전트

공급사 견적 한 건에 대해 **업체 검증**(국세청 사업자 상태·뉴스·제출 서류)과 **가격 검증**(조달청 나라장터쇼핑몰 동일 규격 단가)을 모두 수행하고, 진행 / 조건부 / 보류를 사내 규정 근거와 함께 권고하는 에이전트입니다. 재견적 요청·등록 보류 같은 조치는 구매 담당자가 승인해야만 진행됩니다.

- 서비스 기획(사용자·문제·가치, 정책, 성공 기준): [SERVICE.md](SERVICE.md)
- 평가 보고서: [1차](evaluation/round1_report.md) · [2차 이후](evaluation/round2_report.md)

```
질문: 베타산업(999-99-00002) 견적: 작업용의자 595×600×895mm 1개 290,000원(VAT 별도). 진행해도 될까?

업체 판정: 적합 / 주의 / 부적합   ← 국세청 상태 · 위험 보도 · 설립일 · 인원 · 서류 (코드 규칙)
가격 판정: 적정 / 검토 필요 / 과다 / 판단 불가   ← VAT · 포장 단위 환산 후 같은 규격 조달 단가 중앙값 대비 비율
권고: 진행 / 조건부 / 보류  + 근거 규정 [purchase_rule#7] ...
다음 조치: 재견적 요청 — 구매 담당자 승인 후 실행됩니다.
```

## 결과 요약

| 지표 | 1차 (round1) | 최종 (round8) | 목표 |
|---|---|---|---|
| 테스트 세트 통과율 (20건) | 17/20 (85%) | **20/20 (100%)** | 85% 이상 |
| guardrail | 3/3 (100%) | **3/3 (100%)** | 100% |
| 도구 정확도 | 95.5% | 97.7% | 90% 이상 |
| RAGAS faithfulness / context_recall | - | **0.972 / 1.000** (round7) | 0.8 이상 |
| LLM-as-Judge (5점) | - | **4.92** (round5) · round7 재측정 예정 | 4 이상 |
| 응답 시간 중앙값 | 2.9초 | 2.8초 | 20초 이내 |
| 단위 테스트 (pytest) | - | **72건 통과** | - |

### 개선 이력

| 라운드 | 무엇을 고쳤나 | 결과 |
|---|---|---|
| round2 | 1차 실패 3건 원인 수정: 정보 부족을 '부적합'으로 오판 → '확인 불가', 범위 밖 품목 규칙 검사 선행, 규정 질의 분류 보정 | 85% → **100%**, 업체에 불리한 오판 2건 → 0건 |
| round3 | LangGraph 전환(HITL interrupt), 질문 해석 LLM이 예시 규격을 베껴 틀린 기준가를 쓰던 문제(테스트는 통과했지만 답변을 직접 읽고 발견) | P01 기준가 정정 |
| round4 | 판정 결과·근거 조항을 코드로 고정하고 trace에 판정 기록 | RAGAS faithfulness 0.549 → **0.974** |
| round5 | Supervisor(업체·가격 검증 병렬 배분) + 사내 데이터 MCP 서버 | 품질 유지 (구조 개선) |
| round6 | **강사 피드백 반영 — 가격 비교 조건 고정**: 품목 10종의 세부품명·규격·기준 단위·포장 구성을 고정하고 조건을 만족한 표본만 중앙값에 사용, 제외 사유 기록 | 단위가 섞인 표본 제외 (예: 라벨용지 '롤' 1건) |
| round7 | LLM-as-Judge 감점 2건 보완: 규정 답변에 구간별 절차, 범위 밖 안내에 조항 인용 | 감점 원인 해소 |
| round8 | 개인정보 마스킹 미들웨어: LLM 호출 전 주민번호·전화번호·이메일 마스킹 (사업자번호는 유지) | 응답·trace 원본 0건 |

## 시연

> 캡처는 `docs/screenshots/`에 둔다 (11/13 시연 후 추가). 장면별 입력과 순서: [docs/DEMO.md](docs/DEMO.md)

| 장면 | 캡처 |
|---|---|
| ① 정상 견적 → 진행 | `docs/screenshots/01_proceed.png` |
| ② 가격 과다 → 보류 + 재견적 요청 승인 대기 → 구매 담당자 승인 | `docs/screenshots/02_hitl.png` |
| ③ 부적합 업체(국세청 폐업) → 등록 보류 | `docs/screenshots/03_vendor.png` |
| ④ 가드레일: 공급사가 타사 견적 요청 → 차단 | `docs/screenshots/04_guardrail.png` |
| ⑤ trace: 단계별 입력·출력과 판정 규칙 | `docs/screenshots/05_trace.png` |

## 동작 흐름

```
POST /query ─ 개인정보 마스킹 ─ 입력 가드레일 ─ 질문 해석(LLM, Pydantic 구조화 출력) + 규칙 라우팅
   ├─ 규정 질의      → 규정 RAG(Chroma, 조항 단위) → 답변 + [doc_id] 인용
   ├─ 공급사 타사 조회 → 차단 (G1)
   ├─ 범위 밖 품목    → 안내 (용역·공사·맞춤 제작·중고·렌탈)
   └─ 견적 검증 → Supervisor ─┬─ 업체 검증 에이전트 (국세청 · 뉴스 LLM 분류 · 제출 서류 → 코드 판정)
                              └─ 가격 검증 에이전트 (조달 단가 검색 · 비교 조건 필터 · VAT/단위 환산 · IQR 중앙값 → 코드 판정)
                                       ↓
                              규정 검토 에이전트 (권고표 · 근거 조항 · 조치 제안)
                                       ↓
                              조치가 있으면 승인 대기(interrupt) → 구매 담당자 승인/거부 → 재개
```

- **판정은 LLM이 아니라 코드**가 한다(업체 판정 · 가격 판정 · 권고 · 가격 환산). LLM은 질문 해석, 뉴스 분류, 규정 답변 작성에만 쓴다.
- 판정 기준 숫자는 [src/config.py](src/config.py)와 [data/docs/](data/docs/) 규정 문서가 같다.

### 사용한 패턴

| 패턴 | 구현 |
|---|---|
| LCEL + Pydantic 구조화 출력 | 질문 해석 `ParsedQuery` (공급사 · 품목 · 규격 · 견적가 · 단위 · VAT) |
| RAG | 규정 5개 문서를 조항 단위로 Chroma에 저장, `doc_id = 파일#조항`, 판정별 근거 조항은 코드로 고정 |
| 도구 다중 사용 | `check_business_status` · `search_news` · `get_supplier_docs` · `get_quotes` · `search_procurement_prices` · `normalize_price` · `search_policy` |
| MCP | 공급사 · 견적 · 제출 서류를 사내 데이터 MCP 서버(`src/mcp_server.py`)로 제공, 실패 시 직접 호출로 전환 |
| 가드레일 | G1 타사 정보 차단 · G2 조치 자동 실행 금지 · G3 견적서 속 지시문 무시 · G4 근거 부족 시 판정 보류 · G5 범위 밖 안내 · 개인정보 마스킹 |
| HITL | LangGraph `interrupt` + 체크포인터, 재개 전 구매 담당자 권한 확인 |
| 미들웨어 | 개인정보 마스킹, 규격 매칭 실패 시 재검색, 모델 자동 대체(Haiku 4.5 → Sonnet 4.5) |
| Supervisor | 견적마다 업체 · 가격 검증 에이전트를 병렬 배분(`Send`), 규정 검토 에이전트가 결합 |
| Trace | 모든 단계의 입력 · 출력 · 적용 규칙을 응답 `trace`에 기록 |
| 평가 | 테스트 세트 자동 채점, RAGAS, LLM-as-Judge(답변 모델과 다른 모델) |

## 구조

```
src/        graph.py(LangGraph: 마스킹 · 라우팅 · Supervisor · 하위 에이전트 병렬 · 승인 대기 interrupt)
            agent.py(판정 규칙 · 하위 에이전트 작업 · 프롬프트 · 근거 조항) · tools.py(도구) · config.py(판정 기준 · 비교 조건)
            data.py · mcp_server.py · mcp_client.py(사내 데이터 MCP) · retriever.py(규정 RAG) · api.py(POST /query)
data/       suppliers.json(가상 공급사) · docs/(사내 규정 더미 5개) · fixtures/(조달 단가 추출본, 국세청·뉴스 fixture)
scripts/    extract_procurement.py(조달청 원본 CSV → 테스트 품목 추출)
evaluation/ test_queries.csv · run_eval.py · run_ragas.py · run_judge.py · ragas_references.json · results/ · 보고서
tests/      test_rules.py(판정 규칙 · 비교 조건 · 마스킹 단위 테스트, LLM 호출 없음)
web/        index.html(테스트 화면)
```

## 실행

```bash
python -m venv .venv                     # Python 3.12+ (3.14에서 확인)
source .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -r requirements.txt          # 서비스 실행 + 단위 테스트
cp .env.example .env                     # AWS 키 입력 (국세청 LIVE 조회 시 DATA_GO_KR_API_KEY)
pytest                                   # 단위 테스트 72건 (LLM 호출 없음, 수 초)
python -m uvicorn src.api:app --port 8000   # http://localhost:8000 테스트 화면
```

- 첫 질문 때 규정 문서 인덱스(`chroma_db/`)를 자동으로 만든다 (임베딩 호출 때문에 몇 초 더 걸림).
- 테스트 화면에서 역할 버튼(구매 담당자 · 임직원 · 공급사)을 고르고 견적을 넣어 [검증하기]를 누른다. 장면별 예시: [docs/DEMO.md](docs/DEMO.md)

명령줄에서 호출할 때 (macOS · Linux):

```bash
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
     -d '{"question": "베타산업(999-99-00002) 견적: 작업용의자 595×600×895mm 1개 290,000원(VAT 별도). 진행해도 될까?"}'
# 승인 대기 응답의 thread_id로 승인 (question은 빈 문자열이라도 필요)
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
     -d '{"question": "", "thread_id": "<응답의 thread_id>", "approval": "approve", "role": "buyer"}'
```

Windows의 Git Bash · cmd에서는 명령줄의 한글이 UTF-8로 전송되지 않아 `There was an error parsing the body`가 날 수 있다. 질문을 UTF-8 JSON 파일로 저장해 `--data-binary @q.json`으로 보내거나, PowerShell에서 다음처럼 호출한다.

```powershell
$body = @{ question = "베타산업(999-99-00002) 견적: 작업용의자 595×600×895mm 1개 290,000원(VAT 별도). 진행해도 될까?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/query -Method Post -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

### API

`POST /query`

| 필드 | 필수 | 설명 |
|---|---|---|
| `question` | O | 견적 내용 또는 규정 질문 (최대 2,000자) |
| `role` | | `buyer`(기본, 구매 담당자) · `employee`(임직원, 조치는 안내만) · `supplier`(공급사, 자사 견적만) |
| `supplier_id` | supplier일 때 | 공급사 ID (예: `S03`) |
| `thread_id` · `approval` | 승인 시 | 승인 대기 응답의 `thread_id`와 `"approve"` 또는 `"reject"` (`question`은 빈 문자열로 보냄) |

응답: `{"answer", "contexts": [{"doc_id", "text"}], "trace": [{"step", "input", "output"}]}`. 조치 승인 대기 시 `status: "pending_approval"`, `thread_id`, `action`이 추가된다. 승인은 `role: buyer`만 가능하다.

### 평가와 테스트

```bash
pip install -r requirements-eval.txt                      # RAGAS 평가용 (선택)
python evaluation/run_eval.py --tag <태그>                # 테스트 세트 20건 자동 채점 (fixture 모드)
python evaluation/run_ragas.py --tag ragas_<태그>         # RAGAS faithfulness · context_recall
python evaluation/run_judge.py --from ragas_<태그> --tag judge_<태그>   # LLM-as-Judge
```

- 평가는 항상 fixture 모드(저장된 API 응답)로 실행해 결과를 재현할 수 있다. 결과는 `evaluation/results/<태그>.json`.
- Python 3.14에서는 ragas 의존성 `scikit-network`가 빌드되지 않는다. `requirements-eval.txt` 상단 안내대로 `pip install ragas==0.4.3 --no-deps` 후 나머지를 설치한다 (평가 지표에는 scikit-network가 필요 없음).

## 알려진 한계 (데모)

- **역할은 요청 본문의 `role` 값을 그대로 믿는다.** 로그인이 없는 데모라 누구나 `role: buyer`로 보내면 구매 담당자로 처리된다. 공급사 정보 차단(G1)과 조치 승인(G2)은 이 전제에서 동작하며, 운영에서는 로그인 토큰에서 역할을 정해야 한다.
- 승인 대기 상태는 메모리에 있어 서버를 재시작하면 사라진다. 승인/거부는 결과만 응답하고 실제 조치는 하지 않는다.
- 가격 기준은 테스트 품목 10종의 조달 단가 추출본뿐이다. 다른 품목은 기준가가 없어 판단 불가로 안내한다.
- 개인정보 마스킹은 정규식 기반이라 이름 · 주소 · 형식이 다른 번호는 가리지 못한다.
- 자세한 목록: [SERVICE.md](SERVICE.md) 4장 "알려진 한계와 운영 시 보완"

## 데이터 안내

공급사명·사업자번호·견적·뉴스·규정은 모두 가상 데이터입니다. 실제 데이터는 국세청 사업자 상태 API와 조달청 나라장터쇼핑몰 품목 등록 내역(공개 데이터, 업체명·사업자번호 제외 후 추출)입니다. 원본 CSV(`data/raw/`)는 용량이 커서 저장소에 포함하지 않습니다.

## API 키

저장소에는 키가 들어 있지 않습니다. 실행하는 사람이 `.env.example`을 복사해 본인 키를 넣습니다.

| 키 | 필요한 경우 |
|---|---|
| `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` | 서버 실행, `run_eval.py` · RAGAS · Judge (Bedrock LLM · 임베딩 호출) |
| `DATA_GO_KR_API_KEY` | `API_MODE=LIVE`로 국세청 실시간 조회를 할 때만. 평가(fixture 모드)에는 필요 없음 |
| (없음) | `pytest` 단위 테스트 72건은 LLM을 호출하지 않아 키 없이 실행됨 |

- `.env`는 `.gitignore`로 제외되어 커밋되지 않는다. 개발 중에는 저장소 밖 상위 폴더의 `.env`를 읽는다 (`src/config.py`).
- 실행 결과는 키 없이도 `evaluation/results/`의 평가 결과 파일과 보고서로 확인할 수 있다.
