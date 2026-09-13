# Gross cap cash sensitivity 연구

`portfolio-gross-cap-cash-sensitivity-v1`은 고정된 gross cap `.60`과 `.80`을 비교한다. 두 arm은 corrected-entry 엔진, held band `.04`, cadence 4주, volatility target `.10`, symbol 및 leveraged ETF cap `.20`, drawdown trigger `.10`, 초기 자본 1억원, 인출 없음으로 고정한다. 비용은 1x와 3x이며 fold 1–7과 continuous를 각각 기록한다.

실행 순서는 각 arm의 비용 1x/3x 16개를 포함한 32개이며 CPU deadline은 900초이다. control 16개는 frozen cost3 실험의 기존 JSON과 전체 equality 및 Decimal 회계를 먼저 통과해야 한다. 실패, hash mismatch, 회계 잔차, cap 초과, deadline은 즉시 중단하고 ledger와 failure를 보존한다. 재시도·탐색·추가 parity simulation은 허용하지 않는다.

observer는 valuation 이벤트마다 UTC timestamp, NAV, cash, 종목별 평가액, gross·symbol·leveraged cap 초과의 실제 금액과 시각을 기록한다. 일별 마지막 UTC valuation의 현금 KRW/현금 비율/gross exposure는 평균으로 집계하며 초기 자본을 포함한 observer MDD, 순수익, trade count, trade days, 비용과 turnover를 fold와 continuous로 분리해 보고한다. cap scaling 분모와 단계별 빈도는 엔진의 opening execution sizing 호출을 기준으로 저장하고, strategy decision frequency나 cap 근접 자체와 혼동하지 않는다. target weight normalization도 gross-dependent이므로 scaling event가 0이어도 gross cap 효과가 없다는 뜻은 아니다.

원천 자료의 실제 종목별 coverage와 요청한 3년 범위를 함께 표시한다. 상장 전 구간 생성, historical PIT 완전성, 배당 receipt timing, early-close 처리는 보장하지 않는다. 원천에는 `is_leveraged` 필드가 없으므로 frozen universe 이름과 engine의 `SOXL`, `TQQQ` 매핑을 사용한다(`UPRO` 없음). 결과는 자동 승격이나 실거래로 연결되지 않는다.
