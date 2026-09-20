# Action receipt capture-time typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: R1-04 action receipt preflight의 evidence capture timestamp 계약

## 변경

- preflight가 이미 검증한 UTC `datetime`을 `EvidenceInput.captured_at`에 전달하도록
  수정했습니다. 검증 전 문자열 cast를 제거해 timezone-aware timestamp 계약을 보존합니다.
- receipt/review 내용, source hashes, operator review 또는 ledger 적용은 변경하지 않았습니다.

## 검증

- preflight strict mypy — 통과
- Ruff, `git diff --check` — 통과
- preflight/action collection/review 테스트 — `34 passed, 2 warnings`

## 제한

- 실제 action facts와 PIT coverage가 없으므로 R1-04 경제 승격이나 자동 ledger 적용은
  수행하지 않습니다.
