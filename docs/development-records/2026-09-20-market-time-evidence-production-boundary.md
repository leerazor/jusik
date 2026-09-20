# Market time-evidence production boundary

- 상태: 완료 (기술 slice); 기존 canonical readiness는 계속 차단
- 기록 시각: 2026-09-20T00:00:00Z
- 작업 slug: `market-time-evidence-production-boundary-20260920`
- 기준/통합: `d8cdb62` / 미통합
- 범위: 새 `market_research` 서비스 실행이 공식 calendar의 initial-capital anchor와 per-NAV evaluation timestamp를 저장하도록 경계를 추가했습니다. 기존 canonical run/replay artifact는 변경하지 않았습니다.

## 변경과 결정

- `ResearchEquityPoint.evaluation_at`과 `MarketResearchResult.initial_capital_at`을 legacy 호환 optional 필드로 추가했습니다.
- `market_time_evidence.attach_time_evidence()`가 새 service result에만 적용됩니다. US는 NMS, KR은 KRX session을 조회하고 NAV timestamp는 공식 close, anchor는 첫 공식 open 이전 event anchor로 저장합니다.
- timestamp가 일부만 있거나 역순이면 모델/readiness가 fail-closed합니다. 기존 artifact에 필드를 소급하거나 session 날짜만으로 canonical timestamp를 만들지 않습니다.
- readiness는 두 필드가 모두 검증된 새 run에서만 `missing_initial_capital_at`·`missing_nav_timestamps`를 제거합니다. 현재 canonical run은 legacy payload이므로 세 missing code가 그대로 남습니다.
- frozen R0 replay는 기존 strategy 경로와 결과 비교를 변경하지 않았습니다. 따라서 legacy replay identity를 보존합니다.

## 문서·계약 영향

- 사용자 문서: 기존 [`docs/forward-simulation-time-evidence.md`](../forward-simulation-time-evidence.md)의 legacy/canonical 분리 의미와 일치하며 별도 사용자 동작 변경은 없습니다.
- 운영 문서: runner resume·service/timer·PAPER/live는 변경하지 않았습니다.
- API·데이터 계약: 새 결과에는 optional causal fields가 포함될 수 있고, legacy 입력은 계속 읽힙니다. 기존 readiness 승격이나 성과 계산은 수행하지 않았습니다.

## 검증

- `pytest backend/tests/test_market_research.py backend/tests/test_market_performance_readiness.py backend/tests/test_market_time_evidence.py -q` — 72 passed.
- replay focused test는 현재 변경을 commit한 뒤 frozen dependency clean 상태에서 재검증합니다.
- Ruff check/format 및 변경 source strict mypy — 통과.

## 안전·운영 상태

- 새 research 실행·network·원본 DB·runner resume·주문·PAPER/live·remote push·Windows 종료는 수행하지 않았습니다.

## 증거와 재개

- 코드: `backend/jusik/market_time_evidence.py`, `market_history_models.py`, `market_research_service.py`, `market_performance_readiness.py`.
- 남은 차단 조건: 기존 canonical run은 새 optional fields가 없고, KOFR application evidence도 없습니다. 동일 canonical input으로 새 run을 별도 등록·검증해야 합니다.
- 다음 시작: commit 후 frozen replay와 canonical readiness를 다시 실행해 backward compatibility 및 기존 3개 missing code를 확인합니다.
