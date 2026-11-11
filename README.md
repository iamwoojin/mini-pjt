# 구매 업체·가격 검증 에이전트

공급사 견적 한 건에 대해 **업체 검증**(국세청 사업자 상태·뉴스·제출 서류)과 **가격 검증**(조달청 나라장터쇼핑몰 동일 규격 단가)을 모두 수행하고, 진행 / 조건부 / 보류를 사내 규정 근거와 함께 권고하는 에이전트입니다. 서비스 설명은 [SERVICE.md](SERVICE.md)를 보세요.

## 결과 요약

| 지표 | 1차 | 최종 (round4) | 목표 |
|---|---|---|---|
| 테스트 세트 통과율 (20건) | 85% | **100%** | 85% 이상 |
| guardrail | 100% | **100%** | 100% |
| RAGAS faithfulness / context_recall | - | **0.974 / 1.000** | 0.8 이상 |
| LLM-as-Judge | - | **4.92 / 5** | 4 이상 |
| 응답 시간 중앙값 | 2.9초 | 3.2초 | 20초 이내 |

자세한 내용: [1차 보고서](evaluation/round1_report.md) · [2차 이후 보고서](evaluation/round2_report.md)

## 구조

```
src/        graph.py(LangGraph 흐름 · 승인 대기 interrupt) · agent.py(판정 규칙 · 프롬프트 · 근거 조항)
            tools.py(API 도구) · retriever.py(규정 RAG) · api.py(POST /query) · config.py
data/       suppliers.json(가상 공급사) · docs/(사내 규정 더미) · fixtures/(조달 단가 추출본, 국세청·뉴스 fixture)
scripts/    extract_procurement.py(조달청 원본 CSV → 테스트 품목 추출)
evaluation/ test_queries.csv · run_eval.py · run_ragas.py · run_judge.py · ragas_references.json · results/ · 보고서
tests/      test_rules.py(판정 규칙 단위 테스트, LLM 호출 없음)
web/        index.html(테스트 화면)
```

## 실행

```bash
pip install -r requirements.txt          # Python 3.12+ 권장
cp .env.example .env                     # AWS 키 입력 (국세청 LIVE 조회 시 DATA_GO_KR_API_KEY)
uvicorn src.api:app --port 8000          # http://localhost:8000 테스트 화면
curl -X POST localhost:8000/query -H "Content-Type: application/json" \
     -d '{"question": "베타산업(999-99-00002) 견적: 작업용의자 595×600×895mm 1개 290,000원(VAT 별도). 진행해도 될까?"}'
```

평가와 테스트:

```bash
pytest                                                    # 판정 규칙 단위 테스트 (수 초)
python evaluation/run_eval.py --tag round4                # 테스트 세트 20건 자동 채점
python evaluation/run_ragas.py --tag ragas_round4         # RAGAS faithfulness · context_recall
python evaluation/run_judge.py --from ragas_round4 --tag judge_round4   # LLM-as-Judge
```

- Python 3.14에서는 ragas 의존성 `scikit-network`가 빌드되지 않는다. 이 경우 `pip install ragas --no-deps` 후 나머지 의존성을 설치한다 (평가 지표에는 scikit-network가 필요 없음).
- 승인 대기 응답(`status: pending_approval`)을 받으면 같은 `thread_id`로 `{"approval": "approve"}`를 보내 재개한다. 승인은 `role: buyer`만 가능하다.

## 데이터 안내

공급사명·사업자번호·견적·뉴스·규정은 모두 가상 데이터입니다. 실제 데이터는 국세청 사업자 상태 API와 조달청 나라장터쇼핑몰 품목 등록 내역(공개 데이터, 업체명·사업자번호 제외 후 추출)입니다. 원본 CSV(`data/raw/`)는 용량이 커서 저장소에 포함하지 않습니다.
