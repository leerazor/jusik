# Market snapshot read hash binding

- 상태: 구현·검증 완료, 통합 대기
- 기록 시각: 2026-09-27T07:19:03Z
- 작업 slug: `market-snapshot-read-hash-binding`
- 기준/통합: `b0b28fa7a1e3ae918265f74181831268e80071c2` / local `main` fast-forward `32771f4f35d75cc23c554520b4a5c661e117c77b`
- 범위: snapshot 조회 시 row 본문과 requested key의 canonical hash 일치를 강제하고 SQLite fixture 회귀 테스트를 추가했습니다. 스키마와 저장 데이터는 변경하지 않았습니다.

## 변경과 결정

- `MarketHistoryStore.get_snapshot`가 Pydantic 모델을 복원한 다음 계산된 `snapshot.input_hash`와 조회 키를 비교합니다. 불일치 시 해시값이나 본문을 노출하지 않는 `ValueError`로 fail closed 합니다.
- 정상 roundtrip과 absent key의 `KeyError` 보존을 확인하고, 정상 schema의 변경된 source artifact 및 snapshot field가 원래 key에 저장된 경우 각각 거부되는지 검사합니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 사용자 흐름은 바뀌지 않습니다.
- 운영 문서: 해당 없음.
- API·설정·데이터 계약: schema·API 형식·저장 형식 변경은 없습니다. 손상되거나 서로 다른 key에 바인딩된 snapshot row 조회 동작만 거부합니다.

## 검증

- `backend/.venv/bin/python -m pytest -q backend/tests/test_market_research.py` — 32 passed; 기존 의존성 deprecation warning 2개.
- `backend/.venv/bin/ruff check backend/jusik/market_history_store.py backend/tests/test_market_research.py` — 통과.
- `backend/.venv/bin/ruff format --check backend/jusik/market_history_store.py backend/tests/test_market_research.py` — 통과.
- `backend/.venv/bin/mypy --strict jusik/market_history_store.py` — 통과.
- `backend/.venv/bin/mypy jusik --strict` — 실패: 이 격리 venv에 선택 의존성 `pyarrow`와 `torch`가 없어 기존 `research_marketparquet.py` 및 `research_optimizer.py`에서 4개 오류.
- `backend/.venv/bin/mypy --strict tests/test_market_research.py` — 기존 45·317행의 unused `type: ignore` 2개로 실패; 수정 범위 밖입니다.
- `git diff --check` — 통과.
- 선택 의존성은 네트워크 없이 설치한 task-local `backend/.venv`에 없으며, 이를 위해 네트워크나 데이터 접근을 수행하지 않았습니다.
- 독립 read-only code review — PASS, 수정 필요 없음. 정상 roundtrip, schema-valid artifact/metadata 변형, absent-key `KeyError`, 민감 정보가 없는 오류를 확인했습니다.
- 통합 main에서 `backend/.venv/bin/python -m pytest -q backend/tests/test_market_research.py` — 32 passed, 기존 dependency deprecation warning 2개; 변경 파일 Ruff check/format과 `jusik/market_history_store.py` strict mypy, `git diff HEAD^ HEAD --check`도 통과했습니다.

## 안전·운영 상태

- 임시 SQLite와 fixture만 사용했습니다. 네트워크/API, 자격증명, 운영 DB, PAPER/live, 주문, 배포, 원격 push 변경은 없습니다.
- 이 저장 무결성 수정은 과거 KRX run/export binding을 복구하지 않으며 PIT 적격성을 입증하거나 승격하지 않습니다.
- 독립 review와 통합 검증 후 작업 worktree를 clean 상태에서 제거했고 local branch/commit은 보존했습니다. 사용자 소유 루트 `HANDOFF.md`는 미수정입니다.

## 증거와 재개

- audit: 별도 audit 산출물 없음; 회귀 fixture와 `tmp_path` SQLite 테스트만 사용.
- 남은 작업·차단 조건: 없음. 전체 strict mypy 및 test module strict mypy의 위 환경/기존 annotation 제한은 구현 모듈 type check와 focused tests 통과를 무효화하지 않지만 완전한 suite type-check로 보고하지 않습니다.
- 다음 시작: 후속 task가 있으면 작업 등록부의 별도 범위와 worktree에서 이어갑니다. 이 변경은 과거 KRX prepared export와 run의 provenance binding을 복구하지 않습니다.
