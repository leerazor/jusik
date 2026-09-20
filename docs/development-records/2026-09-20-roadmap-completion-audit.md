# Investment roadmap completion audit

- 상태: 미완료·외부 입력 대기
- 기록 시각: 2026-09-20T00:00:00Z
- 기준: current `main`, canonical roadmap 40개 항목, current mandate governance

## Gate audit

| 영역 | 현재 판정 | 근거와 남은 조건 |
| --- | --- | --- |
| 승인 설계·mandate | 통과 | mandate SHA `22efba...c264ab1`, governance validator 통과, checksum projection 동기화 |
| roadmap runner | 기술 통과·운영 pause | bounded `run-once`가 `paused`, task/attempt 없음; service inactive, timer disabled |
| SEC source gate | 통과 | event-near source `52/52` verified; priority catalog `8/8` source verified |
| SEC action facts | 미완료 | operator facts·revision/content hash·독립 review 필요; 자동 ledger 적용 금지 |
| KRX diagnostics | 기술 통과·readiness 차단 | requested/observed date coverage complete, zero/missing OHLCV 29건, readiness insufficient |
| FX/PIT | 미완료 | FRED/ECB historical availability 부족; KoreaExim key 및 row-level timestamp 계약 필요 |
| 비용·세금 | 미완료 | broker/계좌별 fee schedule·시장·상품·유효기간·체결시각 근거 필요 |
| 성과 metrics | 기술 계산 통과·경제 승격 차단 | CAGR/MDD/Calmar 계산 가능; Sharpe·Sortino·Profit Factor·max loss unavailable |
| PAPER/live·실주문 | 금지 유지 | 자동 승격·실주문·remote push 수행하지 않음 |

## 재개 순서

1. SEC priority 8개 row를 원문과 대조해 operator form을 채우고 CLI `ready=true`, exit `0`을 확인합니다.
2. KoreaExim 또는 승인된 PIT FX 원천을 bounded probe하고 publication/availability cutoff를 검증합니다.
3. broker/계좌 비용·세금 계약과 realized P&L/lot 근거를 독립 대사합니다.
4. 모든 입력이 통과한 뒤에만 canonical NAV·성과·OOS·stress·paper 후보를 다시 평가합니다.

현재 자료가 없는 항목을 합성하거나 기존 approximate 결과를 strict/economic acceptance로 승격하지
않습니다.

## 최신 SEC source 재검증

- 전체 event-near queue는 `52/52` verified, missing accession `0`, SHA mismatch `0`,
  `ready=true`였습니다.
- priority form은 source `8/8`, reference missing/unexpected `0/0`이지만 operator facts와
  verification/revision/content fields가 비어 있어 `ready=false`, exit `2`입니다.
  `automatic_ledger_application=false`는 유지됩니다.
