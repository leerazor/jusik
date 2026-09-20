# FX currency strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: FX service의 지원 통화와 `ExchangeRate` literal 계약

## 변경

- 지원 통화 목록을 `Currency` typed tuple로 선언하고 `_rate()` 입력을 같은 literal로
  제한했습니다.
- 환율 endpoint, stale 정책, 환율 자료와 NAV 적용은 변경하지 않았습니다.

## 검증

- FX module strict mypy — 통과
- Ruff, `git diff --check` — 통과
- FX signal/service 테스트 — `14 passed`

## 제한

- 현재 FX source의 historical PIT availability와 publication timestamp 부족은 그대로입니다.
- 함께 실행한 investor 회귀에는 기존 시간 민감 실패 2건이 있었으며 이번 FX 변경과 무관해
  수정하지 않았습니다.
