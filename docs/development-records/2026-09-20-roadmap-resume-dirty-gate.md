# roadmap runner resume dirty-worktree fail-closed gate

- 상태: 완료 (구현·회귀 검증)
- 작업: `roadmap-resume-dirty-gate-20260920`
- 기준 커밋: `1af2a1c`
- 범위: `investment-roadmap` scope의 `resume`가 `store.resume()`를 호출하기
  전에 dispatch governance, 필수 roadmap 문서 추적 상태, clean worktree를
  순서대로 확인하도록 보강했습니다.

## 변경

- `resume_runner()`는 기존 `validate_dispatch_gate()` 의미를 유지합니다.
- `_roadmap_documents_ready()` 실패 시 필수 문서 누락·미추적 상태로 fail-closed
  하며 paused 상태를 유지합니다.
- `_roadmap_dispatch_gate()`가 `_git_ready()`를 재검사하므로 tracked dirty
  worktree에서는 paused 상태를 해제하지 않습니다.
- clean temp Git repository에서는 정상적으로 resume합니다.
- operator hold, scope binding, mandate identity, queue, service/timer,
  network, PAPER/live, remote push는 변경하지 않았습니다.

## 검증

- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest backend/tests/test_development_runner_roadmap.py -q` — 22 passed
- runner/planning/roadmap/governance pytest 묶음 — 117 passed
- Ruff check/format, `mypy --strict backend/jusik/development_runner.py`,
  `git diff --check` — 통과
- dirty tracked roadmap, untracked required document, clean resume 회귀를
  `backend/tests/test_development_runner_roadmap.py`에 추가했습니다.
- 실제 운영 runner resume이나 dispatch는 실행하지 않았습니다.
