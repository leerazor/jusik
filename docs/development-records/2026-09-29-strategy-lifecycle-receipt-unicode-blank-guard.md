# Lifecycle receipt ID 공백 판정 일치

- 상태: 완료
- 기록 시각: `2026-09-29T02:10:14Z`
- 작업 slug: `strategy-lifecycle-receipt-unicode-blank-guard`
- 기준/통합: `7dfc9344cb154d84e511ef8b94ea4820914802f2` / `49433e58b1128ca6a047a9d37d852a6fba1f4d61`
- 범위: Python API, SQLite 직접 INSERT, 기존 DB 재개방, `verify()`가 receipt ID 공백을 같은 기준으로 판정하도록 수정했습니다. PAPER/live·brokerage·운영 DB·시장 자료·mandate는 바꾸지 않았습니다.

## 변경과 결정

- Python `str.strip()`이 제거하는 공백 코드포인트를 SQLite trigger에 맞췄습니다. `length(trim(...))`가 embedded NUL에서 길이 0을 반환하는 차이는 `trim(...) = ''` 판정으로 바로잡았습니다.
- 기존 SQLite CHECK가 `length(trim(...))`를 사용하는 receipt table은 단일 `BEGIN IMMEDIATE` transaction에서 재구성합니다. 기존 receipt 행을 모두 복사한 뒤 trigger를 다시 설치하며, 기존 공백 ID 행은 보존하되 신규 저장과 `verify()`에서는 거부합니다.
- trigger 재설치 실패 시 transaction rollback으로 이전 trigger를 보존합니다. 첫 독립 review가 찾은 trigger 교체 경합과 embedded NUL 오거부를 보정 커밋에서 해결했습니다.

## 문서·계약 영향

- 사용자 문서: 갱신하지 않았습니다. 내부 SQLite 무결성 기준이며 화면·사용자 흐름은 바뀌지 않습니다.
- 운영 문서: 갱신하지 않았습니다. 서비스·배포 동작은 바뀌지 않습니다.
- API·설정·데이터 계약: receipt ID의 내부 저장 무결성 기준을 Python `str.strip()`과 일치시켰습니다. 변경 내역은 작업 등록부와 이 기록에 보존했습니다.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_strategy_lifecycle_receipt.py` — 51 passed (task worktree와 통합 `main`에서 각각 통과).
- `backend/.venv/bin/ruff check backend/jusik/strategy_lifecycle_receipt.py backend/tests/test_strategy_lifecycle_receipt.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/strategy_lifecycle_receipt.py backend/tests/test_strategy_lifecycle_receipt.py` — 두 파일 형식 통과.
- `backend/.venv/bin/python -m mypy --strict --config-file backend/pyproject.toml backend/jusik/strategy_lifecycle_receipt.py backend/tests/test_strategy_lifecycle_receipt.py` — 두 파일 통과.
- `git diff --check` — 통과. 최종 변경에 대한 별도 `role.review` — PASS.

## 안전·운영 상태

- task-local SQLite와 synthetic fixture만 사용했습니다. 주문, PAPER/live, provider/API, credential, 유료 서비스, 운영 DB, 원격 push는 없었습니다.
- 검사 후 task worktree `/home/kwl/projects/jusik-strategy-lifecycle-receipt-unicode-blank-guard`를 정상 제거했습니다. 브랜치 `fix/strategy-lifecycle-receipt-unicode-blank-guard`와 통합 commit은 보존했습니다.
- 통합 `main` 체크아웃은 `/home/kwl/projects/jusik-strategy-lifecycle-receipt-unicode-integration`에 있습니다. 사용자 소유 루트 `HANDOFF.md`와 기존 handoff 브랜치는 수정하지 않았습니다.

## 증거와 재개

- 남은 작업·차단 조건: 이 bounded 작업에는 없습니다. trust-boundary 우선 결정은 사용자 결정 전까지 PENDING입니다.
- 다음 시작: 최신 handoff와 `docs/worktree-tasks.md`를 확인하고, trust-root 소유·통제 경계에 대한 사용자 결정을 받은 뒤에만 해당 구현을 계획합니다. 새 연구는 `docs/research-mandate.md`와 JSON을 먼저 확인합니다.
