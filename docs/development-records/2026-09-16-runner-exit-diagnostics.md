# Codex 종료 진단

- 상태: 검증 대기
- 기록 시각: 2026-09-16T03:22:01Z
- 작업 slug: `runner-exit-diagnostics`
- 기준/통합: `ca493eb` / 없음
- 범위: 연구 task의 nonzero `codex_exit` 시도에 private 진단 sidecar를 기록하고 재시도 prompt를 보강했습니다. 기존 상태·스키마·retry 정책과 비연구 경로는 보존했습니다.

## 변경과 결정

- `backend/jusik/development_runner.py`는 `attempt/exit-diagnostics.json`에 signed return code, 음수 코드에 대한 signal number, completion 파일 존재 여부만 기록합니다.
- 상태를 먼저 `failed`/`codex_exit`로 저장한 뒤 sidecar를 best effort로 기록하므로 sidecar `OSError`가 실패 상태를 가리지 않습니다.
- retry prompt는 이전 task registry, 소유 worktree, artifact를 확인하고 일치하는 소유 branch를 재사용하도록 안내합니다.

## 문서·계약 영향

- 사용자 문서: [development-runner.md](../development-runner.md)에 private exit 진단과 실패 처리 동작을 기록했습니다.
- 운영 문서: 해당 없음. 실행기 설치·서비스 운영 절차는 바뀌지 않았습니다.
- API·설정·데이터 계약: SQLite 스키마와 상태·retry 계약은 바뀌지 않았습니다.

## 검증

- `backend/.venv/bin/pytest -q backend/tests/test_development_runner.py` — 통과 (50 passed).
- `backend/.venv/bin/ruff format --check backend/jusik/development_runner.py backend/tests/test_development_runner.py` — 통과.
- `backend/.venv/bin/ruff check backend/jusik/development_runner.py backend/tests/test_development_runner.py` — 통과.
- `PYTHONPATH=backend backend/.venv/bin/python -m mypy --strict backend/jusik/development_runner.py` — 통과.
- 실행하지 않은 검사: 전체 pytest, PAPER 실행, 실 CLI 실패 시뮬레이션은 범위 밖입니다.

## 안전·운영 상태

- 실주문, 서비스 상태, 데이터베이스 스키마, 원격 push, 전역 설정 변경은 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 없음.
- 남은 작업·차단 조건: focused 검증과 parent 통합 검토가 남아 있습니다.
- 다음 시작: 허용된 실행기 테스트와 Ruff·mypy를 실행해 sidecar 및 기존 pause/timeout/completion 회귀를 확인합니다.
