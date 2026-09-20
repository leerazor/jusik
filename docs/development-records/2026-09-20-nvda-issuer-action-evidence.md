# NVDA issuer action evidence candidate

- 상태: 단일 issuer evidence candidate 확보·R1-04/R1-05 승격 보류
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `nvda-issuer-action-evidence-20260920`
- 범위: 기존 Alpha Vantage NVDA 배당 원문과 SEC 공식 filing exhibit 한 건을 오프라인 대조했습니다. 자동 원장·성과·readiness에는 연결하지 않았습니다.

## 대조 결과

- symbol: `NVDA`
- kind: `dividend`
- ex/record date: `2025-09-11`
- payment date: `2025-10-02`
- amount: `USD 0.01`
- issuer source: SEC accession `0001045810-25-000207`, exhibit `q2fy26pr.htm`
- issuer raw SHA-256: `caea50c56d2c63a13fe844e165267d038a1649575d1a50e6830c031d58175826`
- issuer raw bytes: `380097`
- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-nvda-issuer-action-evidence/`

SEC filing exhibit의 배당 금액·record/payment 날짜가 Alpha 원문과 일치하는 것을 확인했습니다.
이는 한 event의 issuer-source 후보가 확보됐다는 의미이며, 전체 심볼·기간의 coverage,
관측시각과 effective/payment 경계, 보유수량·가격·세금은 증명하지 않습니다.

## 판정

- `operator_verified=false`로 보존했습니다. 자동 review manifest나 ledger 입력으로 만들지 않습니다.
- R1-04/R1-05 checkbox와 경제 acceptance를 변경하지 않았습니다.
- split·다른 배당·상장폐지·중단일은 별도 issuer evidence가 필요합니다.
- 기존 Alpha source와 SEC submissions의 원본 bytes는 변경하지 않았습니다.

## 검증과 안전

- SEC bounded GET 1회와 로컬 텍스트 대조를 수행했습니다.
- raw SHA·크기·accession을 request manifest에 고정했습니다.
- 실제 주문, PAPER/live, runner 재개, 원격 push, Windows 종료는 없습니다.

## 후속 batch

동일한 절차로 SEC exhibit 두 건을 추가 대조했습니다.

- `q3fy26pr.htm`: `2025-12-04` record/ex-date, `2025-12-26` payment, USD `0.01`, SHA
  `54b34964b16fe5c6ebee427a80806226c7e9cdaa877a6e9d722606a9f275f158`
- `q4fy26pr.htm`: `2026-03-11` record/ex-date, `2026-04-01` payment, USD `0.01`, SHA
  `b61e6e66c346a7a3ce0ab17090432ec87d87cb6ad7b9e4fe9153693bf3c541e7`

세 event 모두 Alpha 원문과 amount/date가 일치하며 batch audit은
`/home/kwl/.local/share/jusik/portfolio-audit/20260920-nvda-issuer-action-evidence-batch/`
에 보존했습니다. 이는 issuer evidence 후보 범위를 3건으로 넓힌 것이며, 전체 coverage나
operator verification을 대신하지 않습니다.
