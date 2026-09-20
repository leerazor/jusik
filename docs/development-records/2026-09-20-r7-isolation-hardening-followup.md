# R7 isolation workspace hardening follow-up

- 상태: 완료된 fail-closed 보강
- 기록 시각: 2026-09-20T02:00:00Z
- 작업 slug: `r7-isolation-hardening-followup-20260920`
- 기준/통합: `3e4b33f` / 별도 worktree 커밋
- 범위: R7 isolation workspace 생성·manifest 소비 경계만 보강했으며, simulation,
  PAPER/live, 주문, runner와 retrospective source 내용은 변경하지 않았습니다.

## 변경과 결정

- parent directory를 구성 요소별 `O_NOFOLLOW` descriptor로 열어 조상 symlink와
  경로 교체가 workspace 생성 대상이 되는 경계를 줄였습니다.
- R7 gate가 caller가 조작한 dataclass 경로를 소비하지 않도록 manifest가 가리키는
  `root/<child>`·`root/workspace.json`과 실제 workspace 경로 필드를 exact binding합니다.
- 기존 source hash 재검증과 0600/0700·paper-only 검사는 유지했습니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자-visible 동작은 바뀌지 않고 invalid workspace만 차단합니다.
- 운영 문서: 해당 없음. runner/service 설정을 변경하지 않았습니다.
- API·설정·데이터 계약: R7 isolation gate의 fail-closed 경계만 강화했습니다.

## 검증

- `pytest backend/tests/test_research_r7_isolation.py backend/tests/test_research_r7_gate.py -q` — 13 passed
- `ruff check` (변경 source/test 4개) — 통과
- `mypy --strict` (변경 source 2개) — 기존 import 범위 오류 10개로 실패; 변경 코드 신규 오류 없음
- `git diff --check` — 통과

## 안전·운영 상태

- 실제 simulation, PAPER/live, 주문, network collection, runner 재개와 원격 push는 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 코드·테스트 diff로 검증했습니다.
- 남은 작업·차단 조건: R7 경제 평가와 PAPER 결정은 여전히 사전등록 OOS·자료·독립 review에 의해 차단됩니다.
- 다음 시작: main 통합 전 focused R7 검증과 독립 review 결과를 다시 확인합니다.
