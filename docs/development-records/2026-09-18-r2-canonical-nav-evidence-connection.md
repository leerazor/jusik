# R2 canonical NAV evidence 연결

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `r2-canonical-nav-evidence-connection`
- 기준/통합: `aa6f715d007e410d89189c953d21f05edbf57867` / `3af356aca45361acf3c193f4c71405fd3210233c`
- 범위: 고정 R0 미국 run의 NAV residual, session calendar evidence, modeled-cost evidence를 하나의 canonical-only envelope로 연결했습니다. 일반 reconciliation과 readiness의 unavailable·blocked 의미는 유지했습니다.

## 변경과 결정

- `market_performance_readiness.py`에 `verify_canonical_session_evidence()`를 추가했습니다. 고정 run/evidence/manifest/calendar와 기간을 기존 private schema·canonical·session validator로 검증하고 identity/session facts만 반환합니다. whole readiness, policy, cost verifier를 호출하지 않습니다.
- `research_canonical_nav_reconciliation.py`는 고정 canonical run bytes를 bounded-read하고 `reconcile_json_bytes()`를 실행한 뒤 session verifier와 modeled-cost verifier를 각각 한 번 호출합니다. run·manifest·period·ordered 252 sessions·dataset SHA·106 trades·252 NAV를 fail-closed로 교차 결속합니다.
- envelope의 `residual`은 기존 행·잔차·실패 날짜를 보존합니다. `canonical.coverage`에서만 calendar·independent modeled accounting·KRW NAV source를 verified로 표시하고, `projection.digest`와 `accounting.digest`를 분리해 기록합니다.
- review 보완으로 session verifier의 symlink/path alias를 거부하고, readiness manifest/calendar와 실제 cost verifier가 접근하는 파일을 artifact별 `limit+1` bounded-read로 검증합니다. self-pinned cost verifier source SHA와 cost evidence의 verifier-source/evidence SHA를 기존 chain 절차로 갱신했으며 canonical run/result bytes는 변경하지 않았습니다.
- 갱신된 cost verifier source SHA는 `df05cdd4d9cbbc5620549357d043ff4d0a146c73de03f6decb7ecb676ae5c652`, tracked cost evidence bytes SHA는 `6f53848cefc0935f7112fa2c518606aa6e41485404456910272ef3a9511484d6`입니다. evidence의 run·dataset·manifest·cache artifact SHA와 accounting digest는 재계산 없이 보존했습니다.
- verifier source와 cache raw member의 부재는 각각 `verifier_unavailable`, `cache_raw_unavailable`로 보존하며, oversize는 artifact별 `*_too_large`로 구분합니다.

## 문서·계약 영향

- 사용자 문서: `docs/research-nav-reconciliation.md`에 canonical adapter의 고정 입력·출력·종료 코드·보존 의미를 추가했습니다.
- 운영 문서: 해당 없음. 연구 재실행·네트워크·DB·서비스·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 신규 stdout-only `r2-canonical-nav-evidence-connection/v1` envelope와 좁은 session verifier를 추가했습니다. 기존 generic CLI contract는 변경하지 않았습니다.

## 검증

- `python -m py_compile backend/jusik/market_performance_cost_evidence.py backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py` — 통과.
- `/tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_market_performance_cost_evidence.py backend/tests/test_market_performance_readiness.py backend/tests/test_research_nav_reconciliation.py backend/tests/test_research_canonical_nav_reconciliation.py -q` — 114 passed.
- `/tmp/jusik-r2-canonical-venv/bin/python -m ruff check backend/jusik/market_performance_cost_evidence.py backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py backend/tests/test_market_performance_cost_evidence.py backend/tests/test_research_canonical_nav_reconciliation.py` 및 동일 경로 `ruff format --check` — 통과.
- `/tmp/jusik-r2-canonical-venv/bin/python -m mypy --config-file backend/pyproject.toml backend/jusik/market_performance_cost_evidence.py backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py` — 통과.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m jusik.market_performance_cost_evidence --canonical` — exit 0, verified 106 trades / 252 sessions / zero residual.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m jusik.research_canonical_nav_reconciliation` — exit 0, 252 rows, 106 trades, residual failure 0.
- `_canonical_source_hash()` 및 tracked evidence bytes가 각각 `VERIFIER_SOURCE_SHA256` / `CANONICAL_EVIDENCE_SHA256`와 일치 — 통과.
- `git diff --check` — 통과.
- local `main`에서 동일 focused pytest — 114 passed. Ruff check/format, strict mypy, 두 canonical CLI, `git diff --check`가 모두 통과했습니다.
- Terra 독립 최종 review — P1/P2 없음, PASS. 경로 별칭, 실제 consumer bounded-read, self-pin, stable unavailable error code를 재검토했습니다.

## 안전·운영 상태

- canonical artifact는 읽기만 했습니다. 실제 주문, PAPER/live 실행, 연구 재실행, 네트워크, 운영 DB·서비스·원격 push는 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; fixed run/evidence/manifest/dataset 경로와 SHA는 코드 상수 및 verifier chain으로 사용합니다.
- 남은 작업·차단 조건: 이 연결 범위에는 없음. 배당 완전성·실제 비용 타당성·무위험률·실제 NAV timestamp·benchmark·미래 검증은 별도 근거가 필요합니다.
- 다음 시작: roadmap/readiness에서 현재 남은 blocker를 다시 대조하고 외부 요청이나 연구 재실행 없이 가능한 다음 최소 작업을 선정합니다.
