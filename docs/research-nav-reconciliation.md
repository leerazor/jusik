# 저장 NAV 구성요소 진단 계약

`jusik.research_nav_reconciliation`은 저장된 연구 결과의 `result.equity`를 오프라인에서 읽어 날짜별 구성요소 관계를 검사합니다. 각 행은 `nav_krw - cash_krw - invested_krw`를 Decimal로 계산하며 절댓값이 `1 KRW` 이하이면 통과입니다. 입력의 원래 `session` 날짜를 그대로 사용하고, 날짜를 정렬하거나 누락된 날짜를 0으로 채우지 않습니다.

CLI는 다음과 같이 원본 파일과 고정 SHA-256을 함께 요구합니다.

```text
backend/.venv/bin/python -m jusik.research_nav_reconciliation \
  --input <run.json> \
  --expected-sha256 <64 lowercase hex> \
  --residual-output <residual.json> \
  --coverage-output <coverage.json>
```

원본 SHA가 일치하면 `residual-output`에는 모든 행의 금액·residual·통과 여부·최대 절댓값·실패 날짜가 기록되고, `coverage-output`에는 관측 행 수·고유성·순서·첫/마지막 세션이 기록됩니다. 두 artifact는 별도 파일이며 CLI는 residual 초과 시에도 두 파일을 보존한 뒤 종료 코드 `1`을 반환합니다. 정상 입력은 종료 코드 `0`을 반환하고, 구조·날짜·금액·SHA·UTF-8 오류는 artifact를 만들지 않고 종료 코드 `2`를 반환합니다. 쓰기 전에 입력과 두 출력의 경로·`..`·symlink·hardlink 별칭 및 출력 간 별칭을 모두 검사해 충돌을 거부합니다.

JSON의 null, bool, 비수치, 비유한 값, 음수, 중복 키, 빈 equity, 잘못된 구조를 거부합니다. Decimal 연산은 ambient context의 precision에 의존하지 않도록 행별 필요한 precision을 계산한 local context에서 수행합니다.

이 진단은 저장 NAV 구성요소 일관성만 확인합니다. 독립 calendar와 독립 수량·가격·현금흐름 회계는 `unavailable`, 경제 평가는 `not-evaluated`, benchmark와 future 평가는 `blocked`로 기록합니다. 관측 세션을 모든 실제 거래일로 해석하지 않으며 전체 R2-05 checkbox는 변경하지 않습니다.
