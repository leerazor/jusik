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
