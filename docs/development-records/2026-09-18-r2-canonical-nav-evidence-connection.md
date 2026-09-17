# R2 canonical NAV evidence 연결

- 상태: 완료
- 기록 시각: 2026-09-18T00:00:00Z
- 작업 slug: `r2-canonical-nav-evidence-connection`
- 기준/통합: `aa6f715d007e410d89189c953d21f05edbf57867` / 통합 전
- 범위: 고정 R0 미국 run의 NAV residual, session calendar evidence, modeled-cost evidence를 하나의 canonical-only envelope로 연결했습니다. 일반 reconciliation과 readiness의 unavailable·blocked 의미는 유지했습니다.

## 변경과 결정

- `market_performance_readiness.py`에 `verify_canonical_session_evidence()`를 추가했습니다. 고정 run/evidence/manifest/calendar와 기간을 기존 private schema·canonical·session validator로 검증하고 identity/session facts만 반환합니다. whole readiness, policy, cost verifier를 호출하지 않습니다.
- `research_canonical_nav_reconciliation.py`는 고정 canonical run bytes를 bounded-read하고 `reconcile_json_bytes()`를 실행한 뒤 session verifier와 modeled-cost verifier를 각각 한 번 호출합니다. run·manifest·period·ordered 252 sessions·dataset SHA·106 trades·252 NAV를 fail-closed로 교차 결속합니다.
- envelope의 `residual`은 기존 행·잔차·실패 날짜를 보존합니다. `canonical.coverage`에서만 calendar·independent modeled accounting·KRW NAV source를 verified로 표시하고, `projection.digest`와 `accounting.digest`를 분리해 기록합니다.

## 문서·계약 영향

- 사용자 문서: `docs/research-nav-reconciliation.md`에 canonical adapter의 고정 입력·출력·종료 코드·보존 의미를 추가했습니다.
- 운영 문서: 해당 없음. 연구 재실행·네트워크·DB·서비스·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: 신규 stdout-only `r2-canonical-nav-evidence-connection/v1` envelope와 좁은 session verifier를 추가했습니다. 기존 generic CLI contract는 변경하지 않았습니다.

## 검증

- `python -m py_compile backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py` — 통과.
- `/tmp/jusik-r2-canonical-venv/bin/python -m pytest backend/tests/test_market_performance_readiness.py backend/tests/test_research_nav_reconciliation.py backend/tests/test_research_canonical_nav_reconciliation.py -q` — 71 passed.
- `/tmp/jusik-r2-canonical-venv/bin/python -m ruff check backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py backend/tests/test_research_canonical_nav_reconciliation.py` 및 동일 경로 `ruff format --check` — 통과.
- `/tmp/jusik-r2-canonical-venv/bin/python -m mypy --config-file backend/pyproject.toml backend/jusik/market_performance_readiness.py backend/jusik/research_canonical_nav_reconciliation.py` — 통과.
- `PYTHONPATH=backend /tmp/jusik-r2-canonical-venv/bin/python -m jusik.research_canonical_nav_reconciliation` — exit 0, 252 rows, 106 trades, residual failure 0.
- `git diff --check` — 통과.

## 안전·운영 상태

- canonical artifact는 읽기만 했습니다. 실제 주문, PAPER/live 실행, 연구 재실행, 네트워크, 운영 DB·서비스·원격 push는 수행하지 않았습니다.

## 증거와 재개

- audit: 없음; fixed run/evidence/manifest/dataset 경로와 SHA는 코드 상수 및 verifier chain으로 사용합니다.
- 남은 작업·차단 조건: 통합 agent가 독립 review와 main 통합 후 최종 SHA·검증 결과를 기록해야 합니다.
- 다음 시작: 통합 전용 검토에서 canonical acceptance, mismatch fail-closed, verifier call count와 generic regression을 재검증합니다.
