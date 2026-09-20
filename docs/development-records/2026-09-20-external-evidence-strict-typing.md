# External evidence strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: Treasury external observation parser와 append-only external snapshot store의
  strict type 계약 정리

## 변경

- Treasury series/key 매핑을 `ExternalSeries` literal tuple로 고정해 외부 문자열이
  observation schema를 우회하지 않게 했습니다.
- store snapshot은 `ExternalFeatureSnapshot.observations`의 불변 tuple 계약으로
  반환하도록 정규화했습니다.
- historical availability 정책, source grade, PIT/economic 승격은 변경하지 않았습니다.

## 검증

- 두 모듈 strict mypy — 통과
- Ruff check/format, `git diff --check` — 통과
- external/universe/forward 관련 테스트 — `59 passed, 2 warnings`

## 제한

- 외부 원천의 실제 historical first-seen 시각이나 FX availability를 새로 만들지
  않았습니다. 기존 fail-closed gate와 runner paused 상태를 유지합니다.
