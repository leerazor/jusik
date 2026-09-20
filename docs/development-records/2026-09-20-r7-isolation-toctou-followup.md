# R7 isolation gate TOCTOU follow-up

- 상태: fail-closed 보강 완료
- 기록 시각: 2026-09-20T03:00:00Z
- 작업 slug: `r7-isolation-toctou-followup-20260920`
- 기준/통합: `3ccb8ea` / 현재 작업
- 범위: R7 gate가 workspace 경로를 소비하는 시점의 조상 symlink·child/manifest 교체
  경계를 보강했습니다. R7 simulation, PAPER/live, 주문, runner는 변경하지 않았습니다.

## 변경과 결정

- gate가 workspace root의 모든 경로 구성요소를 `O_NOFOLLOW` held descriptor로 엽니다.
- child directories와 `workspace.json`은 root descriptor 기준으로만 열어 검사합니다.
- manifest 경로 필드가 실제 workspace root의 상대 경로와 exact binding되지 않으면 계속
  차단합니다.

## 검증

- `pytest backend/tests/test_research_r7_isolation.py backend/tests/test_research_r7_gate.py -q`
  — 15 passed
- `ruff check` 변경 source/test — 통과
- `mypy --strict backend/jusik/research_r7_gate.py` — 기존 저장소의 10개 import/타입
  오류로 non-zero; gate 변경 파일 자체의 신규 오류는 확인되지 않았습니다.
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 simulation, PAPER/live, 주문, network collection, runner 재개, 원격 push와 Windows
  종료는 수행하지 않았습니다.
- R7 경제 평가와 PAPER 결정은 사전등록 OOS·stress·독립 review 및 외부 자료 조건 전까지
  차단합니다.
