# Market artifact read hash binding

- 상태: 완료 (검증·독립 review·local main 통합 완료)
- 기록 시각: 2026-09-27T07:35:57Z
- 작업 slug: `market-artifact-read-hash-binding`
- 기준/통합: `fd999991b5b9bc251f5aa9e4929e516428c279c4` / `5903dc2275c6a47fb2012633770461bdc0724c65`
- 범위: SQLite에서 반환한 artifact bytes의 SHA-256을 요청 key와 대조합니다. 손상 bytes는 고정된 비민감 오류로 거부하며 정상 반환과 없는 key의 `KeyError` 동작을 보존합니다.

## 변경과 결정

- `backend/jusik/market_history_store.py`: `get_artifact()`가 bytes를 반환하기 전에 digest를 확인하고, 불일치 시 `ValueError("stored market artifact failed SHA-256 verification")`를 발생시킵니다. 오류에는 bytes나 digest를 넣지 않습니다.
- `backend/tests/test_market_research.py`: 정상 bytes/content type 및 없는 key를 확인하고, temporary SQLite row 변조 뒤 store가 거부하며 download router가 성공 payload를 반환하지 않는지 검사합니다. API 코드는 바꾸지 않았습니다.
- `TestClient`의 예외 전달을 끈 HTTP regression은 generic 500 응답과 손상 bytes·digest의 미포함을 확인합니다.
- 구현 commit: `c9533f97b4dbc9c1aca7472e2b75546c18892b6f`. 독립 reviewer 결과: PASS, 추가 수정 요청 없음.

## 문서·계약 영향

- 사용자 문서: 갱신 불필요. API 경로·성공 응답은 그대로이며, 손상 저장물은 이제 서버 오류로 실패합니다.
- 운영 문서: 갱신 불필요. 운영 데이터, 설정, 서비스는 건드리지 않았습니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- 작업 전용 backend 가상환경을 Python 3.13으로 만들고 잠금 의존성을 로컬 cache에서 설치했습니다. 네트워크 접근이나 전역 설치는 없었습니다.
- 통합 main에서 `backend/.venv/bin/python -m pytest -q backend/tests/test_market_research.py` — 33 passed (기존 dependency deprecation warning 2개).
- Ruff check 및 format check (변경 source/test) — 통과.
- `.venv/bin/mypy --strict jusik/market_history_store.py` — 통과.
- `.venv/bin/mypy --strict tests/test_market_research.py` — 기존 unused `type: ignore` 2건으로 실패 (해당 줄은 이번 변경 범위 밖).
- `git diff HEAD^ HEAD --check` — 통과.

## 안전·운영 상태

- 임시 SQLite와 fixture만을 위한 테스트를 추가하고 실행했습니다. test DB는 임시 경로에서만 사용했습니다.
- 서비스·운영 DB·외부 API/데이터·credential·broker·주문·PAPER/live·비용·promotion을 사용하거나 변경하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 저장 경로의 SQLite row에만 테스트가 변조를 수행하도록 작성됨.
- 남은 작업·차단 조건: 구현 task는 없습니다. 전체 test-module strict mypy의 기존 unused ignore 이슈는 별도 기존 부채입니다. artifact 저장 경로의 digest conflict guard는 독립 task로 재현되어 별도 등록합니다.
- 다음 시작: `market-artifact-write-conflict-guard`에서 신규 저장·동일 bytes 재저장·충돌 시 거부 및 원본 보존·충돌 후 service 전략 미호출을 검증합니다. `FINAL_VALIDATION`/OOS는 사전등록 freeze와 이후 적격·미노출 미래자료 전까지 PENDING/BLOCKED입니다.
