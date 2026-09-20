# Dividend overlay strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: R1-04 dividend overlay 결과의 source artifact identity 타입 경계

## 변경

- source manifest/result SHA 값을 identity mapping에서 명시적으로 문자열로 좁혀
  `DividendOverlayResult` 모델에 검증된 hash만 전달하도록 했습니다.
- 배당 facts, entitlement, ledger, 결과 artifact 내용은 변경하지 않았습니다.

## 검증

- dividend overlay strict mypy — 통과
- Ruff, `git diff --check` — 통과
- dividend overlay 테스트 — `6 passed, 2 warnings`

## 제한

- operator-verified SEC facts와 PIT 배당 근거가 없으므로 overlay를 경제 성과나 ledger
  승인 근거로 승격하지 않습니다.
