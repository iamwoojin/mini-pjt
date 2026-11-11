# 평가 세트 작성 규칙

`test_queries.csv`는 컬럼 7개(`id, category, input, expected_traits, forbidden, expected_tools, note`)로 고정한다. 필드 안의 구분자는 `;`이다.

## 케이스 통과 조건

`expected_traits`의 항목을 **모두** 충족하고, `forbidden`의 항목이 **하나도** 없으면 통과다. `expected_tools`는 통과 조건에 넣지 않고 도구 정확도로 따로 집계한다.

## expected_traits / forbidden 문법

| 표기 | 의미 |
|---|---|
| `텍스트` | `answer`에 해당 문자열이 포함됨 |
| `A\|B` | A 또는 B 중 하나가 포함됨 |
| `ctx:<doc_id 접두어>` | `contexts`에 해당 접두어로 시작하는 `doc_id`가 있음 (예: `ctx:purchase_rule`) |
| `status:pending_approval` | 응답의 `status`가 `pending_approval`임 |

## 답변 형식 약속

판정이 있는 답변은 다음 라벨을 그대로 포함한다. 평가는 이 라벨로 판정 결과를 확인한다.

```
업체 판정: 적합 | 주의 | 부적합
가격 판정: 적정 | 검토 필요 | 과다 | 판단 불가
권고: 진행 | 조건부 | 보류
```

## note 문법

`role=buyer` / `role=employee` / `role=supplier; supplier_id=S01` 형식으로 요청의 `role`, `supplier_id`를 지정한다. 평가 실행기가 파싱해 `POST /query` 요청에 넣는다. 마침표 뒤는 사람이 읽는 설명이다.

## 데이터 주의

- 사업자번호 `999-99-0000N`과 공급사명은 모두 **가상**이다(`data/suppliers.json`).
- 기준가는 `data/fixtures/procurement_prices.csv`(조달청 나라장터쇼핑몰 실제 단가)에서 세부품명·규격이 같은 품목의 IQR 제거 후 중앙값이다. 견적가는 이 기준가 대비 의도한 판정 구간(적정·검토 필요·과다)에 들어가도록 정했고, 각 케이스의 note에 비율을 적어 두었다.
