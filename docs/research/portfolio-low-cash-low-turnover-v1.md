# 저현금·저회전 포트폴리오 실험 v1

이 문서는 `portfolio-low-cash-low-turnover-v1` 오프라인 실행 계약이다. 실행은
요청 JSON의 입력 파일을 읽기 전용으로 사용하며, 제품 엔진·registry·PAPER·서비스
설정을 변경하지 않는다.

## 실행

```bash
cd backend
python -m jusik.research_portfolio_low_cash_experiment \
  --request /absolute/path/request.json \
  --output-dir /absolute/path/to/new-audit-directory
```

요청 JSON의 키는 다음 네 개로 고정된다. `source_path`는
`PortfolioInput.model_dump_json()` 파일이며, 두 `*_sha256` 값은 해당 파일의
소문자 SHA-256이다.

```json
{
  "source_path": "/absolute/path/portfolio-input.json",
  "source_sha256": "<64 lowercase hex characters>",
  "engine_path": "/absolute/path/research_portfolio_engine.py",
  "engine_sha256": "<64 lowercase hex characters>"
}
```

실행 전 사전등록을 먼저 저장하고, frozen engine을 corrected-entry variant로
복사한다. observer는 복사된 engine의 `equity()` 안에서 계산된 동일 NAV·현금·종목
평가액만 기록한다. observer off/on 전체 `PortfolioSimulation`은 exact equality여야
하며, parity 두 회를 별도로 보존한다.

## 고정 설계

개발 기간은 `2023-09-13..2024-09-12`, `2024-09-13..2025-09-12`이고 비용 배수는
1·2다. 각 비용 배수는 fee/slippage/FX spread 각 0.001 또는 0.002다. grid는
`(gross_cap, volatility_target) = (0.60, 0.10), (0.80, 0.20), (0.95, 0.20),
(0.95, 0.30)`에 cadence 4·8주, band 0.02·0.04, drawdown 0.10·0.20을
곱한 32개다. 따라서 개발 simulation은 128회다.

초기 자본은 100,000,000 KRW, `symbol_cap`과 leveraged ETF cap은 각각 0.20이며,
후보는 `inverse_volatility_fx_vix`, 정책은 `low_turnover_combined`이다. 첫 grid
profile의 cadence 4주·band 0.02·drawdown 0.10을 baseline으로 고정한다.

개발 결과에서 사전등록된 조건을 만족하는 비-baseline 후보를 net return 평균으로
내림차순 정렬하고 ID를 tie-breaker로 사용해 최대 두 finalist를 동결한다. 동결
뒤 baseline과 finalist만 `2025-09-13..2026-09-11` final 및
`2023-09-13..2026-09-11` continuous를 실행한다(최대 12회). finalist가 없으면
negative result로 baseline만 보고하고 heldout retuning은 하지 않는다.

## 판정 및 보고

후보별로 다음을 저장한다.

- UTC 일별 마지막 cash의 median/p90
- 모든 observer NAV와 초기자본을 포함한 global peak drawdown
- actual leveraged value 최대치와 cap 위반 목록
- 전체 및 월별 trade-days
- 일별 평균 NAV 기준 annual notional turnover
- 거래금액 p0/p25/p50/p75/p90/p100
- net price return, transaction cost, FX cost

Finalist eligibility는 두 개발 기간·두 비용이 모두 complete/accounting-valid이고,
global DD가 20% 미만이며 actual leverage가 `20% + 1e-8pp` 이하인 경우다. 각
dev/cost 셀에서 baseline보다 일별 마지막 cash median이 엄격히 낮고 trade-days가
증가하지 않아야 한다. Global DD는 engine의 episode drawdown과 다른 관측 지표다.

결과는 `results.json`, `results.csv`, `report.md`, `preregistration.json`,
`finalist-freeze.json`, 각 simulation/observer artifact와 hash manifest에 기록된다.
입력 hash는 실행 전후 재검증하고 기존 출력 디렉터리 덮어쓰기·재개는 거부한다.
자료는 retrospective 재사용 자료이며 배당·세금은 제외한다. 결과는 미래 성과 보장,
PAPER 활성화, 자동 승격 또는 실거래 적합성을 의미하지 않는다.
