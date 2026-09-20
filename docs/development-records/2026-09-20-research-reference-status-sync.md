# Research backend reference status sync

- 상태: 완료 (문서 동기화)
- 기록 시각: 2026-09-20T04:42:00Z
- 범위: `docs/research.md`의 canonical roadmap·mandate·runner 운영 상태 설명을 현재
  tracked 상태에 맞췄습니다. 코드, 연구 결과, 원장, 서비스, PAPER/live, 주문은 변경하지
  않았습니다.

## 결정

- `docs/research-mandate.json` bytes SHA-256은
  `22efba4714bc0baf65c56bdfd84dcdee91184a760a13d4d30c5a94486c264ab1`입니다.
- roadmap runner는 fail-closed 검증을 유지한 수동 `pause`/서비스 `inactive` 상태입니다.
- 기존 backend research reference와 investment-roadmap scope를 분리하는 설명은 유지하며,
  자동 PAPER/live 승격·실주문 금지는 변경하지 않았습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_research_mandate_governance.py
  backend/tests/test_development_runner.py -q` — `75 passed`.
- `git diff --check` 통과.
- 관련 변경은 `docs/research.md`, `docs/worktree-tasks.md`, 이 개발 기록뿐이며 비밀값은
  포함하지 않습니다.
