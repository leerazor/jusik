# 전진 simulation 시간 근거 bundle

`backend/jusik/research_portfolio_time_evidence.py`는 고정된 오프라인
`PortfolioInput`, simulation 설정, 공식 `MarketCalendar` 바이트를 받아 새
simulation 결과와 시간 근거 sidecar를 함께 저장하는 opt-in adapter입니다. 기존
engine·run·replay·readiness 저장소는 읽기만 하며, 기존 run의 날짜나 시각을
소급 보정하지 않습니다.

생성은 반드시 `--allow-new-simulation`을 지정해야 합니다. adapter는 engine의
`_instrument_data`와 `_events`를 먼저 고정·검사하고 public `simulate`를 한 번만
호출합니다. 생성 디렉터리는 새 경로여야 하며 `input.json`, `config.json`, 원본
`calendar.json` 바이트, 기존 shape의 `simulation.json`, `time-evidence.json`,
마지막 `manifest.json`을 원자적으로 기록합니다. manifest에는 각 파일의 크기와
SHA-256, source/event-plan SHA, 달력 payload/provider/version을 저장합니다.

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
