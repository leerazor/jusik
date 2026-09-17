# 전진 simulation 시간 근거 bundle

`backend/jusik/research_portfolio_time_evidence.py`는 고정된 오프라인
`PortfolioInput`, simulation 설정, 공식 `MarketCalendar` 바이트를 받아 새
simulation 결과와 시간 근거 sidecar를 함께 저장하는 opt-in adapter입니다. 기존
engine·run·replay·readiness 저장소는 읽기만 하며, 기존 run의 날짜나 시각을
소급 보정하지 않습니다.

실행 시간 정책은 `legacy`(기본값)와 `official` 두 가지입니다. `legacy`는 기존
engine 시각과 기존 bundle config/manifest shape를 그대로 유지합니다. `official`은
달력의 각 bar session open/close를 engine의 event, known-bar, target, volatility
계산에 주입하고 모든 warmup bar도 session 존재·coverage·공식 close 인과성을 먼저
검사합니다. official manifest는 `execution_time_policy`와 현재 engine source
SHA-256을 함께 고정하며 검증 시 둘 중 하나라도 달라지면 fail-closed합니다.

생성은 반드시 `--allow-new-simulation`을 지정해야 합니다. adapter는 engine의
`_instrument_data`와 `_events`를 먼저 고정·검사하고 public `simulate`를 한 번만
호출합니다. 생성 디렉터리는 새 경로여야 하며 `input.json`, `config.json`, 원본
`calendar.json` 바이트, 기존 shape의 `simulation.json`, `time-evidence.json`,
마지막 `manifest.json`을 원자적으로 기록합니다. manifest에는 각 파일의 크기와
SHA-256, source/event-plan SHA, 달력 payload/provider/version을 저장합니다.
입력 JSON은 lexical token 400,000개, 파일 20 MiB, 전체 50 MiB, depth 64,
object key 2,000개, list item 20,000개의 기존 bounded 계약을 유지합니다.

초기자본 시각은 첫 engine event와 같은 UTC instant의
`timestamp_kind=engine_event_anchor`, `logical_order=before_first_event`입니다.
이는 시장 open 또는 과거 입금 사실이 아닙니다. 각 NAV는 engine의 원래
`evaluation_at`과 exact NAV를 보존하고, 같은 시각의 close event group과 공식
`MarketSession`의 calendar/session identity, `open_at`, `close_at`을 연결합니다.
각 session의 실제 `close_at`이 evaluation보다 늦으면 fail-closed합니다. 따라서
지연 폐장 XKRX 자료가 engine의 고정 시각에 먼저 보이는 경우와 warmup bar의 미래
노출을 허용하지 않습니다. 여러 시장의 close가 다른 시각이면 하나의 가짜 global
close로 합치지 않습니다.

검증은 생성된 bundle과 호출자가 명시한 manifest SHA만 읽으며 engine을 실행하지
않습니다.

```bash
PYTHONPATH=backend python -m jusik.research_portfolio_time_evidence \
  generate --request request.json --output-dir /path/to/new-bundle \
  --allow-new-simulation

PYTHONPATH=backend python -m jusik.research_portfolio_time_evidence \
  verify --bundle-dir /path/to/new-bundle \
  --expected-manifest-sha256 <manifest-sha256>
```

이 artifact는 기존 성과 지표를 계산하거나 readiness를 승격하지 않으며, 실제
broker 주문·PAPER/live 실행·network·DB/API pointer를 사용하지 않습니다.

## 역사적 bundle 예시

2026-09-18에 고정된 rebalance-band source manifest와 tracked market-session
calendar만 사용해 continuous 기간 `2024-04-24..2026-09-08`의 historical
approximate bundle을 생성했습니다. audit 경로는
`/home/kwl/.local/share/jusik/portfolio-audit/forward-simulation-time-evidence-run/run-gr68c4/bundle-continuous-official`이고
manifest SHA-256은
`eec4aae8ed3c0366e9d15fa84657004d0e25429e2815b05e8a4870727718520b`입니다.
공식 execution-time policy에서 event 16,824개, NAV 1,172개, trade 171개를
보존했으며, 생성과 manifest 고정 SHA 검증은 각각 한 번 수행했습니다.

이 bundle은 재사용한 historical 자료에 대한 기술적 시간 순서 근거일 뿐이며,
point-in-time·prospective·canonical 또는 R4 economic evidence가 아닙니다.
성과 지표·readiness·PAPER/live 설정을 만들거나 승격하지 않으며, 원자료의
시각·완전성·배당·생존자 편향 한계도 해결하지 않습니다.
