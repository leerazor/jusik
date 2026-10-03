# 공식 현금 배당 입력 동결

- 상태: 구현 완료, supervisor 통합·독립 검토 대기
- 기록 시각: 2026-10-03 UTC
- 작업 slug: `official-dividend-input-20261003`
- 기준/통합: `5b97061c0130f844ba78fc519a90fca33e779e11` / 없음
- 범위: 승인 종목의 현행 공식 배당 검토 사실을 독립 오프라인 JSON으로 검증·동결. 기존 검토 적격 판정·overlay·원장은 보존.

## 변경과 결정

- `backend/jusik/research_official_dividend_input.py`: 승인 목록의 전체 snapshot과 사건별 현재 공급자 revision/content SHA·최신 review ID를 검증한다. 저장된 payload SHA, 검토 내용 hash/ID, 공식 원문 bytes SHA, 신원 근거 파일 SHA와 URL을 재검증한다. 금액 외 비교 충돌·필수 사실 결손을 거부하고 금액 충돌은 원래 strict status와 정확한 Decimal 차액을 보존한다.
- 출력은 canonical JSON의 전체 bytes SHA 파일명과 O_EXCL로 동결한다. 기존 파일은 byte 일치 시만 재사용한다. 후향/PIT·원장·NAV 플래그를 명시한다.
- SQLite 두 DB 간 원자적 snapshot은 없으므로 별도 복사본을 권장하고, 두 번의 새 읽기 transaction으로 pin 변화를 재검사한다. 검토자의 신원 판단과 원문 의미를 자동 입증하지 않는다.

## 문서·계약 영향

- 사용자·입력 계약: `docs/research.md`에 manifest v1 예시, CLI 호출, 산출물 의미와 신뢰 경계를 추가했다.
- 운영 문서/API: 변경 없음. 오프라인 CLI이며 서비스·UI는 연결하지 않았다.

## 검증

- `PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests/test_research_official_dividend_input.py` — 18건 통과. 일치·금액 충돌·idempotence·pin/원문/신원/날짜/통화/주당 기준 오류를 포함.
- `RUFF_CACHE_DIR=/tmp/ruff-official backend/.venv/bin/ruff check backend/jusik/research_official_dividend_input.py backend/tests/test_research_official_dividend_input.py` — 통과.
- `MYPY_CACHE_DIR=/tmp/mypy-official PYTHONPATH=backend backend/.venv/bin/mypy --strict backend/jusik/research_official_dividend_input.py` — 통과.
- 기존 overlay focused 회귀 포함 23건 통과(API/endpoint 1건은 의도적으로 제외). 실제 MSFT 12건 사본 최종 대사는 supervisor 통합 단계에서 수행.

## 안전·운영 상태

- 별도 워크트리에서 코드·문서만 변경. 운영 DB, PAPER·실주문, 서비스, 배포, 원격 push는 변경하지 않았다.

## 증거와 재개

- supervisor 제공 DB 사본과 manifest: `/tmp/official-dividend-msft/`. 이 경로는 임시 검증 자료이며 저장소에 포함하지 않는다.
- 다음 시작: 독립 코드 검토와 실제 MSFT 사본 재실행·기존 overlay 회귀 후 로컬 main에 통합한다.
- workflow 판단: 도움 됨 — 기존 모델·검토/수집 DB 계약을 재사용했다.
- 근거: synthetic focused 18건 통과; 시간·비용 절감은 미측정.
- 다음 조정: 유지 — 새 원장이나 서비스 연결 없이 동결 입력 경계만 검증한다.
