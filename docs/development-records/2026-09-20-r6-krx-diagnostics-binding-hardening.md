# R6 KRX diagnostics 다중 entry binding hardening

- 상태: 기술 hardening 완료·한국 readiness insufficient 유지
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `r6-krx-diagnostics-binding-hardening-20260920`
- 기준/통합: `701623b` / 통합 예정
- 범위: legacy KRX cache manifest에서 entry key와 checkpoint가 독립 배열인 경우 잘못된 날짜·응답 결속을 방지했습니다. 단일 entry 진단은 유지하고, 다중 entry는 명시적 binding이 없으면 fail-closed로 표시합니다.

## 변경과 결정

- `CacheCheckpointBinding`을 추가해 새 cache write가 response key와 causal checkpoint를 명시적으로 함께 보존하도록 했습니다.
- `diagnose_krx_cache()`는 explicit binding을 우선 사용하고, legacy manifest의 다중 entry는 정렬된 `zip`으로 임의 결속하지 않고 `unbound:<key>`·`cache_integrity=false`로 보존합니다.
- 진단 결과에 요청·관측·누락 session과 `date_coverage`를 추가해 cache 내부 요청 범위의 날짜 대사를 명시합니다. 이는 provider 전체 기간 coverage나 PIT completeness를 의미하지 않습니다.
- 기존 manifest는 optional field omission으로 계속 읽히며, 날짜·board를 추정하지 않습니다.

## 후속 malformed-row 진단

- 통합 커밋 `7301cd1`에서 `KrxCacheDiagnosticEntry`와 `KrxCacheDiagnostics`에
  `malformed_rows`를 추가했습니다. JSON/envelope가 깨졌거나 `OutBlock_1`의 행 타입이
  잘못된 응답을 원문 내용으로 수치화하되, 기존 parser의 fail-closed 판정은 유지합니다.
- HTTP auth/비-2xx 응답은 행 malformed로 오인하지 않고 `0`으로 기록합니다. unbound cache
  entry도 행 손상과 구분해 `malformed_rows=0`으로 두고 parse failure·무결성 실패로 남깁니다.

## 문서·계약 영향

- 사용자 문서: 해당 없음. 읽기 전용 진단의 fail-closed 동작만 강화했습니다.
- 운영 문서: `docs/worktree-tasks.md`에 후속 hardening을 등록합니다.
- API·설정·데이터 계약: `checkpoint_bindings` optional field를 추가했습니다. legacy manifest는
  호환되지만 다중 entry 진단은 binding 없이는 승격되지 않습니다.

## 검증

- `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py -k 'krx_cache_diagnostic' -q` — `3 passed`.
- 후속 `backend/.venv/bin/python -m pytest backend/tests/test_market_data_collector.py -q` — `140 passed`.
- SEC/action/metrics 인접 회귀 묶음 — `179 passed`, 경고 2건.
- `backend/.venv/bin/python -m ruff check backend/jusik/market_data_collector.py backend/tests/test_market_data_collector.py` — 통과.
- `backend/.venv/bin/python -m mypy --strict backend/jusik/market_data_collector.py` — 통과.
- `git diff --check` — 통과.
- 후속 malformed-row 구현 후 collector 전체 pytest — `144 passed`; Ruff·strict mypy·diff
  검사 통과.
- 후속 aggregate 회귀 테스트 커밋 `0d68dd5`에서 cache 진단의 malformed row 합산 경로를
  고정했습니다. collector 전체 pytest는 `145 passed`로 재검증했습니다.
- 실제 cache CLI — requested/observed `2026-06-29`, missing `[]`, `date_coverage=complete`, zero/missing `29`, readiness `insufficient`, exit 2.

## 안전·운영 상태

- 실제 자료·원장·서비스·PAPER/live·실주문·remote push·Windows 종료를 수행하지 않았습니다.
- readiness는 기존 zero/missing OHLCV 및 provider coverage 부족으로 `insufficient`입니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260920-r6-krx-diagnostics-binding-hardening/report.json`; SHA-256 `6f54afb85d2b9343b296a544d5eb2cb165cac4da2c4ec42132ddf3ff4c624045`; 새 원시 자료 없음.
- 남은 작업·차단 조건: legacy manifest의 explicit entry/checkpoint binding과 전체 PIT coverage가 없으면 한국 경제 평가를 승격하지 않습니다.
- 다음 시작: KRX manifest binding 설계가 승인되거나, 더 우선인 R1 SEC manual review/FX·비용 자료 gate를 해소할 수 있는지 확인합니다.
