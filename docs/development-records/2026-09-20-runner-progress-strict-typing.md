# Runner progress strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: read-only runner progress projection의 launch limit 타입 경계

## 변경

- config에서 유효성 검사된 `daily_launches` 값을 `int | None`으로 명시적으로 좁힌 뒤
  `RunnerPolicy`에 전달합니다.
- runner dispatch, pause, queue, service/timer 운영 상태는 변경하지 않았습니다.

## 검증

- `research_progress.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- runner progress 테스트 — `20 passed, 2 warnings`

## 제한

- read-only projection 개선이며 자동 runner 재개나 경제 연구 dispatch를 수행하지 않습니다.
