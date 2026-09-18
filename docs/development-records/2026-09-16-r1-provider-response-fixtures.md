# 공급자 응답 분류와 실패 cache 회귀

- 상태: 완료
- 기록 시각: 2026-09-16T04:07:34Z
- 작업 slug: `r1-provider-response-fixtures`
- 기준/통합: `b805841` / `e335342829a50cd56f57c782ec12edb25764bb72`
- 범위: collector의 공급자 응답 분류·검증 경계와 오프라인 회귀 fixture를 추가하고 독립 review에서 확인된 Alpha 일일 요청 한도와 Yahoo identity cache 경계를 보완했습니다. 기존 인증·예산·재시도, membership·product·event·accounting 집계 정책과 KRX 빈 거래일 처리를 보존했습니다.

## 변경과 결정

- `CollectorParseError`, `CollectorQuotaError`, `CollectorNullError`, `CollectorCoverageError`를 기존 `CollectorError` 계층 아래에 추가하고 인증·예산 예외 호환성을 유지했습니다.
- 알려진 공급자 오류 envelope는 고정 메시지로 분류하며 parser 경계에서 원문 예외 원인을 제거합니다.
- `HttpFetcher.get`의 validator가 fresh 응답 저장 전과 resume 반환 전에 같은 요청별 parser를 실행합니다. 실패 응답은 manifest와 raw cache에 저장하지 않습니다.
- Alpha의 명시적 `request limit` 문구는 quota로 분류하고 API key 언급만으로 auth·quota를 추정하지 않습니다.
- Network Yahoo 요청은 상위 admission row의 기대 exchange/currency를 fresh·resume validator에 전달해 identity 불일치 응답을 cache에 저장하거나 반환하지 않습니다. 기존 3인자 transport adapter 호출은 유지합니다.
- KRX의 명시적 `OutBlock_1: []`는 NetworkTransport에서 정상 no-trade 자료로 허용합니다. 17개 합성 fixture는 한 종목·한 세션·seed 0으로 고정했습니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-research.md` — 응답 분류, 검증 시점, no-trade 계약을 명시했습니다.
- 운영 문서: 해당 없음 — 수집·서비스·설정·원격 운영은 변경하지 않았습니다.
- API·설정·데이터 계약: collector 예외와 cache 검증 경계만 확장했으며 기존 성공 payload 구조는 유지했습니다.

## 검증

- `backend/.venv/bin/python -m pytest tests/test_market_data_collector.py tests/test_market_history_approximate.py -q` (backend cwd) — 143 passed, 2 dependency deprecation warnings; 2.15s.
- `backend/.venv/bin/python -m ruff check jusik/market_data_collector.py tests/test_market_data_collector.py` (backend cwd) — 통과; 0.02s.
- `backend/.venv/bin/python -m mypy jusik/market_data_collector.py` (backend cwd) — 통과; 0.30s.
- `backend/.venv/bin/python -m ruff format --check jusik/market_data_collector.py tests/test_market_data_collector.py` (backend cwd) — 기존 debt와 동일한 collector 3개·test 8개 hunk로 실패; 신규 hunk는 없습니다.
- 실행하지 않은 검사: 전체 저장소 검사와 실제 provider 수집은 범위 밖입니다.

## 안전·운영 상태

- HTTP와 sleep은 fixture/mock만 사용했습니다. 실제 provider 요청, 주문, PAPER/live, DB, service, 설정, remote push는 수행하지 않았습니다.

## 증거와 재개

- audit: `/home/kwl/.local/share/jusik/portfolio-audit/20260916-r1-06-518dc0fb`; manifest: `fixture-manifest.json`.
- 남은 작업·차단 조건: 독립 재검토와 local main 통합 검사가 통과했습니다. 경제 평가는 not-evaluated이며 R1 전체 완료를 의미하지 않습니다.
- 다음 시작: 이 slice의 추가 구현은 없습니다. 다른 체크리스트 착수는 별도 범위로 판단합니다.

## Astra 통합 및 독립 검토

- Terra가 Alpha 일일 요청 한도 분류와 Yahoo pre-cache identity 대조를 지적했고, Luna가 `6cb05a1`에서 수정했습니다. Terra 재검토는 PASS이며 추가 중요 지적이 없습니다.
- 최초 구현자 receipt 오타로 라우팅 감사가 실패했습니다. 해당 기록과 커밋을 보존하고 같은 worktree의 단일 소유자를 순차 교체했습니다. 후속 Luna 및 Terra model-only 전달 감사는 PASS이며 opaque message의 암호학적 무결성은 주장하지 않습니다.
- main 통합 후 pytest143·Ruff check·configured strict mypy가 통과했습니다. format diff는 기준 collector/test의 기존 부채와 정확히 일치합니다. 검사 명령과 실행 시간은 audit `integration-verification.json`과 원문 로그에 보존했습니다.
- 신규 fixture는 최종17개, seed0, 각1심볼/1세션입니다. HTTP/retry sleep은 mock 처리했습니다. 모든 검사는 단일 프로세스 순차 실행으로900초 한도 안입니다.
- 사용자 가시 경제 결과가 없는 회귀 검증 작업이므로 성과 catalog 및 웹 성과 공개는 해당 없음입니다. benchmark·미래 관찰 자료를 생성하거나 approximate를 승격하지 않았습니다.
- 증거·소스 snapshot·SHA manifest와 audit `HANDOFF.md`를 보관하고 해시를 검증한 후 해당 worktree/branch를 정리했습니다. 기존 루트 `HANDOFF.md`는 보존합니다.
