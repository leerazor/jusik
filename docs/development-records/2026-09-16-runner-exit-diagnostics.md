# Codex 종료 진단

- 상태: 완료
- 기록 시각: 2026-09-16T03:31:34Z
- 작업 slug: `runner-exit-diagnostics`
- 기준/통합: `ca493eb` / `269a34d3e965e82cb36c9baac4c6eb18b2d2d835`
- 범위: 연구 task의 nonzero `codex_exit` 시도에 private 진단 sidecar를 기록하고 재시도 prompt를 보강했습니다. 기존 상태·스키마·retry 정책과 비연구 경로는 보존했습니다.

## 변경과 결정

- `backend/jusik/development_runner.py`는 `attempt/exit-diagnostics.json`에 signed return code, 음수 코드에 대한 signal number, completion 파일 존재 여부만 기록합니다.
- 상태를 먼저 `failed`/`codex_exit`로 저장한 뒤 sidecar를 best effort로 기록하므로 sidecar `OSError`가 실패 상태를 가리지 않습니다.
- retry prompt는 이전 task registry, 소유 worktree, artifact를 확인하고 일치하는 소유 branch를 재사용하도록 안내합니다.
- roadmap runner fixture는 live checklist 진행 상태와 무관하게 R0 완료·R1-R7 미완료 기준을 사용하며, 실제 tracked roadmap 문서의 내용과 checkmark는 변경하지 않습니다.

## 문서·계약 영향

- 사용자 문서: [development-runner.md](../development-runner.md)에 private exit 진단과 실패 처리 동작을 기록했습니다.
- 운영 문서: 해당 없음. 실행기 설치·서비스 운영 절차는 바뀌지 않았습니다.
- API·설정·데이터 계약: SQLite 스키마와 상태·retry 계약은 바뀌지 않았습니다.

## 검증

- `backend/.venv/bin/pytest -q backend/tests/test_development_runner.py backend/tests/test_development_runner_planning.py backend/tests/test_development_runner_roadmap.py` — 통과 (84 passed).
- `backend/.venv/bin/ruff format --check backend/jusik/development_runner.py backend/tests/test_development_runner.py backend/tests/test_development_runner_roadmap.py` — 통과.
- `backend/.venv/bin/ruff check backend/jusik/development_runner.py backend/tests/test_development_runner.py backend/tests/test_development_runner_roadmap.py` — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict backend/jusik/development_runner.py backend/jusik/development_runner_roadmap.py` — 통과.
- 실행하지 않은 검사: 전체 pytest, PAPER 실행, 실 CLI 실패 시뮬레이션은 범위 밖입니다.

## 안전·운영 상태

- 실주문, 서비스 상태, 데이터베이스 스키마, 원격 push, 전역 설정 변경은 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-roadmap-recovery`; manifest: `runner-integration.json`; source hash와 원본 검사 결과는 `runner-source/`, `runner-final/`에 보존합니다.
- 남은 작업·차단 조건: 없음. 과거 CLI 종료 원인은 누락된 종료 코드를 소급 생성하지 않아 미확정으로 유지합니다.
- 다음 시작: 복구 작업 완료 뒤 자동 실행을 재개하고 새 비정상 종료가 있으면 private exit-diagnostics.json부터 확인합니다.

## 통합 검증 (2026-09-16T03:34:52.215623+00:00)

main에서 실행기·planner·roadmap pytest84, 관련 Ruff check/format 및 strict mypy2 source가 통과했습니다. 최초 통합의 3개 실패는 실제 로드맵 진행을 읽던 테스트 fixture 때문이었으며 임시 복사본 상태를 고정해 해결했습니다. 실제 로드맵 체크는 바꾸지 않았습니다. 독립 Terra 재검토는 P1/P2 없음입니다.
