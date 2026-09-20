# Main settings env loading typing cleanup

- 상태: 완료
- 기록 시각: 2026-09-20T00:00:00Z
- 범위: portfolio backend lifespan의 `.env.prod` Settings 생성 경계

## 변경

- `Settings()`가 pydantic-settings runtime에서 `.env.prod`의 필수 `kis_base_url`을
  읽는다는 점을 코드에 명시하고, 생성된 정적 시그니처의 false-positive만 국소적으로
  무시했습니다.
- 환경 파일, endpoint validation, broker client 초기화와 주문 정책은 변경하지 않았습니다.

## 검증

- `main.py` strict mypy — 통과
- Ruff, `git diff --check` — 통과
- start/portfolio 관련 테스트 — `45 passed`

## 제한

- 실제 환경값·credential·broker 주문을 읽거나 실행하지 않았습니다.
