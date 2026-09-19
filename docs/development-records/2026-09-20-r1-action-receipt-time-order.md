# Action receipt temporal ordering

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r1-action-receipt-time-order-20260920`
- 기준/통합: `042e87e` / local `main` 통합 대기
- 구현 커밋: `2c24b9b`
- 독립 검토 보완 커밋: `a2a7405`
- 범위: action receipt preflight와 해당 회귀 테스트, 이 기록만 변경했습니다. 기존
  receipt identity/hash, 경제 acceptance, collector, 원장, PAPER/live, 서비스와
  원격 상태는 변경하지 않았습니다.

## 변경과 결정

- `requested_start > requested_end`인 collection attempt를 거부합니다.
- `started_at > completed_at`인 attempt를 거부합니다. pending attempt의 `None`
  completion은 기존 상태 계약대로 유지합니다.
- event의 `first_seen_at > last_seen_at`을 거부합니다.
- revision의 `first_seen_at < attempt.started_at`을 거부합니다.
- event에 연결된 모든 revision을 sequence 순서로 정렬해 관측 시각이
  비감소인지 확인하고, event의 `first_seen_at <= min(revision.first_seen_at)` 및
  `max(revision.first_seen_at) <= last_seen_at` 경계를 검증합니다.
- 모든 비교는 timezone-aware UTC로 정규화한 값으로 수행하며, 동일한 시각은
  허용합니다. 기존 revision completion 시각 문자열 일치와 hash/identity 검사는
  그대로 유지합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자에게 노출되는 동작은 바뀌지 않습니다.
- 운영 문서: 해당 없음. runner·서비스 운영 계약은 변경하지 않았습니다.
- API·설정·데이터 계약: preflight가 시간 역전을 fail-closed로 거부하는 기술
  검증만 보강했으며, 경제 acceptance나 연구 상태 승격은 하지 않았습니다.

## 검증

- `python -m pytest -q tests/test_market_history_action_receipt_preflight.py` — 11 passed
- `ruff check jusik/market_history_action_receipt_preflight.py tests/test_market_history_action_receipt_preflight.py` — 통과
- `ruff format --check jusik/market_history_action_receipt_preflight.py tests/test_market_history_action_receipt_preflight.py` — 통과
- `mypy jusik/market_history_action_receipt_preflight.py` — strict 설정으로 통과
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 주문·PAPER/live 승격·외부 데이터 수집·서비스 변경·원격 push를 수행하지
  않았습니다. 고정 fixture만 사용했습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 기존 fixed receipt identity/hash 보존
- 남은 작업·차단 조건: main 통합 후 통합 검증이 필요합니다. 이
  작업만으로 R1-04/R1-05 경제 acceptance 또는 coverage를 승격하지 않습니다.
- 다음 시작: Astra가 `2c24b9b`와 `a2a7405`를 검토한 뒤 local `main`에 통합하고 동일 검사를
  다시 실행합니다.
