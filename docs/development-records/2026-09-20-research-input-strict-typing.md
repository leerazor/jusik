# Research input strict typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: 연구 설정과 KIS historical provider의 기존 strict mypy 오류 제거

## 변경

- `.env.dev`의 필수 KIS 설정은 명시적인 non-empty 문자열 검증 후 `SecretStr`로
  변환합니다. 선택적 OpenAI key도 빈 값과 secret 타입을 구분합니다.
- KIS 응답의 시장 분류를 `KOSPI | KOSDAQ | UNKNOWN` literal로 고정해 외부 문자열이
  `SymbolSnapshot` 계약을 우회하지 않도록 했습니다.
- 실제 credential 값, paper/live 상태, 주문 경로는 변경하지 않았습니다.

## 검증

- `mypy --strict` (`research_config.py`, `research_data.py`, `research_engine.py`) — 통과
- Ruff check/format, `git diff --check` — 통과
- 연구 설정·데이터·API 테스트 — `22 passed, 2 warnings`
- 연구 엔진·데이터 테스트 — `29 passed`

## 제한

- 이 작업은 자료 completeness, PIT availability, 경제 acceptance를 승격하지 않습니다.
- runner는 계속 paused/inactive 상태로 유지하며 remote push와 Windows 종료를 수행하지
  않습니다.
