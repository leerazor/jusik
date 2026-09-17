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

## 고정 canonical 연결 adapter

`jusik.research_canonical_nav_reconciliation`은 입력 인자를 받지 않고 등록된 R0 미국 run만 읽습니다. 고정 run bytes를 먼저 `reconcile_json_bytes()`로 대사한 뒤, 좁은 `verify_canonical_session_evidence()`와 기존 `verify_canonical_cost_evidence()`를 각각 한 번 호출해 동일한 run SHA·manifest SHA·`2025-09-11`~`2026-09-11` 기간을 연결합니다. 두 근거가 함께 증명하는 것은 순서가 보존된 정확히 252개 session, 106개 modeled trade, 252개 NAV와 고정 dataset SHA뿐입니다.

adapter 출력은 `r2-canonical-nav-evidence-connection/v1` 결정적 envelope입니다. `residual`에는 위 일반 대사의 행·잔차·실패 날짜를 그대로 보존하고, `canonical.coverage`에서만 calendar·독립 modeled-accounting·KRW NAV source를 `verified`로 표시합니다. `canonical.provenance`는 run/manifest/dataset/session-evidence/calendar SHA와 기간·session 목록을 보존하며, `projection.digest`와 `accounting.digest`는 각각 residual projection과 기존 비용 verifier의 digest로 명확히 구분합니다. 일반 reconciliation의 `unavailable`, `not-evaluated`, `blocked` 의미와 전체 R2-05 checkbox는 바뀌지 않습니다.

adapter가 호출하는 session/cost verifier는 run, manifest, calendar, dataset, evidence, cache 파일을 모두 `limit+1` bounded read로 확인한 뒤 해시·구조 검증을 진행합니다. 초과 시 `manifest_too_large`, `calendar_too_large`, `dataset_too_large`, `evidence_too_large`, `cache_*_too_large`로 fail-closed 합니다. 기존 cost verifier의 self-pinned source/evidence chain은 새 source/evidence SHA로 갱신해 실제 consumer에서 비용 chain을 bounded하게 검사합니다.

현재 cost verifier source SHA는 `8aa7f94a8fce5b61a1c44642be7d0e6cd7f0c9475ac765a7dd1b2d3780ba73c7`, tracked cost evidence bytes SHA는 `865de8fe7273996d856d9b60e2c72a0e9dae20eb989e16cfe5495b31c66d945a`입니다. evidence 안의 run·dataset·manifest·cache artifact SHA와 106 trade/252 session accounting digest는 그대로 유지됩니다.

CLI는 다음처럼 실행하며 성공은 0, 잔차 실패는 1, 고정 근거·구조·identity 검증 실패는 2입니다.

```text
PYTHONPATH=backend python -m jusik.research_canonical_nav_reconciliation
```
