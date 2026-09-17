# 동결 NAV 시장 성과 지표

`backend/jusik/market_performance_metrics.py`는 이미 고정된 NAV 곡선만 읽어
Decimal 기반 성과 지표를 계산하는 순수 모듈이다. 시장 자료 수집, 전략, replay,
broker, PAPER/live 실행과 주문을 호출하지 않는다.

## 입력 계약

입력은 `market-performance-metrics-input/v1` JSON이다. 양의 초기 자본과 명시적인
UTC `initial_capital_at`, offset이 있는 UTC `timestamp`와 양의 유한 `nav`, `data_grade`(`strict`, `approximate`,
`fixture`), `data_source`, 완전성 근거, 비용 포함 근거, 연 무위험률과 근거,
`sessions_per_year=252`, `calculation_policy`를 모두 포함해야 한다. NAV에는 명시된
거래 비용이 이미 포함되어야 하며 계산기는 비용을 다시 차감하지 않는다. 입력
등급은 결과에 그대로 보존하고 다른 등급으로 승격하지 않는다.

완전성 근거는 관측 범위를 채운 상태와 거래소 달력 근거를 함께 증명해야 한다.
휴장일 때문에 UTC 날짜 사이에 간격이 생기는 것은 `allowed_gaps`로 설명할 수
있지만, 계산기가 날짜만 보고 휴장일이나 누락 세션을 추정하지는 않는다. 명시적
`missing_sessions`가 있거나 근거가 partial/unknown이면 모든 지표를
`unavailable`로 반환한다.

## 계산 및 unavailable 경계

- 총 순수익률은 `final_nav / initial_capital - 1`이다.
- CAGR은 `initial_capital_at`부터 최종 NAV까지의 실제 UTC 달력 경과일을 `Decimal(365)`로 나눈 지수로 계산한다. 첫 NAV가 anchor보다 앞서거나 최종 경과일이 0 이하이면 계산하지 않는다.
- MDD는 초기 자본을 첫 running peak에 포함한다.
- Sharpe는 초기 자본에서 첫 NAV로의 단순 수익률을 포함한 일별 단순 초과수익률의 표본 표준편차를 사용하고, 연 무위험률은 252제곱근 방식으로 일률 변환한 뒤 `sqrt(252)`로 연율화한다.
- Calmar는 `CAGR / MDD`이며 MDD가 0이면 unavailable이다.
- 유효한 MDD에 대해서만 `MDD <= 0.20` hard filter를 반환한다.

기간이 양수가 아니거나, NAV가 0/음수/비유한이거나, 날짜가 중복·역순이거나,
비용·완전성 근거가 없으면
해당 지표를 0 또는 무한대로 만들지 않는다. 각 unavailable 결과에는 안정적인
reason code가 남는다.

무위험률 근거, Sharpe 표본 부족, 0 변동성은 Sharpe만 unavailable로 만든다. 이
경우 기간과 NAV가 유효하면 total return, CAGR, MDD, Calmar와 hard filter는
계산한다. hard filter는 별도 객체의 `passed: true|false|null`로 직렬화한다.

## 동결 JSON 어댑터

`market-performance-metrics-envelope/v1` envelope는 입력 파일 경로와 명시적인
소문자 SHA-256을 참조한다. `evaluate_saved_performance`는 JSON을 파싱하기 전에
입력 SHA를 확인하고, 중복 JSON key·지원하지 않는 schema·입력과 같은 경로 또는
hardlink인 output을 거부한다. 금융 JSON 숫자는 Decimal으로 읽어 float 반올림을
피하고, 입력 크기와 NAV 개수에도 bounded limit이 있다. 결과는 output 디렉터리의
임시 파일에 fsync한 뒤 원자적으로 교체하므로 output 경로가 검사 후 바뀌어도
source/envelope를 덮어쓰지 않는다.

