# Volatility target 15%·rebalance cadence 비용 trade-off 연구

이 문서는 `portfolio-volatility15-cadence-cost-tradeoff-v1`의 실행 전 보고서 초안입니다.
실행 attempt는 `527025c895ad4d54a9559469434162a8`이며 historical simulation은 Astra가
명시적으로 승인한 단일 실행에서만 수행합니다.

## 사전등록 조건

변동성 목표는 0.15로 고정합니다. gross cap 0.60, corrected-entry, held band 0.04,
symbol/leveraged ETF cap 0.20, drawdown trigger 0.10, 초기자본 1억원, 인출 없음과
기존 universe·eligibility·기간을 유지합니다. 비교 변수는 첫 월요일 anchor를 기준으로
하는 4주와 8주 cadence뿐이며, 비용 배수는 1x와 3x입니다.

대조군 16개는 선행 volatility-target 연구의 `variant_c1/c3` JSON을 새
`control_c1/c3`로 정확히 재현합니다. 이 재현과 회계 검증이 모두 통과한 후 변형군
16개를 실행합니다. 총 호출 상한은 CPU exact 32회, hard deadline 900초, 재시도 0회,
GPU 0회입니다.

## 결과

실행 전이므로 수치는 비워 둡니다. 실행 결과는 각 기간별 paired 행으로 현금 금액·비율,
비용 차감 순수익, turnover, 거래수, 거래비용·FX 비용, 초기자본을 포함한 observer NAV
running-peak MDD와 실제 cap 초과 관측을 기록합니다. fold는 서로 합성하지 않고
continuous를 별도로 보고합니다.

## 한계와 증거

현재 저장된 archive는 후향적으로 재사용하며 PIT와 배당 receipt 시점을 독립 검증하지
않습니다. receipt, early-close, partial/cancel/reject는 지원하지 않습니다. 실패 시
ledger의 완료·누락 artifact와 명시적인 새 attempt 승인 조건을 남기며 자동 재실행하지
않습니다.

실행 후 아래 SHA와 audit 경로를 채웁니다.

|항목|경로|SHA-256|
|---|---|---|
|preregistration|audit/experiment/preregistration.json|pending|
|results|audit/experiment/results.json|pending|
|hash manifest|audit/experiment/hash-manifest.json|pending|
