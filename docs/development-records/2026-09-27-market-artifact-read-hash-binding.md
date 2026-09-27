# Market artifact read hash binding

- 상태: 차단 (구현 완료, 런타임 검사 환경 미설치)
- 기록 시각: 2026-09-27T07:29:45Z
- 작업 slug: `market-artifact-read-hash-binding`
- 기준/통합: `fd999991b5b9bc251f5aa9e4929e516428c279c4` / 없음
- 범위: SQLite에서 반환한 artifact bytes의 SHA-256을 요청 key와 대조합니다. 손상 bytes는 고정된 비민감 오류로 거부하며 정상 반환과 없는 key의 `KeyError` 동작을 보존합니다.

## 변경과 결정

- `backend/jusik/market_history_store.py`: `get_artifact()`가 bytes를 반환하기 전에 digest를 확인하고, 불일치 시 `ValueError("stored market artifact failed SHA-256 verification")`를 발생시킵니다. 오류에는 bytes나 digest를 넣지 않습니다.
- `backend/tests/test_market_research.py`: 정상 bytes/content type 및 없는 key를 확인하고, temporary SQLite row 변조 뒤 store가 거부하며 download router가 성공 payload를 반환하지 않는지 검사합니다. API 코드는 바꾸지 않았습니다.
- `TestClient`의 예외 전달을 끈 HTTP regression은 generic 500 응답과 손상 bytes·digest의 미포함을 확인하도록 작성했습니다. 런타임 의존성 부재로 아직 실행되지 않았습니다.

## 문서·계약 영향

- 사용자 문서: 갱신 불필요. API 경로·성공 응답은 그대로이며, 손상 저장물은 이제 서버 오류로 실패합니다.
- 운영 문서: 갱신 불필요. 운영 데이터, 설정, 서비스는 건드리지 않았습니다.
- API·설정·데이터 계약: 변경 없음.

## 검증

- `python -m py_compile jusik/market_history_store.py tests/test_market_research.py` — 통과 (Python 3.13.15).
- `git diff --check` — 통과.
- `python -m pytest tests/test_market_research.py -q` — 실행 불가: 환경에 `pytest` 모듈이 없습니다.
- `python -m ruff check jusik/market_history_store.py tests/test_market_research.py` 및 `python -m ruff format --check jusik/market_history_store.py tests/test_market_research.py` — 실행 불가: 환경에 `ruff` 모듈이 없습니다.
- `python -m mypy jusik/market_history_store.py --strict` — 실행 불가: 환경에 `mypy` 모듈이 없습니다.
- 작업 워크트리에 프로젝트 가상환경이 없고 패키지 설치는 수행하지 않았습니다. 재개 조건은 격리된 backend dev 가상환경에 잠금/선언된 테스트 도구를 준비한 뒤 위 focused pytest, Ruff, strict mypy 검사를 실행하는 것입니다.

## 안전·운영 상태

- 임시 SQLite와 fixture만을 위한 테스트를 추가했습니다. 테스트는 현재 미실행입니다.
- 서비스·운영 DB·외부 API/데이터·credential·broker·주문·PAPER/live·비용·promotion을 사용하거나 변경하지 않았습니다.

## 증거와 재개

- audit: 없음; manifest: 없음; hash: 저장 경로의 SQLite row에만 테스트가 변조를 수행하도록 작성됨.
- 남은 작업·차단 조건: focused runtime/lint/type 검사 미실행. backend dev dependency environment가 준비되면 재개합니다.
- 다음 시작: 격리된 backend 가상환경에 프로젝트 개발 의존성을 준비하고 기록된 네 검증 명령을 실행합니다.