```bash
python -m jusik.market_performance_metrics \
  --input performance-envelope.json \
  --output performance-result.json
```

이 기능은 경제적 결과를 승격하거나 후보를 선택하지 않는다. 근거가 부족한 동결
결과는 계산하지 않고 계속 unavailable로 남긴다.

## 성과 입력 준비 진단

`backend/jusik/market_performance_readiness.py`는 저장된
`MarketResearchRun`을 읽기 전용으로 검사한다. 입력 파일은 최대 10MiB이고 호출자는
반드시 소문자 SHA-256을 함께 제공해야 한다. JSON 중복 key·비유한 수·지원하지 않는
구조, request/result 불일치, 5,000개 초과 NAV, 중복·역순·기간 밖 세션과 0 이하 NAV는
안전한 오류 code로 거부한다. 원본 파일에는 쓰지 않는다.

현재 승격 대상은 완료된 미국 `approximate` pilot/result뿐이다. 유효한 canonical run은
항상 `status=blocked`, `ready_for_metrics=false`, `economic_evaluation=not-evaluated`로
보고하며, 다음 누락 code를 정해진 순서로 반환한다.

```text
missing_initial_capital_at
missing_nav_timestamps
missing_session_completeness_evidence
missing_calendar_evidence
missing_cost_inclusion_evidence
missing_risk_free_evidence
missing_calculation_policy
```

실행 시각, readiness의 `calendar=ready`, 기록된 fee/slippage/sell-tax 요율은 독립
근거를 만들지 않는다. 결과에는 원래 `approximate` 등급, `simulated` 여부, provenance와
hash source facts, request의 비용 가정 pointer만 보존한다. 이 진단기는 성과 evaluator,
전략, 수집기, 네트워크를 호출하지 않으며 성과 수치나 hard-filter를 계산하지 않는다.

```bash
python -m jusik.market_performance_readiness \
  --run /path/to/us-web-pilot-run.json \
  --expected-sha256 <sha256>
```

위 명령은 caller-provided SHA를 확인하는 generic inspection이며 보고서의
`canonical=false`를 유지한다. 등록된 frozen artifact의 acceptance가 필요한 local
검증에서만 `--canonical`을 추가한다. 이 flag는 코드에 등록된 artifact SHA와 일치할
때만 canonical 보고서를 만들며, 다른 파일이나 임의 SHA로 우회할 수 없다.

## canonical R0 세션 대사 근거

등록된 canonical R0 미국 approximate run에는
`backend/jusik/data/r0_us_session_evidence_v1.json`이 별도 불변 근거로 연결된다.
근거는 baseline manifest, run, tracked
`backend/jusik/data/market_sessions_2023_2026.json`의 전체 바이트와 내부 달력
payload SHA를 함께 고정하며, `exchange_calendars 4.12`의 XNYS·`America/New_York`
현지 세션 날짜를 요청 기간 `2025-09-11~2026-09-11` 양끝 포함으로 해석한다. 달력에서
재계산한 252개 날짜와 run의 252개 equity 날짜를 순서와 canonical digest까지 대조하고,
누락·초과·중복·unavailable이 없어야 통과한다. 실제 달력의 close 시각은 NAV timestamp나
초기자본 anchor로 사용하지 않는다.

검증된 canonical 보고서만 다음 두 누락 code를 제거한다.

```bash
PYTHONPATH=backend python -m jusik.market_performance_readiness \
  --run /path/to/us-web-pilot-run.json \
  --expected-sha256 cc9150f8b77a27ffd6b001449c0475933ff744a37011801923f87cbdc5558275 \
  --canonical
```

근거가 없거나 SHA·기간·달력·관측 날짜가 바뀌면 fail-closed 오류가 발생한다. 이
근거는 세션 날짜 완전성만 증명하며 strict point-in-time 자료, 가격·기업행사·FX·비용,
NAV timestamp 또는 경제적 성과를 증명하지 않는다.
