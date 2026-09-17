# R0 미국 세션 대사 근거

- 상태: 완료
- 기록 시각: 2026-09-17T00:00:00Z
- 작업 slug: `r0-us-session-evidence`
- 기준/통합: `1151035` / 통합 전
- 범위: canonical R0 미국 approximate run의 요청 기간 세션 날짜 대사와 readiness 진단만 변경했습니다. 성과 계산, 수집, 전략, runner, API, PAPER/live, 주문은 변경하지 않았습니다.

## 변경과 결정

- `backend/jusik/data/r0_us_session_evidence_v1.json`에 baseline manifest·run·tracked XNYS 달력의 전체 SHA 체인, provider/version, 현지 날짜 의미, 252/252 canonical digest와 제한사항을 고정했습니다.
- `backend/jusik/market_performance_readiness.py`는 canonical 경로에서만 증거 파일·달력 바이트·달력 payload 내부 hash·run 요청 기간·실제 equity 날짜를 재검증합니다. 검증 성공 시 `missing_calendar_evidence`와 `missing_session_completeness_evidence`만 제거하며, 상태는 계속 `blocked`/`ready_for_metrics=false`/`not-evaluated`입니다.
- generic 진단과 canonical identity 경계를 유지하고, 증거 부재·변조·SHA/기간/세션 불일치에는 fail-closed 오류를 반환합니다.

## 문서·계약 영향

- 사용자 문서: `docs/market-performance-metrics.md`에 canonical 세션 근거 계약과 실행 예를 추가했습니다.
- 운영 문서: 해당 없음. 서비스·DB·설정은 변경하지 않았습니다.
- API·설정·데이터 계약: readiness report에 검증된 `session_evidence` facts가 추가될 수 있으나 성과 입력 승격 계약은 바꾸지 않았습니다.

## 검증

- `PYTHONPATH=backend /home/kwl/projects/jusik/backend/.venv/bin/python -m pytest backend/tests/test_market_performance_readiness.py -q` — 기존 및 신규 focused 테스트 통과.
- canonical local acceptance — 고정 run과 tracked XNYS 달력에서 252/252, 누락·초과·중복·unavailable 0, 나머지 5개 누락 순서 확인.
- Ruff, mypy, 전체 관련 pytest는 최종 실행 결과를 통합 보고에 기록합니다.

## 안전·운영 상태

- 원본 run·달력·증거 파일은 읽기만 했으며 입력 파일을 변경하지 않았습니다.
- 네트워크, 연구 재실행, PAPER/live, 실제 주문, 운영 DB·서비스·원격 push는 수행하지 않았습니다.

## 증거와 재개

- tracked evidence: `backend/jusik/data/r0_us_session_evidence_v1.json`; evidence SHA-256은 코드에 고정되어 검증됩니다.
- 남은 작업·차단 조건: main 통합 전 독립 review와 통합 검증.
- 다음 시작: evidence/run/calendar SHA와 focused readiness 검사를 다시 실행한 뒤 통합합니다.
