# 오프라인 회계 artifact

`python -m jusik.market_history_action_artifact --input PATH --output PATH`는
명시적인 초기 상태와 기업행동 전이 목록을 읽어 결정적인 JSON 진단 artifact를
생성합니다. 입력은 `schema_version: 1`, `seed: 0`, `initial_state`, `steps`를
포함해야 합니다. 초기 상태는 `price_basis: "raw"`를 명시하고 미수금과 action
기록을 빈 배열로 시작합니다. 수량·가격·원가는 유한한 Decimal 문자열이며 통화는
KRW 또는 USD 하나만 사용할 수 있습니다.

최소 입력 예시는 다음과 같습니다.

```json
{"schema_version":1,"seed":0,"initial_state":{"holdings":[],"cash":"0","currency":"KRW","price_basis":"raw","receivables":[],"action_records":[]},"steps":[]}
```

각 step은 `split`, `accrual`, `payment` 중 하나의 phase, timezone-aware ISO
`at`, 그리고 action을 가집니다. 전이는 배열 순서와 UTC 시각 순서대로 적용합니다.
분할은 raw 가격과 전후 가격을 요구하며 분할 전후 NAV와 원가를 보존합니다. 배당은
확인된 권리를 먼저 미수금으로 동결한 뒤 명시된 지급 시각에 현금으로 옮깁니다.
조정가격·미상 가격 기준, 누락된 권리·가격, phase와 kind 충돌은 결과에 실패
상태로 남고 해당 시점의 상태는 보존됩니다.

artifact에는 초기·최종 상태와 모든 전이의 전후 전체 상태, NAV, 현금, 미수금,
action 기록, status/reason, action identity, UTC 시각을 보존합니다. 원본 입력의
SHA-256과 바이트 크기도 기록합니다. 최상위 `coverage`는 항상 `incomplete`,
`economic_status`는 항상 `not-evaluated`입니다. 이 도구는 자료 수집, 시장 세션
추론, 데이터베이스, 전략, PAPER/live 거래 또는 주문을 수행하지 않습니다.

입력은 최대 1MiB, 전이는 최대 80개, 심볼은 최대 4개, UTC 날짜는 최대 40개입니다.
입력과 출력 경로의 symlink 및 hardlink alias를 거절하고, 출력은 기존 파일을
덮어쓰지 않는 `O_EXCL` 방식으로 최대 50MiB까지 한 번만 생성합니다. 구조·파일
오류는 exit 2이며, 전이 계산 실패는 artifact를 만들고 exit 0으로 반환하므로
소비자는 각 전이의 `result.status`를 확인해야 합니다.

이 기술 slice는 전체 R1-04 로드맵 항목을 완료하거나 체크하지 않습니다. 실제 시장
자료 연결, 완전성 검증과 경제적 평가는 별도 작업이며 결과는 계속
`incomplete`/`not-evaluated`로 남습니다.
