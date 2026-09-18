# Timestamp provenance 경로 정규화 보완

- 상태: 완료
- 기록 시각: 2026-09-18T17:05:00Z
- 작업 slug: `timestamp-provenance-path-fix`
- 기준/통합: `0742757` / 진행 중
- 범위: sanitized provenance의 `source/jusik/...` 경로를 승인 hash 대사에 정확히 연결했습니다. 외부 archive·전략·주문·PAPER는 변경하지 않았습니다.

## 변경과 결정

- `backend/jusik/research_signal_timestamp_forensics.py`가 provenance 경로에서 마지막 `jusik/`만 잘라 `source/` 접두사를 잃던 문제를 수정했습니다.
- `source/jusik` 쌍을 기준으로 canonical relative key를 만들며, 다른 경로 형식은 계속 fail-closed로 무시·검증합니다.

## 검증

- `backend/.venv/bin/python -m pytest -q backend/tests/test_research_signal_timestamp_forensics.py` — 8 passed.
- `backend/.venv/bin/python -m ruff check backend/jusik/research_signal_timestamp_forensics.py` — 통과.
- `backend/.venv/bin/python -m ruff format --check backend/jusik/research_signal_timestamp_forensics.py` — 통과.
- 기존 외부 frozen archive replay는 현재 달력 source hash가 과거 승인 hash와 달라 계속 fail-closed이며, 과거 artifact를 재서명하지 않았습니다.

## 안전·운영 상태

- 운영 DB·서비스·runner 설정·PAPER/live·브로커·원격 push 변경 없음.

## 증거와 재개

- 남은 작업: stale frozen archive는 별도 artifact migration/재승인 없이는 통과시키지 않습니다.
- 다음 시작: runner planner 결과와 전체 테스트의 남은 기존 hash/date drift를 읽고, 경제 경로에 직접 기여하는 최소 작업만 선택합니다.
