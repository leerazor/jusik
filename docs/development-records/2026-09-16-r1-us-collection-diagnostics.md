# R1-05 미국 수집 진단

- 상태: 완료
- 기록 시각: 2026-09-16T00:00:00Z
- 작업 slug: `r1-us-collection-diagnostics`
- 기준/통합: `d9ac948` / 없음
- 범위: 미국 Yahoo 수집 결과의 선택적 진단 계약, 심볼별 coverage 대사, 안전한 실패 직렬화와 관련 회귀 검증을 추가했습니다. 기존 membership·사건 cutoff·전략 선택·cache 계약은 유지했습니다.

## 변경과 결정

- `backend/jusik/market_history_approximate.py`에 `CollectionDiagnostics`와 심볼별 `CollectionCoverage` 계약을 추가했습니다. 요청 기간·warmup 시작·고정 reason code·expected/actual/missing/retained/event-excluded 대사를 보존하고, 기존 파일 입력에는 선택 필드로 호환됩니다.
- `backend/jusik/market_data_collector.py`는 parser가 검증한 고유 Yahoo 행만 actual로 집계합니다. identity mismatch는 `CollectorIdentityError`로 구분하며, 명시적이고 시간 순서가 확인된 delisting만 observed_delisting으로 기록합니다. 전체 Yahoo 실패에는 typed diagnostics를 `CollectorPartialError`에 첨부합니다.
- `backend/jusik/market_research_cli.py`는 전체 실패 JSON에 구조화 진단만 추가하고 종료 코드 2와 실패 cache 차단을 유지합니다.
- `docs/market-research.md`에 진단 분모·대사·unknown·delisting 정책을 기록했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md` — 선택적 진단 필드와 reason code를 설명했습니다.
- 운영 문서: 해당 없음 — 수집 endpoint·설정·서비스 운영은 바꾸지 않았습니다.
- API·설정·데이터 계약: prepared approximate dataset에 선택적 `collection_diagnostics`를 추가했으며 기존 파일은 계속 읽습니다.

## 검증

- `backend/.venv/bin/python -m pytest -q tests/test_market_data_collector.py tests/test_market_history_approximate.py` — 통과, 148건.
- `backend/.venv/bin/python -m mypy --config-file pyproject.toml jusik/market_history_approximate.py jusik/market_data_collector.py jusik/market_research_cli.py` — 통과.
- Ruff 실행은 전용 venv에 실행 binary가 없어 수행하지 못했습니다. 설치된 Python package가 binary 위치를 제공하지 않아 기존 format debt 비교도 별도 audit에 기록합니다.

## 안전·운영 상태

- 오프라인 합성 transport만 사용했습니다. 네트워크·GPU·PAPER/live·주문·운영 원장·서비스·설정·원격 push 변경은 없습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-05-eae146bd`; manifest: 기존 `code-manifest.json`과 검증 로그를 갱신해야 합니다.
- 남은 작업·차단 조건: Terra 독립 review와 Astra local main 통합이 남았습니다. 실제 원인 입력·benchmark·미래 관측 자료가 없어 경제 평가는 not-evaluated이며 R1-05 전체 checkbox는 감독이 보류합니다.
- 다음 시작: 독립 diff review에서 reason code·delisting cutoff·all-failure serialization을 확인한 뒤 통합 검증을 수행합니다.
