# Kiwoom settings loader typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: Kiwoom paper/production settings의 pydantic-settings env file 호출 경계

## 변경

- `_env_file`은 pydantic-settings가 runtime에서 소비하는 private constructor option임을
  명시하고, 타입 생성 시그니처 차이를 국소적인 설명된 ignore로 제한했습니다.
- 환경 파일 존재 확인, 공식 endpoint·credential·계좌 형식 검증은 유지했습니다.

## 검증

- `kiwoom_config.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- Kiwoom 설정/adapter 테스트 — `28 passed`

## 제한

- 계좌 credential을 읽거나 노출하지 않았고 실제 주문·live 실행은 수행하지 않았습니다.
