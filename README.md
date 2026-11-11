# 업체 검증 및 견적 검증 에이전트

공급사 견적 한 건에 대해 **업체 검증**(국세청 사업자 상태·뉴스·제출 서류)과 **가격 검증**(조달청 나라장터쇼핑몰 동일 규격 단가)을 모두 수행하고, 진행 / 조건부 / 보류를 사내 규정 근거와 함께 권고하는 에이전트입니다. 서비스 설명은 [SERVICE.md](SERVICE.md)를 보세요.

> 🚧 Day 8: 제안서와 스켈레톤 단계입니다. 구현은 Day 9부터 진행합니다.

## 구조

```
src/        agent.py(에이전트·판정 규칙) · tools.py(API 도구) · retriever.py(규정 RAG) · api.py(POST /query)
data/       suppliers.json(가상 공급사) · docs/(사내 규정 더미) · fixtures/(조달 단가 추출본, 국세청·뉴스 fixture)
scripts/    extract_procurement.py(조달청 원본 CSV → 테스트 품목 추출)
evaluation/ test_queries.csv · README.md(채점 규칙) · round1_report.md · round2_report.md
web/        index.html(테스트 화면)
```

## 실행

```bash
pip install -r requirements.txt
# 상위 폴더 또는 이 폴더의 .env에 AWS 키, DATA_GO_KR_API_KEY(국세청 상태조회) 설정
uvicorn src.api:app --reload
curl -X POST localhost:8000/query -H "Content-Type: application/json" -d '{"question": "..."}'
```

## 데이터 안내

공급사명·사업자번호·견적·뉴스·규정은 모두 가상 데이터입니다. 실제 데이터는 국세청 사업자 상태 API와 조달청 나라장터쇼핑몰 품목 등록 내역(공개 데이터, 업체명·사업자번호 제외 후 추출)입니다. 원본 CSV(`data/raw/`)는 용량이 커서 저장소에 포함하지 않습니다.
