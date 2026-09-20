# R7 source identity binding hardening

- 상태: 완료된 fail-closed 보강
- 범위: R7 isolation manifest가 caller-supplied identity만 저장해 실제
  retrospective source path/hash와 연결하지 않던 경계를 보완했습니다.

## 변경

- workspace manifest에 canonical source path→SHA-256 `source_hashes`를 저장합니다.
- 생성 시 계산한 source hash 집합과 identity hash 집합을 gate에서 비교하고,
  manifest의 각 source를 재해시해 변조·누락·symlink 경로를 차단합니다.
- source가 생성 후 변경되면 R7 gate는 `isolated_workspace_manifest_unavailable`로
  fail-closed 됩니다.

## 검증

- `pytest backend/tests/test_research_r7_isolation.py backend/tests/test_research_r7_gate.py -q`: 11 passed
- Ruff 변경 모듈·테스트: 통과
- `git diff --check`: 통과
- strict mypy: 기존 import 경로의 범위 밖 오류 10개로 실패했으며 새 진단은
  확인되지 않았습니다.

실제 simulation, PAPER/live, 주문, runner 재개, 원격 push와 Windows 종료는 없습니다.
